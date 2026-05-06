import type { ReactNode } from 'react'
import './ui.css'

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <header className="iu-page-heading">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div className="iu-page-actions">{actions}</div> : null}
    </header>
  )
}
