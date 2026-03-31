"""Delete zero-byte Parquet shards from hourly metrics output.

Usage:
    python scripts/utilities/cleanup_zero_byte_metrics.py
    python scripts/utilities/cleanup_zero_byte_metrics.py --dry-run
    python scripts/utilities/cleanup_zero_byte_metrics.py --metrics-path data/metrics/hourly_metrics
"""

from __future__ import annotations

import argparse
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cleanup_zero_byte_metrics(metrics_path: Path, dry_run: bool = False) -> tuple[int, int]:
    parquet_files = list(metrics_path.rglob("*.parquet"))
    deleted = 0

    for parquet_file in parquet_files:
        if parquet_file.stat().st_size == 0:
            if dry_run:
                print(f"would-delete: {parquet_file}")
            else:
                parquet_file.unlink(missing_ok=True)
                print(f"deleted: {parquet_file}")
            deleted += 1

    return len(parquet_files), deleted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete zero-byte parquet files from hourly metrics directory"
    )
    parser.add_argument(
        "--metrics-path",
        default=None,
        help="Path to hourly metrics directory (default: data/metrics/hourly_metrics)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would be deleted without deleting",
    )
    args = parser.parse_args()

    root = _project_root()
    metrics_path = Path(args.metrics_path) if args.metrics_path else root / "data" / "metrics" / "hourly_metrics"

    if not metrics_path.exists():
        raise FileNotFoundError(f"Metrics path does not exist: {metrics_path}")

    total, deleted = cleanup_zero_byte_metrics(metrics_path, dry_run=args.dry_run)
    action = "would-delete" if args.dry_run else "deleted"
    print(f"scanned_parquet_files: {total}")
    print(f"{action}_zero_byte_files: {deleted}")


if __name__ == "__main__":
    main()
