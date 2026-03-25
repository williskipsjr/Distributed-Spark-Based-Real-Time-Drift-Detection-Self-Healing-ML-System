# PROJECT CONTEXT

Last updated: 2026-03-26

## Project summary

Distributed Spark-based real-time ML system for electricity load forecasting with drift detection and planned self-healing retraining.

Current primary objective: implement self-healing automation now that inference and drift validation are stabilized.

## What the system currently does

1. Builds supervised time-series dataset with lag/rolling features from PJM data.
2. Trains XGBoost model and stores artifact as bundle `{model, features}`.
3. Streams records via Kafka producer.
4. Runs Spark Structured Streaming inference and writes hourly metrics to parquet.
5. Computes drift report from baseline vs recent windows.
6. Runs drift detector over recent vs baseline windows.

## Canonical model features

```
[
  "hour_of_day",
  "day_of_week",
  "month",
  "is_weekend",
  "lag_1",
  "lag_24",
  "lag_168",
  "rolling_24",
  "rolling_168"
]
```

## Important recent technical decisions

- Model serving fixed on `artifacts/models/model_v2.joblib` with enforced feature ordering.
- Producer supports both supervised parquet and raw CSV replay with on-the-fly aggregation.
- Spark job now supports graceful finite runs via `--run-seconds`.
- Production sink writes via native Spark parquet streaming path for stability.
- Drift detector now anchors windows to latest metrics timestamp (replay-compatible).
- Drift detector handles NaN baseline std via fallback to baseline mean-prediction variability.

## Current state of major modules

- `src/data/*`: stable for aggregate supervised feature generation.
- `src/ml/train_baseline.py`: stable; outputs bundle artifacts.
- `src/streaming/kafka_producer.py`: stable; supports raw CSV aggregation and supervised parquet.
- `src/streaming/spark_job.py`: stabilized for production replay runs; graceful duration supported.
- `src/drift_detection/drift_detector.py`: stable for replay and live timelines.

## Current validated runtime commands

Producer:

```bash
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --sleep-seconds 0.1 --log-level INFO
```

Spark job (WSL):

```bash
export PYSPARK_PYTHON="$(which python)"
export PYSPARK_DRIVER_PYTHON="$(which python)"
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120
```

## What is still missing for project completion

- Feature-level drift detection (KS, PSI).
- Automated retraining and model promotion workflow (self-healing).
- Version registry and richer runtime monitoring.

