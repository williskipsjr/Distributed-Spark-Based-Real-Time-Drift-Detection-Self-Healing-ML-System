# ARCHITECTURE.md

---

## High-Level System Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE PHASE                            │
│                                                             │
│  hrl_load_metered-2018.csv                                  │
│           │                                                 │
│           ▼                                                 │
│   offline_preprocess.py ──► pjm_cleaned.parquet            │
│           │                                                 │
│           ▼                                                 │
│   feature_builder.py   ──► pjm_supervised.parquet          │
│           │                                                 │
│           ▼                                                 │
│   train_baseline.py    ──► model_v1.joblib                  │
│                            baseline_metrics.json            │
│                            baseline_features.parquet        │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ model artifact
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    ONLINE / STREAMING PHASE                 │
│                                                             │
│   kafka_producer.py                                         │
│   (pjm_cleaned.parquet → JSON records)                      │
│           │                                                 │
│           ▼                                                 │
│   Kafka topic: pjm.load                (Docker, port 9092) │
│           │                                                 │
│           ▼                                                 │
│   spark_job.py  (Spark Structured Streaming)                │
│   ├── JSON parse                                            │
│   ├── Time feature extraction (Spark UDF)                   │
│   ├── pandas_udf batch inference (broadcast model)          │
│   ├── Error computation |actual − predicted|                │
│   └── 1-hour windowed aggregation                          │
│           │                         │                       │
│           ▼                         ▼                       │
│  data/predictions/    data/metrics/hourly_metrics/          │
│  (raw scored rows)    (parquet: stats per hour)             │
└─────────────────────────────────────────────────────────────┘
                        │
                        │ hourly_metrics parquet
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    DRIFT DETECTION PHASE                    │
│                                                             │
│   drift_detector.py                                         │
│   ├── Load all hourly_metrics parquet                       │
│   ├── 7-day baseline window                                 │
│   ├── 24-hour recent window                                 │
│   ├── performance_drift: error ratio > 1.5                  │
│   └── prediction_drift: mean shift > 2 × baseline_std      │
│           │                                                 │
│           ▼                                                 │
│   artifacts/drift/drift_report.json                         │
└─────────────────────────────────────────────────────────────┘
                        │
             [drift_detected = true]
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              SELF-HEALING RETRAINING (PLANNED)              │
│                                                             │
│   retraining_pipeline.py (not yet implemented)              │
│   ├── Extract recent window (720h, ratio 0.7/0.3)          │
│   ├── Retrain XGBoost candidate                             │
│   ├── Evaluate vs. deployed model                           │
│   └── Promote if better → deployed_model.joblib             │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### `Config` (`src/common/config.py`)
- Loads `configs/base.yaml` as baseline
- Deep-merges `configs/dev.yaml` (or any env-specific file) on top
- Environment selection: `BDA_ENV` env var → defaults to `"dev"`
- Dot-path accessor: `config.get("kafka.bootstrap_servers")`
- Used by every module that needs runtime configuration

### `Logger` (`src/common/logging.py`)
- Structured event-key logging (e.g., `"spark-stream-start"`, `"drift-detected"`)
- JSON output for production pipelines; human-readable text for dev
- All streaming pipeline events produce machine-parseable log entries

### `offline_preprocess.py` (`src/data/`)
- **Input**: `data/raw/hrl_load_metered-2018.csv`
- **Output**: `data/processed/pjm_cleaned.parquet`, `pjm_supervised.parquet`
- Normalizes column names, parses timestamps, drops nulls, sorts chronologically
- Delegates feature creation to `feature_builder`

### `feature_builder.py` (`src/data/`)
- **`FEATURE_COLUMNS`** — single source of truth for feature list and order:
  `['hour_of_day', 'day_of_week', 'month', 'is_weekend', 'lag_1', 'lag_24', 'lag_168', 'rolling_24', 'rolling_168']`
- Pandas path: used offline (preprocessing + training)
- Spark path: `add_time_features_spark()`, `add_features_spark()` — used in streaming job
- Deterministic sort by group + timestamp to prevent feature leakage

### `train_baseline.py` (`src/ml/`)
- Chronological 80/20 train/validation split (no shuffle — critical for time-series)
- Saves model as bundle: `{"model": XGBRegressor, "features": FEATURE_COLUMNS}`
- Baseline artifacts frozen for drift reference: `baseline_features.parquet`

### `model_io.py` (`src/ml/`)
- **`load_model(path)`** — loads joblib, auto-wraps legacy raw estimators in bundle format
- **`predict(df)`** — validates feature alignment before inference
- **`predict_batch(df)`** — appends `predicted_load` column; used in streaming `foreachBatch`
- Version tag defaults to `"v1"`, embedded in prediction output rows

### `kafka_producer.py` (`src/streaming/`)
- Reads `pjm_cleaned.parquet`, iterates sorted records, publishes to `pjm.load` topic
- Message: `{"timestamp": "<ISO>", "load_mw": <float>}`
- Configurable `--sleep-seconds` (default 0.1) for rate simulation
- Loops continuously until interrupted

### `spark_job.py` (`src/streaming/`)
- SparkSession: `local[*]`, package `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1`
- Stream source: Kafka `pjm.load`, `startingOffsets=latest`
- Feature UDF: `add_time_features_spark()` applied in-stream on `timestamp`
- Inference: `pandas_udf` with broadcast XGBoost model for low-latency batch scoring
- Hourly metrics: `withWatermark("timestamp", "1 hour")` → `window()` groupBy → 8 agg columns
- Deduplication: `dropDuplicates(["timestamp_hour"])` on formatted partition key
- Checkpoint: `checkpoints/spark_predictions/` (cleared on each restart)
- Output sink: `data/metrics/hourly_metrics/`, format=parquet, mode=append

### `drift_detector.py` (`src/drift_detection/`)
- Input: all `*.parquet` under `data/metrics/hourly_metrics/`
- Baseline window: rows where `timestamp_hour ∈ [now-7d, now-24h)`
- Recent window: rows where `timestamp_hour ≥ now-24h`
- **performance_drift**: `recent_mean_error > baseline_mean_error × 1.5`
- **prediction_drift**: `|recent_mean_pred − baseline_mean_pred| > baseline_std × 2`
- Output: `artifacts/drift/drift_report.json`

---

## Data Storage Design

### `data/processed/`
| File | Format | Contents |
|------|--------|----------|
| `pjm_cleaned.parquet` | Parquet | Normalized load data with timestamp + load_mw |
| `pjm_supervised.parquet` | Parquet | pjm_cleaned + all 9 engineered features |

### `data/metrics/hourly_metrics/`
Partitioned parquet written by Spark job. Each partition key = `timestamp_hour` (formatted `yyyy-MM-dd-HH`).

Schema per row:
```
timestamp_hour   : string  (partition key, format: yyyy-MM-dd-HH)
mean_prediction  : double
max_prediction   : double
min_prediction   : double
std_prediction   : double
mean_error       : double  ← primary drift signal
max_error        : double
record_count     : long
```

### `artifacts/`
```
artifacts/
├── models/
│   ├── model_v1.joblib          # Bundle: {model: XGBRegressor, features: [...]}
│   └── deployed_model.joblib    # [PLANNED] Promoted model for live serving
├── baselines/
│   ├── baseline_metrics.json    # {train_rows, val_rows, MAE, RMSE, R²}
│   └── baseline_features.parquet # Feature snapshot at training time
└── drift/
    └── drift_report.json        # Latest {drift_detected, drift_type, error stats}
```

### Why Parquet

- Columnar format: queries scan only needed columns → fast for time-windowed analytics
- Efficient compression for floating-point numeric data
- Self-describing schema (no external catalog needed)
- Native support in both pandas (`read_parquet`) and Spark (`spark.read.parquet`)
- Append-mode support with Spark Structured Streaming sinks

---

## Configuration Architecture

```
configs/base.yaml          # complete baseline — all keys defined here
        +
configs/dev.yaml           # only keys that differ in dev
        ↓ deep-merge
Config object              # accessed via config.get("section.key")
```

Key config sections:
- `kafka.*` — bootstrap servers, consumer group, topic names
- `spark.*` — app name, master, trigger interval, shuffle partitions
- `drift.*` — feature columns, KS p-value threshold, PSI thresholds, MAE ratio
- `retraining.*` — window hours, sample ratios, cooldown
- `model.*` — artifact paths for baseline/deployed model
- `storage.*` — parquet sink paths

---

## Environment Setup

```
Windows (development)
├── VS Code + Python .venv (Windows)
├── Requirements: requirements.txt
└── Used for: offline preprocessing, model training, editing

WSL (runtime)
├── Ubuntu Linux subsystem
├── Separate .venv (WSL Python)
├── spark-3.5.1-bin-hadoop3/ (local Spark binary)
└── Used for: running spark_job.py

Docker
├── apache/kafka:latest
├── Port: 9092
└── Used for: Kafka broker (Zookeeper embedded)
```

### Run Commands

```bash
# 1. Start Kafka (Docker)
docker run -p 9092:9092 apache/kafka:latest

# 2. Run offline preprocessing (Windows .venv or WSL)
python -m src.data.offline_preprocess

# 3. Train baseline model
python -m src.ml.train_baseline

# 4. Start Kafka producer (publish stream)
python -m src.streaming.kafka_producer

# 5. Run Spark streaming job (WSL, uses local Spark binary)
python -m src.streaming.spark_job

# 6. Run drift detection
python -m src.drift_detection.drift_detector
```
