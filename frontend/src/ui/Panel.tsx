import type { ReactNode } from 'react'
import './ui.css'

export function Panel({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="iu-panel">
      <header className="iu-panel__header">
        <div className="iu-panel__title">
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {actions ? <div className="iu-action-bar">{actions}</div> : null}
      </header>
      <div className="iu-panel__body">{children}</div>
    </section>
  )
}
