# Scripts Guide

This folder organizes one-off scripts used during development and operations.

## utilities/

Operational helper scripts that are still useful for regular checks:

- `check_producer_data.py`: Verify producer input scale and feature-ready output.
- `validate_model_v2.py`: Offline sanity checks for deployed model behavior.

## archive_debug/

Historical debugging and incident analysis scripts retained for traceability:

- `compare_models.py`
- `debug_step_by_step.py`
- `diagnose_aggregation.py`
- `test_fix_zone_aggregation.py`

These archived scripts are not part of the production runtime path.
