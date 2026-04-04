'use client'

import { useGetSelfHealingStatus } from '@/lib/api/hooks'
import { KPICard } from '@/components/dashboard/kpi-card'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { EndpointMeta } from '@/components/dashboard/endpoint-meta'
import { Panel } from '@/components/dashboard/panel'
import { Timestamp } from '@/components/dashboard/timestamp'
import { ErrorState } from '@/components/dashboard/error-state'
import { KPISkeleton } from '@/components/dashboard/skeleton'

export default function SelfHealingPage() {
  const selfHealing = useGetSelfHealingStatus(30)

  if (selfHealing.error) {
    return <ErrorState onRetry={() => void selfHealing.refetch()} />
  }

  const envelope = selfHealing.data
  const data = envelope?.data

  return (
    <div className="space-y-6" suppressHydrationWarning>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between" suppressHydrationWarning>
        <div>
          <p className="telemetry-label">endpoint /api/v1/self-healing/status</p>
          <h1 className="text-3xl font-bold uppercase tracking-[0.08em] text-foreground md:text-4xl">Self-Healing Status</h1>
          <p className="mt-1 text-sm text-muted-foreground">Decision stream and retrain trigger state.</p>
        </div>
        {envelope && (
          <div className="border border-border bg-card px-4 py-3">
            <div className="flex items-center gap-3">
              <StatusBadge status={data?.candidate_ready_for_promotion ? 'healthy' : 'warning'} label={data?.candidate_ready_for_promotion ? 'Candidate Ready' : 'Candidate Not Ready'} />
              <StatusBadge status={envelope.is_stale ? 'warning' : 'ok'} label={envelope.is_stale ? 'Stale' : 'Fresh'} />
            </div>
          </div>
        )}
      </div>

      {envelope && (
        <EndpointMeta
          endpoint="GET /api/v1/self-healing/status?limit=30"
          generatedAt={envelope.generated_at}
          isStale={envelope.is_stale}
          sourceOk={Object.values(envelope.source_status).every((source) => source.ok)}
        />
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" suppressHydrationWarning>
        {selfHealing.isLoading ? (
          <>
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
          </>
        ) : (
          <>
            <KPICard title="Latest Decision" value={data?.latest_decision ?? 'N/A'} />
            <KPICard
              title="Consecutive Drift"
              value={data?.consecutive_drift_count ?? 'N/A'}
              unit={data?.required_consecutive_drifts != null ? `/ ${data.required_consecutive_drifts}` : undefined}
              status={
                data?.consecutive_drift_count != null && data?.required_consecutive_drifts != null && data.consecutive_drift_count >= data.required_consecutive_drifts
                  ? 'warning'
                  : 'healthy'
              }
            />
            <KPICard
              title="Candidate Promotion"
              value={data?.candidate_ready_for_promotion ? 'READY' : 'WAIT'}
              status={data?.candidate_ready_for_promotion ? 'healthy' : 'warning'}
            />
            <KPICard
              title="Decisions Logged"
              value={data?.count ?? 0}
              description="from /api/v1/self-healing/status"
            />
          </>
        )}
      </div>

      <Panel title="Latest reason" subtitle="Current system rationale from latest decision fields">
        <div className="grid gap-3 md:grid-cols-2" suppressHydrationWarning>
          <div className="border border-border bg-background/60 p-3">
            <p className="telemetry-label">latest_reason</p>
            <p className="mt-1 text-sm text-foreground/90">{data?.latest_reason ?? 'N/A'}</p>
          </div>
          <div className="border border-border bg-background/60 p-3">
            <p className="telemetry-label">last_retrain_at_utc</p>
            <p className="mt-1 text-sm text-foreground/90">{data?.last_retrain_at_utc ? <Timestamp date={data.last_retrain_at_utc} format="full" /> : 'N/A'}</p>
          </div>
        </div>
      </Panel>

      <Panel title="Decision log" subtitle="Recent entries from /api/v1/self-healing/status:data.decisions">
        <div className="space-y-2" suppressHydrationWarning>
          {data?.decisions?.length ? (
            data.decisions.map((entry, index) => (
              <div key={`${entry.timestamp ?? 'row'}-${index}`} className="border border-border p-3" suppressHydrationWarning>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={entry.command_ok ? 'ok' : 'warning'} label={entry.command_ok ? 'command ok' : 'command fail'} />
                  <StatusBadge status={entry.dry_run ? 'healthy' : 'critical'} label={entry.dry_run ? 'dry run' : 'live'} />
                </div>
                <p className="mt-2 text-sm text-foreground/90">{entry.reason ?? 'No reason provided'}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {entry.timestamp ? <Timestamp date={entry.timestamp} format="full" /> : 'No timestamp'}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No decision entries available.</p>
          )}
        </div>
      </Panel>
    </div>
  )
}
