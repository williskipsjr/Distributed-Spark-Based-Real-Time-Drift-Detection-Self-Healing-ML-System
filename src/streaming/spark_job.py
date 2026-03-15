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
from src.data.feature_builder import FEATURE_COLUMNS, add_time_features_spark
from src.ml.model_io import get_model_version, load_model


logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_base_config() -> Config:
    return Config.load(env_name="base", env_file="base.yaml")


def _create_spark_session() -> SparkSession:
    spark = (
        SparkSession.builder.appName("pjm-load-streaming")
        .master("local[*]")
        .config("spark.hadoop.io.native.lib.available", "false")
        .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem")
        .config("spark.hadoop.fs.file.impl.disable.cache", "true")
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1")
        .getOrCreate()
    )

    return spark


def _kafka_message_schema() -> StructType:
    return StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("load_mw", DoubleType(), False),
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

    parsed = (
        kafka_df.select(F.col("value").cast("string").alias("json_value"))
        .select(F.from_json(F.col("json_value"), _kafka_message_schema()).alias("payload"))
        .select("payload.*")
        .withColumn("timestamp", F.to_timestamp(F.col("timestamp")))
        .withColumn("actual_load", F.col("load_mw").cast("double"))
        .drop("load_mw")
        .dropna(subset=["timestamp", "actual_load"])
    )

    with_time_features = add_time_features_spark(parsed, timestamp_col="timestamp")
    return with_time_features


def _clear_directory_contents(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _ensure_feature_columns(df: DataFrame) -> DataFrame:
    result = df
    for feature_name in FEATURE_COLUMNS:
        if feature_name not in result.columns:
            result = result.withColumn(feature_name, F.lit(0.0))
        result = result.withColumn(feature_name, F.col(feature_name).cast("double"))
    return result


def _build_prediction_udf(broadcast_model):
    @F.pandas_udf(DoubleType())
    def predict_load(*feature_columns: pd.Series) -> pd.Series:
        bundle = broadcast_model.value
        model = bundle["model"]
        features = bundle["features"]
        features_df = pd.concat(feature_columns, axis=1)
        features_df.columns = FEATURE_COLUMNS  # assign Spark column names
        features_df = features_df.astype(float, errors="ignore")
        features_df = features_df[features]  # enforce bundle feature order
        predictions = model.predict(features_df)
        return pd.Series(predictions, dtype="float64")

    return predict_load


def _validate_actual_load_column(df: DataFrame) -> None:
    if "actual_load" not in df.columns:
        logger.error(
            "actual_load-column-missing",
            extra={"message": "actual_load column missing — error metrics cannot be computed"},
        )
        raise ValueError("actual_load column missing — error metrics cannot be computed")


def _add_predictions(stream_df: DataFrame, broadcast_model, model_version: str) -> DataFrame:
    _validate_actual_load_column(stream_df)
    predict_load = _build_prediction_udf(broadcast_model)
    prepared_df = _ensure_feature_columns(stream_df)

    return (
        prepared_df.withColumn("predicted_load", predict_load(*[F.col(feature) for feature in FEATURE_COLUMNS]))
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
            F.col("mean_prediction"),
            F.col("max_prediction"),
            F.col("min_prediction"),
            F.col("std_prediction"),
            F.col("mean_error"),
            F.col("max_error"),
            F.col("record_count"),
        )
    )


def _write_metrics_batch(batch_df: DataFrame, batch_id: int, output_path: Path) -> None:
    rows = int(batch_df.count())
    if rows == 0:
        return

    logger.info(
        "hourly-metrics-computed",
        extra={
            "batch_id": int(batch_id),
            "rows": rows,
        },
    )
    logger.info(
        "error-metrics-computed",
        extra={
            "batch_id": int(batch_id),
            "rows": rows,
        },
    )

    batch_df.write.mode("append").parquet(str(output_path))

    logger.info(
        "metrics-batch-written",
        extra={
            "batch_id": int(batch_id),
            "output_path": str(output_path),
            "rows": rows,
        },
    )


def run_streaming_job(output_path: str | None = None, checkpoint_path: str | None = None) -> None:
    config = _load_base_config()
    bootstrap_servers = config.get("kafka.bootstrap_servers", "localhost:9092")
    topic = config.get("kafka.topics.raw_load", "pjm.load")

    root = _project_root()
    predictions_output = root / "data" / "predictions"
    resolved_output = Path(output_path) if output_path else root / "data" / "metrics" / "hourly_metrics"
    resolved_checkpoint = Path(checkpoint_path) if checkpoint_path else root / "checkpoints" / "spark_predictions"
    resolved_output.mkdir(parents=True, exist_ok=True)
    if resolved_checkpoint.exists():
        shutil.rmtree(resolved_checkpoint)
    resolved_checkpoint.mkdir(parents=True, exist_ok=True)
    _clear_directory_contents(predictions_output)

    model_path = root / "artifacts" / "models" / "model_v1.joblib"
    spark = _create_spark_session()
    model = load_model(model_path=str(model_path))
    model_version = get_model_version(model)
    broadcast_model = spark.sparkContext.broadcast(model)
    logger.info("model-broadcast-created", extra={"model_version": model_version})

    stream_df = _prepare_stream(spark=spark, bootstrap_servers=bootstrap_servers, topic=topic)
    scored_stream_df = _add_predictions(
        stream_df=stream_df,
        broadcast_model=broadcast_model,
        model_version=model_version,
    )
    hourly_metrics_df = _build_hourly_metrics(scored_df=scored_stream_df)

    logger.info(
        "spark-stream-start",
        extra={
            "app_name": "pjm-load-streaming",
            "bootstrap_servers": bootstrap_servers,
            "topic": topic,
            "output_path": str(resolved_output),
            "checkpoint_path": str(resolved_checkpoint),
            "predictions_cleanup_path": str(predictions_output),
            "model_version": model_version,
        },
    )

    logger.info(
        "hourly-metrics-configured",
        extra={
            "window_duration": "1 hour",
            "output_path": str(resolved_output),
        },
    )

    deduped_hourly_metrics_df = (
        hourly_metrics_df.withColumn("timestamp_hour", F.date_format(F.col("timestamp_hour"), "yyyy-MM-dd-HH"))
        .dropDuplicates(["timestamp_hour"])
    )

    query = (
        deduped_hourly_metrics_df.writeStream.format("parquet")
        .option("checkpointLocation", str(resolved_checkpoint))
        .partitionBy("timestamp_hour")
        .outputMode("append")
        .start(str(resolved_output))
    )
    query.awaitTermination()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spark Structured Streaming prediction job for PJM load events")
    parser.add_argument("--output-path", dest="output_path", default=None, help="Parquet sink directory")
    parser.add_argument(
        "--checkpoint-path",
        dest="checkpoint_path",
        default=None,
        help="Checkpoint directory for Spark streaming",
    )
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=True)
    run_streaming_job(output_path=args.output_path, checkpoint_path=args.checkpoint_path)


if __name__ == "__main__":
    main()
