"""Drift Detection Module.

Loads hourly aggregated prediction metrics written by the Spark streaming job,
splits them into a 7-day baseline window and a 24-hour recent window, computes
drift statistics, and saves a JSON report under artifacts/drift/.

Usage:
    python -m src.drift_detection.drift_detector
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.logging import configure_logging, get_logger


logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_hourly_metrics(metrics_path: Path) -> pd.DataFrame:
    parquet_files = sorted(metrics_path.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No hourly metrics parquet files found in: {metrics_path}")

    frames = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(frames, ignore_index=True)
    df["timestamp_hour"] = pd.to_datetime(df["timestamp_hour"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_hour"])
    df = df.sort_values("timestamp_hour").reset_index(drop=True)
    return df


def _split_windows(
    df: pd.DataFrame,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reference = now or datetime.now(tz=timezone.utc)
    recent_cutoff = reference - timedelta(hours=24)
    baseline_start = reference - timedelta(days=7)

    recent_df = df[df["timestamp_hour"] >= recent_cutoff].copy()
    baseline_df = df[
        (df["timestamp_hour"] >= baseline_start) & (df["timestamp_hour"] < recent_cutoff)
    ].copy()

    return baseline_df, recent_df


def _compute_drift_report(
    baseline_df: pd.DataFrame,
    recent_df: pd.DataFrame,
    reference_time: datetime,
) -> dict[str, Any]:
    if baseline_df.empty:
        raise ValueError(
            "Baseline window (previous 7 days) contains no data — drift detection cannot run"
        )
    if recent_df.empty:
        raise ValueError(
            "Recent window (last 24 hours) contains no data — drift detection cannot run"
        )

    baseline_mean_error = float(baseline_df["mean_error"].mean())
    recent_mean_error = float(recent_df["mean_error"].mean())

    baseline_mean_prediction = float(baseline_df["mean_prediction"].mean())
    recent_mean_prediction = float(recent_df["mean_prediction"].mean())

    baseline_std_prediction = float(baseline_df["std_prediction"].mean())
    # When each hourly window has a single record, std_prediction can be NaN.
    # Fall back to variability of mean_prediction across baseline windows.
    if pd.isna(baseline_std_prediction) or baseline_std_prediction <= 0:
        fallback_std = float(baseline_df["mean_prediction"].std(ddof=0))
        baseline_std_prediction = fallback_std if not pd.isna(fallback_std) else 0.0

    performance_drift = recent_mean_error > baseline_mean_error * 1.5
    prediction_drift = (
        abs(recent_mean_prediction - baseline_mean_prediction) > baseline_std_prediction * 2
    )

    drift_detected = performance_drift or prediction_drift

    if performance_drift:
        drift_type = "performance_drift"
    elif prediction_drift:
        drift_type = "prediction_drift"
    else:
        drift_type = "none"

    baseline_start = baseline_df["timestamp_hour"].min()
    baseline_end = baseline_df["timestamp_hour"].max()
    recent_start = recent_df["timestamp_hour"].min()
    recent_end = recent_df["timestamp_hour"].max()

    return {
        "report_generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_time_utc": reference_time.astimezone(timezone.utc).isoformat(),
        "baseline_window": {
            "start_utc": baseline_start.isoformat(),
            "end_utc": baseline_end.isoformat(),
            "rows": int(len(baseline_df)),
        },
        "recent_window": {
            "start_utc": recent_start.isoformat(),
            "end_utc": recent_end.isoformat(),
            "rows": int(len(recent_df)),
        },
        "drift_detected": drift_detected,
        "drift_type": drift_type,
        "baseline_error": baseline_mean_error,
        "recent_error": recent_mean_error,
        "baseline_mean_prediction": baseline_mean_prediction,
        "recent_mean_prediction": recent_mean_prediction,
        "baseline_std_prediction": baseline_std_prediction,
    }


def run_drift_detection(
    metrics_path: str | None = None,
    report_path: str | None = None,
) -> dict[str, Any]:
    root = _project_root()
    resolved_metrics = (
        Path(metrics_path) if metrics_path else root / "data" / "metrics" / "hourly_metrics"
    )
    resolved_report = (
        Path(report_path) if report_path else root / "artifacts" / "drift" / "drift_report.json"
    )
    resolved_report.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "drift-detection-started",
        extra={"metrics_path": str(resolved_metrics)},
    )

    metrics_df = _load_hourly_metrics(resolved_metrics)

    # Anchor detection windows to the newest metric timestamp so historical replay data
    # (e.g., 2018/2019) can still be evaluated without relying on wall-clock time.
    reference = metrics_df["timestamp_hour"].max()
    if pd.isna(reference):
        raise ValueError("Metrics dataset has no valid timestamp_hour values")

    baseline_df, recent_df = _split_windows(metrics_df, now=reference.to_pydatetime())

    report = _compute_drift_report(baseline_df, recent_df, reference.to_pydatetime())

    if report["drift_detected"]:
        logger.warning(
            "drift-detected",
            extra={
                "drift_type": report["drift_type"],
                "baseline_error": report["baseline_error"],
                "recent_error": report["recent_error"],
            },
        )

    resolved_report.write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(
        "drift-detection-complete",
        extra={
            "drift_detected": report["drift_detected"],
            "drift_type": report["drift_type"],
            "report_path": str(resolved_report),
        },
    )

    return report


def main() -> None:
    configure_logging(level="INFO", json_logs=False)
    try:
        report = run_drift_detection()
        print(json.dumps(report, indent=2, default=str))
        sys.exit(0)
    except Exception as exc:
        logger.error("drift-detection-failed", extra={"error": str(exc)})
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
