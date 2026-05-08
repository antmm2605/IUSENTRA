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
  className,
}: {
  title: string
  description?: string
  actions?: ReactNode
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  level?: 1 | 2 | 3
  className?: string
}) {
  const HeadingTag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3'
  return (
    <header className={cn('ius-section-header', className)}>
      <div className="ius-section-header__main">
        {area || icon ? <IusLegalIcon area={area} icon={icon} tone={tone} /> : null}
        <div>
          <HeadingTag>{title}</HeadingTag>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="ius-section-header__actions">{actions}</div> : null}
    </header>
  )
}
