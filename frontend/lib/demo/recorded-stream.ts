import path from 'node:path'

type ParquetRow = Record<string, unknown>

export interface RecordedStreamPoint {
  timestamp: string
  actual_mw: number
  predicted_mw: number
  abs_error_mw: number
  projection_mw: number
  model_version: string
}

export interface RecordedStreamEnvelope {
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

interface LoadRow {
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

const DATASET_PATH = path.resolve(process.cwd(), '..', 'data', 'processed', 'pjm_supervised.parquet')
const DATASET_DISPLAY_PATH = path.posix.join('data', 'processed', 'pjm_supervised.parquet')
const METRICS_DISPLAY_PATH = path.posix.join('data', 'metrics', 'hourly_metrics')

const parquetModulePromise = import('parquetjs-lite')
let cachedRowsPromise: Promise<LoadRow[]> | null = null

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

  if (typeof value === 'number') {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
  }

  return null
}

function normalizeLoadRow(row: ParquetRow): LoadRow {
  const timestamp = toIsoTimestamp(row.datetime) ?? new Date().toISOString()

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
}

async function loadRecordedRows(): Promise<LoadRow[]> {
  if (!cachedRowsPromise) {
    cachedRowsPromise = (async () => {
      const parquetModule = await parquetModulePromise
      const parquetReaderFactory = parquetModule?.ParquetReader ?? parquetModule?.default?.ParquetReader

      if (!parquetReaderFactory?.openFile) {
        throw new Error('parquetjs-lite ParquetReader is unavailable')
      }

      const reader = await parquetReaderFactory.openFile(DATASET_PATH)
      const cursor = reader.getCursor()
      const rows: LoadRow[] = []

      while (true) {
        const row = await cursor.next()
        if (!row) {
          break
        }

        rows.push(normalizeLoadRow(row))
      }

      await reader.close()
      return rows.filter((row) => row.timestamp && Number.isFinite(row.load_mw))
    })()
  }

  return cachedRowsPromise
}

function getFeatureValue(row: LoadRow, key: keyof LoadRow, fallback: number): number {
  const value = row[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function buildProjection(points: RecordedStreamPoint[], currentPrediction: number): number {
  const previousPoint = points.at(-1)
  if (!previousPoint) {
    return Number(currentPrediction.toFixed(1))
  }

  const delta = currentPrediction - previousPoint.predicted_mw
  return Number((currentPrediction + delta * 0.45).toFixed(1))
}

function summarizePoints(points: RecordedStreamPoint[]) {
  if (points.length === 0) {
    return {
      count: 0,
      mae_mw: null,
      rmse_mw: null,
      mape_pct: null,
    }
  }

  const totalAbsError = points.reduce((sum, point) => sum + point.abs_error_mw, 0)
  const totalSquaredError = points.reduce((sum, point) => sum + point.abs_error_mw * point.abs_error_mw, 0)
  const totalPctError = points.reduce(
    (sum, point) => sum + (point.actual_mw ? (point.abs_error_mw / point.actual_mw) * 100 : 0),
    0
  )

  return {
    count: points.length,
    mae_mw: Number((totalAbsError / points.length).toFixed(2)),
    rmse_mw: Number(Math.sqrt(totalSquaredError / points.length).toFixed(2)),
    mape_pct: Number((totalPctError / points.length).toFixed(2)),
  }
}

export async function buildRecordedStreamEnvelope(limit: number, tick: number): Promise<RecordedStreamEnvelope> {
  const rows = await loadRecordedRows()
  const normalizedLimit = Math.max(1, Math.min(limit, 96))
  const totalPoints = rows.length

  if (totalPoints === 0) {
    const now = new Date().toISOString()
    return {
      generated_at: now,
      data_as_of: null,
      stale_after_seconds: 60,
      is_stale: true,
      source_status: {
        predictions: {
          ok: false,
          path: DATASET_DISPLAY_PATH,
          last_modified: null,
          error: 'No recorded parquet rows were found',
        },
        hourly_metrics: {
          ok: false,
          path: METRICS_DISPLAY_PATH,
          last_modified: null,
          error: 'No recorded parquet rows were found',
        },
      },
      data: {
        window: '24h',
        points: [],
        summary: { count: 0, mae_mw: null, rmse_mw: null, mape_pct: null },
        stream_cursor: 0,
        total_points: 0,
      },
    }
  }

  const maxStartIndex = Math.max(0, totalPoints - normalizedLimit)
  const startSeed = Math.max(0, totalPoints - Math.max(normalizedLimit * 3, 72))
  const cycleLength = Math.max(1, maxStartIndex - startSeed + 1)
  const cursorOffset = tick % cycleLength
  const startIndex = Math.min(maxStartIndex, startSeed + cursorOffset)
  const slice = rows.slice(startIndex, startIndex + normalizedLimit)

  const points = slice.map((row) => {
    const actual = row.load_mw
    const blendedPrediction =
      getFeatureValue(row, 'rolling_24', actual) * 0.58 +
      getFeatureValue(row, 'lag_24', actual) * 0.24 +
      getFeatureValue(row, 'lag_168', actual) * 0.08 +
      getFeatureValue(row, 'lag_1', actual) * 0.10

    const predicted = Number(blendedPrediction.toFixed(1))
    const absError = Number(Math.abs(actual - predicted).toFixed(1))

    return {
      timestamp: row.timestamp,
      actual_mw: Number(actual.toFixed(1)),
      predicted_mw: predicted,
      abs_error_mw: absError,
      projection_mw: 0,
      model_version: 'v-recorded-pjm-parquet',
    }
  })

  const projectedPoints = points.map((point, index) => {
    const previousPrediction = index > 0 ? points[index - 1].predicted_mw : point.predicted_mw
    return {
      ...point,
      projection_mw: buildProjection(points.slice(0, index), previousPrediction),
    }
  })

  const latestTimestamp = projectedPoints[projectedPoints.length - 1]?.timestamp ?? null

  return {
    generated_at: new Date().toISOString(),
    data_as_of: latestTimestamp,
    stale_after_seconds: 60,
    is_stale: false,
    source_status: {
      predictions: {
        ok: true,
        path: DATASET_DISPLAY_PATH,
        last_modified: latestTimestamp,
        error: null,
      },
      hourly_metrics: {
        ok: true,
        path: METRICS_DISPLAY_PATH,
        last_modified: latestTimestamp,
        error: null,
      },
    },
    data: {
      window: '24h',
      points: projectedPoints,
      summary: summarizePoints(projectedPoints),
      stream_cursor: startIndex,
      total_points: totalPoints,
    },
  }
}
