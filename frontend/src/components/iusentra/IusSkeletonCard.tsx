import { cn } from '@/lib/utils'

export function IusSkeletonCard({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <section className={cn('ius-skeleton-card', className)} aria-hidden="true">
      <span className="ius-skeleton-card__icon" />
      <div>
        {Array.from({ length: Math.max(1, lines) }).map((_, index) => (
          <span className="ius-skeleton-line" key={index} />
        ))}
      </div>
    </section>
  )
}
