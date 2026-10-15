import './ui.css'
import './activity.css'
import { createPortal } from 'react-dom'
import { useInlineActivity } from './useBusyActivity'

export function LoadingState({
  title = 'Caricamento in corso',
  message = 'Stiamo recuperando i dati reali dello studio.',
}: {
  title?: string
  message?: string
}) {
  const target = useInlineActivity(title)
  return target ? createPortal(
    <section className="iu-loading-state iu-inline-activity" aria-live="polite" aria-busy="true">
      <div className="iu-loading-state__body">
        <span className="iu-loading-state__spinner" aria-hidden="true" />
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
    </section>, target,
  ) : null
}
