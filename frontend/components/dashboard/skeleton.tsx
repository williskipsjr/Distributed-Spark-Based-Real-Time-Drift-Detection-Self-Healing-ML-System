import { cn } from '@/lib/utils'

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('border border-border p-4', className)}>
      <div className="space-y-3">
        <div className="h-3 w-24 animate-pulse bg-muted" />
        <div className="h-48 animate-pulse bg-muted" />
      </div>
    </div>
  )
}

export function KPISkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('border border-border p-4', className)}>
      <div className="space-y-2">
        <div className="h-3 w-20 animate-pulse bg-muted" />
        <div className="h-8 w-32 animate-pulse bg-muted" />
        <div className="h-3 w-16 animate-pulse bg-muted" />
      </div>
    </div>
  )
}

export function ListItemSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('border border-border p-3', className)}>
      <div className="space-y-2">
        <div className="h-4 w-32 animate-pulse bg-muted" />
        <div className="h-3 w-24 animate-pulse bg-muted" />
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="border border-border p-3">
          <div className="flex gap-3">
            <div className="h-4 w-32 flex-1 animate-pulse bg-muted" />
            <div className="h-4 w-16 animate-pulse bg-muted" />
            <div className="h-4 w-16 animate-pulse bg-muted" />
          </div>
        </div>
      ))}
    </div>
  )
}
