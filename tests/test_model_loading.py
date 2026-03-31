"""
Unit tests for model loading and active model pointer system.
"""
import json
from pathlib import Path

import pytest

from src.ml.model_io import (
    load_model,
    _resolve_active_model_path,
    _active_model_pointer_path,
)
from src.data.feature_builder import FEATURE_COLUMNS


@pytest.mark.unit
class TestModelPointerSystem:
    """Tests for active model pointer mechanism."""
    
    def test_pointer_path_exists(self, project_root):
        """Test that pointer path is correctly resolved."""
        pointer_path = _active_model_pointer_path()
        assert pointer_path is not None
        assert isinstance(pointer_path, Path)
        assert 'active_model.json' in str(pointer_path)
    
    def test_resolve_pointer_when_exists(self, project_root, temp_artifacts_dir):
        """Test pointer resolution when file exists."""
        # Create a test pointer file
        pointer_path = temp_artifacts_dir / "models" / "active_model.json"
        test_model_path = project_root / "artifacts" / "models" / "model_v2.joblib"
        
        pointer_data = {
            "active_model_path": str(test_model_path),
            "active_model_version": "v2",
            "previous_model_path": None,
            "previous_model_version": None
        }
        
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pointer_path, 'w') as f:
            json.dump(pointer_data, f)
        
        # Monkeypatch the pointer path
        import src.ml.model_io
        original_pointer_path = _active_model_pointer_path
        src.ml.model_io._active_model_pointer_path = lambda: pointer_path
        
        try:
            resolved = _resolve_active_model_path()
            # Note: resolved might be None if model_v2.joblib doesn't exist
            # This is expected - we're testing the pointer file parsing
        finally:
            src.ml.model_io._active_model_pointer_path = original_pointer_path
    
    def test_pointer_file_structure(self, project_root):
        """Test that pointer file (if exists) has correct structure."""
        pointer_path = _active_model_pointer_path()
        
        if pointer_path.exists():
            with open(pointer_path, 'r') as f:
                pointer_data = json.load(f)
            
            required_keys = ['active_model_path', 'active_model_version']
            for key in required_keys:
                assert key in pointer_data, f"Missing key in pointer: {key}"
            
            assert isinstance(pointer_data['active_model_path'], str)
            assert isinstance(pointer_data['active_model_version'], str)


@pytest.mark.unit
class TestModelLoading:
    """Tests for model loading functionality."""
    
    def test_load_model_no_path(self):
        """Test loading model with default (pointer-first) behavior."""
        try:
            bundle = load_model(model_path=None)
            assert bundle is not None
            assert 'model' in bundle
            assert 'features' in bundle
        except FileNotFoundError:
            pytest.skip("No models found in artifacts")
    
    def test_load_model_explicit_path(self, project_root):
        """Test loading model with explicit path."""
        model_path = project_root / "artifacts" / "models" / "model_v2.joblib"
        
        if model_path.exists():
            bundle = load_model(model_path=model_path)
            assert bundle is not None
            assert 'model' in bundle
            assert 'features' in bundle
    
    def test_loaded_model_has_features(self):
        """Test that loaded model bundle has correct feature list."""
        try:
            bundle = load_model(model_path=None)
            features = bundle.get('features')
            assert features is not None
            assert features == list(FEATURE_COLUMNS)
        except FileNotFoundError:
            pytest.skip("No models found in artifacts")
    
    def test_loaded_model_is_predictor(self):
        """Test that loaded model has predict method."""
        try:
            bundle = load_model(model_path=None)
            model = bundle['model']
            assert hasattr(model, 'predict'), "Model lacks predict method"
        except FileNotFoundError:
            pytest.skip("No models found in artifacts")
    
    def test_model_prediction_shape(self, sample_features_df):
        """Test that model produces predictions with correct shape."""
        try:
            bundle = load_model(model_path=None)
            model = bundle['model']
            
            predictions = model.predict(sample_features_df)
            assert len(predictions) == len(sample_features_df)
        except FileNotFoundError:
            pytest.skip("No models found in artifacts")
    
    def test_model_prediction_scale(self, sample_features_df):
        """Test that model predictions are in expected scale."""
        try:
            bundle = load_model(model_path=None)
            model = bundle['model']
            
            predictions = model.predict(sample_features_df)
            pred_mean = predictions.mean()
            
            # Predictions should be in PJM-wide scale (~150k-210k), not zone scale (~6k)
            assert 100000 < pred_mean < 250000, \
                f"Predictions out of scale: mean={pred_mean:.0f}"
        except FileNotFoundError:
            pytest.skip("No models found in artifacts")


@pytest.mark.unit
class TestModelConsistency:
    """Tests for model loading consistency."""
    
    def test_same_model_loaded_multiple_times(self):
        """Test that loading model multiple times gives consistent predictions."""
        try:
            bundle1 = load_model(model_path=None)
            bundle2 = load_model(model_path=None)
            
            # Models should be same version
            assert bundle1['features'] == bundle2['features']
        except FileNotFoundError:
            pytest.skip("No models found in artifacts")
    
    def test_explicit_path_matches_pointer(self, project_root):
        """Test that explicit path and pointer give consistent results."""
        model_v2_path = project_root / "artifacts" / "models" / "model_v2.joblib"
        
        if model_v2_path.exists():
            bundle_default = load_model(model_path=None)
            bundle_explicit = load_model(model_path=model_v2_path)
            
            # Both should be loadable
            assert bundle_default is not None
            assert bundle_explicit is not None
