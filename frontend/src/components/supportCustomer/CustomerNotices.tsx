import { Headset, Lock, TriangleAlert } from 'lucide-react'
import type { SupportCustomerViewState } from './types'
import { takeChargeVisible } from './uiState'

/** Avvisi di stato: sessione conclusa / link non più valido, presa in carico del SUPERADMIN. */
export function CustomerNotices({ state }: { state: SupportCustomerViewState }) {
  if (state.sessionClosed && state.closedReason === 'unavailable') {
    return (
      <section className="iu-support-customer__notice iu-support-customer__notice--danger" id="sessionClosedNotice" role="alert">
        <p className="iu-support-customer__notice-title">
          <TriangleAlert size={16} aria-hidden="true" />
          <span>Sessione non disponibile</span>
        </p>
        <p>{state.unavailableMessage}</p>
      </section>
    )
  }
  if (state.sessionClosed) {
    return (
      <section className="iu-support-customer__notice iu-support-customer__notice--warning" id="sessionClosedNotice" role="alert">
        <p className="iu-support-customer__notice-title">
          <Lock size={16} aria-hidden="true" />
          <span>Sessione conclusa</span>
        </p>
        <p>
          Questo link appartiene a una sessione già chiusa. Chiedi all&apos;operatore un nuovo link di assistenza per riprendere la connessione.
        </p>
      </section>
    )
  }
  if (!takeChargeVisible(state)) return null
  return (
    <section className="iu-support-customer__notice iu-support-customer__notice--info" id="takeChargeNotice" role="status">
      <p className="iu-support-customer__notice-title">
        <Headset size={16} aria-hidden="true" />
        <span>Richiesta visualizzata dal SUPERADMIN</span>
      </p>
      <p>
        La richiesta è stata presa in carico. Puoi premere <strong>Avvia assistenza</strong> per autorizzare schermo, chat e procedere con l&apos;assistenza remota.
      </p>
    </section>
  )
}
