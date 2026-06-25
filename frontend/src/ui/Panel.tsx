import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { IusSectionHeader } from '@/components/iusentra'
import './ui.css'

export function Panel({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <Card className="iu-panel ius-panel-card">
      <CardContent className="ius-panel-card__content">
        <IusSectionHeader title={title} description={subtitle} actions={actions} level={2} className="iu-panel__header" sequence={false} />
        <div className="iu-panel__body ius-panel-card__body">{children}</div>
      </CardContent>
    </Card>
  )
}
