import { useEffect, type ReactNode } from 'react'
import {
  ArrowLeft,
  Copy,
  Keyboard,
  Link,
  Maximize2,
  MessageCircle,
  Mic,
  MicOff,
  Monitor,
  MousePointer2,
  RadioTower,
  ShieldCheck,
  XCircle,
} from 'lucide-react'

type SupportPresence = {
  client?: boolean
  operator?: boolean
}

type SupportSession = {
  public_id?: string
  customer_name?: string
  practice_label?: string
  status_label?: string
  presence?: SupportPresence
  advanced_control_requested?: boolean
  advanced_control_approved?: boolean
}

type SupportBootstrap = {
  customerJoinUrl?: string
  customerName?: string
  status?: string
  closed?: boolean
}

declare global {
  interface Window {
    SUPPORT_BOOTSTRAP?: SupportBootstrap
    SUPPORT_SESSION?: SupportSession
    SUPPORT_ASSET_VERSION?: string
    __IUSENTRA_SUPPORT_OPERATOR_SCRIPT_LOADED__?: boolean
  }
}

function iconNode(icon: ReactNode) {
  return <span className="iu-support-icon" aria-hidden="true">{icon}</span>
}

function operatorScriptUrl(): string {
  const version = window.SUPPORT_ASSET_VERSION || String(Date.now())
  return `/static/js/support_operator_room.js?v=${encodeURIComponent(version)}`
}

function readJsonScript<T>(id: string): T | null {
  const element = document.getElementById(id)
  if (!element?.textContent) return null
  try {
    return JSON.parse(element.textContent) as T
  } catch {
    return null
  }
}

export default function SupportOperatorRoom({
  bootstrap = window.SUPPORT_BOOTSTRAP || readJsonScript<SupportBootstrap>('support-operator-bootstrap') || {},
  sessione = window.SUPPORT_SESSION || readJsonScript<SupportSession>('support-operator-session') || {},
}: {
  bootstrap?: SupportBootstrap
  sessione?: SupportSession
}) {
  const closed = Boolean(bootstrap.closed || bootstrap.status === 'closed')
  const customerName = sessione.customer_name || bootstrap.customerName || 'cliente non indicato'
  const practiceLabel = sessione.practice_label || ''
  const statusLabel = sessione.status_label || 'Sessione aggiornata'
  const clientConnected = Boolean(sessione.presence?.client)

  useEffect(() => {
    if (window.__IUSENTRA_SUPPORT_OPERATOR_SCRIPT_LOADED__) return
    window.__IUSENTRA_SUPPORT_OPERATOR_SCRIPT_LOADED__ = true
    const script = document.createElement('script')
    script.src = operatorScriptUrl()
    script.defer = true
    script.dataset.supportOperatorRuntime = '1'
    document.body.appendChild(script)
  }, [])

  return (
    <main className="iu-support-operator" id="supportOperatorShell" data-support-operator-react="true">
      <header className="iu-support-operator__topbar">
        <div className="iu-support-operator__brand">
          <span className="iu-support-operator__mark">I</span>
          <div>
            <p>IUSENTRA</p>
            <h1>Stanza operatore</h1>
            <span>{customerName}{practiceLabel ? ` - ${practiceLabel}` : ''}</span>
          </div>
        </div>
        <div className="iu-support-operator__badges">
          <span className="badge bg-light text-dark border" id="statusBadge">{statusLabel}</span>
          <span className={`badge ${clientConnected ? 'bg-success' : 'bg-secondary'}`} id="peerBadge">
            {clientConnected ? 'Cliente collegato' : 'Cliente non collegato'}
          </span>
          <span className="badge bg-secondary" id="remoteControlBadge">Controllo PC non attivo</span>
        </div>
        <div className="iu-support-operator__actions">
          <button className="iu-support-button iu-support-button--primary" id="joinBtn" type="button" disabled={closed}>
            {iconNode(<RadioTower size={16} />)}<span>Entra</span>
          </button>
          <button className="iu-support-button" id="requestAdvancedBtn" type="button" disabled={closed}>
            {iconNode(<ShieldCheck size={16} />)}<span>Richiedi controllo PC</span>
          </button>
          <button className="iu-support-button" id="fullscreenBtn" type="button">
            {iconNode(<Maximize2 size={16} />)}<span>Schermo intero</span>
          </button>
          <button className="iu-support-button iu-support-button--danger" id="closeBtn" type="button" disabled={closed}>
            {iconNode(<XCircle size={16} />)}<span>Chiudi</span>
          </button>
          <a className="iu-support-button" href="/admin/supporto-remoto">
            {iconNode(<ArrowLeft size={16} />)}<span>Console</span>
          </a>
          <label className="iu-support-switch" htmlFor="operatorMic">
            <input type="checkbox" id="operatorMic" disabled={closed} />
            {iconNode(<Mic size={15} />)}
            <span>Microfono</span>
          </label>
          <button className="iu-support-button" id="operatorMuteMicBtn" type="button" aria-pressed="false" disabled>
            {iconNode(<MicOff size={15} />)}<span>Muta microfono</span>
          </button>
        </div>
      </header>

      <section className="iu-support-operator__stage" aria-label="Schermo cliente">
        <div className="support-room__screen support-room__screen--operator" id="remoteScreen">
          <video id="remoteVideo" autoPlay playsInline />
          <audio id="remoteAudio" autoPlay />
          <img id="remoteAgentFrame" className="support-room__agent-frame d-none" alt="Schermo cliente condiviso tramite agente locale" />
          <div className="support-room__screen-empty" id="remoteVideoFallback">
            <Monitor size={34} />
            <span>Il video del cliente comparirà qui appena la condivisione schermo è attiva.</span>
          </div>
        </div>
      </section>

      <section className="iu-support-operator__dock" aria-label="Pannello assistenza">
        <article className="iu-support-panel">
          <div className="iu-support-panel__title">
            {iconNode(<Link size={17} />)}
            <span>Link cliente</span>
          </div>
          <div className="iu-support-input-row">
            <input className="iu-support-input" id="joinUrlField" readOnly value={bootstrap.customerJoinUrl || ''} aria-label="Link cliente" />
            <button className="iu-support-button" id="copyLinkBtn" type="button">
              {iconNode(<Copy size={15} />)}<span>Copia</span>
            </button>
          </div>
          <p>Il controllo del PC richiede consenso separato del cliente e agente IUSENTRA Assistenza.</p>
        </article>

        <article className="iu-support-panel iu-support-panel--control">
          <div className="iu-support-panel__title">
            {iconNode(<MousePointer2 size={17} />)}
            <span>Controllo PC</span>
          </div>
          <p id="remoteControlHint">Dopo l'approvazione: clic sinistro, clic destro, doppio clic sul video, testo e tasti rapidi.</p>
          <div className="iu-support-control-grid">
            <input className="iu-support-input" id="remoteControlText" placeholder="Testo da digitare sul PC cliente" />
            <button className="iu-support-button iu-support-button--primary" id="sendRemoteTextBtn" type="button">
              {iconNode(<Keyboard size={15} />)}<span>Digita</span>
            </button>
          </div>
          <div className="iu-support-key-row" aria-label="Tasti rapidi">
            {[
              ['Enter', 'Invio'],
              ['Tab', 'Tab'],
              ['Escape', 'Esc'],
              ['Backspace', 'Cancella'],
              ['ArrowLeft', 'Sinistra'],
              ['ArrowUp', 'Su'],
              ['ArrowDown', 'Giù'],
              ['ArrowRight', 'Destra'],
            ].map(([key, label]) => (
              <button className="iu-support-button iu-support-button--compact" type="button" data-remote-key={key} key={key}>
                {label}
              </button>
            ))}
          </div>
        </article>

        <article className="iu-support-panel iu-support-panel--chat">
          <div className="iu-support-panel__title">
            {iconNode(<MessageCircle size={17} />)}
            <span>Chat tecnica</span>
          </div>
          <div id="chatLog" className="support-chat-log" />
          <div className="iu-support-input-row">
            <input className="iu-support-input" id="chatInput" placeholder="Scrivi un messaggio operativo" />
            <button className="iu-support-button" id="sendBtn" type="button">Invia</button>
          </div>
        </article>
      </section>
    </main>
  )
}
