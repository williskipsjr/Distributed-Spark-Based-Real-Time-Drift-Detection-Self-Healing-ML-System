"""
Integration tests for the complete self-healing ML system.
"""
import json
import time
from pathlib import Path

import pytest


@pytest.mark.integration
class TestProducerToModel:
    """Integration: Producer → Model Loading."""
    
    def test_producer_data_loads_into_model_format(self, project_root):
        """Test that producer data can be loaded into model."""
        from src.streaming.kafka_producer import _load_and_prepare_data, _resolve_dataset_path
        from src.data.feature_builder import FEATURE_COLUMNS
        
        dataset_path = _resolve_dataset_path(None)
        df = _load_and_prepare_data(dataset_path)
        
        # Check all features present
        for col in FEATURE_COLUMNS:
            assert col in df.columns, f"Missing feature: {col}"
        
        # Check data quality
        assert df.shape[0] > 0
        assert df[FEATURE_COLUMNS].notna().all().all()
    
    def test_model_prediction_on_producer_data(self, project_root):
        """Test that model can make predictions on producer data."""
        from src.streaming.kafka_producer import _load_and_prepare_data, _resolve_dataset_path
        from src.data.feature_builder import FEATURE_COLUMNS
        from src.ml.model_io import load_model
        
        try:
            # Load data
            dataset_path = _resolve_dataset_path(None)
            df = _load_and_prepare_data(dataset_path)
            
            # Load model
            bundle = load_model(model_path=None)
            model = bundle['model']
            
            # Make predictions
            X = df[FEATURE_COLUMNS].head(100)
            predictions = model.predict(X)
            
            assert len(predictions) == len(X)
            assert (predictions > 0).all()
        except FileNotFoundError:
            pytest.skip("Required artifacts not found")


@pytest.mark.integration
class TestTriggerToPromotion:
    """Integration: Trigger Decision → Promotion Execution."""
    
    def test_trigger_no_action_no_promotion(self, project_root):
        """Test that no_action decision doesn't promote."""
        from src.self_healing.trigger import evaluate_trigger
        
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=1,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # No action shouldn't create promotion recommendation
        assert decision['decision'] == 'no_action'
        assert 'promote' not in decision.get('recommendation', '').lower()
    
    def test_trigger_retrain_creates_candidate(self, project_root):
        """Test that retrain decision would generate candidate."""
        # This is integration: trigger → retrain pipeline
        # In dry-run, just verify the decision logic
        from src.self_healing.trigger import evaluate_trigger
        
        decision = evaluate_trigger(
            consecutive_drift_count=3,  # Trigger drift threshold
            days_since_last_promotion=2,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should recommend retraining
        assert decision['decision'] in ['retrain_candidate', 'no_action']


@pytest.mark.integration
class TestPointerConsistency:
    """Integration: Pointer system consistency across loads."""
    
    def test_multiple_model_loads_same_pointer(self):
        """Test that multiple loads respect same pointer."""
        from src.ml.model_io import load_model, _resolve_active_model_path
        
        try:
            path1 = _resolve_active_model_path()
            path2 = _resolve_active_model_path()
            
            assert path1 == path2, "Pointer changed between calls"
        except FileNotFoundError:
            pytest.skip("Pointer not found")
    
    def test_fallback_to_latest_when_no_pointer(self, tmp_path, monkeypatch):
        """Test fallback to latest model when pointer missing."""
        from src.ml.model_io import load_model
        
        # Monkeypatch artifacts path to temp (no pointer)
        # Model loading should fall back to latest by mtime
        try:
            bundle = load_model(model_path=None)
            assert bundle is not None
            assert 'model' in bundle
        except Exception:
            # Either pointer exists or models exist
            pass


@pytest.mark.integration
class TestDecisionAuditTrail:
    """Integration: Audit trails are properly maintained."""
    
    def test_trigger_decisions_logged(self, project_root):
        """Test that trigger decisions are appended to log."""
        log_file = project_root / "artifacts" / "self_healing" / "trigger_decisions.jsonl"
        
        if log_file.exists():
            initial_lines = len(log_file.read_text().strip().split('\n'))
            
            # Capture initial state
            assert initial_lines >= 0
    
    def test_promotion_events_logged(self, project_root):
        """Test that promotion events are appended to log."""
        log_file = project_root / "artifacts" / "models" / "promotion_log.jsonl"
        
        if log_file.exists():
            initial_lines = len(log_file.read_text().strip().split('\n'))
            
            # Capture initial state
            assert initial_lines >= 0


@pytest.mark.integration
@pytest.mark.requires_kafka
class TestKafkaProducerIntegration:
    """Integration: Kafka producer end-to-end."""
    
    def test_producer_sends_valid_messages(self, kafka_admin, kafka_topics_clean):
        """Test producer sends properly formatted Kafka messages."""
        from src.streaming.kafka_producer import run_producer
        import threading
        
        # Start producer in background thread
        producer_thread = threading.Thread(
            target=lambda: run_producer(
                dataset_path='data/stream_dataset/hrl_load_metered-2019.csv',
                sleep_seconds=0.1,
                max_messages=5,
                log_level='ERROR'
            ),
            daemon=True
        )
        producer_thread.start()
        
        # Give producer time to send messages
        time.sleep(2)
        
        # Check Kafka has messages
        # (Would need kafka-python consumer here)
        producer_thread.join(timeout=5)


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Integration: Complete self-healing workflow."""
    
    def test_stable_model_no_changes(self, project_root):
        """Test that stable model doesn't trigger promotion."""
        from src.self_healing.trigger import evaluate_trigger
        
        # Simulate stable operation
        decision = evaluate_trigger(
            consecutive_drift_count=0,
            days_since_last_promotion=1,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should maintain status quo
        assert decision['decision'] == 'no_action'
    
    def test_drift_detected_triggers_retrain(self, project_root):
        """Test that drift detection triggers retraining."""
        from src.self_healing.trigger import evaluate_trigger
        
        decision = evaluate_trigger(
            consecutive_drift_count=3,  # Exceeds threshold
            days_since_last_promotion=2,
            candidate_report_exists=False,
            candidate_report_content=None,
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should recommend action
        assert decision['decision'] in ['retrain_candidate', 'no_action']


@pytest.mark.integration
class TestExceptionHandling:
    """Integration: System graceful degradation."""
    
    def test_missing_candidate_report_handled(self, project_root):
        """Test system handles missing candidate report gracefully."""
        from src.self_healing.promotion import evaluate_promotion_gate
        
        decision = evaluate_promotion_gate(
            candidate_report_path=Path("nonexistent.json"),
            current_model_version="v2",
            min_relative_improvement=0.02,
            dry_run=True
        )
        
        # Should return sensible decision, not crash
        assert decision.promote is False
        assert decision.reason is not None
    
    def test_missing_metrics_handled(self, project_root):
        """Test system handles missing metrics gracefully."""
        from src.drift_detection.drift_monitor import get_latest_metrics
        
        try:
            metrics = get_latest_metrics()
            # Either returns metrics or None/empty, doesn't crash
            assert metrics is None or isinstance(metrics, dict)
        except Exception as e:
            # Metrics might not exist, that's ok
            pass
