import { getDemoState, startDemoPipeline, stopDemoPipeline } from './state'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface DemoApiInput {
  path: string
  method: HttpMethod
}

const source = (ok: boolean, path: string, ts: string, error: string | null = null) => ({
  ok,
  path,
  last_modified: ts,
  error,
})

const noise = (seed: number) => {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return x - Math.floor(x)
}

const toIso = (deltaMs: number) => new Date(Date.now() + deltaMs).toISOString()

const pickHealthLevel = (driftDetected: boolean) => (driftDetected ? 'degraded' : 'ok')

function generatePredictions(limit: number, pipelineRunning: boolean) {
  if (!pipelineRunning) {
    return {
      points: [],
      summary: { count: 0, mae_mw: null, rmse_mw: null, mape_pct: null },
    }
  }

  const points = [] as Array<{
    timestamp: string
    actual_mw: number
    predicted_mw: number
    abs_error_mw: number
    model_version: string
  }>

  const count = Math.max(12, Math.min(limit, 48))
  const currentSlot = Math.floor(Date.now() / (3 * 1000))
  const growthDirection = currentSlot % 10 < 5 ? 1 : -1

  for (let i = count - 1; i >= 0; i--) {
    const seed = currentSlot - i
    const wave = Math.sin(seed / 2.7) * 52
    const trend = growthDirection * (count - i) * 7
    const baseline = 1120 + wave + trend

    const predicted = baseline + (noise(seed + 17) - 0.5) * 24
    const actual = predicted + (noise(seed + 41) - 0.5) * 70
    const absError = Math.abs(actual - predicted)

    points.push({
      timestamp: toIso(-(i + 1) * 10 * 60 * 1000),
      actual_mw: Number(actual.toFixed(2)),
      predicted_mw: Number(predicted.toFixed(2)),
      abs_error_mw: Number(absError.toFixed(2)),
      model_version: seed % 7 === 0 ? 'v2.2.0-candidate' : 'v2.1.0',
    })
  }

  const mae = points.reduce((sum, p) => sum + p.abs_error_mw, 0) / points.length
  const rmse = Math.sqrt(points.reduce((sum, p) => sum + p.abs_error_mw * p.abs_error_mw, 0) / points.length)
  const mape =
    points.reduce((sum, p) => sum + (p.actual_mw ? (p.abs_error_mw / p.actual_mw) * 100 : 0), 0) /
    points.length

  return {
    points,
    summary: {
      count: points.length,
      mae_mw: Number(mae.toFixed(2)),
      rmse_mw: Number(rmse.toFixed(2)),
      mape_pct: Number(mape.toFixed(2)),
    },
  }
}

export function getMockApiResponse({ path, method }: DemoApiInput): unknown | null {
  const state = getDemoState()
  if (!state.enabled) return null

  const now = new Date().toISOString()
  const pipelineRunning = state.pipelineRunning
  const cycle = Math.floor(Date.now() / (60 * 1000))
  const driftDetected = pipelineRunning && cycle % 6 === 0
  const predictionDriftScore = driftDetected ? 0.72 : 0.28
  const performanceDriftScore = driftDetected ? 0.69 : 0.24

  if (method === 'POST' && path === '/control/pipeline/start') {
    startDemoPipeline()
    return {
      action: 'start',
      dry_run: false,
      steps: [
        {
          service: 'pipeline',
          action: 'start',
          accepted: true,
          dry_run: false,
          status: 'running',
          message: 'Demo pipeline started',
          command: ['demo', 'pipeline', 'start'],
          pid: 4242,
        },
      ],
    }
  }

  if (method === 'POST' && path === '/control/pipeline/stop') {
    stopDemoPipeline()
    return {
      action: 'stop',
      dry_run: false,
      steps: [
        {
          service: 'pipeline',
          action: 'stop',
          accepted: true,
          dry_run: false,
          status: 'stopped',
          message: 'Demo pipeline stopped',
          command: ['demo', 'pipeline', 'stop'],
          pid: null,
        },
      ],
    }
  }

  if (method === 'GET' && path.startsWith('/predictions')) {
    const limitMatch = path.match(/limit=(\d+)/)
    const limit = limitMatch ? Number(limitMatch[1]) : 48
    const generated = generatePredictions(limit, pipelineRunning)

    return {
      generated_at: now,
      data_as_of: generated.points[generated.points.length - 1]?.timestamp ?? null,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        predictions: source(true, 'demo://predictions', now),
        hourly_metrics: source(true, 'demo://hourly_metrics', now),
      },
      data: {
        window: '24h',
        points: generated.points,
        summary: generated.summary,
      },
    }
  }

  if (method === 'GET' && path === '/dashboard/summary') {
    const generated = generatePredictions(24, pipelineRunning)
    const last = generated.points[generated.points.length - 1]

    return {
      generated_at: now,
      data_as_of: last?.timestamp ?? null,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        hourly_metrics: source(true, 'demo://hourly_metrics', now),
        drift_report: source(true, 'demo://drift_report', now),
        active_model: source(true, 'demo://active_model', now),
      },
      data: {
        latest_timestamp: last?.timestamp ?? null,
        actual_mw: last?.actual_mw ?? null,
        predicted_mw: last?.predicted_mw ?? null,
        abs_error_mw: last?.abs_error_mw ?? null,
        pct_error: last && last.actual_mw ? Number(((last.abs_error_mw / last.actual_mw) * 100).toFixed(2)) : null,
        drift_detected: driftDetected,
        active_model_version: driftDetected ? 'v2.2.0-candidate' : 'v2.1.0',
        health_level: pickHealthLevel(driftDetected),
      },
    }
  }

  if (method === 'GET' && path === '/drift/current') {
    return {
      generated_at: now,
      data_as_of: now,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        drift_report: source(true, 'demo://drift_report', now),
      },
      data: {
        drift_available: pipelineRunning,
        drift_detected: driftDetected,
        detected_at: driftDetected ? now : null,
        metrics: {
          prediction_drift: {
            detected: driftDetected,
            score: predictionDriftScore,
            threshold: 0.6,
          },
          performance_drift: {
            detected: driftDetected,
            score: performanceDriftScore,
            threshold: 0.55,
          },
        },
        feature_drift: [
          { feature: 'temperature', ks_score: 0.23, psi_score: 0.18, drifted: driftDetected },
          { feature: 'humidity', ks_score: 0.19, psi_score: 0.15, drifted: driftDetected && cycle % 2 === 0 },
          { feature: 'hour_of_day', ks_score: 0.09, psi_score: 0.05, drifted: false },
          { feature: 'weekday', ks_score: 0.04, psi_score: 0.03, drifted: false },
        ],
      },
    }
  }

  if (method === 'GET' && path.startsWith('/drift/history')) {
    const events = Array.from({ length: 20 }).map((_, idx) => {
      const drift = pipelineRunning && (cycle - idx) % 6 === 0
      return {
        timestamp: toIso(-(19 - idx) * 10 * 60 * 1000),
        drift_detected: drift,
        prediction_drift_score: drift ? 0.68 + noise(idx) * 0.08 : 0.22 + noise(idx) * 0.12,
        performance_drift_score: drift ? 0.62 + noise(idx + 7) * 0.09 : 0.2 + noise(idx + 9) * 0.11,
      }
    })

    return {
      generated_at: now,
      data_as_of: events[events.length - 1]?.timestamp ?? now,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        drift_history: source(true, 'demo://drift_history', now),
      },
      data: {
        events,
        count: events.length,
      },
    }
  }

  if (method === 'GET' && path === '/system/health') {
    const overall = !pipelineRunning ? 'degraded' : driftDetected ? 'degraded' : 'ok'

    return {
      generated_at: now,
      data_as_of: now,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        hourly_metrics: source(true, 'demo://hourly_metrics', now),
        drift_report: source(true, 'demo://drift_report', now),
        active_model: source(true, 'demo://active_model', now),
      },
      data: {
        overall,
        components: {
          hourly_metrics: {
            status: pipelineRunning ? 'ok' : 'warning',
            last_data_ts: pipelineRunning ? now : null,
            is_stale: !pipelineRunning,
            message: pipelineRunning ? 'Streaming metrics healthy' : 'Pipeline is stopped',
          },
          drift_artifacts: {
            status: driftDetected ? 'warning' : 'ok',
            last_data_ts: now,
            is_stale: false,
            message: driftDetected ? 'Drift alerts are active' : 'Drift scores within threshold',
          },
          model_artifacts: {
            status: 'ok',
            last_data_ts: now,
            is_stale: false,
            message: 'Model registry and active pointer are healthy',
          },
        },
      },
    }
  }

  if (method === 'GET' && path === '/models/active') {
    return {
      generated_at: now,
      data_as_of: now,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        active_model: source(true, 'demo://active_model', now),
      },
      data: {
        active_model_version: driftDetected ? 'v2.2.0-candidate' : 'v2.1.0',
        active_model_path: driftDetected ? 'artifacts/models/model_v2.joblib' : 'artifacts/models/model_v1.joblib',
        previous_model_version: driftDetected ? 'v2.1.0' : 'v2.0.4',
        previous_model_path: 'artifacts/models/model_v1.joblib',
        promoted_at_utc: driftDetected ? now : toIso(-(3 * 60 * 60 * 1000)),
      },
    }
  }

  if (method === 'GET' && path.startsWith('/models/versions')) {
    const events = Array.from({ length: 12 }).map((_, idx) => {
      const promote = pipelineRunning && (cycle - idx) % 9 === 0
      return {
        timestamp: toIso(-(11 - idx) * 20 * 60 * 1000),
        event_type: promote ? 'promotion' : 'evaluation',
        decision: promote ? 'promote' : 'hold',
        reason: promote
          ? 'Candidate outperformed active model on rolling MAE.'
          : 'Candidate improvement not yet stable for promotion.',
        current_active_model_version: promote ? 'v2.2.0-candidate' : 'v2.1.0',
        target_model_version: 'v2.2.0-candidate',
        pointer_updated: promote,
      }
    })

    return {
      generated_at: now,
      data_as_of: now,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        promotion_log: source(true, 'demo://promotion_log', now),
        candidate_report: source(true, 'demo://candidate_report', now),
        active_model: source(true, 'demo://active_model', now),
      },
      data: {
        active_model_version: driftDetected ? 'v2.2.0-candidate' : 'v2.1.0',
        candidate_version: 'v2.2.0-candidate',
        candidate_ready_for_promotion: pipelineRunning,
        events,
        count: events.length,
      },
    }
  }

  if (method === 'GET' && path.startsWith('/self-healing/status')) {
    const decisions = Array.from({ length: 10 }).map((_, idx) => {
      const trigger = pipelineRunning && (cycle - idx) % 6 === 0
      return {
        timestamp: toIso(-(9 - idx) * 15 * 60 * 1000),
        decision: trigger ? 'retrain_triggered' : 'monitor',
        reason: trigger
          ? 'Consecutive drift threshold reached; retrain pipeline scheduled.'
          : 'Monitoring drift counters and candidate quality.',
        dry_run: false,
        command_ok: true,
        required_consecutive_drifts: 3,
      }
    })

    return {
      generated_at: now,
      data_as_of: now,
      stale_after_seconds: 300,
      is_stale: false,
      source_status: {
        trigger_decisions: source(true, 'demo://trigger_decisions', now),
        candidate_report: source(true, 'demo://candidate_report', now),
        monitor_state: source(true, 'demo://monitor_state', now),
      },
      data: {
        latest_decision: decisions[decisions.length - 1]?.decision ?? 'monitor',
        latest_reason: decisions[decisions.length - 1]?.reason ?? 'Monitoring',
        candidate_ready_for_promotion: pipelineRunning,
        consecutive_drift_count: driftDetected ? 3 : 1,
        required_consecutive_drifts: 3,
        last_retrain_at_utc: driftDetected ? now : toIso(-(2 * 60 * 60 * 1000)),
        decisions,
        count: decisions.length,
      },
    }
  }

  if (method === 'GET' && path === '/control/services') {
    const runningStatus = pipelineRunning ? 'running' : 'stopped'

    return {
      services: [
        {
          service: 'producer',
          status: runningStatus,
          allowed_actions: ['start', 'stop', 'restart'],
          managed_process: true,
          pid: pipelineRunning ? 4301 : null,
          last_started_at: state.pipelineStartedAt,
          last_stopped_at: pipelineRunning ? null : now,
          last_exit_code: pipelineRunning ? null : 0,
          last_error: null,
        },
        {
          service: 'spark_predictions',
          status: runningStatus,
          allowed_actions: ['start', 'stop', 'restart'],
          managed_process: true,
          pid: pipelineRunning ? 4302 : null,
          last_started_at: state.pipelineStartedAt,
          last_stopped_at: pipelineRunning ? null : now,
          last_exit_code: pipelineRunning ? null : 0,
          last_error: null,
        },
        {
          service: 'drift_monitor',
          status: pipelineRunning ? (driftDetected ? 'running' : 'running') : 'stopped',
          allowed_actions: ['start', 'stop', 'restart'],
          managed_process: true,
          pid: pipelineRunning ? 4303 : null,
          last_started_at: state.pipelineStartedAt,
          last_stopped_at: pipelineRunning ? null : now,
          last_exit_code: pipelineRunning ? null : 0,
          last_error: driftDetected ? 'Alert mode enabled due to drift spikes' : null,
        },
      ],
    }
  }

  if (method === 'GET' && path.includes('/control/services/') && path.endsWith('/logs?tail=200')) {
    const serviceName = path.split('/')[3] ?? 'service'
    return {
      service: serviceName,
      lines: [
        { timestamp: toIso(-90000), level: 'info', message: `[${serviceName}] heartbeat ok` },
        { timestamp: toIso(-60000), level: driftDetected ? 'warning' : 'info', message: driftDetected ? `[${serviceName}] drift threshold exceeded` : `[${serviceName}] processing batch` },
        { timestamp: toIso(-30000), level: 'info', message: `[${serviceName}] latency stable` },
      ],
      line_count: 3,
    }
  }

  if (method === 'POST' && path.includes('/control/services/')) {
    const segments = path.split('/')
    const serviceName = segments[3] ?? 'service'
    const action = segments[4] as 'start' | 'stop' | 'restart'

    return {
      service: serviceName,
      action,
      accepted: true,
      dry_run: false,
      status: action === 'stop' ? 'stopped' : 'running',
      message: `Demo action ${action} accepted for ${serviceName}`,
      command: ['demo', serviceName, action],
      pid: action === 'stop' ? null : 5001,
    }
  }

  return null
}
