# Scripts Guide

This folder organizes one-off scripts used during development and operations.

## utilities/

Operational helper scripts that are still useful for regular checks:

- `check_producer_data.py`: Verify producer input scale and feature-ready output.
- `validate_model_v2.py`: Offline sanity checks for deployed model behavior.
- `cleanup_zero_byte_metrics.py`: Remove zero-byte parquet shards from `data/metrics/hourly_metrics`.
- `check_model_version_in_metrics.py`: Verify active model version values written in hourly metrics parquet output.

## archive_debug/

Historical debugging and incident analysis scripts retained for traceability:

- `compare_models.py`
- `debug_step_by_step.py`
- `diagnose_aggregation.py`
- `test_fix_zone_aggregation.py`

These archived scripts are not part of the production runtime path.
