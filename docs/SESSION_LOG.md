# SESSION_LOG.md

> Append a new session entry after every development session. This serves as long-term project memory.

---

## Session 1 8 Pre-March 2026 (Approximate)

**Work Done**
- Set up project repository structure:
  - `src/common/` — config loader, structured logger, shared schemas
  - `src/data/` — offline preprocessing + feature builder
  - `configs/base.yaml` and `configs/dev.yaml` with deep-merge architecture
- Installed project dependencies: `requirements.txt`

**Issues Encountered**
- None recorded at this stage.

**Resolution**
- N/A

**Next Steps**
- Implement data preprocessing pipeline
- Train baseline model

---

## Session 2 — 9-11 March 2026 (Approximate)

**Work Done**
- Implemented `src/data/offline_preprocess.py`:
  - Loaded PJM CSV (`hrl_load_metered-2018.csv`)
  - Normalized columns, parsed timestamps, dropped nulls, sorted chronologically
  - Wrote `pjm_cleaned.parquet` and `pjm_supervised.parquet`
- Implemented `src/data/feature_builder.py`:
  - Defined canonical `FEATURE_COLUMNS` list
  - Pandas-based offline feature functions
  - Spark-compatible `add_time_features_spark()` for streaming parity

**Issues Encountered**
- Column naming inconsistency in CSV (`Datetime Beginning EPT` vs `datetime_beginning_ept`)
- Needed deterministic sort by group + timestamp to prevent feature leakage

**Resolution**
- Preprocessing normalizes all column names before any operations
- Deterministic sort enforced in feature_builder

**Next Steps**
- Train baseline XGBoost model
- Build Kafka producer

---

## Session 3 — 9-11 March 2026 (Approximate)

**Work Done**
- Implemented `src/ml/train_baseline.py`:
  - XGBoost regressor, chronological 80/20 split
  - Metrics: MAE=144.99, RMSE=538.61, R²=0.9988
  - Saved `model_v1.joblib` as bundle `{model, features}`, `baseline_metrics.json`, `baseline_features.parquet`
- Implemented `src/ml/model_io.py`:
  - `load_model()` with legacy auto-wrap for raw estimators
  - `predict()` and `predict_batch()` as single inference contract

**Issues Encountered**
- Legacy artifact compatibility: old model files were raw estimators, not bundles

**Resolution**
- `_is_bundle()` check with auto-wrap in `load_model()` handles both formats

**Next Steps**
- Build Kafka producer
- Implement Spark streaming job

---

## Session 4 — 9-11 March 2026 (Approximate)

**Work Done**
- Implemented `src/streaming/kafka_producer.py`:
  - Reads `pjm_cleaned.parquet`, publishes to `pjm.load` topic
  - Message format: `{"timestamp": ..., "load_mw": ...}`
  - Configurable rate via `--sleep-seconds`
- Started Kafka via Docker: `docker run -p 9092:9092 apache/kafka:latest`

**Issues Encountered**
- None recorded.

**Resolution**
- N/A

**Next Steps**
- Implement Spark structured streaming inference job

---

## Session 5 — 9-11 March 2026 (Approximate)

**Work Done**
- Implemented `src/streaming/spark_job.py`:
  - SparkSession with `local[*]`, Kafka connector package
  - JSON parse → time features → broadcast model inference via `pandas_udf`
  - Hourly windowed metrics: 8 columns per 1-hour window
  - Deduplicated parquet sink: `data/metrics/hourly_metrics/`
  - Checkpoint: `checkpoints/spark_predictions/`
- Added WSL-specific Spark workarounds (native lib, RawLocalFileSystem)

**Issues Encountered**
- Hadoop native library warning in WSL environment
- Duplicate hourly rows possible with microbatch mode

**Resolution**
- Hadoop config overrides in SparkSession builder
- `dropDuplicates(["timestamp_hour"])` applied before sink write

**Next Steps**
- Implement drift detection engine
- Run end-to-end test

---

## Session 6 — 12-14 March 2026 (Approximate)

**Work Done**
- Implemented `src/drift_detection/drift_detector.py`:
  - Loads all hourly metrics parquet files
  - 7-day baseline vs. 24-hour recent window comparison
  - performance_drift: `recent_mean_error > baseline_mean_error × 1.5`
  - prediction_drift: `|recent_mean - baseline_mean| > baseline_std × 2`
  - Outputs `artifacts/drift/drift_report.json`
- Wrote `progress.md` capturing full system architecture and implementation status

**Issues Encountered**
- Drift detector cannot run without sufficient historical data in `hourly_metrics/`

**Resolution**
- Added explicit `ValueError` with descriptive messages for empty windows
- Documented requirement: need 25+ hours of streaming data before drift detection

**Next Steps**
- Run full end-to-end pipeline test
- Fix any remaining config/path issues
- Begin work on self-healing retraining module

---

## Session 7 — March 15, 2026

**Work Done**
- **Git housekeeping**:
  - Identified `.venv/` (WSL Python environment) was causing Git to track 1000+ files
  - Expanded `.gitignore` with comprehensive venv patterns (`.venv/`, `venv/`, `env/`, etc.)
  - Ran `git rm -r --cached` to remove any index-tracked venv paths (no file deletion)
  - Identified `spark-3.5.1-bin-hadoop3/` and `.tgz` archive as the primary source of 1000+ untracked entries in `git status`
  - Added both to `.gitignore` — verified `git status` is now clean of these entries

- **Documentation sprint**:
  - Generated complete developer knowledge base in `docs/` folder:
    - `PROJECT_CONTEXT.md` — master project brain
    - `ARCHITECTURE.md` — technical architecture with full ASCII pipeline diagrams
    - `PROGRESS.md` — completed / in-progress / not-yet-implemented tracker
    - `ISSUES_LOG.md` — 7 documented issues with root causes and resolutions
    - `RECENT_CONTEXT.md` — last session interactions summary
    - `DEBUG_GUIDE.md` — 11-section debugging reference
    - `NEXT_STEPS.md` — immediate, short-term, and long-term roadmap
    - `SESSION_LOG.md` — this file
    - `START_NEW_CHAT_CONTEXT.md` — single copy-paste context block for new AI chats

**Issues Encountered**
- Git was showing 1000+ entries due to unignored Spark distribution directory
- WSL venv was not comprehensively gitignored

**Debugging Actions**
- `git ls-files | Select-String` — verified no tracked venv paths
- `git status --short` — verified Spark directory removed from status noise
- Read all source files to build comprehensive documentation

**Resolution**
- Both issues resolved via `.gitignore` additions
- Full documentation suite generated in `docs/`

**Pending**
- All changes (`.gitignore`, source files, `docs/`) need to be committed
- Full end-to-end pipeline test still pending
- Next major development work: implement retraining module

**Next Steps**
1. `git add . && git commit -m "..."` — commit all pending work
2. Run full pipeline: Kafka → producer → Spark job → drift detector
3. Implement `src/ml/retrain.py` (Phase 4 retraining pipeline)
4. Implement KS-test / PSI feature drift (Phase 3 statistical drift)

---

## Session 9 — March 17, 2026

**Problem Identified & Fixed: Multi-Zone Data Leakage**

The raw PJM dataset contains multiple rows **per timestamp** (one per transmission zone). The preprocessing was treating this as independent records, causing:
- **Training data leakage**: zone A's load at time T influences zone B's lag features, mixing transmission zones
- **Invalid lag features**: `lag_1` could come from a different zone than the current record
- **Unrealistic model performance**: R²=0.9988 from 199K+ rows with zone-embedded information → artificially high

**Work Done**

1. **Modified `src/data/offline_preprocess.py`**:
  - Fixed CSV path resolution to look in `data/raw/` directory
  - Added aggregation step after timestamp parsing:
    ```python
    df = df.groupby("datetime")["load_mw"].sum().reset_index()
    ```
  - Aggregates all transmission zones per timestamp into a single row
  - Result: **8759 unique timestamps** (one row per hour)
  - All zone/region categorical columns drop naturally from aggregation
  - Changed `group_cols` default from `("load_area",)` → `()` for single time series

2. **Modified `src/data/feature_builder.py`**:
  - Added branching in `add_lag_and_rolling_features_pandas()`:
    - **Non-empty `group_cols`** (multi-zone): uses `groupby().shift()` (backward compatible)
    - **Empty `group_cols`** (single time series): operates directly on Series (no cross-zone leakage)
  - Lag features now correctly reference prior timestamps from the same aggregated load signal

3. **Modified `src/streaming/kafka_producer.py`**:
  - Changed default dataset from `pjm_cleaned.parquet` → `pjm_supervised.parquet`
  - Added `FEATURE_COLUMNS` import for runtime validation
  - Expanded Kafka payload to include full `"features"` dict with all 9 feature columns
  - Each numeric value cast to Python `int`/`float` for clean JSON serialization
  - Validates all required columns present before streaming

4. **Retrained `src/ml/train_baseline.py`** with corrected data:
  - **Before**: 199,795 train rows, 49,949 val rows → R²=0.9988 (data leakage artifact)
  - **After**: 6,872 train rows, 1,719 val rows → R²=0.9179 (realistic performance)
  - MAE increased from 144.99 → 3486.28 MW (reflecting true prediction uncertainty)
  - RMSE increased from 538.61 → 5916.73 MW

**Impact**

✅ **Eliminates data leakage**: Single aggregated time series, no zone mixing
✅ **Correct lag computation**: `lag_1`, `lag_24`, `lag_168` now reference prior system-level load
✅ **Realistic metrics**: R²=0.91 reflects actual model capability, not dataset artifacts
✅ **Streaming parity**: Kafka producer now sends complete feature set required by model

**Artifacts Updated**

- `data/processed/pjm_cleaned.parquet` — 8759 rows (1 per timestamp)
- `data/processed/pjm_supervised.parquet` — 8591 rows (trainable; lag rows dropped)
- `artifacts/models/model_v1.joblib` — retrained XGBoost with realistic R²
- `artifacts/baselines/baseline_metrics.json` — updated with new metrics

**Pending**

- Full end-to-end pipeline test with Kafka → Spark → drift detection
- Verify Spark streaming job still works with new feature-rich Kafka messages
- Retraining pipeline (`src/ml/retrain.py`) implementation

**Next Steps**

1. Commit all changes:
  ```bash
  git add src/data/ src/streaming/ src/ml/train_baseline.py docs/
  git commit -m "fix(pipeline): eliminate multi-zone data leakage and retrain model

  - Aggregate multi-zone data into system-level time series (8759 unique timestamps)
  - Fix lag/rolling feature computation for single aggregated time series
  - Update Kafka producer to stream full feature set
  - Retrain model on corrected dataset (R²=0.91, realistic metrics)
  - Eliminate cross-zone training data leakage"
  ```
2. Run end-to-end pipeline test
3. Implement retraining module (Phase 4)

---

## Session 8 — March 17, 2026

**Work Done**
- **Documentation audit and completion**:
  - Verified all 8 documentation files are present and complete in `docs/` folder
  - Created `reset_pipeline.py` utility script for safely clearing streaming state before restarting pipeline
    - Supports `--keep-predictions` and `--hard-reset` flags
    - Clears `hourly_metrics/`, `spark_predictions/` checkpoints, and optionally `predictions/` and drift reports
  - Catalogued all issues from entire project conversation into `ISSUES_LOG.md`:
    - **Issue 1**: Git tracking `.venv/` (1000+ files) — RESOLVED via `.gitignore` expansion
    - **Issue 2**: Spark binary distribution in `git status` — RESOLVED via `.gitignore` entry
    - **Issue 3**: Hadoop native library warning in WSL — RESOLVED via Spark config override
    - **Issue 4**: Training-serving feature skew risk — RESOLVED via centralized `FEATURE_COLUMNS` + bundle format
    - **Issue 5**: Legacy model artifact compatibility — RESOLVED via auto-wrap in `load_model()`
    - **Issue 6**: Duplicate hourly metrics in Spark sink — RESOLVED via `dropDuplicates()` on `timestamp_hour`
    - **Issue 7**: Drift detector fails with empty windows — HANDLED via informative error messages

**Project Status Summary**
- **Core pipeline**: ✅ Fully implemented and ready for testing
  - Offline preprocessing + feature engineering
  - Baseline XGBoost model training (R²=0.9988)
  - Kafka producer for streaming simulation
  - Spark Structured Streaming inference job with hourly metrics aggregation
  - Drift detection engine (error-level + prediction-level signals)
- **Knowledge base**: ✅ Complete
  - 8 documentation files covering architecture, progress, issues, debugging, roadmap
  - `START_NEW_CHAT_CONTEXT.md` for new AI chat sessions
- **Repository state**: ✅ Cleaned
  - All 1000+ git tracking issues resolved
  - `.gitignore` comprehensive (`.venv/`, Spark, data, artifacts, checkpoints, etc.)

**Issues Encountered**
- None in this session (review/verification-only work)

**Pending Work**
- **Git commit**: All newly generated files (`docs/`, `reset_pipeline.py`) and modified files (`.gitignore`, source files) awaiting commit
- **End-to-end testing**: Full pipeline not yet tested with real streaming data
- **Self-healing retraining**: `src/ml/retrain.py` not yet implemented
- **Advanced drift signals**: KS-test and PSI-based feature drift not yet integrated

**Current Git Status**
```
Modified: .gitignore, configs/base.yaml, requirements.txt, src/ml/train_baseline.py
Untracked: 
  - src/drift_detection/
  - src/ml/model_io.py
  - src/streaming/
  - progress.md
  - docs/
  - reset_pipeline.py
```

**Next Steps**
1. **Commit all work**: `git add . && git commit -m "feat: drift detection, streaming, model IO, docs, reset utility; fix gitignore"`
2. **Test end-to-end pipeline**:
   - Start Kafka: `docker run -p 9092:9092 apache/kafka:latest`
   - Run producer: `python -m src.streaming.kafka_producer --sleep-seconds 0.01`
   - Run Spark job (WSL): `python -m src.streaming.spark_job`
   - After 24+ hours of data, run: `python -m src.drift_detection.drift_detector`
3. **Implement Phase 4**: Self-healing retraining module (`src/ml/retrain.py`)
4. **Implement Phase 3**: Feature-level drift detection (KS-test + PSI)
