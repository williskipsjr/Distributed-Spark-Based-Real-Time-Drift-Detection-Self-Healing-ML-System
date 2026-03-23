# Distributed Spark-Based Real-Time Drift Detection & Self-Healing ML System

Real-time ML inference pipeline for power load forecasting using **Kafka + Spark Structured Streaming + XGBoost**, with drift-monitoring workflow and diagnostics for production debugging.

## Overview

This project supports:

- Offline supervised dataset training (`XGBoost`)
- Real-time Kafka ingestion (`pjm.load`)
- Spark Structured Streaming inference using Pandas UDF
- Prediction/error metric generation
- Drift detection module (separate component)
- Strong debugging hooks for feature and inference validation

## Tech Stack

- Python 3.10+
- Apache Spark 3.5.x
- Apache Kafka
- Pandas / NumPy
- XGBoost / scikit-learn
- Joblib
- Parquet-based artifacts and outputs

## Repository Layout

```text
.
├── artifacts/
│   ├── baselines/
│   └── models/
├── configs/
│   └── base.yaml
├── data/
│   ├── processed/
│   └── metrics/
├── docs/
├── src/
│   ├── common/
│   ├── data/
│   ├── drift_detection/
│   ├── ml/
│   │   └── train_baseline.py
│   └── streaming/
│       └── spark_job.py
└── README.md
```
## Model Training (Offline)

Train baseline model artifact and metrics:

````bash
python -m src.ml.train_baseline --log-level INFO