import type { SupportRealtimeMessage } from './types'

/**
 * Canale realtime `/support/ws/<public_id>` (segnalazione WebRTC, chat,
 * fotogrammi dell'agente locale, comandi di controllo PC).
 *
 * Stessa semantica di connectWs() dello script legacy: una sola promessa di
 * apertura condivisa, ping periodico, chiusura intenzionale distinta da una
 * chiusura inattesa. In più la riconnessione con attesa crescente: lo script
 * legacy dichiarava wsReconnectBaseDelayMs/wsReconnectMaxDelayMs senza usarli.
 */

export const WS_PING_INTERVAL_MS = 20000
export const WS_RECONNECT_BASE_DELAY_MS = 800
export const WS_RECONNECT_MAX_DELAY_MS = 6000

type RealtimeChannelOptions = {
  url: () => string
  onOpen: () => void
  onMessage: (message: SupportRealtimeMessage) => void
  /** Chiusura non richiesta dalla pagina (rete, server, sessione). */
  onUnexpectedClose: () => void
  /** Chiamata prima di ogni tentativo di riconnessione: false annulla. */
  shouldReconnect: () => boolean
  onReconnecting: (attempt: number, delayMs: number) => void
}

export function reconnectDelay(attempt: number): number {
  return Math.min(WS_RECONNECT_BASE_DELAY_MS * 2 ** Math.max(0, attempt), WS_RECONNECT_MAX_DELAY_MS)
}

export class SupportRealtimeChannel {
  private ws: WebSocket | null = null
  private openPromise: Promise<void> | null = null
  private pingTimer: number | null = null
  private reconnectTimer: number | null = null
  private reconnectAttempts = 0
  private readonly intentionallyClosed = new WeakSet<WebSocket>()
  private readonly options: RealtimeChannelOptions

  constructor(options: RealtimeChannelOptions) {
    this.options = options
  }

  isOpen(): boolean {
    return Boolean(this.ws && this.ws.readyState === WebSocket.OPEN)
  }

  send(message: SupportRealtimeMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false
    this.ws.send(JSON.stringify(message))
    return true
  }

  connect(): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return Promise.resolve()
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING && this.openPromise) return this.openPromise
    this.clearReconnectTimer()
    const ws = new WebSocket(this.options.url())
    this.ws = ws
    this.openPromise = new Promise<void>((resolve, reject) => {
      let settled = false
      const settleOk = () => {
        if (settled) return
        settled = true
        resolve()
      }
      const settleKo = (message: string) => {
        if (settled) return
        settled = true
        reject(new Error(message))
      }

      ws.onopen = () => {
        this.reconnectAttempts = 0
        this.startPing(ws)
        this.options.onOpen()
        settleOk()
      }
      ws.onerror = () => {
        settleKo('Canale realtime non disponibile.')
      }
      ws.onmessage = (event: MessageEvent) => {
        let message: SupportRealtimeMessage = {}
        try {
          message = JSON.parse(String(event.data || '{}')) as SupportRealtimeMessage
        } catch {
          return
        }
        this.options.onMessage(message)
      }
      ws.onclose = () => {
        settleKo('Canale realtime chiuso prima della connessione.')
        // Socket sostituito o chiuso dalla pagina: nessun avviso, nessuna riconnessione.
        if (this.ws !== ws || this.intentionallyClosed.has(ws)) return
        this.stopPing()
        this.openPromise = null
        this.ws = null
        this.options.onUnexpectedClose()
        this.scheduleReconnect()
      }
    })
    return this.openPromise
  }

  /** Chiusura richiesta dalla pagina: nessun messaggio di errore, nessuna riconnessione. */
  close(): void {
    this.clearReconnectTimer()
    this.reconnectAttempts = 0
    this.stopPing()
    const ws = this.ws
    this.ws = null
    this.openPromise = null
    if (ws) {
      this.intentionallyClosed.add(ws)
      try {
        ws.close()
      } catch {
        // Già chiuso.
      }
    }
  }

  private startPing(ws: WebSocket): void {
    this.stopPing()
    this.pingTimer = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
    }, WS_PING_INTERVAL_MS)
  }

  private stopPing(): void {
    if (this.pingTimer !== null) window.clearInterval(this.pingTimer)
    this.pingTimer = null
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null || !this.options.shouldReconnect()) return
    const delay = reconnectDelay(this.reconnectAttempts)
    this.reconnectAttempts += 1
    this.options.onReconnecting(this.reconnectAttempts, delay)
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null
      if (!this.options.shouldReconnect()) return
      this.connect().catch(() => {
        // L'errore arriva anche a onclose, che pianifica il tentativo successivo.
      })
    }, delay)
  }
}
