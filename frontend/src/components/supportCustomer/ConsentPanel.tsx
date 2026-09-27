import { CircleCheck, CirclePlay, CircleStop, Hourglass, Lock, Mic, MicOff, Monitor, RefreshCw } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { SupportConsent, SupportCustomerViewState } from './types'
import { canToggleMicrophone, micButtonLabel, startButtonView, type StartButtonView } from './uiState'

type ConsentPanelProps = {
  state: SupportCustomerViewState
  remoteAudioRef: (element: HTMLAudioElement | null) => void
  onConsentChange: (key: keyof SupportConsent, value: boolean) => void
  onStart: () => void
  onStop: () => void
  onToggleMic: () => void
}

const CONSENT_ITEMS: Array<{ key: keyof SupportConsent; id: string; label: string }> = [
  { key: 'screen', id: 'consentScreen', label: 'Autorizzo la condivisione dello schermo' },
  { key: 'audio', id: 'consentAudio', label: 'Autorizzo il microfono' },
  { key: 'chat', id: 'consentChat', label: 'Autorizzo la chat tecnica' },
]

function StartIcon({ kind }: { kind: StartButtonView['kind'] }) {
  if (kind === 'active') return <CircleCheck size={16} aria-hidden="true" />
  if (kind === 'ready') return <CirclePlay size={16} aria-hidden="true" />
  if (kind === 'closed') return <Lock size={16} aria-hidden="true" />
  if (kind === 'starting') return <RefreshCw size={16} aria-hidden="true" className="iu-support-customer__spin" />
  return <Hourglass size={16} aria-hidden="true" />
}

export function ConsentPanel({ state, remoteAudioRef, onConsentChange, onStart, onStop, onToggleMic }: ConsentPanelProps) {
  const closed = state.sessionClosed
  const start = startButtonView(state)
  const startTone = start.kind === 'active' ? 'success' : start.kind === 'ready' ? 'primary' : 'neutral'
  const consentLocked = closed || state.starting || state.supportStarted
  return (
    <section className="iu-support-customer__panel" id="customerScreenPanel" aria-labelledby="customerScreenPanelTitle">
      <h2 className="iu-support-customer__panel-title" id="customerScreenPanelTitle">
        <Monitor size={17} aria-hidden="true" />
        <span>Autorizzazioni assistenza</span>
      </h2>
      <fieldset className="iu-support-customer__consents" disabled={consentLocked}>
        <legend className="iu-support-customer__sr-only">Consensi per l&apos;assistenza remota</legend>
        {CONSENT_ITEMS.map((item) => (
          <label className="iu-support-customer__consent" htmlFor={item.id} key={item.id}>
            <input
              type="checkbox"
              id={item.id}
              checked={state.consent[item.key]}
              onChange={(event) => onConsentChange(item.key, event.currentTarget.checked)}
            />
            <span>{item.label}</span>
          </label>
        ))}
      </fieldset>
      <p className="iu-support-customer__hint" id="consentHint">
        I consensi si registrano quando premi Avvia assistenza. La condivisione dello schermo è necessaria per procedere.
      </p>
      <div className="iu-support-customer__actions">
        <Button
          id="startBtn"
          type="button"
          tone={startTone}
          disabled={start.disabled}
          aria-disabled={start.disabled}
          aria-describedby="consentHint"
          title={start.title}
          onClick={onStart}
        >
          <StartIcon kind={start.kind} />
          <span>{start.label}</span>
        </Button>
        <Button
          id="customerMuteMicBtn"
          type="button"
          tone={state.micMuted ? 'primary' : 'neutral'}
          aria-pressed={state.micMuted}
          disabled={!canToggleMicrophone(state)}
          onClick={onToggleMic}
        >
          {state.micMuted ? <Mic size={16} aria-hidden="true" /> : <MicOff size={16} aria-hidden="true" />}
          <span>{micButtonLabel(state)}</span>
        </Button>
        <Button id="stopBtn" type="button" tone="danger" disabled={closed || !state.stopEnabled} onClick={onStop}>
          <CircleStop size={16} aria-hidden="true" />
          <span>Termina sessione</span>
        </Button>
      </div>
      <audio id="remoteAudio" className="iu-support-customer__audio" ref={remoteAudioRef} autoPlay />
    </section>
  )
}
