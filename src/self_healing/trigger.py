"""Self-healing trigger policy.

Reads drift outputs and emits one clear decision:
- no_action
- retrain_candidate
- promote_candidate

The decision is appended to a JSONL log with timestamp and reason.
Dry-run mode is supported to demo logic without running retrain/promote commands.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import configure_logging, get_logger


logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(event) + "\n")


def _normalize_trigger_log_schema(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    normalized: list[str] = []
    changed = False
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            normalized.append(text)
            continue

        if isinstance(payload, dict):
            ts = payload.get("timestamp") or payload.get("decision_time_utc") or payload.get("checked_at_utc")
            if ts is not None and "timestamp" not in payload:
                payload["timestamp"] = ts
                changed = True

            if "decision" not in payload:
                legacy_decision = payload.get("trigger_decision") or payload.get("action")
                if legacy_decision is not None:
                    payload["decision"] = legacy_decision
                    changed = True

            if "reason" not in payload:
                legacy_reason = payload.get("trigger_reason")
                if legacy_reason is not None:
                    payload["reason"] = legacy_reason
                    changed = True

            normalized.append(json.dumps(payload))
        else:
            normalized.append(text)

    if changed:
        path.write_text("\n".join(normalized) + "\n", encoding="utf-8")


def _candidate_is_promotion_ready(
    candidate_report: dict[str, Any],
    min_relative_improvement: float,
) -> tuple[bool, str]:
    if not candidate_report:
        return False, "candidate report missing"

    for explicit_flag in ("promotion_recommended", "ready_for_promotion", "candidate_better"):
        if bool(candidate_report.get(explicit_flag)):
            return True, f"{explicit_flag}=true"

    current_metrics = candidate_report.get("current_metrics")
    candidate_metrics = candidate_report.get("candidate_metrics")
    if isinstance(current_metrics, dict) and isinstance(candidate_metrics, dict):
        current_mae = current_metrics.get("mae")
        candidate_mae = candidate_metrics.get("mae")
        if isinstance(current_mae, (int, float)) and isinstance(candidate_mae, (int, float)) and current_mae > 0:
            relative_improvement = (float(current_mae) - float(candidate_mae)) / float(current_mae)
            if relative_improvement >= min_relative_improvement:
                return True, f"candidate MAE improved by {relative_improvement:.2%}"
            return False, f"candidate MAE improvement {relative_improvement:.2%} below threshold"

    return False, "candidate report has no recognized promotion signal"


def evaluate_trigger(
    drift_report: dict[str, Any] | None = None,
    monitor_state: dict[str, Any] | None = None,
    candidate_report: dict[str, Any] | None = None,
    required_consecutive_drifts: int = 2,
    min_relative_improvement: float = 0.02,
    consecutive_drift_count: int | None = None,
    days_since_last_promotion: int | None = None,
    candidate_report_exists: bool | None = None,
    candidate_report_content: dict[str, Any] | None = None,
    dry_run: bool | None = None,
) -> tuple[str, str] | dict[str, Any]:
    # ----------------------------------------------------
    # ---------------- Trigger Decision Block ------------
    # Produces one policy action from drift + candidate context.
    # ----------------------------------------------------
    legacy_call = (
        consecutive_drift_count is not None
        or days_since_last_promotion is not None
        or candidate_report_exists is not None
        or candidate_report_content is not None
    )

    if legacy_call:
        drift_report = {"drift_detected": int(consecutive_drift_count or 0) > 0}
        monitor_state = {"consecutive_drift_count": int(consecutive_drift_count or 0)}
        if candidate_report_exists is False:
            candidate_report = {}
        else:
            candidate_report = candidate_report_content or {}

    drift_report = drift_report or {}
    monitor_state = monitor_state or {}

    drift_detected = bool(drift_report.get("drift_detected", False))
    consecutive = int(monitor_state.get("consecutive_drift_count", 0))

    if drift_detected:
        if consecutive >= required_consecutive_drifts:
            decision = "retrain_candidate"
            reason = f"persistent drift detected ({consecutive} consecutive checks >= {required_consecutive_drifts})"
            return {"decision": decision, "reason": reason, "dry_run": bool(dry_run)} if legacy_call else (decision, reason)
        decision = "no_action"
        reason = f"drift detected but persistence threshold not met ({consecutive}/{required_consecutive_drifts})"
        return {"decision": decision, "reason": reason, "dry_run": bool(dry_run)} if legacy_call else (decision, reason)

    ready, reason = _candidate_is_promotion_ready(candidate_report or {}, min_relative_improvement)
    if ready:
        decision = "promote_candidate"
        msg = f"no active drift and candidate is promotion-ready ({reason})"
        return {"decision": decision, "reason": msg, "dry_run": bool(dry_run)} if legacy_call else (decision, msg)

    decision = "no_action"
    msg = f"model stable: no action; no active drift and no promotion-ready candidate ({reason})"
    return {"decision": decision, "reason": msg, "dry_run": bool(dry_run)} if legacy_call else (decision, msg)


def _run_command(command: str) -> tuple[bool, str]:
    completed = subprocess.run(command, shell=True, check=False, capture_output=True, text=True)
    output = (completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")
    return completed.returncode == 0, output.strip()


def _default_promote_command(min_relative_improvement: float) -> str:
    return (
        f'"{sys.executable}" -m src.self_healing.promotion promote --no-dry-run '
        f"--min-relative-improvement {min_relative_improvement}"
    )


def run_trigger(
    drift_report_path: str | None = None,
    monitor_state_path: str | None = None,
    candidate_report_path: str | None = None,
    decision_log_path: str | None = None,
    required_consecutive_drifts: int = 2,
    min_relative_improvement: float = 0.02,
    dry_run: bool = True,
    retrain_command: str | None = None,
    promote_command: str | None = None,
) -> dict[str, Any]:
    # Executes trigger evaluation and optionally runs retrain/promote command.
    root = _project_root()

    resolved_drift = Path(drift_report_path) if drift_report_path else root / "artifacts" / "drift" / "drift_report.json"
    resolved_state = Path(monitor_state_path) if monitor_state_path else root / "artifacts" / "drift" / "drift_monitor_state.json"
    resolved_candidate = Path(candidate_report_path) if candidate_report_path else root / "artifacts" / "models" / "candidate_report.json"
    resolved_log = Path(decision_log_path) if decision_log_path else root / "artifacts" / "self_healing" / "trigger_decisions.jsonl"

    drift_report = _read_json(resolved_drift)
    monitor_state = _read_json(resolved_state)
    candidate_report = _read_json(resolved_candidate)

    decision, reason = evaluate_trigger(
        drift_report=drift_report,
        monitor_state=monitor_state,
        candidate_report=candidate_report,
        required_consecutive_drifts=required_consecutive_drifts,
        min_relative_improvement=min_relative_improvement,
    )

    command_executed = None
    command_ok = None
    command_output = None

    if not dry_run:
        if decision == "retrain_candidate" and retrain_command:
            command_executed = retrain_command
            command_ok, command_output = _run_command(retrain_command)
        elif decision == "promote_candidate":
            effective_promote_command = promote_command or _default_promote_command(min_relative_improvement)
            command_executed = effective_promote_command
            command_ok, command_output = _run_command(effective_promote_command)

    event = {
        "decision_time_utc": _utc_now_iso(),
        "decision": decision,
        "reason": reason,
        "dry_run": dry_run,
        "required_consecutive_drifts": required_consecutive_drifts,
        "min_relative_improvement": min_relative_improvement,
        "drift_report_path": str(resolved_drift),
        "monitor_state_path": str(resolved_state),
        "candidate_report_path": str(resolved_candidate),
        "command_executed": command_executed,
        "command_ok": command_ok,
        "command_output": command_output,
    }
    _append_jsonl(resolved_log, event)

    logger.info(
        "self-healing-trigger-decision",
        extra={
            "decision": decision,
            "reason": reason,
            "dry_run": dry_run,
            "log_path": str(resolved_log),
        },
    )

    return event


def main() -> None:
    # CLI entrypoint for one-shot trigger evaluation.
    parser = argparse.ArgumentParser(description="Evaluate self-healing trigger policy")
    parser.add_argument("--drift-report-path", default=None, help="Path to drift_report.json")
    parser.add_argument("--monitor-state-path", default=None, help="Path to drift monitor state JSON")
    parser.add_argument("--candidate-report-path", default=None, help="Path to candidate comparison report JSON")
    parser.add_argument("--decision-log-path", default=None, help="Path to decision log JSONL")
    parser.add_argument(
        "--required-consecutive-drifts",
        type=int,
        default=2,
        help="Consecutive drift count required for retrain_candidate",
    )
    parser.add_argument(
        "--min-relative-improvement",
        type=float,
        default=0.02,
        help="Relative MAE improvement required for promote_candidate when explicit flag missing",
    )
    parser.add_argument("--dry-run", action="store_true", help="Evaluate and log decisions without running commands")
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Allow retrain/promote command execution when configured",
    )
    parser.set_defaults(dry_run=True)
    parser.add_argument("--retrain-command", default=None, help="Command for retrain_candidate action")
    parser.add_argument("--promote-command", default=None, help="Command for promote_candidate action")
    args = parser.parse_args()

    configure_logging(level="INFO", json_logs=False)
    event = run_trigger(
        drift_report_path=args.drift_report_path,
        monitor_state_path=args.monitor_state_path,
        candidate_report_path=args.candidate_report_path,
        decision_log_path=args.decision_log_path,
        required_consecutive_drifts=args.required_consecutive_drifts,
        min_relative_improvement=args.min_relative_improvement,
        dry_run=args.dry_run,
        retrain_command=args.retrain_command,
        promote_command=args.promote_command,
    )
    print(json.dumps(event, indent=2))


if __name__ == "__main__":
    main()


try:
    _normalize_trigger_log_schema(_project_root() / "artifacts" / "self_healing" / "trigger_decisions.jsonl")
except Exception:
    pass
