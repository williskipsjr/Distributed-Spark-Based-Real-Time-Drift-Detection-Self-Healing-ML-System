# PROJECT_CONTEXT.md

---

## Project Overview

This project is a **production-style distributed ML platform** for real-time electricity load forecasting with built-in mechanisms for detecting data/model drift and triggering automated model retraining.

The system ingest a live stream of electricity consumption records via **Kafka**, processes them using **Apache Spark Structured Streaming**, scores each record against a trained **XGBoost model**, aggregates hourly performance metrics, and runs a **drift detector** that compares recent prediction quality against a historical baseline—escalating to self-healing retraining when drift is confirmed.

---

## Problem Statement

ML models deployed in production on time-series data degrade silently as real-world distributions shift (seasonality changes, demand pattern changes, data pipeline changes). Without monitoring, this degradation is invisible until user-facing quality drops.

This system solves:

- **Continuous real-time inference** on streaming electricity load data
- **Automated drift detection** by comparing recent vs. historical error distributions
- **Self-healing retraining** pipeline that promotes better models without human intervention
- **Observability** through structured logging and parquet-based metric sinks

---

## Authors

- **Ngamchingseh Willis Kipgen**
- **Muhhamad Owais**

Course: Big Data Analytics (BDA-Project) — IIIT Dharwad, 2nd Year, 4th Semester

---

## Key Objectives

| # | Objective | Status |
|---|-----------|--------|
| 1 | Real-time ML inference on streaming Kafka data | ✅ Done |
| 2 | Feature engineering parity (offline + online) | ✅ Done |
| 3 | Hourly metrics aggregation (error + prediction stats) | ✅ Done |
| 4 | Drift detection engine (window-based statistical checks) | ✅ Done |
| 5 | Self-healing automated retraining pipeline | 🔲 Planned |
| 6 | KS-test / PSI-based feature distribution drift | 🔲 Planned |
| 7 | Model version registry with promotion gate | 🔲 Planned |
| 8 | Monitoring dashboard | 🔲 Planned |

---

## Technology Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| Stream transport | Apache Kafka | Docker `apache/kafka:latest`, port `9092` |
| Stream processing | Apache Spark / PySpark | 3.5.1 (`spark-3.5.1-bin-hadoop3`) |
| ML model | XGBoost | `XGBRegressor` via `xgboost>=2.0` |
| Data serialization | Apache Parquet | via `pyarrow>=15.0` |
| Data manipulation | pandas | `>=2.2` |
| Model persistence | joblib | `>=1.3` |
| Kafka Python client | kafka-python | `>=2.0` |
| Scikit-learn | scikit-learn | `>=1.4` (metrics, preprocessing) |
| Config system | PyYAML | `>=6.0`, deep-merged YAML |
| OS / Runtime | WSL (Ubuntu) + Windows | Spark job runs in WSL; dev in Windows venv |
| Python env (dev) | `.venv` (Windows) | VS Code development |
| Python env (runtime) | `.venv` (WSL) | Spark job execution |
| Container runtime | Docker | Kafka broker |

---

## Project Folder Structure

```
Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System/
│
├── configs/
│   ├── base.yaml              # Production runtime defaults (Kafka, Spark, drift, retrain)
│   └── dev.yaml               # Development overrides (deep-merged on top of base)
│
├── src/
│   ├── __init__.py
│   ├── common/
│   │   ├── config.py          # YAML config loader with deep-merge + env selection
│   │   ├── logging.py         # Structured logging (JSON/text, event-key pattern)
│   │   └── schemas.py         # Shared dataclass + Spark StructType schemas
│   ├── data/
│   │   ├── offline_preprocess.py   # ETL: CSV → cleaned + supervised parquet
│   │   └── feature_builder.py      # Feature engineering (pandas + Spark helpers)
│   ├── ml/
│   │   ├── train_baseline.py  # XGBoost training, evaluation, artifact saving
│   │   └── model_io.py        # Model load / predict / predict_batch (bundle format)
│   ├── streaming/
│   │   ├── kafka_producer.py  # Publishes historical records to Kafka as live stream
│   │   └── spark_job.py       # Spark Structured Streaming inference + metrics job
│   └── drift_detection/
│       └── drift_detector.py  # Drift analysis on hourly metrics parquet
│
├── data/
│   ├── raw/
│   │   └── hrl_load_metered-2018.csv   # PJM Hourly Load source dataset
│   ├── processed/
│   │   ├── pjm_cleaned.parquet         # Cleaned + normalized data
│   │   └── pjm_supervised.parquet      # With engineered features (lag, rolling)
│   ├── predictions/                    # Scored records from streaming job
│   └── metrics/
│       └── hourly_metrics/             # Parquet: hourly aggregated error + prediction stats
│
├── artifacts/
│   ├── models/
│   │   └── model_v1.joblib             # Trained XGBoost bundle {model, features}
│   ├── baselines/
│   │   ├── baseline_metrics.json       # MAE, RMSE, R² from training run
│   │   └── baseline_features.parquet   # Feature stat snapshot for drift reference
│   └── drift/
│       └── drift_report.json           # Latest drift detection output
│
├── checkpoints/
│   └── spark_predictions/              # Spark Structured Streaming checkpoint state
│
├── spark-3.5.1-bin-hadoop3/            # Local Spark binary (gitignored)
├── .venv/                              # Python venv (gitignored)
├── .gitignore
├── requirements.txt
├── progress.md                         # Live development progress notes
└── docs/                              # ← This knowledge base folder
```

---

## End-to-End Data Pipeline Summary

```
PJM Historical CSV (hrl_load_metered-2018.csv)
           │
           ▼
  offline_preprocess.py
  (normalize, sort, clean)
           │
           ▼
  feature_builder.py
  (lag_1, lag_24, lag_168, rolling_24, rolling_168,
   hour_of_day, day_of_week, month, is_weekend)
           │
      ┌────┴────┐
      ▼         ▼
pjm_cleaned   pjm_supervised
.parquet       .parquet
      │         │
      │         ▼
      │   train_baseline.py
      │   (XGBoost, chrono split 80/20)
      │         │
      │   model_v1.joblib + baseline_metrics.json
      │
      ▼
kafka_producer.py
(reads cleaned parquet, publishes JSON records)
           │
           ▼
  Kafka topic: pjm.load
           │
           ▼
  spark_job.py (Spark Structured Streaming)
  ├── JSON parse → feature engineering (Spark UDF)
  ├── pandas_udf batch inference (broadcast model)
  ├── error column: |actual_load - predicted_load|
  └── _build_hourly_metrics() → 1-hour window aggregation
           │
      ┌────┴──────────────────┐
      ▼                       ▼
data/predictions/      data/metrics/hourly_metrics/
(scored records)       (mean/max/min/std prediction,
                        mean/max error, record_count)
                               │
                               ▼
                    drift_detector.py
                    ├── 7-day baseline window
                    ├── 24-hour recent window
                    ├── performance_drift check
                    └── prediction_drift check
                               │
                               ▼
                    artifacts/drift/drift_report.json
                               │
                    [PLANNED] → Retraining Pipeline
                               │
                    [PLANNED] → Model Promotion Gate
```

---

## System Components

### `src/common/config.py`
YAML-based config loader. Loads `base.yaml` then deep-merges `dev.yaml` (or any env file) on top. Environment selected via `BDA_ENV` env var or explicit `env_name`. Returns a `Config` object with dot-path access (`config.get("kafka.bootstrap_servers")`).

### `src/common/logging.py`
Structured logging wrapper. Emits JSON (production) or text (dev) log entries. Uses event-key pattern (e.g., `"spark-stream-start"`, `"drift-detected"`) for machine-parseable operational logs.

### `src/common/schemas.py`
Shared Spark `StructType` schemas and Python dataclasses for cross-module data contracts. Prevents schema drift between producer, streaming job, and drift detector.

### `src/data/offline_preprocess.py`
Offline ETL: loads the PJM CSV, normalizes columns, parses timestamps, drops nulls, sorts chronologically, calls `feature_builder` to generate lag/rolling features, and writes two parquets.

### `src/data/feature_builder.py`
Canonical feature engineering module. Defines `FEATURE_COLUMNS` (the exact ordered list used everywhere). Provides pandas functions for offline use and Spark-compatible helpers (`add_time_features_spark`, `add_features_spark`) for streaming parity.

### `src/ml/train_baseline.py`
Trains an `XGBRegressor` on `pjm_supervised.parquet` with a strict chronological 80/20 split. Saves the model as a bundle `{"model": estimator, "features": FEATURE_COLUMNS}` via joblib. Writes metrics JSON and feature stats parquet.

### `src/ml/model_io.py`
Single inference contract used by both offline scoring and the Spark streaming job. Auto-wraps legacy raw-estimator artifacts in bundle format. `predict_batch()` appends `predicted_load` to a DataFrame.

### `src/streaming/kafka_producer.py`
Reads `pjm_cleaned.parquet`, sorts by timestamp, and publishes records one-by-one to `pjm.load` Kafka topic as `{"timestamp": ..., "load_mw": ...}` JSON. Supports configurable sleep interval for rate control.

### `src/streaming/spark_job.py`
The core streaming runtime. Creates a SparkSession with the Kafka connector package, subscribes to `pjm.load`, applies time features via Spark UDF, runs batch inference with a broadcast XGBoost model via `pandas_udf`, computes hourly windowed metrics, and writes deduplicated hourly parquet files to `data/metrics/hourly_metrics/`.

### `src/drift_detection/drift_detector.py`
Loads all hourly metrics parquet files, splits data into a **7-day baseline window** and a **24-hour recent window**, then evaluates two drift signals:
- **performance_drift**: `recent_mean_error > baseline_mean_error × 1.5`
- **prediction_drift**: `|recent_mean_prediction − baseline_mean_prediction| > baseline_std × 2`

Outputs a JSON report to `artifacts/drift/drift_report.json`.
