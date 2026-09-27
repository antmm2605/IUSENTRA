import { AgentScreenRelay } from './agentScreenRelay'
import { LocalSupportAgent } from './localAgent'
import { acquireCustomerMedia, type CustomerMediaStreams } from './customerMedia'
import { liveAudioTracks, setTracksEnabled, stopStream, errorMessage } from './mediaCapture'
import { SupportPeerLink } from './peerLink'
import { SupportRealtimeChannel } from './realtimeChannel'
import {
  SupportApiError,
  fetchRtcConfiguration,
  fetchSupportState,
  postClose,
  postConsent,
  postEscalation,
  postStart,
  supportWebSocketUrl,
} from './supportApi'
import type {
  ChatAuthor,
  SupportConsent,
  SupportCustomerBootstrap,
  SupportCustomerSession,
  SupportCustomerViewState,
  SupportRealtimeMessage,
} from './types'
import { ViewStore } from './viewStore'

/**
 * Regia della stanza cliente: porta in TypeScript la logica di
 * web/static/js/support_customer_room.js (consenso, avvio, chiusura, polling
 * dello stato, canale realtime, WebRTC, agente locale, controllo PC, chat).
 * React legge lo stato da `store`; nessuna manipolazione diretta del DOM.
 */

export const STATE_POLL_DELAY_MS = 12000
const MAX_CHAT_MESSAGES = 300

const AGENT_UNREACHABLE = /failed to fetch|networkerror|load failed|agente.*non disponibile|local signer/i

export const ADVANCED_AGENT_REQUIRED_MESSAGE =
  "Per il controllo del PC serve Local Signer aggiornato o l'agente IUSENTRA Assistenza su questo computer. "
  + 'IUSENTRA prova ad aggiornarlo automaticamente; se il servizio locale non risponde, apri il pacchetto ufficiale e riprova. '
  + 'La sola visualizzazione dello schermo funziona già dal browser.'

export const SESSION_UNAVAILABLE_MESSAGE =
  "Questo link di assistenza non è più valido o la sessione è stata rimossa. Chiedi all'operatore un nuovo link."

export function initialViewState(boot: SupportCustomerBootstrap, session: SupportCustomerSession): SupportCustomerViewState {
  const closed = boot.closed || session.status === 'closed'
  return {
    statusText: session.status_label || 'Sessione aggiornata',
    operatorConnected: Boolean(session.presence?.operator),
    operatorReadyForStart: false,
    supportStarted: false,
    starting: false,
    stopEnabled: false,
    sessionClosed: closed,
    closedReason: closed ? 'closed' : '',
    unavailableMessage: '',
    consent: { screen: true, audio: false, chat: true },
    micMuted: false,
    micTrackCount: 0,
    advancedRequested: false,
    advancedBusy: false,
    chat: [],
    fullscreen: false,
    chatCompact: false,
  }
}

/** Presa in carico: operatore presente o stato che segue l'apertura della stanza operatore. */
export function operatorHasTakenCharge(session: SupportCustomerSession): boolean {
  const status = String(session.status || '').toLowerCase()
  return Boolean(session.presence?.operator) || status === 'waiting_client' || status === 'waiting_peer' || status === 'active'
}

export class SupportCustomerController {
  readonly store: ViewStore<SupportCustomerViewState>
  private readonly boot: SupportCustomerBootstrap
  private readonly agent: LocalSupportAgent
  private readonly relay: AgentScreenRelay
  private readonly channel: SupportRealtimeChannel
  private readonly peer: SupportPeerLink
  private media: CustomerMediaStreams = { localStream: null, micStream: null, screenStream: null }
  private remoteStream: MediaStream | null = null
  private remoteAudio: HTMLAudioElement | null = null
  private stateTimer: number | null = null
  private stateSyncInFlight = false
  private mounted = false
  private chatSequence = 0

  constructor(boot: SupportCustomerBootstrap, session: SupportCustomerSession) {
    this.boot = boot
    this.store = new ViewStore(initialViewState(boot, session))
    const onStatus = (text: string) => this.setStatus(text)
    this.agent = new LocalSupportAgent({
      localControlBase: boot.localControlBase,
      localSignerBase: boot.localSignerBase,
      localSignerLatestVersion: boot.localSignerLatestVersion,
      onStatus,
    })
    this.channel = new SupportRealtimeChannel({
      url: () => supportWebSocketUrl(boot),
      onOpen: () => this.setStatus('Canale realtime attivo'),
      onMessage: (message) => {
        void this.handleRealtimeMessage(message)
      },
      onUnexpectedClose: () => {
        if (this.state.sessionClosed) return
        this.setStatus('Canale realtime chiuso')
        this.setPeer(false)
      },
      shouldReconnect: () => this.mounted && !this.state.sessionClosed && (this.state.supportStarted || this.relay.isControlArmed),
      onReconnecting: (_attempt, delayMs) => {
        this.setStatus(`Canale realtime chiuso: nuovo tentativo tra ${Math.max(1, Math.round(delayMs / 1000))} s`)
      },
    })
    this.relay = new AgentScreenRelay({
      agent: this.agent,
      publicId: boot.publicId,
      token: boot.authToken,
      send: (message) => this.channel.send(message),
      onStatus,
      onNotice: (text) => this.appendChat(text, 'me'),
      isClosed: () => this.state.sessionClosed,
    })
    this.peer = new SupportPeerLink({
      rtcConfiguration: () => fetchRtcConfiguration(boot),
      localStream: () => this.media.localStream,
      sendSignal: (message) => {
        this.channel.send(message)
      },
      onRemoteStream: (stream) => this.attachRemoteStream(stream),
      onChatMessage: (text) => this.appendChat(`Operatore: ${text}`, 'other'),
      onConnectionState: onStatus,
    })
  }

  get state(): SupportCustomerViewState {
    return this.store.getSnapshot()
  }

  // ── Stato visibile ───────────────────────────────────────────────────────

  setStatus(text: string): void {
    this.store.update({ statusText: text })
  }

  private setPeer(connected: boolean): void {
    this.store.update({ operatorConnected: connected })
  }

  appendChat(text: string, who: ChatAuthor = 'other'): void {
    this.chatSequence += 1
    const message = { id: this.chatSequence, text, who }
    this.store.update((current) => ({ chat: [...current.chat, message].slice(-MAX_CHAT_MESSAGES) }))
  }

  // ── Ciclo di vita ────────────────────────────────────────────────────────

  mount(): void {
    if (this.mounted) return
    this.mounted = true
    document.addEventListener('visibilitychange', this.onVisibilityChange)
    document.addEventListener('fullscreenchange', this.onFullscreenChange)
    window.addEventListener('beforeunload', this.onBeforeUnload)
    if (this.state.sessionClosed) {
      this.markSessionClosed(this.state.closedReason || 'closed')
      return
    }
    void this.agent.autoPrepareLocalSignerForSupport()
    void this.syncState()
    this.startPolling()
  }

  unmount(): void {
    if (!this.mounted) return
    this.mounted = false
    document.removeEventListener('visibilitychange', this.onVisibilityChange)
    document.removeEventListener('fullscreenchange', this.onFullscreenChange)
    window.removeEventListener('beforeunload', this.onBeforeUnload)
    this.stopPolling()
    this.teardown()
  }

  private readonly onVisibilityChange = () => {
    if (!document.hidden) void this.syncState()
  }

  private readonly onFullscreenChange = () => {
    this.store.update({ fullscreen: Boolean(document.fullscreenElement) })
  }

  private readonly onBeforeUnload = () => {
    this.teardown()
  }

  private startPolling(): void {
    if (this.stateTimer !== null || this.state.sessionClosed) return
    this.stateTimer = window.setInterval(() => {
      void this.syncState()
    }, STATE_POLL_DELAY_MS)
  }

  private stopPolling(): void {
    if (this.stateTimer !== null) window.clearInterval(this.stateTimer)
    this.stateTimer = null
  }

  // ── Audio in uscita e in ingresso ────────────────────────────────────────

  bindRemoteAudio(element: HTMLAudioElement | null): void {
    this.remoteAudio = element
    if (element && this.remoteStream && element.srcObject !== this.remoteStream) element.srcObject = this.remoteStream
  }

  private attachRemoteStream(stream: MediaStream): void {
    this.remoteStream = stream
    if (this.remoteAudio) this.remoteAudio.srcObject = stream
  }

  private customerAudioTracks(): MediaStreamTrack[] {
    return liveAudioTracks(this.media.micStream, this.media.localStream)
  }

  private refreshMicTracks(): void {
    this.store.update({ micTrackCount: this.customerAudioTracks().length })
  }

  private applyMicMuted(muted: boolean): void {
    setTracksEnabled(this.customerAudioTracks(), !muted)
    this.store.update({ micMuted: muted, micTrackCount: this.customerAudioTracks().length })
  }

  toggleMicrophone(): void {
    const current = this.state
    if (current.sessionClosed) return
    const tracks = this.customerAudioTracks()
    if (!tracks.length && !current.consent.audio) {
      this.refreshMicTracks()
      return
    }
    const muted = !current.micMuted
    this.applyMicMuted(muted)
    this.setStatus(
      tracks.length
        ? (muted ? 'Microfono cliente disattivato' : 'Microfono cliente attivo')
        : (muted ? "Microfono cliente disattivato all'avvio" : "Microfono cliente attivo all'avvio"),
    )
  }

  setConsent(key: keyof SupportConsent, value: boolean): void {
    if (this.state.sessionClosed) return
    const consent = { ...this.state.consent, [key]: value }
    // Togliendo il consenso al microfono si azzera anche la scelta «muto».
    this.store.update(key === 'audio' && !value ? { consent, micMuted: false } : { consent })
  }

  // ── Stato della sessione dal server ──────────────────────────────────────

  private applySession(session: SupportCustomerSession): void {
    const closed = this.state.sessionClosed
    this.store.update({
      statusText: session.status_label || 'Sessione aggiornata',
      operatorConnected: Boolean(session.presence?.operator),
      operatorReadyForStart: closed ? this.state.operatorReadyForStart : operatorHasTakenCharge(session),
      advancedRequested: Boolean(session.advanced_control_requested && !session.advanced_control_approved),
    })
    if (session.status === 'closed') this.markSessionClosed('closed')
  }

  async syncState(): Promise<void> {
    if (this.stateSyncInFlight || this.state.sessionClosed) return
    this.stateSyncInFlight = true
    try {
      const payload = await fetchSupportState(this.boot)
      this.applySession(payload.session || {})
    } catch (error) {
      console.error(error)
      if (error instanceof SupportApiError && (error.status === 401 || error.status === 404)) {
        this.markSessionClosed('unavailable', SESSION_UNAVAILABLE_MESSAGE)
      }
    } finally {
      this.stateSyncInFlight = false
    }
  }

  // ── Canale realtime ──────────────────────────────────────────────────────

  private async handleRealtimeMessage(message: SupportRealtimeMessage): Promise<void> {
    try {
      switch (message.type) {
        case 'peer_state':
          this.setPeer(Boolean(message.connected))
          return
        case 'offer':
          await this.peer.handleOffer(message.sdp as RTCSessionDescriptionInit)
          return
        case 'answer':
          await this.peer.handleAnswer(message.sdp as RTCSessionDescriptionInit)
          return
        case 'ice':
          if (message.candidate) await this.peer.addRemoteIceCandidate(message.candidate as RTCIceCandidateInit)
          return
        case 'chat':
          this.appendChat(`Operatore: ${String(message.text ?? '')}`, 'other')
          return
        case 'remote_control':
          await this.relay.executeRemoteCommand(message)
          return
        case 'error':
          this.setStatus(`Canale realtime: ${String(message.message || 'errore non specificato')}`)
          return
        default:
          // pong, start_offer (destinato all'operatore) e altri messaggi: nessuna azione.
      }
    } catch (error) {
      console.error(error)
      this.setStatus(`Errore connessione assistenza: ${errorMessage(error)}`)
    }
  }

  // ── Avvio e chiusura ─────────────────────────────────────────────────────

  async startSession(): Promise<void> {
    const current = this.state
    if (current.sessionClosed) {
      this.markSessionClosed(current.closedReason || 'closed')
      return
    }
    if (current.starting || current.supportStarted) return
    if (!current.operatorReadyForStart) {
      this.setStatus('Attendi che il SUPERADMIN prenda in carico la richiesta')
      return
    }
    this.store.update({ starting: true })
    try {
      await postConsent(this.boot, current.consent)
      this.media = await acquireCustomerMedia({
        consent: current.consent,
        micMuted: current.micMuted,
        relay: this.relay,
        isActive: () => !this.state.sessionClosed && this.state.supportStarted,
        onStatus: (text) => this.setStatus(text),
        onNotice: (text) => this.appendChat(text, 'me'),
        onMicMuted: (muted) => this.store.update({ micMuted: muted }),
      })
      this.applyMicMuted(this.state.micMuted)
      await this.channel.connect()
      if (this.media.localStream) await this.peer.ensure()
      await postStart(this.boot)
      this.store.update({ supportStarted: true, stopEnabled: true })
      this.setStatus('Sessione avviata')
      this.startPolling()
      await this.syncState()
    } catch (error) {
      console.error(error)
      this.teardown()
      this.setStatus(`Errore: ${errorMessage(error)}`)
    } finally {
      this.store.update({ starting: false })
    }
  }

  async stopSession(): Promise<void> {
    let closedOnServer = false
    try {
      await postClose(this.boot)
      closedOnServer = true
    } catch (error) {
      console.error(error)
    } finally {
      this.teardown()
      this.store.update({ stopEnabled: false, operatorReadyForStart: false })
      this.setStatus('Sessione chiusa')
    }
    // Il server ha chiuso la sessione: il link resta in sola lettura (lo script
    // legacy ci arrivava solo al successivo aggiornamento di stato).
    if (closedOnServer) this.markSessionClosed('closed')
  }

  /** Rilascia connessioni e flussi (cleanup(false) dello script legacy); il polling resta. */
  teardown(): void {
    void this.relay.disarm()
    this.peer.close()
    this.channel.close()
    stopStream(this.media.localStream)
    stopStream(this.media.screenStream)
    stopStream(this.media.micStream)
    this.media = { localStream: null, micStream: null, screenStream: null }
    this.store.update({ micMuted: false, supportStarted: false, micTrackCount: 0 })
  }

  markSessionClosed(reason: 'closed' | 'unavailable' = 'closed', message = ''): void {
    this.stopPolling()
    this.teardown()
    this.store.update({
      sessionClosed: true,
      closedReason: reason,
      unavailableMessage: message,
      statusText: reason === 'unavailable' ? 'Sessione non disponibile' : 'Sessione chiusa',
      operatorConnected: false,
      operatorReadyForStart: false,
      stopEnabled: false,
      advancedRequested: false,
      advancedBusy: false,
      starting: false,
    })
  }

  // ── Controllo PC (escalation) ────────────────────────────────────────────

  async approveAdvanced(): Promise<void> {
    if (this.state.sessionClosed || this.state.advancedBusy) return
    this.store.update({ advancedBusy: true })
    try {
      await this.relay.ensureControl()
      await this.channel.connect()
      await postEscalation(this.boot, 'approve')
      this.store.update({ advancedRequested: false })
      this.appendChat('Hai approvato il controllo remoto del PC.', 'me')
      this.startPolling()
      await this.syncState()
    } catch (error) {
      // «Failed to fetch» = agente non in esecuzione o rete locale bloccata dal browser.
      const raw = errorMessage(error)
      const visibleMessage = AGENT_UNREACHABLE.test(raw) ? ADVANCED_AGENT_REQUIRED_MESSAGE : `Errore: ${raw}`
      this.setStatus(visibleMessage)
      this.appendChat(visibleMessage, 'me')
    } finally {
      this.store.update({ advancedBusy: false })
    }
  }

  async rejectAdvanced(): Promise<void> {
    if (this.state.sessionClosed || this.state.advancedBusy) return
    this.store.update({ advancedBusy: true })
    try {
      await postEscalation(this.boot, 'reject')
      await this.relay.disarm()
      this.store.update({ advancedRequested: false })
      this.appendChat('Hai rifiutato il controllo remoto del PC.', 'me')
    } catch (error) {
      this.setStatus(`Errore: ${errorMessage(error)}`)
    } finally {
      this.store.update({ advancedBusy: false })
    }
  }

  // ── Chat ─────────────────────────────────────────────────────────────────

  /** Invia il testo (data channel, altrimenti WebSocket). Restituisce true se il campo va svuotato. */
  sendChat(rawText: string): boolean {
    if (this.state.sessionClosed) return false
    const text = rawText.trim()
    if (!text) return false
    const delivered = this.peer.sendChat(text) || this.channel.send({ type: 'chat', text })
    this.appendChat(`Tu: ${text}`, 'me')
    if (!delivered) this.setStatus("Messaggio non recapitato: avvia l'assistenza per scrivere al tecnico")
    return true
  }

  // ── Schermo intero e chat compatta ───────────────────────────────────────

  async toggleFullscreen(shell: HTMLElement | null): Promise<void> {
    if (this.state.sessionClosed) return
    if (this.state.fullscreen) {
      this.store.update({ fullscreen: false })
      if (document.fullscreenElement) {
        try {
          await document.exitFullscreen()
        } catch {
          // Il browser può aver già chiuso lo schermo intero.
        }
      }
      return
    }
    this.store.update({ fullscreen: true, chatCompact: true })
    try {
      if (shell?.requestFullscreen && document.fullscreenEnabled !== false) await shell.requestFullscreen()
    } catch {
      // Schermo intero negato: resta il layout a tutta finestra.
      this.store.update({ fullscreen: true })
    }
  }

  toggleCompactChat(): void {
    this.store.update((current) => ({ chatCompact: !current.chatCompact }))
  }
}
