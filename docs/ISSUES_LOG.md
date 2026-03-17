# ISSUES_LOG.md

---

## Issue 1: Git Tracking WSL Virtual Environment

**Problem**
The WSL Python virtual environment (`.venv/`) was being treated by Git as a tracked or tracked-candidate directory, contributing to 1000+ stray file entries appearing in `git status`.

**Context**
File: `.gitignore`, `.venv/` directory at repo root.
The `.venv/` is used by WSL to run `spark_job.py` and must remain on disk but must NOT be committed to the repository.

**Error / Logs**
```
git status showing 1k+ entries many of which were inside .venv/
```

**Root Cause**
While `.venv/` was already listed in `.gitignore`, the ignore patterns did not cover all possible venv naming conventions (`venv/`, `env/`, nested paths). Additionally `git rm --cached` had not been run to remove any previously indexed entries.

**Resolution**
1. Expanded `.gitignore` with comprehensive venv patterns:
   ```
   .venv/
   venv/
   env/
   **/.venv/
   **/venv/
   **/env/
   ```
2. Ran `git rm -r --cached --ignore-unmatch -- .venv venv env` to remove all cached entries without deleting local files.
3. Verified: `git ls-files | Select-String '(^|/)(\.venv|venv|env)(/|$)'` → empty output.

**Status**: RESOLVED

---

## Issue 2: Spark Binary Distribution Appearing in `git status`

**Problem**
The local Spark 3.5.1 binary distribution (`spark-3.5.1-bin-hadoop3/`) and its archive (`spark-3.5.1-bin-hadoop3.tgz`) were showing up as untracked in `git status`, causing 1000+ noisy entries.

**Context**
File: `.gitignore`.
The `spark-3.5.1-bin-hadoop3/` directory is a local installation required to run the Spark streaming job under WSL. It should never be committed to the repository.

**Error / Logs**
```
?? spark-3.5.1-bin-hadoop3/
?? spark-3.5.1-bin-hadoop3.tgz
```

**Root Cause**
Neither the Spark directory nor its `.tgz` archive were listed in `.gitignore`. They were untracked but visible, creating the false impression of thousands of pending changes.

**Resolution**
Added to `.gitignore`:
```
spark-3.5.1-bin-hadoop3/
spark-3.5.1-bin-hadoop3.tgz
```

After saving, `git status` no longer showed either entry.

**Status**: RESOLVED

---

## Issue 3: Spark Job Hadoop Native Library Warning

**Problem**
When running `spark_job.py` under WSL, Spark emits warnings about native Hadoop libraries not being available.

**Context**
File: `src/streaming/spark_job.py`, `_create_spark_session()`.
Running in `local[*]` mode on Windows/WSL without a full Hadoop native library installation.

**Error / Logs**
```
WARN NativeCodeLoader: Unable to load native-hadoop library for your platform…
```

**Root Cause**
Spark attempts to load platform-native Hadoop IO libraries. They are absent in the local WSL environment. Spark falls back to Java implementations automatically.

**Resolution**
Added to SparkSession config:
```python
.config("spark.hadoop.io.native.lib.available", "false")
.config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem")
.config("spark.hadoop.fs.file.impl.disable.cache", "true")
```
This explicitly disables native lib lookup and forces the RawLocalFileSystem implementation, suppressing the warning and improving local mode stability.

**Status**: RESOLVED (workaround applied)

---

## Issue 4: Training-Serving Feature Skew Risk

**Problem**
If offline training and online streaming used different feature engineering logic or different feature orders, the XGBoost model would silently produce garbage predictions — a classic training-serving skew bug.

**Context**
Files: `src/data/feature_builder.py`, `src/ml/train_baseline.py`, `src/streaming/spark_job.py`.

**Root Cause**
Potential for divergence between pandas-based offline feature computation and Spark UDF-based online feature computation.

**Resolution**
- Centralized `FEATURE_COLUMNS` list in `feature_builder.py` as single source of truth for both paths
- Model saved as a bundle `{"model": ..., "features": FEATURE_COLUMNS}` so feature ordering is embedded in the artifact
- `_build_prediction_udf` in `spark_job.py` enforces `features_df = features_df[features]` to align to bundle order
- `_ensure_feature_columns` in `spark_job.py` guards against missing columns in streaming batches by filling with `0.0`

**Status**: RESOLVED (by design)

---

## Issue 5: Legacy Model Artifact Compatibility

**Problem**
Older model artifacts saved as a raw `XGBRegressor` object would break `predict_batch()` if the code expected a bundle dict `{"model": ..., "features": ...}`.

**Context**
File: `src/ml/model_io.py`.

**Root Cause**
Model artifact format evolved from raw estimator to bundle dict, but old `.joblib` files still exist on disk or could be shared across environments.

**Resolution**
`load_model()` in `model_io.py` detects format via `_is_bundle()`:
```python
def _is_bundle(obj: Any) -> bool:
    return isinstance(obj, dict) and "model" in obj and "features" in obj
```
Legacy raw estimators are auto-wrapped on load:
```python
if not _is_bundle(loaded):
    bundle = {"model": loaded, "features": FEATURE_COLUMNS}
```

**Status**: RESOLVED (by design)

---

## Issue 6: Duplicate Hourly Metrics in Parquet Sink

**Problem**
Spark Structured Streaming with microbatch processing and checkpointing can re-emit the same hourly window multiple times, causing duplicate rows in the parquet sink that would corrupt drift detection statistics.

**Context**
File: `src/streaming/spark_job.py`, `_build_hourly_metrics()`.

**Root Cause**
Spark's `append` output mode with watermark-based windowing can emit early partial results for a window before all data arrives, then emit updated results — leading to multiple rows for the same `timestamp_hour`.

**Resolution**
Applied `dropDuplicates(["timestamp_hour"])` on the formatted partition column before writing:
```python
deduped_hourly_metrics_df = (
    hourly_metrics_df
    .withColumn("timestamp_hour", F.date_format(F.col("timestamp_hour"), "yyyy-MM-dd-HH"))
    .dropDuplicates(["timestamp_hour"])
)
```
Output partitioned by `timestamp_hour` to align physical files with logical windows.

**Status**: RESOLVED (by design)

---

## Issue 7: Drift Detector Fails With Empty Windows

**Problem**
If `data/metrics/hourly_metrics/` has no parquet files, or if one of the time windows (baseline or recent) is empty, the drift detector raises an unhandled exception.

**Context**
File: `src/drift_detection/drift_detector.py`.

**Root Cause**
Early-stage development: Spark job may not have run long enough to populate both a 24-hour recent window AND a 7-day baseline window. Or `data/metrics/hourly_metrics/` directory is empty.

**Error / Logs**
```
FileNotFoundError: No hourly metrics parquet files found in: ...
ValueError: Baseline window (previous 7 days) contains no data
ValueError: Recent window (last 24 hours) contains no data
```

**Resolution**
Explicit guard conditions were implemented in `_load_hourly_metrics()` and `_compute_drift_report()`:
- Raises `FileNotFoundError` if no parquet files found
- Raises `ValueError` for each empty window with descriptive message
- These propagate cleanly and are printed to structured logs

**For development testing**: Drift detector cannot be meaningfully tested without at least ~25 hours of streaming data in `data/metrics/hourly_metrics/`. Use historical replay via `kafka_producer.py` with a higher rate (lower `--sleep-seconds`) to populate faster.

**Status**: HANDLED (raises informative errors; not yet silently graceful)
