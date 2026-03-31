"""Retraining pipeline for self-healing candidate model generation.

Creates a recent supervised dataset from streaming CSV data, trains a timestamped
candidate model, compares it against the current production model, and writes a
candidate comparison report for trigger/promotion decisions.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

from src.common.logging import configure_logging, get_logger
from src.data.feature_builder import FEATURE_COLUMNS, FeatureSpec, build_supervised_pandas
from src.ml.model_io import load_model, predict


TARGET_COLUMN = "load_mw"

CANONICAL_COLUMN_MAP = {
    "Datetime Beginning UTC": "datetime_beginning_utc",
    "Datetime Beginning EPT": "datetime_beginning_ept",
    "NERC Region": "nerc_region",
    "Market Region": "mkt_region",
    "Transmission Zone": "zone",
    "Load Area": "load_area",
    "MW": "mw",
    "Company Verified": "is_verified",
}


@dataclass(frozen=True)
class CandidateArtifacts:
    candidate_model_path: str
    candidate_metrics_path: str
    candidate_report_path: str
    supervised_window_path: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [column.strip() for column in normalized.columns]

    rename_map: dict[str, str] = {}
    for column in normalized.columns:
        if column in CANONICAL_COLUMN_MAP:
            rename_map[column] = CANONICAL_COLUMN_MAP[column]
        else:
            rename_map[column] = column.strip().lower().replace(" ", "_")

    return normalized.rename(columns=rename_map)


def _parse_datetime_column(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except TypeError:
        # Fallback for older pandas versions without format="mixed" support.
        return pd.to_datetime(series, errors="coerce")


def _prepare_supervised_from_stream_csv(stream_csv_path: Path) -> pd.DataFrame:
    # Converts stream CSV into supervised feature matrix for retraining.
    df = pd.read_csv(stream_csv_path)
    df = _normalize_columns(df)

    datetime_col = "datetime_beginning_ept" if "datetime_beginning_ept" in df.columns else "datetime_beginning_utc"
    if datetime_col not in df.columns:
        raise KeyError("Expected datetime_beginning_ept or datetime_beginning_utc in stream dataset")
    if "mw" not in df.columns:
        raise KeyError("Expected MW/mw column in stream dataset")

    df[datetime_col] = _parse_datetime_column(df[datetime_col])
    df = df.dropna(subset=[datetime_col, "mw"]).copy()

    aggregated = (
        df.rename(columns={datetime_col: "datetime", "mw": "load_mw"})
        .groupby("datetime", as_index=False)["load_mw"]
        .sum()
        .sort_values("datetime")
        .reset_index(drop=True)
    )

    supervised = build_supervised_pandas(
        df=aggregated,
        spec=FeatureSpec(timestamp_col="datetime", target_col="load_mw", group_cols=()),
        drop_na_features=True,
    )
    return supervised


def _chronological_split(df: pd.DataFrame, train_ratio: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = df.sort_values("datetime").reset_index(drop=True)
    split_idx = int(len(ordered) * train_ratio)
    if split_idx <= 0 or split_idx >= len(ordered):
        raise ValueError("Dataset too small for chronological split")
    return ordered.iloc[:split_idx], ordered.iloc[split_idx:]


def _metrics(y_true: pd.Series, y_pred: pd.Series | Any) -> dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(mean_squared_error(y_true, y_pred) ** 0.5)
    r2 = float(r2_score(y_true, y_pred))
    return {"mae": mae, "rmse": rmse, "r2": r2}


def run_retrain_pipeline(
    stream_csv_path: str | None = None,
    recent_days: int = 30,
    current_model_path: str | None = None,
    min_relative_improvement: float = 0.02,
) -> dict[str, Any]:
    # ----------------------------------------------------
    # --------------- Candidate Retrain Flow -------------
    # Trains candidate model and compares it against active model.
    # ----------------------------------------------------
    logger = get_logger(__name__)
    root = _project_root()

    resolved_stream_csv = (
        Path(stream_csv_path)
        if stream_csv_path
        else root / "data" / "stream_dataset" / "hrl_load_metered-2020.csv"
    )
    if not resolved_stream_csv.exists():
        raise FileNotFoundError(f"Stream dataset not found: {resolved_stream_csv}")

    models_dir = root / "artifacts" / "models"
    candidates_dir = models_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate_version = f"candidate_{ts}"

    candidate_model_path = candidates_dir / f"model_{candidate_version}.joblib"
    candidate_metrics_path = candidates_dir / f"metrics_{candidate_version}.json"
    candidate_report_path = models_dir / "candidate_report.json"
    supervised_window_path = candidates_dir / f"supervised_window_{candidate_version}.parquet"

    logger.info(
        "retrain-pipeline-started",
        extra={"stream_csv_path": str(resolved_stream_csv), "recent_days": recent_days},
    )

    supervised = _prepare_supervised_from_stream_csv(resolved_stream_csv)
    supervised["datetime"] = pd.to_datetime(supervised["datetime"], errors="coerce")
    supervised = supervised.dropna(subset=["datetime", TARGET_COLUMN] + FEATURE_COLUMNS)

    latest_time = supervised["datetime"].max()
    if pd.isna(latest_time):
        raise ValueError("Supervised dataset has no valid datetime values")

    cutoff = latest_time - timedelta(days=max(1, recent_days))
    recent_supervised = supervised[supervised["datetime"] >= cutoff].copy().reset_index(drop=True)
    if len(recent_supervised) < 300:
        raise ValueError(
            f"Recent supervised window too small ({len(recent_supervised)} rows). "
            "Increase recent_days or provide longer stream data."
        )

    recent_supervised.to_parquet(supervised_window_path, index=False)

    train_df, val_df = _chronological_split(recent_supervised, train_ratio=0.8)
    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]
    x_val = val_df[FEATURE_COLUMNS]
    y_val = val_df[TARGET_COLUMN]

    candidate_model = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=500,
        learning_rate=0.05,
        max_depth=8,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    candidate_model.fit(x_train, y_train)

    try:
        setattr(candidate_model, "model_version", candidate_version)
    except Exception:
        pass

    candidate_bundle = {"model": candidate_model, "features": FEATURE_COLUMNS}
    joblib.dump(candidate_bundle, candidate_model_path)

    current_bundle = load_model(current_model_path)
    current_pred = predict(current_bundle, x_val)
    candidate_pred = candidate_model.predict(x_val)

    current_metrics = _metrics(y_val, current_pred)
    candidate_metrics = _metrics(y_val, candidate_pred)

    relative_improvement_mae = (
        (current_metrics["mae"] - candidate_metrics["mae"]) / current_metrics["mae"]
        if current_metrics["mae"] > 0
        else 0.0
    )

    promotion_recommended = (
        relative_improvement_mae >= min_relative_improvement
        and candidate_metrics["rmse"] <= current_metrics["rmse"]
    )

    metrics_payload = {
        "model_version": candidate_version,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_rows": int(len(train_df)),
        "validation_rows": int(len(val_df)),
        "feature_columns": FEATURE_COLUMNS,
        "candidate_metrics": candidate_metrics,
    }
    candidate_metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    report_payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_version": candidate_version,
        "current_model_path": str(Path(current_model_path)) if current_model_path else "latest_from_artifacts_models",
        "candidate_model_path": str(candidate_model_path),
        "recent_data": {
            "stream_csv_path": str(resolved_stream_csv),
            "recent_days": int(recent_days),
            "window_start_utc": recent_supervised["datetime"].min().isoformat(),
            "window_end_utc": recent_supervised["datetime"].max().isoformat(),
            "rows": int(len(recent_supervised)),
        },
        "split": {"train_rows": int(len(train_df)), "validation_rows": int(len(val_df))},
        "current_metrics": current_metrics,
        "candidate_metrics": candidate_metrics,
        "relative_improvement_mae": float(relative_improvement_mae),
        "min_relative_improvement": float(min_relative_improvement),
        "promotion_recommended": bool(promotion_recommended),
        "ready_for_promotion": bool(promotion_recommended),
        "candidate_better": bool(candidate_metrics["mae"] < current_metrics["mae"]),
        "artifacts": asdict(
            CandidateArtifacts(
                candidate_model_path=str(candidate_model_path),
                candidate_metrics_path=str(candidate_metrics_path),
                candidate_report_path=str(candidate_report_path),
                supervised_window_path=str(supervised_window_path),
            )
        ),
    }

    candidate_report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    logger.info(
        "retrain-pipeline-complete",
        extra={
            "candidate_version": candidate_version,
            "promotion_recommended": bool(promotion_recommended),
            "candidate_report_path": str(candidate_report_path),
        },
    )

    return report_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run self-healing retraining pipeline")
    parser.add_argument(
        "--stream-csv-path",
        default=None,
        help="Path to stream CSV used for recent retraining window",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=30,
        help="Number of recent days to include for candidate retraining",
    )
    parser.add_argument(
        "--current-model-path",
        default=None,
        help="Explicit current model path (default: latest model in artifacts/models)",
    )
    parser.add_argument(
        "--min-relative-improvement",
        type=float,
        default=0.02,
        help="Minimum relative MAE improvement required to recommend promotion",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser


def main() -> None:
    # CLI entrypoint for candidate retraining workflow.
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=False)

    report = run_retrain_pipeline(
        stream_csv_path=args.stream_csv_path,
        recent_days=args.recent_days,
        current_model_path=args.current_model_path,
        min_relative_improvement=args.min_relative_improvement,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
