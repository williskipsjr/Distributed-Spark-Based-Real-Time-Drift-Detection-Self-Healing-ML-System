# PROGRESS.md

---

## Completed Components

### Infrastructure
- [x] **Config system** (`src/common/config.py`) — YAML deep-merge loader, dot-path accessor, env selection via `BDA_ENV`
- [x] **Structured logging** (`src/common/logging.py`) — event-key JSON/text logging for all pipeline stages
- [x] **Shared schemas** (`src/common/schemas.py`) — dataclasses and Spark `StructType` for cross-module contracts
- [x] **`.gitignore`** — correctly excludes `.venv/`, `spark-3.5.1-bin-hadoop3/`, `data/`, `artifacts/`, `checkpoints/`, `__pycache__/`, `*.pyc`, `*.csv`, `*.parquet`

### Data Pipeline
- [x] **Offline preprocessing** (`src/data/offline_preprocess.py`)
  - PJM CSV → `pjm_cleaned.parquet` + `pjm_supervised.parquet`
  - Column normalization, timestamp parsing, null dropping, chronological sort
- [x] **Feature engineering** (`src/data/feature_builder.py`)
  - `FEATURE_COLUMNS`: `['hour_of_day', 'day_of_week', 'month', 'is_weekend', 'lag_1', 'lag_24', 'lag_168', 'rolling_24', 'rolling_168']`
  - Pandas path for offline, Spark UDF path for streaming

### ML Model
- [x] **Baseline training** (`src/ml/train_baseline.py`)
  - XGBoost regressor, chronological 80/20 split
  - Artifacts: `model_v1.joblib`, `baseline_metrics.json`, `baseline_features.parquet`
- [x] **Baseline metrics** (from `artifacts/baselines/baseline_metrics.json`)
  - Train rows: **199,795** | Validation rows: **49,949**
  - MAE: **144.99** | RMSE: **538.61** | R²: **0.9988**
- [x] **Model I/O** (`src/ml/model_io.py`)
  - `load_model()` — auto-normalizes legacy vs. bundle format
  - `predict()`, `predict_batch()` — single inference contract for offline + streaming

### Streaming
- [x] **Kafka producer** (`src/streaming/kafka_producer.py`)
  - Reads `pjm_cleaned.parquet` → publishes to `pjm.load` topic as JSON stream
  - Configurable rate via `--sleep-seconds`
- [x] **Spark Structured Streaming job** (`src/streaming/spark_job.py`)
  - Kafka subscribe → JSON parse → feature engineering → broadcast model inference
  - Hourly windowed metrics aggregation (8 metric columns per hour)
  - Parquet sink: `data/metrics/hourly_metrics/`
  - Checkpoint: `checkpoints/spark_predictions/`
  - Uses `pandas_udf` for batch inference
  - Deduplication on `timestamp_hour` partition key

### Drift Detection
- [x] **Drift detector** (`src/drift_detection/drift_detector.py`)
  - 7-day baseline vs. 24-hour recent window comparison
  - performance_drift check (error ratio threshold: 1.5×)
  - prediction_drift check (mean shift threshold: 2× std)
  - JSON report output: `artifacts/drift/drift_report.json`

### Repository / DevOps
- [x] **Git cleanup** — untracked WSL `.venv` from index; added to `.gitignore`
- [x] **Git cleanup** — ignored `spark-3.5.1-bin-hadoop3/` and `.tgz` archive
- [x] **`requirements.txt`** — pinned major dependencies

---

## In Progress

| Component | Status | Notes |
|-----------|--------|-------|
| `progress.md` updates | Partially tracked | File exists but shows as untracked in `git status` |
| `src/drift_detection/` | Core logic done | Statistical tests (KS, PSI) not yet integrated |
| `src/streaming/spark_job.py` | Running | Minor config/path tweaks ongoing |

---

## Not Yet Implemented

### Self-Healing Retraining Pipeline
- `src/ml/retrain.py` — triggered when `drift_report.json` shows `drift_detected: true`
- Window extraction: last 720 hours, blended 70% recent / 30% historical
- Candidate model training + validation against deployed model metrics
- Promotion gate: deploy only if candidate MAE < deployed model MAE

### Statistical Drift Tests (advanced)
- **Kolmogorov–Smirnov test** per feature column (p-value threshold: `0.05` from config)
- **Population Stability Index (PSI)** per feature (warning: `0.10`, critical: `0.25`)
- Feature-level drift reporting (not just error-level)
- Integration into `drift_detector.py`

### Model Version Registry
- Lifecycle events: train → deploy → retire
- Version comparison logs
- `artifacts/models/deployed_model.joblib` promotion/replacement

### Monitoring Dashboard
- Streaming metrics visualization (error trends over time)
- Drift alert display
- Model performance timeline
- Options: Streamlit, Grafana + Prometheus, or custom FastAPI + frontend
