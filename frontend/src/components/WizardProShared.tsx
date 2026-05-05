import { CheckCircle2 } from 'lucide-react'
import { Badge } from './dashboard'
import type { WizardProMatter, WizardProStepStatus } from '../wizardProData'

export function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

export function WizardStepper({ steps }: { steps: WizardProStepStatus[] }) {
  if (!steps.length) return null
  return (
    <nav className="iu-wiz-stepper" aria-label="Step preparazione udienza">
      {steps.map((step) => (
        <a
          key={step.n}
          href={step.href}
          aria-current={step.active ? 'step' : undefined}
          className={`${step.active ? 'is-active' : ''} ${step.confirmed ? 'is-done' : ''} ${step.available ? '' : 'is-locked'}`}
        >
          <span>{step.confirmed ? <CheckCircle2 size={15}/> : step.n}</span>
          <b>{step.label}</b>
        </a>
      ))}
    </nav>
  )
}

export function MatterSummary({ matter }: { matter: WizardProMatter | null }) {
  if (!matter) {
    return (
      <section className="iu-wiz-panel">
        <h2>Fascicolo non disponibile</h2>
        <p>La sessione non espone un fascicolo collegato nel repository corrente.</p>
      </section>
    )
  }
  return (
    <section className="iu-wiz-panel iu-wiz-matter">
      <div className="iu-wiz-panel__head">
        <div>
          <span className="iu-wiz-kicker">Fascicolo</span>
          <h2>{matter.title}</h2>
        </div>
        {matter.statusLabel ? <Badge tone="primary">{matter.statusLabel}</Badge> : null}
      </div>
      <div className="iu-wiz-facts">
        <span><b>Cliente</b>{matter.client}</span>
        <span><b>Controparte</b>{matter.opponent}</span>
        <span><b>Ufficio</b>{matter.court}</span>
        <span><b>RG</b>{matter.rg || matter.number}</span>
        <span><b>Giudice</b>{matter.judge}</span>
        <span><b>Sezione</b>{matter.section}</span>
        <span><b>Udienza</b>{matter.nextHearingLabel}</span>
        <span><b>Documenti</b>{matter.documentsCount}</span>
      </div>
      <div className="iu-wiz-actions">
        <a href={matter.href}>Apri fascicolo</a>
        <a href={matter.deadlineHref}>Scadenziario</a>
        <a href={matter.timesheetHref}>Timesheet</a>
      </div>
    </section>
  )
}
