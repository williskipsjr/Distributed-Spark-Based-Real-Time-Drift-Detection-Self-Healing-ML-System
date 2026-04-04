from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class SourceStatusEntry(BaseModel):
    ok: bool
    path: str
    last_modified: str | None
    error: str | None


class DashboardSummaryData(BaseModel):
    latest_timestamp: str | None
    actual_mw: float | None
    predicted_mw: float | None
    abs_error_mw: float | None
    pct_error: float | None
    drift_detected: bool
    active_model_version: str | None
    health_level: Literal["ok", "degraded", "critical"]


class DashboardSummarySourceStatus(BaseModel):
    hourly_metrics: SourceStatusEntry
    drift_report: SourceStatusEntry
    active_model: SourceStatusEntry


class DashboardSummaryEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: DashboardSummarySourceStatus
    data: DashboardSummaryData


class PredictionPoint(BaseModel):
    timestamp: str | None
    actual_mw: float | None
    predicted_mw: float | None
    abs_error_mw: float | None
    model_version: str | None


class PredictionSummary(BaseModel):
    count: int
    mae_mw: float | None
    rmse_mw: float | None
    mape_pct: float | None


class PredictionsData(BaseModel):
    window: Literal["24h", "7d", "30d"]
    points: list[PredictionPoint]
    summary: PredictionSummary


class PredictionsSourceStatus(BaseModel):
    predictions: SourceStatusEntry
    hourly_metrics: SourceStatusEntry | None = None


class PredictionsEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: PredictionsSourceStatus
    data: PredictionsData


class DriftMetricEntry(BaseModel):
    detected: bool
    score: float | None
    threshold: float | None


class FeatureDriftEntry(BaseModel):
    feature: str | None = None
    ks_score: float | None = None
    psi_score: float | None = None
    drifted: bool | None = None


class DriftCurrentMetrics(BaseModel):
    prediction_drift: DriftMetricEntry
    performance_drift: DriftMetricEntry


class DriftCurrentData(BaseModel):
    drift_available: bool
    drift_detected: bool
    detected_at: str | None
    metrics: DriftCurrentMetrics
    feature_drift: list[FeatureDriftEntry]


class DriftCurrentSourceStatus(BaseModel):
    drift_report: SourceStatusEntry


class DriftCurrentEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: DriftCurrentSourceStatus
    data: DriftCurrentData


class DriftHistoryEvent(BaseModel):
    timestamp: str | None
    drift_detected: bool
    prediction_drift_score: float | None
    performance_drift_score: float | None


class DriftHistoryData(BaseModel):
    events: list[DriftHistoryEvent]
    count: int


class DriftHistorySourceStatus(BaseModel):
    drift_history: SourceStatusEntry


class DriftHistoryEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: DriftHistorySourceStatus
    data: DriftHistoryData


class HealthComponent(BaseModel):
    status: Literal["ok", "warning", "critical"]
    last_data_ts: str | None
    is_stale: bool
    message: str | None


class SystemHealthComponents(BaseModel):
    hourly_metrics: HealthComponent
    drift_artifacts: HealthComponent
    model_artifacts: HealthComponent


class SystemHealthData(BaseModel):
    overall: Literal["ok", "degraded", "critical"]
    components: SystemHealthComponents


class SystemHealthSourceStatus(BaseModel):
    hourly_metrics: SourceStatusEntry
    drift_report: SourceStatusEntry
    active_model: SourceStatusEntry


class SystemHealthEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: SystemHealthSourceStatus
    data: SystemHealthData


class ModelsActiveData(BaseModel):
    active_model_version: str | None
    active_model_path: str | None
    previous_model_version: str | None
    previous_model_path: str | None
    promoted_at_utc: str | None


class ModelsActiveSourceStatus(BaseModel):
    active_model: SourceStatusEntry


class ModelsActiveEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: ModelsActiveSourceStatus
    data: ModelsActiveData


class ModelVersionEvent(BaseModel):
    timestamp: str | None
    event_type: str | None
    decision: str | None
    reason: str | None
    current_active_model_version: str | None
    target_model_version: str | None
    pointer_updated: bool | None


class ModelsVersionsData(BaseModel):
    active_model_version: str | None
    candidate_version: str | None
    candidate_ready_for_promotion: bool
    events: list[ModelVersionEvent]
    count: int


class ModelsVersionsSourceStatus(BaseModel):
    promotion_log: SourceStatusEntry
    candidate_report: SourceStatusEntry
    active_model: SourceStatusEntry


class ModelsVersionsEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: ModelsVersionsSourceStatus
    data: ModelsVersionsData


class SelfHealingDecisionEvent(BaseModel):
    timestamp: str | None
    decision: str | None
    reason: str | None
    dry_run: bool | None
    command_ok: bool | None
    required_consecutive_drifts: int | None = None


class SelfHealingStatusData(BaseModel):
    latest_decision: str | None
    latest_reason: str | None
    candidate_ready_for_promotion: bool
    consecutive_drift_count: int | None
    required_consecutive_drifts: int | None
    last_retrain_at_utc: str | None
    decisions: list[SelfHealingDecisionEvent]
    count: int


class SelfHealingStatusSourceStatus(BaseModel):
    trigger_decisions: SourceStatusEntry
    candidate_report: SourceStatusEntry
    monitor_state: SourceStatusEntry


class SelfHealingStatusEnvelope(BaseModel):
    generated_at: str | None
    data_as_of: str | None
    stale_after_seconds: int
    is_stale: bool
    source_status: SelfHealingStatusSourceStatus
    data: SelfHealingStatusData


class ControlActionRequest(BaseModel):
    dry_run: bool = True
    profile: Literal["default", "python", "wsl", "docker"] = "default"
    args: dict[str, Any] = Field(default_factory=dict)


class ControlServiceState(BaseModel):
    service: str
    status: Literal["stopped", "starting", "running", "stopping", "failed"]
    allowed_actions: list[str]
    managed_process: bool
    pid: int | None = None
    last_started_at: str | None = None
    last_stopped_at: str | None = None
    last_exit_code: int | None = None
    last_error: str | None = None


class ControlServiceCatalog(BaseModel):
    services: list[ControlServiceState]


class ControlServiceActionResponse(BaseModel):
    service: str
    action: Literal["start", "stop", "restart"]
    accepted: bool
    dry_run: bool
    status: Literal["stopped", "starting", "running", "stopping", "failed"]
    message: str
    command: list[str] | None = None
    pid: int | None = None


class ControlServiceLogsResponse(BaseModel):
    service: str
    lines: list[str]
    line_count: int


class ControlPipelineResponse(BaseModel):
    action: Literal["start", "stop"]
    dry_run: bool
    steps: list[ControlServiceActionResponse]
