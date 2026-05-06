import type { ReactNode } from 'react'
import { PageHeader } from './PageHeader'
import './ui.css'

export function Page({
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
    <main className="iu-content iu-page">
      <PageHeader title={title} subtitle={subtitle} actions={actions} />
      {children}
    </main>
  )
}
