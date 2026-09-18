import { apiJson, apiPostJson } from './api/client'
import { csrfHeader } from './api/csrf'

export type ClientPortalResponse<T = Record<string, unknown>> = T & {
  ok: boolean
  message?: string
  code?: string
  dashboard?: ClientPortalStudioPayload | ClientPortalClientPayload
}

export type PortalOption = {
  id: string
  label: string
  email?: string
  phone?: string
  fiscalCode?: string
  clientId?: string
  clientName?: string
  number?: string
  status?: string
  openedAt?: string
}

export type PortalRow = Record<string, unknown> & {
  id?: string
  title?: string
  status?: string
  body?: string
  label?: string
  created_at_label?: string
  updated_at_label?: string
  uploaded_at_label?: string
  starts_at_label?: string
  expires_at_label?: string
}

export type ClientPortalStudioPayload = {
  ok: boolean
  surface: 'studio'
  title: string
  canWrite: boolean
  featureFlags: Record<string, boolean>
  summary: Record<string, number>
  clientOptions: PortalOption[]
  matterOptions: PortalOption[]
  preventivoOptions?: PortalOption[]
  clients: PortalRow[]
  matters: PortalRow[]
  invites: PortalRow[]
  documentRequests: PortalRow[]
  documents: PortalRow[]
  signatures: PortalRow[]
  messages: PortalRow[]
  appointments: PortalRow[]
  notifications: PortalRow[]
  questionnaires: PortalRow[]
  surveys: PortalRow[]
  evidencePacks: PortalRow[]
  settings: Record<string, unknown>
}

export type ClientPortalClientPayload = {
  ok: boolean
  surface: 'client' | 'invite'
  token?: string
  message?: string
  featureFlags: Record<string, boolean>
  activityCenter?: {
    openItems: number
    nextAction: string
  }
  invite?: PortalRow
  client?: PortalRow
  matter?: PortalRow
  steps?: PortalRow[]
  documentRequests?: PortalRow[]
  documents?: PortalRow[]
  signatures?: PortalRow[]
  consents?: PortalRow[]
  /** L'informativa che il cliente deve poter leggere prima di accettare. */
  privacyNotice?: {
    key?: string
    version?: string
    title?: string
    declaration?: string
    text?: string
    sections?: { heading?: string; body?: string }[]
    controller?: { nome?: string; indirizzo?: string; email?: string; telefono?: string }
  }
  messages?: PortalRow[]
  appointments?: PortalRow[]
  notifications?: PortalRow[]
  questionnaires?: PortalRow[]
  surveys?: PortalRow[]
  evidencePacks?: PortalRow[]
  settings?: Record<string, unknown>
  uploadLimits?: {
    maxUploadMb: number
    allowedUploadTypes: string[]
    allowedLabel: string
  }
  profileCompletion?: {
    complete: boolean
    filled: number
    total: number
    percent: number
    missing: string[]
  }
}

export const emptyStudioPortal: ClientPortalStudioPayload = {
  ok: false,
  surface: 'studio',
  title: 'Portale Clienti',
  canWrite: false,
  featureFlags: {},
  summary: {},
  clientOptions: [],
  matterOptions: [],
  clients: [],
  matters: [],
  invites: [],
  documentRequests: [],
  documents: [],
  signatures: [],
  messages: [],
  appointments: [],
  notifications: [],
  questionnaires: [],
  surveys: [],
  evidencePacks: [],
  settings: {},
}

export const emptyClientPortal: ClientPortalClientPayload = {
  ok: false,
  surface: 'client',
  featureFlags: {},
  steps: [],
  documentRequests: [],
  documents: [],
  signatures: [],
  consents: [],
  messages: [],
  appointments: [],
  notifications: [],
  questionnaires: [],
  surveys: [],
  evidencePacks: [],
}

const TOKEN_KEY = 'iusentraClientPortalToken'

export function readClientPortalToken(): string {
  return window.localStorage.getItem(TOKEN_KEY) || window.sessionStorage.getItem(TOKEN_KEY) || ''
}

export function storeClientPortalToken(token: string): void {
  if (!token) return
  window.localStorage.setItem(TOKEN_KEY, token)
  window.sessionStorage.setItem(TOKEN_KEY, token)
}

export function clearClientPortalToken(): void {
  window.localStorage.removeItem(TOKEN_KEY)
  window.sessionStorage.removeItem(TOKEN_KEY)
}

export function clientPortalTokenFromPath(pathname = window.location.pathname): string {
  const match = pathname.match(/^\/portale-cliente\/invito\/(.+)$/)
  return match ? decodeURIComponent(match[1]) : ''
}

export async function loadStudioClientPortal(): Promise<ClientPortalStudioPayload> {
  return apiJson<ClientPortalStudioPayload>('/api/v1/ui/client-portal/dashboard', emptyStudioPortal)
}

export async function studioPortalPost<T = ClientPortalResponse>(
  url: string,
  body: Record<string, unknown>,
): Promise<T> {
  return apiPostJson<T>(url, body, { ok: false, message: 'Operazione non completata.' } as T)
}

export async function loadInvitePreview(token: string): Promise<ClientPortalClientPayload> {
  if (!token) return emptyClientPortal
  return apiJson<ClientPortalClientPayload>(`/api/v1/ui/client-portal/public/invites/${encodeURIComponent(token)}`, emptyClientPortal)
}

export async function acceptInvite(token: string): Promise<ClientPortalResponse<ClientPortalClientPayload>> {
  return apiPostJson<ClientPortalResponse<ClientPortalClientPayload>>(
    `/api/v1/ui/client-portal/public/invites/${encodeURIComponent(token)}/accept`,
    {},
    { ...emptyClientPortal, ok: false, message: 'Invito non attivato.' },
  )
}

export async function loadClientPortal(token = readClientPortalToken()): Promise<ClientPortalClientPayload> {
  if (!token) return emptyClientPortal
  return apiJson<ClientPortalClientPayload>('/api/v1/ui/client-portal/public/dashboard', emptyClientPortal, {
    headers: { 'X-Client-Portal-Token': token },
  })
}

export async function clientPortalPost<T = ClientPortalResponse>(
  url: string,
  body: Record<string, unknown>,
  token = readClientPortalToken(),
): Promise<T> {
  return apiPostJson<T>(url, body, { ok: false, message: 'Operazione non completata.' } as T, {
    headers: token ? { 'X-Client-Portal-Token': token } : {},
  })
}

export type ModuloPortale = {
  ok?: boolean
  compilabile?: boolean
  campi?: unknown[]
  pagine?: { numero: number; larghezza: number; altezza: number }[]
  documento?: string
  nome?: string
  versione?: number
  message?: string
}

/** I campi predisposti di un modulo mandato dallo studio. */
export async function caricaModuloPortale(
  documentId: string,
  token = readClientPortalToken(),
  signal?: AbortSignal,
): Promise<ModuloPortale> {
  return apiJson<ModuloPortale>(
    `/api/v1/ui/client-portal/public/documents/${encodeURIComponent(documentId)}/modulo`,
    { ok: false, compilabile: false, campi: [], pagine: [] },
    { headers: token ? { 'X-Client-Portal-Token': token } : {}, signal },
  )
}

/** Salva la copia compilata: l'originale dello studio non viene toccato. */
export async function compilaModuloPortale(
  documentId: string,
  valori: Record<string, string | boolean>,
  token = readClientPortalToken(),
): Promise<ClientPortalResponse> {
  return apiPostJson<ClientPortalResponse>(
    `/api/v1/ui/client-portal/public/documents/${encodeURIComponent(documentId)}/modulo`,
    { valori },
    { ok: false, message: 'Modulo non compilato.' },
    { headers: token ? { 'X-Client-Portal-Token': token } : {} },
  )
}

export type LinkInvito = {
  ok?: boolean
  available?: boolean
  url?: string
  message?: string
}

/** Il link riservato di un invito, decifrato dal server per l'avvocato. */
export async function caricaLinkInvito(inviteId: string): Promise<LinkInvito> {
  if (!inviteId) return { ok: false, available: false, url: '' }
  return apiJson<LinkInvito>(
    `/api/v1/ui/client-portal/studio/invites/${encodeURIComponent(inviteId)}/link`,
    { ok: false, available: false, url: '', message: 'Link non recuperabile.' },
  )
}

export type ConversazionePortale = {
  ok?: boolean
  messages?: Record<string, unknown>[]
  cursor?: string
  nuovi?: number
}

/** La coda della conversazione di una pratica, per la pagina dello studio. */
export async function caricaConversazioneStudio(matterId: string, segnalibro = ''): Promise<ConversazionePortale> {
  if (!matterId) return { ok: false, messages: [], cursor: segnalibro }
  const parametri = new URLSearchParams({ matterId })
  if (segnalibro) parametri.set('since', segnalibro)
  return apiJson<ConversazionePortale>(
    `/api/v1/ui/client-portal/studio/conversation?${parametri.toString()}`,
    { ok: false, messages: [], cursor: segnalibro },
  )
}

/** La coda della conversazione della propria pratica, per la pagina del cliente. */
export async function caricaConversazioneCliente(
  segnalibro = '',
  token = readClientPortalToken(),
): Promise<ConversazionePortale> {
  if (!token) return { ok: false, messages: [], cursor: segnalibro }
  const parametri = new URLSearchParams()
  if (segnalibro) parametri.set('since', segnalibro)
  const coda = parametri.toString()
  return apiJson<ConversazionePortale>(
    `/api/v1/ui/client-portal/public/conversation${coda ? `?${coda}` : ''}`,
    { ok: false, messages: [], cursor: segnalibro },
    { headers: { 'X-Client-Portal-Token': token } },
  )
}

export async function uploadClientPortalDocument(
  file: File,
  requestId: string,
  token = readClientPortalToken(),
): Promise<ClientPortalResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('requestId', requestId)
  try {
    const response = await fetch('/api/v1/ui/client-portal/public/documents', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        ...csrfHeader(),
        ...(token ? { 'X-Client-Portal-Token': token } : {}),
      },
      body: form,
    })
    const payload = await response.json()
    return payload as ClientPortalResponse
  } catch {
    return { ok: false, message: 'Documento non caricato.' }
  }
}

export async function uploadStudioSignatureDocument(
  file: File,
  matterId: string,
  title: string,
): Promise<ClientPortalResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('matterId', matterId)
  form.append('title', title)
  try {
    const response = await fetch('/api/v1/ui/client-portal/studio/signature-requests/upload', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { ...csrfHeader() },
      body: form,
    })
    const payload = await response.json()
    return payload as ClientPortalResponse
  } catch {
    return { ok: false, message: 'Documento da firmare non caricato.' }
  }
}

export function clientPortalDocumentUrl(documentId: string, token = readClientPortalToken()): string {
  return `/api/v1/ui/client-portal/public/documents/${encodeURIComponent(documentId)}/download?token=${encodeURIComponent(token)}`
}

export function studioPortalDocumentUrl(documentId: string): string {
  return `/api/v1/ui/client-portal/studio/documents/${encodeURIComponent(documentId)}/download`
}

export async function exportClientPortalConversation(
  matterId: string,
  token = readClientPortalToken(),
): Promise<ClientPortalResponse> {
  if (!matterId || !token) return { ok: false, message: 'Conversazione non disponibile.' }
  try {
    const response = await fetch(`/api/v1/ui/client-portal/public/conversation-export?matterId=${encodeURIComponent(matterId)}`, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Client-Portal-Token': token,
      },
    })
    return await response.json() as ClientPortalResponse
  } catch {
    return { ok: false, message: 'Conversazione non esportata.' }
  }
}
