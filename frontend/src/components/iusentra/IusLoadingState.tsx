import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useInlineActivity } from '../../ui/useBusyActivity'
import '../../ui/activity.css'

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
  const target = useInlineActivity(title)
  return target ? createPortal(
    <section className={cn('ius-feedback-state ius-loading-state iu-inline-activity', className)} aria-live="polite" aria-busy="true">
      <LoaderCircle aria-hidden="true" className="ius-spin" />
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {children}
    </section>, target,
  ) : null
}
