import { CheckCircle2, Circle, CircleDot } from 'lucide-react'
import { cn } from '@/lib/utils'

export type IusWizardStep = {
  id: string
  label: string
  description?: string
  state?: 'done' | 'current' | 'pending' | 'warning'
}

export function IusWizardStepper({
  steps,
  className,
}: {
  steps: IusWizardStep[]
  className?: string
}) {
  return (
    <ol className={cn('ius-wizard-stepper', className)} aria-label="Avanzamento procedura">
      {steps.map((step, index) => {
        const state = step.state || 'pending'
        const Icon = state === 'done' ? CheckCircle2 : state === 'current' ? CircleDot : Circle
        return (
          <li className={`ius-wizard-stepper__item is-${state}`} key={step.id} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="ius-wizard-stepper__marker">
              <Icon aria-hidden="true" />
            </span>
            <span>
              <strong>{index + 1}. {step.label}</strong>
              {step.description ? <small>{step.description}</small> : null}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
