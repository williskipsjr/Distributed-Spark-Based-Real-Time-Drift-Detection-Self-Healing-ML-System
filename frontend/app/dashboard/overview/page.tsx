'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { useGetDashboardSummary, useGetPredictions } from '@/lib/api/hooks'
import { KPICard } from '@/components/dashboard/kpi-card'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { Timestamp } from '@/components/dashboard/timestamp'
import { ErrorState } from '@/components/dashboard/error-state'
import { KPISkeleton } from '@/components/dashboard/skeleton'
import { EndpointMeta } from '@/components/dashboard/endpoint-meta'
import { Panel } from '@/components/dashboard/panel'
import { Activity, TrendingUp, TrendingDown, Radar } from 'lucide-react'

export default function OverviewPage() {
  const summary = useGetDashboardSummary()
  const predictions = useGetPredictions('24h', 48)

  const isLoading = summary.isLoading || predictions.isLoading
  const error = summary.error || predictions.error

  const summaryEnvelope = summary.data
  const summaryData = summaryEnvelope?.data
  const predictionsEnvelope = predictions.data
  const predictionsData = predictionsEnvelope?.data

  const chartData =
    predictionsData?.points.map((point) => ({
      timestamp: point.timestamp
        ? new Date(point.timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'Unknown',
      predicted: point.predicted_mw,
      actual: point.actual_mw,
      error: point.abs_error_mw,
    })) || []

  if (error) {
    return <ErrorState onRetry={() => void Promise.all([summary.refetch(), predictions.refetch()])} />
  }

  const freshnessStatus = summaryEnvelope?.is_stale ? 'warning' : 'healthy'
  const healthStatus = summaryData
    ? summaryData.health_level === 'ok'
      ? 'healthy'
      : summaryData.health_level === 'degraded'
        ? 'warning'
        : 'critical'
    : 'warning'

  const sourceStatusBadges: Array<[string, boolean]> = summaryEnvelope
    ? [
        ['Hourly metrics', summaryEnvelope.source_status.hourly_metrics.ok],
        ['Drift report', summaryEnvelope.source_status.drift_report.ok],
        ['Active model', summaryEnvelope.source_status.active_model.ok],
      ]
    : []

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="telemetry-label">endpoint /api/v1/dashboard/summary + /api/v1/predictions</p>
          <h1 className="text-3xl font-bold uppercase tracking-[0.08em] text-foreground md:text-4xl">Overview</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Primary prediction telemetry with real-time serving quality indicators.
          </p>
        </div>
        {summaryEnvelope && (
          <div className="border border-border bg-card/80 px-4 py-3">
            <div className="flex items-center gap-3">
              <StatusBadge status={healthStatus} label={summaryData ? summaryData.health_level : 'Unknown'} />
              <StatusBadge status={freshnessStatus} label={summaryEnvelope.is_stale ? 'Stale' : 'Fresh'} />
              {summaryData?.drift_detected && <StatusBadge status="critical" label="Drift Detected" />}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              {summaryEnvelope.data_as_of ? (
                <Timestamp date={summaryEnvelope.data_as_of} format="relative" />
              ) : (
                'No data timestamp available'
              )}
            </div>
          </div>
        )}
      </div>

      <Panel
        title="Prediction telemetry"
        subtitle="Main stream from /api/v1/predictions with actual vs predicted power load"
        right={<StatusBadge status="ok" label="hero chart" />}
      >
        <div className="space-y-4">
          {predictionsEnvelope && (
            <EndpointMeta
              endpoint="GET /api/v1/predictions?window=24h&limit=48"
              generatedAt={predictionsEnvelope.generated_at}
              isStale={predictionsEnvelope.is_stale}
              sourceOk={predictionsEnvelope.source_status.predictions.ok}
            />
          )}
          {isLoading ? (
            <div className="h-[420px] animate-pulse bg-muted" />
          ) : chartData.length === 0 ? (
            <div className="flex h-[420px] items-center justify-center border border-border bg-background/60 text-muted-foreground">
              <p className="text-sm uppercase tracking-[0.12em]">No prediction data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={chartData} margin={{ top: 16, right: 22, left: 6, bottom: 8 }}>
                <CartesianGrid strokeDasharray="2 6" stroke="rgba(255,255,255,0.12)" vertical={false} />
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
                    color: '#f4f4f4',
                  }}
                  labelStyle={{ color: '#dfff00' }}
                />
                <Legend wrapperStyle={{ paddingTop: '12px', fontSize: '12px' }} />
                <Line
                  type="monotone"
                  dataKey="predicted"
                  stroke="#00d5ff"
                  dot={false}
                  isAnimationActive={false}
                  strokeWidth={2.7}
                  name="Predicted MW"
                />
                <Line
                  type="monotone"
                  dataKey="actual"
                  stroke="#dfff00"
                  dot={false}
                  isAnimationActive={false}
                  strokeWidth={2.2}
                  name="Actual MW"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {isLoading ? (
          <>
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
            <KPISkeleton />
          </>
        ) : (
          <>
            <KPICard
              title="Actual Load"
              value={summaryData?.actual_mw?.toFixed(1) ?? 'N/A'}
              unit="MW"
              icon={<TrendingUp className="h-4 w-4" />}
              status={healthStatus === 'critical' ? 'critical' : healthStatus === 'warning' ? 'warning' : 'healthy'}
            />
            <KPICard
              title="Predicted Load"
              value={summaryData?.predicted_mw?.toFixed(1) ?? 'N/A'}
              unit="MW"
              status={summaryData?.drift_detected ? 'warning' : 'healthy'}
            />
            <KPICard
              title="Absolute Error"
              value={summaryData?.abs_error_mw?.toFixed(1) ?? 'N/A'}
              unit="MW"
              icon={<TrendingDown className="h-4 w-4" />}
              status={summaryData?.pct_error && summaryData.pct_error > 5 ? 'warning' : 'healthy'}
            />
            <KPICard
              title="Active Model"
              value={summaryData?.active_model_version || 'N/A'}
              icon={<Radar className="h-4 w-4" />}
              description="from /api/v1/dashboard/summary"
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.45fr_1fr]">
        <Panel
          title="Summary endpoint state"
          subtitle="KPI stream from /api/v1/dashboard/summary"
          right={<StatusBadge status={summaryData?.drift_detected ? 'critical' : 'healthy'} label={summaryData?.drift_detected ? 'drift true' : 'drift false'} />}
        >
          {summaryEnvelope && (
            <div className="space-y-4">
              <EndpointMeta
                endpoint="GET /api/v1/dashboard/summary"
                generatedAt={summaryEnvelope.generated_at}
                isStale={summaryEnvelope.is_stale}
                sourceOk={Object.values(summaryEnvelope.source_status).every((source) => source.ok)}
              />
              <div className="grid gap-3 md:grid-cols-3">
                <div className="border border-border bg-background/60 p-3">
                  <p className="telemetry-label">health level</p>
                  <p className="mt-1 text-lg font-bold uppercase tracking-[0.08em]">{summaryData?.health_level ?? 'unknown'}</p>
                </div>
                <div className="border border-border bg-background/60 p-3">
                  <p className="telemetry-label">latest_timestamp</p>
                  <p className="mt-1 text-sm text-foreground/90">
                    {summaryData?.latest_timestamp ? <Timestamp date={summaryData.latest_timestamp} format="full" /> : 'N/A'}
                  </p>
                </div>
                <div className="border border-border bg-background/60 p-3">
                  <p className="telemetry-label">pct_error</p>
                  <p className="mt-1 text-lg font-bold">
                    {summaryData?.pct_error != null ? `${summaryData.pct_error.toFixed(2)}%` : 'N/A'}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {sourceStatusBadges.map(([label, ok]) => (
                  <StatusBadge
                    key={label}
                    status={ok ? 'ok' : 'warning'}
                    label={`${label} ${ok ? 'ok' : 'degraded'}`}
                  />
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel
          title="Prediction quality"
          subtitle="Summary metrics from /api/v1/predictions"
          right={<Activity className="h-4 w-4 text-secondary" />}
        >
          {predictionsData && (
            <div className="space-y-3">
              <div className="border border-border bg-background/60 p-3">
                <p className="telemetry-label">window</p>
                <p className="mt-1 text-lg font-bold uppercase">{predictionsData.window}</p>
              </div>
              <div className="border border-border bg-background/60 p-3">
                <p className="telemetry-label">mae_mw</p>
                <p className="mt-1 text-lg font-bold text-secondary">
                  {predictionsData.summary.mae_mw != null ? predictionsData.summary.mae_mw.toFixed(2) : 'N/A'}
                </p>
              </div>
              <div className="border border-border bg-background/60 p-3">
                <p className="telemetry-label">rmse_mw</p>
                <p className="mt-1 text-lg font-bold text-secondary">
                  {predictionsData.summary.rmse_mw != null ? predictionsData.summary.rmse_mw.toFixed(2) : 'N/A'}
                </p>
              </div>
              <div className="border border-border bg-background/60 p-3">
                <p className="telemetry-label">mape_pct</p>
                <p className="mt-1 text-lg font-bold text-secondary">
                  {predictionsData.summary.mape_pct != null ? `${predictionsData.summary.mape_pct.toFixed(2)}%` : 'N/A'}
                </p>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
