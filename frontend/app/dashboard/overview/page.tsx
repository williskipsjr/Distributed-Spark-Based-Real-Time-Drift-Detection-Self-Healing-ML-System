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
import { Activity, TrendingUp, TrendingDown } from 'lucide-react'

export default function OverviewPage() {
  const summary = useGetDashboardSummary()
  const predictions = useGetPredictions('24h', 48)

  const isLoading = summary.isLoading || predictions.isLoading
  const error = summary.error || predictions.error

  const summaryEnvelope = summary.data
  const summaryData = summaryEnvelope?.data
  const predictionsData = predictions.data?.data

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
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-1">Overview</h1>
          <p className="text-sm text-muted-foreground">
            Latest load forecast, drift state, and serving health.
          </p>
        </div>
        {summaryEnvelope && (
          <div className="rounded-xl border border-border bg-card/80 px-4 py-3 shadow-sm">
            <div className="flex items-center gap-3">
              <StatusBadge
                status={healthStatus}
                label={summaryData ? summaryData.health_level : 'Unknown'}
              />
              <StatusBadge
                status={freshnessStatus}
                label={summaryEnvelope.is_stale ? 'Stale' : 'Fresh'}
              />
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

      {summaryEnvelope && (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Source status</p>
              <p className="text-sm text-muted-foreground mt-1">
                {summaryEnvelope.generated_at ? (
                  <Timestamp date={summaryEnvelope.generated_at} format="relative" />
                ) : (
                  'Generated just now'
                )}
              </p>
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
        </div>
      )}

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
                icon={<TrendingUp className="w-4 h-4" />}
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
                icon={<TrendingDown className="w-4 h-4" />}
                status={summaryData?.pct_error && summaryData.pct_error > 5 ? 'warning' : 'healthy'}
              />
              <KPICard
                title="Active Model"
                value={summaryData?.active_model_version || 'N/A'}
                description="Production serving version"
                icon={<Activity className="w-4 h-4" />}
              />
          </>
        )}
      </div>

      {/* System Status Card */}
        {summaryData && (
        <div className="p-6 rounded-xl border border-border bg-card hover:border-primary/30 transition-all">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-1">System Health</h3>
              <p className="text-sm text-muted-foreground">
                  Overall system operational status and freshness
              </p>
            </div>
            <StatusBadge
                status={healthStatus}
              label={
                  summaryData.health_level === 'ok'
                    ? 'Healthy'
                    : summaryData.health_level === 'degraded'
                      ? 'Degraded'
                      : 'Critical'
              }
            />
          </div>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
              <div className="rounded-lg border border-border/60 bg-background/50 p-3">
                <p className="text-muted-foreground text-xs uppercase tracking-wider mb-1">Latest timestamp</p>
                <p className="font-medium text-foreground">
                  {summaryData.latest_timestamp ? new Date(summaryData.latest_timestamp).toLocaleString() : 'N/A'}
                </p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/50 p-3">
                <p className="text-muted-foreground text-xs uppercase tracking-wider mb-1">Percentage error</p>
                <p className="font-medium text-foreground">
                  {summaryData.pct_error != null ? `${summaryData.pct_error.toFixed(2)}%` : 'N/A'}
                </p>
              </div>
              <div className="rounded-lg border border-border/60 bg-background/50 p-3">
                <p className="text-muted-foreground text-xs uppercase tracking-wider mb-1">Drift</p>
                <p className="font-medium text-foreground">
                  {summaryData.drift_detected ? 'Detected' : 'Normal'}
                </p>
              </div>
            </div>
        </div>
      )}

      {/* Predictions Chart */}
      <div className="p-6 rounded-xl border border-border bg-card">
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-foreground mb-1">
            Actual vs Predicted Values
          </h3>
          <p className="text-sm text-muted-foreground">
            Model predictions compared to actual observed values (last 10 data points)
          </p>
        </div>

        {isLoading ? (
          <div className="h-80 bg-muted rounded-lg animate-pulse" />
        ) : chartData.length === 0 ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground rounded-lg bg-muted/30">
            <p className="text-sm">No prediction data available yet</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border) / 0.5)" vertical={false} />
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
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                }}
                labelStyle={{ color: 'rgb(var(--color-foreground))' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Line
                type="monotone"
                dataKey="predicted"
                stroke="var(--color-primary)"
                dot={false}
                isAnimationActive={false}
                strokeWidth={2.5}
                name="Predicted"
              />
              <Line
                type="monotone"
                dataKey="actual"
                stroke="var(--color-chart-1)"
                dot={false}
                isAnimationActive={false}
                strokeWidth={2.5}
                name="Actual"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {predictionsData && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Window</p>
            <p className="text-sm font-medium text-foreground">{predictionsData.window}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">MAE</p>
            <p className="text-sm font-medium text-foreground">
              {predictionsData.summary.mae_mw != null ? `${predictionsData.summary.mae_mw.toFixed(1)} MW` : 'N/A'}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">MAPE</p>
            <p className="text-sm font-medium text-foreground">
              {predictionsData.summary.mape_pct != null ? `${predictionsData.summary.mape_pct.toFixed(2)}%` : 'N/A'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
