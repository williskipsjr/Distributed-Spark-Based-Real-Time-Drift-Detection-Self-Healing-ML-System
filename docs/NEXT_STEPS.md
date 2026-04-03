# NEXT STEPS

Last updated: 2026-04-03

## Immediate (next session)

1. Run 24h soak test for orchestrator with decision log review.
2. Add integration test for promotion -> serving reload chain (non-dry-run in controlled fixture).
3. Add operational runbook for rollback + replay after failed reload.
4. Add alert thresholds for repeated reload failures.

## Short-term

1. Add regression tests for:
   - feature-order enforcement
   - drift report numeric stability (NaN guard)
   - replay-window anchoring behavior.
2. Add runbook scripts for:
   - cleanup of stale/zero-byte parquet
   - one-command producer+spark smoke execution.
3. Add periodic compaction/rotation for model lifecycle registry JSONL artifacts.

## Medium-term

1. Expand feature drift inputs from hourly aggregates to richer feature snapshots at scoring time.
2. Integrate monitoring dashboard for model and drift trends.
3. Add API layer for dashboard consumption.

## Project milestone status

- Streaming inference stability: In progress.
- Drift detection hardening: Completed.
- Self-healing loop: Completed (initial production-ready baseline).

