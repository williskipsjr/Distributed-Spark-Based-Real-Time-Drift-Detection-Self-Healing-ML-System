# Distributed Spark-Based Real-Time Drift Detection & Self-Healing ML System

## 1. Project Overview

This project implements a production-style Big Data ML system for **real-time electricity load forecasting** with foundations for **drift-aware self-healing retraining**.

The current implementation delivers an end-to-end core pipeline:

- Offline historical preprocessing and supervised dataset generation
- Baseline model training and artifact management
- Kafka-based streaming simulation
- Spark Structured Streaming inference pipeline
- Prediction sink storage for monitoring and downstream analytics

### System Objectives

- Build a real-time ML monitoring-ready forecasting system
- Detect and respond to distribution/performance drift (next phase)
- Maintain model quality over time using automated retraining (next phase)
- Use distributed infrastructure patterns suitable for production and research

### Core Technologies

- **Apache Spark / PySpark** (distributed stream processing)
- **Apache Kafka** (event streaming transport)
- **Python** (ML + orchestration)
- **XGBoost** (baseline regression model)
- **Parquet** (columnar data storage)
- **Spark Structured Streaming** (micro-batch streaming engine)

### Architecture Idea

Historical dataset → model training → streaming pipeline → real-time predictions → drift monitoring (planned) → automated retraining (planned).

---

## 2. Repository Structure

Current repository layout (implemented):

- `src/`
  - `common/`
    - `config.py`: YAML config loader, deep-merge, env handling
    - `logging.py`: structured logging (JSON/text)
    - `schemas.py`: shared dataclass and Spark schemas
  - `data/`
    - `offline_preprocess.py`: offline ETL to cleaned + supervised parquet
    - `feature_builder.py`: shared feature logic for pandas and Spark
  - `ml/`
    - `train_baseline.py`: baseline model training/evaluation/artifacts
    - `model_io.py`: model loading + inference utilities
  - `streaming/`
    - `kafka_producer.py`: real-time simulation publisher to Kafka
    - `spark_job.py`: Spark streaming inference job
- `configs/`
  - `base.yaml`: main runtime defaults (Kafka, Spark, paths, drift/retrain placeholders)
  - `dev.yaml`: development overrides
- `data/`
  - `raw/`: raw source CSV
  - `processed/`: `pjm_cleaned.parquet`, `pjm_supervised.parquet`
  - `predictions/`: Spark streaming prediction output
- `artifacts/`
  - `models/`: trained model binaries (`model_v1.joblib`)
  - `baselines/`: baseline metrics/features artifacts
- `checkpoints/`
  - `spark_predictions/`: Structured Streaming checkpoint state

This structure cleanly separates shared infrastructure, data engineering, model lifecycle, and streaming execution.

---

## 3. Dataset

### Dataset Name

**PJM Hourly Load Dataset**

### Relevant fields used in current implementation

- `datetime` (normalized from `Datetime Beginning EPT` / `datetime_beginning_ept`)
- `load_mw` (normalized from `MW` / `mw`)

### Why this dataset was selected

- It is a **time-series forecasting** problem with hourly resolution
- Large historical coverage makes it suitable for Big Data workflows
- Naturally prone to distribution shifts (seasonality, demand pattern changes)
- Supports realistic streaming simulation from historical records

### How it is used in this project

- Historical CSV is preprocessed offline
- Cleaned parquet is used for Kafka stream simulation
- Supervised parquet is used to train baseline ML model
- Real-time records from Kafka are scored in Spark and persisted

---

## 4. Data Preprocessing Pipeline

Module: `src/data/offline_preprocess.py`

### Implemented steps

1. Load CSV dataset (supports both `hrl_load_metered_2018.csv` and `hrl_load_metered-2018.csv`)
2. Normalize and canonicalize column names
3. Parse timestamp column using `Datetime Beginning EPT` equivalent
4. Drop invalid/null timestamp and target rows
5. Sort chronologically (by `load_area`, then `datetime`)
6. Rename `MW`/`mw` to `load_mw`
7. Build supervised features via shared `feature_builder`
8. Save parquet outputs

### Output datasets

- `data/processed/pjm_cleaned.parquet`
- `data/processed/pjm_supervised.parquet`

### Why Parquet instead of CSV

- Columnar format optimized for analytics/scans
- Better compression and IO performance
- Native fit for Spark and pandas workflows
- Preserves schema consistency for downstream pipelines

---

## 5. Feature Engineering

Module: `src/data/feature_builder.py`

### Engineered features

- `hour_of_day`
- `day_of_week`
- `month`
- `is_weekend`
- `lag_1`
- `lag_24`
- `lag_168`
- `rolling_24`
- `rolling_168`

### Implementation notes

- Shared constants: `FEATURE_COLUMNS`
- pandas functions for offline training data preparation
- Spark-compatible helpers for streaming parity (`add_time_features_spark`, `add_features_spark`)
- Deterministic ordering by group + timestamp to avoid feature leakage

### Why lag/rolling matter

Lag and rolling features encode temporal dependency and local trend context:

- `lag_1` captures immediate autocorrelation
- `lag_24` captures daily seasonality
- `lag_168` captures weekly seasonality
- rolling windows smooth noise and reveal short-term/weekly baseline behavior

These are critical for accurate electricity demand forecasting.

---

## 6. Baseline Model Training

Module: `src/ml/train_baseline.py`

### Model

- **XGBoost Regressor** (`XGBRegressor`)

### Why XGBoost

- Strong performance on tabular/time-derived features
- Handles nonlinear interactions well
- Stable and fast for baseline production-like experiments
- Good bias/variance tradeoff for this feature engineering setup

### Training process (implemented)

1. Load `data/processed/pjm_supervised.parquet`
2. Validate target + feature columns
3. Chronological split (80% train / 20% validation)
4. Train XGBoost model
5. Run validation predictions
6. Compute metrics and persist artifacts

### Evaluation metrics

- **MAE**: average absolute prediction error magnitude
- **RMSE**: penalizes larger errors more strongly than MAE
- **R²**: proportion of variance explained by the model

### Baseline run results (current)

From `artifacts/baselines/baseline_metrics.json` (Model `v1`):

- Train rows: **199,795**
- Validation rows: **49,949**
- **MAE**: **144.99097879121524**
- **RMSE**: **538.6145449681322**
- **R²**: **0.9988481287986403**

### Saved artifacts

- `artifacts/models/model_v1.joblib`
- `artifacts/baselines/baseline_metrics.json`
- `artifacts/baselines/baseline_features.parquet`

---

## 7. Model Inference Utilities

Module: `src/ml/model_io.py`

### Implemented capabilities

- Load model from explicit path or auto-load latest `.joblib` under `artifacts/models`
- Validate inference input against `FEATURE_COLUMNS`
- Predict from pandas DataFrame via `predict(...)`
- Batch scoring via `predict_batch(...)` with appended `predicted_load`
- Optional metadata support (`model_version`, default `v1`)

### Reuse value

This module is the **single inference contract** used by both offline and streaming paths, reducing logic duplication and minimizing training-serving skew.

---

## 8. Kafka Streaming Producer

Module: `src/streaming/kafka_producer.py`

### Purpose

Simulate real-time electricity load stream from historical cleaned data.

### Implemented pipeline

Load parquet → parse/sort by timestamp → publish sequential JSON records to Kafka → loop continuously.

### Kafka topic

- `pjm.load` (configured via `configs/base.yaml` → `kafka.topics.raw_load`)

### Message format

```json
{
  "timestamp": "<ISO datetime>",
  "load_mw": 12345.67
}
```

### Real-time simulation

- Per-record delay using sleep interval (`--sleep-seconds`, default `0.1`)

### Logging events

- `producer-start`
- `record-published`
- `producer-stop`

---

## 9. Spark Structured Streaming Pipeline

Module: `src/streaming/spark_job.py`

### Streaming flow

Kafka topic → Spark Structured Streaming → JSON parse → feature engineering → model inference (`foreachBatch`) → parquet output.

### Implemented steps

1. Create SparkSession with app name `pjm-load-streaming`
2. Include Kafka connector package:
   - `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1`
3. Subscribe to Kafka topic `pjm.load`
4. Parse JSON payload (`timestamp`, `load_mw`)
5. Transform to prediction frame (`actual_load`, time features)
6. Load model once at startup (`artifacts/models/model_v1.joblib`)
7. Score each micro-batch in `foreachBatch`:
   - Spark batch → pandas
   - `predict_batch()`
   - append `model_version`
   - pandas → Spark DataFrame
8. Write predictions in append mode to parquet

### Output fields

- `timestamp`
- `actual_load`
- `predicted_load`
- `model_version`

### Output location

- `data/predictions/`

### Checkpointing

- `checkpoints/spark_predictions/`

### Why checkpointing is required

Checkpointing preserves stream progress and state for fault tolerance, enabling restart recovery and preventing duplicated processing across restarts.

### Logging events

- `spark-stream-start`
- `batch-processed`
- `prediction-written`

---

## 10. System Architecture (Current Implemented Flow)

PJM Dataset  
↓  
Offline preprocessing  
↓  
Feature engineering  
↓  
Baseline model training  
↓  
Kafka producer (simulated stream)  
↓  
Kafka topic (`pjm.load`)  
↓  
Spark Structured Streaming  
↓  
ML prediction pipeline  
↓  
Prediction storage (`data/predictions`)  

---

## 11. Current Project Status

Completed so far:

- ✔ Dataset ingestion and normalization
- ✔ Deterministic feature engineering (offline + Spark helpers)
- ✔ Baseline ML model training (XGBoost)
- ✔ Evaluation metrics computation (MAE, RMSE, R²)
- ✔ Model artifact and baseline metadata storage
- ✔ Kafka producer for real-time simulation
- ✔ Spark Structured Streaming ingestion and scoring pipeline
- ✔ Real-time prediction output persistence with checkpointing

Infrastructure also completed:

- Structured config system (`base.yaml` + `dev.yaml`, deep-merge loader)
- Structured logging system for operational observability
- Shared schema module for data contracts

---

## 12. Next Steps (Future Work)

Planned implementation phases:

1. **Drift Detection Engine**
   - Feature distribution drift checks per window
   - Trigger policy integration

2. **Statistical Monitoring**
   - Kolmogorov–Smirnov test
   - Population Stability Index (PSI)
   - Prediction/error distribution monitoring

3. **Automatic Retraining System**
   - Recent window extraction
   - Candidate model training and validation
   - Promotion gate (deploy-if-better)

4. **Model Version Management**
   - Expanded registry with lifecycle events
   - Promotion/replacement logs

5. **Monitoring Dashboard**
   - Streaming metrics visualization
   - Drift alerts
   - Model timeline and performance trends

---

## 13. Why This Is a Big Data System

This project qualifies as a Big Data/ML systems implementation because it combines:

- **Distributed compute** via Spark processing model
- **Streaming ingestion and micro-batch processing** via Kafka + Structured Streaming
- **Scalable storage patterns** using Parquet sinks and artifactized model lifecycle
- **Real-time ML inference architecture** in continuous pipeline form
- **Large historical dataset handling** with offline/online integration patterns

The system is not just model training; it is an end-to-end ML data platform foundation.

---

## 14. Resume Value

This project demonstrates practical engineering capability in:

- Big Data Engineering
- Real-Time Data Pipelines
- Distributed ML Systems
- Spark Structured Streaming
- Kafka Streaming Architecture
- ML Model Monitoring Foundations
- Production-style MLOps project structuring and artifact management

It reflects applied skills in building reliable, modular, and extensible ML systems suitable for infrastructure-scale forecasting use cases.
