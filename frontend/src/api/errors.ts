import type { ApiErrorPayload } from './types'

const STATUS_MESSAGES: Record<number, string> = {
  400: 'La richiesta contiene dati non validi.',
  401: 'La sessione e scaduta. Accedi nuovamente per continuare.',
  403: 'Non hai i permessi per eseguire questa operazione.',
  404: 'La risorsa richiesta non e disponibile.',
  409: 'I dati sono stati modificati. Aggiorna la pagina e riprova.',
  422: 'Completa i campi richiesti prima di continuare.',
  500: 'Si e verificato un problema durante il caricamento.',
}

export class ApiClientError extends Error {
  status: number
  payload: ApiErrorPayload

  constructor(status: number, payload: ApiErrorPayload) {
    super(toUserMessage(payload, status))
    this.name = 'ApiClientError'
    this.status = status
    this.payload = payload
  }
}

export function toUserMessage(payload: ApiErrorPayload | unknown, status = 500): string {
  const record = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as ApiErrorPayload
    : {}
  const warningMessage = Array.isArray(record.warnings)
    ? record.warnings.map((warning) => warning.message).filter(Boolean).join(' ')
    : ''
  const backendMessage = String(record.message || record.errore || warningMessage || '').trim()
  return backendMessage || STATUS_MESSAGES[status] || 'Operazione non riuscita. Riprova tra qualche istante.'
}

export function normaliseErrorPayload(payload: unknown, status: number, fallback: unknown): ApiErrorPayload {
  const record = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : {}
  const base = fallback && typeof fallback === 'object' && !Array.isArray(fallback)
    ? fallback as Record<string, unknown>
    : {}
  const merged = Object.keys(record).length ? record : base
  return {
    ...merged,
    ok: false,
    status,
    message: toUserMessage(record, status),
  } as ApiErrorPayload
}
