"""Inspect model version values present in hourly metrics parquet output.

Usage:
    python scripts/utilities/check_model_version_in_metrics.py
    python scripts/utilities/check_model_version_in_metrics.py --tail 20
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Check active model version values in hourly metrics")
    parser.add_argument(
        "--metrics-path",
        default=None,
        help="Optional metrics directory (default: data/metrics/hourly_metrics)",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=10,
        help="Number of latest rows to show",
    )
    args = parser.parse_args()

    root = _project_root()
    metrics_path = Path(args.metrics_path) if args.metrics_path else root / "data" / "metrics" / "hourly_metrics"

    files = sorted(metrics_path.rglob("*.parquet"))
    if not files:
        print("no_parquet_files_found")
        return

    frames = []
    for f in files:
        try:
            if f.stat().st_size == 0:
                continue
            frames.append(pd.read_parquet(f))
        except Exception as exc:
            print(f"skip_bad_file: {f} | {exc}")

    if not frames:
        print("no_readable_parquet_files")
        return

    df = pd.concat(frames, ignore_index=True)
    if "timestamp_hour" in df.columns:
        df["timestamp_hour"] = pd.to_datetime(df["timestamp_hour"], errors="coerce")
        df = df.sort_values("timestamp_hour")

    if "active_model_version" not in df.columns:
        print("active_model_version_column_missing")
        print("note: start a new Spark run after latest code to populate this column")
        return

    print("unique_active_model_versions:", sorted(df["active_model_version"].dropna().astype(str).unique().tolist()))
    print("latest_rows:")
    cols = [c for c in ["timestamp_hour", "active_model_version", "mean_error", "record_count"] if c in df.columns]
    print(df[cols].tail(max(1, args.tail)).to_string(index=False))


if __name__ == "__main__":
    main()
