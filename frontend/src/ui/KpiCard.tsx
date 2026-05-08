import type { ReactNode } from 'react'
import { IusMetricCard } from '@/components/iusentra'
import './ui.css'

export function KpiCard({
  label,
  value,
  note,
  badge,
}: {
  label: string
  value: ReactNode
  note?: string
  badge?: ReactNode
}) {
  return (
    <IusMetricCard label={label} value={value} note={note} badge={badge} className="iu-kpi-card" />
  )
}
