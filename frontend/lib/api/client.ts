import { z } from 'zod'
import type { ApiEnvelope } from './types'
import {
  ApiEnvelopeSchema,
  ControlPipelineResponseSchema,
  ControlServiceActionResponseSchema,
  ControlServiceCatalogSchema,
  ControlServiceLogsResponseSchema,
  ControlServiceStateSchema,
  DashboardSummaryEnvelopeSchema,
  DriftCurrentEnvelopeSchema,
  DriftHistoryEnvelopeSchema,
  ModelsActiveEnvelopeSchema,
  ModelsVersionsEnvelopeSchema,
  PredictionsEnvelopeSchema,
  SelfHealingStatusEnvelopeSchema,
  SystemHealthEnvelopeSchema,
} from './types'

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
const CONTROL_API_KEY = process.env.NEXT_PUBLIC_CONTROL_API_KEY || ''
const API_PREFIX = API_BASE_URL.endsWith('/api/v1') ? '' : '/api/v1'

/**
 * Error class for API errors
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public envelope?: ApiEnvelope
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * Fetch wrapper for API calls
 */
async function fetchApi<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit & {
    requiresAuth?: boolean
  } = {}
): Promise<T> {
  const { requiresAuth = false, ...fetchOptions } = options

  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = `${API_BASE_URL}${API_PREFIX}${normalizedPath}`

  const headers = new Headers(fetchOptions.headers)

  if (fetchOptions.method && fetchOptions.method !== 'GET') {
    headers.set('Content-Type', 'application/json')
  }

  if (requiresAuth && CONTROL_API_KEY) {
    headers.set('x-control-key', CONTROL_API_KEY)
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    })

    const json = await response.json()

    if (!response.ok) {
      const envelope = ApiEnvelopeSchema.safeParse(json)
      throw new ApiError(
        response.status,
        `HTTP_${response.status}`,
        json.message || `HTTP ${response.status}`,
        envelope.success ? (envelope.data as ApiEnvelope) : undefined
      )
    }

    return schema.parse(json)
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }

    if (error instanceof SyntaxError) {
      throw new ApiError(500, 'PARSE_ERROR', 'Failed to parse response JSON')
    }

    throw new ApiError(
      500,
      'NETWORK_ERROR',
      error instanceof Error ? error.message : 'Unknown network error'
    )
  }
}

/**
 * Read API endpoints
 */
export const readApi = {
  getSummary: () => fetchApi('/dashboard/summary', DashboardSummaryEnvelopeSchema),

  getPredictions: (window?: string, limit?: number) => {
    const params = new URLSearchParams()
    if (window) params.append('window', window)
    if (limit) params.append('limit', String(limit))

    const query = params.toString()
    return fetchApi(`/predictions${query ? `?${query}` : ''}`, PredictionsEnvelopeSchema)
  },

  getDriftCurrent: () => fetchApi('/drift/current', DriftCurrentEnvelopeSchema),

  getDriftHistory: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : ''
    return fetchApi(`/drift/history${query}`, DriftHistoryEnvelopeSchema)
  },

  getSystemHealth: () => fetchApi('/system/health', SystemHealthEnvelopeSchema),

  getModelsActive: () => fetchApi('/models/active', ModelsActiveEnvelopeSchema),

  getModelsVersions: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : ''
    return fetchApi(`/models/versions${query}`, ModelsVersionsEnvelopeSchema)
  },

  getSelfHealingStatus: (limit?: number) => {
    const query = limit ? `?limit=${limit}` : ''
    return fetchApi(`/self-healing/status${query}`, SelfHealingStatusEnvelopeSchema)
  },
}

/**
 * Control API endpoints
 */
export const controlApi = {
  getServices: () =>
    fetchApi('/control/services', ControlServiceCatalogSchema, { requiresAuth: true }),

  getServiceStatus: (serviceName: string) =>
    fetchApi(`/control/services/${serviceName}/status`, ControlServiceStateSchema, {
      requiresAuth: true,
    }),

  startService: (serviceName: string, dryRun: boolean = true) =>
    fetchApi('/control/services/' + serviceName + '/start', ControlServiceActionResponseSchema, {
      method: 'POST',
      body: JSON.stringify({ dry_run: dryRun }),
      requiresAuth: true,
    }),

  stopService: (serviceName: string, dryRun: boolean = true) =>
    fetchApi('/control/services/' + serviceName + '/stop', ControlServiceActionResponseSchema, {
      method: 'POST',
      body: JSON.stringify({ dry_run: dryRun }),
      requiresAuth: true,
    }),

  restartService: (serviceName: string, dryRun: boolean = true) =>
    fetchApi('/control/services/' + serviceName + '/restart', ControlServiceActionResponseSchema, {
      method: 'POST',
      body: JSON.stringify({ dry_run: dryRun }),
      requiresAuth: true,
    }),

  getServiceLogs: (serviceName: string, tail: number = 200) => {
    const query = `?tail=${tail}`
    return fetchApi(`/control/services/${serviceName}/logs${query}`, ControlServiceLogsResponseSchema, {
      requiresAuth: true,
    })
  },

  startPipeline: (dryRun: boolean = true) =>
    fetchApi('/control/pipeline/start', ControlPipelineResponseSchema, {
      method: 'POST',
      body: JSON.stringify({ dry_run: dryRun }),
      requiresAuth: true,
    }),

  stopPipeline: (dryRun: boolean = true) =>
    fetchApi('/control/pipeline/stop', ControlPipelineResponseSchema, {
      method: 'POST',
      body: JSON.stringify({ dry_run: dryRun }),
      requiresAuth: true,
    }),
}

export { ApiEnvelopeSchema }
