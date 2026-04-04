'use client'

import { useGetModelsActive, useGetModelsVersions } from '@/lib/api/hooks'
import { useRecordedModelsData } from '@/lib/hooks/useRecordedModelsData'
import { DEMO_STATE_EVENT, getDemoState } from '@/lib/demo/state'
import { useEffect, useState } from 'react'
import { KPICard } from '@/components/dashboard/kpi-card'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { EndpointMeta } from '@/components/dashboard/endpoint-meta'
import { Panel } from '@/components/dashboard/panel'
import { Timestamp } from '@/components/dashboard/timestamp'
import { ErrorState } from '@/components/dashboard/error-state'
import { KPISkeleton } from '@/components/dashboard/skeleton'

export default function ModelsPage() {
  const [demoEnabled, setDemoEnabled] = useState(false)

  useEffect(() => {
    const sync = () => {
      setDemoEnabled(getDemoState().enabled)
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

  const modelsActive = useGetModelsActive()
  const modelVersions = useGetModelsVersions(30)
  const demoModels = useRecordedModelsData()

  const useDemoMode = demoEnabled || Boolean(modelsActive.error || modelVersions.error)
  const activeModels = useDemoMode ? demoModels.active : modelsActive
  const versionModels = useDemoMode ? demoModels.versions : modelVersions

  if (activeModels.error || versionModels.error) {
    return <ErrorState onRetry={() => void Promise.all([activeModels.refetch(), versionModels.refetch()])} />
  }

  const activeEnvelope = activeModels.data
  const versionsEnvelope = versionModels.data

  const active = activeEnvelope?.data
  const versions = versionsEnvelope?.data

  return (
    <div className="space-y-6" suppressHydrationWarning>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between" suppressHydrationWarning>
        <div>
          <p className="telemetry-label">endpoint /api/v1/models/active + /api/v1/models/versions</p>
          <h1 className="text-3xl font-bold uppercase tracking-[0.08em] text-foreground md:text-4xl">Model Versions</h1>
          <p className="mt-1 text-sm text-muted-foreground">Active model pointer and promotion history.</p>
        </div>
        <div className="border border-border bg-card px-4 py-3">
          <div className="flex items-center gap-3">
            <StatusBadge status={versions?.candidate_ready_for_promotion ? 'healthy' : 'warning'} label={versions?.candidate_ready_for_promotion ? 'Candidate Ready' : 'Candidate Pending'} />
            <StatusBadge status={activeEnvelope?.is_stale || versionsEnvelope?.is_stale ? 'warning' : 'ok'} label={activeEnvelope?.is_stale || versionsEnvelope?.is_stale ? 'Stale' : 'Fresh'} />
          </div>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        {activeEnvelope && (
          <EndpointMeta
            endpoint="GET /api/v1/models/active"
            generatedAt={activeEnvelope.generated_at}
            isStale={activeEnvelope.is_stale}
            sourceOk={activeEnvelope.source_status.active_model.ok}
          />
        )}
        {versionsEnvelope && (
          <EndpointMeta
            endpoint="GET /api/v1/models/versions?limit=30"
            generatedAt={versionsEnvelope.generated_at}
            isStale={versionsEnvelope.is_stale}
            sourceOk={Object.values(versionsEnvelope.source_status).every((source) => source.ok)}
          />
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" suppressHydrationWarning>
        {activeModels.isLoading || versionModels.isLoading ? (
          <>
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
          </>
        ) : (
          <>
            <KPICard title="Active Version" value={active?.active_model_version ?? 'N/A'} status="healthy" />
            <KPICard title="Candidate Version" value={versions?.candidate_version ?? 'N/A'} status={versions?.candidate_ready_for_promotion ? 'healthy' : 'warning'} />
            <KPICard title="Previous Version" value={active?.previous_model_version ?? 'N/A'} />
            <KPICard title="Events" value={versions?.count ?? 0} description="from /api/v1/models/versions" />
          </>
        )}
      </div>

      <Panel title="Active pointer" subtitle="Current production pointer from /api/v1/models/active">
        <div className="grid gap-3 md:grid-cols-2" suppressHydrationWarning>
          <div className="border border-border bg-background/60 p-3">
            <p className="telemetry-label">active_model_path</p>
            <p className="mt-1 break-all text-sm text-foreground/90">{active?.active_model_path ?? 'N/A'}</p>
          </div>
          <div className="border border-border bg-background/60 p-3">
            <p className="telemetry-label">promoted_at_utc</p>
            <p className="mt-1 text-sm text-foreground/90">{active?.promoted_at_utc ? <Timestamp date={active.promoted_at_utc} format="full" /> : 'N/A'}</p>
          </div>
        </div>
      </Panel>

      <Panel title="Promotion history" subtitle="Recent event stream from /api/v1/models/versions:data.events">
        <div className="space-y-2" suppressHydrationWarning>
          {versions?.events?.length ? (
            versions.events.map((event, index) => (
              <div key={`${event.timestamp ?? 'event'}-${index}`} className="border border-border p-3" suppressHydrationWarning>
                <div className="flex flex-wrap items-center gap-2" suppressHydrationWarning>
                  <StatusBadge status={event.pointer_updated ? 'healthy' : 'warning'} label={event.pointer_updated ? 'pointer updated' : 'no pointer update'} />
                  <StatusBadge status={event.decision === 'promote' ? 'ok' : 'warning'} label={event.decision ?? 'no decision'} />
                </div>
                <p className="mt-2 text-sm text-foreground/90">{event.reason ?? 'No reason provided'}</p>
                <p className="mt-1 text-xs text-muted-foreground">{event.timestamp ? <Timestamp date={event.timestamp} format="full" /> : 'No timestamp'}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No model version events available.</p>
          )}
        </div>
      </Panel>
    </div>
  )
}
