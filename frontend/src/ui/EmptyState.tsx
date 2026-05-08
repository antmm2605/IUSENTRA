import type { ReactNode } from 'react'
import { IusEmptyState } from '@/components/iusentra'
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
    <IusEmptyState title={title} message={message} action={action} className="iu-empty-state" />
  )
}
