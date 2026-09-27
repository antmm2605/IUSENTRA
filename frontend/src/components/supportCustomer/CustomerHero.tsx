import { MessageSquare, MessageSquareText, Maximize2, Minimize2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { SupportCustomerViewState } from './types'
import { compactChatButtonLabel, fullscreenButtonLabel } from './uiState'

type CustomerHeroProps = {
  state: SupportCustomerViewState
  onToggleFullscreen: () => void
  onToggleCompactChat: () => void
}

export function CustomerHero({ state, onToggleFullscreen, onToggleCompactChat }: CustomerHeroProps) {
  const closed = state.sessionClosed
  return (
    <header className="iu-support-customer__hero">
      <div className="iu-support-customer__brand">
        <span className="iu-support-customer__mark" aria-hidden="true">I</span>
        <div>
          <p className="iu-support-customer__wordmark">IUSENTRA</p>
          <p className="iu-support-customer__subtitle">Assistenza remota protetta</p>
        </div>
      </div>
      <h1 className="iu-support-customer__title">Assistenza remota con consenso esplicito</h1>
      <p className="iu-support-customer__text">
        Il SUPERADMIN dello studio può vedere solo lo schermo e l&apos;audio che autorizzi qui. La sessione resta cifrata, tracciata e chiudibile in qualsiasi momento.
      </p>
      <div className="iu-support-customer__badges">
        <span className="iu-badge iu-badge--neutral" id="statusBadge" role="status" aria-live="polite">
          {state.statusText}
        </span>
        <span className={`iu-badge ${state.operatorConnected ? 'iu-badge--success' : 'iu-badge--neutral'}`} id="peerBadge">
          {state.operatorConnected ? 'Operatore collegato' : 'Operatore non collegato'}
        </span>
      </div>
      <div className="iu-support-customer__hero-actions">
        <Button
          id="customerFullscreenBtn"
          type="button"
          tone={state.fullscreen ? 'primary' : 'neutral'}
          aria-pressed={state.fullscreen}
          disabled={closed}
          onClick={onToggleFullscreen}
        >
          {state.fullscreen ? <Minimize2 size={16} aria-hidden="true" /> : <Maximize2 size={16} aria-hidden="true" />}
          <span>{fullscreenButtonLabel(state)}</span>
        </Button>
        <Button
          id="compactChatBtn"
          type="button"
          tone={state.chatCompact ? 'primary' : 'neutral'}
          aria-pressed={state.chatCompact}
          aria-controls="customerChatPanel"
          disabled={closed}
          onClick={onToggleCompactChat}
        >
          {state.chatCompact ? <MessageSquareText size={16} aria-hidden="true" /> : <MessageSquare size={16} aria-hidden="true" />}
          <span>{compactChatButtonLabel(state)}</span>
        </Button>
      </div>
    </header>
  )
}
