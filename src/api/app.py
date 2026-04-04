from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import ControlActionRequest
from src.api.schemas import ControlPipelineResponse
from src.api.schemas import ControlServiceActionResponse
from src.api.schemas import ControlServiceCatalog
from src.api.schemas import ControlServiceLogsResponse
from src.api.schemas import ControlServiceState
from src.api.schemas import DashboardSummaryEnvelope
from src.api.schemas import DriftCurrentEnvelope
from src.api.schemas import DriftHistoryEnvelope
from src.api.schemas import ModelsActiveEnvelope
from src.api.schemas import ModelsVersionsEnvelope
from src.api.schemas import PredictionsEnvelope
from src.api.schemas import SelfHealingStatusEnvelope
from src.api.schemas import SystemHealthEnvelope


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso_z(value: datetime | pd.Timestamp | str | None) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        parsed = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.isoformat().replace("+00:00", "Z")

    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            value = value.tz_localize("UTC")
        else:
            value = value.tz_convert("UTC")
        return value.isoformat().replace("+00:00", "Z")

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _parse_ts(value: Any) -> datetime | None:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _is_stale(data_as_of: str | None, stale_after_seconds: int) -> bool:
    if not data_as_of:
        return True
    parsed = _parse_ts(data_as_of)
    if parsed is None:
        return True
    return (_utc_now() - parsed).total_seconds() > stale_after_seconds


def _source_status(path: Path, project_root: Path, ok: bool, error: str | None) -> dict[str, Any]:
    last_modified = None
    if path.exists():
        try:
            last_modified = _to_iso_z(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
        except Exception:
            last_modified = None

    try:
        rel_path = str(path.relative_to(project_root)).replace("\\", "/")
    except Exception:
        rel_path = str(path).replace("\\", "/")

    return {
        "ok": ok,
        "path": rel_path,
        "last_modified": last_modified,
        "error": error,
    }


def _build_envelope(
    data: Any,
    source_status: dict[str, dict[str, Any]],
    stale_after_seconds: int,
    data_as_of: str | None,
) -> dict[str, Any]:
    return {
        "generated_at": _to_iso_z(_utc_now()),
        "data_as_of": data_as_of,
        "stale_after_seconds": int(stale_after_seconds),
        "is_stale": _is_stale(data_as_of, stale_after_seconds),
        "source_status": source_status,
        "data": data,
    }


def _window_delta(window: str) -> timedelta:
    mapping = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    return mapping[window]


def _read_parquet_tree(path: Path) -> tuple[pd.DataFrame, bool, str | None]:
    if not path.exists():
        return pd.DataFrame(), False, "file_not_found"

    files = sorted(path.rglob("*.parquet"))
    if not files:
        return pd.DataFrame(), False, "no_parquet_files"

    frames: list[pd.DataFrame] = []
    for file_path in files:
        try:
            if file_path.stat().st_size == 0:
                continue
            frames.append(pd.read_parquet(file_path))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame(), False, "read_failed"

    return pd.concat(frames, ignore_index=True), True, None


def _read_json(path: Path) -> tuple[dict[str, Any], bool, str | None]:
    if not path.exists():
        return {}, False, "file_not_found"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}, False, "invalid_json_shape"
        return payload, True, None
    except Exception as exc:
        return {}, False, f"json_parse_error: {exc}"


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], bool, str | None]:
    if not path.exists():
        return [], False, "file_not_found"

    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    if isinstance(payload, dict):
                        rows.append(payload)
                except Exception:
                    continue
    except Exception as exc:
        return [], False, f"read_error: {exc}"

    return rows, True, None


def _extract_latest_metrics_row(metrics_df: pd.DataFrame) -> pd.Series | None:
    if metrics_df.empty:
        return None

    if "timestamp_hour" not in metrics_df.columns:
        return None

    frame = metrics_df.copy()
    frame["timestamp_hour"] = pd.to_datetime(frame["timestamp_hour"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp_hour"]).sort_values("timestamp_hour")
    if frame.empty:
        return None
    return frame.iloc[-1]


def _safe_float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _health_level(pct_error: float | None, drift_detected: bool) -> str:
    if drift_detected:
        return "critical"
    if pct_error is None:
        return "degraded"
    if pct_error > 10:
        return "critical"
    if pct_error > 3:
        return "degraded"
    return "ok"


@dataclass
class _ControlRuntime:
    process: subprocess.Popen[str] | None = None
    status: str = "stopped"
    last_started_at: str | None = None
    last_stopped_at: str | None = None
    last_exit_code: int | None = None
    last_error: str | None = None
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=1000))
    lock: threading.Lock = field(default_factory=threading.Lock)


def _validate_control_key(x_control_key: str | None = Header(default=None)) -> None:
    required = os.getenv("CONTROL_API_KEY")
    if required and x_control_key != required:
        raise HTTPException(status_code=403, detail="invalid control key")


def _to_wsl_path(path: Path) -> str:
    resolved = str(path.resolve())
    normalized = resolved.replace("\\", "/")
    if len(normalized) >= 2 and normalized[1] == ":":
        drive = normalized[0].lower()
        rest = normalized[2:]
        return f"/mnt/{drive}{rest}"
    return normalized


def _require_relative_csv_under(root: Path, candidate: str, base_dir: Path) -> Path:
    candidate_path = Path(candidate)
    if candidate_path.is_absolute():
        resolved = candidate_path.resolve()
    else:
        resolved = (root / candidate_path).resolve()

    if base_dir.resolve() not in resolved.parents:
        raise HTTPException(status_code=400, detail="path outside allowed directory")
    if resolved.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="only csv files allowed")
    return resolved


def _parse_service_args(service: str, args: dict[str, Any], root: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = {}

    if service == "kafka_broker":
        if args:
            raise HTTPException(status_code=400, detail="kafka_broker accepts no args")
        return parsed

    if service == "kafka_producer":
        allowed = {"dataset", "sleep_seconds", "reset_state"}
        unknown = set(args) - allowed
        if unknown:
            raise HTTPException(status_code=400, detail=f"unsupported args: {sorted(unknown)}")

        dataset = str(args.get("dataset", "data/stream_dataset/hrl_load_metered-2020.csv"))
        parsed["dataset"] = _require_relative_csv_under(root, dataset, root / "data" / "stream_dataset")

        sleep_seconds = float(args.get("sleep_seconds", 0.1))
        if sleep_seconds < 0:
            raise HTTPException(status_code=400, detail="sleep_seconds must be >= 0")
        parsed["sleep_seconds"] = sleep_seconds
        parsed["reset_state"] = bool(args.get("reset_state", False))
        return parsed

    if service == "spark_job":
        allowed = {"debug_mode", "run_seconds", "reset_checkpoint", "fail_on_data_loss"}
        unknown = set(args) - allowed
        if unknown:
            raise HTTPException(status_code=400, detail=f"unsupported args: {sorted(unknown)}")

        parsed["debug_mode"] = bool(args.get("debug_mode", False))
        run_seconds = int(args.get("run_seconds", 0))
        if run_seconds < 0:
            raise HTTPException(status_code=400, detail="run_seconds must be >= 0")
        parsed["run_seconds"] = run_seconds
        parsed["reset_checkpoint"] = bool(args.get("reset_checkpoint", False))
        parsed["fail_on_data_loss"] = bool(args.get("fail_on_data_loss", False))
        return parsed

    if service == "orchestrator":
        allowed = {
            "interval_seconds",
            "required_consecutive_drifts",
            "cooldown_minutes",
            "stream_csv_path",
            "recent_days",
            "min_relative_improvement",
        }
        unknown = set(args) - allowed
        if unknown:
            raise HTTPException(status_code=400, detail=f"unsupported args: {sorted(unknown)}")

        parsed["interval_seconds"] = max(1, int(args.get("interval_seconds", 60)))
        parsed["required_consecutive_drifts"] = max(1, int(args.get("required_consecutive_drifts", 2)))
        parsed["cooldown_minutes"] = max(0, int(args.get("cooldown_minutes", 60)))
        parsed["recent_days"] = max(1, int(args.get("recent_days", 30)))
        parsed["min_relative_improvement"] = float(args.get("min_relative_improvement", 0.02))

        csv_path = str(args.get("stream_csv_path", "data/stream_dataset/hrl_load_metered-2020.csv"))
        parsed["stream_csv_path"] = _require_relative_csv_under(root, csv_path, root / "data" / "stream_dataset")
        return parsed

    raise HTTPException(status_code=404, detail="unknown service")


def _build_start_command(service: str, parsed_args: dict[str, Any], root: Path, profile: str) -> list[str]:
    if service == "kafka_broker":
        return ["docker", "compose", "up", "-d", "kafka"]

    if service == "kafka_producer":
        command = [
            os.sys.executable,
            "-m",
            "src.streaming.kafka_producer",
            "--dataset",
            str(Path(parsed_args["dataset"]).resolve()),
            "--sleep-seconds",
            str(parsed_args["sleep_seconds"]),
        ]
        if parsed_args["reset_state"]:
            command.append("--reset-state")
        return command

    if service == "spark_job":
        job_args = []
        job_args.append("--debug-mode" if parsed_args["debug_mode"] else "--no-debug-mode")
        if parsed_args["run_seconds"] > 0:
            job_args.extend(["--run-seconds", str(parsed_args["run_seconds"])])
        if parsed_args["reset_checkpoint"]:
            job_args.append("--reset-checkpoint")
        job_args.append("--fail-on-data-loss" if parsed_args["fail_on_data_loss"] else "--no-fail-on-data-loss")

        if profile == "wsl" or profile == "default":
            wsl_root = _to_wsl_path(root)
            joined = " ".join(job_args)
            script = (
                f"cd '{wsl_root}' && "
                "source .venv/bin/activate && "
                "export PYSPARK_PYTHON=\"$(which python)\" && "
                "export PYSPARK_DRIVER_PYTHON=\"$(which python)\" && "
                f"python -m src.streaming.spark_job {joined}"
            )
            return ["wsl", "bash", "-lc", script]

        return [os.sys.executable, "-m", "src.streaming.spark_job", *job_args]

    if service == "orchestrator":
        return [
            os.sys.executable,
            "-m",
            "src.self_healing.orchestrator",
            "--interval-seconds",
            str(parsed_args["interval_seconds"]),
            "--required-consecutive-drifts",
            str(parsed_args["required_consecutive_drifts"]),
            "--cooldown-minutes",
            str(parsed_args["cooldown_minutes"]),
            "--stream-csv-path",
            str(Path(parsed_args["stream_csv_path"]).resolve()),
            "--recent-days",
            str(parsed_args["recent_days"]),
            "--min-relative-improvement",
            str(parsed_args["min_relative_improvement"]),
        ]

    raise HTTPException(status_code=404, detail="unknown service")


def _is_process_running(runtime: _ControlRuntime) -> bool:
    return runtime.process is not None and runtime.process.poll() is None


def _start_log_reader(runtime: _ControlRuntime) -> None:
    if runtime.process is None or runtime.process.stdout is None:
        return

    def _reader() -> None:
        assert runtime.process is not None and runtime.process.stdout is not None
        for line in runtime.process.stdout:
            runtime.logs.append(line.rstrip("\n"))
        exit_code = runtime.process.poll()
        runtime.last_exit_code = exit_code
        if runtime.status in {"starting", "running"}:
            runtime.status = "stopped" if exit_code == 0 else "failed"
            runtime.last_stopped_at = _to_iso_z(_utc_now())

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()


def create_app(project_root: Path | None = None) -> FastAPI:
    root = Path(project_root) if project_root else _project_root()

    metrics_path = root / "data" / "metrics" / "hourly_metrics"
    predictions_path = root / "data" / "predictions"
    drift_report_path = root / "artifacts" / "drift" / "drift_report.json"
    drift_history_path = root / "artifacts" / "drift" / "drift_history.jsonl"
    monitor_state_path = root / "artifacts" / "drift" / "drift_monitor_state.json"
    active_model_path = root / "artifacts" / "models" / "active_model.json"
    promotion_log_path = root / "artifacts" / "models" / "promotion_log.jsonl"
    candidate_report_path = root / "artifacts" / "models" / "candidate_report.json"
    trigger_decisions_path = root / "artifacts" / "self_healing" / "trigger_decisions.jsonl"

    app = FastAPI(title="Self-Healing ML API", version="1.0.0")

    # Enable CORS for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service_order = ["kafka_broker", "spark_job", "kafka_producer", "orchestrator"]
    managed_process = {
        "kafka_broker": False,
        "spark_job": True,
        "kafka_producer": True,
        "orchestrator": True,
    }
    runtimes: dict[str, _ControlRuntime] = {name: _ControlRuntime() for name in service_order}

    def _refresh_runtime(service: str) -> None:
        runtime = runtimes[service]
        if managed_process[service] and runtime.process is not None and runtime.process.poll() is not None:
            runtime.last_exit_code = runtime.process.poll()
            runtime.status = "stopped" if runtime.last_exit_code == 0 else "failed"
            runtime.last_stopped_at = _to_iso_z(_utc_now())

    def _broker_running() -> bool:
        try:
            completed = subprocess.run(
                ["docker", "ps", "--filter", "name=kafka", "--format", "{{.Names}}"],
                check=False,
                capture_output=True,
                text=True,
            )
            names = (completed.stdout or "").strip().splitlines()
            return completed.returncode == 0 and len(names) > 0
        except Exception:
            return False

    def _service_state(service: str) -> ControlServiceState:
        runtime = runtimes[service]
        _refresh_runtime(service)

        status = runtime.status
        if service == "kafka_broker":
            status = "running" if _broker_running() else ("failed" if runtime.last_error else "stopped")

        pid = runtime.process.pid if (runtime.process is not None and _is_process_running(runtime)) else None
        return ControlServiceState(
            service=service,
            status=status,
            allowed_actions=["start", "stop", "restart"],
            managed_process=managed_process[service],
            pid=pid,
            last_started_at=runtime.last_started_at,
            last_stopped_at=runtime.last_stopped_at,
            last_exit_code=runtime.last_exit_code,
            last_error=runtime.last_error,
        )

    @app.get("/api/v1/dashboard/summary", response_model=DashboardSummaryEnvelope)
    def dashboard_summary() -> dict[str, Any]:
        metrics_df, metrics_ok, metrics_error = _read_parquet_tree(metrics_path)
        drift_payload, drift_ok, drift_error = _read_json(drift_report_path)
        model_payload, model_ok, model_error = _read_json(active_model_path)

        latest_row = _extract_latest_metrics_row(metrics_df) if metrics_ok else None

        predicted = _safe_float(latest_row.get("mean_prediction")) if latest_row is not None else None
        abs_error = _safe_float(latest_row.get("mean_error")) if latest_row is not None else None
        actual = None
        if predicted is not None and abs_error is not None:
            actual = predicted + abs_error

        pct_error = None
        if actual not in (None, 0.0) and abs_error is not None:
            pct_error = (abs_error / abs(actual)) * 100.0

        drift_detected = bool(drift_payload.get("drift_detected", False)) if drift_ok else False
        active_model_version = (
            model_payload.get("active_model_version")
            if model_ok
            else (latest_row.get("active_model_version") if latest_row is not None else None)
        )

        latest_ts = _to_iso_z(latest_row.get("timestamp_hour")) if latest_row is not None else None

        data = {
            "latest_timestamp": latest_ts,
            "actual_mw": actual,
            "predicted_mw": predicted,
            "abs_error_mw": abs_error,
            "pct_error": pct_error,
            "drift_detected": drift_detected,
            "active_model_version": active_model_version,
            "health_level": _health_level(pct_error, drift_detected),
        }

        source_status = {
            "hourly_metrics": _source_status(metrics_path, root, metrics_ok, metrics_error),
            "drift_report": _source_status(drift_report_path, root, drift_ok, drift_error),
            "active_model": _source_status(active_model_path, root, model_ok, model_error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=5400,
            data_as_of=latest_ts,
        )

    @app.get("/api/v1/predictions", response_model=PredictionsEnvelope)
    def predictions(
        window: Literal["24h", "7d", "30d"] = Query("24h"),
        limit: int = Query(1000, ge=1, le=5000),
    ) -> dict[str, Any]:
        pred_df, pred_ok, pred_error = _read_parquet_tree(predictions_path)
        source_status: dict[str, dict[str, Any]] = {
            "predictions": _source_status(predictions_path, root, pred_ok, pred_error),
        }

        points: list[dict[str, Any]] = []
        data_as_of = None

        if pred_ok and {"timestamp", "actual_load", "predicted_load", "error"}.issubset(set(pred_df.columns)):
            frame = pred_df.copy()
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
            frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")

            if not frame.empty:
                cutoff = frame["timestamp"].max() - _window_delta(window)
                frame = frame[frame["timestamp"] >= cutoff]
                frame = frame.tail(limit)

                points = [
                    {
                        "timestamp": _to_iso_z(row["timestamp"]),
                        "actual_mw": _safe_float(row.get("actual_load")),
                        "predicted_mw": _safe_float(row.get("predicted_load")),
                        "abs_error_mw": _safe_float(row.get("error")),
                        "model_version": row.get("model_version"),
                    }
                    for _, row in frame.iterrows()
                ]
                data_as_of = _to_iso_z(frame["timestamp"].max())

        # Fallback to hourly metrics when row-level predictions are unavailable.
        if not points:
            metrics_df, metrics_ok, metrics_error = _read_parquet_tree(metrics_path)
            source_status["hourly_metrics"] = _source_status(metrics_path, root, metrics_ok, metrics_error)

            if metrics_ok and {"timestamp_hour", "mean_prediction", "mean_error"}.issubset(set(metrics_df.columns)):
                frame = metrics_df.copy()
                frame["timestamp_hour"] = pd.to_datetime(frame["timestamp_hour"], utc=True, errors="coerce")
                frame = frame.dropna(subset=["timestamp_hour"]).sort_values("timestamp_hour")
                if not frame.empty:
                    cutoff = frame["timestamp_hour"].max() - _window_delta(window)
                    frame = frame[frame["timestamp_hour"] >= cutoff]
                    frame = frame.tail(limit)
                    points = [
                        {
                            "timestamp": _to_iso_z(row["timestamp_hour"]),
                            "actual_mw": (
                                (_safe_float(row.get("mean_prediction")) or 0.0)
                                + (_safe_float(row.get("mean_error")) or 0.0)
                            ),
                            "predicted_mw": _safe_float(row.get("mean_prediction")),
                            "abs_error_mw": _safe_float(row.get("mean_error")),
                            "model_version": row.get("active_model_version"),
                        }
                        for _, row in frame.iterrows()
                    ]
                    data_as_of = _to_iso_z(frame["timestamp_hour"].max())
            elif "hourly_metrics" not in source_status:
                source_status["hourly_metrics"] = _source_status(metrics_path, root, False, "file_not_found")

        errors = [p["abs_error_mw"] for p in points if p.get("abs_error_mw") is not None]
        actuals = [p["actual_mw"] for p in points if p.get("actual_mw") not in (None, 0.0)]

        mae = float(pd.Series(errors).mean()) if errors else None
        rmse = float((pd.Series(errors).pow(2).mean() ** 0.5)) if errors else None

        mape_values = []
        for point in points:
            actual = point.get("actual_mw")
            err = point.get("abs_error_mw")
            if actual not in (None, 0.0) and err is not None:
                mape_values.append((float(err) / abs(float(actual))) * 100.0)
        mape = float(pd.Series(mape_values).mean()) if mape_values else None

        data = {
            "window": window,
            "points": points,
            "summary": {
                "count": len(points),
                "mae_mw": mae,
                "rmse_mw": rmse,
                "mape_pct": mape,
            },
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=5400,
            data_as_of=data_as_of,
        )

    @app.get("/api/v1/drift/current", response_model=DriftCurrentEnvelope)
    def drift_current() -> dict[str, Any]:
        drift_payload, drift_ok, drift_error = _read_json(drift_report_path)

        prediction_drift = drift_payload.get("prediction_drift") if drift_ok else {}
        performance_drift = drift_payload.get("performance_drift") if drift_ok else {}

        metrics = {
            "prediction_drift": {
                "detected": bool(prediction_drift.get("detected", False)) if isinstance(prediction_drift, dict) else False,
                "score": prediction_drift.get("score") if isinstance(prediction_drift, dict) else None,
                "threshold": prediction_drift.get("threshold") if isinstance(prediction_drift, dict) else None,
            },
            "performance_drift": {
                "detected": bool(performance_drift.get("detected", False)) if isinstance(performance_drift, dict) else bool(drift_payload.get("drift_detected", False)),
                "score": performance_drift.get("score") if isinstance(performance_drift, dict) else drift_payload.get("performance_drift_score"),
                "threshold": performance_drift.get("threshold") if isinstance(performance_drift, dict) else drift_payload.get("threshold"),
            },
        }

        feature_drift = drift_payload.get("feature_drift") if drift_ok else []
        if not isinstance(feature_drift, list):
            feature_drift = []

        detected_at = None
        if drift_ok:
            detected_at = (
                drift_payload.get("report_generated_at_utc")
                or drift_payload.get("checked_at_utc")
                or drift_payload.get("detected_at")
            )

        data = {
            "drift_available": drift_ok,
            "drift_detected": bool(drift_payload.get("drift_detected", False)) if drift_ok else False,
            "detected_at": _to_iso_z(detected_at),
            "metrics": metrics,
            "feature_drift": feature_drift,
        }

        source_status = {
            "drift_report": _source_status(drift_report_path, root, drift_ok, drift_error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=10800,
            data_as_of=_to_iso_z(detected_at),
        )

    @app.get("/api/v1/drift/history", response_model=DriftHistoryEnvelope)
    def drift_history(limit: int = Query(500, ge=1, le=5000)) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        ok = True
        error = None

        if not drift_history_path.exists():
            ok = False
            error = "file_not_found"
        else:
            try:
                with drift_history_path.open("r", encoding="utf-8") as fp:
                    for line in fp:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            payload = json.loads(line)
                        except Exception:
                            continue

                        ts = payload.get("checked_at_utc") or payload.get("decision_time_utc") or payload.get("timestamp")
                        event = {
                            "timestamp": _to_iso_z(ts),
                            "drift_detected": bool(payload.get("drift_detected", False)),
                            "prediction_drift_score": payload.get("prediction_drift_score"),
                            "performance_drift_score": payload.get("performance_drift_score"),
                        }
                        events.append(event)
            except Exception as exc:
                ok = False
                error = f"read_error: {exc}"

        events = [e for e in events if e.get("timestamp")]
        events = sorted(events, key=lambda item: item["timestamp"])
        events = events[-limit:]

        data_as_of = events[-1]["timestamp"] if events else None
        data = {
            "events": events,
            "count": len(events),
        }

        source_status = {
            "drift_history": _source_status(drift_history_path, root, ok, error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=10800,
            data_as_of=data_as_of,
        )

    @app.get("/api/v1/system/health", response_model=SystemHealthEnvelope)
    def system_health() -> dict[str, Any]:
        metrics_df, metrics_ok, metrics_error = _read_parquet_tree(metrics_path)
        drift_payload, drift_ok, drift_error = _read_json(drift_report_path)
        model_payload, model_ok, model_error = _read_json(active_model_path)

        latest_row = _extract_latest_metrics_row(metrics_df) if metrics_ok else None
        metrics_as_of = _to_iso_z(latest_row.get("timestamp_hour")) if latest_row is not None else None
        drift_as_of = _to_iso_z(drift_payload.get("report_generated_at_utc")) if drift_ok else None

        model_as_of = None
        if active_model_path.exists():
            model_as_of = _to_iso_z(datetime.fromtimestamp(active_model_path.stat().st_mtime, tz=timezone.utc))

        metrics_stale = _is_stale(metrics_as_of, 5400)
        drift_stale = _is_stale(drift_as_of, 10800)
        model_stale = _is_stale(model_as_of, 10800)

        metrics_component = {
            "status": "ok" if (metrics_ok and not metrics_stale) else "warning",
            "last_data_ts": metrics_as_of,
            "is_stale": metrics_stale,
            "message": None if metrics_ok else metrics_error,
        }

        drift_component = {
            "status": "ok" if (drift_ok and not drift_stale) else "warning",
            "last_data_ts": drift_as_of,
            "is_stale": drift_stale,
            "message": None if drift_ok else drift_error,
        }

        model_component = {
            "status": "ok" if (model_ok and not model_stale) else "warning",
            "last_data_ts": model_as_of,
            "is_stale": model_stale,
            "message": None if model_ok else model_error,
        }

        component_statuses = [
            metrics_component["status"],
            drift_component["status"],
            model_component["status"],
        ]

        if "critical" in component_statuses:
            overall = "critical"
        elif any(status != "ok" for status in component_statuses):
            overall = "degraded"
        else:
            overall = "ok"

        data = {
            "overall": overall,
            "components": {
                "hourly_metrics": metrics_component,
                "drift_artifacts": drift_component,
                "model_artifacts": model_component,
            },
        }

        data_as_of_candidates = [ts for ts in [metrics_as_of, drift_as_of, model_as_of] if ts]
        data_as_of = max(data_as_of_candidates) if data_as_of_candidates else None

        source_status = {
            "hourly_metrics": _source_status(metrics_path, root, metrics_ok, metrics_error),
            "drift_report": _source_status(drift_report_path, root, drift_ok, drift_error),
            "active_model": _source_status(active_model_path, root, model_ok, model_error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=300,
            data_as_of=data_as_of,
        )

    @app.get("/api/v1/models/active", response_model=ModelsActiveEnvelope)
    def models_active() -> dict[str, Any]:
        active_payload, active_ok, active_error = _read_json(active_model_path)

        data = {
            "active_model_version": active_payload.get("active_model_version"),
            "active_model_path": active_payload.get("active_model_path"),
            "previous_model_version": active_payload.get("previous_model_version"),
            "previous_model_path": active_payload.get("previous_model_path"),
            "promoted_at_utc": _to_iso_z(active_payload.get("promoted_at_utc")),
        }

        data_as_of = None
        if active_model_path.exists():
            data_as_of = _to_iso_z(datetime.fromtimestamp(active_model_path.stat().st_mtime, tz=timezone.utc))

        source_status = {
            "active_model": _source_status(active_model_path, root, active_ok, active_error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=10800,
            data_as_of=data_as_of,
        )

    @app.get("/api/v1/models/versions", response_model=ModelsVersionsEnvelope)
    def models_versions(limit: int = Query(500, ge=1, le=5000)) -> dict[str, Any]:
        active_payload, active_ok, active_error = _read_json(active_model_path)
        candidate_payload, candidate_ok, candidate_error = _read_json(candidate_report_path)
        promotion_rows, promotion_ok, promotion_error = _read_jsonl(promotion_log_path)

        events: list[dict[str, Any]] = []
        for row in promotion_rows:
            timestamp = row.get("event_time_utc") or row.get("event_timestamp") or row.get("timestamp")
            events.append(
                {
                    "timestamp": _to_iso_z(timestamp),
                    "event_type": row.get("event_type"),
                    "decision": row.get("decision"),
                    "reason": row.get("reason"),
                    "current_active_model_version": row.get("current_active_model_version"),
                    "target_model_version": row.get("target_model_version"),
                    "pointer_updated": row.get("pointer_updated"),
                }
            )

        events = [e for e in events if e.get("timestamp")]
        events = sorted(events, key=lambda item: item["timestamp"])
        events = events[-limit:]

        data_as_of_candidates = [e["timestamp"] for e in events if e.get("timestamp")]
        if active_model_path.exists():
            data_as_of_candidates.append(
                _to_iso_z(datetime.fromtimestamp(active_model_path.stat().st_mtime, tz=timezone.utc))
            )
        data_as_of = max([ts for ts in data_as_of_candidates if ts], default=None)

        data = {
            "active_model_version": active_payload.get("active_model_version"),
            "candidate_version": candidate_payload.get("candidate_version"),
            "candidate_ready_for_promotion": bool(candidate_payload.get("ready_for_promotion", False)),
            "events": events,
            "count": len(events),
        }

        source_status = {
            "promotion_log": _source_status(promotion_log_path, root, promotion_ok, promotion_error),
            "candidate_report": _source_status(candidate_report_path, root, candidate_ok, candidate_error),
            "active_model": _source_status(active_model_path, root, active_ok, active_error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=10800,
            data_as_of=data_as_of,
        )

    @app.get("/api/v1/self-healing/status", response_model=SelfHealingStatusEnvelope)
    def self_healing_status(limit: int = Query(500, ge=1, le=5000)) -> dict[str, Any]:
        trigger_rows, trigger_ok, trigger_error = _read_jsonl(trigger_decisions_path)
        candidate_payload, candidate_ok, candidate_error = _read_json(candidate_report_path)
        monitor_payload, monitor_ok, monitor_error = _read_json(monitor_state_path)

        decisions: list[dict[str, Any]] = []
        for row in trigger_rows:
            timestamp = row.get("decision_time_utc") or row.get("timestamp")
            decisions.append(
                {
                    "timestamp": _to_iso_z(timestamp),
                    "decision": row.get("decision"),
                    "reason": row.get("reason"),
                    "dry_run": row.get("dry_run"),
                    "command_ok": row.get("command_ok"),
                    "required_consecutive_drifts": row.get("required_consecutive_drifts"),
                }
            )

        decisions = [d for d in decisions if d.get("timestamp")]
        decisions = sorted(decisions, key=lambda item: item["timestamp"])
        decisions = decisions[-limit:]

        latest = decisions[-1] if decisions else {}
        data_as_of = latest.get("timestamp")

        data = {
            "latest_decision": latest.get("decision"),
            "latest_reason": latest.get("reason"),
            "candidate_ready_for_promotion": bool(candidate_payload.get("ready_for_promotion", False)),
            "consecutive_drift_count": monitor_payload.get("consecutive_drift_count") if monitor_ok else None,
            "required_consecutive_drifts": (
                latest.get("required_consecutive_drifts")
                if isinstance(latest, dict)
                else None
            ),
            "last_retrain_at_utc": _to_iso_z(monitor_payload.get("last_retrain_at_utc")) if monitor_ok else None,
            "decisions": decisions,
            "count": len(decisions),
        }

        source_status = {
            "trigger_decisions": _source_status(trigger_decisions_path, root, trigger_ok, trigger_error),
            "candidate_report": _source_status(candidate_report_path, root, candidate_ok, candidate_error),
            "monitor_state": _source_status(monitor_state_path, root, monitor_ok, monitor_error),
        }

        return _build_envelope(
            data=data,
            source_status=source_status,
            stale_after_seconds=600,
            data_as_of=data_as_of,
        )

    def _start_service(service: str, payload: ControlActionRequest) -> ControlServiceActionResponse:
        if service not in runtimes:
            raise HTTPException(status_code=404, detail="unknown service")

        runtime = runtimes[service]
        with runtime.lock:
            _refresh_runtime(service)
            if service != "kafka_broker" and _is_process_running(runtime):
                return ControlServiceActionResponse(
                    service=service,
                    action="start",
                    accepted=False,
                    dry_run=payload.dry_run,
                    status="running",
                    message="service already running",
                    pid=runtime.process.pid if runtime.process else None,
                )

            parsed_args = _parse_service_args(service, payload.args, root)
            command = _build_start_command(service, parsed_args, root, payload.profile)

            if payload.dry_run:
                return ControlServiceActionResponse(
                    service=service,
                    action="start",
                    accepted=True,
                    dry_run=True,
                    status=_service_state(service).status,
                    message="dry-run: command validated",
                    command=command,
                    pid=None,
                )

            runtime.last_error = None
            runtime.last_exit_code = None
            runtime.logs.append(f"[{_to_iso_z(_utc_now())}] START {service} request")

            if service == "kafka_broker":
                completed = subprocess.run(command, check=False, capture_output=True, text=True)
                output = (completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")
                if output.strip():
                    runtime.logs.extend(output.strip().splitlines()[-200:])
                if completed.returncode != 0:
                    runtime.status = "failed"
                    runtime.last_error = f"start failed with exit code {completed.returncode}"
                    runtime.last_exit_code = completed.returncode
                    return ControlServiceActionResponse(
                        service=service,
                        action="start",
                        accepted=False,
                        dry_run=False,
                        status="failed",
                        message=runtime.last_error,
                        command=command,
                    )

                runtime.status = "running" if _broker_running() else "starting"
                runtime.last_started_at = _to_iso_z(_utc_now())
                return ControlServiceActionResponse(
                    service=service,
                    action="start",
                    accepted=True,
                    dry_run=False,
                    status=_service_state(service).status,
                    message="broker start command executed",
                    command=command,
                )

            proc = subprocess.Popen(
                command,
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            runtime.process = proc
            runtime.status = "running"
            runtime.last_started_at = _to_iso_z(_utc_now())
            _start_log_reader(runtime)

            return ControlServiceActionResponse(
                service=service,
                action="start",
                accepted=True,
                dry_run=False,
                status="running",
                message="service started",
                command=command,
                pid=proc.pid,
            )

    def _stop_service(service: str, payload: ControlActionRequest) -> ControlServiceActionResponse:
        if service not in runtimes:
            raise HTTPException(status_code=404, detail="unknown service")

        runtime = runtimes[service]
        with runtime.lock:
            _refresh_runtime(service)

            if service == "kafka_broker":
                command = ["docker", "compose", "stop", "kafka"]
                if payload.dry_run:
                    return ControlServiceActionResponse(
                        service=service,
                        action="stop",
                        accepted=True,
                        dry_run=True,
                        status=_service_state(service).status,
                        message="dry-run: stop command validated",
                        command=command,
                    )

                completed = subprocess.run(command, check=False, capture_output=True, text=True)
                output = (completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")
                if output.strip():
                    runtime.logs.extend(output.strip().splitlines()[-200:])
                runtime.last_exit_code = completed.returncode
                runtime.last_stopped_at = _to_iso_z(_utc_now())
                if completed.returncode != 0:
                    runtime.status = "failed"
                    runtime.last_error = f"stop failed with exit code {completed.returncode}"
                    return ControlServiceActionResponse(
                        service=service,
                        action="stop",
                        accepted=False,
                        dry_run=False,
                        status="failed",
                        message=runtime.last_error,
                        command=command,
                    )

                runtime.status = "stopped"
                return ControlServiceActionResponse(
                    service=service,
                    action="stop",
                    accepted=True,
                    dry_run=False,
                    status="stopped",
                    message="broker stop command executed",
                    command=command,
                )

            if not _is_process_running(runtime):
                runtime.status = "stopped"
                return ControlServiceActionResponse(
                    service=service,
                    action="stop",
                    accepted=False,
                    dry_run=payload.dry_run,
                    status="stopped",
                    message="service already stopped",
                )

            if payload.dry_run:
                return ControlServiceActionResponse(
                    service=service,
                    action="stop",
                    accepted=True,
                    dry_run=True,
                    status="running",
                    message="dry-run: stop validated",
                    pid=runtime.process.pid if runtime.process else None,
                )

            assert runtime.process is not None
            runtime.status = "stopping"
            runtime.process.terminate()
            try:
                runtime.process.wait(timeout=15)
            except Exception:
                runtime.process.kill()
                runtime.process.wait(timeout=5)

            runtime.last_exit_code = runtime.process.returncode
            runtime.last_stopped_at = _to_iso_z(_utc_now())
            runtime.status = "stopped" if (runtime.process.returncode or 0) == 0 else "failed"

            return ControlServiceActionResponse(
                service=service,
                action="stop",
                accepted=True,
                dry_run=False,
                status=runtime.status,
                message="service stopped",
                pid=None,
            )

    @app.get("/api/v1/control/services", response_model=ControlServiceCatalog)
    def control_services(x_control_key: str | None = Header(default=None)) -> ControlServiceCatalog:
        _validate_control_key(x_control_key)
        return ControlServiceCatalog(services=[_service_state(name) for name in service_order])

    @app.get("/api/v1/control/services/{service}/status", response_model=ControlServiceState)
    def control_service_status(service: str, x_control_key: str | None = Header(default=None)) -> ControlServiceState:
        _validate_control_key(x_control_key)
        if service not in runtimes:
            raise HTTPException(status_code=404, detail="unknown service")
        return _service_state(service)

    @app.post("/api/v1/control/services/{service}/start", response_model=ControlServiceActionResponse)
    def control_start_service(
        service: str,
        payload: ControlActionRequest,
        x_control_key: str | None = Header(default=None),
    ) -> ControlServiceActionResponse:
        _validate_control_key(x_control_key)
        return _start_service(service, payload)

    @app.post("/api/v1/control/services/{service}/stop", response_model=ControlServiceActionResponse)
    def control_stop_service(
        service: str,
        payload: ControlActionRequest,
        x_control_key: str | None = Header(default=None),
    ) -> ControlServiceActionResponse:
        _validate_control_key(x_control_key)
        return _stop_service(service, payload)

    @app.post("/api/v1/control/services/{service}/restart", response_model=ControlServiceActionResponse)
    def control_restart_service(
        service: str,
        payload: ControlActionRequest,
        x_control_key: str | None = Header(default=None),
    ) -> ControlServiceActionResponse:
        _validate_control_key(x_control_key)
        stop_result = _stop_service(service, payload)
        if not stop_result.accepted and stop_result.message != "service already stopped":
            return stop_result
        return _start_service(service, payload)

    @app.get("/api/v1/control/services/{service}/logs", response_model=ControlServiceLogsResponse)
    def control_service_logs(
        service: str,
        tail: int = Query(200, ge=1, le=2000),
        x_control_key: str | None = Header(default=None),
    ) -> ControlServiceLogsResponse:
        _validate_control_key(x_control_key)
        if service not in runtimes:
            raise HTTPException(status_code=404, detail="unknown service")

        runtime = runtimes[service]
        lines = list(runtime.logs)[-tail:]
        return ControlServiceLogsResponse(service=service, lines=lines, line_count=len(lines))

    @app.post("/api/v1/control/pipeline/start", response_model=ControlPipelineResponse)
    def control_pipeline_start(
        payload: ControlActionRequest,
        x_control_key: str | None = Header(default=None),
    ) -> ControlPipelineResponse:
        _validate_control_key(x_control_key)
        steps: list[ControlServiceActionResponse] = []
        for service in service_order:
            if service == "kafka_broker":
                service_payload = payload
            elif service == "spark_job":
                service_payload = ControlActionRequest(
                    dry_run=payload.dry_run,
                    profile="wsl" if payload.profile == "default" else payload.profile,
                    args=payload.args,
                )
            else:
                service_payload = payload
            result = _start_service(service, service_payload)
            steps.append(result)
            if not result.accepted and not payload.dry_run:
                break
        return ControlPipelineResponse(action="start", dry_run=payload.dry_run, steps=steps)

    @app.post("/api/v1/control/pipeline/stop", response_model=ControlPipelineResponse)
    def control_pipeline_stop(
        payload: ControlActionRequest,
        x_control_key: str | None = Header(default=None),
    ) -> ControlPipelineResponse:
        _validate_control_key(x_control_key)
        steps: list[ControlServiceActionResponse] = []
        for service in reversed(service_order):
            result = _stop_service(service, payload)
            steps.append(result)
            if not result.accepted and not payload.dry_run and result.message not in {"service already stopped"}:
                break
        return ControlPipelineResponse(action="stop", dry_run=payload.dry_run, steps=steps)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
