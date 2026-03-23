from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
from kafka import KafkaProducer

from src.common.config import Config
from src.common.logging import configure_logging, get_logger
from src.data.feature_builder import FEATURE_COLUMNS, build_supervised_pandas, FeatureSpec


logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_base_config() -> Config:
    return Config.load(env_name="base", env_file="base.yaml")


def _resolve_dataset_path(dataset_path: str | None) -> Path:
    """Resolve input path, supporting both supervised (aggregate) and raw (zone-level) formats."""
    root = _project_root()

    if dataset_path:
        resolved = Path(dataset_path)
        if resolved.exists():
            return resolved
        raise FileNotFoundError(f"Dataset not found: {resolved}")

    # Try supervised (aggregate) first
    supervised = root / "data" / "processed" / "pjm_supervised.parquet"
    if supervised.exists():
        return supervised

    # Fall back to raw zone-level data
    raw = root / "data" / "raw" / "hrl_load_metered-2018.csv"
    if raw.exists():
        return raw

    raise FileNotFoundError("No dataset found. Tried: pjm_supervised.parquet, hrl_load_metered-2018.csv")


def _load_and_prepare_data(dataset_path: Path) -> pd.DataFrame:
    """
    Load dataset and ensure it's in aggregate form (PJM-wide, not per-zone).

    Handles two cases:
    1. Supervised parquet (already aggregate) - use as-is
    2. Raw CSV (zone-level) - aggregate by timestamp
    """
    if dataset_path.suffix == ".parquet":
        logger.info("loading-aggregate-parquet", extra={"path": str(dataset_path)})
        df = pd.read_parquet(dataset_path)

        # Verify required columns exist
        required = ["datetime", "load_mw"] + FEATURE_COLUMNS
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise KeyError(f"Supervised dataset missing columns: {', '.join(missing)}")

        return df

    elif dataset_path.suffix == ".csv":
        logger.info("loading-zone-level-csv", extra={"path": str(dataset_path)})
        df = pd.read_csv(dataset_path)

        # Standardize column names
        df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
        if "mw" not in df.columns:
            raise KeyError("CSV dataset must contain 'mw' column")

        # Use EPT timezone column (local time for load area)
        datetime_col = "datetime_beginning_ept" if "datetime_beginning_ept" in df.columns else "datetime_beginning_utc"
        if datetime_col not in df.columns:
            raise KeyError(f"CSV dataset must contain '{datetime_col}' column")

        df["datetime"] = pd.to_datetime(df[datetime_col], errors="coerce")
        df = df.dropna(subset=["datetime", "mw"]).copy()

        # CRITICAL FIX: Aggregate all zones per timestamp
        # This matches the training pipeline which did: df.groupby("datetime")["load_mw"].sum()
        logger.info(
            "aggregating-zones-to-pjm-wide",
            extra={
                "unique_timestamps_before": df["datetime"].nunique(),
                "unique_zones": df["load_area"].nunique() if "load_area" in df.columns else 0,
            },
        )

        df_agg = df.groupby("datetime")["mw"].sum().reset_index()
        df_agg.columns = ["datetime", "load_mw"]
        df_agg = df_agg.sort_values("datetime").reset_index(drop=True)

        logger.info(
            "zone-aggregation-complete",
            extra={
                "rows": len(df_agg),
                "load_mw_mean": float(df_agg["load_mw"].mean()),
                "load_mw_range": [float(df_agg["load_mw"].min()), float(df_agg["load_mw"].max())],
            },
        )

        # Build features on aggregated data (same as training)
        df_with_features = build_supervised_pandas(
            df=df_agg,
            spec=FeatureSpec(timestamp_col="datetime", target_col="load_mw", group_cols=()),
            drop_na_features=True,
        )

        logger.info(
            "feature-engineering-complete",
            extra={"rows": len(df_with_features), "lag_1_mean": float(df_with_features["lag_1"].mean())},
        )

        return df_with_features

    else:
        raise ValueError(f"Unsupported file format: {dataset_path.suffix}")


def _create_producer(bootstrap_servers: str) -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda payload: json.dumps(payload).encode("utf-8"),
        linger_ms=10,
        retries=3,
        acks="all",
    )


def run_producer(dataset_path: str | None = None, sleep_seconds: float = 0.1) -> None:
    config = _load_base_config()
    bootstrap_servers = config.get("kafka.bootstrap_servers", "localhost:9092")
    topic = config.get("kafka.topics.raw_load", "pjm.load")

    resolved_dataset = _resolve_dataset_path(dataset_path)
    df = _load_and_prepare_data(resolved_dataset)

    # Verify data is in expected range (aggregate PJM-wide)
    mean_load = df["load_mw"].mean()
    if mean_load < 50000:
        logger.warning(
            "data-distribution-warning",
            extra={
                "mean_load": mean_load,
                "warning": "Mean load < 50k. Data may not be aggregated to PJM-wide level!",
                "expected_mean": "~180k",
            },
        )

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", "load_mw"]).sort_values("datetime").reset_index(drop=True)

    producer = _create_producer(bootstrap_servers=bootstrap_servers)
    logger.info(
        "producer-start",
        extra={
            "dataset_path": str(resolved_dataset),
            "rows": int(len(df)),
            "topic": topic,
            "bootstrap_servers": bootstrap_servers,
            "sleep_seconds": sleep_seconds,
            "mean_load_mw": float(mean_load),
        },
    )

    published_count = 0
    try:
        while True:
            for _, row in df.iterrows():
                payload: dict[str, Any] = {
                    "timestamp": row["datetime"].isoformat(),
                    "load_mw": float(row["load_mw"]),
                    "features": {
                        "hour_of_day": int(row["hour_of_day"]),
                        "day_of_week": int(row["day_of_week"]),
                        "month": int(row["month"]),
                        "is_weekend": int(row["is_weekend"]),
                        "lag_1": float(row["lag_1"]),
                        "lag_24": float(row["lag_24"]),
                        "lag_168": float(row["lag_168"]),
                        "rolling_24": float(row["rolling_24"]),
                        "rolling_168": float(row["rolling_168"]),
                    },
                }
                producer.send(topic, value=payload)
                producer.flush()

                published_count += 1
                logger.info(
                    "record-published",
                    extra={
                        "topic": topic,
                        "offset_record": published_count,
                        "timestamp": payload["timestamp"],
                        "load_mw": payload["load_mw"],
                    },
                )
                time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("producer-stop", extra={"published_records": published_count, "reason": "keyboard-interrupt"})
    finally:
        producer.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish aggregated PJM load records to Kafka as a simulated real-time stream. "
        "Accepts both aggregate parquet files and raw zone-level CSVs (aggregates on-the-fly)."
    )
    parser.add_argument(
        "--dataset",
        dest="dataset_path",
        default=None,
        help="Path to dataset (parquet or CSV). If CSV, must be zone-level data (auto-aggregates to PJM-wide).",
    )
    parser.add_argument(
        "--sleep-seconds",
        dest="sleep_seconds",
        type=float,
        default=0.1,
        help="Delay between published records (seconds)",
    )
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=True)
    run_producer(dataset_path=args.dataset_path, sleep_seconds=args.sleep_seconds)


if __name__ == "__main__":
    main()

