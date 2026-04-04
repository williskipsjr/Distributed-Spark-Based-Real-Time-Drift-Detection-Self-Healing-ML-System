import { cn } from '@/lib/utils'

interface LogLine {
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error'
  message: string
}

interface LogsPanelProps {
  title: string
  lines: LogLine[]
  className?: string
}

const levelClassMap: Record<LogLine['level'], string> = {
  debug: 'text-foreground/70',
  info: 'text-cyan-300',
  warning: 'text-amber-300',
  error: 'text-red-400',
}

export function LogsPanel({ title, lines, className }: LogsPanelProps) {
  return (
    <section className={cn('border border-border bg-background/75', className)}>
      <header className="border-b border-border px-4 py-3">
        <h3 className="telemetry-label">{title}</h3>
      </header>
      <div className="max-h-72 space-y-1 overflow-y-auto px-4 py-3 font-mono text-xs">
        {lines.length === 0 ? (
          <p className="text-muted-foreground">No logs available</p>
        ) : (
          lines.map((line, index) => (
            <p key={`${line.timestamp}-${index}`} className={cn('leading-relaxed', levelClassMap[line.level])}>
              <span className="text-foreground/40">{new Date(line.timestamp).toLocaleTimeString()}</span>{' '}
              <span className="uppercase tracking-wide">[{line.level}]</span> {line.message}
            </p>
          ))
        )}
      </div>
    </section>
  )
}
