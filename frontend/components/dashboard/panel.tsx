import { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PanelProps {
  title?: string
  subtitle?: string
  right?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
}

export function Panel({
  title,
  subtitle,
  right,
  children,
  className,
  contentClassName,
}: PanelProps) {
  return (
    <section
      className={cn(
        'border border-border bg-card/95',
        className
      )}
    >
      {(title || subtitle || right) && (
        <header className="border-b border-border px-5 py-4 md:px-6 md:py-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              {title && <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-muted-foreground">{title}</h2>}
              {subtitle && <p className="mt-2 text-sm text-foreground/80">{subtitle}</p>}
            </div>
            {right}
          </div>
        </header>
      )}
      <div className={cn('px-5 py-4 md:px-6 md:py-5', contentClassName)}>{children}</div>
    </section>
  )
}
