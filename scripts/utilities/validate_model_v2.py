"""Offline sanity check for model_v2 before deployment."""

import pandas as pd
import joblib
import numpy as np
from pathlib import Path

# Load v2 model
model_bundle = joblib.load("artifacts/models/model_v2.joblib")
model = model_bundle["model"]
features = model_bundle["features"]

print(f"\n{'='*80}")
print("MODEL V2 SANITY CHECK")
print(f"{'='*80}\n")

# Load validation data
df_val = pd.read_parquet("data/processed/pjm_supervised.parquet")
df_val = df_val.sort_values("datetime").reset_index(drop=True)
split_idx = int(len(df_val) * 0.8)
val_df = df_val.iloc[split_idx:]

X_val = val_df[features]
y_val = val_df["load_mw"]

# Predict
preds = model.predict(X_val)

print(f"ACTUAL LOAD DISTRIBUTION:")
print(f"  Mean: {y_val.mean():,.0f} MW")
print(f"  Min:  {y_val.min():,.0f} MW")
print(f"  Max:  {y_val.max():,.0f} MW")
print(f"  Std:  {y_val.std():,.0f} MW")

print(f"\nPREDICTED LOAD DISTRIBUTION:")
print(f"  Mean: {preds.mean():,.0f} MW")
print(f"  Min:  {preds.min():,.0f} MW")
print(f"  Max:  {preds.max():,.0f} MW")
print(f"  Std:  {preds.std():,.0f} MW")

print(f"\nPREDICTION QUALITY:")
errors = np.abs(y_val.values - preds)
print(f"  MAE: {errors.mean():,.0f} MW")
print(f"  Median AE: {np.median(errors):,.0f} MW")
print(f"  95th pct AE: {np.percentile(errors, 95):,.0f} MW")
print(f"  % Negative Preds: {(preds < 0).sum() / len(preds) * 100:.2f}%")
print(f"  % Preds < 50k: {(preds < 50000).sum() / len(preds) * 100:.2f}%")

print(f"\nSAMPLE PREDICTIONS (first 10 rows):")
comparison = pd.DataFrame({
    "actual": y_val.iloc[:10].values,
    "predicted": preds[:10],
    "error": errors[:10]
})
comparison.columns = ["actual_mw", "predicted_mw", "error_mw"]
print(comparison.to_string(index=False))

print(f"\n{'='*80}")
print("VERDICT:")
any_negative = (preds < 0).any()
scale_ok = preds.mean() > 100000 and preds.mean() < 250000
mae_ok = errors.mean() < 10000

print(f"  ✓ No negative predictions: {not any_negative}")
print(f"  ✓ Realistic scale (100k-250k): {scale_ok}")
print(f"  ✓ MAE < 10k: {mae_ok}")

if not any_negative and scale_ok and mae_ok:
    print(f"\n✓✓✓ MODEL V2 PASSED ALL SANITY CHECKS ✓✓✓")
    exit(0)
else:
    print(f"\n✗✗✗ MODEL V2 FAILED CHECKS - DO NOT DEPLOY ✗✗✗")
    exit(1)
print(f"{'='*80}\n")
