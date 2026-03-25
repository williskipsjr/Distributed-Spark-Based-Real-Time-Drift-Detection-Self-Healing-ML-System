"""Check what data the Kafka producer would actually send."""

from pathlib import Path
from src.streaming.kafka_producer import _load_and_prepare_data, _resolve_dataset_path
import pandas as pd

print(f"\n{'='*80}")
print("KAFKA PRODUCER DATA VERIFICATION")
print(f"{'='*80}\n")

# Check what the producer would send when called with defaults
try:
    resolved = _resolve_dataset_path(None)
    print(f"Default dataset resolved to: {resolved}")
    
    df = _load_and_prepare_data(resolved)
    
    print(f"\nData loaded from producer pipeline:")
    print(f"  Rows: {len(df)}")
    print(f"  Mean load_mw: {df['load_mw'].mean():,.0f} MW")
    print(f"  Min load_mw: {df['load_mw'].min():,.0f} MW")
    print(f"  Max load_mw: {df['load_mw'].max():,.0f} MW")
    print(f"  Mean lag_1: {df['lag_1'].mean():,.0f} MW")
    print(f"  Columns: {list(df.columns)}")
    
    # Check if this matches training expectation
    if df['load_mw'].mean() > 100000:
        print(f"\n✓ DATA IS AGGREGATED (PJM-wide, ~180k scale)")
        print(f"  → Kafka producer will send correct aggregated data")
        print(f"  → Model V2 will work correctly")
    elif df['load_mw'].mean() < 10000:
        print(f"\n✗ DATA IS ZONE-LEVEL (per-area, ~1k-6k scale)")
        print(f"  → Kafka producer sends WRONG data")
        print(f"  → Model will fail with OOD predictions")
    else:
        print(f"\n? DATA IS AMBIGUOUS (scale {df['load_mw'].mean():,.0f})")
        
except Exception as e:
    print(f"Error: {e}")

# Also check what raw 2019 data looks like
print(f"\n{'='*80}")
print("2019 ZONE-LEVEL DATA (raw CSV):")
print(f"{'='*80}\n")

raw_2019 = Path("data/stream_dataset/hrl_load_metered-2019.csv")
if raw_2019.exists():
    df_raw = pd.read_csv(raw_2019)
    print(f"Unique timestamps: {df_raw['datetime_beginning_ept'].nunique()}")
    print(f"Unique load areas (zones): {df_raw['load_area'].nunique()}")
    print(f"Total records: {len(df_raw)}")
    
    # Group by timestamp like training does
    df_agg = df_raw.groupby("datetime_beginning_ept")["mw"].sum().reset_index()
    print(f"\nAfter aggregation to PJM-wide:")
    print(f"  Rows: {len(df_agg)}")
    print(f"  Mean load: {df_agg['mw'].mean():,.0f} MW")
    print(f"  Min load: {df_agg['mw'].min():,.0f} MW")
    print(f"  Max load: {df_agg['mw'].max():,.0f} MW")
else:
    print(f"2019 CSV not found")

print(f"\n{'='*80}\n")
