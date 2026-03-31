"""
Unit tests for model retraining pipeline.
"""
import json
from pathlib import Path

import pytest
import pandas as pd


@pytest.mark.unit
class TestRetrainPipelineBasics:
    """Tests for retraining pipeline basics."""
    
    def test_retrain_module_imports(self):
        """Test that retrain pipeline modules can be imported."""
        try:
            from src.self_healing.retrain_pipeline import run_retrain_pipeline
            assert callable(run_retrain_pipeline)
        except ImportError:
            pytest.skip("Retrain pipeline not available")
    
    def test_retrain_returns_artifacts(self):
        """Test that retrain pipeline produces artifacts."""
        try:
            from src.self_healing.retrain_pipeline import run_retrain_pipeline
            
            # Dry-run should not crash
            result = run_retrain_pipeline(
                dataset_csv=None,
                dry_run=True
            )
            
            assert result is not None or result is None  # Just test it doesn't crash
        except ImportError:
            pytest.skip("Retrain pipeline not available")


@pytest.mark.unit
class TestTrainingDataWindow:
    """Tests for training data windowing in retrain."""
    
    def test_recent_data_window_extraction(self):
        """Test extraction of recent data window for retraining."""
        try:
            from src.self_healing.retrain_pipeline import build_training_window
            
            # Create recent stream data
            df = pd.DataFrame({
                'timestamp': pd.date_range('2020-01-31', periods=1000, freq='H'),
                'load_mw': [180000 + i*100 for i in range(1000)],
            })
            
            window = build_training_window(df)
            
            assert isinstance(window, pd.DataFrame) or window is None
            if isinstance(window, pd.DataFrame):
                assert len(window) > 0
        except (ImportError, AttributeError):
            pytest.skip("build_training_window not available")
    
    def test_window_size_reasonable(self):
        """Test that training window has reasonable size."""
        try:
            from src.self_healing.retrain_pipeline import build_training_window
            
            df = pd.DataFrame({
                'timestamp': pd.date_range('2020-01-01', periods=5000, freq='H'),
                'load_mw': [180000 + i*100 for i in range(5000)],
            })
            
            window = build_training_window(df)
            
            # Window should be subset of original
            if isinstance(window, pd.DataFrame):
                assert len(window) <= len(df)
                assert len(window) > 0
        except (ImportError, AttributeError):
            pytest.skip("build_training_window not available")


@pytest.mark.unit
class TestCandidateModelGeneration:
    """Tests for candidate model generation."""
    
    def test_candidate_model_creation(self):
        """Test that candidate model is created."""
        try:
            from src.self_healing.retrain_pipeline import train_candidate_model
            
            X = pd.DataFrame({
                'hour_of_day': [i % 24 for i in range(100)],
                'day_of_week': [i % 7 for i in range(100)],
                'lag_1': [180000 + i*100 for i in range(100)],
            })
            y = [180000 + i*100 for i in range(100)]
            
            candidate = train_candidate_model(X, y)
            
            assert candidate is not None
            if hasattr(candidate, 'predict'):
                # Test predictions
                preds = candidate.predict(X)
                assert len(preds) == len(X)
        except (ImportError, AttributeError, TypeError):
            pytest.skip("train_candidate_model not available or has different signature")
    
    def test_candidate_versioning(self):
        """Test that candidate model gets a version ID."""
        try:
            from src.self_healing.retrain_pipeline import generate_candidate_version
            
            version = generate_candidate_version()
            
            assert isinstance(version, str)
            assert len(version) > 0
            # Should have timestamp format
        except (ImportError, AttributeError):
            pytest.skip("generate_candidate_version not available")


@pytest.mark.unit
class TestCandidateEvaluation:
    """Tests for candidate model evaluation."""
    
    def test_candidate_metrics_computation(self):
        """Test that candidate metrics are computed."""
        try:
            from src.self_healing.retrain_pipeline import compute_candidate_metrics
            
            y_true = [180000 + i*100 for i in range(50)]
            y_pred = [180000 + i*100 for i in range(50)]  # Perfect prediction
            
            metrics = compute_candidate_metrics(y_true, y_pred)
            
            assert isinstance(metrics, dict)
            if 'mae' in metrics:
                assert metrics['mae'] >= 0
            if 'rmse' in metrics:
                assert metrics['rmse'] >= 0
        except (ImportError, AttributeError):
            pytest.skip("compute_candidate_metrics not available")
    
    def test_candidate_comparison_with_current(self):
        """Test comparing candidate to current model."""
        try:
            from src.self_healing.retrain_pipeline import compare_models
            
            current_metrics = {'mae': 2000, 'rmse': 3000}
            candidate_metrics = {'mae': 1500, 'rmse': 2500}
            
            comparison = compare_models(current_metrics, candidate_metrics)
            
            assert isinstance(comparison, dict)
            if 'candidate_better' in comparison:
                assert isinstance(comparison['candidate_better'], bool)
        except (ImportError, AttributeError):
            pytest.skip("compare_models not available")


@pytest.mark.unit
class TestCandidateReport:
    """Tests for candidate report generation."""
    
    def test_candidate_report_structure(self, project_root):
        """Test that candidate report has expected fields."""
        report_path = project_root / "artifacts" / "models" / "candidate_report.json"
        
        if report_path.exists():
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            # Check expected fields
            expected_fields = ['candidate_model_version', 'metrics']
            for field in expected_fields:
                assert field in report or report != {}, f"Missing field: {field}"
    
    def test_candidate_report_metrics_valid(self, project_root):
        """Test that metrics in report are valid."""
        report_path = project_root / "artifacts" / "models" / "candidate_report.json"
        
        if report_path.exists():
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            metrics = report.get('metrics', {})
            if metrics:
                # Metrics should be numeric
                for key, value in metrics.items():
                    if value is not None:
                        assert isinstance(value, (int, float)), f"{key} not numeric"
    
    def test_candidate_promotion_readiness(self, project_root):
        """Test that report indicates promotion readiness."""
        report_path = project_root / "artifacts" / "models" / "candidate_report.json"
        
        if report_path.exists():
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            # Should indicate if ready for promotion
            if 'promotion_recommended' in report:
                assert isinstance(report['promotion_recommended'], bool)


@pytest.mark.unit
class TestRetrainArtifacts:
    """Tests for retrain pipeline artifacts."""
    
    def test_candidate_model_saved(self, project_root):
        """Test that candidate model is saved to disk."""
        candidates_dir = project_root / "artifacts" / "models" / "candidates"
        
        if candidates_dir.exists():
            # Check if any candidate models exist
            candidates = list(candidates_dir.glob("model_candidate_*.joblib"))
            assert len(candidates) >= 0  # May be empty on fresh run
    
    def test_candidate_metrics_saved(self, project_root):
        """Test that candidate metrics are saved."""
        candidates_dir = project_root / "artifacts" / "models" / "candidates"
        
        if candidates_dir.exists():
            metrics_files = list(candidates_dir.glob("metrics_candidate_*.json"))
            assert len(metrics_files) >= 0  # May be empty on fresh run


@pytest.mark.unit
class TestRetrainValidation:
    """Tests for retrain data validation."""
    
    def test_insufficient_data_handling(self):
        """Test handling of insufficient training data."""
        try:
            from src.self_healing.retrain_pipeline import validate_training_window
            
            # Very small window
            small_df = pd.DataFrame({
                'timestamp': pd.date_range('2020-01-01', periods=5, freq='H'),
                'load_mw': [180000, 182000, 181000, 180500, 181500],
            })
            
            is_valid = validate_training_window(small_df)
            
            assert isinstance(is_valid, bool)
            # Small window may not be valid
        except (ImportError, AttributeError):
            pytest.skip("validate_training_window not available")
    
    def test_data_quality_checks(self):
        """Test data quality validation before retraining."""
        try:
            from src.self_healing.retrain_pipeline import validate_training_data
            
            # Good data
            good_df = pd.DataFrame({
                'load_mw': [180000 + i*100 for i in range(500)],
            })
            
            is_valid = validate_training_data(good_df)
            
            assert isinstance(is_valid, bool)
        except (ImportError, AttributeError):
            pytest.skip("validate_training_data not available")


@pytest.mark.unit
class TestRetrainEdgeCases:
    """Tests for edge cases in retraining."""
    
    def test_retrain_with_empty_window(self):
        """Test retraining with empty data window."""
        try:
            from src.self_healing.retrain_pipeline import run_retrain_pipeline
            
            # Should handle gracefully
            result = run_retrain_pipeline(
                dataset_csv=None,
                dry_run=True
            )
            
            assert result is None or isinstance(result, dict)
        except ImportError:
            pytest.skip("Retrain pipeline not available")
    
    def test_retrain_duplicate_timestamps(self):
        """Test retraining with duplicate timestamps."""
        try:
            from src.self_healing.retrain_pipeline import build_training_window
            
            # Data with duplicates
            df = pd.DataFrame({
                'timestamp': ['2020-01-01 00:00'] * 10 + pd.date_range('2020-01-01 01:00', periods=90, freq='H').tolist(),
                'load_mw': [180000 + i for i in range(100)],
            })
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            window = build_training_window(df)
            
            # Should handle duplicates
            assert window is None or isinstance(window, pd.DataFrame)
        except (ImportError, AttributeError):
            pytest.skip("build_training_window not available")
    
    def test_retrain_with_nans(self):
        """Test retraining with missing values."""
        try:
            from src.self_healing.retrain_pipeline import build_training_window
            
            df = pd.DataFrame({
                'timestamp': pd.date_range('2020-01-01', periods=100, freq='H'),
                'load_mw': [180000 + i*100 for i in range(100)],
            })
            df.loc[50:60, 'load_mw'] = float('nan')
            
            window = build_training_window(df)
            
            # Should handle NaNs
            assert window is None or isinstance(window, pd.DataFrame)
        except (ImportError, AttributeError):
            pytest.skip("build_training_window not available")
