'use client'

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'
import { useGetDriftCurrent, useGetDriftHistory } from '@/lib/api/hooks'
import { KPICard } from '@/components/dashboard/kpi-card'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { Timestamp } from '@/components/dashboard/timestamp'
import { ErrorState } from '@/components/dashboard/error-state'
import { KPISkeleton } from '@/components/dashboard/skeleton'
import { EndpointMeta } from '@/components/dashboard/endpoint-meta'
import { Panel } from '@/components/dashboard/panel'
import { AlertTriangle, Activity } from 'lucide-react'

export default function DriftPage() {
  const driftCurrent = useGetDriftCurrent()
  const driftHistory = useGetDriftHistory(20)

  const isLoading = driftCurrent.isLoading || driftHistory.isLoading
  const error = driftCurrent.error || driftHistory.error

  const driftEnvelope = driftCurrent.data
  const driftData = driftEnvelope?.data
  const historyEnvelope = driftHistory.data
  const historyDataSource = historyEnvelope?.data

  const historyData =
    historyDataSource?.events.map((item) => ({
      timestamp: item.timestamp
        ? new Date(item.timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'Unknown',
      prediction_drift_score: item.prediction_drift_score,
      performance_drift_score: item.performance_drift_score,
      drift_detected: item.drift_detected ? 1 : 0,
    })) || []

  if (error) {
    return <ErrorState onRetry={() => void Promise.all([driftCurrent.refetch(), driftHistory.refetch()])} />
  }

  const freshnessStatus = driftEnvelope?.is_stale ? 'warning' : 'healthy'
  const currentStatus = driftData
    ? driftData.drift_detected
      ? 'critical'
      : driftData.drift_available
        ? 'healthy'
        : 'warning'
    : 'warning'

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="telemetry-label">endpoint /api/v1/drift/current + /api/v1/drift/history</p>
          <h1 className="text-3xl font-bold uppercase tracking-[0.08em] text-foreground md:text-4xl">Drift Analysis</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Drift truth panel prioritizing immediate anomaly state.
          </p>
        </div>
        {driftEnvelope && (
          <div className="border border-border bg-card px-4 py-3">
            <div className="flex items-center gap-3">
              <StatusBadge status={currentStatus} label={driftData?.drift_detected ? 'Drift detected' : driftData?.drift_available ? 'Stable' : 'Unavailable'} />
              <StatusBadge status={freshnessStatus} label={driftEnvelope.is_stale ? 'Stale' : 'Fresh'} />
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {driftData?.detected_at ? <Timestamp date={driftData.detected_at} format="relative" /> : 'No detection timestamp available'}
            </div>
          </div>
        )}
      </div>

      {driftEnvelope && driftData && (
        <Panel title="Drift state" subtitle="Primary state from /api/v1/drift/current">
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-[1.4fr_1fr]">
              <div className={`border p-5 ${driftData.drift_detected ? 'border-red-500/50 bg-red-500/10' : 'border-primary/40 bg-primary/10'}`}>
                <p className="telemetry-label">drift_detected</p>
                <p className={`mt-2 text-4xl font-bold uppercase tracking-[0.08em] ${driftData.drift_detected ? 'text-red-400' : 'text-primary'}`}>
                  {String(driftData.drift_detected)}
                </p>
                <p className="mt-3 text-sm text-foreground/90">
                  {driftData.drift_detected ? 'Action recommended: inspect drift scores and trigger mitigation path.' : 'No active drift trigger in current snapshot.'}
                </p>
              </div>
              <div className="space-y-3">
                <div className="border border-border bg-background/60 p-3">
                  <p className="telemetry-label">detected_at</p>
                  <p className="mt-1 text-sm">
                    {driftData.detected_at ? <Timestamp date={driftData.detected_at} format="full" /> : 'N/A'}
                  </p>
                </div>
                <div className="border border-border bg-background/60 p-3">
                  <p className="telemetry-label">drift_available</p>
                  <div className="mt-1">
                    <StatusBadge status={driftData.drift_available ? 'ok' : 'warning'} label={String(driftData.drift_available)} />
                  </div>
                </div>
              </div>
            </div>
            <EndpointMeta
              endpoint="GET /api/v1/drift/current"
              generatedAt={driftEnvelope.generated_at}
              isStale={driftEnvelope.is_stale}
              sourceOk={driftEnvelope.source_status.drift_report.ok}
            />
          </div>
        </Panel>
      )}

      {driftEnvelope && (
        <div className="border border-border bg-card p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="telemetry-label">source status</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {driftEnvelope.generated_at ? <Timestamp date={driftEnvelope.generated_at} format="relative" /> : 'Generated just now'}
              </p>
            </div>
            <StatusBadge
              status={driftEnvelope.source_status.drift_report.ok ? 'ok' : 'warning'}
              label={driftEnvelope.source_status.drift_report.ok ? 'Drift report ok' : 'Drift report degraded'}
            />
          </div>
        </div>
      )}

      {driftData && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {isLoading ? (
            <>
              <KPISkeleton />
              <KPISkeleton />
              <KPISkeleton />
            </>
          ) : (
            <>
              <KPICard
                title="Prediction Drift"
                value={driftData.metrics.prediction_drift.detected ? 'Detected' : 'Clear'}
                status={driftData.metrics.prediction_drift.detected ? 'warning' : 'healthy'}
                icon={driftData.metrics.prediction_drift.detected ? <AlertTriangle className="w-4 h-4" /> : <Activity className="w-4 h-4" />}
                description={
                  driftData.metrics.prediction_drift.score != null
                    ? `Score ${driftData.metrics.prediction_drift.score.toFixed(3)}`
                    : 'No score available'
                }
              />
              <KPICard
                title="Performance Drift"
                value={driftData.metrics.performance_drift.detected ? 'Detected' : 'Clear'}
                status={driftData.metrics.performance_drift.detected ? 'warning' : 'healthy'}
                description={
                  driftData.metrics.performance_drift.score != null
                    ? `Score ${driftData.metrics.performance_drift.score.toFixed(3)}`
                    : 'No score available'
                }
              />
              <KPICard
                title="Feature Drifted"
                value={driftData.feature_drift.filter((f) => f.drifted).length}
                unit={`/ ${driftData.feature_drift.length}`}
                description="Features with shifts"
              />
            </>
          )}
        </div>
      )}

      {/* Features Table */}
      {driftData && driftData.feature_drift.length > 0 && (
        <Panel title="Feature drift" subtitle="Feature-level drift flags from /api/v1/drift/current">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-foreground">Feature Drift Analysis</h3>

          <div className="space-y-2">
            {driftData.feature_drift.map((feature, idx) => (
              <div
                key={idx}
                className="border border-border p-3"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground text-sm">
                      {feature.feature || 'Unnamed feature'}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <p className="text-xs text-muted-foreground">
                        KS: {feature.ks_score != null ? feature.ks_score.toFixed(3) : 'N/A'}
                      </p>
                      <span className="text-muted-foreground">•</span>
                      <p className="text-xs text-muted-foreground">
                        PSI: {feature.psi_score != null ? feature.psi_score.toFixed(3) : 'N/A'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-sm font-semibold text-foreground">
                        {feature.ks_score != null ? feature.ks_score.toFixed(3) : 'N/A'}
                      </p>
                      <p className="text-xs text-muted-foreground">KS Score</p>
                    </div>
                    <StatusBadge
                      status={feature.drifted ? 'warning' : 'healthy'}
                      label={feature.drifted ? 'Drifted' : 'Normal'}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Drift History Chart */}
      <Panel title="Drift timeline" subtitle="Historical event scores from /api/v1/drift/history">
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">Drift Score Timeline</h3>
          <p className="mt-1 text-sm text-muted-foreground">Historical drift detection scores</p>
        </div>
        {historyEnvelope && (
          <div className="mb-4">
            <EndpointMeta
              endpoint="GET /api/v1/drift/history?limit=20"
              generatedAt={historyEnvelope.generated_at}
              isStale={historyEnvelope.is_stale}
              sourceOk={historyEnvelope.source_status.drift_history.ok}
            />
          </div>
        )}

        {isLoading ? (
          <div className="h-64 animate-pulse bg-muted" />
        ) : historyData.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            No drift history available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={historyData}>
              <defs>
                <linearGradient id="colorDrift" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00d5ff" stopOpacity={0.85} />
                  <stop offset="95%" stopColor="#00d5ff" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="2 6" stroke="rgba(255,255,255,0.12)" />
              <XAxis
                dataKey="timestamp"
                stroke="rgba(255,255,255,0.55)"
                style={{ fontSize: '11px', fontWeight: 600 }}
              />
              <YAxis stroke="rgba(255,255,255,0.55)" style={{ fontSize: '11px', fontWeight: 600 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #202328',
                  borderRadius: '0px',
                }}
                labelStyle={{ color: '#dfff00' }}
              />
              <Area
                type="monotone"
                dataKey="prediction_drift_score"
                stroke="#00d5ff"
                fillOpacity={1}
                fill="url(#colorDrift)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Panel>

      {/* Drifted Features Count Chart */}
      <Panel title="Drift event bars" subtitle="Binary drift flags from /api/v1/drift/history">
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">Drift Event Timeline</h3>
          <p className="mt-1 text-sm text-muted-foreground">Number of drift events over time</p>
        </div>

        {isLoading ? (
          <div className="h-64 animate-pulse bg-muted" />
        ) : historyData.length === 0 ? (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            No drift history available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={historyData}>
              <CartesianGrid strokeDasharray="2 6" stroke="rgba(255,255,255,0.12)" />
              <XAxis
                dataKey="timestamp"
                stroke="rgba(255,255,255,0.55)"
                style={{ fontSize: '11px', fontWeight: 600 }}
              />
              <YAxis stroke="rgba(255,255,255,0.55)" style={{ fontSize: '11px', fontWeight: 600 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0a0a0a',
                  border: '1px solid #202328',
                  borderRadius: '0px',
                }}
                labelStyle={{ color: '#dfff00' }}
              />
              <Bar
                dataKey="drift_detected"
                fill="#ef4444"
                isAnimationActive={false}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Panel>
    </div>
  )
}
