from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from src.common import get_config
from src.common.logging import configure_logging, get_logger
from src.data.feature_builder import FEATURE_COLUMNS


TARGET_COLUMN = "load_mw"


@dataclass(frozen=True)
class BaselineArtifacts:
    model_path: str
    metrics_path: str
    baseline_features_path: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_paths(
    input_path: str | None,
    model_path: str | None,
    metrics_path: str | None,
    baseline_features_path: str | None,
) -> tuple[Path, Path, Path, Path]:
    root = _project_root()

    input_dataset = Path(input_path) if input_path else root / "data" / "processed" / "pjm_supervised.parquet"
    resolved_model = Path(model_path) if model_path else root / "artifacts" / "models" / "model_v1.joblib"
    resolved_metrics = Path(metrics_path) if metrics_path else root / "artifacts" / "baselines" / "baseline_metrics.json"
    resolved_baseline_features = (
        Path(baseline_features_path)
        if baseline_features_path
        else root / "artifacts" / "baselines" / "baseline_features.parquet"
    )
    return input_dataset, resolved_model, resolved_metrics, resolved_baseline_features


def _validate_columns(df: pd.DataFrame) -> None:
    required = set(FEATURE_COLUMNS + [TARGET_COLUMN, "datetime"])
    missing = [col for col in sorted(required) if col not in df.columns]
    if missing:
        raise KeyError(f"Dataset is missing required columns: {', '.join(missing)}")


def _chronological_split(df: pd.DataFrame, train_ratio: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0 and 1")

    ordered = df.sort_values("datetime").reset_index(drop=True)
    split_idx = int(len(ordered) * train_ratio)
    if split_idx <= 0 or split_idx >= len(ordered):
        raise ValueError("Dataset too small for chronological split")
    return ordered.iloc[:split_idx], ordered.iloc[split_idx:]


def train_baseline(
    input_path: str | None = None,
    model_path: str | None = None,
    metrics_path: str | None = None,
    baseline_features_path: str | None = None,
) -> dict[str, float | int | str]:
    logger = get_logger(__name__)
    dataset_path, resolved_model, resolved_metrics, resolved_feature_output = _resolve_paths(
        input_path=input_path,
        model_path=model_path,
        metrics_path=metrics_path,
        baseline_features_path=baseline_features_path,
    )

    if not dataset_path.exists():
        raise FileNotFoundError(f"Supervised dataset not found: {dataset_path}")

    df = pd.read_parquet(dataset_path)
    _validate_columns(df)

    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", TARGET_COLUMN] + FEATURE_COLUMNS)

    train_df, val_df = _chronological_split(df=df, train_ratio=0.8)

    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]
    x_val = val_df[FEATURE_COLUMNS]
    y_val = val_df[TARGET_COLUMN]

    logger.info(
        "baseline-training-start",
        extra={
            "dataset_path": str(dataset_path),
            "train_rows": int(len(train_df)),
            "validation_rows": int(len(val_df)),
            "feature_count": int(len(FEATURE_COLUMNS)),
        },
    )

    model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=500,
        learning_rate=0.05,
        max_depth=8,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_val)
    mae = float(mean_absolute_error(y_val, predictions))
    rmse = float(mean_squared_error(y_val, predictions) ** 0.5)
    r2 = float(r2_score(y_val, predictions))

    resolved_model.parent.mkdir(parents=True, exist_ok=True)
    resolved_metrics.parent.mkdir(parents=True, exist_ok=True)
    resolved_feature_output.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, resolved_model)

    baseline_features = train_df[["datetime"] + FEATURE_COLUMNS + [TARGET_COLUMN]].copy()
    baseline_features.to_parquet(resolved_feature_output, index=False)

    metrics_payload: dict[str, float | int | str | list[str] | dict[str, str]] = {
        "model_version": "v1",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_column": TARGET_COLUMN,
        "feature_columns": FEATURE_COLUMNS,
        "split": {"train_ratio": "0.8", "validation_ratio": "0.2"},
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(val_df)),
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "artifacts": asdict(
            BaselineArtifacts(
                model_path=str(resolved_model),
                metrics_path=str(resolved_metrics),
                baseline_features_path=str(resolved_feature_output),
            )
        ),
    }

    with resolved_metrics.open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics_payload, metrics_file, indent=2)

    logger.info(
        "baseline-training-complete",
        extra={
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "model_path": str(resolved_model),
            "metrics_path": str(resolved_metrics),
            "baseline_features_path": str(resolved_feature_output),
        },
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(val_df)),
        "model_path": str(resolved_model),
        "metrics_path": str(resolved_metrics),
        "baseline_features_path": str(resolved_feature_output),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train baseline XGBoost model for PJM load forecasting")
    parser.add_argument("--input", dest="input_path", default=None, help="Path to supervised parquet dataset")
    parser.add_argument("--model-out", dest="model_path", default=None, help="Output path for model artifact")
    parser.add_argument("--metrics-out", dest="metrics_path", default=None, help="Output path for metrics JSON")
    parser.add_argument(
        "--baseline-features-out",
        dest="baseline_features_path",
        default=None,
        help="Output path for baseline features parquet",
    )
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=True)

    train_baseline(
        input_path=args.input_path,
        model_path=args.model_path,
        metrics_path=args.metrics_path,
        baseline_features_path=args.baseline_features_path,
    )


if __name__ == "__main__":
    main()
