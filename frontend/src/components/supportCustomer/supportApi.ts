import type { SupportCustomerBootstrap, SupportCustomerSession } from './types'

/**
 * Chiamate HTTP della stanza cliente verso `/support/api/<public_id>/...`.
 *
 * Il ruolo resta nella query (`?role=client`, richiesto da authorize_support_http),
 * il token viaggia nell'intestazione `X-Support-Token`: non finisce nei log di
 * accesso né nella cronologia come accadeva con `?token=` nello script legacy.
 * Il WebSocket invece non ammette intestazioni dal browser: lì il token resta in query.
 */

export class SupportApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'SupportApiError'
    this.status = status
  }
}

type SupportFetchOptions = {
  method?: 'GET' | 'POST'
  body?: Record<string, unknown>
  query?: Record<string, string>
}

function queryString(boot: SupportCustomerBootstrap, extra: Record<string, string> = {}): string {
  const params = new URLSearchParams({ role: boot.role, ...extra })
  return params.toString()
}

export function supportApiUrl(boot: SupportCustomerBootstrap, path: string, extra: Record<string, string> = {}): string {
  return `${boot.apiPrefix}${path}?${queryString(boot, extra)}`
}

/** Messaggio leggibile dalla risposta: JSON del server, altrimenti testo breve (mai una pagina HTML). */
export function supportErrorMessage(payload: Record<string, unknown>, rawText: string, status: number): string {
  const fromPayload = [payload.description, payload.error, payload.message, payload.errore]
    .map((value) => (typeof value === 'string' ? value.trim() : ''))
    .find(Boolean)
  if (fromPayload) return fromPayload
  const trimmed = rawText.trim()
  if (trimmed && !trimmed.startsWith('<') && trimmed.length <= 240) return trimmed
  if (status === 401) return 'Link di assistenza non valido.'
  if (status === 404) return 'Sessione assistenza non trovata.'
  return `Errore del server (HTTP ${status}).`
}

export async function supportFetchJson<T extends Record<string, unknown>>(
  boot: SupportCustomerBootstrap,
  path: string,
  options: SupportFetchOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'X-Support-Token': boot.authToken,
  }
  if (options.body) headers['Content-Type'] = 'application/json'
  const response = await fetch(supportApiUrl(boot, path, options.query), {
    method: options.method || 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
    credentials: 'same-origin',
    cache: 'no-store',
  })
  const rawText = await response.text()
  let payload: Record<string, unknown> = {}
  try {
    payload = rawText ? JSON.parse(rawText) as Record<string, unknown> : {}
  } catch {
    payload = {}
  }
  if (!response.ok) {
    throw new SupportApiError(supportErrorMessage(payload, rawText, response.status), response.status)
  }
  return payload as T
}

export type SupportStatePayload = { ok?: boolean; session?: SupportCustomerSession }
export type SupportWebrtcPayload = { ok?: boolean; rtcConfiguration?: RTCConfiguration }

export function fetchSupportState(boot: SupportCustomerBootstrap): Promise<SupportStatePayload> {
  return supportFetchJson<SupportStatePayload>(boot, '/state', { query: { events: '0' } })
}

export async function fetchRtcConfiguration(boot: SupportCustomerBootstrap): Promise<RTCConfiguration> {
  // Le credenziali TURN sono temporanee (HMAC con scadenza): si chiedono al
  // momento di creare la connessione, non si mettono nel bootstrap della pagina.
  const payload = await supportFetchJson<SupportWebrtcPayload>(boot, '/webrtc-config')
  return payload.rtcConfiguration || { iceServers: [] }
}

export function postConsent(boot: SupportCustomerBootstrap, consent: { screen: boolean; audio: boolean; chat: boolean }) {
  return supportFetchJson(boot, '/consent', {
    method: 'POST',
    body: {
      consent_screen: consent.screen,
      consent_audio: consent.audio,
      consent_chat: consent.chat,
    },
  })
}

export function postStart(boot: SupportCustomerBootstrap) {
  return supportFetchJson(boot, '/start', { method: 'POST', body: {} })
}

export function postClose(boot: SupportCustomerBootstrap) {
  return supportFetchJson(boot, '/close', { method: 'POST', body: {} })
}

export function postEscalation(boot: SupportCustomerBootstrap, action: 'approve' | 'reject') {
  return supportFetchJson(boot, '/escalation', { method: 'POST', body: { action } })
}

export function supportWebSocketUrl(boot: SupportCustomerBootstrap): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const params = new URLSearchParams({ role: boot.role, token: boot.authToken })
  return `${protocol}://${window.location.host}${boot.wsBase}/${encodeURIComponent(boot.publicId)}?${params.toString()}`
}
