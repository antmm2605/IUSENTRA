import type { ReactNode } from 'react'
import './ui.css'

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string
  message?: string
  action?: ReactNode
}) {
  return (
    <section className="iu-empty-state" aria-live="polite">
      <div className="iu-empty-state__body">
        <h2>{title}</h2>
        {message ? <p>{message}</p> : null}
        {action}
      </div>
    </section>
  )
}
