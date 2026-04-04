'use client'

import { useState, useCallback } from 'react'
import {
  useGetControlServices,
  useGetServiceLogs,
  useStartService,
  useStopService,
  useRestartService,
  useStartPipeline,
  useStopPipeline,
} from '@/lib/api/hooks'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { Timestamp } from '@/components/dashboard/timestamp'
import { ErrorState } from '@/components/dashboard/error-state'
import { Panel } from '@/components/dashboard/panel'
import { LogsPanel } from '@/components/dashboard/logs-panel'
import { ListItemSkeleton } from '@/components/dashboard/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { toast } from 'sonner'
import { Play, Square, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'

interface ConfirmAction {
  type: 'start' | 'stop' | 'restart' | 'start-pipeline' | 'stop-pipeline'
  serviceName?: string
}

export default function ControlPage() {
  const [dryRun, setDryRun] = useState(true)
  const [expandedService, setExpandedService] = useState<string | null>(null)
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null)

  const services = useGetControlServices()
  const startServiceMutation = useStartService({
    onSuccess: () => {
      toast.success('Service started successfully')
    },
    onError: (error) => {
      toast.error(`Failed to start service: ${error.message}`)
    },
  })

  const stopServiceMutation = useStopService({
    onSuccess: () => {
      toast.success('Service stopped successfully')
    },
    onError: (error) => {
      toast.error(`Failed to stop service: ${error.message}`)
    },
  })

  const restartServiceMutation = useRestartService({
    onSuccess: () => {
      toast.success('Service restarted successfully')
    },
    onError: (error) => {
      toast.error(`Failed to restart service: ${error.message}`)
    },
  })

  const startPipelineMutation = useStartPipeline({
    onSuccess: () => {
      toast.success('Pipeline started successfully')
    },
    onError: (error) => {
      toast.error(`Failed to start pipeline: ${error.message}`)
    },
  })

  const stopPipelineMutation = useStopPipeline({
    onSuccess: () => {
      toast.success('Pipeline stopped successfully')
    },
    onError: (error) => {
      toast.error(`Failed to stop pipeline: ${error.message}`)
    },
  })

  const executeAction = useCallback(
    (type: ConfirmAction['type'], serviceName?: string) => {
      setConfirmAction(null)

      const actualDryRun = dryRun

      switch (type) {
        case 'start':
          if (serviceName) {
            startServiceMutation.mutate({ serviceName, dryRun: actualDryRun })
          }
          break
        case 'stop':
          if (serviceName) {
            stopServiceMutation.mutate({ serviceName, dryRun: actualDryRun })
          }
          break
        case 'restart':
          if (serviceName) {
            restartServiceMutation.mutate({ serviceName, dryRun: actualDryRun })
          }
          break
        case 'start-pipeline':
          startPipelineMutation.mutate({ dryRun: actualDryRun })
          break
        case 'stop-pipeline':
          stopPipelineMutation.mutate({ dryRun: actualDryRun })
          break
      }
    },
    [
      dryRun,
      restartServiceMutation,
      startPipelineMutation,
      startServiceMutation,
      stopPipelineMutation,
      stopServiceMutation,
    ]
  )

  const handleServiceAction = useCallback(
    (type: ConfirmAction['type'], serviceName?: string) => {
      if (!dryRun) {
        setConfirmAction({ type, serviceName })
      } else {
        executeAction(type, serviceName)
      }
    },
    [dryRun, executeAction]
  )

  const isLoading = services.isLoading
  const error = services.error

  if (error) {
    return <ErrorState onRetry={() => void services.refetch()} />
  }

  const servicesList = services.data?.services || []

  return (
    <div className="space-y-6" suppressHydrationWarning>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between" suppressHydrationWarning>
        <div>
          <p className="telemetry-label">endpoint /api/v1/control/services + control action endpoints</p>
          <h1 className="text-3xl font-bold uppercase tracking-[0.08em] text-foreground md:text-4xl">Pilot Control</h1>
          <p className="mt-1 text-sm text-muted-foreground">Actions mapped directly to control endpoints.</p>
        </div>
        <div className="border border-border bg-card px-4 py-3">
          <div className="flex items-center gap-3">
            <StatusBadge status={dryRun ? 'healthy' : 'warning'} label={dryRun ? 'Dry run' : 'Production'} />
            <StatusBadge status="ok" label={`${servicesList.length} services`} />
          </div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2" suppressHydrationWarning>
        <div className="border border-border bg-card/70 p-3">
          <p className="telemetry-label">service state endpoint</p>
          <p className="mt-1 text-sm text-foreground/90">GET /api/v1/control/services</p>
        </div>
        <div className="border border-border bg-card/70 p-3">
          <p className="telemetry-label">actions endpoint pattern</p>
          <p className="mt-1 text-sm text-foreground/90">POST /api/v1/control/services/:service/:action and /control/pipeline/:action</p>
        </div>
      </div>

      {/* Dry Run Toggle */}
      <div className="flex items-center justify-between border border-border bg-card p-4">
        <div>
          <p className="telemetry-label">execution mode</p>
          <p className="mt-1 text-lg font-bold uppercase tracking-[0.1em] text-foreground">Dry Run</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {dryRun
              ? 'Simulating actions without making changes'
              : 'Actions will be executed in production'}
          </p>
        </div>
        <Switch checked={dryRun} onCheckedChange={setDryRun} className="ml-4" />
      </div>

      {/* Safety Warning */}
      {!dryRun && (
        <div className="border border-red-500/35 bg-red-500/10 p-4">
          <p className="text-sm font-medium text-red-300">
            Production Mode Active - Actions will execute in production. Confirmation required.
          </p>
        </div>
      )}

      {/* Pipeline Controls */}
      <Panel title="Pipeline control" subtitle="POST /api/v1/control/pipeline/start and /stop">
        <div className="flex gap-2">
          <Button
            onClick={() => handleServiceAction('start-pipeline')}
            disabled={startPipelineMutation.isPending}
            className="gap-2 border border-primary/35 bg-primary/20 text-primary hover:bg-primary/30"
          >
            <Play className="w-4 h-4" />
            {startPipelineMutation.isPending ? 'Starting...' : 'Start Pipeline'}
          </Button>
          <Button
            onClick={() => handleServiceAction('stop-pipeline')}
            disabled={stopPipelineMutation.isPending}
            variant="destructive"
            className="gap-2 border border-red-500/35 bg-red-500/20 text-red-200 hover:bg-red-500/30"
          >
            <Square className="w-4 h-4" />
            {stopPipelineMutation.isPending ? 'Stopping...' : 'Stop Pipeline'}
          </Button>
        </div>
      </Panel>

      {/* Services List */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold uppercase tracking-[0.1em] text-foreground">
          Services ({servicesList.length})
        </h2>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <ListItemSkeleton key={i} />
            ))}
          </div>
        ) : servicesList.length > 0 ? (
          <div className="space-y-2">
            {servicesList.map((service) => (
              <ServiceCard
                key={service.service}
                service={service}
                isExpanded={expandedService === service.service}
                onToggleExpand={() =>
                  setExpandedService(expandedService === service.service ? null : service.service)
                }
                onAction={handleServiceAction}
                isPending={
                  startServiceMutation.isPending ||
                  stopServiceMutation.isPending ||
                  restartServiceMutation.isPending
                }
              />
            ))}
          </div>
        ) : (
          <div className="border border-border p-6 text-center">
            <p className="text-muted-foreground">No services available</p>
          </div>
        )}
      </div>

      {/* Confirmation Dialog */}
      {confirmAction && (
        <ConfirmActionDialog
          action={confirmAction}
          onConfirm={() => executeAction(confirmAction.type, confirmAction.serviceName)}
          onCancel={() => setConfirmAction(null)}
          isLoading={
            startServiceMutation.isPending ||
            stopServiceMutation.isPending ||
            restartServiceMutation.isPending ||
            startPipelineMutation.isPending ||
            stopPipelineMutation.isPending
          }
        />
      )}
    </div>
  )
}

interface ServiceCardProps {
  service: {
    service: string
    status: 'stopped' | 'starting' | 'running' | 'stopping' | 'failed'
    allowed_actions: string[]
    managed_process: boolean
    pid?: number | null
    last_started_at: string | null
    last_stopped_at: string | null
    last_exit_code: number | null
    last_error: string | null
  }
  isExpanded: boolean
  onToggleExpand: () => void
  onAction: (type: ConfirmAction['type'], serviceName: string) => void
  isPending: boolean
}

function ServiceCard({
  service,
  isExpanded,
  onToggleExpand,
  onAction,
  isPending,
}: ServiceCardProps) {
  const serviceLogs = useGetServiceLogs(service.service, isExpanded)

  return (
    <div className="overflow-hidden border border-border bg-card">
      {/* Service Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1">
            <button
              onClick={onToggleExpand}
              className="p-1 hover:bg-muted"
            >
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
            <div className="flex-1">
              <p className="font-medium uppercase tracking-[0.08em] text-foreground">{service.service}</p>
              {service.last_started_at || service.last_stopped_at ? (
                <Timestamp
                  date={service.last_started_at || service.last_stopped_at || new Date().toISOString()}
                  format="relative"
                />
              ) : (
                <p className="text-xs text-muted-foreground">No recent transition timestamp</p>
              )}
            </div>
          </div>

          <StatusBadge status={service.status} />
        </div>

        {service.last_error && (
          <p className="text-sm text-muted-foreground mt-2">{service.last_error}</p>
        )}
      </div>

      <div className="grid gap-2 border-b border-border bg-background/60 p-3 md:grid-cols-3">
        <div>
          <p className="telemetry-label">status endpoint</p>
          <p className="mt-1 text-xs text-foreground/90">GET /api/v1/control/services/{service.service}/status</p>
        </div>
        <div>
          <p className="telemetry-label">logs endpoint</p>
          <p className="mt-1 text-xs text-foreground/90">GET /api/v1/control/services/{service.service}/logs</p>
        </div>
        <div>
          <p className="telemetry-label">actions endpoint</p>
          <p className="mt-1 text-xs text-foreground/90">POST /api/v1/control/services/{service.service}/start|stop|restart</p>
        </div>
      </div>

      {/* Service Controls */}
      <div className="p-4 border-t border-border flex gap-2 flex-wrap">
        <Button
          size="sm"
          onClick={() => onAction('start', service.service)}
          disabled={isPending || service.status === 'running'}
          className="gap-1 border border-primary/35 bg-primary/20 text-primary hover:bg-primary/30"
        >
          <Play className="w-3 h-3" />
          Start
        </Button>
        <Button
          size="sm"
          onClick={() => onAction('stop', service.service)}
          disabled={isPending || service.status === 'stopped'}
          variant="destructive"
          className="gap-1 border border-red-500/35 bg-red-500/20 text-red-200 hover:bg-red-500/30"
        >
          <Square className="w-3 h-3" />
          Stop
        </Button>
        <Button
          size="sm"
          onClick={() => onAction('restart', service.service)}
          disabled={isPending}
          variant="outline"
          className="gap-1 border border-[color:var(--warning)]/35 bg-[color:var(--warning)]/12 text-[color:var(--warning)] hover:bg-[color:var(--warning)]/20"
        >
          <RotateCcw className="w-3 h-3" />
          Restart
        </Button>
      </div>

      {/* Logs Section */}
      {isExpanded && (
        <div className="border-t border-border p-4 bg-muted/30">
          {serviceLogs.isLoading ? (
            <div className="text-xs text-muted-foreground">Loading logs...</div>
          ) : serviceLogs.error ? (
            <div className="text-xs text-red-400">Failed to load logs</div>
          ) : serviceLogs.data && serviceLogs.data.lines.length > 0 ? (
            <LogsPanel title={`${service.service} logs`} lines={serviceLogs.data.lines} />
          ) : (
            <div className="text-xs text-muted-foreground">No logs available</div>
          )}
        </div>
      )}
    </div>
  )
}

interface ConfirmActionDialogProps {
  action: ConfirmAction
  onConfirm: () => void
  onCancel: () => void
  isLoading: boolean
}

function ConfirmActionDialog({
  action,
  onConfirm,
  onCancel,
  isLoading,
}: ConfirmActionDialogProps) {
  const getActionLabel = () => {
    switch (action.type) {
      case 'start':
        return `start ${action.serviceName}`
      case 'stop':
        return `stop ${action.serviceName}`
      case 'restart':
        return `restart ${action.serviceName}`
      case 'start-pipeline':
        return 'start the pipeline'
      case 'stop-pipeline':
        return 'stop the pipeline'
    }
  }

  return (
    <AlertDialog open={true}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Confirm Action</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to {getActionLabel()}? This action will be executed in production.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2 my-4">
          <p className="text-sm font-medium text-foreground">
            This will execute immediately and may affect your running services.
          </p>
        </div>
        <div className="flex gap-2 justify-end">
          <AlertDialogCancel onClick={onCancel} disabled={isLoading}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isLoading}
            className="border border-red-500/35 bg-red-500/20 text-red-200 hover:bg-red-500/30"
          >
            {isLoading ? 'Executing...' : 'Execute'}
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  )
}
