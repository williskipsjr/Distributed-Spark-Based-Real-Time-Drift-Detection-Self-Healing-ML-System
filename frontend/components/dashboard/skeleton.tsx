import { cn } from '@/lib/utils'

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('p-4 rounded-lg border border-slate-200 dark:border-slate-800', className)}>
      <div className="space-y-3">
        <div className="h-4 w-24 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
        <div className="h-48 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
      </div>
    </div>
  )
}

export function KPISkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('p-4 rounded-lg border border-slate-200 dark:border-slate-800', className)}>
      <div className="space-y-2">
        <div className="h-4 w-20 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
        <div className="h-8 w-32 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
        <div className="h-3 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
      </div>
    </div>
  )
}

export function ListItemSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('p-3 rounded-md border border-slate-200 dark:border-slate-800', className)}>
      <div className="space-y-2">
        <div className="h-4 w-32 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
        <div className="h-3 w-24 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="p-3 rounded-md border border-slate-200 dark:border-slate-800">
          <div className="flex gap-3">
            <div className="h-4 w-32 bg-slate-200 dark:bg-slate-800 rounded animate-pulse flex-1" />
            <div className="h-4 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
            <div className="h-4 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  )
}
