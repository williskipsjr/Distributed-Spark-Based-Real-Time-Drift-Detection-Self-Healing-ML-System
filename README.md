# Distributed Spark-Based Real-Time Drift Detection and Self-Healing ML System

End-to-end real-time ML pipeline for PJM electricity load forecasting.

The system uses:

- Kafka for streaming events
- Spark Structured Streaming for online inference
- XGBoost for forecasting
- Drift detection over hourly metrics
- A production-oriented debugging workflow

## 1. What This Project Does

1. Builds supervised time-series data with canonical lag and rolling features.
2. Trains a baseline XGBoost model and stores it as a bundle (`model` + ordered `features`).
3. Streams load records from dataset replay into Kafka.
4. Scores streaming records in Spark and writes hourly metrics to parquet.
5. Runs drift detection on recent vs baseline windows.

## 2. Core Feature Contract

These features are the strict model contract used in both training and serving:

```python
[
	"hour_of_day",
	"day_of_week",
	"month",
	"is_weekend",
	"lag_1",
	"lag_24",
	"lag_168",
	"rolling_24",
	"rolling_168",
]
```

## 3. Environment Setup

### 3.1 Python

Use the project virtual environment in both Windows and WSL contexts.

Windows PowerShell:

```powershell
& "C:/Users/Willis/OneDrive/Documents/IIIT-DWD/2nd Year/4th Sem/Big Data/BDA-Project/.venv/Scripts/Activate.ps1"
```

WSL bash:

```bash
cd "/mnt/c/Users/Willis/OneDrive/Documents/IIIT-DWD/2nd Year/4th Sem/Big Data/BDA-Project/Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
source .venv/bin/activate
```

### 3.2 Dependencies

```bash
pip install -r requirements.txt
```

### 3.3 Kafka

Start Kafka in a dedicated terminal:

```powershell
docker run -p 9092:9092 apache/kafka:latest
```

## 4. Offline Training

Train the baseline model bundle:

```bash
python -m src.ml.train_baseline --log-level INFO
```

Outputs:

- `artifacts/models/model_v2.joblib`
- `artifacts/baselines/baseline_metrics_v2.json`

## 5. Running the Streaming Pipeline

Run producer and Spark in separate terminals.

### 5.1 Kafka Producer

Replay 2019 raw stream dataset:

```bash
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --sleep-seconds 0.1 --log-level INFO
```

Notes:

- Raw CSV is aggregated to PJM-wide load before feature generation.
- Producer sends payload with timestamp, load, and feature object.

### 5.2 Spark Job (Production Mode)

Run in WSL terminal:

```bash
cd "/mnt/c/Users/Willis/OneDrive/Documents/IIIT-DWD/2nd Year/4th Sem/Big Data/BDA-Project/Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System"
source .venv/bin/activate
export PYSPARK_PYTHON="$(which python)"
export PYSPARK_DRIVER_PYTHON="$(which python)"
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120
```

Important:

- The `export PYSPARK_PYTHON` and `export PYSPARK_DRIVER_PYTHON` lines are required to force Spark driver/worker interpreter consistency.
- Use `--run-seconds` instead of shell `timeout` for graceful shutdown.

### 5.3 Spark Job (Debug Mode)

```bash
python -m src.streaming.spark_job --debug-mode --run-seconds 120
```

## 6. Output Paths

- Hourly metrics output: `data/metrics/hourly_metrics/`
- Spark checkpoints: `checkpoints/spark_predictions/`
- Drift report: `artifacts/drift/drift_report.json`

## 7. Validate Metrics Quickly

```bash
python - <<'PY'
import pandas as pd
from pathlib import Path

p = Path("data/metrics/hourly_metrics")
files = [f for f in p.glob("**/*.parquet") if f.stat().st_size > 0]
print("usable_files:", len(files))

dfs = []
for f in files:
	try:
		dfs.append(pd.read_parquet(f))
	except Exception as e:
		print("skip_bad_file:", f, "|", e)

df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
print("rows:", len(df))
if not df.empty:
	print(df.head())
	print(df.describe(include="all"))
PY
```

## 8. Run Drift Detection

```bash
python -m src.drift_detection.drift_detector
cat artifacts/drift/drift_report.json
```

## 9. Common Operations

Clear stale output/checkpoints before a fresh replay run:

```bash
rm -rf data/metrics/hourly_metrics/*
rm -rf checkpoints/spark_predictions/*
```

Remove zero-byte parquet files (if interrupted writes occurred):

```bash
python - <<'PY'
from pathlib import Path
p = Path("data/metrics/hourly_metrics")
removed = 0
for f in p.glob("**/*.parquet"):
	if f.stat().st_size == 0:
		f.unlink()
		removed += 1
print("removed_zero_byte_files:", removed)
PY
```

## 10. Current Status

- Streaming inference now runs with stabilized writer flow and graceful timed termination support.
- Drift detection runs successfully and reports structured JSON output.
- Next phase: self-healing trigger/retrain automation based on drift report.

## 11. Documentation Map

Project documentation is organized under `docs/`.

- Main index: `docs/INDEX.md`
- Context and roadmap: `docs/PROJECT_CONTEXT.md`, `docs/RECENT_CONTEXT.md`, `docs/NEXT_STEPS.md`
- Logs: `docs/SESSION_LOG.md`, `docs/ISSUES_LOG.md`
- Technical references: `docs/ARCHITECTURE.md`, `docs/DEBUG_GUIDE.md`
- Script index: `scripts/README.md`

Use `docs/INDEX.md` as the entry point.

## 12. Repository Hygiene

- Runtime outputs are intentionally ignored (`*.log`, data/artifacts/checkpoints).
- Before sharing analysis results, prefer scripts/notebooks or docs entries rather than committing local logs.
- If interrupted runs produce broken parquet files, remove zero-byte parts before analysis.