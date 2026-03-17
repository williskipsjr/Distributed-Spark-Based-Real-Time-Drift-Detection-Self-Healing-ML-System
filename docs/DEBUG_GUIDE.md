
# DEBUG_GUIDE.md

> Developer reference for debugging each layer of the system.

---

## 1. Inspect Hourly Metrics (Drift Input Data)

Run this whenever the drift detector fails or you want to verify the Spark job is writing data correctly.

```python
import pandas as pd
from pathlib import Path

metrics_path = Path("data/metrics/hourly_metrics")
files = sorted(metrics_path.rglob("*.parquet"))
print(f"Found {len(files)} parquet files")

if files:
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df["timestamp_hour"] = pd.to_datetime(df["timestamp_hour"], utc=True, errors="coerce")
    df = df.sort_values("timestamp_hour")
    print(df.dtypes)
    print(df.head(10))
    print(f"\nDate range: {df['timestamp_hour'].min()} → {df['timestamp_hour'].max()}")
    print(f"Total rows: {len(df)}")
    print(f"\nMean error stats:\n{df['mean_error'].describe()}")
```

**When to run**: Before running `drift_detector.py` to verify data is populated.  
**Run from**: Project root, with `data/metrics/hourly_metrics/` present.

---

## 2. Inspect Predictions Parquet

```python
import pandas as pd
from pathlib import Path

pred_path = Path("data/predictions")
files = sorted(pred_path.rglob("*.parquet"))
print(f"Found {len(files)} prediction parquet files")

if files:
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    print(df.columns.tolist())
    print(df.head())
    print(df.describe())
```

**When to run**: After the Spark job has been running to verify predictions are being written.

---

## 3. Validate Processed Parquet Files

```python
import pandas as pd

df_clean = pd.read_parquet("data/processed/pjm_cleaned.parquet")
df_super = pd.read_parquet("data/processed/pjm_supervised.parquet")

print("=== pjm_cleaned ===")
print(df_clean.dtypes)
print(df_clean.head())
print(f"Shape: {df_clean.shape}")
print(f"Nulls: {df_clean.isnull().sum().sum()}")

print("\n=== pjm_supervised ===")
print(df_super.dtypes)
print(df_super.head())
expected_features = ['hour_of_day','day_of_week','month','is_weekend',
                     'lag_1','lag_24','lag_168','rolling_24','rolling_168']
missing = [c for c in expected_features if c not in df_super.columns]
print(f"Missing feature columns: {missing}")
```

**When to run**: After `offline_preprocess.py` to confirm the ETL ran correctly.

---

## 4. Validate the Trained Model

```python
import joblib
import pandas as pd
from src.data.feature_builder import FEATURE_COLUMNS

bundle = joblib.load("artifacts/models/model_v1.joblib")
print("Bundle keys:", list(bundle.keys()))
print("Feature list:", bundle["features"])
print("Feature match:", bundle["features"] == FEATURE_COLUMNS)

# Quick smoke test
test_row = {col: [0.0] for col in FEATURE_COLUMNS}
test_df = pd.DataFrame(test_row)
pred = bundle["model"].predict(test_df)
print("Smoke test prediction:", pred)
```

**When to run**: After training to confirm the artifact is valid.

---

## 5. Inspect Drift Report

```python
import json
from pathlib import Path

report_path = Path("artifacts/drift/drift_report.json")
if report_path.exists():
    report = json.loads(report_path.read_text())
    print(json.dumps(report, indent=2))
else:
    print("No drift report found — run drift_detector.py first")
```

**Expected output**:
```json
{
  "drift_detected": false,
  "drift_type": "none",
  "baseline_error": 142.5,
  "recent_error": 138.2,
  "baseline_mean_prediction": 12500.0,
  "recent_mean_prediction": 12480.0,
  "baseline_std_prediction": 800.0
}
```

---

## 6. Check Spark Checkpoint State

Checkpoint issues are the #1 cause of Spark streaming failures on restart.

```powershell
# Windows / WSL — check checkpoint directory
Get-ChildItem -Recurse "checkpoints/spark_predictions" | Select-Object Name, Length

# Or in bash (WSL)
find checkpoints/spark_predictions -type f | head -20
```

**If Spark job fails on restart with "checkpoint incompatible" error:**

The `spark_job.py` is configured to clear the checkpoint directory on startup via `shutil.rmtree(resolved_checkpoint)`. This is intentional for development. If you see checkpoint errors, manually delete:
```bash
rm -rf checkpoints/spark_predictions/
```
Then restart the Spark job.

---

## 7. Kafka Connectivity Test

```python
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable

# Test producer connection
try:
    producer = KafkaProducer(bootstrap_servers="localhost:9092")
    print("Kafka producer connected ✓")
    producer.close()
except NoBrokersAvailable:
    print("ERROR: Kafka not available on localhost:9092 — is Docker running?")

# Test consumer and list topics
from kafka.admin import KafkaAdminClient
try:
    admin = KafkaAdminClient(bootstrap_servers="localhost:9092")
    topics = admin.list_topics()
    print("Available topics:", topics)
    admin.close()
except Exception as e:
    print(f"Admin error: {e}")
```

**When Kafka is not available**: Restart Docker container:
```bash
docker run -p 9092:9092 apache/kafka:latest
```

---

## 8. Run Drift Detector Manually

```bash
# From project root in WSL or Windows with activated venv
python -m src.drift_detection.drift_detector
```

**Expected log output (no drift)**:
```
drift-detection-started  {"metrics_path": "data/metrics/hourly_metrics"}
drift-detection-complete {"drift_detected": false, "drift_type": "none", "report_path": "..."}
```

**Expected log output (drift detected)**:
```
drift-detection-started  {...}
drift-detected           {"drift_type": "performance_drift", "baseline_error": 142.5, "recent_error": 235.0}
drift-detection-complete {"drift_detected": true, ...}
```

**Common failures**:
- `FileNotFoundError: No hourly metrics parquet files` → Spark job hasn't run yet
- `ValueError: Baseline window contains no data` → Less than 25 hours of data collected

---

## 9. Spark Job Debugging

```bash
# Run Spark job with verbose Python logging (WSL)
BDA_ENV=dev python -m src.streaming.spark_job 2>&1 | tee spark_debug.log

# Filter for only your app logs (ignore Spark internals)
BDA_ENV=dev python -m src.streaming.spark_job 2>&1 | grep -v "^[0-9]\{2\}/[0-9]\{2\}"
```

**Key log events to watch for**:
```
model-broadcast-created        → model loaded and broadcast successfully
spark-stream-start             → subscription to Kafka topic confirmed
hourly-metrics-configured      → windowing query set up
hourly-metrics-computed        → data is flowing and being aggregated
metrics-batch-written          → parquet file written to hourly_metrics/
```

**If `batch-processed` appears but no files are written**: check output path permissions and parquet schema.

---

## 10. Baseline Metrics Reference

For drift threshold calibration, the trained baseline model's validation-set metrics:

| Metric | Value |
|--------|-------|
| MAE | 144.99 |
| RMSE | 538.61 |
| R² | 0.9988 |
| Train rows | 199,795 |
| Validation rows | 49,949 |

**performance_drift threshold**: `recent_mean_error > 144.99 × 1.5 = 217.49`  
**Current drift config** (`base.yaml`):
```yaml
drift:
  ks_pvalue_threshold: 0.05
  psi_warning_threshold: 0.10
  psi_critical_threshold: 0.25
  rolling_mae_increase_ratio: 1.20
```
Note: The drift detector currently uses a hardcoded ratio of `1.5` for error threshold. The config values `rolling_mae_increase_ratio: 1.20` are reserved for the future statistical drift implementation.

---

## 11. Git Status Reference

After the cleanups performed in this session, a clean `git status` should show:

```
M  .gitignore              ← needs commit
M  configs/base.yaml       ← needs commit
M  requirements.txt        ← needs commit
M  src/ml/train_baseline.py ← needs commit
?? progress.md             ← add to staging when ready
?? src/drift_detection/    ← add to staging when ready
?? src/ml/model_io.py      ← add to staging when ready
?? src/streaming/          ← add to staging when ready
?? docs/                   ← this knowledge base folder
```

**To commit all pending work**:
```bash
cd Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System
git add .gitignore configs/ requirements.txt src/ progress.md docs/
git commit -m "feat: add drift detection, streaming job, model IO; fix gitignore"
```
