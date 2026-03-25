# NEXT STEPS

Last updated: 2026-03-26

## Immediate (next session)

1. Implement self-healing trigger script:
   - read `artifacts/drift/drift_report.json`
   - trigger retraining when `drift_detected=true`
   - persist decision and action logs.
2. Implement retraining runner (`src/ml/retrain.py`) with explicit input/output artifact paths.
3. Add model promotion policy:
   - compare new model against baseline thresholds
   - promote only on acceptance criteria.
4. Add serving reload workflow:
   - restart or reload Spark job with promoted model.

## Short-term

1. Add regression tests for:
   - feature-order enforcement
   - drift report numeric stability (NaN guard)
   - replay-window anchoring behavior.
2. Add runbook scripts for:
   - cleanup of stale/zero-byte parquet
   - one-command producer+spark smoke execution.
3. Track model version metadata in a registry JSON.

## Medium-term

1. Implement feature-level drift (KS/PSI) in `src/drift_detection/drift_detector.py`.
2. Add retraining provenance tracking (dataset, timestamp, metrics, model hash).
3. Integrate monitoring dashboard for model and drift trends.

## Project milestone status

- Streaming inference stability: In progress.
- Drift detection hardening: Completed.
- Self-healing loop: In progress.

