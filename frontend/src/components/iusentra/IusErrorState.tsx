import type { ReactNode } from 'react'
import { AlertTriangle, ChevronDown, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function IusErrorState({
  title = 'Dati non disponibili',
  message = 'Non e stato possibile caricare i dati. Verifica la connessione o riprova.',
  details,
  onRetry,
  retryLabel = 'Riprova',
  action,
  className,
}: {
  title?: string
  message?: string
  details?: string
  onRetry?: () => void
  retryLabel?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <section className={cn('ius-feedback-state ius-error-state', className)} role="alert">
      <AlertTriangle aria-hidden="true" />
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      <div className="ius-feedback-state__actions">
        {onRetry ? (
          <Button type="button" variant="outline" onClick={onRetry}>
            <RotateCcw aria-hidden="true" />
            {retryLabel}
          </Button>
        ) : null}
        {action}
      </div>
      {details ? (
        <details className="ius-error-state__details">
          <summary>
            <ChevronDown aria-hidden="true" />
            Dettagli tecnici
          </summary>
          <pre>{details}</pre>
        </details>
      ) : null}
    </section>
  )
}
