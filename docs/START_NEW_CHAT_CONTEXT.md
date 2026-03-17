# START_NEW_CHAT_CONTEXT.md

> **HOW TO USE**: Copy the block below and paste it as your very first message in a new AI chat session. It gives the AI full context to resume development immediately.

---

```
=== PROJECT CONTEXT: Distributed Spark-Based Real-Time Drift Detection & Self-Healing ML System ===

AUTHORS: Ngamchingseh Willis Kipgen, Muhhamad Owais
COURSE: Big Data Analytics, IIIT Dharwad — 2nd Year, 4th Semester

---

## WHAT THIS SYSTEM IS

A production-style distributed ML platform for real-time electricity load forecasting with
automated data drift detection and self-healing model retraining using Apache Spark + Kafka.

Dataset: PJM Hourly Load (hrl_load_metered-2018.csv) — ~250k rows of hourly electricity demand.

---

## TECHNOLOGY STACK

- Apache Spark 3.5.1 (spark-3.5.1-bin-hadoop3, local[*] mode)
- Apache Kafka (Docker: apache/kafka:latest, port 9092)
- Python (XGBoost, pandas, pyarrow, joblib, kafka-python, scikit-learn, PySpark, PyYAML)
- Parquet (all storage: processed data, predictions, hourly metrics)
- WSL (Ubuntu) for running Spark job | Windows (.venv) for development
- Config: YAML deep-merge (base.yaml + dev.yaml, env via BDA_ENV)

---

## FULL PIPELINE

PJM CSV
  → offline_preprocess.py → pjm_cleaned.parquet + pjm_supervised.parquet
  → train_baseline.py → model_v1.joblib (XGBoost bundle {model, features})
    Baseline: MAE=144.99, RMSE=538.61, R²=0.9988, 199795 train / 49949 val rows

STREAMING:
  kafka_producer.py → pjm.load (Kafka topic)
    → spark_job.py (Spark Structured Streaming)
      → JSON parse → time features (Spark UDF)
      → pandas_udf inference (broadcast model)
      → hourly window aggregation (8 metric columns)
      → data/metrics/hourly_metrics/ (parquet, partitioned by timestamp_hour)
      → data/predictions/ (raw scored rows)

DRIFT DETECTION:
  drift_detector.py
    → reads data/metrics/hourly_metrics/
    → 7-day baseline window vs 24-hour recent window
    → performance_drift: recent_mean_error > baseline_mean_error × 1.5
    → prediction_drift: |recent_mean_pred - baseline_mean_pred| > baseline_std × 2
    → outputs artifacts/drift/drift_report.json

---

## REPOSITORY STRUCTURE

src/
  common/     config.py, logging.py, schemas.py
  data/       offline_preprocess.py, feature_builder.py
  ml/         train_baseline.py, model_io.py
  streaming/  kafka_producer.py, spark_job.py
  drift_detection/ drift_detector.py

configs/      base.yaml (production), dev.yaml (overrides)
data/raw/     hrl_load_metered-2018.csv
data/processed/ pjm_cleaned.parquet, pjm_supervised.parquet
data/metrics/ hourly_metrics/ (parquet written by Spark job)
data/predictions/ (scored streaming rows)
artifacts/
  models/     model_v1.joblib
  baselines/  baseline_metrics.json, baseline_features.parquet
  drift/      drift_report.json

GITIGNORED (present on disk, not in repo):
  .venv/                     ← WSL Python environment
  spark-3.5.1-bin-hadoop3/  ← Local Spark binary
  spark-3.5.1-bin-hadoop3.tgz
  data/, artifacts/, checkpoints/

---

## FEATURE COLUMNS (canonical order — must never change)

FEATURE_COLUMNS = [
  'hour_of_day', 'day_of_week', 'month', 'is_weekend',
  'lag_1', 'lag_24', 'lag_168', 'rolling_24', 'rolling_168'
]

Model saved as bundle: {"model": XGBRegressor, "features": FEATURE_COLUMNS}

---

## CURRENT STATUS (as of March 15, 2026)

✅ DONE:
  - Offline ETL + feature engineering
  - Baseline model training + artifacts
  - Kafka producer (streaming simulation)
  - Spark Structured Streaming job (inference + hourly metrics)
  - Drift detector (error-level + prediction-level drift)
  - Git housekeeping (.venv and Spark dir gitignored)
  - Complete docs/ knowledge base generated

🔲 NOT YET IMPLEMENTED:
  - Self-healing retraining pipeline (src/ml/retrain.py)
  - KS-test / PSI feature-level drift (in drift_detector.py)
  - Model version registry
  - Monitoring dashboard

📋 PENDING GIT COMMIT:
  Modified: .gitignore, configs/base.yaml, requirements.txt, src/ml/train_baseline.py
  Untracked: src/drift_detection/, src/ml/model_io.py, src/streaming/, progress.md, docs/

---

## IMMEDIATE NEXT TASKS

1. git add . && git commit -m "feat: drift detection, streaming job, model IO, docs, gitignore fix"
2. Run end-to-end test: Kafka → producer → Spark job → drift_detector
3. Implement src/ml/retrain.py (retraining pipeline triggered by drift)
4. Add KS-test + PSI to drift_detector.py (feature-level drift)

---

## RUN COMMANDS

# Start Kafka
docker run -p 9092:9092 apache/kafka:latest

# Offline pipeline (run once)
python -m src.data.offline_preprocess
python -m src.ml.train_baseline

# Live streaming
python -m src.streaming.kafka_producer --sleep-seconds 0.01  # fast replay
python -m src.streaming.spark_job                            # WSL

# Drift detection (after 25+ hours of metrics)
python -m src.drift_detection.drift_detector

---

## KEY CONFIG (base.yaml highlights)

kafka.bootstrap_servers: localhost:9092
kafka.topics.raw_load: pjm.load
spark.master: local[*]
drift.rolling_mae_increase_ratio: 1.20
retraining.window_hours: 720
retraining.recent_ratio: 0.7
retraining.cooldown_hours: 24

---

## DOCS FOLDER

Full documentation is in docs/:
  PROJECT_CONTEXT.md  ← Master reference
  ARCHITECTURE.md     ← Technical design + ASCII diagrams
  PROGRESS.md         ← Done/in-progress/todo tracker
  ISSUES_LOG.md       ← 7 documented bugs with resolutions
  RECENT_CONTEXT.md   ← Last session interactions
  DEBUG_GUIDE.md      ← 11-section debugging reference
  NEXT_STEPS.md       ← Roadmap (immediate → long-term)
  SESSION_LOG.md      ← Development history per session

=== END OF CONTEXT ===
```
