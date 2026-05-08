import { AlertTriangle, CheckCircle2, Info, ShieldCheck, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IusStatusBadge } from './IusStatusBadge'

export type IusComplianceItem = {
  id: string
  label: string
  state: 'verified' | 'not_verified' | 'compliant' | 'not_compliant' | 'review' | 'gap'
  detail?: string
}

const stateLabels: Record<IusComplianceItem['state'], string> = {
  verified: 'Verificato',
  not_verified: 'Non verificato',
  compliant: 'Conforme',
  not_compliant: 'Non conforme',
  review: 'Revisione manuale richiesta',
  gap: 'Coverage gap',
}

const stateTone: Record<IusComplianceItem['state'], 'success' | 'warning' | 'danger' | 'info' | 'neutral'> = {
  verified: 'success',
  not_verified: 'warning',
  compliant: 'success',
  not_compliant: 'danger',
  review: 'warning',
  gap: 'info',
}

const stateIcons = {
  verified: CheckCircle2,
  not_verified: Info,
  compliant: ShieldCheck,
  not_compliant: XCircle,
  review: AlertTriangle,
  gap: Info,
}

export function IusCompliancePanel({
  title = 'Conformita e controlli',
  items,
  className,
}: {
  title?: string
  items: IusComplianceItem[]
  className?: string
}) {
  return (
    <section className={cn('ius-compliance-panel', className)} aria-label={title}>
      <header>
        <ShieldCheck aria-hidden="true" />
        <h2>{title}</h2>
      </header>
      <div className="ius-compliance-panel__list">
        {items.map((item) => {
          const Icon = stateIcons[item.state]
          return (
            <article className="ius-compliance-panel__item" key={item.id}>
              <Icon aria-hidden="true" />
              <div>
                <strong>{item.label}</strong>
                {item.detail ? <p>{item.detail}</p> : null}
              </div>
              <IusStatusBadge tone={stateTone[item.state]}>{stateLabels[item.state]}</IusStatusBadge>
            </article>
          )
        })}
      </div>
    </section>
  )
}
