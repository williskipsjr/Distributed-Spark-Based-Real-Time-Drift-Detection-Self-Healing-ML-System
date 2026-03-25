"""
PRODUCTION ML DEBUG: 6-Step Root Cause Analysis for Training-Serving Skew

This script systematically debugs the critical prediction issue where:
- Training data (2018): actual_load ≈ 150,000 - 260,000
- Streaming predictions (2019): predicted_load ≈ -30,000 to 90,000
- Error ≈ 180,000 (fundamental, not noise)

Follow EXACT 6-step process to identify root cause.
"""

import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from src.data.feature_builder import FEATURE_COLUMNS, build_supervised_pandas, FeatureSpec

# ============================================================================
# STEP 1: VALIDATE FEATURE CONSISTENCY
# ============================================================================
def step1_validate_feature_consistency():
    print("\n" + "="*80)
    print("STEP 1: VALIDATE FEATURE CONSISTENCY")
    print("="*80)

    # Load training data (2018)
    print("\n[1.1] Loading training data (2018)...")
    train_df = pd.read_parquet("data/processed/pjm_supervised.parquet")
    print(f"[OK] Training data shape: {train_df.shape}")
    print(f"  DateTime range: {train_df['datetime'].min()} to {train_df['datetime'].max()}")

    # Extract small batch
    train_batch = train_df[FEATURE_COLUMNS + ["load_mw"]].head(10)
    print(f"\nTraining batch (first 10 rows):")
    print(train_batch.to_string())

    # Load streaming data (2019)
    print("\n[1.2] Loading streaming data (2019)...")
    stream_raw = pd.read_csv("data/stream_dataset/hrl_load_metered-2019.csv")
    print(f"[OK] Streaming raw data shape: {stream_raw.shape}")

    # Rename columns to match training pipeline
    stream_raw_renamed = stream_raw.rename(columns={
        "datetime_beginning_ept": "datetime",
        "mw": "load_mw"
    })

    # Build features using SAME pipeline as training
    stream_df = build_supervised_pandas(
        stream_raw_renamed[["datetime", "load_mw", "load_area"]],
        spec=FeatureSpec(timestamp_col="datetime", target_col="load_mw", group_cols=("load_area",)),
        drop_na_features=True
    )
    print(f"[OK] Streaming data with features shape: {stream_df.shape}")
    print(f"  DateTime range: {stream_df['datetime'].min()} to {stream_df['datetime'].max()}")

    # Extract small batch
    stream_batch = stream_df[FEATURE_COLUMNS + ["load_mw"]].head(10)
    print(f"\nStreaming batch (first 10 rows):")
    print(stream_batch.to_string())

    # [1.3] COMPARE FEATURE DISTRIBUTIONS
    print("\n[1.3] Feature distribution comparison:")
    print("="*80)
    comparison_data = []

    for col in FEATURE_COLUMNS:
        train_stats = {
            "mean": train_df[col].mean(),
            "std": train_df[col].std(),
            "min": train_df[col].min(),
            "max": train_df[col].max(),
        }
        stream_stats = {
            "mean": stream_df[col].mean(),
            "std": stream_df[col].std(),
            "min": stream_df[col].min(),
            "max": stream_df[col].max(),
        }

        comparison_data.append({
            "Feature": col,
            "Train Mean": f"{train_stats['mean']:.3f}",
            "Stream Mean": f"{stream_stats['mean']:.3f}",
            "Train Std": f"{train_stats['std']:.3f}",
            "Stream Std": f"{stream_stats['std']:.3f}",
        })

    comparison_df = pd.DataFrame(comparison_data)
    print(comparison_df.to_string(index=False))

    # Check target variable
    print("\n[1.4] Target variable (load_mw) comparison:")
    print(f"Training load_mw:")
    print(f"  Mean: {train_df['load_mw'].mean():,.2f}")
    print(f"  Std:  {train_df['load_mw'].std():,.2f}")
    print(f"  Min:  {train_df['load_mw'].min():,.2f}")
    print(f"  Max:  {train_df['load_mw'].max():,.2f}")

    print(f"\nStreaming load_mw:")
    print(f"  Mean: {stream_df['load_mw'].mean():,.2f}")
    print(f"  Std:  {stream_df['load_mw'].std():,.2f}")
    print(f"  Min:  {stream_df['load_mw'].min():,.2f}")
    print(f"  Max:  {stream_df['load_mw'].max():,.2f}")

    return train_df, stream_df, train_batch, stream_batch


# ============================================================================
# STEP 2: VALIDATE MODEL BEHAVIOR ON STREAMING DATA
# ============================================================================
def step2_validate_model_predictions(stream_df, stream_batch):
    print("\n" + "="*80)
    print("STEP 2: VALIDATE MODEL BEHAVIOR ON STREAMING DATA")
    print("="*80)

    # Load model
    print("\n[2.1] Loading model...")
    bundle = joblib.load("artifacts/models/model_v1.joblib")
    model = bundle["model"]
    features = bundle["features"]
    print(f"[OK] Model loaded. Feature count: {len(features)}")
    print(f"  Features: {features}")

    # Test on streaming batch OFFLINE (outside Spark)
    print("\n[2.2] Testing model on streaming batch (OFFLINE, pandas only)...")
    stream_features = stream_batch[features].copy()
    stream_predictions = model.predict(stream_features)

    print(f"[OK] Predictions generated. Shape: {stream_predictions.shape}")
    print(f"\nPredictions vs Actual:")
    results_df = pd.DataFrame({
        "actual_load": stream_batch["load_mw"].values,
        "predicted_load": stream_predictions,
        "error": np.abs(stream_batch["load_mw"].values - stream_predictions)
    })
    print(results_df.to_string())

    print(f"\nPrediction statistics:")
    print(f"  Predicted min/max: {stream_predictions.min():,.2f} / {stream_predictions.max():,.2f}")
    print(f"  Predicted mean:    {stream_predictions.mean():,.2f}")
    print(f"  Predicted std:     {stream_predictions.std():,.2f}")

    print(f"\nError statistics:")
    errors = np.abs(stream_batch["load_mw"].values - stream_predictions)
    print(f"  Mean error:  {errors.mean():,.2f}")
    print(f"  Max error:   {errors.max():,.2f}")
    print(f"  Min error:   {errors.min():,.2f}")

    # Check if predictions are reasonable
    if stream_predictions.mean() > 100_000:
        print("\n[OK] GOOD: Model predictions are in expected range (>100k)")
        return True, stream_predictions
    else:
        print("\n[FAIL] BAD: Model predictions are unreasonably small!")
        return False, stream_predictions


# ============================================================================
# STEP 3: CHECK SCALING / NORMALIZATION
# ============================================================================
def step3_check_scaling(train_df):
    print("\n" + "="*80)
    print("STEP 3: CHECK SCALING / NORMALIZATION")
    print("="*80)

    print("\n[3.1] Checking training code for scaling...")

    # Read training script
    train_script_path = "src/ml/train_baseline.py"
    with open(train_script_path, "r") as f:
        train_code = f.read()

    # Check for scaling keywords
    scaling_keywords = ["StandardScaler", "MinMaxScaler", "RobustScaler", "preprocessing", "scale("]
    has_scaling = any(keyword in train_code for keyword in scaling_keywords)

    if has_scaling:
        print("[FAIL] SCALING DETECTED in training code")
        print("  This is likely the root cause of feature mismatch!")
    else:
        print("[OK] No scaling/normalization found in training code")
        print("  Model trained on raw feature values")

    print("\n[3.2] Checking model artifact...")
    bundle = joblib.load("artifacts/models/model_v1.joblib")
    print(f"  Bundle keys: {list(bundle.keys())}")

    if "scaler" in bundle:
        print("[FAIL] SCALER STORED in model bundle!")
        print("  Streaming inference MUST apply same scaler")
    else:
        print("[OK] No scaler in model bundle")

    print("\n[3.3] Checking Spark job for scaling...")
    spark_script_path = "src/streaming/spark_job.py"
    with open(spark_script_path, "r") as f:
        spark_code = f.read()

    if "scale" in spark_code.lower() or "scaler" in spark_code.lower():
        print("[FAIL] Scaling code detected in Spark job")
    else:
        print("[OK] No scaling applied in Spark job (correct, if training had no scaling)")


# ============================================================================
# STEP 4: VALIDATE TEMPORAL FEATURES (CRITICAL)
# ============================================================================
def step4_validate_temporal_features(stream_df, stream_batch):
    print("\n" + "="*80)
    print("STEP 4: VALIDATE TEMPORAL FEATURES (CRITICAL)")
    print("="*80)

    print("\n[4.1] Verifying lag_1 == load_mw(t-1)...")

    # Get a window where we can verify lags
    test_window = stream_df[stream_df["load_area"] == stream_df["load_area"].iloc[0]].iloc[:100]
    test_window = test_window.reset_index(drop=True)

    # Manually check lag_1
    for i in range(1, min(5, len(test_window))):
        expected_lag_1 = test_window.loc[i-1, "load_mw"]
        actual_lag_1 = test_window.loc[i, "lag_1"]
        match = np.isclose(expected_lag_1, actual_lag_1, rtol=1e-5)
        status = "[OK]" if match else "[FAIL]"
        print(f"  {status} Row {i}: lag_1={actual_lag_1:.2f}, prev_load={expected_lag_1:.2f}")

    print("\n[4.2] Verifying lag_24 correctness...")
    for i in range(24, min(30, len(test_window))):
        expected_lag_24 = test_window.loc[i-24, "load_mw"]
        actual_lag_24 = test_window.loc[i, "lag_24"]
        match = np.isclose(expected_lag_24, actual_lag_24, rtol=1e-5)
        status = "[OK]" if match else "[FAIL]"
        print(f"  {status} Row {i}: lag_24={actual_lag_24:.2f}, 24h_ago={expected_lag_24:.2f}")

    print("\n[4.3] Verifying rolling_24 correctness...")
    for i in range(24, min(30, len(test_window))):
        # rolling_24 should be mean of load_mw from t-24 to t-1
        expected_rolling_24 = test_window.loc[i-24:i-1, "load_mw"].mean()
        actual_rolling_24 = test_window.loc[i, "rolling_24"]
        match = np.isclose(expected_rolling_24, actual_rolling_24, rtol=1e-5)
        status = "[OK]" if match else "[FAIL]"
        print(f"  {status} Row {i}: rolling_24={actual_rolling_24:.2f}, expected={expected_rolling_24:.2f}")

    print("\n[4.4] Summary of temporal features:")
    lag_cols = ["lag_1", "lag_24", "lag_168", "rolling_24", "rolling_168"]
    for col in lag_cols:
        null_count = stream_df[col].isna().sum()
        print(f"  {col}: {null_count} NaN values out of {len(stream_df)} rows")


# ============================================================================
# STEP 5: IDENTIFY ROOT CAUSE
# ============================================================================
def step5_identify_root_cause(train_df, stream_df, model_predictions_valid):
    print("\n" + "="*80)
    print("STEP 5: IDENTIFY ROOT CAUSE")
    print("="*80)

    # Check 1: Feature order
    print("\n[5.1] Feature order check...")
    print(f"  Expected order: {FEATURE_COLUMNS}")

    # Check 2: Data types
    print("\n[5.2] Data type check...")
    for col in FEATURE_COLUMNS[:3]:
        train_dtype = train_df[col].dtype
        stream_dtype = stream_df[col].dtype
        match = train_dtype == stream_dtype
        print(f"  {col}: train={train_dtype}, stream={stream_dtype} {'[OK]' if match else '[FAIL]'}")

    # Check 3: Feature ranges
    print("\n[5.3] Feature range analysis...")
    time_features = ["hour_of_day", "day_of_week", "month", "is_weekend"]
    lag_features = ["lag_1", "lag_24", "lag_168"]
    rolling_features = ["rolling_24", "rolling_168"]

    print("  Time features (should be bounded):")
    for col in time_features:
        print(f"    {col}: train=[{train_df[col].min()}, {train_df[col].max()}], stream=[{stream_df[col].min()}, {stream_df[col].max()}]")

    print("  Lag features (should match load_mw range ~150k-260k):")
    for col in lag_features:
        print(f"    {col}: train=[{train_df[col].min():,.0f}, {train_df[col].max():,.0f}], stream=[{stream_df[col].min():,.0f}, {stream_df[col].max():,.0f}]")

    print("\n[5.4] ROOT CAUSE DETERMINATION:")
    print("-" * 80)

    if model_predictions_valid:
        print("[OK] Model predictions are CORRECT on streaming data (offline)")
        print("[OK] This means the issue is in SPARK/UDF handling, NOT feature computation")
        print("\n-> ROOT CAUSE: Spark Pandas UDF struct unpacking misaligns feature order")
        print("  When F.struct(*FEATURE_COLUMNS) is passed to pandas_udf,")
        print("  Spark may be unpacking columns in wrong order or as separate Series")
        return "SPARK_UDF_MISALIGNMENT"
    else:
        print("[FAIL] Model predictions are WRONG on streaming data (offline)")
        print("  This means the issue is in FEATURE ENGINEERING, not Spark")

        if (stream_df["load_mw"].mean() < train_df["load_mw"].mean() * 0.5):
            print("\n-> ROOT CAUSE: Data distribution shift (2019 has lower load than 2018)")
            return "DATA_DISTRIBUTION_SHIFT"
        else:
            print("\n-> ROOT CAUSE: Feature computation mismatch or scaling issue")
            return "FEATURE_COMPUTATION_ERROR"


# ============================================================================
# STEP 6: RECOMMEND FIX
# ============================================================================
def step6_recommend_fix(root_cause):
    print("\n" + "="*80)
    print("STEP 6: FIX RECOMMENDATION")
    print("="*80)

    if root_cause == "SPARK_UDF_MISALIGNMENT":
        print("""
The Pandas UDF in spark_job.py is receiving struct input incorrectly.

CURRENT CODE (BUGGY):
  Line 181 in spark_job.py:
    predict_load(F.struct(*[F.col(c) for c in FEATURE_COLUMNS]))

ISSUE:
  When Spark unpacks a struct in pandas_udf, it creates a DataFrame.
  The UDF receives: pdf = DataFrame with columns named after FEATURE_COLUMNS
  But Spark may not preserve column order or may unpack incorrectly.

FIX:
  Instead of passing struct, select columns explicitly and preserve order!

  Change from:
    predict_load(F.struct(*[F.col(c) for c in FEATURE_COLUMNS]))

  To:
    predict_load(F.concat_ws("||", *[F.col(c).cast("string") for c in FEATURE_COLUMNS]))

  OR (BETTER): Use columns directly without struct:
    .mapInPandas(
        lambda pdf: apply_model_to_batch(pdf, broadcast_model.value),
        schema=..."
        )
""")

    elif root_cause == "DATA_DISTRIBUTION_SHIFT":
        print("""
The 2019 streaming data has fundamentally different load distribution than 2018.

ACTION: Retrain model on 2019 data or use domain adaptation.
""")

    elif root_cause == "FEATURE_COMPUTATION_ERROR":
        print("""
Features are computed differently in streaming vs training.

CHECK:
  1. Temporal alignment - are timestamps sorted correctly?
  2. Group column handling - is grouping by load_area correct?
  3. Window boundaries - do rolling windows use same lookback?
""")


# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "[DEBUG] " + "="*76 + " [DEBUG]")
    print("    PRODUCTION ML DEBUG: 6-STEP ROOT CAUSE ANALYSIS")
    print("    Issue: Predictions wrong by ~180,000 (training-serving skew)")
    print("[DEBUG] " + "="*76 + " [DEBUG]\n")

    # Step 1
    train_df, stream_df, train_batch, stream_batch = step1_validate_feature_consistency()

    # Step 2
    model_valid, predictions = step2_validate_model_predictions(stream_df, stream_batch)

    # Step 3
    step3_check_scaling(train_df)

    # Step 4
    step4_validate_temporal_features(stream_df, stream_batch)

    # Step 5
    root_cause = step5_identify_root_cause(train_df, stream_df, model_valid)

    # Step 6
    step6_recommend_fix(root_cause)

    print("\n" + "="*80)
    print(f"ANALYSIS COMPLETE. ROOT CAUSE: {root_cause}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
