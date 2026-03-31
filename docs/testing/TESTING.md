# Testing Guide - Self-Healing ML System

Complete automated test suite replacing all manual terminal commands.

## Quick Start

```powershell
# Terminal 1: Setup and activate
cd 'c:\Users\Willis\OneDrive\Documents\IIIT-DWD\2nd Year\4th Sem\Big Data\BDA-Project\Distributed-Spark-Based-Real-Time-Drift-Detection-Self-Healing-ML-System'
& ".\.venv\Scripts\Activate.ps1"

# Install test dependencies
pip install pytest pytest-cov pytest-timeout

# Run all tests
pytest
```

## Test Organization

### Unit Tests (Fast, Isolated)
- **`test_producer.py`** - Data loading, aggregation, quality checks (10 tests)
- **`test_model_loading.py`** - Model pointer system, loading consistency (12 tests)
- **`test_trigger.py`** - Trigger decision logic (12 tests)
- **`test_promotion.py`** - Promotion gates and rollback (14 tests)

### Integration Tests (Slower, Multi-Component)
- **`test_integration.py`** - End-to-end workflows (15 tests)

## Running Tests

### Run All Tests
```powershell
pytest
# Output: Collected XX tests
#         XX passed in X.XXs
```

### Run by Category
```powershell
# Unit tests only (fast, ~10 seconds)
pytest -m unit

# Integration tests only (slower, ~30 seconds)
pytest -m integration

# Skip Kafka/Spark tests
pytest -m "not requires_kafka and not requires_spark"
```

### Run Specific Test File
```powershell
pytest tests/test_producer.py -v
pytest tests/test_trigger.py -v
pytest tests/test_promotion.py -v
```

### Run Single Test
```powershell
pytest tests/test_producer.py::TestProducerDataLoading::test_load_csv_data -v
```

### Show Details
```powershell
# Verbose output
pytest -v --tb=short

# Show print statements
pytest -s

# Show slowest 10 tests
pytest --durations=10

# Stop on first failure
pytest -x
```

## Test Coverage

```powershell
# Install coverage
pip install pytest-cov

# Generate coverage report
pytest --cov=src --cov-report=html

# View report
Start-Process htmlcov/index.html
```

## Test Markers

```powershell
@pytest.mark.unit              # Unit tests (isolated)
@pytest.mark.integration       # Integration tests
@pytest.mark.requires_kafka    # Needs Kafka running
@pytest.mark.requires_spark    # Needs Spark running
@pytest.mark.slow              # Takes >5 seconds
```

### Filter Examples
```powershell
# Only fast unit tests
pytest -m "unit and not requires_kafka and not requires_spark"

# All except integration
pytest -m "not integration"

# Both unit and integration, no slow tests
pytest -m "not slow"
```

## Common Scenarios

### Before Commit (Quick Check)
```powershell
pytest -m "unit and not requires_kafka" -x --tb=short
```

### Full System Check
```powershell
pytest --tb=short -v
```

### Debug Failing Test
```powershell
pytest tests/test_producer.py::TestProducerDataLoading::test_load_csv_data -s -vv
```

## Troubleshooting

### "No tests found"
```powershell
# Ensure tests/ has __init__.py
# Ensure test files start with test_
pytest --collect-only
```

### "Kafka connection refused"
```powershell
# Skip Kafka tests
pytest -m "not requires_kafka"
```

### "Test hangs"
```powershell
# Already configured in pytest.ini with 300s timeout
```

## Fixtures Available

See `conftest.py` for shared fixtures:
- `temp_artifacts_dir` - Temporary directory for test artifacts
- `sample_features_df` - Sample feature DataFrame
- `sample_kafka_message` - Sample Kafka message
- `sample_metrics_row` - Sample metrics
- `kafka_admin` - Kafka admin client
- `project_root` - Project root path

## Expected Run Times

- Unit tests: 10-15 seconds
- Integration tests: 20-30 seconds
- Full suite: 30-45 seconds
- With coverage: +10-15 seconds

## Test Development

### Add New Test
```python
def test_my_feature():
    """Test that feature X works."""
    result = my_function()
    assert result is not None
```

### Parametrized Tests
```python
@pytest.mark.parametrize("input,expected", [
    (0, True),
    (1, False),
])
def test_multiple_cases(input, expected):
    assert function(input) == expected
```
