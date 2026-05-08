import type { ReactNode } from 'react'
import { ArrowRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { IusLegalIcon } from './IusLegalIcon'
import { IusStatusBadge } from './IusStatusBadge'

export function IusChannelCard({
  title,
  description,
  status,
  statusTone = 'neutral',
  icon,
  officialChannel,
  actionLabel,
  actionHref,
  children,
  className,
}: {
  title: string
  description?: string
  status?: string
  statusTone?: 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'gold'
  icon?: LucideIcon
  officialChannel?: string
  actionLabel?: string
  actionHref?: string
  children?: ReactNode
  className?: string
}) {
  return (
    <article className={cn('ius-channel-card', className)}>
      <header>
        <IusLegalIcon area="telematico" icon={icon} tone="primary" />
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {status ? <IusStatusBadge tone={statusTone}>{status}</IusStatusBadge> : null}
      </header>
      {officialChannel ? <p className="ius-channel-card__official">Canale ufficiale: {officialChannel}</p> : null}
      {children ? <div className="ius-channel-card__body">{children}</div> : null}
      {actionHref && actionLabel ? (
        <Button asChild variant="outline">
          <a href={actionHref}>
            {actionLabel}
            <ArrowRight aria-hidden="true" />
          </a>
        </Button>
      ) : null}
    </article>
  )
}
