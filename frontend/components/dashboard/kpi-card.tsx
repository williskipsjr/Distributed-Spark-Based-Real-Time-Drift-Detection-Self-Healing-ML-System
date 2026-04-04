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
  positive: 'text-green-600 dark:text-green-400',
  negative: 'text-red-600 dark:text-red-400',
  neutral: 'text-slate-600 dark:text-slate-400',
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
    healthy: 'bg-emerald-500/10 border-emerald-500/30',
    warning: 'bg-amber-500/10 border-amber-500/30',
    critical: 'bg-red-500/10 border-red-500/30',
  }

  return (
    <div
      className={cn(
        'p-6 rounded-xl border transition-all duration-300',
        'bg-card border-border hover:border-primary/40 hover:shadow-lg',
        status && statusBgMap[status],
        className
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="text-xs uppercase font-semibold text-muted-foreground/70 tracking-wider mb-2">{title}</p>
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-bold text-foreground">{value}</p>
            {unit && <p className="text-sm font-medium text-muted-foreground">{unit}</p>}
          </div>
        </div>
        {icon && (
          <div className="p-3 rounded-lg bg-primary/10 text-primary ml-4 flex-shrink-0">
            {icon}
          </div>
        )}
      </div>

      {(trend !== undefined || description) && (
        <div className="flex items-center justify-between pt-4 border-t border-border/50">
          {trend !== undefined && (
            <p className={cn('text-sm font-semibold', trendColorMap[getTrendColor()])}>
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
