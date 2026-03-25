# START NEW CHAT CONTEXT

Copy and paste this block in a new chat to resume fast.

```
PROJECT: Distributed Spark-Based Real-Time Drift Detection Self-Healing ML System
UPDATED: 2026-03-26

CURRENT GOAL:
- build self-healing trigger + retraining workflow on top of stable inference and drift detection

SYSTEM OVERVIEW:
- Offline: preprocess -> supervised features -> XGBoost train -> model bundle artifact
- Streaming: Kafka producer -> Spark Structured Streaming inference -> hourly metrics parquet
- Drift: baseline/recent window comparison from hourly parquet metrics

CANONICAL FEATURE ORDER:
["hour_of_day","day_of_week","month","is_weekend","lag_1","lag_24","lag_168","rolling_24","rolling_168"]

CRITICAL FIXES ALREADY APPLIED:
- Strict feature-order enforcement in serving path from bundle features
- Spark run stabilization in local environment (single local worker + hardened runtime configs)
- Production writer path migrated to native Spark parquet sink (removed fragile callback path)
- Added graceful finite run support: `--run-seconds`
- Drift detector uses latest metrics timestamp anchor (works for historical replay data)
- Drift detector handles NaN baseline std via fallback

DEPLOYED SERVING MODEL:
- artifacts/models/model_v2.joblib

RECENT VALIDATION SNAPSHOT:
- metrics summary loaded successfully from hourly parquet:
  - rows: 2786
  - prediction range realistic (no invalid scale collapse)
- drift detector output:
  - drift_detected: false
  - drift_type: none

NEXT ACTIONS:
1) Implement self-healing trigger on drift_report.json
2) Implement retraining runner and promotion checks
3) Add model version registry updates on promotion
4) Add operational smoke/regression scripts

KNOWN GOOD RUN COMMANDS (WSL):
producer:
python -m src.streaming.kafka_producer --dataset "data/stream_dataset/hrl_load_metered-2019.csv" --sleep-seconds 0.1 --log-level INFO

spark:
export PYSPARK_PYTHON="$(which python)"
export PYSPARK_DRIVER_PYTHON="$(which python)"
python -m src.streaming.spark_job --no-debug-mode --run-seconds 120

drift:
python -m src.drift_detection.drift_detector

KNOWN PENDING WORK:
- KS/PSI feature-level drift implementation
- self-healing retraining and promotion automation
- model registry and monitoring layer
```

