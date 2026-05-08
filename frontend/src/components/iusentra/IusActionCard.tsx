import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusLegalIcon } from './IusLegalIcon'

export function IusActionCard({
  title,
  description,
  actionLabel,
  href,
  children,
  area,
  icon,
  tone = 'primary',
  className,
}: {
  title: string
  description?: string
  actionLabel?: string
  href?: string
  children?: ReactNode
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  className?: string
}) {
  return (
    <Card className={cn('ius-action-card', className)}>
      <CardContent className="ius-action-card__content">
        <IusLegalIcon area={area} icon={icon} tone={tone} />
        <div className="ius-action-card__body">
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
          {children}
        </div>
        {href && actionLabel ? (
          <Button asChild variant="outline" size="sm" className="ius-action-card__button">
            <a href={href}>{actionLabel}<ArrowRight data-icon="inline-end" /></a>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}
