import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface KPICardProps {
  title: string
  value: string | number
  unit?: string
  icon?: ReactNode
  status?: 'healthy' | 'warning' | 'critical'
  trend?: number
  description?: string
  className?: string
}

const trendColorMap = {
  positive: 'text-primary',
  negative: 'text-red-400',
  neutral: 'text-muted-foreground',
}

export function KPICard({
  title,
  value,
  unit,
  icon,
  status,
  trend,
  description,
  className,
}: KPICardProps) {
  const getTrendColor = () => {
    if (!trend) return 'neutral'
    return trend > 0 ? 'positive' : trend < 0 ? 'negative' : 'neutral'
  }

  const statusBgMap = {
    healthy: 'border-primary/40',
    warning: 'border-[color:var(--warning)]/50',
    critical: 'border-red-500/50',
  }

  return (
    <div
      className={cn(
        'border bg-card p-5 md:p-6',
        'border-border',
        status && statusBgMap[status],
        className
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="telemetry-label mb-2">{title}</p>
          <div className="flex items-baseline gap-2">
            <p className="telemetry-kpi text-foreground">{value}</p>
            {unit && <p className="telemetry-kpi-unit">{unit}</p>}
          </div>
        </div>
        {icon && (
          <div className="ml-4 flex-shrink-0 border border-border bg-background/70 p-3 text-secondary">
            {icon}
          </div>
        )}
      </div>

      {(trend !== undefined || description) && (
        <div className="flex items-center justify-between border-t border-border pt-4">
          {trend !== undefined && (
            <p className={cn('text-xs font-semibold uppercase tracking-[0.1em]', trendColorMap[getTrendColor()])}>
              {trend > 0 ? '↑ +' : trend < 0 ? '↓ ' : '→ '}{Math.abs(trend).toFixed(1)}%
            </p>
          )}
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
      )}
    </div>
  )
}
