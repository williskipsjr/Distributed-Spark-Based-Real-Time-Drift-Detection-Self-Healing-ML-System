# FRONTEND INTEGRATION PLAN

Last updated: 2026-04-01

## Goal

Deliver a reliable monitoring UI for the current Spark + drift + self-healing pipeline without changing core ML behavior. The frontend should present accurate hourly state, not pseudo real-time claims.

## Scope

- Build a read-only API layer for frontend consumption.
- Build monitoring views for prediction quality, drift, model status, and self-healing actions.
- Add explicit freshness and degraded-state handling.

Out of scope for v1:

- Manual trigger controls (retrain/promote/rollback buttons).
- Multi-user auth and RBAC.
- Streaming push transport (WebSocket/SSE).

## Ground Truth Constraints

1. Hourly metrics are the canonical frontend source (`data/metrics/hourly_metrics/*.parquet`).
2. Drift state is artifact-driven (`artifacts/drift/*`).
3. Model state is artifact-driven (`artifacts/models/*`).
4. Self-healing state is artifact-driven (`artifacts/self_healing/*`).
5. API responses must include freshness metadata because pipeline components can be stale independently.

## Phase-by-Phase Execution Plan

### Phase 0: Contract Freeze (do first)

Deliverables:

1. Response schema for each API endpoint.
2. Shared query parameters for time windows and limits.
3. Standard API envelope for freshness and degraded-state reporting.

Required envelope fields (all endpoints):

- `generated_at`: API generation timestamp (UTC ISO8601).
- `data_as_of`: newest source record timestamp used in payload.
- `stale_after_seconds`: expected freshness threshold for endpoint.
- `is_stale`: boolean computed from `data_as_of`.
- `source_status`: object with file-read status per data source.

Acceptance criteria:

1. Endpoint specs are documented before coding handlers.
2. Frontend can render stale state using only envelope fields.

---

### Phase 1: API v1 (read-only, no control actions)

Implement these endpoints first:

1. `GET /api/v1/dashboard/summary`
2. `GET /api/v1/predictions?window=24h|7d|30d&limit=...`
3. `GET /api/v1/drift/current`
4. `GET /api/v1/drift/history?limit=...`
5. `GET /api/v1/system/health`

Why this subset first:

- Covers the highest-value UI views.
- Validates parquet + JSON artifact reads.
- Forces stale/degraded behavior to be solved early.

Implementation notes:

1. Use FastAPI + Pydantic models for strict response contracts.
2. Add a small in-process TTL cache for expensive reads (30-60 seconds).
3. Fail soft on missing files: return empty data + source_status errors, not generic 500.

Acceptance criteria:

1. All 5 endpoints return contract-compliant responses with freshness fields.
2. Missing artifact files do not crash the API process.
3. Health endpoint reflects source-level failures and staleness.

---

### Phase 2: Frontend v1 (two screens first)

Build these views first:

1. Dashboard
2. Drift Monitoring

Dashboard minimum widgets:

1. Latest predicted vs actual load.
2. Latest error (absolute and percentage).
3. 24h trend chart.
4. Global health/staleness banner.

Drift Monitoring minimum widgets:

1. Current drift status summary.
2. Drift trend timeline from history records.
3. Feature-level breakdown if present in artifact.

Refresh policy:

1. Poll every 30-60 seconds.
2. Show explicit "Last updated" and stale indicator.

Acceptance criteria:

1. UI remains functional when endpoints return stale data.
2. Empty-state rendering exists for all major panels.

---

### Phase 3: API v2 + Additional Views

Add endpoints:

1. `GET /api/v1/models/active`
2. `GET /api/v1/models/versions`
3. `GET /api/v1/self-healing/status`

Add views:

1. Model Management
2. Self-Healing Status

Model Management minimum data:

1. Active model id/version and activation timestamp.
2. Promotion history timeline.
3. Candidate evaluation summary (if available).

Self-Healing minimum data:

1. Recent trigger decisions.
2. Last retrain attempt status.
3. Last promotion decision and reason.

Acceptance criteria:

1. Frontend can explain current serving model and recent promotion decisions.
2. Self-healing panel shows decision trace without needing log file access.

---

### Phase 4: Hardening + Ops Readiness

Deliverables:

1. API test coverage for stale/missing/corrupt source scenarios.
2. Frontend loading/error/empty state coverage.
3. Lightweight runbook for starting API + frontend + pipeline together.

Acceptance criteria:

1. Known failure modes are observable from UI health indicators.
2. Team can demo stable monitoring flow end-to-end.

## Endpoint Cross-Reference Matrix

| Endpoint | Primary data sources | Frontend usage | Failure mode handling |
|---|---|---|---|
| `/api/v1/dashboard/summary` | `data/metrics/hourly_metrics/*.parquet`, `artifacts/drift/drift_report.json`, `artifacts/models/active_model.json` | Top-level dashboard cards and status bar | Return partial summary + `source_status` for unreadable sources |
| `/api/v1/predictions` | `data/metrics/hourly_metrics/*.parquet` | Forecast vs actual trend chart | Return empty series with stale metadata |
| `/api/v1/drift/current` | `artifacts/drift/drift_report.json` | Current drift indicator and table | Return `drift_available=false` with source error details |
| `/api/v1/drift/history` | `artifacts/drift/drift_history.jsonl` | Drift timeline chart | Return empty list when file missing/empty |
| `/api/v1/system/health` | all above + optional process checks | Health banner and diagnostics panel | Always respond with component statuses |
| `/api/v1/models/active` | `artifacts/models/active_model.json` | Active model card | Return unknown state with source status |
| `/api/v1/models/versions` | `artifacts/models/promotion_log.jsonl`, `artifacts/models/candidate_report.json` | Version history timeline | Return partial list if one source fails |
| `/api/v1/self-healing/status` | `artifacts/self_healing/trigger_decisions.jsonl`, `artifacts/models/candidate_report.json` | Self-healing decision feed | Return empty decisions + source errors |

## Implementation Order Checklist (One by One)

1. Write API response models and shared freshness envelope.
2. Implement file readers with safe parse + source_status reporting.
3. Implement the 5 Phase 1 endpoints.
4. Add API tests for happy path + stale + missing file scenarios.
5. Scaffold frontend app with route skeleton and shared API client.
6. Build Dashboard view wired to summary + predictions + health.
7. Build Drift Monitoring view wired to drift current + history.
8. Add models/self-healing endpoints and views.
9. Run end-to-end validation and capture screenshots + notes.

## Risks and Controls

1. Risk: stale parquet shards and zero-byte files.
   - Control: skip unreadable files, mark source degraded, continue serving.
2. Risk: inconsistent artifact schema between runs.
   - Control: tolerant parsing with explicit defaults and schema version in response.
3. Risk: frontend misrepresents freshness as live streaming.
   - Control: mandatory stale badge and "data as of" timestamp in all key widgets.
4. Risk: API latency spikes from repeated parquet scans.
   - Control: short TTL caching and optional window/limit query constraints.

## Validation and Cross-Reference Checks

Cross-references used for this plan:

1. `docs/ARCHITECTURE.md` (pipeline flow and source-of-truth artifacts).
2. `docs/NEXT_STEPS.md` (dashboard as medium-term item).
3. `docs/PROGRESS.md` (dashboard currently pending).
4. `docs/reports/FINAL_REPORT.md` (monitoring expectations and alerting direction).

Planned follow-up after each phase:

1. Update `docs/PROGRESS.md` with phase completion.
2. Update `docs/NEXT_STEPS.md` by replacing completed frontend tasks with next executable items.
3. Append implementation notes in `docs/SESSION_LOG.md`.
