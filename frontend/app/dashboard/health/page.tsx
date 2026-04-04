'use client'

import { useGetSystemHealth } from '@/lib/api/hooks'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { Timestamp } from '@/components/dashboard/timestamp'
import { ErrorState } from '@/components/dashboard/error-state'
import { KPISkeleton } from '@/components/dashboard/skeleton'
import { ActivitySquare, CheckCircle2, AlertCircle as AlertIcon } from 'lucide-react'

export default function HealthPage() {
  const health = useGetSystemHealth()

  const isLoading = health.isLoading
  const error = health.error

  const healthEnvelope = health.data
  const healthData = healthEnvelope?.data

  if (error) {
    return <ErrorState onRetry={() => void health.refetch()} />
  }

  const getComponentIcon = (status: string) => {
    switch (status) {
      case 'ok':
        return <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
      case 'warning':
        return <AlertIcon className="w-5 h-5 text-amber-600 dark:text-amber-400" />
      case 'critical':
        return <AlertIcon className="w-5 h-5 text-red-600 dark:text-red-400" />
      default:
        return <ActivitySquare className="w-5 h-5 text-slate-600 dark:text-slate-400" />
    }
  }

  const componentEntries = healthData ? Object.entries(healthData.components) : []
  const freshnessStatus = healthEnvelope?.is_stale ? 'warning' : 'healthy'

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">System Health</h1>
          <p className="text-sm text-muted-foreground mt-1">Monitor all system components.</p>
        </div>
        {healthEnvelope && (
          <div className="rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
            <div className="flex items-center gap-3">
              <StatusBadge
                status={healthData?.overall === 'ok' ? 'healthy' : healthData?.overall === 'degraded' ? 'warning' : 'critical'}
                label={healthData?.overall === 'ok' ? 'Healthy' : healthData?.overall === 'degraded' ? 'Degraded' : 'Critical'}
              />
              <StatusBadge status={freshnessStatus} label={healthEnvelope.is_stale ? 'Stale' : 'Fresh'} />
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {healthEnvelope.data_as_of ? <Timestamp date={healthEnvelope.data_as_of} format="relative" /> : 'No data timestamp available'}
            </div>
          </div>
        )}
      </div>

      {/* Overall Status */}
      {isLoading ? (
        <KPISkeleton />
      ) : (
        healthData && (
          <div className="p-6 rounded-xl border border-border bg-card/80">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Overall System Status</h2>
                <p className="text-sm text-muted-foreground mt-2">3 components monitored</p>
              </div>
              <StatusBadge
                status={healthData.overall === 'ok' ? 'healthy' : healthData.overall === 'degraded' ? 'warning' : 'critical'}
                label={
                  healthData.overall === 'ok'
                    ? 'All Systems Healthy'
                    : healthData.overall === 'degraded'
                      ? 'Degraded'
                      : 'Critical'
                }
              />
            </div>
          </div>
        )
      )}

      {/* Components List */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Component Status</h2>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <KPISkeleton key={i} />
            ))}
          </div>
        ) : componentEntries.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {componentEntries.map(([name, component]) => (
              <div
                key={name}
                className="p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="mt-1">
                    {getComponentIcon(component.status)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-medium text-foreground">
                        {name.replace(/_/g, ' ')}
                      </h3>
                      <StatusBadge
                        status={component.status}
                        className="flex-shrink-0"
                      />
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {component.message || 'No message available'}
                    </p>
                    {component.last_data_ts ? (
                      <Timestamp date={component.last_data_ts} format="relative" className="mt-2 text-xs" />
                    ) : (
                      <p className="mt-2 text-xs text-muted-foreground">No timestamp available</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 text-center rounded-lg border border-border">
            <p className="text-muted-foreground">No components available</p>
          </div>
        )}
      </div>

      {/* Health Summary */}
      {healthData && componentEntries.length > 0 && (
        <div className="p-4 rounded-lg border border-border bg-card">
          <h3 className="font-semibold text-foreground mb-4">Health Summary</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                {componentEntries.filter(([, component]) => component.status === 'ok').length}
              </p>
              <p className="text-xs text-muted-foreground mt-1">Healthy</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">
                {componentEntries.filter(([, component]) => component.status === 'warning').length}
              </p>
              <p className="text-xs text-muted-foreground mt-1">Warning</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                {componentEntries.filter(([, component]) => component.status === 'critical').length}
              </p>
              <p className="text-xs text-muted-foreground mt-1">Critical</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
