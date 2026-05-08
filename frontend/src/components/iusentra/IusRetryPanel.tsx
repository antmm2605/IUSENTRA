import { RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function IusRetryPanel({
  title = 'Controllo da ripetere',
  message = 'L operazione non ha restituito un esito utilizzabile.',
  onRetry,
  retryLabel = 'Riprova',
  className,
}: {
  title?: string
  message?: string
  onRetry: () => void
  retryLabel?: string
  className?: string
}) {
  return (
    <section className={cn('ius-retry-panel', className)}>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      <Button type="button" onClick={onRetry}>
        <RotateCcw aria-hidden="true" />
        {retryLabel}
      </Button>
    </section>
  )
}
