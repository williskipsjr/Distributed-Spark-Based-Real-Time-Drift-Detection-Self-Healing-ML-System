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
from src.data.feature_builder import FEATURE_COLUMNS


logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_base_config() -> Config:
    return Config.load(env_name="base", env_file="base.yaml")


def _resolve_dataset_path(dataset_path: str | None) -> Path:
    root = _project_root()
    resolved = Path(dataset_path) if dataset_path else root / "data" / "processed" / "pjm_supervised.parquet"
    if not resolved.exists():
        raise FileNotFoundError(f"Supervised dataset not found: {resolved}")
    return resolved


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
    df = pd.read_parquet(resolved_dataset)
    required_columns = ["datetime", "load_mw"] + FEATURE_COLUMNS
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise KeyError(f"Supervised dataset is missing required columns: {', '.join(missing)}")

    df = df.copy()
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
                    extra={"topic": topic, "offset_record": published_count, "timestamp": payload["timestamp"]},
                )
                time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("producer-stop", extra={"published_records": published_count, "reason": "keyboard-interrupt"})
    finally:
        producer.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish PJM load records to Kafka as a simulated real-time stream")
    parser.add_argument("--dataset", dest="dataset_path", default=None, help="Path to cleaned parquet dataset")
    parser.add_argument(
        "--sleep-seconds",
        dest="sleep_seconds",
        type=float,
        default=0.1,
        help="Delay between published records",
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
