from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.mark.unit
def test_models_active_soft_failure_when_pointer_missing(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/models/active")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["active_model_version"] is None
    assert body["source_status"]["active_model"]["ok"] is False


@pytest.mark.unit
def test_models_versions_reads_promotion_timeline(tmp_path: Path):
    models_dir = tmp_path / "artifacts" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    (models_dir / "active_model.json").write_text(
        json.dumps(
            {
                "active_model_version": "v3",
                "active_model_path": "artifacts/models/model_v3.joblib",
            }
        ),
        encoding="utf-8",
    )

    (models_dir / "candidate_report.json").write_text(
        json.dumps(
            {
                "candidate_version": "v4",
                "ready_for_promotion": True,
            }
        ),
        encoding="utf-8",
    )

    promotion_log = models_dir / "promotion_log.jsonl"
    promotion_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_time_utc": "2026-04-04T10:00:00Z",
                        "event_type": "promote",
                        "decision": "promote",
                        "reason": "all promotion gates passed",
                        "current_active_model_version": "v2",
                        "target_model_version": "v3",
                        "pointer_updated": True,
                    }
                ),
                json.dumps(
                    {
                        "event_time_utc": "2026-04-04T11:00:00Z",
                        "event_type": "promote",
                        "decision": "no_action",
                        "reason": "candidate worse",
                        "current_active_model_version": "v3",
                        "target_model_version": "v4",
                        "pointer_updated": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/models/versions", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["active_model_version"] == "v3"
    assert body["data"]["candidate_version"] == "v4"
    assert body["data"]["candidate_ready_for_promotion"] is True
    assert body["data"]["count"] == 2
    assert body["data"]["events"][0]["timestamp"] == "2026-04-04T10:00:00Z"
    assert body["source_status"]["promotion_log"]["ok"] is True


@pytest.mark.unit
def test_self_healing_status_reads_decision_feed(tmp_path: Path):
    self_healing_dir = tmp_path / "artifacts" / "self_healing"
    self_healing_dir.mkdir(parents=True, exist_ok=True)
    (self_healing_dir / "trigger_decisions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "decision_time_utc": "2026-04-04T12:00:00Z",
                        "decision": "retrain_candidate",
                        "reason": "persistent drift",
                        "dry_run": False,
                        "command_ok": True,
                        "required_consecutive_drifts": 2,
                    }
                ),
                json.dumps(
                    {
                        "decision_time_utc": "2026-04-04T12:10:00Z",
                        "decision": "promote_candidate",
                        "reason": "candidate ready",
                        "dry_run": False,
                        "command_ok": True,
                        "required_consecutive_drifts": 2,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    models_dir = tmp_path / "artifacts" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "candidate_report.json").write_text(
        json.dumps({"ready_for_promotion": True}),
        encoding="utf-8",
    )

    drift_dir = tmp_path / "artifacts" / "drift"
    drift_dir.mkdir(parents=True, exist_ok=True)
    (drift_dir / "drift_monitor_state.json").write_text(
        json.dumps(
            {
                "consecutive_drift_count": 2,
                "last_retrain_at_utc": "2026-04-04T12:01:00Z",
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/self-healing/status", params={"limit": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["latest_decision"] == "promote_candidate"
    assert body["data"]["candidate_ready_for_promotion"] is True
    assert body["data"]["consecutive_drift_count"] == 2
    assert body["data"]["required_consecutive_drifts"] == 2
    assert body["data"]["count"] == 2
    assert body["source_status"]["trigger_decisions"]["ok"] is True
