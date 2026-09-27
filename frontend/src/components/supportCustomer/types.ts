/**
 * Tipi della stanza cliente di assistenza remota (`/support/join/<token>`).
 *
 * Il bootstrap arriva dal server (web/blueprints/support_remote.py, customer_room)
 * e contiene SOLO il token del cliente: nessun token o link dell'operatore.
 */

export type SupportCustomerBootstrap = {
  publicId: string
  role: 'client'
  authToken: string
  apiPrefix: string
  wsBase: string
  localControlBase: string
  localSignerBase: string
  localSignerLatestVersion: string
  customerName: string
  status: string
  closed: boolean
}

export type SupportCustomerPresence = {
  client?: boolean
  operator?: boolean
}

/** Vista ridotta della sessione (il server espone al cliente solo questi campi). */
export type SupportCustomerSession = {
  public_id?: string
  status?: string
  status_label?: string
  customer_name?: string
  practice_label?: string
  presence?: SupportCustomerPresence
  advanced_control_requested?: boolean
  advanced_control_approved?: boolean
}

export type ChatAuthor = 'me' | 'other'

export type ChatMessage = {
  id: number
  text: string
  who: ChatAuthor
}

export type SupportConsent = {
  screen: boolean
  audio: boolean
  chat: boolean
}

/** Messaggio del canale realtime `/support/ws/<public_id>`. */
export type SupportRealtimeMessage = {
  type?: string
  [key: string]: unknown
}

/** Perché la stanza è in sola lettura. */
export type SupportClosedReason = '' | 'closed' | 'unavailable'

export type SupportCustomerViewState = {
  statusText: string
  operatorConnected: boolean
  operatorReadyForStart: boolean
  supportStarted: boolean
  starting: boolean
  stopEnabled: boolean
  sessionClosed: boolean
  closedReason: SupportClosedReason
  unavailableMessage: string
  consent: SupportConsent
  micMuted: boolean
  micTrackCount: number
  advancedRequested: boolean
  advancedBusy: boolean
  chat: ChatMessage[]
  fullscreen: boolean
  chatCompact: boolean
}
