import { apiJson, apiPostJson } from '@/api/client'
import type {
  AttivitaDettaglio,
  AzioneEsito,
  BacklogPayload,
  PianoGiornoPayload,
} from './types'

const pianoVuoto: PianoGiornoPayload = {
  ok: false,
  stato: 'non_generato',
  data: '',
  data_label: '',
  utente: '',
  versione_piano: '',
  copertura: [],
  copertura_completa: false,
  riepilogo: {},
  sezioni: { da_fare_ora: [], pec: [], fascicoli: [], economico: [], da_assegnare: [] },
  agenda_oggi: [],
  avvisi: [],
  sintesi: '',
  sintesi_da_lex: false,
}

const pianoCache = new Map<string, { etag: string; piano: PianoGiornoPayload }>()

export type StatoAggiornamentoPiano = 'queued' | 'running' | 'done' | 'failed'

export type AggiornamentoPianoResponse = {
  ok: boolean
  accettato?: boolean
  gia_in_coda?: boolean
  avvio_immediato_richiesto?: boolean
  job_id?: string
  run_id?: string
  stato?: StatoAggiornamentoPiano
  stato_scheduler?: string
  messaggio?: string
  detail?: string
}

export type StatoAggiornamentoPianoResponse = {
  ok: boolean
  job_id?: string
  stato?: StatoAggiornamentoPiano
  /** Compatibilità con eventuali risposte precedenti del servizio automatico. */
  status?: StatoAggiornamentoPiano
  messaggio?: string
  detail?: string
  report?: Record<string, unknown>
}

export async function fetchPianoGiorno(
  signal?: AbortSignal,
  opts: { user?: string; date?: string } = {},
): Promise<PianoGiornoPayload> {
  const params = new URLSearchParams()
  if (opts.user) params.set('user', opts.user)
  if (opts.date) params.set('date', opts.date)
  const query = params.toString()
  const url = `/api/v1/ui/daily-plan${query ? `?${query}` : ''}`
  const cacheKey = `${opts.user || ''}|${opts.date || ''}`
  const cached = pianoCache.get(cacheKey)
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      signal,
      headers: {
        Accept: 'application/json',
        ...(cached?.etag ? { 'If-None-Match': cached.etag } : {}),
      },
    })
    if (response.status === 304 && cached) {
      return cached.piano
    }
    if (!response.ok) return pianoVuoto
    const payload = (await response.json()) as PianoGiornoPayload
    const etag = response.headers.get('ETag')
    if (etag) {
      pianoCache.set(cacheKey, { etag, piano: payload })
    }
    return payload
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    return pianoVuoto
  }
}

export function fetchDettaglioAttivita(itemId: string, signal?: AbortSignal) {
  return apiJson<{ ok: boolean; attivita?: AttivitaDettaglio }>(
    `/api/v1/ui/daily-plan/items/${encodeURIComponent(itemId)}`,
    { ok: false },
    { signal },
  )
}

export function fetchBacklog(
  opts: { user?: string; date?: string; cursor?: string; limit?: number } = {},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams()
  if (opts.user) params.set('user', opts.user)
  if (opts.date) params.set('date', opts.date)
  if (opts.cursor) params.set('cursor', opts.cursor)
  params.set('limit', String(opts.limit || 25))
  return apiJson<BacklogPayload>(
    `/api/v1/ui/daily-plan/backlog?${params.toString()}`,
    { ok: false, items: [], next_cursor: '', total_matching: 0, truncated: false },
    { signal },
  )
}

export function richiediAggiornamento(targetDate: string) {
  return apiPostJson<AggiornamentoPianoResponse>(
    '/api/v1/ui/daily-plan/refresh',
    {
      mode: 'incremental',
      date: targetDate,
      idempotency_key: `ui-${crypto.randomUUID()}`,
    },
    { ok: false },
  )
}

export function fetchStatoAggiornamento(jobId: string, signal?: AbortSignal) {
  return apiJson<StatoAggiornamentoPianoResponse>(
    `/api/v1/ui/daily-plan/jobs/${encodeURIComponent(jobId)}`,
    { ok: false, job_id: jobId },
    { signal },
  )
}

export function eseguiAzione(itemId: string, action: string, params: Record<string, unknown> = {}) {
  return apiPostJson<AzioneEsito>(
    `/api/v1/ui/daily-plan/items/${encodeURIComponent(itemId)}/action`,
    { action, params },
    { ok: false },
  )
}
