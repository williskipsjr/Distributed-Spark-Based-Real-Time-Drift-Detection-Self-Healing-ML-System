'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { readApi, controlApi } from './client'

// Query keys factory
const queryKeys = {
  all: ['api'] as const,
  read: () => [...queryKeys.all, 'read'] as const,
  summary: () => [...queryKeys.read(), 'summary'] as const,
  predictions: (window?: string, limit?: number) =>
    [...queryKeys.read(), 'predictions', window, limit] as const,
  drift: () => [...queryKeys.read(), 'drift'] as const,
  driftCurrent: () => [...queryKeys.drift(), 'current'] as const,
  driftHistory: (limit?: number) => [...queryKeys.drift(), 'history', limit] as const,
  health: () => [...queryKeys.read(), 'health'] as const,
  models: () => [...queryKeys.read(), 'models'] as const,
  modelsActive: () => [...queryKeys.models(), 'active'] as const,
  modelsVersions: (limit?: number) => [...queryKeys.models(), 'versions', limit] as const,
  selfHealing: () => [...queryKeys.read(), 'self-healing'] as const,
  selfHealingStatus: (limit?: number) =>
    [...queryKeys.selfHealing(), 'status', limit] as const,
  control: () => [...queryKeys.all, 'control'] as const,
  services: () => [...queryKeys.control(), 'services'] as const,
  serviceLogs: (serviceName: string) =>
    [...queryKeys.control(), 'logs', serviceName] as const,
}

// Read API hooks - 30s polling interval
const READ_POLL_INTERVAL = 30000

export function useGetDashboardSummary() {
  return useQuery({
    queryKey: queryKeys.summary(),
    queryFn: async () => {
      return readApi.getSummary()
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetPredictions(window?: string, limit?: number) {
  return useQuery({
    queryKey: queryKeys.predictions(window, limit),
    queryFn: async () => {
      return readApi.getPredictions(window, limit)
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetDriftCurrent() {
  return useQuery({
    queryKey: queryKeys.driftCurrent(),
    queryFn: async () => {
      return readApi.getDriftCurrent()
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetDriftHistory(limit?: number) {
  return useQuery({
    queryKey: queryKeys.driftHistory(limit),
    queryFn: async () => {
      return readApi.getDriftHistory(limit)
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetSystemHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: async () => {
      return readApi.getSystemHealth()
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetModelsActive() {
  return useQuery({
    queryKey: queryKeys.modelsActive(),
    queryFn: async () => {
      return readApi.getModelsActive()
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetModelsVersions(limit?: number) {
  return useQuery({
    queryKey: queryKeys.modelsVersions(limit),
    queryFn: async () => {
      return readApi.getModelsVersions(limit)
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

export function useGetSelfHealingStatus(limit?: number) {
  return useQuery({
    queryKey: queryKeys.selfHealingStatus(limit),
    queryFn: async () => {
      return readApi.getSelfHealingStatus(limit)
    },
    refetchInterval: READ_POLL_INTERVAL,
    staleTime: READ_POLL_INTERVAL / 2,
  })
}

// Control API hooks - 10s polling interval, manual refresh
const CONTROL_POLL_INTERVAL = 10000

export function useGetControlServices(enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.services(),
    queryFn: async () => {
      return controlApi.getServices()
    },
    refetchInterval: CONTROL_POLL_INTERVAL,
    staleTime: CONTROL_POLL_INTERVAL / 2,
    enabled,
  })
}

export function useGetServiceLogs(serviceName: string, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.serviceLogs(serviceName),
    queryFn: async () => {
      return controlApi.getServiceLogs(serviceName)
    },
    refetchInterval: CONTROL_POLL_INTERVAL,
    staleTime: CONTROL_POLL_INTERVAL / 2,
    enabled,
  })
}

// Control action mutations
export interface ControlActionOptions {
  onSuccess?: () => void
  onError?: (error: Error) => void
}

export function useStartService(options?: ControlActionOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      serviceName,
      dryRun,
    }: {
      serviceName: string
      dryRun: boolean
    }) => {
      return controlApi.startService(serviceName, dryRun)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services() })
      options?.onSuccess?.()
    },
    onError: (error) => {
      options?.onError?.(error instanceof Error ? error : new Error(String(error)))
    },
  })
}

export function useStopService(options?: ControlActionOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      serviceName,
      dryRun,
    }: {
      serviceName: string
      dryRun: boolean
    }) => {
      return controlApi.stopService(serviceName, dryRun)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services() })
      options?.onSuccess?.()
    },
    onError: (error) => {
      options?.onError?.(error instanceof Error ? error : new Error(String(error)))
    },
  })
}

export function useRestartService(options?: ControlActionOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      serviceName,
      dryRun,
    }: {
      serviceName: string
      dryRun: boolean
    }) => {
      return controlApi.restartService(serviceName, dryRun)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services() })
      options?.onSuccess?.()
    },
    onError: (error) => {
      options?.onError?.(error instanceof Error ? error : new Error(String(error)))
    },
  })
}

export function useStartPipeline(options?: ControlActionOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ dryRun }: { dryRun: boolean }) => {
      return controlApi.startPipeline(dryRun)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services() })
      options?.onSuccess?.()
    },
    onError: (error) => {
      options?.onError?.(error instanceof Error ? error : new Error(String(error)))
    },
  })
}

export function useStopPipeline(options?: ControlActionOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ dryRun }: { dryRun: boolean }) => {
      return controlApi.stopPipeline(dryRun)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.services() })
      options?.onSuccess?.()
    },
    onError: (error) => {
      options?.onError?.(error instanceof Error ? error : new Error(String(error)))
    },
  })
}
