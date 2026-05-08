import type { ReactNode } from 'react'
import { Breadcrumbs, type BreadcrumbItem } from './Breadcrumbs'
import './shell.css'

export function WorkspaceHeader({
  title,
  description,
  breadcrumbs = [],
  actions,
}: {
  title: string
  description?: string
  breadcrumbs?: BreadcrumbItem[]
  actions?: ReactNode
}) {
  return (
    <section className="iu-workspace-header">
      <div>
        <Breadcrumbs items={breadcrumbs} />
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="iu-quick-actions">{actions}</div> : null}
    </section>
  )
}
