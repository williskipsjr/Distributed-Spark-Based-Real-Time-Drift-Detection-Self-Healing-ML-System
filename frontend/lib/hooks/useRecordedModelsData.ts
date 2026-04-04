import { useEffect, useState } from 'react'
import { DEMO_STATE_EVENT, getDemoState } from '@/lib/demo/state'
import type { ModelsActiveEnvelope, ModelsVersionsEnvelope } from '@/lib/api/types'

interface RecordedModelsResponse {
  generated_at: string
  active: ModelsActiveEnvelope
  versions: ModelsVersionsEnvelope
}

interface QueryLike<T> {
  data: T | undefined
  isLoading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

export function useRecordedModelsData() {
  const [pipelineRunning, setPipelineRunning] = useState<boolean>(() => getDemoState().pipelineRunning)
  const [data, setData] = useState<RecordedModelsResponse | undefined>(undefined)
  const [error, setError] = useState<Error | null>(null)
  const [isLoading, setIsLoading] = useState(false)

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
      setData(undefined)
      setError(null)
      setIsLoading(false)
      return
    }

    let cancelled = false

    const loadRecordedModels = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch('/api/demo/models-stream', {
          cache: 'no-store',
        })

        if (!response.ok) {
          throw new Error(`Recorded models request failed with HTTP ${response.status}`)
        }

        const payload = (await response.json()) as RecordedModelsResponse
        if (!cancelled) {
          setData(payload)
        }
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError : new Error('Failed to load recorded model registry'))
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadRecordedModels()

    return () => {
      cancelled = true
    }
  }, [pipelineRunning])

  const currentQuery: QueryLike<ModelsActiveEnvelope> = {
    data: data?.active,
    isLoading,
    error,
    refetch: async () => {
      setData(undefined)
    },
  }

  const versionsQuery: QueryLike<ModelsVersionsEnvelope> = {
    data: data?.versions,
    isLoading,
    error,
    refetch: async () => {
      setData(undefined)
    },
  }

  return {
    active: currentQuery,
    versions: versionsQuery,
  }
}
