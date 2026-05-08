import type { ReactNode } from 'react'
import { IusSectionHeader } from '@/components/iusentra'
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
    <IusSectionHeader title={title} description={subtitle} actions={actions} level={1} className="iu-page-heading" />
  )
}
