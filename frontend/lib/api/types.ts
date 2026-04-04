import { z } from 'zod'

export const SourceStatusEntrySchema = z.object({
  ok: z.boolean(),
  path: z.string(),
  last_modified: z.string().datetime().nullable(),
  error: z.string().nullable(),
})

export type SourceStatusEntry = z.infer<typeof SourceStatusEntrySchema>

export const ApiEnvelopeSchema = z.object({
  generated_at: z.string().datetime().nullable(),
  data_as_of: z.string().datetime().nullable(),
  stale_after_seconds: z.number().int(),
  is_stale: z.boolean(),
  source_status: z.record(z.string(), SourceStatusEntrySchema),
  data: z.unknown(),
})

export type ApiEnvelope<T = unknown> = z.infer<typeof ApiEnvelopeSchema> & {
  data: T
}

export const DashboardSummaryDataSchema = z.object({
  latest_timestamp: z.string().datetime().nullable(),
  actual_mw: z.number().nullable(),
  predicted_mw: z.number().nullable(),
  abs_error_mw: z.number().nullable(),
  pct_error: z.number().nullable(),
  drift_detected: z.boolean(),
  active_model_version: z.string().nullable(),
  health_level: z.enum(['ok', 'degraded', 'critical']),
})

export const DashboardSummaryEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    hourly_metrics: SourceStatusEntrySchema,
    drift_report: SourceStatusEntrySchema,
    active_model: SourceStatusEntrySchema,
  }),
  data: DashboardSummaryDataSchema,
})

export type DashboardSummaryData = z.infer<typeof DashboardSummaryDataSchema>
export type DashboardSummaryEnvelope = z.infer<typeof DashboardSummaryEnvelopeSchema>

export const PredictionPointSchema = z.object({
  timestamp: z.string().datetime().nullable(),
  actual_mw: z.number().nullable(),
  predicted_mw: z.number().nullable(),
  abs_error_mw: z.number().nullable(),
  model_version: z.string().nullable(),
})

export const PredictionSummarySchema = z.object({
  count: z.number().int(),
  mae_mw: z.number().nullable(),
  rmse_mw: z.number().nullable(),
  mape_pct: z.number().nullable(),
})

export const PredictionsDataSchema = z.object({
  window: z.enum(['24h', '7d', '30d']),
  points: z.array(PredictionPointSchema),
  summary: PredictionSummarySchema,
})

export const PredictionsEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    predictions: SourceStatusEntrySchema,
    hourly_metrics: SourceStatusEntrySchema.optional(),
  }),
  data: PredictionsDataSchema,
})

export type PredictionPoint = z.infer<typeof PredictionPointSchema>
export type PredictionSummary = z.infer<typeof PredictionSummarySchema>
export type PredictionsData = z.infer<typeof PredictionsDataSchema>
export type PredictionsEnvelope = z.infer<typeof PredictionsEnvelopeSchema>

export const DriftMetricSchema = z.object({
  detected: z.boolean(),
  score: z.number().nullable(),
  threshold: z.number().nullable(),
})

export const DriftFeatureSchema = z.object({
  feature: z.string().nullable(),
  ks_score: z.number().nullable(),
  psi_score: z.number().nullable(),
  drifted: z.boolean().nullable(),
})

export const DriftCurrentDataSchema = z.object({
  drift_available: z.boolean(),
  drift_detected: z.boolean(),
  detected_at: z.string().datetime().nullable(),
  metrics: z.object({
    prediction_drift: DriftMetricSchema,
    performance_drift: DriftMetricSchema,
  }),
  feature_drift: z.array(DriftFeatureSchema),
})

export const DriftCurrentEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    drift_report: SourceStatusEntrySchema,
  }),
  data: DriftCurrentDataSchema,
})

export const DriftHistoryEventSchema = z.object({
  timestamp: z.string().datetime().nullable(),
  drift_detected: z.boolean(),
  prediction_drift_score: z.number().nullable(),
  performance_drift_score: z.number().nullable(),
})

export const DriftHistoryDataSchema = z.object({
  events: z.array(DriftHistoryEventSchema),
  count: z.number().int(),
})

export const DriftHistoryEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    drift_history: SourceStatusEntrySchema,
  }),
  data: DriftHistoryDataSchema,
})

export type DriftMetric = z.infer<typeof DriftMetricSchema>
export type DriftFeature = z.infer<typeof DriftFeatureSchema>
export type DriftCurrentData = z.infer<typeof DriftCurrentDataSchema>
export type DriftCurrentEnvelope = z.infer<typeof DriftCurrentEnvelopeSchema>
export type DriftHistoryEvent = z.infer<typeof DriftHistoryEventSchema>
export type DriftHistoryData = z.infer<typeof DriftHistoryDataSchema>
export type DriftHistoryEnvelope = z.infer<typeof DriftHistoryEnvelopeSchema>

export const HealthComponentSchema = z.object({
  status: z.enum(['ok', 'warning', 'critical']),
  last_data_ts: z.string().datetime().nullable(),
  is_stale: z.boolean(),
  message: z.string().nullable(),
})

export const SystemHealthDataSchema = z.object({
  overall: z.enum(['ok', 'degraded', 'critical']),
  components: z.object({
    hourly_metrics: HealthComponentSchema,
    drift_artifacts: HealthComponentSchema,
    model_artifacts: HealthComponentSchema,
  }),
})

export const SystemHealthEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    hourly_metrics: SourceStatusEntrySchema,
    drift_report: SourceStatusEntrySchema,
    active_model: SourceStatusEntrySchema,
  }),
  data: SystemHealthDataSchema,
})

export type HealthComponent = z.infer<typeof HealthComponentSchema>
export type SystemHealthData = z.infer<typeof SystemHealthDataSchema>
export type SystemHealthEnvelope = z.infer<typeof SystemHealthEnvelopeSchema>

export const ModelsActiveDataSchema = z.object({
  active_model_version: z.string().nullable(),
  active_model_path: z.string().nullable(),
  previous_model_version: z.string().nullable(),
  previous_model_path: z.string().nullable(),
  promoted_at_utc: z.string().datetime().nullable(),
})

export const ModelsActiveEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    active_model: SourceStatusEntrySchema,
  }),
  data: ModelsActiveDataSchema,
})

export type ModelsActiveData = z.infer<typeof ModelsActiveDataSchema>
export type ModelsActiveEnvelope = z.infer<typeof ModelsActiveEnvelopeSchema>

export const ModelVersionEventSchema = z.object({
  timestamp: z.string().datetime().nullable(),
  event_type: z.string().nullable(),
  decision: z.string().nullable(),
  reason: z.string().nullable(),
  current_active_model_version: z.string().nullable(),
  target_model_version: z.string().nullable(),
  pointer_updated: z.boolean().nullable(),
})

export const ModelsVersionsDataSchema = z.object({
  active_model_version: z.string().nullable(),
  candidate_version: z.string().nullable(),
  candidate_ready_for_promotion: z.boolean(),
  events: z.array(ModelVersionEventSchema),
  count: z.number().int(),
})

export const ModelsVersionsEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    promotion_log: SourceStatusEntrySchema,
    candidate_report: SourceStatusEntrySchema,
    active_model: SourceStatusEntrySchema,
  }),
  data: ModelsVersionsDataSchema,
})

export type ModelVersionEvent = z.infer<typeof ModelVersionEventSchema>
export type ModelsVersionsData = z.infer<typeof ModelsVersionsDataSchema>
export type ModelsVersionsEnvelope = z.infer<typeof ModelsVersionsEnvelopeSchema>

export const SelfHealingDecisionEventSchema = z.object({
  timestamp: z.string().datetime().nullable(),
  decision: z.string().nullable(),
  reason: z.string().nullable(),
  dry_run: z.boolean().nullable(),
  command_ok: z.boolean().nullable(),
  required_consecutive_drifts: z.number().int().nullable(),
})

export const SelfHealingStatusDataSchema = z.object({
  latest_decision: z.string().nullable(),
  latest_reason: z.string().nullable(),
  candidate_ready_for_promotion: z.boolean(),
  consecutive_drift_count: z.number().int().nullable(),
  required_consecutive_drifts: z.number().int().nullable(),
  last_retrain_at_utc: z.string().datetime().nullable(),
  decisions: z.array(SelfHealingDecisionEventSchema),
  count: z.number().int(),
})

export const SelfHealingStatusEnvelopeSchema = ApiEnvelopeSchema.extend({
  source_status: z.object({
    trigger_decisions: SourceStatusEntrySchema,
    candidate_report: SourceStatusEntrySchema,
    monitor_state: SourceStatusEntrySchema,
  }),
  data: SelfHealingStatusDataSchema,
})

export type SelfHealingDecisionEvent = z.infer<typeof SelfHealingDecisionEventSchema>
export type SelfHealingStatusData = z.infer<typeof SelfHealingStatusDataSchema>
export type SelfHealingStatusEnvelope = z.infer<typeof SelfHealingStatusEnvelopeSchema>

export const ControlActionRequestSchema = z.object({
  dry_run: z.boolean().default(true),
  profile: z.enum(['default', 'python', 'wsl', 'docker']).default('default'),
  args: z.record(z.unknown()).default({}),
})

export type ControlActionRequest = z.infer<typeof ControlActionRequestSchema>

export const ControlServiceStateSchema = z.object({
  service: z.string(),
  status: z.enum(['stopped', 'starting', 'running', 'stopping', 'failed']),
  allowed_actions: z.array(z.string()),
  managed_process: z.boolean(),
  pid: z.number().int().nullable().optional(),
  last_started_at: z.string().datetime().nullable(),
  last_stopped_at: z.string().datetime().nullable(),
  last_exit_code: z.number().int().nullable(),
  last_error: z.string().nullable(),
})

export const ControlServiceCatalogSchema = z.object({
  services: z.array(ControlServiceStateSchema),
})

export type ControlServiceState = z.infer<typeof ControlServiceStateSchema>
export type ControlServiceCatalog = z.infer<typeof ControlServiceCatalogSchema>

export const ControlLogLineSchema = z.object({
  timestamp: z.string().datetime(),
  level: z.enum(['debug', 'info', 'warning', 'error']),
  message: z.string(),
})

export const ControlServiceLogsResponseSchema = z.object({
  service: z.string(),
  lines: z.array(ControlLogLineSchema),
  line_count: z.number().int(),
})

export type ControlLogLine = z.infer<typeof ControlLogLineSchema>
export type ControlServiceLogsResponse = z.infer<typeof ControlServiceLogsResponseSchema>

export const ControlServiceActionResponseSchema = z.object({
  service: z.string(),
  action: z.enum(['start', 'stop', 'restart']),
  accepted: z.boolean(),
  dry_run: z.boolean(),
  status: z.enum(['stopped', 'starting', 'running', 'stopping', 'failed']),
  message: z.string(),
  command: z.array(z.string()).nullable(),
  pid: z.number().int().nullable().optional(),
})

export type ControlServiceActionResponse = z.infer<typeof ControlServiceActionResponseSchema>

export const ControlPipelineResponseSchema = z.object({
  action: z.enum(['start', 'stop']),
  dry_run: z.boolean(),
  steps: z.array(ControlServiceActionResponseSchema),
})

export type ControlPipelineResponse = z.infer<typeof ControlPipelineResponseSchema>
