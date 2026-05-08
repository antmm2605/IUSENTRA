import type { ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export function IusLoadingState({
  title = 'Caricamento in corso',
  message = 'Recupero dei dati reali dello studio.',
  children,
  className,
}: {
  title?: string
  message?: string
  children?: ReactNode
  className?: string
}) {
  return (
    <section className={cn('ius-feedback-state ius-loading-state', className)} aria-live="polite" aria-busy="true">
      <LoaderCircle aria-hidden="true" className="ius-spin" />
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {children}
    </section>
  )
}
