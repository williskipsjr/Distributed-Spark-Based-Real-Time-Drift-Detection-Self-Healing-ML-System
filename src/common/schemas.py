from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class PJMLoadRecord:
    datetime_beginning_utc: datetime
    datetime_beginning_ept: datetime
    nerc_region: str | None
    market_region: str | None
    transmission_zone: str | None
    load_area: str | None
    mw: float
    company_verified: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PJMLoadRecord":
        return cls(
            datetime_beginning_utc=_as_datetime(data["datetime_beginning_utc"]),
            datetime_beginning_ept=_as_datetime(data["datetime_beginning_ept"]),
            nerc_region=data.get("nerc_region"),
            market_region=data.get("market_region"),
            transmission_zone=data.get("transmission_zone"),
            load_area=data.get("load_area"),
            mw=float(data["mw"]),
            company_verified=_as_optional_bool(data.get("company_verified")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class KafkaLoadMessage:
    event_id: str
    event_time: datetime
    source: str
    payload: PJMLoadRecord

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KafkaLoadMessage":
        return cls(
            event_id=str(data["event_id"]),
            event_time=_as_datetime(data["event_time"]),
            source=str(data.get("source", "pjm_api")),
            payload=PJMLoadRecord.from_dict(data["payload"]),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["payload"] = self.payload.to_dict()
        return payload


@dataclass(slots=True)
class PredictionRecord:
    prediction_time: datetime
    event_time: datetime
    model_version: str
    actual_mw: float | None
    predicted_mw: float
    abs_error: float | None
    load_area: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictionRecord":
        actual = data.get("actual_mw")
        predicted = float(data["predicted_mw"])
        abs_error = data.get("abs_error")
        if abs_error is None and actual is not None:
            abs_error = abs(float(actual) - predicted)

        return cls(
            prediction_time=_as_datetime(data["prediction_time"]),
            event_time=_as_datetime(data["event_time"]),
            model_version=str(data["model_version"]),
            actual_mw=float(actual) if actual is not None else None,
            predicted_mw=predicted,
            abs_error=float(abs_error) if abs_error is not None else None,
            load_area=data.get("load_area"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DriftMetricRecord:
    timestamp: datetime
    feature_name: str
    ks_stat: float
    ks_pvalue: float
    psi_score: float
    rolling_mae: float | None
    drift_flag: bool
    severity: str
    model_version: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DriftMetricRecord":
        return cls(
            timestamp=_as_datetime(data["timestamp"]),
            feature_name=str(data["feature_name"]),
            ks_stat=float(data["ks_stat"]),
            ks_pvalue=float(data["ks_pvalue"]),
            psi_score=float(data["psi_score"]),
            rolling_mae=float(data["rolling_mae"]) if data.get("rolling_mae") is not None else None,
            drift_flag=bool(data["drift_flag"]),
            severity=str(data.get("severity", "stable")),
            model_version=str(data["model_version"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pjm_spark_schema():
    from pyspark.sql.types import BooleanType, DoubleType, StringType, StructField, StructType

    return StructType(
        [
            StructField("datetime_beginning_utc", StringType(), False),
            StructField("datetime_beginning_ept", StringType(), False),
            StructField("nerc_region", StringType(), True),
            StructField("market_region", StringType(), True),
            StructField("transmission_zone", StringType(), True),
            StructField("load_area", StringType(), True),
            StructField("mw", DoubleType(), False),
            StructField("company_verified", BooleanType(), True),
        ]
    )


def prediction_spark_schema():
    from pyspark.sql.types import DoubleType, StringType, StructField, StructType

    return StructType(
        [
            StructField("prediction_time", StringType(), False),
            StructField("event_time", StringType(), False),
            StructField("model_version", StringType(), False),
            StructField("actual_mw", DoubleType(), True),
            StructField("predicted_mw", DoubleType(), False),
            StructField("abs_error", DoubleType(), True),
            StructField("load_area", StringType(), True),
        ]
    )


def drift_metric_spark_schema():
    from pyspark.sql.types import BooleanType, DoubleType, StringType, StructField, StructType

    return StructType(
        [
            StructField("timestamp", StringType(), False),
            StructField("feature_name", StringType(), False),
            StructField("ks_stat", DoubleType(), False),
            StructField("ks_pvalue", DoubleType(), False),
            StructField("psi_score", DoubleType(), False),
            StructField("rolling_mae", DoubleType(), True),
            StructField("drift_flag", BooleanType(), False),
            StructField("severity", StringType(), False),
            StructField("model_version", StringType(), False),
        ]
    )


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise ValueError("Datetime field cannot be null")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _as_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None
