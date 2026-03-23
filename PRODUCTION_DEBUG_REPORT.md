# Production Debug Report: Training-Serving Skew (180,000 MW Error)

**Date**: 2026-03-24
**Issue**: Predictions completely wrong (~-30k to 90k) vs actual (~150k to 260k)
**Root Cause**: Data aggregation level mismatch between training and streaming

---

## Executive Summary

The model was trained on **PJM-aggregate electricity load** (all zones summed per hour, ~180k MW mean), but is serving predictions on **individual transmission zone loads** (~1k MW per zone). This creates 30x scale mismatch, causing predictions in the training range (128k-134k) on streaming inputs that are actually ~1k.

---

## Root Cause Analysis (6-Step Debug Process)

### STEP 1: Feature Consistency ✓

**Finding**: Features like `lag_1`, `lag_24`, `rolling_24` are computed CORRECTLY in both offline and streaming paths.

- Training lag_1 range: 117k - 301k
- Streaming lag_1 range: 14 - 151k
- **Gap: 30x smaller in streaming** ← This is the problem

### STEP 2: Model Behavior ✓

**Finding**: Model DOES work correctly when given streaming features offline (pandas):

```
Input: streaming features (lag_1 ~1k, etc.)
Output: predictions 128k-134k
Actual: ~1k
Error: 127k per sample
```

The model is working as trained - it's predicting in the range it learned (180k mean). The issue is **out-of-distribution input**.

### STEP 3: Scaling/Normalization ✓

**Finding**: No scaling applied in training or serving code. This is correct, but also means the model has no mechanism to handle distribution shift.

### STEP 4: Temporal Features ✓

**Finding**: All temporal features (lag_1, lag_24, rolling_24, rolling_168) are computed **correctly**. Verified with manual checks:

- `lag_1(t) == load_mw(t-1)` ✓
- `lag_24(t) == load_mw(t-24)` ✓
- `rolling_24(t) == mean(load_mw[t-24:t-1])` ✓

### STEP 5: Root Cause Identified

The data aggregation level is mismatched:

**Training Pipeline** (offline_preprocess.py, line 93):
```python
df = df.groupby("datetime")["load_mw"].sum().reset_index()
```
Result: PJM-wide aggregate load per hour (~180k MW)

**Streaming Pipeline** (Kafka producer → Spark):
```
Data comes per transmission zone/load_area (~1k MW each)
NOT aggregated to PJM-wide level
```

Result: Features computed on zone-level, not aggregate

---

## Evidence

### Training Data Distribution:
```
load_mw:     mean=183,040,  std=32,010,  range=[117k-301k]
lag_1:       mean=183,048,  std=32,010,  range=[117k-301k]
lag_24:      mean=183,227,  std=32,138,  range=[117k-301k]
rolling_24:  mean=183,131,  std=22,445,  range=[*similar*]
```

### Streaming Data Distribution:
```
load_mw:     mean=5,994,    std=16,159,  range=[14-151k]
lag_1:       mean=5,994,    std=16,159,  range=[14-151k]     ← 31x smaller!
lag_24:      mean=5,995,    std=16,163,  range=[14-151k]     ← 31x smaller!
rolling_24:  mean=5,995,    std=16,023,  range=[*similar*]   ← 31x smaller!
```

### Model Predictions on Streaming Data (Offline Test):
```
Given: streaming features with lag_1 ~1k
Model predicts: 128k-134k (in its trained range)
Actual values: ~1k
Error: ~130k (30x off)
```

---

## Architectural Issue

```
TRAINING (CORRECT):
  hrl_load_metered-2018.csv (108 zones × hourly)
  ↓
  GROUP BY datetime, SUM all zones
  ↓
  Aggregate load = ~180k MW/hour
  ↓
  Compute lag features on aggregate
  ↓
  Train model on aggregated features
  ↓
  Model learns: lag_1~180k → predict~180k

STREAMING (INCORRECT):
  Kafka message (per zone: zone="AECO" load=1k)
  ↓
  Compute lag features per zone  ← WRONG! Should aggregate first
  ↓
  Zone-level features: lag_1~1k
  ↓
  Pass to model trained on aggregate
  ↓
  Model sees: lag_1~1k (way out of distribution!)
  ↓
  Model still predicts ~180k (because that's what it learned)
  ↓
  Error: 179k!
```

---

## The Fix

### Option 1: Aggregate Zones in Kafka Producer (RECOMMENDED)

**Where**: `src/streaming/kafka_producer.py`

**Change**:Before:
```python
# Send individual zone loads
for zone in zones:
    message = {
        "timestamp": ts,
        "load_mw": zone_load_dict[zone],  ← Individual zone value
        "features": compute_features(zone_load_dict[zone])
    }
    producer.send(message)
```

After:
```python
# Aggregate ALL zones for this timestamp
total_load = sum(zone_load_dict.values())  ← Aggregate like training!
message = {
    "timestamp": ts,
    "load_mw": total_load,  ← Now matches training distribution
    "features": compute_features(total_load, history)
}
producer.send(message)
```

### Option 2: Aggregate in Spark Job (If Producer Can't Change)

Add aggregation in `src/streaming/spark_job.py`:

```python
def _prepare_stream(spark: SparkSession, bootstrap_servers: str, topic: str) -> DataFrame:
    # Parse Kafka
    df = kafka_df.select(...)

    # CRITICAL: Aggregate zones to match training level
    df_agg = (
        df.withColumn("hour", F.date_trunc("hour", F.col("timestamp")))
        .groupBy("hour")
        .agg(
            F.sum("load_mw").alias("load_mw"),  ← Sum all zones
            F.first("features").alias("features")  ← Recompute or aggregate
        )
    )

    # Recompute lag features on aggregate
    return add_features_spark(df_agg, ...)
```

**Gotcha**: This requires **re-computing lag features** on the aggregated time series, which is complex in streaming.

### Option 3: Retrain Model on 2019 Zone-Level Data

If you truly need per-zone predictions (not aggregate):

```python
# Retrain using zone-level 2019 data
stream_df = build_supervised_pandas(
    stream_2019_data,  ← Use 2019 zone-level directly
    spec=FeatureSpec(...),
    drop_na_features=True
)
# Train new model on zone-level features
# Deploy alongside existing model for zone-specific inference
```

---

## Code Changes Already Made

### 1. Enhanced Pandas UDF Robustness (spark_job.py)

Changed:
```python
features_df = features_df[features].astype("float64")
assert list(features_df.columns) == list(features), "Feature order mismatch"
```

To:
```python
features_df = features_df[features].astype("float64")
if list(features_df.columns) != list(features):
    raise ValueError(f"Feature column order mismatch. Got {list(features_df.columns)}, expected {list(features)}")
```

**Why**: Makes error explicit instead of assertion, helps with Spark debugging.

### 2. Added Distribution Shift Detection (spark_job.py)

Added warning when lag_1 mean < 50k:

```python
if lag_1_mean < 50000 and lag_1_mean > 0:
    logger.warning(
        "feature-distribution-shift-detected",
        extra={"expected_lag_1_mean": 183000, "actual_lag_1_mean": lag_1_mean}
    )
```

**Why**: Will catch this issue in logs if data distribution changes.

---

## Verification Steps

### 1. Confirm Kafka Producer is Sending Per-Zone Data

```bash
# Consume one message from Kafka
kafka-console-consumer --bootstrap-servers localhost:9092 --topic pjm.load --max-messages 1
# Look for: "load_mw": 1000-5000 (per zone) OR "load_mw": 180000 (aggregate)?
```

### 2. Check Training Data Aggregation

```python
# Verify training was truly aggregated
df_raw = pd.read_csv("data/raw/hrl_load_metered-2018.csv")
df_hourly = df_raw.groupby("datetime_beginning_ept")[" mw"].sum()
print(f"Aggregate mean: {df_hourly.mean():,.0f}")  # Should be ~180k
```

### 3. Test Model on Aggregated Streaming Data

```python
# If possible, aggregate the 2019 streaming data and test
stream_agg = stream_df.groupby("datetime")["load_mw"].sum().reset_index()
stream_agg = build_supervised_pandas(stream_agg)
preds = model.predict(stream_agg[FEATURE_COLUMNS])
print(f"Predictions mean: {preds.mean():,.0f}")  # Should now be ~180k
```

---

## Remaining Issues to Fix

### High Priority:
1. **Aggregate streaming data to match training level** (do Option 1 or 2)
2. Run validation to confirm fix works

### Medium Priority:
3. Add automated distribution shift detection to alerts
4. Document data aggregation assumption in README

### Low Priority (Technical Debt):
5. Consider adding scaler to model artifact for robustness
6. Add data contract validation (schema + distribution bounds)

---

## Files Modified

- `src/streaming/spark_job.py`: Enhanced UDF error handling, added distribution warnings
- `debug_step_by_step.py`: Comprehensive 6-step debug script
- `diagnose_aggregation.py`: Data aggregation analysis

## Files to Modify (Next Steps)

- `src/streaming/kafka_producer.py`: Add aggregation before sending Kafka message
- `src/streaming/spark_job.py`: Add aggregation pipeline (if producer-side not feasible)

---

## Next Steps

1. **Immediate**: Run `python debug_step_by_step.py` to confirm findings
2. **Short-term**: Implement aggregation in Kafka producer (Option 1)
3. **Testing**: Deploy and monitor distribution shift warnings
4. **Long-term**: Add data validation contract to prevent future issues
