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
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Drift Detection</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track drift signals, feature shifts, and historical events.
          </p>
        </div>
        {driftEnvelope && (
          <div className="rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
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

      {driftEnvelope && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Source status</p>
              <p className="text-sm text-muted-foreground mt-1">
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
        <div className="p-6 rounded-xl border border-border bg-card">
          <h3 className="font-semibold text-foreground mb-4">Feature Drift Analysis</h3>

          <div className="space-y-2">
            {driftData.feature_drift.map((feature, idx) => (
              <div
                key={idx}
                className="p-3 rounded-md border border-border hover:bg-muted/50 transition-colors"
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
        </div>
      )}

      {/* Drift History Chart */}
      <div className="p-6 rounded-xl border border-border bg-card">
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">Drift Score Timeline</h3>
          <p className="text-sm text-muted-foreground mt-1">Historical drift detection scores</p>
        </div>

        {isLoading ? (
          <div className="h-64 bg-muted rounded animate-pulse" />
        ) : historyData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-muted-foreground">
            No drift history available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={historyData}>
              <defs>
                <linearGradient id="colorDrift" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border) / 0.5)" />
              <XAxis
                dataKey="timestamp"
                stroke="rgb(var(--color-muted-foreground) / 0.6)"
                style={{ fontSize: '12px' }}
              />
              <YAxis stroke="rgb(var(--color-muted-foreground) / 0.6)" style={{ fontSize: '12px' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--color-card))',
                  border: '1px solid rgb(var(--color-border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'rgb(var(--color-foreground))' }}
              />
              <Area
                type="monotone"
                dataKey="prediction_drift_score"
                stroke="#f59e0b"
                fillOpacity={1}
                fill="url(#colorDrift)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Drifted Features Count Chart */}
      <div className="p-6 rounded-xl border border-border bg-card">
        <div className="mb-4">
          <h3 className="font-semibold text-foreground">Drift Event Timeline</h3>
          <p className="text-sm text-muted-foreground mt-1">Number of drift events over time</p>
        </div>

        {isLoading ? (
          <div className="h-64 bg-muted rounded animate-pulse" />
        ) : historyData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-muted-foreground">
            No drift history available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={historyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border) / 0.5)" />
              <XAxis
                dataKey="timestamp"
                stroke="rgb(var(--color-muted-foreground) / 0.6)"
                style={{ fontSize: '12px' }}
              />
              <YAxis stroke="rgb(var(--color-muted-foreground) / 0.6)" style={{ fontSize: '12px' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgb(var(--color-card))',
                  border: '1px solid rgb(var(--color-border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'rgb(var(--color-foreground))' }}
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
      </div>
    </div>
  )
}
