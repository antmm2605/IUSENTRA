import { useEffect, useState } from 'react'
import { FileSignature } from 'lucide-react'
import { IusWizardStepper, type IusWizardStep } from '../iusentra/IusWizardStepper'
import {
  emptySigningOverview,
  loadSigningOverview,
  type SigningOverview,
  type SigningStep,
} from '../../clientPortalSigning'
import { ConferimentoSignStep } from './ConferimentoSignStep'
import { IdentityCaptureStep } from './IdentityCaptureStep'
import { PreventivoStep } from './PreventivoStep'
import { ReceiptStep } from './ReceiptStep'

type SigningWorkflowPanelProps = {
  onNotice: (tone: 'success' | 'warning', text: string) => void
}

function stepperState(step: SigningStep, currentKey: string): IusWizardStep['state'] {
  if (step.status === 'completato') return 'done'
  if (step.status === 'rifiutato' || step.status === 'in_revisione') return 'warning'
  if (step.key === currentKey) return 'current'
  return 'pending'
}

function currentStepKey(overview: SigningOverview): string {
  const order = ['dati', 'identita', 'preventivo', 'conferimento', 'firma', 'riepilogo']
  for (const key of order) {
    const step = overview.steps.find((item) => item.key === key)
    if (step && step.status !== 'completato') return key
  }
  return 'riepilogo'
}

/**
 * Percorso guidato «Incarico e firma»: preventivo → documento d'identità →
 * conferimento → firma → ricevuta. Visibile solo con il feature flag
 * routes.appV2.clientPortal.signingWorkflow attivo.
 */
export function SigningWorkflowPanel({ onNotice }: SigningWorkflowPanelProps) {
  const [overview, setOverview] = useState<SigningOverview>(emptySigningOverview)
  const [loading, setLoading] = useState(true)

  const reload = async () => {
    setLoading(true)
    setOverview(await loadSigningOverview())
    setLoading(false)
  }

  useEffect(() => {
    void reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onResult = (ok: boolean, message: string, nextOverview?: unknown) => {
    onNotice(ok ? 'success' : 'warning', message)
    if (nextOverview && typeof nextOverview === 'object' && (nextOverview as SigningOverview).steps) {
      setOverview(nextOverview as SigningOverview)
    } else if (ok) {
      void reload()
    }
  }

  if (loading) {
    return (
      <section className="iu-client-portal-panel" id="panel-incarico">
        <div className="iu-client-portal-panel__head"><h2>Incarico e firma</h2><FileSignature size={18} aria-hidden="true" /></div>
        <p className="iu-client-portal-muted">Caricamento del percorso in corso…</p>
      </section>
    )
  }

  if (!overview.ok) {
    if (overview.code === 'feature_disabled') return null
    return (
      <section className="iu-client-portal-panel" id="panel-incarico">
        <div className="iu-client-portal-panel__head"><h2>Incarico e firma</h2><FileSignature size={18} aria-hidden="true" /></div>
        <p className="iu-client-portal-muted">{overview.message || 'Percorso non disponibile al momento.'}</p>
      </section>
    )
  }

  const current = currentStepKey(overview)
  const stepperSteps: IusWizardStep[] = overview.steps.map((step) => ({
    id: step.key,
    label: step.title,
    state: stepperState(step, current),
  }))
  const signedOrReview = overview.signature.firmaEseguita

  return (
    <section className="iu-client-portal-panel iu-signing-panel" id="panel-incarico">
      <div className="iu-client-portal-panel__head">
        <h2>Incarico e firma</h2>
        <FileSignature size={18} aria-hidden="true" />
      </div>
      <IusWizardStepper steps={stepperSteps} className="iu-signing-stepper" />

      <details className="iu-signing-section" open={!signedOrReview && current === 'preventivo'}>
        <summary><h3>1. Preventivo</h3></summary>
        <PreventivoStep preventivi={overview.preventivi} consents={overview.consents} onResult={onResult} />
      </details>

      <details className="iu-signing-section" open={current === 'identita'}>
        <summary><h3>2. Documento d’identità</h3></summary>
        <IdentityCaptureStep
          identity={overview.identity}
          consents={overview.consents}
          onResult={onResult}
          onReload={() => void reload()}
        />
      </details>

      <details className="iu-signing-section" open={!signedOrReview && (current === 'conferimento' || current === 'firma')}>
        <summary><h3>3. Conferimento incarico e firma</h3></summary>
        <ConferimentoSignStep
          conferimento={overview.conferimento}
          signature={overview.signature}
          consents={overview.consents}
          otpStepUp={overview.otpStepUp}
          onResult={onResult}
        />
      </details>

      {signedOrReview ? (
        <details className="iu-signing-section" open>
          <summary><h3>4. Riepilogo e ricevuta</h3></summary>
          <ReceiptStep />
        </details>
      ) : null}

      <p className="iu-signing-disclaimer">{overview.qualifiedSignature.note}</p>
    </section>
  )
}
