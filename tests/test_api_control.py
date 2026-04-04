from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.mark.unit
def test_control_services_list_available(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/control/services")

    assert response.status_code == 200
    body = response.json()
    names = {item["service"] for item in body["services"]}
    assert {"kafka_broker", "spark_job", "kafka_producer", "orchestrator"}.issubset(names)


@pytest.mark.unit
def test_control_start_spark_dry_run_includes_pyspark_exports(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.post(
        "/api/v1/control/services/spark_job/start",
        json={"dry_run": True, "profile": "wsl", "args": {"debug_mode": False}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["dry_run"] is True
    command = body["command"]
    assert command[0] == "wsl"
    assert "PYSPARK_PYTHON" in command[-1]
    assert "PYSPARK_DRIVER_PYTHON" in command[-1]


@pytest.mark.unit
def test_control_rejects_unsupported_args(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.post(
        "/api/v1/control/services/orchestrator/start",
        json={"dry_run": True, "args": {"evil": "rm -rf /"}},
    )

    assert response.status_code == 400
    assert "unsupported args" in response.json()["detail"]


@pytest.mark.unit
def test_control_api_key_guardrail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CONTROL_API_KEY", "secret-key")
    client = TestClient(create_app(project_root=tmp_path))

    denied = client.get("/api/v1/control/services")
    assert denied.status_code == 403

    allowed = client.get("/api/v1/control/services", headers={"x-control-key": "secret-key"})
    assert allowed.status_code == 200
