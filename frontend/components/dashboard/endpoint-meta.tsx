import { Timestamp } from '@/components/dashboard/timestamp'
import { StatusBadge } from '@/components/dashboard/status-badge'

interface EndpointMetaProps {
  endpoint: string
  generatedAt: string | null
  isStale: boolean
  sourceOk?: boolean
}

export function EndpointMeta({ endpoint, generatedAt, isStale, sourceOk = true }: EndpointMetaProps) {
  return (
    <div className="grid gap-3 border border-border bg-background/70 px-4 py-3 md:grid-cols-4">
      <div>
        <p className="telemetry-label">endpoint</p>
        <p className="telemetry-value mt-1 text-sm">{endpoint}</p>
      </div>
      <div>
        <p className="telemetry-label">generated_at</p>
        <p className="mt-1 text-sm text-foreground/90">
          {generatedAt ? <Timestamp date={generatedAt} format="full" /> : 'N/A'}
        </p>
      </div>
      <div>
        <p className="telemetry-label">is_stale</p>
        <div className="mt-1">
          <StatusBadge status={isStale ? 'warning' : 'healthy'} label={isStale ? 'true' : 'false'} />
        </div>
      </div>
      <div>
        <p className="telemetry-label">source</p>
        <div className="mt-1">
          <StatusBadge status={sourceOk ? 'ok' : 'failed'} label={sourceOk ? 'ok' : 'degraded'} />
        </div>
      </div>
    </div>
  )
}
