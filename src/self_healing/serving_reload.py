from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import configure_logging, get_logger
from src.self_healing.model_registry import append_registry_event

logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _active_pointer_path() -> Path:
    return _project_root() / "artifacts" / "models" / "active_model.json"


def _reload_state_path() -> Path:
    return _project_root() / "artifacts" / "models" / "serving_reload_state.json"


def _reload_log_path() -> Path:
    return _project_root() / "artifacts" / "models" / "serving_reload_log.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")


def _default_reload_command() -> str:
    return (
        f'"{sys.executable}" -m src.streaming.spark_job --no-debug-mode '
        "--run-seconds 120 --reset-checkpoint"
    )


def reload_serving(
    reload_command: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    pointer = _read_json(_active_pointer_path())
    model_version = pointer.get("active_model_version")
    model_path = pointer.get("active_model_path")

    effective_command = reload_command or _default_reload_command()

    event = {
        "event_time_utc": _utc_now_iso(),
        "event_type": "serving_reload",
        "dry_run": dry_run,
        "reload_command": effective_command,
        "active_model_version": model_version,
        "active_model_path": model_path,
        "ok": None,
        "output": None,
    }

    if dry_run:
        event["ok"] = True
        event["output"] = "dry-run"
    else:
        completed = subprocess.run(
            effective_command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        output = (completed.stdout or "") + (("\n" + completed.stderr) if completed.stderr else "")
        event["ok"] = completed.returncode == 0
        event["output"] = output.strip()

    _append_jsonl(_reload_log_path(), event)
    _write_json(
        _reload_state_path(),
        {
            "last_reload_at_utc": event["event_time_utc"],
            "last_reload_ok": event["ok"],
            "active_model_version": model_version,
            "active_model_path": model_path,
            "reload_command": effective_command,
        },
    )

    append_registry_event(
        event_type="serving_reload",
        model_version=str(model_version) if model_version is not None else None,
        model_path=str(model_path) if model_path is not None else None,
        metadata={"dry_run": dry_run, "ok": event["ok"]},
    )

    logger.info(
        "serving-reload-complete",
        extra={"dry_run": dry_run, "ok": event["ok"], "model_version": model_version},
    )
    return event


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serving reload workflow for promoted models")
    parser.add_argument("--reload-command", default=None, help="Command to execute for serving reload")
    parser.add_argument("--dry-run", action="store_true", help="Log reload decision without command execution")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Execute reload command")
    parser.set_defaults(dry_run=True)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(level=args.log_level, json_logs=False)
    result = reload_serving(reload_command=args.reload_command, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
