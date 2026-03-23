import joblib
import pandas as pd
import numpy as np


def main():
    # 1) Load trained model bundle
    bundle = joblib.load("artifacts/models/model_v1.joblib")
    model = bundle["model"]
    features = bundle["features"]

    print("Loaded model bundle")
    print(f"Feature count: {len(features)}")
    print(f"First 10 features: {features[:10]}")

    # 2) Load supervised dataset
    df = pd.read_parquet("data/processed/pjm_supervised.parquet")
    print(f"\nLoaded dataset shape: {df.shape}")

    # 3) Extract small sample
    sample = df[features].head(5)

    # 4) Simulate CURRENT (buggy) Pandas UDF behavior
    # Simulate Spark passing columns separately
    cols = [sample[col] for col in features]

    # Concatenate like current UDF
    wrong_df = pd.concat(cols, axis=1)
    wrong_df.columns = features

    print("\n=== WRONG UDF INPUT ===")
    print(wrong_df.head())

    wrong_preds = model.predict(wrong_df)
    print("\n=== WRONG PREDICTIONS ===")
    print(wrong_preds)

    # 5) Simulate CORRECT behavior (row-wise integrity)
    correct_df = sample.copy()

    print("\n=== CORRECT INPUT ===")
    print(correct_df.head())

    correct_preds = model.predict(correct_df)
    print("\n=== CORRECT PREDICTIONS ===")
    print(correct_preds)

    # 6) Compare
    print("\n=== COMPARISON ===")
    diff = correct_preds - wrong_preds
    abs_diff = np.abs(diff)

    print("Per-row diff (correct - wrong):")
    print(diff)

    print("\nSummary:")
    print(f"Wrong min/max:   {wrong_preds.min():,.3f} / {wrong_preds.max():,.3f}")
    print(f"Correct min/max: {correct_preds.min():,.3f} / {correct_preds.max():,.3f}")
    print(f"Mean abs diff:   {abs_diff.mean():,.3f}")
    print(f"Max abs diff:    {abs_diff.max():,.3f}")

    wrong_unrealistic = np.any(wrong_preds < 0) or (wrong_preds.max() < 10_000)
    correct_expected = correct_preds.mean() > 100_000

    print("\nHeuristic checks:")
    print(f"Wrong looks unrealistic (negative or very small): {wrong_unrealistic}")
    print(f"Correct looks in expected scale (~200k):         {correct_expected}")

    if np.allclose(wrong_preds, correct_preds, rtol=1e-9, atol=1e-9):
        print("\nResult: No mismatch found in this local simulation.")
    else:
        print("\nResult: Mismatch detected. This supports Pandas UDF input-handling/alignment as root cause.")
        print("Recommended Spark fix: use struct-based UDF input:")
        print("predict_load(F.struct(*[F.col(f) for f in FEATURE_COLUMNS]))")


if __name__ == "__main__":
    main()