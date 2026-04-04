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
  healthy: 'bg-primary/10 text-primary border-primary/35',
  warning: 'bg-[color:var(--warning)]/15 text-[color:var(--warning)] border-[color:var(--warning)]/35',
  critical: 'bg-red-500/15 text-red-400 border-red-500/35',
  error: 'bg-red-500/15 text-red-400 border-red-500/35',
  running: 'bg-primary/10 text-primary border-primary/35',
  stopped: 'bg-muted text-muted-foreground border-border',
  ok: 'bg-primary/10 text-primary border-primary/35',
  degraded: 'bg-[color:var(--warning)]/15 text-[color:var(--warning)] border-[color:var(--warning)]/35',
  starting: 'bg-[color:var(--warning)]/15 text-[color:var(--warning)] border-[color:var(--warning)]/35',
  stopping: 'bg-[color:var(--warning)]/15 text-[color:var(--warning)] border-[color:var(--warning)]/35',
  failed: 'bg-red-500/15 text-red-400 border-red-500/35',
}

const statusDotMap = {
  healthy: 'bg-primary',
  warning: 'bg-[color:var(--warning)]',
  critical: 'bg-red-500',
  error: 'bg-red-500',
  running: 'bg-primary',
  stopped: 'bg-muted-foreground',
  ok: 'bg-primary',
  degraded: 'bg-[color:var(--warning)]',
  starting: 'bg-[color:var(--warning)]',
  stopping: 'bg-[color:var(--warning)]',
  failed: 'bg-red-500',
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const displayLabel = label || status.charAt(0).toUpperCase() + status.slice(1)

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.11em] border',
        statusColorMap[status],
        className
      )}
    >
      <div className={cn('w-2 h-2 rounded-full', statusDotMap[status])} />
      {displayLabel}
    </div>
  )
}
