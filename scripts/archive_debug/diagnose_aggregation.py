"""
Diagnose data aggregation mismatch between training and streaming data.

Key question: Why is streaming data ~30x smaller than training data?
Answer: Different aggregation levels!
"""

import pandas as pd
from src.data.feature_builder import FeatureSpec, build_supervised_pandas

# Load training data
print("TRAINING DATA AGGREGATION ANALYSIS")
print("="*80)
train_df = pd.read_parquet("data/processed/pjm_supervised.parquet")
print(f"Training data shape: {train_df.shape}")
print(f"Unique load_areas in training: {train_df['load_area'].nunique()}")
print(f"\nLoad area list (first 20):")
print(train_df["load_area"].unique()[:20])

# Sample stats by area
print(f"\nTraining data stats by load_area:")
area_stats = train_df.groupby("load_area")["load_mw"].agg(["count", "mean", "min", "max"])
print(area_stats.head(10))

# Load streaming data
print("\n" + "="*80)
print("STREAMING DATA AGGREGATION ANALYSIS")
print("="*80)
stream_raw = pd.read_csv("data/stream_dataset/hrl_load_metered-2019.csv")
print(f"Streaming raw data shape: {stream_raw.shape}")
print(f"Columns: {list(stream_raw.columns)}")

# Check aggregation levels
print(f"\nUnique zones: {stream_raw['zone'].nunique()}")
print(f"Unique load_areas: {stream_raw['load_area'].nunique()}")
print(f"Unique mkt_regions: {stream_raw['mkt_region'].nunique()}")
print(f"Unique nerc_regions: {stream_raw['nerc_region'].nunique()}")

# Check which load_areas match
stream_areas = set(stream_raw["load_area"].unique())
train_areas = set(train_df["load_area"].unique())

print(f"\nCommon load_areas: {len(stream_areas & train_areas)}")
print(f"Training-only: {len(train_areas - stream_areas)}")
print(f"Streaming-only: {len(stream_areas - train_areas)}")

# Find metrics
if len(stream_areas & train_areas) > 0:
    common = list(stream_areas & train_areas)[0]
    print(f"\n--- Comparing common area: {common} ---")

    train_subset = train_df[train_df["load_area"] == common]
    stream_subset = stream_raw[stream_raw["load_area"] == common]

    print(f"Training {common}: mean load = {train_subset['load_mw'].mean():,.2f}")
    print(f"Streaming {common}: mean load = {stream_subset['mw'].mean():,.2f}")
    print(f"Ratio: {stream_subset['mw'].mean() / train_subset['load_mw'].mean():.3f}x")

# Recommendation
print("\n" + "="*80)
print("ROOT CAUSE & RECOMMENDATION:")
print("="*80)
print("""
The streaming CSV provides electricity load at ZONE and LOAD_AREA level,
but may not be aggregated to the same level as training data.

OPTIONS TO FIX:

1. VERIFY AGGREGATION LEVEL:
   Check if training data load_mw is per-zone or aggregated to area/region level.
   If training is aggregate, stream data needs to be aggregated same way.

2. AGGREGATE STREAMING TO TRAINING LEVEL:
   If training_load_mw = SUM(all zones in load_area):
       Add aggregation in Kafka producer or Spark:
       stream_df.groupBy("datetime", "load_area").agg(F.sum("mw")).cast("load_mw")

3. RETRAIN MODEL:
   If streaming is truly per-zone (smaller values), retrain model on:
   - 2019 per-zone data for baseline
   - Or use domain adaptation / transfer learning

4. SCALER APPROACH:
   If you must use existing model, apply MinMaxScaler or StandardScaler
   to align 2019 data to 2018 range (not recommended for production).
""")
