import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status:
    | 'healthy'
    | 'warning'
    | 'critical'
    | 'running'
    | 'stopped'
    | 'error'
    | 'ok'
    | 'degraded'
    | 'starting'
    | 'stopping'
    | 'failed'
  label?: string
  className?: string
}

const statusColorMap = {
  healthy: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  warning: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  critical: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
  error: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
  running: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  stopped: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border-slate-500/30',
  ok: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  degraded: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  starting: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  stopping: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  failed: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
}

const statusDotMap = {
  healthy: 'bg-emerald-500',
  warning: 'bg-amber-500',
  critical: 'bg-red-500',
  error: 'bg-red-500',
  running: 'bg-emerald-500',
  stopped: 'bg-slate-400',
  ok: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  starting: 'bg-amber-500',
  stopping: 'bg-amber-500',
  failed: 'bg-red-500',
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const displayLabel = label || status.charAt(0).toUpperCase() + status.slice(1)

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold border transition-all',
        statusColorMap[status],
        className
      )}
    >
      <div className={cn('w-2 h-2 rounded-full', statusDotMap[status])} />
      {displayLabel}
    </div>
  )
}
