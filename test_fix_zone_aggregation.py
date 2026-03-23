#!/usr/bin/env python
"""
Validation script for Fix #1: Zone aggregation in Kafka producer.

Tests that the Kafka producer correctly aggregates zone-level data
to PJM-wide aggregate before sending to Kafka.
"""

import sys
from pathlib import Path

import pandas as pd

# Add project to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.feature_builder import FEATURE_COLUMNS, build_supervised_pandas, FeatureSpec
from src.streaming.kafka_producer import _load_and_prepare_data, _resolve_dataset_path


def test_zone_aggregation():
    """Test that zone-level CSV data is properly aggregated."""
    print("\n" + "="*80)
    print("TEST 1: Zone-Level CSV Aggregation")
    print("="*80)

    # Load zone-level data
    zone_csv = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
    print(f"\nLoading zone-level data from: {zone_csv}")
    df_raw = pd.read_csv(zone_csv)
    print(f"  Raw data shape: {df_raw.shape}")
    print(f"  Unique timestamps: {df_raw['datetime_beginning_ept'].nunique()}")
    print(f"  Unique load_areas (zones): {df_raw['load_area'].nunique()}")

    # Load through producer pipeline
    print("\nProcessing through producer aggregation pipeline...")
    df_processed = _load_and_prepare_data(zone_csv)
    print(f"  Processed data shape: {df_processed.shape}")

    # Validate aggregation
    print("\nValidation:")
    print(f"  Mean load_mw: {df_processed['load_mw'].mean():,.2f} (expected ~6k for 2019)")
    print(f"  Min load_mw: {df_processed['load_mw'].min():,.2f}")
    print(f"  Max load_mw: {df_processed['load_mw'].max():,.2f}")
    print(f"  Mean lag_1: {df_processed['lag_1'].mean():,.2f} (should match load_mw mean)")
    print(f"  Features present: {all(col in df_processed.columns for col in FEATURE_COLUMNS)}")

    # Check data quality
    print(f"\nData quality:")
    print(f"  No NaN in datetime: {df_processed['datetime'].isna().sum() == 0}")
    print(f"  No NaN in load_mw: {df_processed['load_mw'].isna().sum() == 0}")
    print(f"  No NaN in lag_1: {df_processed['lag_1'].isna().sum() == 0}")

    if df_processed['load_mw'].mean() > 5000:
        print("\n[OK] Zone aggregation successful! Data aggregated to expected range.")
        return True
    else:
        print("\n[FAIL] Data still appears zone-level (mean < 5k).")
        return False


def test_parquet_load():
    """Test that parquet (already-aggregate) data loads correctly."""
    print("\n" + "="*80)
    print("TEST 2: Parquet (Aggregate) Data Load")
    print("="*80)

    parquet_file = project_root / "data" / "processed" / "pjm_supervised.parquet"
    print(f"\nLoading aggregate parquet from: {parquet_file}")

    if not parquet_file.exists():
        print("  [SKIP] Parquet file not found.")
        return None

    df_processed = _load_and_prepare_data(parquet_file)
    print(f"  Data shape: {df_processed.shape}")
    print(f"  Mean load_mw: {df_processed['load_mw'].mean():,.2f} (expected ~183k for 2018)")

    if df_processed['load_mw'].mean() > 150000:
        print("\n[OK] Parquet loading successful! Data in training range.")
        return True
    else:
        print("\n[FAIL] Parquet data out of expected range.")
        return False


def test_feature_alignment():
    """Test that features computed match training distribution."""
    print("\n" + "="*80)
    print("TEST 3: Feature Alignment Verification")
    print("="*80)

    zone_csv = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
    print(f"\nLoading and processing 2019 zone data...")

    df_processed = _load_and_prepare_data(zone_csv)
    print(f"  lag_1 mean: {df_processed['lag_1'].mean():,.2f}")
    print(f"  lag_24 mean: {df_processed['lag_24'].mean():,.2f}")
    print(f"  rolling_24 mean: {df_processed['rolling_24'].mean():,.2f}")

    # Compare with training expectations
    train_parquet = project_root / "data" / "processed" / "pjm_supervised.parquet"
    if train_parquet.exists():
        df_train = pd.read_parquet(train_parquet)
        print(f"\nComparison with training data:")
        print(f"  Training lag_1 mean: {df_train['lag_1'].mean():,.2f}")
        print(f"  Streaming lag_1 mean: {df_processed['lag_1'].mean():,.2f}")
        print(f"  Ratio: {df_processed['lag_1'].mean() / df_train['lag_1'].mean():.3f}x")

        if df_processed['lag_1'].mean() < df_train['lag_1'].mean() * 0.1:
            print("\n[FAIL] Features still out-of-distribution (30x off).")
            return False
        else:
            print("\n[OK] Features are in expected range!")
            return True
    else:
        print("\n[SKIP] Training data not available for comparison.")
        return None


def main():
    print("\n" + "[TEST] " + "="*72 + " [TEST]")
    print("  FIX #1 VALIDATION: Zone Aggregation in Kafka Producer")
    print("[TEST] " + "="*72 + " [TEST]\n")

    results = []

    # Test 1: Zone aggregation
    try:
        result = test_zone_aggregation()
        results.append(("Zone Aggregation", result))
    except Exception as e:
        print(f"\n[ERROR] {e}")
        results.append(("Zone Aggregation", False))

    # Test 2: Parquet load
    try:
        result = test_parquet_load()
        results.append(("Parquet Load", result))
    except Exception as e:
        print(f"\n[ERROR] {e}")
        results.append(("Parquet Load", False))

    # Test 3: Feature alignment
    try:
        result = test_feature_alignment()
        results.append(("Feature Alignment", result))
    except Exception as e:
        print(f"\n[ERROR] {e}")
        results.append(("Feature Alignment", False))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    for test_name, result in results:
        if result is None:
            status = "SKIP"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
        print(f"  {test_name:.<40} {status:>10}")

    passed = sum(1 for _, r in results if r is True)
    total = sum(1 for _, r in results if r is not None)

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n[OK] Fix #1 is working correctly!")
        return 0
    else:
        print("\n[FAIL] Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
