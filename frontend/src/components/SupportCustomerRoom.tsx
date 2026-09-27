import { TriangleAlert } from 'lucide-react'
import { AdvancedControlBanner } from './supportCustomer/AdvancedControlBanner'
import { isCustomerBootstrapUsable, readCustomerBootstrap, readCustomerSession } from './supportCustomer/bootstrap'
import { ConsentPanel } from './supportCustomer/ConsentPanel'
import { CustomerChatPanel } from './supportCustomer/CustomerChatPanel'
import { CustomerHero } from './supportCustomer/CustomerHero'
import { CustomerNotices } from './supportCustomer/CustomerNotices'
import type { SupportCustomerBootstrap, SupportCustomerSession } from './supportCustomer/types'
import { useSupportCustomerRoom } from './supportCustomer/useSupportCustomerRoom'
import './SupportCustomerRoom.css'

/**
 * Stanza cliente dell'assistenza remota (`/support/join/<token>`), montata da
 * main.tsx su `#support-customer-react-root`. Sostituisce
 * web/templates/support/customer_room.html + web/static/js/support_customer_room.js
 * (ancora raggiungibili con `?_legacy=1`).
 */

type SupportCustomerRoomProps = {
  bootstrap?: SupportCustomerBootstrap
  sessione?: SupportCustomerSession
}

function SupportCustomerRoomUnavailable() {
  return (
    <main className="iu-support-customer" id="supportCustomerShell" data-support-customer-react="true">
      <section className="iu-support-customer__notice iu-support-customer__notice--danger" role="alert">
        <p className="iu-support-customer__notice-title">
          <TriangleAlert size={16} aria-hidden="true" />
          <span>Stanza di assistenza non disponibile</span>
        </p>
        <p>I dati della sessione non sono arrivati alla pagina. Ricarica il link ricevuto dallo studio; se il problema resta, chiedi all&apos;operatore un nuovo link.</p>
      </section>
    </main>
  )
}

function SupportCustomerRoomView({ bootstrap, sessione }: { bootstrap: SupportCustomerBootstrap; sessione: SupportCustomerSession }) {
  const { state, controller, shellRef, remoteAudioRef, toggleFullscreen } = useSupportCustomerRoom(bootstrap, sessione)
  const shellClasses = ['iu-support-customer', state.fullscreen ? 'iu-support-customer--fullscreen' : '', state.sessionClosed ? 'iu-support-customer--closed' : '']
    .filter(Boolean)
    .join(' ')

  return (
    <main className={shellClasses} id="supportCustomerShell" ref={shellRef} data-support-customer-react="true">
      <CustomerHero state={state} onToggleFullscreen={toggleFullscreen} onToggleCompactChat={() => controller.toggleCompactChat()} />
      <CustomerNotices state={state} />
      <div className="iu-support-customer__grid">
        <ConsentPanel
          state={state}
          remoteAudioRef={remoteAudioRef}
          onConsentChange={(key, value) => controller.setConsent(key, value)}
          onStart={() => {
            void controller.startSession()
          }}
          onStop={() => {
            void controller.stopSession()
          }}
          onToggleMic={() => controller.toggleMicrophone()}
        />
        <CustomerChatPanel state={state} onSend={(text) => controller.sendChat(text)} />
      </div>
      <AdvancedControlBanner
        state={state}
        onApprove={() => {
          void controller.approveAdvanced()
        }}
        onReject={() => {
          void controller.rejectAdvanced()
        }}
      />
    </main>
  )
}

export default function SupportCustomerRoom({
  bootstrap = readCustomerBootstrap(),
  sessione = readCustomerSession(),
}: SupportCustomerRoomProps) {
  if (!isCustomerBootstrapUsable(bootstrap)) return <SupportCustomerRoomUnavailable />
  return <SupportCustomerRoomView bootstrap={bootstrap} sessione={sessione} />
}
