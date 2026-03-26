from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
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


def _load_resume_state(state_path: Path) -> dict[str, Any] | None:
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("resume-state-load-failed", extra={"state_path": str(state_path), "error": str(exc)})
        return None


def _save_resume_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def run_producer(
    dataset_path: str | None = None,
    sleep_seconds: float = 0.1,
    resume: bool = True,
    state_path: str | None = None,
    reset_state: bool = False,
    loop_forever: bool = True,
) -> None:
    config = _load_base_config()
    bootstrap_servers = config.get("kafka.bootstrap_servers", "localhost:9092")
    topic = config.get("kafka.topics.raw_load", "pjm.load")

    resolved_dataset = _resolve_dataset_path(dataset_path)
    df = _load_and_prepare_data(resolved_dataset)
    resolved_state_path = Path(state_path) if state_path else _project_root() / "checkpoints" / "producer" / "producer_state.json"

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

    if reset_state and resolved_state_path.exists():
        resolved_state_path.unlink()
        logger.info("producer-resume-state-reset", extra={"state_path": str(resolved_state_path)})

    start_index = 0
    if resume:
        resume_state = _load_resume_state(resolved_state_path)
        if resume_state:
            saved_dataset = str(resume_state.get("dataset_path", ""))
            saved_rows = int(resume_state.get("rows", 0))
            candidate_index = int(resume_state.get("next_index", 0))
            if saved_dataset == str(resolved_dataset) and saved_rows == len(df) and 0 <= candidate_index < len(df):
                start_index = candidate_index
                logger.info(
                    "producer-resume-enabled",
                    extra={
                        "state_path": str(resolved_state_path),
                        "start_index": start_index,
                        "dataset_path": str(resolved_dataset),
                    },
                )
            elif saved_dataset != str(resolved_dataset):
                logger.info(
                    "producer-resume-state-ignored",
                    extra={
                        "reason": "dataset-mismatch",
                        "state_dataset": saved_dataset,
                        "current_dataset": str(resolved_dataset),
                    },
                )
            elif saved_rows != len(df):
                logger.info(
                    "producer-resume-state-ignored",
                    extra={
                        "reason": "row-count-mismatch",
                        "state_rows": saved_rows,
                        "current_rows": len(df),
                    },
                )

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
            "resume": resume,
            "state_path": str(resolved_state_path),
            "start_index": start_index,
            "loop_forever": loop_forever,
        },
    )

    published_count = 0
    current_index = start_index
    try:
        while True:
            if current_index >= len(df):
                if loop_forever:
                    current_index = 0
                else:
                    logger.info("producer-complete", extra={"published_records": published_count})
                    break

            row = df.iloc[current_index]
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

            current_index += 1
            published_count += 1

            if resume:
                _save_resume_state(
                    resolved_state_path,
                    {
                        "dataset_path": str(resolved_dataset),
                        "rows": len(df),
                        "next_index": current_index,
                        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )

            logger.info(
                "record-published",
                extra={
                    "topic": topic,
                    "offset_record": published_count,
                    "row_index": current_index - 1,
                    "timestamp": payload["timestamp"],
                    "load_mw": payload["load_mw"],
                },
            )
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info(
            "producer-stop",
            extra={
                "published_records": published_count,
                "next_index": current_index,
                "reason": "keyboard-interrupt",
            },
        )
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
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resume publishing from last saved row index",
    )
    parser.add_argument(
        "--state-path",
        dest="state_path",
        default=None,
        help="Path to producer resume state JSON file",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Delete producer resume state before starting",
    )
    parser.add_argument(
        "--loop-forever",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Loop dataset forever; disable to run one pass",
    )
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=True)
    run_producer(
        dataset_path=args.dataset_path,
        sleep_seconds=args.sleep_seconds,
        resume=args.resume,
        state_path=args.state_path,
        reset_state=args.reset_state,
        loop_forever=args.loop_forever,
    )


if __name__ == "__main__":
    main()

