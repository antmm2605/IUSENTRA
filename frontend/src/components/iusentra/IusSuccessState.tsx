import type { ReactNode } from 'react'
import { CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export function IusSuccessState({
  title = 'Operazione completata',
  message,
  action,
  className,
}: {
  title?: string
  message?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <section className={cn('ius-feedback-state ius-success-state', className)} role="status" aria-live="polite">
      <CheckCircle2 aria-hidden="true" />
      <div>
        <h2>{title}</h2>
        {message ? <p>{message}</p> : null}
      </div>
      {action}
    </section>
  )
}
