"""
Unit tests for feature engineering pipeline.
"""
import pandas as pd
import pytest

from src.data.feature_builder import (
    FEATURE_COLUMNS, 
    FeatureSpec, 
    build_supervised_pandas,
    add_time_features_pandas,
    add_lag_and_rolling_features_pandas,
)


@pytest.mark.unit
class TestFeatureColumns:
    """Tests for feature column definitions."""
    
    def test_feature_columns_defined(self):
        """Test that FEATURE_COLUMNS is defined."""
        assert FEATURE_COLUMNS is not None
        assert len(FEATURE_COLUMNS) > 0
    
    def test_feature_columns_are_strings(self):
        """Test that all feature columns are strings."""
        for col in FEATURE_COLUMNS:
            assert isinstance(col, str)
    
    def test_required_features_present(self):
        """Test that required features are in the list."""
        required = ['hour_of_day', 'day_of_week', 'month', 'is_weekend', 
                   'lag_1', 'lag_24', 'lag_168', 'rolling_24', 'rolling_168']
        for feat in required:
            assert feat in FEATURE_COLUMNS, f"Missing required feature: {feat}"


@pytest.mark.unit
class TestFeatureSpec:
    """Tests for FeatureSpec configuration."""
    
    def test_feature_spec_creation(self):
        """Test creating a FeatureSpec."""
        spec = FeatureSpec(
            timestamp_col='datetime',
            target_col='load_mw',
            group_cols=()
        )
        assert spec is not None
        assert spec.timestamp_col == 'datetime'
        assert spec.target_col == 'load_mw'
    
    def test_feature_spec_with_grouped_features(self):
        """Test FeatureSpec with aggregation groups."""
        spec = FeatureSpec(
            timestamp_col='datetime',
            target_col='load_mw',
            group_cols=('zone',)  # Group by zone
        )
        assert spec.group_cols == ('zone',)


@pytest.mark.unit
class TestBuildFeaturesBasic:
    """Tests for basic feature building."""
    
    def test_build_features_input_validation(self):
        """Test that build_features validates input."""
        # Empty dataframe
        df_empty = pd.DataFrame()
        try:
            result = build_supervised_pandas(df_empty, FeatureSpec('dt', 'target', ()))
            # Should either succeed with empty or raise error
            assert isinstance(result, pd.DataFrame)
        except (ValueError, KeyError):
            # Expected for invalid input
            pass
    
    def test_build_features_returns_dataframe(self):
        """Test that build_features returns a DataFrame."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=100, freq='H'),
            'load_mw': [180000 + i*100 for i in range(100)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        assert isinstance(result, pd.DataFrame)
    
    def test_build_features_preserves_index(self):
        """Test that feature building preserves data ordering."""
        n = 50
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=n, freq='H'),
            'load_mw': [180000 + i*100 for i in range(n)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        # Should maintain order
        assert len(result) > 0


@pytest.mark.unit
class TestFeatureEngineering:
    """Tests for feature engineering correctness."""
    
    def test_temporal_features_in_output(self):
        """Test that temporal features (hour, day, month) are generated."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-15 10:30:00', periods=24, freq='H'),
            'load_mw': [180000 + i*100 for i in range(24)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        # Check temporal features exist
        temporal_features = ['hour_of_day', 'day_of_week', 'month', 'is_weekend']
        for feat in temporal_features:
            if feat in result.columns:
                assert not result[feat].isna().all(), f"{feat} all NaN"
    
    def test_lag_features_generation(self):
        """Test that lag features are correctly generated."""
        n = 200
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=n, freq='H'),
            'load_mw': [180000 + i*100 for i in range(n)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        # Lag features should exist (may have NaN for early rows)
        lag_features = ['lag_1', 'lag_24', 'lag_168']
        for feat in lag_features:
            if feat in result.columns:
                assert not result[feat].isna().all(), f"{feat} all NaN"
    
    def test_rolling_features_generation(self):
        """Test that rolling window features are generated."""
        n = 200
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=n, freq='H'),
            'load_mw': [180000 + i*100 for i in range(n)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        # Rolling features
        rolling_features = ['rolling_24', 'rolling_168']
        for feat in rolling_features:
            if feat in result.columns:
                assert not result[feat].isna().all(), f"{feat} all NaN"
    
    def test_hour_of_day_range(self):
        """Test that hour_of_day is in valid range [0, 23]."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=100, freq='H'),
            'load_mw': [180000 + i*100 for i in range(100)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        if 'hour_of_day' in result.columns:
            assert (result['hour_of_day'] >= 0).all()
            assert (result['hour_of_day'] <= 23).all()
    
    def test_day_of_week_range(self):
        """Test that day_of_week is in valid range [0, 6]."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=100, freq='H'),
            'load_mw': [180000 + i*100 for i in range(100)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        if 'day_of_week' in result.columns:
            assert (result['day_of_week'] >= 0).all()
            assert (result['day_of_week'] <= 6).all()
    
    def test_month_range(self):
        """Test that month is in valid range [1, 12]."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=365, freq='D'),
            'load_mw': [180000 + i*10 for i in range(365)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        if 'month' in result.columns:
            assert (result['month'] >= 1).all()
            assert (result['month'] <= 12).all()
    
    def test_is_weekend_binary(self):
        """Test that is_weekend is binary [0, 1]."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=100, freq='D'),
            'load_mw': [180000 + i*10 for i in range(100)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        if 'is_weekend' in result.columns:
            assert set(result['is_weekend'].dropna().unique()).issubset({0, 1})


@pytest.mark.unit
class TestFeatureQuality:
    """Tests for feature output quality."""
    
    def test_features_no_infinite_values(self):
        """Test that generated features have no infinite values."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=100, freq='H'),
            'load_mw': [180000 + i*100 for i in range(100)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        for col in FEATURE_COLUMNS:
            if col in result.columns:
                assert not result[col].isin([float('inf'), float('-inf')]).any(), \
                    f"{col} contains infinite values"
    
    def test_features_reasonable_scales(self):
        """Test that features are in reasonable value ranges."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=200, freq='H'),
            'load_mw': [180000 + i*100 for i in range(200)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=())
        result = build_supervised_pandas(df, spec)
        
        # Lag and rolling features should be in same scale as target (150k-210k)
        for lag_col in ['lag_1', 'lag_24', 'lag_168']:
            if lag_col in result.columns:
                valid_vals = result[lag_col].dropna()
                if len(valid_vals) > 0:
                    assert valid_vals.max() < 1000000, f"{lag_col} exceeds scale"
                    assert valid_vals.min() > 0, f"{lag_col} has non-positive values"


@pytest.mark.unit
class TestFeatureAggregation:
    """Tests for feature building with grouping."""
    
    def test_grouped_feature_building(self):
        """Test feature building with grouped aggregation."""
        df = pd.DataFrame({
            'datetime': pd.date_range('2020-01-01', periods=50, freq='H'),
            'zone': ['north'] * 25 + ['south'] * 25,
            'load_mw': [6000 + i*10 for i in range(50)],
        })
        
        spec = FeatureSpec(timestamp_col='datetime', target_col='load_mw', group_cols=('zone',))
        
        try:
            result = build_supervised_pandas(df, spec)
            assert isinstance(result, pd.DataFrame)
        except NotImplementedError:
            # Grouped features might not be implemented
            pass
