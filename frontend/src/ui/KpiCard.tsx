import type { ReactNode } from 'react'
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
    <article className="iu-kpi-card">
      <div className="iu-layout-split">
        <span className="iu-kpi-card__label">{label}</span>
        {badge}
      </div>
      <strong className="iu-kpi-card__value">{value}</strong>
      {note ? <span className="iu-kpi-card__note">{note}</span> : null}
    </article>
  )
}
