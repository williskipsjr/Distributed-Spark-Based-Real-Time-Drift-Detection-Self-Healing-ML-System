# FRONTEND API CONTRACT (PHASE 0)

Last updated: 2026-04-01
Status: Contract freeze for API v1 implementation

## 1. Base Conventions

Base path:
- /api/v1

Time format:
- UTC ISO8601 strings, example: 2026-04-01T13:00:00Z

Standard query behavior:
- Invalid query params return HTTP 422 with validation detail.
- Missing data sources do not cause generic 500 when partial response is possible.

## 2. Standard Envelope (All Endpoints)

Every successful response must include:

- generated_at: string
- data_as_of: string | null
- stale_after_seconds: integer
- is_stale: boolean
- source_status: object
- data: object | array

source_status schema:

{
  "hourly_metrics": {
    "ok": true,
    "path": "data/metrics/hourly_metrics",
    "last_modified": "2026-04-01T13:00:00Z",
    "error": null
  },
  "drift_report": {
    "ok": false,
    "path": "artifacts/drift/drift_report.json",
    "last_modified": null,
    "error": "file_not_found"
  }
}

Rules:
- ok=true means source read/parse succeeded.
- ok=false requires error string.
- last_modified may be null when missing.

## 3. Shared Query Parameters

window:
- Allowed: 24h, 7d, 30d
- Default: 24h

limit:
- Integer, min 1, max 5000
- Default endpoint-specific

from_ts / to_ts (optional in future extension):
- ISO8601
- If provided, from_ts must be <= to_ts

## 4. Endpoint Contracts (Phase 1)

### 4.1 GET /api/v1/dashboard/summary

Purpose:
- Snapshot for top-level dashboard cards.

data schema:

{
  "latest_timestamp": "2026-04-01T13:00:00Z",
  "actual_mw": 183245.5,
  "predicted_mw": 181932.1,
  "abs_error_mw": 1313.4,
  "pct_error": 0.72,
  "drift_detected": false,
  "active_model_version": "v2",
  "health_level": "ok"
}

Notes:
- health_level enum: ok | degraded | critical
- pct_error is percentage points, not fraction in UI usage.

### 4.2 GET /api/v1/predictions

Query:
- window: 24h | 7d | 30d (default 24h)
- limit: int (default 1000)

data schema:

{
  "window": "24h",
  "points": [
    {
      "timestamp": "2026-04-01T12:00:00Z",
      "actual_mw": 182000.0,
      "predicted_mw": 181200.0,
      "abs_error_mw": 800.0,
      "model_version": "v2"
    }
  ],
  "summary": {
    "count": 24,
    "mae_mw": 1210.3,
    "rmse_mw": 1454.8,
    "mape_pct": 0.83
  }
}

Notes:
- points sorted ascending by timestamp.
- empty points is valid when source has no rows.

### 4.3 GET /api/v1/drift/current

Purpose:
- Current drift state used by drift panel.

data schema:

{
  "drift_available": true,
  "drift_detected": false,
  "detected_at": "2026-04-01T13:05:00Z",
  "metrics": {
    "prediction_drift": {
      "detected": false,
      "score": 0.03,
      "threshold": 0.1
    },
    "performance_drift": {
      "detected": false,
      "score": 0.04,
      "threshold": 0.1
    }
  },
  "feature_drift": [
    {
      "feature": "lag_24",
      "ks_score": 0.08,
      "psi_score": 0.05,
      "drifted": false
    }
  ]
}

Notes:
- drift_available=false when drift report missing/unreadable.
- feature_drift may be empty if not present in report.

### 4.4 GET /api/v1/drift/history

Query:
- limit: int (default 500)

data schema:

{
  "events": [
    {
      "timestamp": "2026-04-01T10:00:00Z",
      "drift_detected": true,
      "prediction_drift_score": 0.12,
      "performance_drift_score": 0.15
    }
  ],
  "count": 120
}

Notes:
- events sorted ascending by timestamp.
- if file missing, return empty events with source_status error.

### 4.5 GET /api/v1/system/health

Purpose:
- Backend status panel and global banner.

data schema:

{
  "overall": "degraded",
  "components": {
    "hourly_metrics": {
      "status": "ok",
      "last_data_ts": "2026-04-01T13:00:00Z",
      "is_stale": false,
      "message": null
    },
    "drift_artifacts": {
      "status": "warning",
      "last_data_ts": null,
      "is_stale": true,
      "message": "drift_report.json missing"
    },
    "model_artifacts": {
      "status": "ok",
      "last_data_ts": "2026-04-01T12:58:00Z",
      "is_stale": false,
      "message": null
    }
  }
}

Notes:
- overall enum: ok | degraded | critical
- component status enum: ok | warning | critical

## 5. Error and Empty-State Policy

Policy:
- Prefer 200 with empty data and source_status details when degradation is partial.
- Return 404 only if endpoint itself is invalid.
- Return 500 only for unexpected server exceptions.

Examples:
- No parquet rows in selected window: 200 with points=[]
- Missing drift_history file: 200 with events=[] and source_status.drift_history.ok=false
- Corrupted JSON parse: 200 if endpoint still constructible, include parse error in source_status

## 6. Freshness Rules

Defaults:
- dashboard/summary stale_after_seconds = 5400
- predictions stale_after_seconds = 5400
- drift/current stale_after_seconds = 10800
- drift/history stale_after_seconds = 10800
- system/health stale_after_seconds = 300

Computation:
- is_stale = now_utc - data_as_of > stale_after_seconds
- if data_as_of is null, is_stale=true

## 7. Implementation Mapping (for next phase)

- data/metrics/hourly_metrics/*.parquet -> summary, predictions, health
- artifacts/drift/drift_report.json -> drift/current, summary, health
- artifacts/drift/drift_history.jsonl -> drift/history
- artifacts/models/active_model.json -> summary, health

## 8. Acceptance Checklist (Phase 0 Complete)

1. Every Phase 1 endpoint has explicit request/response contract.
2. Envelope fields are standardized and mandatory.
3. Freshness semantics are fixed and testable.
4. Empty-state and degraded-state behavior is specified.
5. Contract is ready for FastAPI Pydantic model implementation.
