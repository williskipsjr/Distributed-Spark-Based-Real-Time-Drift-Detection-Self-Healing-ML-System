'use client'

import {
  LineChart,
  Line,
  Area,
  AreaChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { useGetDashboardSummary, useGetPredictions } from '@/lib/api/hooks'
import { useDemoData } from '@/lib/hooks/useDemoData'
import { KPICard } from '@/components/dashboard/kpi-card'
import { StatusBadge } from '@/components/dashboard/status-badge'
import { Timestamp } from '@/components/dashboard/timestamp'
import { KPISkeleton } from '@/components/dashboard/skeleton'
import { EndpointMeta } from '@/components/dashboard/endpoint-meta'
import { Panel } from '@/components/dashboard/panel'
import { Activity, TrendingUp, TrendingDown, Radar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Play, Square } from 'lucide-react'
import { useEffect, useState } from 'react'
import { DEMO_STATE_EVENT, getDemoState, startDemoPipeline, stopDemoPipeline } from '@/lib/demo/state'

// Custom tooltip component for better formatting
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || payload.length === 0) return null

  const data = payload[0]?.payload as { datetimeLabel?: string } | undefined
  
  return (
    <div
      className="rounded border border-border/80 bg-card/95 px-3 py-2 shadow-lg"
      style={{
        backgroundColor: 'rgba(10, 10, 10, 0.95)',
        border: '1px solid rgba(32, 35, 40, 0.9)',
      }}
    >
      <p className="text-xs font-semibold text-foreground/90 mb-1">
        {data?.datetimeLabel ?? 'Unknown'}
      </p>
      {payload.map((entry: any, index: number) => (
        <p key={index} className="text-xs" style={{ color: entry.color }}>
          <span className="font-medium">{entry.name}:</span> {entry.value?.toFixed(0)} MW
        </p>
      ))}
    </div>
  )
}

export default function OverviewPage() {
  const [demoEnabled, setDemoEnabled] = useState(false)
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [forecastStarted, setForecastStarted] = useState(false)
  const [visiblePointCount, setVisiblePointCount] = useState(0)

  useEffect(() => {
    const sync = () => {
      const state = getDemoState()
      setDemoEnabled(state.enabled)
      setPipelineRunning(state.pipelineRunning)
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

  const summary = useGetDashboardSummary()
  const predictions = useGetPredictions('24h', 48)
  const demoData = useDemoData()

  const useDemoSummary = demoEnabled || Boolean(summary.error)
  const useDemoPredictions = demoEnabled || Boolean(predictions.error)
  const demoMode = useDemoSummary || useDemoPredictions

  const activeSummary = useDemoSummary ? demoData.summary : summary
  const activePredictions = useDemoPredictions ? demoData.predictions : predictions
  const isLoading = activeSummary.isLoading || activePredictions.isLoading

  const summaryEnvelope = activeSummary.data
  const summaryData = summaryEnvelope?.data
  const predictionsEnvelope = activePredictions.data
  const predictionsData = predictionsEnvelope?.data
  const showForecast = pipelineRunning && forecastStarted

  const chartData =
    predictionsData?.points.map((point) => ({
      datetimeIso: point.timestamp ?? null,
      timestamp: point.timestamp
        ? new Date(point.timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'Unknown',
      datetimeLabel: point.timestamp
        ? new Date(point.timestamp).toLocaleString('en-US', {
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })
        : 'Unknown',
      predicted: (point as { predicted_mw?: number; predicted_load?: number }).predicted_mw ??
        (point as { predicted_load?: number }).predicted_load ??
        null,
      actual: (point as { actual_mw?: number; actual_load?: number }).actual_mw ??
        (point as { actual_load?: number }).actual_load ??
        null,
      error: (point as { abs_error_mw?: number; error?: number }).abs_error_mw ??
        (point as { error?: number }).error ??
        null,
      projection: (point as { projection_mw?: number; predicted_mw?: number }).projection_mw ??
        (point as { predicted_mw?: number }).predicted_mw ??
        null,
    })) || []

  const visibleChartData = showForecast
    ? chartData.slice(0, Math.min(chartData.length, Math.max(visiblePointCount, 0)))
    : []

  useEffect(() => {
    if (!showForecast) {
      setVisiblePointCount(0)
      return
    }

    setVisiblePointCount((current) => (current > 0 ? current : Math.min(2, chartData.length)))

    const interval = setInterval(() => {
      setVisiblePointCount((current) => {
        if (current >= chartData.length) {
          return current
        }
        return current + 1
      })
    }, 900)

    return () => clearInterval(interval)
  }, [showForecast, chartData.length])

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

  // Calculate dynamic Y-axis domain based on data range
  const calculateYAxisDomain = () => {
    if (visibleChartData.length === 0) return [0, 100]
    
    const allValues = visibleChartData
      .flatMap((d) => [d.predicted, d.actual, d.projection])
      .filter((v) => v != null && typeof v === 'number')
    
    if (allValues.length === 0) return [0, 100]
    
    const min = Math.min(...allValues)
    const max = Math.max(...allValues)
    const padding = 200 // Small padding to show variation clearly
    
    return [Math.floor(min - padding), Math.ceil(max + padding)]
  }

  const yAxisDomain = calculateYAxisDomain()

  const handleStartLoadForecast = () => {
    setForecastStarted(true)
    startDemoPipeline()
  }

  const handleStopLoadForecast = () => {
    setForecastStarted(false)
    stopDemoPipeline()
  }

  return (
    <div className="space-y-6" suppressHydrationWarning>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between" suppressHydrationWarning>
        <div>
          <p className="telemetry-label">endpoint /api/v1/dashboard/summary + /api/v1/predictions</p>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold uppercase tracking-[0.08em] text-foreground md:text-4xl">Overview</h1>
            {demoMode && (
              <StatusBadge status="warning" label="live demo: simulated data" />
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {demoMode 
              ? 'Simulated real-time prediction telemetry with live streaming chart updates.'
              : 'Primary prediction telemetry with real-time serving quality indicators.'}
          </p>
        </div>
        <div className="flex items-center gap-2" suppressHydrationWarning>
          <Button
            onClick={handleStartLoadForecast}
            className="gap-2 border border-primary/40 bg-primary/20 text-primary hover:bg-primary/30"
            disabled={showForecast}
          >
            <Play className="h-4 w-4" />
            Start Load Forecast
          </Button>
          <Button
            onClick={handleStopLoadForecast}
            variant="destructive"
            className="gap-2 border border-red-500/35 bg-red-500/20 text-red-200 hover:bg-red-500/30"
            disabled={!showForecast}
          >
            <Square className="h-4 w-4" />
            Stop
          </Button>
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
        subtitle="Main stream from /api/v1/predictions with hourly load forecasting and datetime trace"
        right={<StatusBadge status="ok" label="hero chart" />}
      >
        <div className="space-y-4" suppressHydrationWarning>
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
          ) : !showForecast || visibleChartData.length === 0 ? (
            <div className="flex h-[420px] items-center justify-center border border-border bg-background/60 text-muted-foreground">
              <p className="text-sm uppercase tracking-[0.12em]">
                {!showForecast
                  ? 'Load forecast stopped. Click Start Load Forecast to stream telemetry.'
                  : 'No prediction data available'}
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={420}>
              <LineChart data={visibleChartData} margin={{ top: 16, right: 22, left: 0, bottom: 8 }}>
                <CartesianGrid 
                  strokeDasharray="3 4" 
                  stroke="rgba(255,255,255,0.08)" 
                  vertical={false}
                  horizontalPoints={[]}
                />
                <XAxis
                  dataKey="timestamp"
                  stroke="rgba(255,255,255,0.4)"
                  style={{ fontSize: '11px', fontWeight: 600 }}
                  tick={{ dy: 4 }}
                />
                <YAxis 
                  stroke="rgba(255,255,255,0.4)" 
                  style={{ fontSize: '11px', fontWeight: 600 }}
                  domain={yAxisDomain}
                  label={{ value: 'MW', angle: -90, position: 'insideLeft', offset: 8 }}
                  width={54}
                />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1 }} />
                <Legend 
                  wrapperStyle={{ paddingTop: '16px', fontSize: '12px' }}
                  iconType="line"
                  height={24}
                />
                
                {/* Predicted MW - Cyan */}
                <Line
                  type="natural"
                  dataKey="predicted"
                  stroke="#00d5ff"
                  dot={{ fill: '#00d5ff', r: 3.5, opacity: 0.7 }}
                  activeDot={{ r: 5.5, opacity: 1 }}
                  isAnimationActive={demoMode}
                  strokeWidth={3}
                  name="Predicted MW"
                  animationDuration={300}
                />
                
                {/* Actual MW - Lime/Yellow */}
                <Line
                  type="natural"
                  dataKey="actual"
                  stroke="#dfff00"
                  dot={{ fill: '#dfff00', r: 3.5, opacity: 0.7 }}
                  activeDot={{ r: 5.5, opacity: 1 }}
                  isAnimationActive={demoMode}
                  strokeWidth={3}
                  name="Actual MW"
                  animationDuration={300}
                />
                
                {/* Projection MW - Orange (Demo mode only) */}
                {demoMode && (
                  <Line
                    type="natural"
                    dataKey="projection"
                    stroke="#ff9a44"
                    strokeDasharray="6 3"
                    dot={{ fill: '#ff9a44', r: 3.5, opacity: 0.7 }}
                    activeDot={{ r: 5.5, opacity: 1 }}
                    isAnimationActive
                    strokeWidth={2.8}
                    name="Projection MW"
                    animationDuration={350}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          )}

          {showForecast && visibleChartData.length > 0 && (
            <div className="border border-border bg-background/60">
              <div className="grid grid-cols-[1.6fr_1fr_1fr_1fr] border-b border-border bg-card/70 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                <span>Hourly metric datetime</span>
                <span className="text-right">Actual MW</span>
                <span className="text-right">Predicted MW</span>
                <span className="text-right">Abs error</span>
              </div>
              {visibleChartData.slice(-6).reverse().map((row, idx) => (
                <div
                  key={`${row.datetimeIso ?? row.timestamp}-${idx}`}
                  className="grid grid-cols-[1.6fr_1fr_1fr_1fr] border-b border-border/70 px-3 py-2 text-xs last:border-b-0"
                >
                  <span className="text-foreground/90">{row.datetimeLabel}</span>
                  <span className="text-right text-foreground/90">
                    {row.actual != null ? row.actual.toFixed(1) : 'N/A'}
                  </span>
                  <span className="text-right text-secondary">
                    {row.predicted != null ? row.predicted.toFixed(1) : 'N/A'}
                  </span>
                  <span className="text-right text-warning">
                    {row.error != null ? row.error.toFixed(1) : 'N/A'}
                  </span>
                </div>
              ))}
            </div>
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
