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
  messages?: PortalRow[]
  appointments?: PortalRow[]
  notifications?: PortalRow[]
  questionnaires?: PortalRow[]
  surveys?: PortalRow[]
  evidencePacks?: PortalRow[]
  settings?: Record<string, unknown>
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
