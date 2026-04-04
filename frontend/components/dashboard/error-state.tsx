import { AlertCircle, RotateCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  className?: string
}

export function ErrorState({
  title = 'Something went wrong',
  message = 'Failed to load data. Please try again.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'p-6 rounded-lg border border-red-500/20 bg-red-500/5 flex flex-col items-center gap-4',
        className
      )}
    >
      <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
      <div className="text-center">
        <h3 className="font-semibold text-red-900 dark:text-red-100">{title}</h3>
        <p className="text-sm text-red-700 dark:text-red-300 mt-1">{message}</p>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="gap-2"
        >
          <RotateCw className="w-3 h-3" />
          Try Again
        </Button>
      )}
    </div>
  )
}
