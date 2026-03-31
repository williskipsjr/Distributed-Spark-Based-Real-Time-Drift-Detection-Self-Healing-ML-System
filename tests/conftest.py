"""
pytest configuration and shared fixtures for the self-healing ML system.
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest
import pandas as pd
from kafka.admin import KafkaAdminClient, NewTopic


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def temp_artifacts_dir(tmp_path):
    """Create a temporary artifacts directory for test isolation."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (artifacts_dir / "models").mkdir(exist_ok=True)
    (artifacts_dir / "models" / "candidates").mkdir(exist_ok=True)
    (artifacts_dir / "models" / "baselines").mkdir(exist_ok=True)
    (artifacts_dir / "self_healing").mkdir(exist_ok=True)
    (artifacts_dir / "metrics").mkdir(exist_ok=True)
    (artifacts_dir / "drift").mkdir(exist_ok=True)
    
    yield artifacts_dir


@pytest.fixture
def kafka_admin():
    """Create Kafka admin client for test setup/teardown."""
    try:
        admin = KafkaAdminClient(bootstrap_servers='localhost:9092', request_timeout_ms=1000)
        yield admin
        admin.close()
    except Exception as e:
        pytest.skip(f"Kafka not available: {e}")


@pytest.fixture
def kafka_topics_clean(kafka_admin):
    """Ensure Kafka topics exist and are clean for tests."""
    topics = ['pjm.load', 'pjm.metrics', 'pjm.drift']
    
    try:
        existing = kafka_admin.list_topics()
        to_create = [
            NewTopic(name=t, num_partitions=1, replication_factor=1)
            for t in topics if t not in existing
        ]
        if to_create:
            kafka_admin.create_topics(new_topics=to_create, validate_only=False)
    except Exception as e:
        pytest.skip(f"Cannot setup Kafka topics: {e}")
    
    yield
    
    # Optional: cleanup if needed
    # try:
    #     kafka_admin.delete_topics(topics=topics)
    # except:
    #     pass


@pytest.fixture
def sample_features_df():
    """Create a sample features DataFrame matching model expectations."""
    return pd.DataFrame({
        'hour_of_day': [0, 1, 2, 3, 4, 5],
        'day_of_week': [0, 0, 0, 0, 0, 0],
        'month': [1, 1, 1, 1, 1, 1],
        'is_weekend': [0, 0, 0, 0, 0, 0],
        'lag_1': [183000, 182500, 181000, 180500, 179000, 178500],
        'lag_24': [185000, 184000, 183000, 182000, 181000, 180000],
        'lag_168': [180000, 180000, 180000, 180000, 180000, 180000],
        'rolling_24': [182000, 182500, 181500, 181000, 180000, 179000],
        'rolling_168': [181000, 181000, 181000, 181000, 181000, 181000],
    })


@pytest.fixture
def sample_kafka_message():
    """Create a sample Kafka message matching producer output."""
    return {
        'load_mw': 182345.67,
        'timestamp': '2026-03-31T12:00:00Z',
        'features': {
            'hour_of_day': 12,
            'day_of_week': 2,
            'month': 3,
            'is_weekend': 0,
            'lag_1': 181900.0,
            'lag_24': 182100.0,
            'lag_168': 181500.0,
            'rolling_24': 182000.0,
            'rolling_168': 181800.0,
        },
        'model_version': 'v2'
    }


@pytest.fixture
def sample_metrics_row():
    """Create a sample metrics aggregation row."""
    return {
        'window_start': '2026-03-31T00:00:00Z',
        'window_end': '2026-03-31T01:00:00Z',
        'mae': 2345.67,
        'rmse': 3456.78,
        'r_squared': 0.85,
        'sample_count': 60,
        'active_model_version': 'v2',
        'model_predictions_mean': 182000.0,
        'model_predictions_std': 5000.0,
    }


@pytest.fixture
def sample_trigger_decision():
    """Create a sample trigger decision output."""
    return {
        'timestamp': '2026-03-31T12:00:00Z',
        'decision': 'no_action',
        'reason': 'model performing well, no action needed',
        'recommendation': None,
        'checks': {
            'consecutive_drift_count': 0,
            'last_promotion_age_hours': 48,
            'model_performance_ok': True,
        }
    }


@pytest.fixture
def sample_promotion_decision():
    """Create a sample promotion gate decision."""
    return {
        'timestamp': '2026-03-31T12:00:00Z',
        'decision': 'promote',
        'reason': 'all promotion gates passed',
        'checks': {
            'mae_gate_pass': True,
            'rmse_gate_pass': True,
            'max_mae_gate_pass': True,
            'model_exists': True,
        },
        'target_model_version': 'candidate_20260331T120000Z'
    }


@pytest.fixture
def monkeypatch_artifacts_dir(monkeypatch, temp_artifacts_dir, project_root):
    """Monkeypatch ARTIFACTS_DIR constant in all modules."""
    # This helps tests use temp artifacts instead of real ones
    import sys
    
    # Patch the path in modules if they import it
    for module_name, module in sys.modules.items():
        if 'src.' in module_name and hasattr(module, 'ARTIFACTS_DIR'):
            monkeypatch.setattr(module, 'ARTIFACTS_DIR', temp_artifacts_dir)
    
    return temp_artifacts_dir


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "requires_kafka: mark test as requiring Kafka"
    )
    config.addinivalue_line(
        "markers", "requires_spark: mark test as requiring Spark"
    )
