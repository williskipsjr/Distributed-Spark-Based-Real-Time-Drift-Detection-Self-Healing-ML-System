# CRITICAL ISSUE: Fix Summary

## Root Cause (1 Sentence)
Model trained on **PJM-aggregated load (~180k MW)** but serving on **individual zones (~1k MW)** → 30x scale mismatch.

---

## Quick Diagnosis

Run this:
```bash
python debug_step_by_step.py
```

Expected output will confirm:
- ✓ Model predicts CORRECTLY offline (~130k for streaming data)
- ✓ Features computed CORRECTLY (lag_1, lag_24, rolling_24)
- ✓ Model loads CORRECTLY
- **✗ Data distribution is 30x different between training and streaming**

---

## The Fix (Pick ONE)

### Fix #1: SUM Zones in Kafka Producer [RECOMMENDED]

**File**: `src/streaming/kafka_producer.py`

**Current** (buggy):
```python
for zone in pjm_zones:
    payload = {
        "timestamp": datetime.now(),
        "load_mw": zone["mw"],          # Individual zone: ~1k
        "features": {...}
    }
    producer.send(payload)
```

**Fixed**:
```python
total_pjm_load = sum(zone["mw"] for zone in pjm_zones)  # Aggregate
payload = {
    "timestamp": datetime.now(),
    "load_mw": total_pjm_load,         # Aggregate: ~180k
    "features": {...}  # Compute lags on aggregate, not individual zone
}
producer.send(payload)
```

**Why**: Matches training pipeline which did `df.groupby("datetime")["load_mw"].sum()`

---

### Fix #2: SUM Zones in Spark Job (If Producer Can't Change)

**File**: `src/streaming/spark_job.py` → `_prepare_stream()` function

Add after parsing Kafka:
```python
# Aggregate all zones to match training aggregation
aggregated_df = (
    df_parsed
    .withColumn("hour", F.date_trunc("hour", F.col("timestamp")))
    .groupBy("hour")
    .agg(
        F.sum("actual_load").alias("actual_load"),  # SUM all zones
        F.max("timestamp").alias("timestamp")
    )
    .select("timestamp", "actual_load")
)

# Recompute features on aggregated load
aggregated_with_features = add_features_spark(
    aggregated_df,
    timestamp_col="timestamp",
    target_col="actual_load"
)

return aggregated_with_features
```

**Issue**: Must recompute lag features on aggregate (complex in streaming)

---

### Fix #3: Retrain Model on Zone-Level Data (Alternative)

If you want **per-zone predictions** instead of aggregate:

```bash
# Retrain using 2019 zone-level data
python -m src.ml.train_baseline --input data/stream_dataset/hrl_load_metered-2019.csv
```

**Usage**: Deploy as separate model for zone-level forecasting.

---

## Verification

After implementing fix, test:

```python
# Run this to verify
python debug_step_by_step.py

# Should now show:
# Predicted min/max: 180,000-200,000 (not 128k like before)
# Error: < 10% (good!)  (not 180,000 like before)
```

---

## What Was Already Fixed

✓ Enhanced UDF error reporting in `spark_job.py`
✓ Added distribution shift detection warnings
✓ Debug scripts created for future diagnosis

---

## Summary

| Issue | Impact | Fix |
|-------|--------|-----|
| Zones not aggregated | Inputs 30x smaller than training | Sum zones per timestamp |
| Lag features computed wrongly | Features out-of-distribution | Compute lags on aggregate |
| No distribution checks | Silent failure | Added warnings (already done) |
| UDF errors unclear | Hard to debug | Enhanced error messages (already done) |

---

## Recommendation

**Do Fix #1** (producer-side aggregation). It's:
- Cleaner (aggregation close to source)
- Easier to test (aggregate before features)
- Safer (no recomputation logic)
- More maintainable (single source of truth)

Expected result: Error drops from 180,000 to <10,000 MW.
