# NEXT_STEPS.md

---

## Immediate Next Tasks

These should be done in the next development session.

### 1. Commit pending changes to Git

```bash
cd Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System
git add .gitignore configs/base.yaml requirements.txt src/ml/train_baseline.py
git add src/drift_detection/ src/ml/model_io.py src/streaming/
git add progress.md docs/
git commit -m "feat: add drift detection, streaming job, model IO; fix gitignore"
git push
```

### 2. Test full end-to-end pipeline

Run all components together and verify metrics are written:

```bash
# Terminal 1 — Kafka (Docker)
docker run -p 9092:9092 apache/kafka:latest

# Terminal 2 — Kafka producer (Windows/WSL)
python -m src.streaming.kafka_producer --sleep-seconds 0.01

# Terminal 3 — Spark job (WSL)
python -m src.streaming.spark_job

# After ~1 hour of data (or use faster replay), run:
python -m src.drift_detection.drift_detector
```

### 3. Verify `data/metrics/hourly_metrics/` is being populated

Use the snippet from [DEBUG_GUIDE.md](DEBUG_GUIDE.md#1-inspect-hourly-metrics-drift-input-data) to confirm parquet files are written and schema is correct.

---

## Short-Term Goals

### Phase 3: Advanced Drift Detection

**Goal**: Implement proper feature-level statistical drift detection alongside the existing error-level checks.

**Tasks**:
- [ ] Add KS-test per feature column using `scipy.stats.ks_2samp`
  - Threshold: `ks_pvalue_threshold: 0.05` (from `base.yaml`)
  - Inputs: `baseline_features.parquet` baseline distribution vs. recent streaming window
- [ ] Add Population Stability Index (PSI) per feature
  - Warning threshold: `psi_warning_threshold: 0.10`
  - Critical threshold: `psi_critical_threshold: 0.25`
- [ ] Emit per-feature drift breakdown in `drift_report.json`
- [ ] Add `drift_type` = `"feature_drift"` as a third signal alongside `performance_drift` and `prediction_drift`

**File to modify**: `src/drift_detection/drift_detector.py`

---

### Phase 4: Self-Healing Retraining Pipeline

**Goal**: Automatically retrain the model when drift is confirmed and promote it if it outperforms the current deployed model.

**Tasks**:
- [ ] Create `src/ml/retrain.py` module
- [ ] Implement recent-window data extraction:
  - Window size: `retraining.window_hours = 720` hours
  - Blend ratio: `retraining.recent_ratio = 0.7`, `historical_ratio = 0.3`
  - Min samples guard: `retraining.min_samples = 500`
- [ ] Retrain XGBoost on blended dataset
- [ ] Evaluate candidate model vs. deployed model on validation set
- [ ] Implement promotion gate: deploy only if candidate MAE < current MAE
- [ ] Save as `artifacts/models/deployed_model.joblib`
- [ ] Log retraining event with timestamp, metrics, decision
- [ ] Honor cooldown: `retraining.cooldown_hours = 24` (no retrain within 24h of last retrain)

**Integration**: `drift_detector.py` should call `retrain.py` after writing the drift report when `drift_detected = true`.

---

### Phase 5: Model Version Registry

**Goal**: Track model lifecycle — training, deployment, and retirement.

**Tasks**:
- [ ] Create `artifacts/models/registry.json` — version log with timestamps and metrics
- [ ] Version naming: `model_v1`, `model_v2`, etc.
- [ ] Log entries on: train, promote, retire
- [ ] Update `model_io.py` to read from registry for `get_model_version()`

---

## Long-Term Goals

### Monitoring Dashboard

**Option A — Streamlit (simple, fast)**
```python
# pip install streamlit
import streamlit as st
import pandas as pd

df = pd.concat([pd.read_parquet(f) for f in Path("data/metrics/hourly_metrics").rglob("*.parquet")])
st.line_chart(df.set_index("timestamp_hour")[["mean_error", "mean_prediction"]])
```

**Option B — Grafana + Prometheus** (production-grade, more setup)  
**Option C — FastAPI + React** (custom, educational)

**Key metrics to display**:
- Rolling MAE trend over time
- `drift_detected` flag timeline
- Model version history
- Prediction vs. actual load comparison

---

### Production Hardening

- [ ] Replace `local[*]` Spark master with actual cluster (YARN or Kubernetes)
- [ ] Replace Docker standalone Kafka with Kafka cluster (multiple brokers)
- [ ] Add schema registry for Kafka messages (Confluent Schema Registry or Avro)
- [ ] Add dead-letter queue for malformed Kafka messages
- [ ] Implement model serving as REST API (FastAPI + `/predict` endpoint)
- [ ] Add CI/CD pipeline for automated testing on code changes
- [ ] Add unit tests for `feature_builder.py`, `drift_detector.py`, `model_io.py`

---

### Academic / Submission Goals

- [ ] Final project report documenting architecture, experiments, and results
- [ ] Demo video showing end-to-end pipeline: data stream → predictions → drift alert
- [ ] GitHub repository clean and organized with README, docs, and working code
- [ ] Benchmark: compare drift detection with/without self-healing retraining
