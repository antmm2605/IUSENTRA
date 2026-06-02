import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusLegalIcon } from './IusLegalIcon'

export function IusSectionHeader({
  title,
  description,
  actions,
  area,
  icon,
  tone = 'primary',
  level = 2,
  sequence = true,
  className,
}: {
  title: string
  description?: string
  actions?: ReactNode
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  level?: 1 | 2 | 3
  sequence?: boolean
  className?: string
}) {
  const HeadingTag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3'
  const headerSequenceProps = sequence ? { 'data-iusentra-sequence-slot': 'page-header' } : {}
  const headingSequenceProps = sequence ? { 'data-iusentra-sequence-part': 'page-header' } : {}
  const descriptionSequenceProps = sequence
    ? {
        'data-iusentra-sequence-slot': 'operational-subtitle',
        'data-iusentra-sequence-part': 'operational-subtitle',
      }
    : {}
  const actionsSequenceProps = sequence
    ? {
        'data-iusentra-sequence-slot': 'primary-actions',
        'data-iusentra-sequence-part': 'primary-actions',
      }
    : {}
  return (
    <header className={cn('ius-section-header', className)} {...headerSequenceProps}>
      <div className="ius-section-header__main">
        {area || icon ? <IusLegalIcon area={area} icon={icon} tone={tone} /> : null}
        <div>
          <HeadingTag {...headingSequenceProps}>{title}</HeadingTag>
          {description ? (
            <p {...descriptionSequenceProps}>
              {description}
            </p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="ius-section-header__actions" {...actionsSequenceProps}>{actions}</div> : null}
    </header>
  )
}
