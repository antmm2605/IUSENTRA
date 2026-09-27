import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { MessagesSquare, Send } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { SupportCustomerViewState } from './types'

type CustomerChatPanelProps = {
  state: SupportCustomerViewState
  onSend: (text: string) => boolean
}

export function CustomerChatPanel({ state, onSend }: CustomerChatPanelProps) {
  const [draft, setDraft] = useState('')
  const logRef = useRef<HTMLDivElement | null>(null)
  const lastMessageId = state.chat.length ? state.chat[state.chat.length - 1].id : 0

  useEffect(() => {
    const log = logRef.current
    if (log) log.scrollTop = log.scrollHeight
  }, [lastMessageId])

  const closed = state.sessionClosed
  const compact = state.chatCompact
  const send = () => {
    if (onSend(draft)) setDraft('')
  }
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && !event.nativeEvent.isComposing) {
      event.preventDefault()
      send()
    }
  }

  return (
    <section
      className={`iu-support-customer__panel iu-support-customer__chat${compact ? ' iu-support-customer__chat--compact' : ''}`}
      id="customerChatPanel"
      aria-labelledby="customerChatPanelTitle"
    >
      <h2 className="iu-support-customer__panel-title" id="customerChatPanelTitle">
        <MessagesSquare size={17} aria-hidden="true" />
        <span>Chat tecnica</span>
      </h2>
      <div
        id="chatLog"
        ref={logRef}
        className="iu-support-customer__chat-log"
        role="log"
        aria-live="polite"
        aria-label="Messaggi della chat tecnica"
        tabIndex={0}
      >
        {state.chat.length === 0 ? (
          <p className="iu-support-customer__chat-empty">Nessun messaggio. Scrivi qui se vuoi spiegare il problema al tecnico.</p>
        ) : (
          state.chat.map((message) => (
            <div key={message.id} className={`support-chat-log__message support-chat-log__message--${message.who}`}>
              {message.text}
            </div>
          ))
        )}
      </div>
      <div className="iu-support-customer__composer">
        <label className="iu-support-customer__label" htmlFor="chatInput">Messaggio al tecnico</label>
        <div className="iu-support-customer__input-row">
          <input
            className="iu-support-customer__input"
            id="chatInput"
            type="text"
            autoComplete="off"
            maxLength={2000}
            placeholder="Scrivi qui se vuoi spiegare il problema"
            value={draft}
            disabled={closed}
            onChange={(event) => setDraft(event.currentTarget.value)}
            onKeyDown={onKeyDown}
          />
          <Button id="sendBtn" type="button" tone="neutral" disabled={closed} onClick={send}>
            <Send size={15} aria-hidden="true" />
            <span>Invia</span>
          </Button>
        </div>
      </div>
    </section>
  )
}
