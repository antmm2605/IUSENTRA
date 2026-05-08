import { cn } from '@/lib/utils'

export function IusSkeletonTable({
  rows = 5,
  columns = 4,
  className,
}: {
  rows?: number
  columns?: number
  className?: string
}) {
  return (
    <div className={cn('ius-skeleton-table', className)} aria-hidden="true">
      {Array.from({ length: Math.max(1, rows) }).map((_, rowIndex) => (
        <div className="ius-skeleton-table__row" key={rowIndex}>
          {Array.from({ length: Math.max(1, columns) }).map((__, columnIndex) => (
            <span className="ius-skeleton-line" key={columnIndex} />
          ))}
        </div>
      ))}
    </div>
  )
}
