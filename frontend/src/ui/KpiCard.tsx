import { isValidElement, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { IusMetricCard } from '@/components/iusentra'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import './ui.css'

const TONE_ONLY_BADGES = new Set(['primary', 'success', 'warning', 'danger', 'neutral', 'info'])

function displayBadge(badge?: ReactNode) {
  if (!isValidElement(badge)) return badge
  const props = badge.props as { children?: ReactNode }
  const child = props.children
  if (typeof child === 'string' && TONE_ONLY_BADGES.has(child.trim().toLowerCase())) {
    return undefined
  }
  return badge
}

export function KpiCard({
  label,
  value,
  note,
  badge,
  href,
  onClick,
  active,
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
  onClick?: () => void
  active?: boolean
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  actionLabel?: string
}) {
  const meaningfulBadge = displayBadge(badge)

  return (
    <IusMetricCard
      label={label}
      value={value}
      note={note}
      badge={meaningfulBadge}
      href={href}
      onClick={onClick}
      active={active}
      area={area}
      icon={icon}
      tone={tone}
      actionLabel={actionLabel}
      className="iu-kpi-card"
    />
  )
}
