import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { FolderOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusLegalIcon } from './IusLegalIcon'

export function IusEmptyState({
  title,
  message,
  action,
  actionHref,
  actionLabel,
  area,
  icon = FolderOpen,
  tone = 'neutral',
  className,
}: {
  title: string
  message?: string
  action?: ReactNode
  actionHref?: string
  actionLabel?: string
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  className?: string
}) {
  return (
    <section className={cn('ius-empty-state', className)} aria-live="polite">
      <IusLegalIcon area={area} icon={icon} tone={tone} />
      <div>
        <h2>{title}</h2>
        {message ? <p>{message}</p> : null}
      </div>
      {action}
      {actionHref && actionLabel ? (
        <Button asChild variant="outline">
          <a href={actionHref}>{actionLabel}</a>
        </Button>
      ) : null}
    </section>
  )
}
