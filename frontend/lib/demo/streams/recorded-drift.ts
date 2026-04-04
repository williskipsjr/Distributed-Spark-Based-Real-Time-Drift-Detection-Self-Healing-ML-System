import path from 'node:path'
import { readdir, stat } from 'node:fs/promises'

type ParquetRow = Record<string, unknown>

interface MetricRow {
  timestamp_hour: string
  active_model_version: string
  mean_prediction: number
  max_prediction: number
  min_prediction: number
  std_prediction: number | null
  mean_error: number
  max_error: number
  record_count: number
}

interface SupervisedRow {
  timestamp: string
  load_mw: number
  hour_of_day: number | null
  day_of_week: number | null
  month: number | null
  is_weekend: number | null
  lag_1: number | null
  lag_24: number | null
  lag_168: number | null
  rolling_24: number | null
  rolling_168: number | null
}

export interface RecordedDriftResponse {
  generated_at: string
  current: {
    generated_at: string
    data_as_of: string | null
    stale_after_seconds: number
    is_stale: boolean
    source_status: {
      drift_report: {
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
      drift_available: boolean
      drift_detected: boolean
      detected_at: string | null
      metrics: {
        prediction_drift: {
          detected: boolean
          score: number | null
          threshold: number | null
        }
        performance_drift: {
          detected: boolean
          score: number | null
          threshold: number | null
        }
      }
      feature_drift: Array<{
        feature: string | null
        ks_score: number | null
        psi_score: number | null
        drifted: boolean | null
      }>
    }
  }
  history: {
    generated_at: string
    data_as_of: string | null
    stale_after_seconds: number
    is_stale: boolean
    source_status: {
      drift_history: {
        ok: boolean
        path: string
        last_modified: string | null
        error: string | null
      }
    }
    data: {
      events: Array<{
        timestamp: string
        drift_detected: boolean
        prediction_drift_score: number | null
        performance_drift_score: number | null
      }>
      count: number
    }
  }
}

const DATASET_ROOT = path.resolve(process.cwd(), '..', 'data')
const SUPERVISED_DATASET_PATH = path.resolve(DATASET_ROOT, 'processed', 'pjm_supervised.parquet')
const METRICS_ROOT = path.resolve(DATASET_ROOT, 'metrics', 'hourly_metrics')

const METRICS_DISPLAY_PATH = path.posix.join('data', 'metrics', 'hourly_metrics')
const DATASET_DISPLAY_PATH = path.posix.join('data', 'processed', 'pjm_supervised.parquet')

const parquetModulePromise = import('parquetjs-lite')

let metricsRowsPromise: Promise<MetricRow[]> | null = null
let supervisedRowsPromise: Promise<SupervisedRow[]> | null = null

function toNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function toNullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function toIsoTimestamp(value: unknown): string | null {
  if (value instanceof Date) {
    return value.toISOString()
  }

  if (typeof value === 'string') {
    const normalized = value.includes('T') ? value : value.replace(' ', 'T')
    const parsed = new Date(normalized.endsWith('Z') ? normalized : `${normalized}Z`)
    return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
  }

  return null
}

async function listParquetFiles(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    const fullPath = path.join(root, entry.name)
    if (entry.isDirectory()) {
      files.push(...(await listParquetFiles(fullPath)))
      continue
    }

    if (entry.isFile() && entry.name.endsWith('.parquet')) {
      const fileStat = await stat(fullPath)
      if (fileStat.size > 0) {
        files.push(fullPath)
      }
    }
  }

  return files
}

async function readParquetRows<T>(filePath: string, mapRow: (row: ParquetRow) => T | null): Promise<T[]> {
  const parquetModule = await parquetModulePromise
  const parquetReaderFactory = parquetModule?.ParquetReader ?? parquetModule?.default?.ParquetReader

  if (!parquetReaderFactory?.openFile) {
    throw new Error('parquetjs-lite ParquetReader is unavailable')
  }

  const reader = await parquetReaderFactory.openFile(filePath)
  const cursor = reader.getCursor()
  const rows: T[] = []

  while (true) {
    const row = await cursor.next()
    if (!row) {
      break
    }

    const mapped = mapRow(row)
    if (mapped) {
      rows.push(mapped)
    }
  }

  await reader.close()
  return rows
}

async function loadMetricsRows(): Promise<MetricRow[]> {
  if (!metricsRowsPromise) {
    metricsRowsPromise = (async () => {
      const files = await listParquetFiles(METRICS_ROOT)
      const rows: MetricRow[] = []

      for (const file of files) {
        const fileRows = await readParquetRows(file, (row) => {
          const timestamp = toIsoTimestamp(row.timestamp_hour)
          if (!timestamp) {
            return null
          }

          return {
            timestamp_hour: timestamp,
            active_model_version: typeof row.active_model_version === 'string' ? row.active_model_version : 'unknown',
            mean_prediction: toNumber(row.mean_prediction),
            max_prediction: toNumber(row.max_prediction),
            min_prediction: toNumber(row.min_prediction),
            std_prediction: toNullableNumber(row.std_prediction),
            mean_error: toNumber(row.mean_error),
            max_error: toNumber(row.max_error),
            record_count: Math.max(1, Math.trunc(toNumber(row.record_count, 1))),
          }
        })

        rows.push(...fileRows)
      }

      return rows.sort((left, right) => left.timestamp_hour.localeCompare(right.timestamp_hour))
    })()
  }

  return metricsRowsPromise
}

async function loadSupervisedRows(): Promise<SupervisedRow[]> {
  if (!supervisedRowsPromise) {
    supervisedRowsPromise = (async () => {
      const fileRows = await readParquetRows(SUPERVISED_DATASET_PATH, (row) => {
        const timestamp = toIsoTimestamp(row.datetime)
        if (!timestamp) {
          return null
        }

        return {
          timestamp,
          load_mw: toNumber(row.load_mw),
          hour_of_day: toNullableNumber(row.hour_of_day),
          day_of_week: toNullableNumber(row.day_of_week),
          month: toNullableNumber(row.month),
          is_weekend: toNullableNumber(row.is_weekend),
          lag_1: toNullableNumber(row.lag_1),
          lag_24: toNullableNumber(row.lag_24),
          lag_168: toNullableNumber(row.lag_168),
          rolling_24: toNullableNumber(row.rolling_24),
          rolling_168: toNullableNumber(row.rolling_168),
        }
      })

      return fileRows.sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    })()
  }

  return supervisedRowsPromise
}

function mean(values: number[]): number {
  if (values.length === 0) {
    return 0
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function std(values: number[]): number {
  if (values.length < 2) {
    return 0
  }

  const average = mean(values)
  const variance = values.reduce((sum, value) => sum + (value - average) ** 2, 0) / values.length
  return Math.sqrt(variance)
}

function median(values: number[]): number {
  if (values.length === 0) {
    return 0
  }

  const sorted = [...values].sort((left, right) => left - right)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function buildFeatureDrift(feature: string, baseline: number[], recent: number[]) {
  const baselineMean = mean(baseline)
  const recentMean = mean(recent)
  const baselineStd = std(baseline)
  const magnitude = Math.abs(recentMean - baselineMean)
  const normalized = baselineStd > 0 ? magnitude / (baselineStd * 2.5) : magnitude / (Math.abs(baselineMean) + 1)
  const score = clamp01(normalized)

  return {
    feature,
    ks_score: Number(score.toFixed(3)),
    psi_score: Number(clamp01(score * 0.82).toFixed(3)),
    drifted: score > 0.35,
  }
}

export async function buildRecordedDriftResponse(tick: number): Promise<RecordedDriftResponse> {
  const metricsRows = await loadMetricsRows()
  const supervisedRows = await loadSupervisedRows()
  const now = new Date().toISOString()

  if (metricsRows.length === 0 || supervisedRows.length === 0) {
    return {
      generated_at: now,
      current: {
        generated_at: now,
        data_as_of: null,
        stale_after_seconds: 60,
        is_stale: true,
        source_status: {
          drift_report: { ok: false, path: METRICS_DISPLAY_PATH, last_modified: null, error: 'Recorded drift data unavailable' },
          hourly_metrics: { ok: false, path: METRICS_DISPLAY_PATH, last_modified: null, error: 'Recorded drift data unavailable' },
        },
        data: {
          drift_available: false,
          drift_detected: false,
          detected_at: null,
          metrics: {
            prediction_drift: { detected: false, score: null, threshold: null },
            performance_drift: { detected: false, score: null, threshold: null },
          },
          feature_drift: [],
        },
      },
      history: {
        generated_at: now,
        data_as_of: null,
        stale_after_seconds: 60,
        is_stale: true,
        source_status: {
          drift_history: { ok: false, path: METRICS_DISPLAY_PATH, last_modified: null, error: 'Recorded drift data unavailable' },
        },
        data: {
          events: [],
          count: 0,
        },
      },
    }
  }

  const meanErrors = metricsRows.map((row) => row.mean_error)
  const errorThreshold = median(meanErrors) + std(meanErrors) * 0.75
  const recentWindow = Math.max(20, Math.min(48, metricsRows.length))
  const maxStart = Math.max(0, metricsRows.length - recentWindow)
  const startIndex = maxStart > 0 ? tick % (maxStart + 1) : 0
  const windowRows = metricsRows.slice(startIndex, startIndex + recentWindow)

  const historyEvents = windowRows.map((row) => {
    const predictionScore = clamp01(row.mean_error / Math.max(errorThreshold * 1.25, 1))
    const performanceScore = clamp01(row.max_error / Math.max(errorThreshold * 1.45, 1))
    const driftDetected = predictionScore >= 0.6 || performanceScore >= 0.55

    return {
      timestamp: row.timestamp_hour,
      drift_detected: driftDetected,
      prediction_drift_score: Number(predictionScore.toFixed(3)),
      performance_drift_score: Number(performanceScore.toFixed(3)),
    }
  })

  const recentMetrics = windowRows.at(-1) ?? metricsRows.at(-1)!
  const latestSupervisedWindow = supervisedRows.slice(Math.max(0, supervisedRows.length - 336))
  const baselineWindow = supervisedRows.slice(Math.max(0, supervisedRows.length - 672), Math.max(0, supervisedRows.length - 336))

  const featurePairs = [
    ['load_mw', baselineWindow.map((row) => row.load_mw), latestSupervisedWindow.map((row) => row.load_mw)],
    ['hour_of_day', baselineWindow.map((row) => row.hour_of_day ?? 0), latestSupervisedWindow.map((row) => row.hour_of_day ?? 0)],
    ['day_of_week', baselineWindow.map((row) => row.day_of_week ?? 0), latestSupervisedWindow.map((row) => row.day_of_week ?? 0)],
    ['rolling_24', baselineWindow.map((row) => row.rolling_24 ?? row.load_mw), latestSupervisedWindow.map((row) => row.rolling_24 ?? row.load_mw)],
    ['lag_24', baselineWindow.map((row) => row.lag_24 ?? row.load_mw), latestSupervisedWindow.map((row) => row.lag_24 ?? row.load_mw)],
  ] as const

  const featureDrift = featurePairs.map(([name, baseline, recent]) => buildFeatureDrift(name, baseline, recent))
  const currentPredictionScore = clamp01(recentMetrics.mean_error / Math.max(errorThreshold * 1.25, 1))
  const currentPerformanceScore = clamp01(recentMetrics.max_error / Math.max(errorThreshold * 1.45, 1))
  const driftDetected = currentPredictionScore >= 0.6 || currentPerformanceScore >= 0.55

  return {
    generated_at: now,
    current: {
      generated_at: now,
      data_as_of: recentMetrics.timestamp_hour,
      stale_after_seconds: 60,
      is_stale: false,
      source_status: {
        drift_report: { ok: true, path: METRICS_DISPLAY_PATH, last_modified: recentMetrics.timestamp_hour, error: null },
        hourly_metrics: { ok: true, path: METRICS_DISPLAY_PATH, last_modified: recentMetrics.timestamp_hour, error: null },
      },
      data: {
        drift_available: true,
        drift_detected: driftDetected,
        detected_at: recentMetrics.timestamp_hour,
        metrics: {
          prediction_drift: {
            detected: driftDetected,
            score: Number(currentPredictionScore.toFixed(3)),
            threshold: Number((errorThreshold * 1.25).toFixed(1)),
          },
          performance_drift: {
            detected: driftDetected,
            score: Number(currentPerformanceScore.toFixed(3)),
            threshold: Number((errorThreshold * 1.45).toFixed(1)),
          },
        },
        feature_drift: featureDrift,
      },
    },
    history: {
      generated_at: now,
      data_as_of: historyEvents.at(-1)?.timestamp ?? recentMetrics.timestamp_hour,
      stale_after_seconds: 60,
      is_stale: false,
      source_status: {
        drift_history: { ok: true, path: METRICS_DISPLAY_PATH, last_modified: historyEvents.at(-1)?.timestamp ?? recentMetrics.timestamp_hour, error: null },
      },
      data: {
        events: historyEvents,
        count: historyEvents.length,
      },
    },
  }
}
