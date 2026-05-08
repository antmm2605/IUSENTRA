import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusSectionHeader } from './IusSectionHeader'

export function IusPageShell({
  title,
  description,
  actions,
  children,
  area,
  icon,
  tone = 'primary',
  className,
}: {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  className?: string
}) {
  return (
    <main className={cn('iu-content iu-page ius-page-shell', className)}>
      <IusSectionHeader
        title={title}
        description={description}
        actions={actions}
        area={area}
        icon={icon}
        tone={tone}
        level={1}
        className="ius-page-shell__header"
      />
      <div className="ius-page-shell__body">{children}</div>
    </main>
  )
}
