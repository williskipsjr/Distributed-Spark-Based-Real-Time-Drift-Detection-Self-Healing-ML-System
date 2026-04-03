from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.drift_detection.drift_detector import _compute_drift_report
from src.self_healing.model_registry import append_registry_event
from src.self_healing.serving_reload import reload_serving


@pytest.mark.unit
def test_feature_drift_metrics_are_computed_when_features_present() -> None:
    base_ts = pd.date_range("2020-01-01", periods=48, freq="h", tz="UTC")
    recent_ts = pd.date_range("2020-01-03", periods=24, freq="h", tz="UTC")

    baseline_df = pd.DataFrame(
        {
            "timestamp_hour": base_ts,
            "mean_error": [1000.0] * 48,
            "mean_prediction": [180000.0] * 48,
            "std_prediction": [2000.0] * 48,
            "hour_of_day": [t.hour for t in base_ts],
            "lag_1": [180000.0 + i for i in range(48)],
        }
    )
    recent_df = pd.DataFrame(
        {
            "timestamp_hour": recent_ts,
            "mean_error": [2500.0] * 24,
            "mean_prediction": [220000.0] * 24,
            "std_prediction": [3000.0] * 24,
            "hour_of_day": [((t.hour + 5) % 24) for t in recent_ts],
            "lag_1": [220000.0 + i for i in range(24)],
        }
    )

    report = _compute_drift_report(
        baseline_df=baseline_df,
        recent_df=recent_df,
        reference_time=datetime.now(timezone.utc),
    )

    assert "feature_drift" in report
    assert "feature_drift_summary" in report
    assert report["feature_drift_summary"]["computed"] is True
    assert report["feature_drift_summary"]["feature_count"] >= 1


@pytest.mark.unit
def test_feature_drift_gracefully_skips_without_feature_columns() -> None:
    base_ts = pd.date_range("2020-01-01", periods=48, freq="h", tz="UTC")
    recent_ts = pd.date_range("2020-01-03", periods=24, freq="h", tz="UTC")

    baseline_df = pd.DataFrame(
        {
            "timestamp_hour": base_ts,
            "mean_error": [1000.0] * 48,
            "mean_prediction": [180000.0] * 48,
            "std_prediction": [2000.0] * 48,
        }
    )
    recent_df = pd.DataFrame(
        {
            "timestamp_hour": recent_ts,
            "mean_error": [1200.0] * 24,
            "mean_prediction": [181000.0] * 24,
            "std_prediction": [2100.0] * 24,
        }
    )

    report = _compute_drift_report(
        baseline_df=baseline_df,
        recent_df=recent_df,
        reference_time=datetime.now(timezone.utc),
    )

    assert report["feature_drift"] == []
    assert report["feature_drift_summary"]["computed"] is False


@pytest.mark.unit
def test_model_registry_append_event(tmp_path: Path) -> None:
    registry_path = tmp_path / "model_registry.jsonl"

    event = append_registry_event(
        event_type="candidate_trained",
        model_version="candidate_test",
        model_path="artifacts/models/candidates/model_candidate_test.joblib",
        metadata={"rows": 123},
        registry_path=registry_path,
    )

    assert registry_path.exists()
    lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event_type"] == "candidate_trained"
    assert payload["model_version"] == "candidate_test"
    assert event["event_type"] == "candidate_trained"


@pytest.mark.unit
def test_serving_reload_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from src.self_healing import serving_reload as module

    root = tmp_path
    (root / "artifacts" / "models").mkdir(parents=True, exist_ok=True)
    (root / "artifacts" / "models" / "active_model.json").write_text(
        json.dumps(
            {
                "active_model_version": "v2",
                "active_model_path": "artifacts/models/model_v2.joblib",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "_project_root", lambda: root)

    result = reload_serving(dry_run=True)
    assert result["ok"] is True
    assert result["output"] == "dry-run"

    state_path = root / "artifacts" / "models" / "serving_reload_state.json"
    assert state_path.exists()
