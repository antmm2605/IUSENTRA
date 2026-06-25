import type { ReactNode } from 'react'
import { PageHeader } from './PageHeader'
import './ui.css'

export function Page({
  title,
  subtitle,
  actions,
  children,
  className,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <main className={`iu-content iu-page ius-page-shell iusentra-route-sequence${className ? ` ${className}` : ''}`}>
      <PageHeader title={title} subtitle={subtitle} actions={actions} />
      {children}
    </main>
  )
}
