from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.logging import get_logger

logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _registry_path() -> Path:
    return _project_root() / "artifacts" / "models" / "model_registry.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_registry_event(
    event_type: str,
    model_version: str | None,
    model_path: str | None,
    metadata: dict[str, Any] | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(registry_path) if registry_path else _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "event_time_utc": _utc_now_iso(),
        "event_type": event_type,
        "model_version": model_version,
        "model_path": model_path,
        "metadata": metadata or {},
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    logger.info(
        "model-registry-event-appended",
        extra={"event_type": event_type, "model_version": model_version, "registry_path": str(path)},
    )
    return event
