import { ApiClientError, apiPostJson, ensureJson } from '@/lib/apiClient'
import type {
  PresidioDetailPayload,
  PresidioEvidencePayload,
  PresidioListFilters,
  PresidioListPayload,
  PresidioMutation,
  PresidioMutationResult,
  PresidioResourceStatus,
  PresidioTransitionsPayload,
} from '../types'

const API_ROOT = '/api/v1/ui/notifiche-legali/presidi'

function appendQuery(params: URLSearchParams, key: string, value: string | number | undefined) {
  if (value === undefined || value === '') return
  params.set(key, String(value))
}

function assertPayloadOk<T extends { ok: boolean }>(payload: T): T {
  if (payload.ok) return payload
  throw new ApiClientError(500, {
    ok: false,
    code: 'invalid_response',
    message: 'Il registro ha restituito una risposta non valida.',
  })
}

export async function getPresidi(
  filters: PresidioListFilters,
  signal?: AbortSignal,
): Promise<PresidioListPayload> {
  const params = new URLSearchParams()
  appendQuery(params, 'status', filters.statuses.join(','))
  appendQuery(params, 'priority', filters.priority)
  appendQuery(params, 'fascicolo', filters.fascicolo.trim())
  appendQuery(params, 'assigned_user', filters.assigned_user)
  appendQuery(params, 'date_from', filters.date_from)
  appendQuery(params, 'date_to', filters.date_to)
  appendQuery(params, 'recipient', filters.recipient.trim())
  appendQuery(params, 'channel', filters.channel)
  appendQuery(params, 'legacy', filters.legacy)
  appendQuery(params, 'needs_review', filters.needs_review)
  appendQuery(params, 'cursor', filters.cursor)
  appendQuery(params, 'limit', filters.limit)
  const payload = await ensureJson<PresidioListPayload>(API_ROOT + '?' + params.toString(), { signal })
  return assertPayloadOk(payload)
}

export async function getPresidio(id: string, signal?: AbortSignal): Promise<PresidioDetailPayload> {
  const payload = await ensureJson<PresidioDetailPayload>(API_ROOT + '/' + encodeURIComponent(id), { signal })
  return assertPayloadOk(payload)
}

export async function getPresidioEvidence(
  id: string,
  signal?: AbortSignal,
): Promise<PresidioEvidencePayload> {
  const payload = await ensureJson<PresidioEvidencePayload>(
    API_ROOT + '/' + encodeURIComponent(id) + '/evidence',
    { signal },
  )
  return assertPayloadOk(payload)
}

export async function getPresidioTransitions(
  id: string,
  signal?: AbortSignal,
): Promise<PresidioTransitionsPayload> {
  const payload = await ensureJson<PresidioTransitionsPayload>(
    API_ROOT + '/' + encodeURIComponent(id) + '/transitions',
    { signal },
  )
  return assertPayloadOk(payload)
}

export async function mutatePresidio(
  id: string,
  mutation: PresidioMutation,
  body: Record<string, unknown> = {},
): Promise<PresidioMutationResult> {
  const payload = await apiPostJson<PresidioMutationResult>(
    API_ROOT + '/' + encodeURIComponent(id) + '/' + mutation,
    body,
    {
      ok: false,
      status: 503,
      code: 'network_unavailable',
      message: 'Operazione non completata. Verifica la connessione e riprova.',
    },
  )
  if (!payload.ok) {
    throw new ApiClientError(payload.status || 500, {
      ok: false,
      code: payload.code,
      message: payload.message,
      warnings: payload.warnings,
    })
  }
  return payload
}

export function evidenceContentUrl(
  presidioId: string,
  evidenceId: string,
  download = false,
): string {
  const base = API_ROOT
    + '/' + encodeURIComponent(presidioId)
    + '/evidence/' + encodeURIComponent(evidenceId)
    + '/content'
  return download ? base + '?download=1' : base
}

export function classifyPresidioError(error: unknown): {
  status: Exclude<PresidioResourceStatus, 'idle' | 'loading' | 'refreshing' | 'ready'>
  message: string
} {
  if (error instanceof ApiClientError) {
    const code = String(error.payload.code || '')
    if (code === 'feature_disabled' || code === 'feature_flag_disabled') {
      return {
        status: 'flag-off',
        message: 'Il nuovo registro non è attivo per questo studio.',
      }
    }
    if (error.status === 403) {
      return {
        status: 'forbidden',
        message: 'Non hai i permessi per consultare i presidi delle notifiche.',
      }
    }
    if (error.status === 503 || code === 'repository_unavailable') {
      return {
        status: 'repository-unavailable',
        message: 'Il registro persistente non è disponibile. Riprova tra qualche istante.',
      }
    }
  }
  return {
    status: 'error',
    message: 'Non è stato possibile caricare i presidi. Riprova tra qualche istante.',
  }
}
