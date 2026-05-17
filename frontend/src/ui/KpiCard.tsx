import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { IusMetricCard } from '@/components/iusentra'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import './ui.css'

export function KpiCard({
  label,
  value,
  note,
  badge,
  href,
  area,
  icon,
  tone = 'primary',
  actionLabel,
}: {
  label: string
  value: ReactNode
  note?: string
  badge?: ReactNode
  href?: string
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  actionLabel?: string
}) {
  return (
    <IusMetricCard
      label={label}
      value={value}
      note={note}
      badge={badge}
      href={href}
      area={area}
      icon={icon}
      tone={tone}
      actionLabel={actionLabel}
      className="iu-kpi-card"
    />
  )
}
