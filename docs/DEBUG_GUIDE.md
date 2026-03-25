# DEBUG GUIDE

Last updated: 2026-03-25

## 1) Validate model artifact and feature contract

```python
import joblib

bundle = joblib.load("artifacts/models/model_v2.joblib")
print(bundle.keys())
print("FEATURE ORDER:", bundle["features"])
```

Expected:
- keys contain `model` and `features`
- feature list has 9 fields in canonical order

## 2) Validate producer data scale before streaming

```bash
python scripts/utilities/check_producer_data.py
```

Expected:
- mean `load_mw` around PJM aggregate scale (roughly six figures)
- not zone-level small values

## 3) Run producer with deterministic source

```bash
python -m src.streaming.kafka_producer --dataset data/processed/pjm_supervised.parquet --sleep-seconds 0.1 --log-level INFO
```

## 4) Run streaming job in debug mode

```bash
python -m src.streaming.spark_job --debug-mode
```

Watch for these debug prints from UDF:
- `MODEL FEATURES: ...`
- `DF COLUMNS: ...`
- `DF VALUES: ...`
- `UDF PRED SAMPLE: ...`

If `DF COLUMNS` does not exactly match `MODEL FEATURES`, stop and fix before trusting predictions.

## 5) Inference misalignment checklist

When predictions are unrealistic (for example negative with positive demand):

1. Confirm `bundle["features"]` order.
2. Confirm UDF uses explicit `features_df = features_df[model_features]`.
3. Confirm there is no `list(row_dict.values())` inference path.
4. Confirm there is no key sorting before DataFrame construction.
5. Confirm no NaN values before `model.predict`.

## 6) Quick offline parity check (single row)

```python
import joblib
import pandas as pd
from random import shuffle

bundle = joblib.load("artifacts/models/model_v2.joblib")
model = bundle["model"]
features = list(bundle["features"])

df = pd.read_parquet("data/processed/pjm_supervised.parquet").dropna(subset=features)
row = df.iloc[0]

keys = features.copy()
shuffle(keys)
row_dict = {k: float(row[k]) for k in keys}

x = pd.DataFrame([row_dict])
x = x[features].astype("float64")

pred = float(model.predict(x)[0])
actual = float(row["load_mw"])
print("PRED", pred)
print("ACTUAL", actual)
```

## 7) Drift detector prerequisites

Drift detector needs enough recent and baseline hourly windows.

```bash
python -m src.drift_detection.drift_detector
```

Common expected failures during short runs:
- no parquet files in `data/metrics/hourly_metrics`
- empty baseline or recent window

