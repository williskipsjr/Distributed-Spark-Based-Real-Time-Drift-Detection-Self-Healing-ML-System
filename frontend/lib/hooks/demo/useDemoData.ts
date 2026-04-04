import { useState, useEffect } from 'react'
import { DEMO_STATE_EVENT, getDemoState } from '@/lib/demo/state'

interface DemoPoint {
  timestamp: string
  predicted_mw: number
  actual_mw: number
  abs_error_mw: number
  projection_mw: number
}

interface DemoSummary {
  actual_mw: number
  predicted_mw: number
  abs_error_mw: number
  pct_error: number | null
  health_level: 'ok' | 'degraded' | 'critical'
  active_model_version: string
  drift_detected: boolean
  latest_timestamp: string
}

interface DemoPredictions {
  points: DemoPoint[]
  window: string
  summary: {
    mae_mw: number | null
    rmse_mw: number | null
    mape_pct: number | null
  }
}

interface RecordedStreamPoint extends DemoPoint {
  model_version: string
}

interface RecordedStreamResponse {
  generated_at: string
  data_as_of: string | null
  stale_after_seconds: number
  is_stale: boolean
  source_status: {
    predictions: {
      ok: boolean
      path: string
      last_modified: string | null
      error: string | null
    }
    hourly_metrics: {
      ok: boolean
      path: string
      last_modified: string | null
      error: string | null
    }
  }
  data: {
    window: '24h'
    points: RecordedStreamPoint[]
    summary: {
      count: number
      mae_mw: number | null
      rmse_mw: number | null
      mape_pct: number | null
    }
    stream_cursor: number
    total_points: number
  }
}

async function fetchRecordedStream(limit: number, tick: number): Promise<RecordedStreamResponse> {
  const response = await fetch(`/api/demo/load-stream?limit=${limit}&tick=${tick}`, {
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`Recorded stream request failed with HTTP ${response.status}`)
  }

  return (await response.json()) as RecordedStreamResponse
}

function buildFallbackStream(tick: number, limit: number): DemoPredictions {
  const points: DemoPoint[] = []
  const normalizedLimit = Math.max(1, Math.min(limit, 48))
  const baseTimestamp = new Date(Date.UTC(2020, 8, 26, 0, 0, 0))

  for (let index = 0; index < normalizedLimit; index++) {
    const offset = (tick + index) * 60 * 60 * 1000
    const timestamp = new Date(baseTimestamp.getTime() + offset)
    const wave = Math.sin((tick + index) / 2.8) * 42
    const trend = (tick + index) * 6
    const actual = 140000 + wave + trend
    const predicted = actual - 220 + Math.cos((tick + index) / 3.4) * 110

    points.push({
      timestamp: timestamp.toISOString(),
      predicted_mw: Math.round(predicted * 10) / 10,
      actual_mw: Math.round(actual * 10) / 10,
      abs_error_mw: Math.abs(predicted - actual),
      projection_mw: Math.round((predicted + 180) * 10) / 10,
    })
  }

  const mae = points.reduce((sum, point) => sum + point.abs_error_mw, 0) / points.length
  const rmse = Math.sqrt(points.reduce((sum, point) => sum + point.abs_error_mw * point.abs_error_mw, 0) / points.length)
  const mape =
    points.reduce((sum, point) => sum + (point.actual_mw ? (point.abs_error_mw / point.actual_mw) * 100 : 0), 0) /
    points.length

  return {
    points,
    window: '24h',
    summary: {
      mae_mw: Number(mae.toFixed(2)),
      rmse_mw: Number(rmse.toFixed(2)),
      mape_pct: Number(mape.toFixed(2)),
    },
  }
}

export function useDemoData() {
  const [summaryData, setSummaryData] = useState<DemoSummary>({
    actual_mw: 140000,
    predicted_mw: 139500,
    abs_error_mw: 500,
    pct_error: 0.36,
    health_level: 'ok',
    active_model_version: 'v-recorded-pjm-parquet',
    drift_detected: false,
    latest_timestamp: new Date().toISOString(),
  })

  const [predictionsData, setPredictionsData] = useState<DemoPredictions>({
    points: [],
    window: '24h',
    summary: {
      mae_mw: 42.5,
      rmse_mw: 56.3,
      mape_pct: 3.8,
    },
  })

  const [pipelineRunning, setPipelineRunning] = useState<boolean>(() => getDemoState().pipelineRunning)
  const [streamTick, setStreamTick] = useState(0)

  useEffect(() => {
    const sync = () => {
      setPipelineRunning(getDemoState().pipelineRunning)
    }

    sync()
    if (typeof window !== 'undefined') {
      window.addEventListener(DEMO_STATE_EVENT, sync)
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener(DEMO_STATE_EVENT, sync)
      }
    }
  }, [])

  useEffect(() => {
    if (!pipelineRunning) {
      return
    }

    const interval = setInterval(() => {
      setStreamTick((current) => current + 1)
    }, 3000) // Add new data point every 3 seconds

    return () => clearInterval(interval)
  }, [pipelineRunning])

  useEffect(() => {
    if (!pipelineRunning) {
      return
    }

    let cancelled = false

    const loadRecordedDemo = async () => {
      try {
        const response = await fetchRecordedStream(48, streamTick)
        if (cancelled) {
          return
        }

        setPredictionsData({
          points: response.data.points.map((point) => ({
            timestamp: point.timestamp,
            predicted_mw: point.predicted_mw,
            actual_mw: point.actual_mw,
            abs_error_mw: point.abs_error_mw,
            projection_mw: point.projection_mw,
          })),
          window: response.data.window,
          summary: {
            mae_mw: response.data.summary.mae_mw ?? 0,
            rmse_mw: response.data.summary.rmse_mw ?? 0,
            mape_pct: response.data.summary.mape_pct ?? 0,
          },
        })

        const lastPoint = response.data.points[response.data.points.length - 1]
        if (lastPoint) {
          setSummaryData({
            actual_mw: lastPoint.actual_mw,
            predicted_mw: lastPoint.predicted_mw,
            abs_error_mw: lastPoint.abs_error_mw,
            pct_error: lastPoint.actual_mw ? Number(((lastPoint.abs_error_mw / lastPoint.actual_mw) * 100).toFixed(2)) : null,
            health_level: lastPoint.abs_error_mw > 12000 ? 'degraded' : 'ok',
            active_model_version: lastPoint.model_version,
            drift_detected: lastPoint.abs_error_mw > 15000,
            latest_timestamp: lastPoint.timestamp,
          })
        }
      } catch {
        if (!cancelled) {
          const fallback = buildFallbackStream(streamTick, 48)
          setPredictionsData(fallback)
          const lastPoint = fallback.points[fallback.points.length - 1]
          if (lastPoint) {
            setSummaryData({
              actual_mw: lastPoint.actual_mw,
              predicted_mw: lastPoint.predicted_mw,
              abs_error_mw: lastPoint.abs_error_mw,
              pct_error: lastPoint.actual_mw ? Number(((lastPoint.abs_error_mw / lastPoint.actual_mw) * 100).toFixed(2)) : null,
              health_level: 'ok',
              active_model_version: 'v-fallback-demo',
              drift_detected: false,
              latest_timestamp: lastPoint.timestamp,
            })
          }
        }
      }
    }

    void loadRecordedDemo()

    return () => {
      cancelled = true
    }
  }, [pipelineRunning, streamTick])

  const visiblePredictionsData = pipelineRunning
    ? predictionsData
    : {
        ...predictionsData,
        points: [],
      }

  return {
    summary: {
      data: {
        data: summaryData,
        generated_at: new Date().toISOString(),
        data_as_of: summaryData.latest_timestamp,
        stale_after_seconds: 300,
        is_stale: false,
        source_status: {
          hourly_metrics: {
            ok: true,
            path: 'data/metrics/hourly_metrics',
            last_modified: summaryData.latest_timestamp,
            error: null,
          },
          drift_report: {
            ok: true,
            path: 'data/processed/pjm_supervised.parquet',
            last_modified: summaryData.latest_timestamp,
            error: null,
          },
          active_model: {
            ok: true,
            path: 'v-recorded-pjm-parquet',
            last_modified: summaryData.latest_timestamp,
            error: null,
          },
        },
      },
      isLoading: false,
      error: null,
    },
    predictions: {
      data: {
        data: visiblePredictionsData,
        generated_at: new Date().toISOString(),
        data_as_of: visiblePredictionsData.points[visiblePredictionsData.points.length - 1]?.timestamp ?? null,
        stale_after_seconds: 300,
        is_stale: false,
        source_status: {
          predictions: {
            ok: true,
            path: 'data/processed/pjm_supervised.parquet',
            last_modified: visiblePredictionsData.points[visiblePredictionsData.points.length - 1]?.timestamp ?? null,
            error: null,
          },
          hourly_metrics: {
            ok: true,
            path: 'data/metrics/hourly_metrics',
            last_modified: visiblePredictionsData.points[visiblePredictionsData.points.length - 1]?.timestamp ?? null,
            error: null,
          },
        },
      },
      isLoading: false,
      error: null,
    },
  }
}
