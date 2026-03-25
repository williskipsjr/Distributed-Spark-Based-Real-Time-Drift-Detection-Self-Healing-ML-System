# ISSUES LOG

Last updated: 2026-03-26

## Issue 1: Git tracking noise from local environment artifacts

- Symptom: very large `git status` noise from local env/install directories.
- Root cause: incomplete ignore coverage for venv and Spark binaries.
- Resolution: expanded `.gitignore` patterns and removed cached tracked paths.
- Status: Resolved.

## Issue 2: Multi-zone data leakage in supervised pipeline

- Symptom: unrealistically high model metrics and lag contamination risk.
- Root cause: zone-level records were not consistently aggregated by timestamp before feature generation.
- Resolution: aggregate to PJM-wide hourly series, regenerate supervised data, retrain model.
- Status: Resolved.

## Issue 3: Producer dataset ambiguity (raw vs supervised)

- Symptom: confusion about source data path and expected scale.
- Root cause: producer supports multiple formats; usage was unclear in runs.
- Resolution: clarified defaults, added validation, and documented explicit dataset commands.
- Status: Resolved.

## Issue 4: Legacy model artifact compatibility

- Symptom: failures when loading old raw-estimator artifacts.
- Root cause: artifact format evolved to model bundle.
- Resolution: compatibility handling in model loader.
- Status: Resolved.

## Issue 5: Checkpoint and restart friction in streaming iterations

- Symptom: repeated local test cycles caused stale-state conflicts.
- Root cause: checkpoint reuse during iterative schema/query changes.
- Resolution: reset strategy and runbook documentation.
- Status: Managed.

## Issue 6: Drift detector empty-window failures

- Symptom: detector failed when no baseline/recent data windows available.
- Root cause: insufficient hourly metrics history and wall-clock anchored windows.
- Resolution: explicit error messages and replay-aware timestamp anchoring update.
- Status: Resolved.

## Issue 7: Critical inference misprediction incident

- Symptom: invalid-scale/negative predictions despite plausible feature values.
- Root cause: inference ordering and environment mismatch risks during serve path.
- Resolution: strict feature order enforcement, model/runtime parity validation, and live re-verification.
- Status: Resolved.

## Issue 8: Production-mode instability from Python callback writer path

- Symptom: Spark streaming termination with `Py4JException` and `Python worker exited unexpectedly`.
- Root cause: fragile Python callback path (`foreachBatch`) under local WSL Spark execution.
- Resolution:
  - replaced production sink with native Spark parquet streaming sink
  - constrained local Spark execution and runtime settings
  - added graceful internal runtime window (`--run-seconds`)
- Status: Resolved.

## Issue 9: Zero-byte parquet artifacts after interrupted runs

- Symptom: pandas/pyarrow read failures (`Parquet file size is 0 bytes`).
- Root cause: interrupted batch writes leaving partial output files.
- Resolution: cleanup runbook for zero-byte file removal and robust read script filtering non-empty files.
- Status: Resolved.

## Issue 10: NaN `baseline_std_prediction` in drift report

- Symptom: drift report produced `baseline_std_prediction: NaN`.
- Root cause: hourly windows often contained single records, making `std_prediction` undefined.
- Resolution: fallback to standard deviation of baseline `mean_prediction` when needed.
- Status: Resolved.

