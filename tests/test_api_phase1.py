from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.mark.unit
def test_dashboard_summary_happy_path(tmp_path: Path):
    metrics_dir = tmp_path / "data" / "metrics" / "hourly_metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "timestamp_hour": pd.to_datetime(["2020-07-15T10:00:00Z", "2020-07-15T11:00:00Z"], utc=True),
            "active_model_version": ["v2", "v2"],
            "mean_prediction": [200000.0, 201000.0],
            "mean_error": [1000.0, 1200.0],
        }
    )
    df.to_parquet(metrics_dir / "part-0001.parquet", index=False)

    drift_dir = tmp_path / "artifacts" / "drift"
    drift_dir.mkdir(parents=True, exist_ok=True)
    (drift_dir / "drift_report.json").write_text(
        json.dumps(
            {
                "report_generated_at_utc": "2020-07-15T11:05:00Z",
                "drift_detected": False,
            }
        ),
        encoding="utf-8",
    )

    models_dir = tmp_path / "artifacts" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "active_model.json").write_text(
        json.dumps({"active_model_version": "v2"}),
        encoding="utf-8",
    )

    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["predicted_mw"] == 201000.0
    assert body["data"]["abs_error_mw"] == 1200.0
    assert body["data"]["active_model_version"] == "v2"
    assert body["source_status"]["hourly_metrics"]["ok"] is True


@pytest.mark.unit
def test_predictions_returns_empty_points_on_missing_metrics(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/predictions", params={"window": "24h", "limit": 100})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["points"] == []
    assert body["source_status"]["hourly_metrics"]["ok"] is False


@pytest.mark.unit
def test_drift_history_missing_file_is_soft_failure(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/drift/history", params={"limit": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["events"] == []
    assert body["source_status"]["drift_history"]["ok"] is False


@pytest.mark.unit
def test_system_health_reports_degraded_when_sources_missing(tmp_path: Path):
    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["overall"] in {"degraded", "critical"}
    assert "components" in body["data"]


@pytest.mark.unit
def test_system_health_reports_degraded_when_metrics_stale(tmp_path: Path):
    metrics_dir = tmp_path / "data" / "metrics" / "hourly_metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "timestamp_hour": pd.to_datetime(["2020-10-30T01:00:00Z"], utc=True),
            "active_model_version": ["v2"],
            "mean_prediction": [201000.0],
            "mean_error": [1200.0],
        }
    ).to_parquet(metrics_dir / "part-0001.parquet", index=False)

    drift_dir = tmp_path / "artifacts" / "drift"
    drift_dir.mkdir(parents=True, exist_ok=True)
    drift_now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    (drift_dir / "drift_report.json").write_text(
        json.dumps({"report_generated_at_utc": drift_now, "drift_detected": False}),
        encoding="utf-8",
    )

    models_dir = tmp_path / "artifacts" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "active_model.json").write_text(
        json.dumps({"active_model_version": "v2"}),
        encoding="utf-8",
    )

    client = TestClient(create_app(project_root=tmp_path))
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["overall"] == "degraded"
    assert body["data"]["components"]["hourly_metrics"]["is_stale"] is True
    assert body["data"]["components"]["hourly_metrics"]["status"] == "warning"
