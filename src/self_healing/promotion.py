"""Promotion and rollback policy for self-healing model lifecycle.

Provides deterministic commands to:
- evaluate promotion gate
- promote candidate model by updating active model pointer
- rollback to previous production model
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import configure_logging, get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    reason: str
    checks: dict[str, Any]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _models_dir() -> Path:
    return _project_root() / "artifacts" / "models"


def _active_pointer_path() -> Path:
    return _models_dir() / "active_model.json"


def _promotion_log_path() -> Path:
    return _models_dir() / "promotion_log.jsonl"


def _candidate_report_path() -> Path:
    return _models_dir() / "candidate_report.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")


def _resolve_current_active_model(pointer: dict[str, Any]) -> tuple[str | None, str | None]:
    model_path = pointer.get("active_model_path")
    model_version = pointer.get("active_model_version")
    if isinstance(model_path, str) and model_path and Path(model_path).exists():
        return model_path, str(model_version) if model_version else None

    candidates = [p for p in _models_dir().glob("model_*.joblib") if p.is_file()]
    if not candidates:
        return None, None

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    latest = candidates[0]
    version = latest.stem.replace("model_", "")
    return str(latest), version


def evaluate_promotion_gate(
    candidate_report: dict[str, Any],
    min_relative_improvement: float,
    max_candidate_mae: float | None,
    require_rmse_non_regression: bool,
) -> PromotionDecision:
    # ----------------------------------------------------
    # -------------- Promotion Gate Evaluation -----------
    # Applies MAE/RMSE/threshold checks before pointer update.
    # ----------------------------------------------------
    if not candidate_report:
        return PromotionDecision(False, "candidate report missing", {"candidate_report_exists": False})

    candidate_model_path = candidate_report.get("candidate_model_path")
    if not isinstance(candidate_model_path, str) or not Path(candidate_model_path).exists():
        return PromotionDecision(
            False,
            "candidate model path missing or file does not exist",
            {"candidate_model_exists": False, "candidate_model_path": candidate_model_path},
        )

    current_metrics = candidate_report.get("current_metrics")
    candidate_metrics = candidate_report.get("candidate_metrics")
    if not isinstance(current_metrics, dict) or not isinstance(candidate_metrics, dict):
        return PromotionDecision(
            False,
            "candidate report missing current_metrics/candidate_metrics",
            {"metrics_present": False},
        )

    current_mae = current_metrics.get("mae")
    current_rmse = current_metrics.get("rmse")
    candidate_mae = candidate_metrics.get("mae")
    candidate_rmse = candidate_metrics.get("rmse")

    numeric = (int, float)
    if not all(isinstance(v, numeric) for v in (current_mae, current_rmse, candidate_mae, candidate_rmse)):
        return PromotionDecision(
            False,
            "non-numeric metrics in candidate report",
            {
                "current_mae": current_mae,
                "current_rmse": current_rmse,
                "candidate_mae": candidate_mae,
                "candidate_rmse": candidate_rmse,
            },
        )

    current_mae_f = float(current_mae)
    candidate_mae_f = float(candidate_mae)
    current_rmse_f = float(current_rmse)
    candidate_rmse_f = float(candidate_rmse)

    relative_improvement = (
        (current_mae_f - candidate_mae_f) / current_mae_f if current_mae_f > 0 else 0.0
    )

    checks = {
        "candidate_model_exists": True,
        "relative_improvement_mae": relative_improvement,
        "min_relative_improvement": min_relative_improvement,
        "mae_gate_pass": relative_improvement >= min_relative_improvement,
        "require_rmse_non_regression": require_rmse_non_regression,
        "rmse_gate_pass": (candidate_rmse_f <= current_rmse_f) if require_rmse_non_regression else True,
        "max_candidate_mae": max_candidate_mae,
        "max_mae_gate_pass": (candidate_mae_f <= max_candidate_mae) if max_candidate_mae is not None else True,
        "current_metrics": current_metrics,
        "candidate_metrics": candidate_metrics,
    }

    promote = bool(checks["mae_gate_pass"] and checks["rmse_gate_pass"] and checks["max_mae_gate_pass"])

    if promote:
        reason = "all promotion gates passed"
    else:
        failed = [k for k in ("mae_gate_pass", "rmse_gate_pass", "max_mae_gate_pass") if not checks[k]]
        reason = f"promotion denied: failed {', '.join(failed)}"

    return PromotionDecision(promote=promote, reason=reason, checks=checks)


def promote_candidate(
    dry_run: bool = True,
    min_relative_improvement: float = 0.02,
    max_candidate_mae: float | None = None,
    require_rmse_non_regression: bool = True,
) -> dict[str, Any]:
    # Executes promotion decision and updates active pointer when allowed.
    pointer_path = _active_pointer_path()
    log_path = _promotion_log_path()
    candidate_report_path = _candidate_report_path()

    pointer = _read_json(pointer_path)
    current_active_path, current_active_version = _resolve_current_active_model(pointer)

    candidate_report = _read_json(candidate_report_path)
    decision = evaluate_promotion_gate(
        candidate_report=candidate_report,
        min_relative_improvement=min_relative_improvement,
        max_candidate_mae=max_candidate_mae,
        require_rmse_non_regression=require_rmse_non_regression,
    )

    event = {
        "event_time_utc": _utc_now_iso(),
        "event_type": "promote",
        "dry_run": dry_run,
        "decision": "promote" if decision.promote else "no_action",
        "reason": decision.reason,
        "checks": decision.checks,
        "current_active_model_path": current_active_path,
        "current_active_model_version": current_active_version,
        "candidate_report_path": str(candidate_report_path),
    }

    if decision.promote:
        candidate_model_path = str(candidate_report.get("candidate_model_path"))
        candidate_version = str(candidate_report.get("candidate_version", Path(candidate_model_path).stem))
        event["target_model_path"] = candidate_model_path
        event["target_model_version"] = candidate_version

        if not dry_run:
            updated_pointer = {
                "active_model_path": candidate_model_path,
                "active_model_version": candidate_version,
                "previous_model_path": current_active_path,
                "previous_model_version": current_active_version,
                "promoted_at_utc": _utc_now_iso(),
                "promotion_reason": decision.reason,
                "promotion_checks": decision.checks,
            }
            _write_json(pointer_path, updated_pointer)
            event["pointer_updated"] = True
        else:
            event["pointer_updated"] = False
    else:
        event["pointer_updated"] = False

    _append_jsonl(log_path, event)

    logger.info(
        "promotion-decision",
        extra={
            "decision": event["decision"],
            "reason": event["reason"],
            "dry_run": dry_run,
            "pointer_updated": event["pointer_updated"],
        },
    )

    return event


def rollback_active_model(dry_run: bool = True) -> dict[str, Any]:
    # Restores previous active model pointer if rollback target exists.
    pointer_path = _active_pointer_path()
    log_path = _promotion_log_path()
    pointer = _read_json(pointer_path)

    active_path = pointer.get("active_model_path")
    active_version = pointer.get("active_model_version")
    previous_path = pointer.get("previous_model_path")
    previous_version = pointer.get("previous_model_version")

    if not previous_path or not Path(str(previous_path)).exists():
        event = {
            "event_time_utc": _utc_now_iso(),
            "event_type": "rollback",
            "dry_run": dry_run,
            "decision": "no_action",
            "reason": "no valid previous model available for rollback",
            "active_model_path": active_path,
            "previous_model_path": previous_path,
        }
        _append_jsonl(log_path, event)
        return event

    event = {
        "event_time_utc": _utc_now_iso(),
        "event_type": "rollback",
        "dry_run": dry_run,
        "decision": "rollback",
        "reason": "rolling back to previous model pointer",
        "active_model_path": active_path,
        "active_model_version": active_version,
        "rollback_target_model_path": previous_path,
        "rollback_target_model_version": previous_version,
    }

    if not dry_run:
        updated_pointer = {
            "active_model_path": str(previous_path),
            "active_model_version": previous_version,
            "previous_model_path": str(active_path) if active_path else None,
            "previous_model_version": active_version,
            "rolled_back_at_utc": _utc_now_iso(),
            "rollback_reason": "manual rollback command",
        }
        _write_json(pointer_path, updated_pointer)
        event["pointer_updated"] = True
    else:
        event["pointer_updated"] = False

    _append_jsonl(log_path, event)
    logger.info(
        "rollback-decision",
        extra={
            "decision": event["decision"],
            "dry_run": dry_run,
            "pointer_updated": event["pointer_updated"],
        },
    )
    return event


def show_status() -> dict[str, Any]:
    pointer = _read_json(_active_pointer_path())
    return {
        "active_pointer_path": str(_active_pointer_path()),
        "promotion_log_path": str(_promotion_log_path()),
        "pointer": pointer,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promotion and rollback policy manager")
    sub = parser.add_subparsers(dest="command", required=True)

    promote_cmd = sub.add_parser("promote", help="Evaluate promotion gate and optionally update active model pointer")
    promote_cmd.add_argument("--dry-run", action="store_true", help="Evaluate without updating pointer")
    promote_cmd.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Apply pointer update if promoted")
    promote_cmd.set_defaults(dry_run=True)
    promote_cmd.add_argument("--min-relative-improvement", type=float, default=0.02)
    promote_cmd.add_argument("--max-candidate-mae", type=float, default=None)
    promote_cmd.add_argument("--require-rmse-non-regression", action=argparse.BooleanOptionalAction, default=True)

    rollback_cmd = sub.add_parser("rollback", help="Rollback active model pointer to previous model")
    rollback_cmd.add_argument("--dry-run", action="store_true", help="Evaluate without updating pointer")
    rollback_cmd.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Apply rollback pointer update")
    rollback_cmd.set_defaults(dry_run=True)

    sub.add_parser("status", help="Show active model pointer and log paths")

    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    # CLI entrypoint for promote/rollback/status actions.
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=False)

    if args.command == "promote":
        result = promote_candidate(
            dry_run=args.dry_run,
            min_relative_improvement=args.min_relative_improvement,
            max_candidate_mae=args.max_candidate_mae,
            require_rmse_non_regression=args.require_rmse_non_regression,
        )
    elif args.command == "rollback":
        result = rollback_active_model(dry_run=args.dry_run)
    else:
        result = show_status()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
