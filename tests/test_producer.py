"""
Unit tests for Kafka producer functionality.
"""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import pandas as pd

from src.streaming.kafka_producer import (
    _resolve_dataset_path,
    _resolve_dataset_sequence,
    _load_and_prepare_data,
)


@pytest.mark.unit
class TestProducerDataLoading:
    """Tests for producer data loading and preparation."""
    
    def test_resolve_dataset_path_default(self):
        """Test default dataset path resolution."""
        path = _resolve_dataset_path(None)
        assert path is not None
        assert path.exists()
        assert path.suffix in ['.csv', '.parquet']
    
    def test_resolve_dataset_path_explicit(self, project_root):
        """Test explicit dataset path resolution."""
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        resolved = _resolve_dataset_path(str(dataset_path))
        assert resolved == dataset_path
        assert resolved.exists()

    def test_resolve_dataset_sequence_yearly_rollover(self, tmp_path):
        """Test yearly dataset sequence auto-advance from starting year."""
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        file_2019 = data_dir / "hrl_load_metered-2019.csv"
        file_2020 = data_dir / "hrl_load_metered-2020.csv"
        file_2021 = data_dir / "hrl_load_metered-2021.csv"
        file_2019.write_text("x", encoding="utf-8")
        file_2020.write_text("x", encoding="utf-8")
        file_2021.write_text("x", encoding="utf-8")

        resolved = _resolve_dataset_sequence(str(file_2020))
        assert resolved == [file_2020.resolve(), file_2021.resolve()]

    def test_resolve_dataset_sequence_non_yearly_single(self, tmp_path):
        """Test non-yearly filenames remain as a single dataset sequence."""
        dataset = tmp_path / "sample_input.csv"
        dataset.write_text("x", encoding="utf-8")

        resolved = _resolve_dataset_sequence(str(dataset))
        assert resolved == [dataset.resolve()]
    
    def test_load_csv_data(self, project_root):
        """Test loading CSV data."""
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
            assert 'load_mw' in df.columns
            # CSV should be aggregated: mean should be ~180k, not ~6k
            assert df['load_mw'].mean() > 100000, "CSV not properly aggregated"
    
    def test_load_parquet_data(self, project_root):
        """Test loading parquet data."""
        dataset_path = project_root / "data" / "processed" / "pjm_supervised.parquet"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
            assert 'load_mw' in df.columns
    
    def test_data_has_required_features(self, project_root):
        """Test that loaded data has all required feature columns."""
        from src.data.feature_builder import FEATURE_COLUMNS
        
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            for col in FEATURE_COLUMNS:
                assert col in df.columns, f"Missing feature column: {col}"
    
    def test_data_aggregation_scale(self, project_root):
        """Test that data is properly aggregated to PJM-wide scale."""
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            mean_load = df['load_mw'].mean()
            # PJM-wide aggregate should be ~150k-210k MW, not zone-level ~6k
            assert 100000 < mean_load < 250000, \
                f"Load scale {mean_load:.0f} suggests improper aggregation"


@pytest.mark.unit
class TestProducerDataQuality:
    """Tests for producer data quality checks."""
    
    def test_loading_no_duplicates(self, project_root):
        """Test that loaded data has no duplicates."""
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            assert not df.duplicated().any(), "Data contains duplicate rows"
    
    def test_loading_no_nans_in_features(self, project_root):
        """Test that loaded data has no NaNs in required features."""
        from src.data.feature_builder import FEATURE_COLUMNS
        
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            for col in FEATURE_COLUMNS:
                assert not df[col].isna().any(), f"Feature {col} contains NaNs"
    
    def test_loading_target_in_range(self, project_root):
        """Test that target values are in expected range."""
        dataset_path = project_root / "data" / "stream_dataset" / "hrl_load_metered-2019.csv"
        if dataset_path.exists():
            df = _load_and_prepare_data(dataset_path)
            assert (df['load_mw'] > 0).all(), "Load values contain non-positive values"
            assert (df['load_mw'] < 1000000).all(), "Load values exceed reasonable limit"
