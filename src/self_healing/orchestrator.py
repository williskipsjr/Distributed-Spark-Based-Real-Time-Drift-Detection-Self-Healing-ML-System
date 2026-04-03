"""
Self-healing ML orchestrator: fully automated drift detection -> trigger decision -> retrain/promote flow.

This combines drift monitoring, trigger policy evaluation, and automated retrain/promotion
into a single unified command with no manual intervention required.

Usage:
    python -m src.self_healing.orchestrator \
        --interval-seconds 60 \
        --required-consecutive-drifts 3 \
        --cooldown-minutes 180 \
        --stream-csv-path data/stream_dataset/hrl_load_metered-2021.csv \
        --recent-days 30 \
        --min-relative-improvement 0.02
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import configure_logging, get_logger
from src.drift_detection.drift_monitor import _load_state, _save_state, _append_jsonl, _cooldown_elapsed, _utc_now
from src.drift_detection.drift_detector import run_drift_detection
from src.self_healing.trigger import evaluate_trigger
from src.self_healing.retrain_pipeline import run_retrain_pipeline
from src.self_healing.promotion import promote_candidate
from src.self_healing.serving_reload import reload_serving


logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_orchestrator(
    interval_seconds: int = 300,
    max_runs: int | None = None,
    required_consecutive_drifts: int = 3,
    cooldown_minutes: int = 180,
    stream_csv_path: str | None = None,
    recent_days: int = 30,
    current_model_path: str | None = None,
    min_relative_improvement: float = 0.02,
    metrics_path: str | None = None,
    report_path: str | None = None,
    history_path: str | None = None,
    state_path: str | None = None,
    decision_log_path: str | None = None,
    reload_serving_after_promotion: bool = False,
    serving_reload_command: str | None = None,
    serving_reload_dry_run: bool = True,
) -> None:
    """
    Run the full self-healing orchestration loop.
    
    Each iteration:
    1. Runs drift detection
    2. Evaluates trigger policy
    3. Executes retrain or promotion if policy allows
    4. Logs all decisions and outcomes
    """
    # ----------------------------------------------------
    # --------------- Unified Self-Heal Loop ------------
    # Drift check -> trigger policy -> retrain/promote action.
    # ----------------------------------------------------
    root = _project_root()
    resolved_history = Path(history_path) if history_path else root / "artifacts" / "drift" / "drift_history.jsonl"
    resolved_state = Path(state_path) if state_path else root / "artifacts" / "drift" / "drift_monitor_state.json"
    resolved_decision_log = (
        Path(decision_log_path) if decision_log_path else root / "artifacts" / "self_healing" / "trigger_decisions.jsonl"
    )

    state = _load_state(resolved_state)

    logger.info(
        "orchestrator-started",
        extra={
            "interval_seconds": interval_seconds,
            "max_runs": max_runs,
            "required_consecutive_drifts": required_consecutive_drifts,
            "cooldown_minutes": cooldown_minutes,
            "stream_csv_path": stream_csv_path,
            "recent_days": recent_days,
            "min_relative_improvement": min_relative_improvement,
            "reload_serving_after_promotion": reload_serving_after_promotion,
        },
    )

    runs = 0
    while True:
        check_at = _utc_now()
        drift_report: dict[str, Any] | None = None
        trigger_decision = "no_action"
        trigger_reason = "unknown"
        action_executed = None
        action_ok = None
        action_output = None
        error = None

        try:
            # Step 1: Drift Detection
            drift_report = run_drift_detection(metrics_path=metrics_path, report_path=report_path)
            drift_detected = bool(drift_report.get("drift_detected", False))

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

            # Step 2: Load trigger context
            candidate_report_path = root / "artifacts" / "models" / "candidate_report.json"
            candidate_report = {}
            if candidate_report_path.exists():
                try:
                    candidate_report = json.loads(candidate_report_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.warning(
                        "candidate-report-load-failed",
                        extra={"path": str(candidate_report_path), "error": str(exc)},
                    )

            # Step 3: Evaluate trigger policy
            trigger_decision, trigger_reason = evaluate_trigger(
                drift_report=drift_report,
                monitor_state=state,
                candidate_report=candidate_report,
                required_consecutive_drifts=required_consecutive_drifts,
                min_relative_improvement=min_relative_improvement,
            )

            # Step 4: Execute action (retrain or promote)
            if trigger_decision == "retrain_candidate" and threshold_reached and cooldown_ok:
                logger.info(
                    "orchestrator-retrain-triggered",
                    extra={"trigger_reason": trigger_reason, "consecutive": consecutive},
                )
                try:
                    retrain_report = run_retrain_pipeline(
                        stream_csv_path=stream_csv_path,
                        recent_days=recent_days,
                        current_model_path=current_model_path,
                        min_relative_improvement=min_relative_improvement,
                    )
                    action_executed = "retrain_pipeline"
                    action_ok = True
                    action_output = retrain_report
                    state["last_retrain_at_utc"] = _utc_now().isoformat()
                    state["total_retrain_triggers"] = int(state.get("total_retrain_triggers", 0)) + 1
                    logger.info(
                        "orchestrator-retrain-complete",
                        extra={
                            "candidate_version": retrain_report.get("candidate_version"),
                            "promotion_recommended": retrain_report.get("promotion_recommended"),
                        },
                    )
                except Exception as exc:
                    action_executed = "retrain_pipeline"
                    action_ok = False
                    action_output = {"error": str(exc)}
                    logger.error("orchestrator-retrain-failed", extra={"error": str(exc)})

            elif trigger_decision == "promote_candidate" and not drift_detected:
                logger.info(
                    "orchestrator-promote-triggered",
                    extra={"trigger_reason": trigger_reason},
                )
                try:
                    promotion_result = promote_candidate(
                        dry_run=False,
                        min_relative_improvement=min_relative_improvement,
                    )
                    action_executed = "promotion"
                    action_ok = promotion_result.get("decision") == "promote" if isinstance(promotion_result, dict) else False
                    action_output = promotion_result

                    if (
                        reload_serving_after_promotion
                        and isinstance(promotion_result, dict)
                        and promotion_result.get("decision") == "promote"
                        and promotion_result.get("pointer_updated")
                    ):
                        reload_result = reload_serving(
                            reload_command=serving_reload_command,
                            dry_run=serving_reload_dry_run,
                        )
                        action_output = {
                            "promotion": promotion_result,
                            "serving_reload": reload_result,
                        }
                        action_executed = "promotion+serving_reload"
                        action_ok = bool(reload_result.get("ok", False))

                    logger.info(
                        "orchestrator-promotion-complete",
                        extra={
                            "decision": promotion_result.get("decision"),
                            "reason": promotion_result.get("reason"),
                            "pointer_updated": promotion_result.get("pointer_updated"),
                        },
                    )
                except Exception as exc:
                    action_executed = "promotion"
                    action_ok = False
                    action_output = {"error": str(exc)}
                    logger.error("orchestrator-promotion-failed", extra={"error": str(exc)})

            # Step 5: Log decision and outcome
            event = {
                "decision_time_utc": check_at.isoformat(),
                "drift_detected": drift_detected,
                "drift_type": drift_report.get("drift_type") if drift_report else None,
                "consecutive_drift_count": consecutive,
                "required_consecutive_drifts": required_consecutive_drifts,
                "threshold_reached": threshold_reached,
                "cooldown_ok": cooldown_ok,
                "trigger_decision": trigger_decision,
                "trigger_reason": trigger_reason,
                "action_executed": action_executed,
                "action_ok": action_ok,
                "action_output_summary": (
                    action_output.get("candidate_version")
                    if isinstance(action_output, dict) and "candidate_version" in action_output
                    else ("success" if action_ok else "failed" if action_executed else "not_executed")
                ),
            }
            _append_jsonl(resolved_decision_log, event)
            _save_state(resolved_state, state)

            logger.info(
                "orchestrator-step-complete",
                extra={
                    "drift_detected": drift_detected,
                    "trigger_decision": trigger_decision,
                    "action_executed": action_executed,
                    "action_ok": action_ok,
                },
            )

        except Exception as exc:
            error = str(exc)
            event = {
                "decision_time_utc": check_at.isoformat(),
                "error": error,
                "action": "check-failed",
            }
            _append_jsonl(resolved_decision_log, event)
            _save_state(resolved_state, state)
            logger.error("orchestrator-step-failed", extra={"error": error})

        runs += 1
        if max_runs is not None and runs >= max_runs:
            break

        time.sleep(max(1, interval_seconds))

    logger.info("orchestrator-stopped", extra={"runs": runs})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Self-healing ML orchestrator: automated drift detection -> retrain/promote flow"
    )
    parser.add_argument("--interval-seconds", type=int, default=300, help="Seconds between orchestration cycles")
    parser.add_argument("--max-runs", type=int, default=None, help="Stop after N cycles (default: run forever)")
    parser.add_argument(
        "--required-consecutive-drifts",
        type=int,
        default=3,
        help="Consecutive drift detections required before retrain action",
    )
    parser.add_argument(
        "--cooldown-minutes",
        type=int,
        default=180,
        help="Minimum minutes between retraining actions",
    )
    parser.add_argument(
        "--stream-csv-path",
        default=None,
        help="Path to stream CSV for retraining window (e.g., data/stream_dataset/hrl_load_metered-2021.csv)",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=30,
        help="Number of recent days to include in retrain window",
    )
    parser.add_argument(
        "--current-model-path",
        default=None,
        help="Explicit current model path (default: latest in artifacts/models)",
    )
    parser.add_argument(
        "--min-relative-improvement",
        type=float,
        default=0.02,
        help="Minimum relative MAE improvement for promotion eligibility",
    )
    parser.add_argument("--metrics-path", default=None, help="Optional metrics parquet directory")
    parser.add_argument("--report-path", default=None, help="Optional drift report output path")
    parser.add_argument("--history-path", default=None, help="Optional drift history JSONL path")
    parser.add_argument("--state-path", default=None, help="Optional monitor state JSON path")
    parser.add_argument("--decision-log-path", default=None, help="Optional decision log JSONL path")
    parser.add_argument(
        "--reload-serving-after-promotion",
        action="store_true",
        help="Run serving reload workflow after successful promotion",
    )
    parser.add_argument(
        "--serving-reload-command",
        default=None,
        help="Explicit command for serving reload workflow",
    )
    parser.add_argument(
        "--serving-reload-dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Execute reload command in dry-run mode by default",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser


def main() -> None:
    # CLI entrypoint for automated self-healing orchestration.
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=False)
    run_orchestrator(
        interval_seconds=args.interval_seconds,
        max_runs=args.max_runs,
        required_consecutive_drifts=args.required_consecutive_drifts,
        cooldown_minutes=args.cooldown_minutes,
        stream_csv_path=args.stream_csv_path,
        recent_days=args.recent_days,
        current_model_path=args.current_model_path,
        min_relative_improvement=args.min_relative_improvement,
        metrics_path=args.metrics_path,
        report_path=args.report_path,
        history_path=args.history_path,
        state_path=args.state_path,
        decision_log_path=args.decision_log_path,
        reload_serving_after_promotion=args.reload_serving_after_promotion,
        serving_reload_command=args.serving_reload_command,
        serving_reload_dry_run=args.serving_reload_dry_run,
    )


if __name__ == "__main__":
    main()
