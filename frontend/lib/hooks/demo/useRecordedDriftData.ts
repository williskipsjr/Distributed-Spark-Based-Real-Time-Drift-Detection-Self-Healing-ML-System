import { useEffect, useState } from 'react'
import { DEMO_STATE_EVENT, getDemoState } from '@/lib/demo/state'
import type { DriftCurrentEnvelope, DriftHistoryEnvelope } from '@/lib/api/types'

interface RecordedDriftResponse {
  generated_at: string
  current: DriftCurrentEnvelope
  history: DriftHistoryEnvelope
}

interface QueryLike<T> {
  data: T | undefined
  isLoading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

export function useRecordedDriftData() {
  const [pipelineRunning, setPipelineRunning] = useState<boolean>(() => getDemoState().pipelineRunning)
  const [streamTick, setStreamTick] = useState(0)
  const [current, setCurrent] = useState<DriftCurrentEnvelope | undefined>(undefined)
  const [history, setHistory] = useState<DriftHistoryEnvelope | undefined>(undefined)
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
      setCurrent(undefined)
      setHistory(undefined)
      setError(null)
      setIsLoading(false)
      return
    }

    const interval = setInterval(() => {
      setStreamTick((value) => value + 1)
    }, 3500)

    return () => clearInterval(interval)
  }, [pipelineRunning])

  useEffect(() => {
    if (!pipelineRunning) {
      return
    }

    let cancelled = false

    const loadRecordedDrift = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`/api/demo/drift-stream?tick=${streamTick}`, {
          cache: 'no-store',
        })

        if (!response.ok) {
          throw new Error(`Recorded drift request failed with HTTP ${response.status}`)
        }

        const payload = (await response.json()) as RecordedDriftResponse
        if (cancelled) {
          return
        }

        setCurrent(payload.current)
        setHistory(payload.history)
      } catch (fetchError) {
        if (!cancelled) {
          setError(fetchError instanceof Error ? fetchError : new Error('Failed to load recorded drift data'))
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadRecordedDrift()

    return () => {
      cancelled = true
    }
  }, [pipelineRunning, streamTick])

  const currentQuery: QueryLike<DriftCurrentEnvelope> = {
    data: current,
    isLoading,
    error,
    refetch: async () => {
      setStreamTick((value) => value + 1)
    },
  }

  const historyQuery: QueryLike<DriftHistoryEnvelope> = {
    data: history,
    isLoading,
    error,
    refetch: async () => {
      setStreamTick((value) => value + 1)
    },
  }

  return {
    current: currentQuery,
    history: historyQuery,
  }
}
