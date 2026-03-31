# Distributed Spark-Based Real-Time Drift Detection and Self-Healing ML System

End-to-end real-time ML pipeline for PJM electricity load forecasting.

The system uses:

- Kafka for streaming events
- Spark Structured Streaming for online inference
- XGBoost for forecasting
- Drift detection over hourly metrics
- A production-oriented debugging workflow

## Script Layout

- Canonical maintenance scripts:
	- `scripts/maintenance/reset_pipeline.py`
- Canonical testing scripts:
	- `scripts/testing/run_tests.py`
	- `scripts/testing/run_tests.ps1`
	- `scripts/testing/validate_test.py`
- Backward-compatible root wrappers (still supported):
	- `reset_pipeline.py`
	- `run_tests.py`
	- `run_tests.ps1`
	- `validate_test.py`

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
 - Producer resume cursor is stored in `checkpoints/producer/producer_state.json` and resumes by default.

Run one pass (no infinite looping):

```bash
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --sleep-seconds 0.1 --no-loop-forever
```

Start over from the beginning (reset cursor):

```bash
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --sleep-seconds 0.1 --reset-state
```

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
- Spark resumes from prior offsets/state by default using checkpoint path `checkpoints/spark_predictions/`.
- Kafka source uses `failOnDataLoss=false` by default so aged-out offsets do not crash local resume runs.

Start from scratch (fresh Spark state):

```bash
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120 --reset-checkpoint
```

Strict mode (fail immediately if any Kafka offsets are missing):

```bash
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120 --fail-on-data-loss
```

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

Note: Drift detection now auto-removes zero-byte parquet shards in `data/metrics/hourly_metrics` before loading metrics.

Run continuously every few minutes (recommended for live monitoring):

```bash
python -m src.drift_detection.drift_monitor --interval-seconds 300
```

Outputs:
- Check history log: `artifacts/drift/drift_history.jsonl`
- Monitor policy state: `artifacts/drift/drift_monitor_state.json`

Retrain guardrails (prevents creating too many models):
- Requires consecutive drift detections (default: 3)
- Enforces cooldown between retrains (default: 180 minutes)
- Default action is "retrain-suggested" only; automatic retrain requires explicit flags.

Example with automatic retrain command:

```bash
python -m src.drift_detection.drift_monitor \
	--interval-seconds 300 \
	--required-consecutive-drifts 3 \
	--cooldown-minutes 180 \
	--trigger-retrain \
	--retrain-command "python -m src.ml.train_baseline"
```

## 9. Common Operations

## 10. Documentation Layout

- Main docs index: `docs/INDEX.md`
- Testing/runbook docs: `docs/testing/`
	- `docs/testing/TESTING.md`
	- `docs/testing/END_TO_END_TEST.md`
	- `docs/testing/QUICK_START.md`
	- `docs/testing/COMPLETE_TESTING_GUIDE.md`
	- `docs/testing/SETUP_TESTING_FRAMEWORK.md`

Self-healing trigger decision (dry-run by default):

```bash
python -m src.self_healing.trigger --dry-run
```

Decision output is one of:
- `no_action`
- `retrain_candidate`
- `promote_candidate`

Decision log file:
- `artifacts/self_healing/trigger_decisions.jsonl`

Example with policy knobs:

```bash
python -m src.self_healing.trigger \
	--dry-run \
	--required-consecutive-drifts 2 \
	--min-relative-improvement 0.02
```

Retrain pipeline (build candidate model + comparison report):

```bash
python -m src.self_healing.retrain_pipeline \
	--stream-csv-path data/stream_dataset/hrl_load_metered-2020.csv \
	--recent-days 30 \
	--min-relative-improvement 0.02
```

Outputs:
- Candidate model artifact: `artifacts/models/candidates/model_candidate_*.joblib`
- Candidate metrics: `artifacts/models/candidates/metrics_candidate_*.json`
- Candidate comparison report: `artifacts/models/candidate_report.json`

Trigger with command wiring (non-dry-run):

```bash
python -m src.self_healing.trigger \
	--no-dry-run \
	--required-consecutive-drifts 2 \
	--retrain-command "python -m src.self_healing.retrain_pipeline --stream-csv-path data/stream_dataset/hrl_load_metered-2020.csv --recent-days 30"
```

Promotion and rollback policy:

```bash
# Gate evaluation only
python -m src.self_healing.promotion promote --dry-run

# Apply promotion when all gates pass
python -m src.self_healing.promotion promote --no-dry-run --min-relative-improvement 0.02

# Roll back to previous production model pointer
python -m src.self_healing.promotion rollback --no-dry-run

# Inspect active/previous pointer state
python -m src.self_healing.promotion status
```

Promotion artifacts:
- Active pointer: `artifacts/models/active_model.json`
- Promotion/rollback audit log: `artifacts/models/promotion_log.jsonl`

Important:
- `src.ml.model_io.load_model()` now checks `artifacts/models/active_model.json` first.
- `src.streaming.spark_job` uses this pointer by default unless `--model-path` is provided.
- `src.self_healing.trigger --no-dry-run` auto-invokes promotion command for `promote_candidate` when no explicit `--promote-command` is supplied.

Serving reload workflow after promotion:

```bash
# 1) Stop current Spark serving job gracefully (recommended with run window)
# If running foreground without run window, stop with Ctrl+C.

# 2) Promote candidate (or rollback if needed)
python -m src.self_healing.promotion promote --no-dry-run --min-relative-improvement 0.02

# 3) Start Spark serving again (it reads active pointer by default)
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120

# 4) Verify active model version appears in metrics output
python scripts/utilities/check_model_version_in_metrics.py --tail 20
```

Notes:
- `active_model_version` is now written to hourly metrics parquet records.
- Use `python -m src.self_healing.promotion status` to inspect current pointer before/after restart.

Fresh replay reset (producer cursor + Spark checkpoint):

```bash
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --reset-state --no-loop-forever
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120 --reset-checkpoint
```

Remove zero-byte parquet files (if interrupted writes occurred):

```bash
python scripts/utilities/cleanup_zero_byte_metrics.py --dry-run
python scripts/utilities/cleanup_zero_byte_metrics.py
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
- Historical reports: `docs/reports/PRODUCTION_DEBUG_REPORT.md`, `docs/reports/FINAL_REPORT.md`
- Script index: `scripts/README.md`

Use `docs/INDEX.md` as the entry point.

## 12. Repository Hygiene

- Runtime outputs are intentionally ignored (`*.log`, data/artifacts/checkpoints).
- Before sharing analysis results, prefer scripts/notebooks or docs entries rather than committing local logs.
- If interrupted runs produce broken parquet files, remove zero-byte parts before analysis.