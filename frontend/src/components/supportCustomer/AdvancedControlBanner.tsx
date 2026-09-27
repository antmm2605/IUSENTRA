import { ShieldAlert } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { SupportCustomerViewState } from './types'
import { advancedBannerVisible } from './uiState'

type AdvancedControlBannerProps = {
  state: SupportCustomerViewState
  onApprove: () => void
  onReject: () => void
}

/** Richiesta di controllo mouse/tastiera: consenso separato del cliente. */
export function AdvancedControlBanner({ state, onApprove, onReject }: AdvancedControlBannerProps) {
  if (!advancedBannerVisible(state)) return null
  return (
    <section className="iu-support-customer__panel iu-support-customer__advanced" id="advancedBanner" aria-labelledby="advancedBannerTitle" role="region">
      <h2 className="iu-support-customer__panel-title" id="advancedBannerTitle">
        <ShieldAlert size={17} aria-hidden="true" />
        <span>Richiesta controllo remoto del PC</span>
      </h2>
      <p className="iu-support-customer__text-muted">
        L&apos;operatore ha chiesto il controllo del mouse e della tastiera su questo PC. Approva solo se hai avviato Local Signer aggiornato o l&apos;agente IUSENTRA Assistenza e vuoi consentire il controllo diretto.
      </p>
      <p className="iu-support-customer__hint">
        Puoi revocare il controllo in qualsiasi momento con Termina sessione. La sola visualizzazione dello schermo funziona già dal browser, senza agente.
      </p>
      <div className="iu-support-customer__actions">
        <Button id="approveAdvancedBtn" type="button" tone="primary" disabled={state.advancedBusy} aria-busy={state.advancedBusy} onClick={onApprove}>
          Approva
        </Button>
        <Button id="rejectAdvancedBtn" type="button" tone="neutral" disabled={state.advancedBusy} onClick={onReject}>
          Rifiuta
        </Button>
      </div>
    </section>
  )
}
