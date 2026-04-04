import { formatDistanceToNow, format } from 'date-fns'
import { cn } from '@/lib/utils'

interface TimestampProps {
  date: string | Date
  format?: 'relative' | 'full'
  className?: string
  showIcon?: boolean
}

export function Timestamp({
  date,
  format: formatType = 'relative',
  className,
  showIcon = false,
}: TimestampProps) {
  const dateObj = typeof date === 'string' ? new Date(date) : date
  
  const displayText =
    formatType === 'relative'
      ? formatDistanceToNow(dateObj, { addSuffix: true })
      : format(dateObj, 'MMM d, yyyy HH:mm:ss')

  return (
    <span
      className={cn('text-xs text-slate-500 dark:text-slate-400', className)}
      title={format(dateObj, 'PPpp')}
    >
      {showIcon && '🕐 '}
      {displayText}
    </span>
  )
}
