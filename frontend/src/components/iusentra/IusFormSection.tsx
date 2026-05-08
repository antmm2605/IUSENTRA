import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusSectionHeader } from './IusSectionHeader'

export function IusFormSection({
  title,
  description,
  children,
  actions,
  area,
  icon,
  tone = 'primary',
  className,
}: {
  title: string
  description?: string
  children: ReactNode
  actions?: ReactNode
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  className?: string
}) {
  return (
    <Card className={cn('ius-form-section', className)}>
      <CardContent className="ius-form-section__content">
        <IusSectionHeader
          title={title}
          description={description}
          actions={actions}
          area={area}
          icon={icon}
          tone={tone}
          level={3}
        />
        <div className="ius-form-section__fields">{children}</div>
      </CardContent>
    </Card>
  )
}
