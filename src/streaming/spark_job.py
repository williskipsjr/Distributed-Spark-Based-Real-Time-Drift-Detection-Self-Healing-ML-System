from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

from src.common.config import Config
from src.common.logging import configure_logging, get_logger
from src.data.feature_builder import FEATURE_COLUMNS
from src.ml.model_io import get_model_version, load_model

logger = get_logger(__name__)

DEBUG_MODE = True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_base_config() -> Config:
    return Config.load(env_name="base", env_file="base.yaml")


def _create_spark_session() -> SparkSession:
    return (
        SparkSession.builder.appName("pjm-load-streaming")
        .master("local[*]")
        .config("spark.hadoop.io.native.lib.available", "false")
        .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem")
        .config("spark.hadoop.fs.file.impl.disable.cache", "true")
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1")
        .getOrCreate()
    )


def _kafka_message_schema() -> StructType:
    features_schema = StructType(
        [
            StructField("hour_of_day", DoubleType(), True),
            StructField("day_of_week", DoubleType(), True),
            StructField("month", DoubleType(), True),
            StructField("is_weekend", DoubleType(), True),
            StructField("lag_1", DoubleType(), True),
            StructField("lag_24", DoubleType(), True),
            StructField("lag_168", DoubleType(), True),
            StructField("rolling_24", DoubleType(), True),
            StructField("rolling_168", DoubleType(), True),
        ]
    )

    return StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("load_mw", DoubleType(), False),
            StructField("features", features_schema, True),
        ]
    )


def _prepare_stream(spark: SparkSession, bootstrap_servers: str, topic: str) -> DataFrame:
    kafka_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap_servers)
        .option("subscribe", topic)
        .option("startingOffsets", "latest")
        .load()
    )

    return (
        kafka_df.select(F.col("value").cast("string").alias("json_value"))
        .select("json_value", F.from_json(F.col("json_value"), _kafka_message_schema()).alias("payload"))
        .select("json_value", "payload.timestamp", "payload.load_mw", "payload.features.*")
        .withColumn("timestamp", F.to_timestamp(F.col("timestamp")))
        .withColumn("actual_load", F.col("load_mw").cast("double"))
        .drop("load_mw")
        .dropna(subset=["timestamp", "actual_load"])
    )


def _clear_directory_contents(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _ensure_feature_columns(df: DataFrame) -> DataFrame:
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    out = df
    for c in FEATURE_COLUMNS:
        out = out.withColumn(c, F.col(c).cast("double"))
    return out


def _validate_feature_batch(batch_df: DataFrame, batch_id: int) -> None:
    if batch_df.rdd.isEmpty():
        return

    print(f"\n=== PRE-UDF FEATURE VALIDATION | batch_id={batch_id} ===")

    # Null check
    null_df = batch_df.select([F.count(F.when(F.col(c).isNull(), 1)).alias(c) for c in FEATURE_COLUMNS])
    null_df.show(truncate=False)

    null_counts = null_df.collect()[0].asDict()
    bad = {k: int(v) for k, v in null_counts.items() if int(v) > 0}
    if bad:
        raise ValueError(f"NULL values detected in features: {bad}")

    # Range check with distribution warning
    range_df = batch_df.select(
        *[F.min(c).alias(f"{c}_min") for c in FEATURE_COLUMNS],
        *[F.max(c).alias(f"{c}_max") for c in FEATURE_COLUMNS],
        F.avg("lag_1").alias("lag_1_mean"),
        F.avg("lag_24").alias("lag_24_mean"),
    )
    range_df.show(truncate=False)

    # CRITICAL: Warn if lag features are outside expected range
    # Training data had lag_1 mean ~183,000; if we see <10,000, distribution has shifted
    range_row = range_df.collect()[0]
    lag_1_mean = float(range_row["lag_1_mean"]) if range_row["lag_1_mean"] is not None else 0

    if lag_1_mean < 50000 and lag_1_mean > 0:
        logger.warning(
            "feature-distribution-shift-detected",
            extra={
                "expected_lag_1_mean": 183000,
                "actual_lag_1_mean": lag_1_mean,
                "ratio": lag_1_mean / 183000,
                "warning": "Input features are significantly different from training distribution"
            }
        )
        print(f"\n*** WARNING: Distribution Shift Detected! ***")
        print(f"    Expected lag_1 mean: ~183,000")
        print(f"    Actual lag_1 mean: {lag_1_mean:,.0f}")
        print(f"    This may indicate:")
        print(f"    - Load values are aggregated at different level than training")
        print(f"    - Streaming source provides per-zone instead of per-area")
        print(f"    - Year-over-year demand changes")
        print(f"*** Predictions may be out-of-distribution ***\n")

    # Dtype check
    print(batch_df.select(*FEATURE_COLUMNS).dtypes)
    print("===============================================\n")


def _build_prediction_udf(broadcast_model):
    @F.pandas_udf(DoubleType())
    def predict_load(pdf: pd.DataFrame) -> pd.Series:
        bundle = broadcast_model.value
        model = bundle["model"]
        features = bundle["features"]

        # CRITICAL FIX: When struct is unpacked, Spark may not preserve column order
        # or may pass columns as a MultiIndex. Explicitly reindex to match model expectations.
        features_df = pdf.copy().reset_index(drop=True)

        # Verify all feature columns exist
        missing = [c for c in features if c not in features_df.columns]
        if missing:
            raise ValueError(f"Missing feature columns in UDF input: {missing}")

        # SELECT COLUMNS IN EXPLICIT ORDER and ensure correct dtype
        # This prevents any ambiguity in column ordering or struct unpacking
        features_df = features_df[features].astype("float64")

        # Verify column order matches model expectations (critical for tree models)
        if list(features_df.columns) != list(features):
            raise ValueError(f"Feature column order mismatch. Got {list(features_df.columns)}, expected {list(features)}")

        # Check for NaN/NULL values
        if features_df.isnull().any().any():
            raise ValueError("NaN/NULL detected in UDF feature batch")

        if DEBUG_MODE and len(features_df) > 0:
            print("\n=== UDF INPUT SAMPLE ===")
            print(features_df.head(1).to_dict(orient="records")[0])
            print("========================\n")

        # Run model inference
        preds = model.predict(features_df)

        if DEBUG_MODE and len(preds) > 0:
            print("UDF PRED SAMPLE:", preds[:5])

        return pd.Series(preds, dtype="float64")

    return predict_load


def _validate_actual_load_column(df: DataFrame) -> None:
    if "actual_load" not in df.columns:
        raise ValueError("actual_load column missing — error metrics cannot be computed")


def _add_predictions(stream_df: DataFrame, broadcast_model, model_version: str) -> DataFrame:
    _validate_actual_load_column(stream_df)
    prepared_df = _ensure_feature_columns(stream_df)

    predict_load = _build_prediction_udf(broadcast_model)

    return (
        prepared_df.withColumn(
            "predicted_load",
            predict_load(F.struct(*[F.col(c) for c in FEATURE_COLUMNS])),
        )
        .withColumn("error", F.abs(F.col("actual_load") - F.col("predicted_load")))
        .withColumn("model_version", F.lit(model_version))
    )


def _build_hourly_metrics(scored_df: DataFrame) -> DataFrame:
    return (
        scored_df.withWatermark("timestamp", "1 hour")
        .groupBy(F.window(F.col("timestamp"), "1 hour"))
        .agg(
            F.avg(F.col("predicted_load")).alias("mean_prediction"),
            F.max(F.col("predicted_load")).alias("max_prediction"),
            F.min(F.col("predicted_load")).alias("min_prediction"),
            F.stddev_samp(F.col("predicted_load")).alias("std_prediction"),
            F.avg(F.col("error")).alias("mean_error"),
            F.max(F.col("error")).alias("max_error"),
            F.count(F.lit(1)).alias("record_count"),
        )
        .select(
            F.col("window.start").alias("timestamp_hour"),
            "mean_prediction",
            "max_prediction",
            "min_prediction",
            "std_prediction",
            "mean_error",
            "max_error",
            "record_count",
        )
    )


def _write_metrics_batch(batch_df: DataFrame, batch_id: int, output_path: Path) -> None:
    rows = int(batch_df.count())
    if rows == 0:
        return

    batch_df.write.mode("append").parquet(str(output_path))
    logger.info(
        "metrics-batch-written",
        extra={"batch_id": int(batch_id), "rows": rows, "output_path": str(output_path)},
    )


def _safe_batch_write(batch_df: DataFrame, batch_id: int, output_path: Path) -> None:
    try:
        _write_metrics_batch(batch_df, batch_id, output_path)
    except Exception as e:
        print(f"BATCH FAILED: {e}")
        raise


def run_streaming_job(
    output_path: str | None = None,
    checkpoint_path: str | None = None,
    debug_mode: bool = DEBUG_MODE,
) -> None:
    config = _load_base_config()
    bootstrap_servers = config.get("kafka.bootstrap_servers", "localhost:9092")
    topic = config.get("kafka.topics.raw_load", "pjm.load")

    root = _project_root()
    resolved_output = Path(output_path) if output_path else root / "data" / "metrics" / "hourly_metrics"
    resolved_checkpoint = Path(checkpoint_path) if checkpoint_path else root / "checkpoints" / "spark_predictions"
    predictions_output = root / "data" / "predictions"

    resolved_output.mkdir(parents=True, exist_ok=True)
    if resolved_checkpoint.exists():
        shutil.rmtree(resolved_checkpoint)
    resolved_checkpoint.mkdir(parents=True, exist_ok=True)
    _clear_directory_contents(predictions_output)

    spark = _create_spark_session()

    model_path = root / "artifacts" / "models" / "model_v1.joblib"
    bundle = load_model(model_path=str(model_path))
    print("MODEL PATH:", str(model_path))
    print("MODEL FEATURES:", bundle["features"])

    model_version = get_model_version(bundle)
    broadcast_model = spark.sparkContext.broadcast(bundle)

    stream_df = _prepare_stream(spark=spark, bootstrap_servers=bootstrap_servers, topic=topic)
    stream_df = _ensure_feature_columns(stream_df)

    # Pre-UDF live feature debug stream
    debug_stream = (
        stream_df.select("timestamp", "actual_load", *FEATURE_COLUMNS)
        .writeStream
        .format("console")
        .option("truncate", False)
        .option("numRows", 20)
        .option("checkpointLocation", str(resolved_checkpoint / "feature_debug_ckpt"))
        .outputMode("append")
        .start()
    )

    # Pre-UDF batch validation stream
    validation_stream = (
        stream_df.select(*FEATURE_COLUMNS)
        .writeStream
        .foreachBatch(_validate_feature_batch)
        .option("checkpointLocation", str(resolved_checkpoint / "feature_validation_ckpt"))
        .outputMode("append")
        .start()
    )

    scored_df = _add_predictions(stream_df, broadcast_model, model_version)

    if debug_mode:
        main_query = (
            scored_df.select("timestamp", "actual_load", "predicted_load", "error", "model_version", *FEATURE_COLUMNS)
            .writeStream
            .format("console")
            .option("truncate", False)
            .option("numRows", 20)
            .option("checkpointLocation", str(resolved_checkpoint / "scored_debug_ckpt"))
            .outputMode("append")
            .start()
        )
    else:
        metrics_df = _build_hourly_metrics(scored_df)
        main_query = (
            metrics_df.writeStream
            .outputMode("update")
            .option("checkpointLocation", str(resolved_checkpoint / "metrics_ckpt"))
            .foreachBatch(lambda batch_df, batch_id: _safe_batch_write(batch_df, batch_id, resolved_output))
            .start()
        )

    try:
        main_query.awaitTermination()
    finally:
        if debug_stream.isActive:
            debug_stream.stop()
        if validation_stream.isActive:
            validation_stream.stop()
        if main_query.isActive:
            main_query.stop()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spark Structured Streaming inference job")
    parser.add_argument("--output-path", dest="output_path", default=None, help="Output parquet path")
    parser.add_argument("--checkpoint-path", dest="checkpoint_path", default=None, help="Checkpoint directory")
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
    parser.add_argument(
        "--debug-mode",
        action=argparse.BooleanOptionalAction,
        default=DEBUG_MODE,
        help="Enable debug console output and disable parquet metrics sink",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    configure_logging(level=args.log_level, json_logs=True)
    run_streaming_job(
        output_path=args.output_path,
        checkpoint_path=args.checkpoint_path,
        debug_mode=args.debug_mode,
    )


if __name__ == "__main__":
    main()