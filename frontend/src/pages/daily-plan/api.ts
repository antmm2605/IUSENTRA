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

let ultimoEtag = ''
let ultimoPiano: PianoGiornoPayload | null = null

export async function fetchPianoGiorno(
  signal?: AbortSignal,
  opts: { user?: string; date?: string } = {},
): Promise<PianoGiornoPayload> {
  const params = new URLSearchParams()
  if (opts.user) params.set('user', opts.user)
  if (opts.date) params.set('date', opts.date)
  const query = params.toString()
  const url = `/api/v1/ui/daily-plan${query ? `?${query}` : ''}`
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      signal,
      headers: {
        Accept: 'application/json',
        ...(ultimoEtag ? { 'If-None-Match': ultimoEtag } : {}),
      },
    })
    if (response.status === 304 && ultimoPiano) {
      return ultimoPiano
    }
    if (!response.ok) return pianoVuoto
    const payload = (await response.json()) as PianoGiornoPayload
    const etag = response.headers.get('ETag')
    if (etag) {
      ultimoEtag = etag
      ultimoPiano = payload
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

export function richiediAggiornamento() {
  return apiPostJson<{ ok: boolean; accettato?: boolean; detail?: string }>(
    '/api/v1/ui/daily-plan/refresh',
    { mode: 'incremental', idempotency_key: `ui-${new Date().toISOString().slice(0, 16)}` },
    { ok: false },
  )
}

export function eseguiAzione(itemId: string, action: string, params: Record<string, unknown> = {}) {
  return apiPostJson<AzioneEsito>(
    `/api/v1/ui/daily-plan/items/${encodeURIComponent(itemId)}/action`,
    { action, params },
    { ok: false },
  )
}
