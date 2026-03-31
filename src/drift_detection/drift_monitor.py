"""Periodic drift monitoring runner with retrain guardrails.

This module executes drift detection on a schedule, appends each check to a JSONL
history log, and applies policy controls to avoid model explosion:
- retrain only after N consecutive drift detections
- retrain only if cooldown has elapsed since the previous retrain

Usage examples:
    python -m src.drift_detection.drift_monitor
    python -m src.drift_detection.drift_monitor --interval-seconds 180
    python -m src.drift_detection.drift_monitor --max-runs 5
    python -m src.drift_detection.drift_monitor --trigger-retrain --retrain-command "python -m src.ml.train_baseline"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.common.logging import configure_logging, get_logger
from src.drift_detection.drift_detector import run_drift_detection


logger = get_logger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_iso_utc(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _load_state(state_path: Path) -> dict[str, Any]:
    # Loads monitor counters/state; returns defaults when missing/corrupt.
    if not state_path.exists():
        return {
            "consecutive_drift_count": 0,
            "last_retrain_at_utc": None,
            "last_check_at_utc": None,
            "total_checks": 0,
            "total_drift_checks": 0,
            "total_retrain_triggers": 0,
        }

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("State file is not a JSON object")
        return {
            "consecutive_drift_count": int(payload.get("consecutive_drift_count", 0)),
            "last_retrain_at_utc": payload.get("last_retrain_at_utc"),
            "last_check_at_utc": payload.get("last_check_at_utc"),
            "total_checks": int(payload.get("total_checks", 0)),
            "total_drift_checks": int(payload.get("total_drift_checks", 0)),
            "total_retrain_triggers": int(payload.get("total_retrain_triggers", 0)),
        }
    except Exception as exc:
        logger.warning("monitor-state-reset", extra={"error": str(exc), "path": str(state_path)})
        return {
            "consecutive_drift_count": 0,
            "last_retrain_at_utc": None,
            "last_check_at_utc": None,
            "total_checks": 0,
            "total_drift_checks": 0,
            "total_retrain_triggers": 0,
        }


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp_path.replace(state_path)


def _append_jsonl(history_path: Path, event: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(event) + "\n")


def _cooldown_elapsed(last_retrain_at_utc: str | None, cooldown_minutes: int) -> bool:
    if cooldown_minutes <= 0:
        return True

    last_retrain = _parse_iso_utc(last_retrain_at_utc)
    if last_retrain is None:
        return True

    return _utc_now() >= last_retrain + timedelta(minutes=cooldown_minutes)


def _run_retrain_command(command: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, shell=True, check=False, capture_output=True, text=True)
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        return completed.returncode == 0, output.strip()
    except Exception as exc:
        return False, str(exc)


def run_monitor(
    interval_seconds: int = 300,
    max_runs: int | None = None,
    required_consecutive_drifts: int = 3,
    cooldown_minutes: int = 180,
    trigger_retrain: bool = False,
    retrain_command: str | None = None,
    metrics_path: str | None = None,
    report_path: str | None = None,
    history_path: str | None = None,
    state_path: str | None = None,
) -> None:
    # ----------------------------------------------------
    # --------------- Periodic Monitor Loop --------------
    # Runs drift checks, applies guardrails, and records events.
    # ----------------------------------------------------
    root = _project_root()
    resolved_history = Path(history_path) if history_path else root / "artifacts" / "drift" / "drift_history.jsonl"
    resolved_state = Path(state_path) if state_path else root / "artifacts" / "drift" / "drift_monitor_state.json"

    state = _load_state(resolved_state)

    logger.info(
        "drift-monitor-started",
        extra={
            "interval_seconds": interval_seconds,
            "max_runs": max_runs,
            "required_consecutive_drifts": required_consecutive_drifts,
            "cooldown_minutes": cooldown_minutes,
            "trigger_retrain": trigger_retrain,
        },
    )

    runs = 0
    while True:
        check_at = _utc_now()
        action = "none"
        action_result = None
        error = None
        report: dict[str, Any] | None = None

        try:
            report = run_drift_detection(metrics_path=metrics_path, report_path=report_path)
            drift_detected = bool(report.get("drift_detected", False))

            state["total_checks"] = int(state.get("total_checks", 0)) + 1
            state["last_check_at_utc"] = check_at.isoformat()

            if drift_detected:
                state["consecutive_drift_count"] = int(state.get("consecutive_drift_count", 0)) + 1
                state["total_drift_checks"] = int(state.get("total_drift_checks", 0)) + 1
            else:
                state["consecutive_drift_count"] = 0

            consecutive = int(state.get("consecutive_drift_count", 0))
            threshold_reached = consecutive >= required_consecutive_drifts
            cooldown_ok = _cooldown_elapsed(state.get("last_retrain_at_utc"), cooldown_minutes)

            if drift_detected and threshold_reached and cooldown_ok:
                if trigger_retrain and retrain_command:
                    ok, output = _run_retrain_command(retrain_command)
                    action = "retrain-triggered"
                    action_result = {"ok": ok, "output": output}
                    if ok:
                        state["last_retrain_at_utc"] = _utc_now().isoformat()
                        state["total_retrain_triggers"] = int(state.get("total_retrain_triggers", 0)) + 1
                else:
                    action = "retrain-suggested"
                    action_result = {
                        "reason": "threshold-and-cooldown-met",
                        "note": "Set --trigger-retrain and --retrain-command to execute automatically",
                    }

            event = {
                "checked_at_utc": check_at.isoformat(),
                "drift_detected": drift_detected,
                "drift_type": report.get("drift_type") if report else None,
                "reference_time_utc": report.get("reference_time_utc") if report else None,
                "consecutive_drift_count": int(state.get("consecutive_drift_count", 0)),
                "required_consecutive_drifts": required_consecutive_drifts,
                "cooldown_minutes": cooldown_minutes,
                "last_retrain_at_utc": state.get("last_retrain_at_utc"),
                "action": action,
                "action_result": action_result,
            }
            _append_jsonl(resolved_history, event)
            _save_state(resolved_state, state)

            logger.info(
                "drift-monitor-check-complete",
                extra={
                    "drift_detected": drift_detected,
                    "consecutive_drift_count": int(state.get("consecutive_drift_count", 0)),
                    "action": action,
                },
            )

        except Exception as exc:
            error = str(exc)
            event = {
                "checked_at_utc": check_at.isoformat(),
                "error": error,
                "action": "check-failed",
            }
            _append_jsonl(resolved_history, event)
            _save_state(resolved_state, state)
            logger.error("drift-monitor-check-failed", extra={"error": error})

        runs += 1
        if max_runs is not None and runs >= max_runs:
            break

        time.sleep(max(1, interval_seconds))

    logger.info("drift-monitor-stopped", extra={"runs": runs})


def main() -> None:
    # CLI entrypoint for scheduled drift monitoring.
    parser = argparse.ArgumentParser(description="Run drift detection periodically with retrain guardrails")
    parser.add_argument("--interval-seconds", type=int, default=300, help="Seconds between checks")
    parser.add_argument("--max-runs", type=int, default=None, help="Stop after N checks (default: run forever)")
    parser.add_argument(
        "--required-consecutive-drifts",
        type=int,
        default=3,
        help="Require this many consecutive drift detections before retrain action",
    )
    parser.add_argument(
        "--cooldown-minutes",
        type=int,
        default=180,
        help="Minimum minutes between retrain triggers",
    )
    parser.add_argument(
        "--trigger-retrain",
        action="store_true",
        help="Execute retrain command when policy conditions are met",
    )
    parser.add_argument(
        "--retrain-command",
        default=None,
        help="Shell command to run for retraining (used with --trigger-retrain)",
    )
    parser.add_argument("--metrics-path", default=None, help="Optional metrics parquet directory")
    parser.add_argument("--report-path", default=None, help="Optional drift report output path")
    parser.add_argument("--history-path", default=None, help="Optional drift history JSONL path")
    parser.add_argument("--state-path", default=None, help="Optional monitor state JSON path")
    args = parser.parse_args()

    configure_logging(level="INFO", json_logs=False)
    run_monitor(
        interval_seconds=args.interval_seconds,
        max_runs=args.max_runs,
        required_consecutive_drifts=args.required_consecutive_drifts,
        cooldown_minutes=args.cooldown_minutes,
        trigger_retrain=args.trigger_retrain,
        retrain_command=args.retrain_command,
        metrics_path=args.metrics_path,
        report_path=args.report_path,
        history_path=args.history_path,
        state_path=args.state_path,
    )


if __name__ == "__main__":
    main()
