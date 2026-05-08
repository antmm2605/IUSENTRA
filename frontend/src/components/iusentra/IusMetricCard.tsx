import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusLegalIcon } from './IusLegalIcon'
import { IusStatusBadge } from './IusStatusBadge'

export function IusMetricCard({
  label,
  value,
  note,
  badge,
  href,
  area,
  icon,
  tone = 'primary',
  actionLabel = 'Apri',
  className,
}: {
  label: string
  value: ReactNode
  note?: ReactNode
  badge?: ReactNode
  href?: string
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  actionLabel?: string
  className?: string
}) {
  const content = (
    <Card className={cn('ius-metric-card', className)}>
      <CardContent className="ius-metric-card__content">
        <IusLegalIcon area={area} icon={icon} tone={tone} className="ius-metric-card__icon" />
        <div className="ius-metric-card__main">
          <div className="ius-metric-card__top">
            <span>{label}</span>
            {badge ? <IusStatusBadge tone={tone}>{badge}</IusStatusBadge> : null}
          </div>
          <strong>{value}</strong>
          {note ? <small>{note}</small> : null}
          {href ? <em>{actionLabel} <ArrowRight /></em> : null}
        </div>
      </CardContent>
    </Card>
  )

  if (!href) return content
  return <a className="ius-card-link" href={href}>{content}</a>
}
