import path from 'node:path'
import { readFile } from 'node:fs/promises'

interface RegistryEventRow {
  event_time_utc?: string
  event_timestamp?: string
  timestamp?: string
  event_type?: string
  model_version?: string
  model_path?: string
  metadata?: Record<string, unknown>
}

interface ActiveModelSnapshot {
  active_model_path: string | null
  active_model_version: string | null
  previous_model_path: string | null
  previous_model_version: string | null
  promoted_at_utc: string | null
}

interface CandidateReportSnapshot {
  candidate_version: string | null
  ready_for_promotion: boolean
  promotion_recommended: boolean
}

export interface RecordedModelsResponse {
  generated_at: string
  active: {
    generated_at: string
    data_as_of: string | null
    stale_after_seconds: number
    is_stale: boolean
    source_status: {
      active_model: {
        ok: boolean
        path: string
        last_modified: string | null
        error: string | null
      }
    }
    data: {
      active_model_version: string | null
      active_model_path: string | null
      previous_model_version: string | null
      previous_model_path: string | null
      promoted_at_utc: string | null
    }
  }
  versions: {
    generated_at: string
    data_as_of: string | null
    stale_after_seconds: number
    is_stale: boolean
    source_status: {
      promotion_log: {
        ok: boolean
        path: string
        last_modified: string | null
        error: string | null
      }
      candidate_report: {
        ok: boolean
        path: string
        last_modified: string | null
        error: string | null
      }
      active_model: {
        ok: boolean
        path: string
        last_modified: string | null
        error: string | null
      }
    }
    data: {
      active_model_version: string | null
      candidate_version: string | null
      candidate_ready_for_promotion: boolean
      events: Array<{
        timestamp: string | null
        event_type: string | null
        decision: string | null
        reason: string | null
        current_active_model_version: string | null
        target_model_version: string | null
        pointer_updated: boolean | null
      }>
      count: number
    }
  }
}

const MODELS_ROOT = path.resolve(process.cwd(), '..', 'artifacts', 'models')
const ACTIVE_MODEL_PATH = path.resolve(MODELS_ROOT, 'active_model.json')
const CANDIDATE_REPORT_PATH = path.resolve(MODELS_ROOT, 'candidate_report.json')
const REGISTRY_LOG_PATH = path.resolve(MODELS_ROOT, 'model_registry.jsonl')
const PROMOTION_LOG_PATH = path.resolve(MODELS_ROOT, 'promotion_log.jsonl')

const ACTIVE_MODEL_DISPLAY_PATH = path.posix.join('artifacts', 'models', 'active_model.json')
const CANDIDATE_REPORT_DISPLAY_PATH = path.posix.join('artifacts', 'models', 'candidate_report.json')
const REGISTRY_LOG_DISPLAY_PATH = path.posix.join('artifacts', 'models', 'model_registry.jsonl')
const PROMOTION_LOG_DISPLAY_PATH = path.posix.join('artifacts', 'models', 'promotion_log.jsonl')

let cachedModelsPromise: Promise<RecordedModelsResponse> | null = null

function toIsoTimestamp(value: unknown): string | null {
  if (value instanceof Date) {
    return value.toISOString()
  }

  if (typeof value === 'string') {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString()
  }

  return null
}

async function readJsonFile<T>(filePath: string): Promise<T | null> {
  try {
    const content = await readFile(filePath, 'utf8')
    return JSON.parse(content) as T
  } catch {
    return null
  }
}

async function readJsonLines(filePath: string): Promise<RegistryEventRow[]> {
  try {
    const content = await readFile(filePath, 'utf8')
    return content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as RegistryEventRow)
  } catch {
    return []
  }
}

function buildSnapshotFallback(now: string): ActiveModelSnapshot {
  return {
    active_model_path: null,
    active_model_version: null,
    previous_model_path: null,
    previous_model_version: null,
    promoted_at_utc: now,
  }
}

export async function buildRecordedModelsResponse(): Promise<RecordedModelsResponse> {
  if (!cachedModelsPromise) {
    cachedModelsPromise = (async () => {
      const now = new Date().toISOString()
      const activeSnapshot = (await readJsonFile<ActiveModelSnapshot>(ACTIVE_MODEL_PATH)) ?? buildSnapshotFallback(now)
      const candidateReport = (await readJsonFile<CandidateReportSnapshot>(CANDIDATE_REPORT_PATH)) ?? {
        candidate_version: activeSnapshot.active_model_version,
        ready_for_promotion: false,
        promotion_recommended: false,
      }

      const registryRows = await readJsonLines(REGISTRY_LOG_PATH)
      const promotionRows = await readJsonLines(PROMOTION_LOG_PATH)
      const registryEvents = [...promotionRows, ...registryRows]
        .map((row) => {
          const timestamp = toIsoTimestamp(row.event_time_utc ?? row.event_timestamp ?? row.timestamp)
          const modelVersion = typeof row.model_version === 'string' ? row.model_version : null
          const metadata = row.metadata ?? {}
          const reasonFromMetadata = typeof metadata.reason === 'string' ? metadata.reason : null
          const reasonFromText = typeof metadata.message === 'string' ? metadata.message : null

          return {
            timestamp,
            event_type: typeof row.event_type === 'string' ? row.event_type : null,
            decision:
              typeof row.event_type === 'string' && row.event_type === 'model_promoted'
                ? 'promote'
                : typeof metadata.decision === 'string'
                  ? metadata.decision
                  : typeof metadata.promotion_recommended === 'boolean' && metadata.promotion_recommended
                    ? 'promote'
                    : 'hold',
            reason:
              reasonFromMetadata ??
              reasonFromText ??
              (typeof metadata.previous_model_version === 'string'
                ? `Transition from ${metadata.previous_model_version}`
                : null),
            current_active_model_version:
              typeof metadata.current_active_model_version === 'string'
                ? metadata.current_active_model_version
                : activeSnapshot.active_model_version,
            target_model_version: modelVersion,
            pointer_updated:
              typeof metadata.pointer_updated === 'boolean'
                ? metadata.pointer_updated
                : row.event_type === 'model_promoted' || row.event_type === 'promote',
          }
        })
        .filter((event) => event.timestamp != null)
        .sort((left, right) => String(left.timestamp).localeCompare(String(right.timestamp)))

      const latestTimestamp = registryEvents.at(-1)?.timestamp ?? activeSnapshot.promoted_at_utc ?? now

      return {
        generated_at: now,
        active: {
          generated_at: now,
          data_as_of: activeSnapshot.promoted_at_utc,
          stale_after_seconds: 60,
          is_stale: false,
          source_status: {
            active_model: {
              ok: true,
              path: ACTIVE_MODEL_DISPLAY_PATH,
              last_modified: activeSnapshot.promoted_at_utc,
              error: null,
            },
          },
          data: {
            active_model_version: activeSnapshot.active_model_version,
            active_model_path: activeSnapshot.active_model_path,
            previous_model_version: activeSnapshot.previous_model_version,
            previous_model_path: activeSnapshot.previous_model_path,
            promoted_at_utc: activeSnapshot.promoted_at_utc,
          },
        },
        versions: {
          generated_at: now,
          data_as_of: latestTimestamp,
          stale_after_seconds: 60,
          is_stale: false,
          source_status: {
            promotion_log: {
              ok: true,
              path: PROMOTION_LOG_DISPLAY_PATH,
              last_modified: latestTimestamp,
              error: null,
            },
            candidate_report: {
              ok: true,
              path: CANDIDATE_REPORT_DISPLAY_PATH,
              last_modified: latestTimestamp,
              error: null,
            },
            active_model: {
              ok: true,
              path: ACTIVE_MODEL_DISPLAY_PATH,
              last_modified: activeSnapshot.promoted_at_utc,
              error: null,
            },
          },
          data: {
            active_model_version: activeSnapshot.active_model_version,
            candidate_version: candidateReport.candidate_version,
            candidate_ready_for_promotion: candidateReport.ready_for_promotion,
            events: registryEvents,
            count: registryEvents.length,
          },
        },
      }
    })()
  }

  return cachedModelsPromise
}
