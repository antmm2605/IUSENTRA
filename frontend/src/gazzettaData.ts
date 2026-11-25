import { csrfHeader } from './api/csrf'

/** Atto del sommario ufficiale della Gazzetta Ufficiale (date in AAAA-MM-GG, mostrate in gg/mm/aaaa). */
export type GazzettaAtto = {
  id: string
  series: string
  seriesLabel: string
  seriesShort: string
  issueNumber: string
  issueDate: string
  issueUrl: string
  heading: string
  title: string
  description: string
  authority: string
  section: string
  kind: string
  kindLabel: string
  actNumber: string
  actDate: string
  editorialCode: string
  page: string
  officialUrl: string
  /** Il testo completo dell'atto è salvato nell'archivio e si legge nella pagina. */
  hasText?: boolean
}

/** Testo completo di un atto, da /api/v1/ui/gazzetta-ufficiale/atti/<id>/testo. */
export type GazzettaTesto = {
  ok: boolean
  id: string
  available: boolean
  heading: string
  text: string
  textUrl: string
  articles: number
  readAt: string
  /** «Gazzetta Ufficiale, vista «originario»» oppure «Normattiva, testo originario (codice redazionale …)». */
  source?: string
  message: string
}

export type GazzettaFacet = { id: string; label: string; count: number }

export type GazzettaStatoSerie = {
  id: string
  label: string
  url: string
  checked: boolean
  ok: boolean
  lastAttemptAt: string
  lastSuccessAt: string
  message: string
  count: number
  latestIssue: { number: string; date: string; url: string } | null
}

export type GazzettaPayload = {
  ok: boolean
  archiveMissing: boolean
  message: string
  items: GazzettaAtto[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
  facets: { series: GazzettaFacet[]; kinds: GazzettaFacet[]; sections: GazzettaFacet[]; authorities: GazzettaFacet[] }
  sourceStates: GazzettaStatoSerie[]
  archive: { from: string; to: string; total: number }
  refresh?: { done: boolean; reason: string }
}

export type GazzettaUltime = {
  ok: boolean
  archiveMissing: boolean
  message: string
  items: GazzettaAtto[]
  sourceStates: GazzettaStatoSerie[]
}

export type GazzettaQuery = {
  q: string
  serie: string
  tipo: string
  rubrica: string
  ente: string
  dal: string
  al: string
  numero: string
  ordine: string
  pagina: number
}

export const GAZZETTA_PAGINA = '/ricerca-legale/gazzetta-ufficiale'
export const GAZZETTA_QUERY_INIZIALE: GazzettaQuery = {
  q: '', serie: '', tipo: '', rubrica: '', ente: '', dal: '', al: '', numero: '', ordine: '', pagina: 1,
}
const ERRORE = 'La Gazzetta Ufficiale non è consultabile in questo momento. Riprova fra poco.'

export function gazzettaVuota(): GazzettaPayload {
  return {
    ok: true,
    archiveMissing: false,
    message: '',
    items: [],
    total: 0,
    page: 1,
    pageSize: 25,
    hasMore: false,
    facets: { series: [], kinds: [], sections: [], authorities: [] },
    sourceStates: [],
    archive: { from: '', to: '', total: 0 },
  }
}

/** Senza scelta esplicita: pertinenza nella ricerca, data dell'atto nell'elenco. */
export const ORDINI_AMMESSI: readonly string[] = ['pertinenza', 'recenti', 'meno_recenti', 'data_atto_recenti', 'data_atto_meno_recenti']

export function gazzettaQueryString(query: GazzettaQuery): string {
  const params = new URLSearchParams()
  for (const chiave of ['q', 'serie', 'tipo', 'rubrica', 'ente', 'dal', 'al', 'numero'] as const) {
    if (query[chiave].trim()) params.set(chiave, query[chiave].trim())
  }
  if (ORDINI_AMMESSI.includes(query.ordine)) params.set('ordine', query.ordine)
  if (query.pagina > 1) params.set('pagina', String(query.pagina))
  const testo = params.toString()
  return testo ? `?${testo}` : ''
}

export function gazzettaQueryDaIndirizzo(search: string): GazzettaQuery {
  const params = new URLSearchParams(search)
  const pagina = Number.parseInt(params.get('pagina') || '1', 10)
  return {
    ...GAZZETTA_QUERY_INIZIALE,
    q: params.get('q') || '',
    serie: params.get('serie') || '',
    tipo: params.get('tipo') || '',
    rubrica: params.get('rubrica') || '',
    ente: params.get('ente') || '',
    dal: params.get('dal') || '',
    al: params.get('al') || '',
    numero: params.get('numero') || '',
    ordine: ORDINI_AMMESSI.includes(params.get('ordine') || '') ? params.get('ordine') || '' : '',
    pagina: Number.isFinite(pagina) && pagina > 0 ? pagina : 1,
  }
}

async function leggi<T>(url: string, init: RequestInit = {}): Promise<T> {
  let risposta: Response
  try {
    risposta = await fetch(url, { credentials: 'same-origin', ...init, headers: { Accept: 'application/json', ...(init.headers || {}) } })
  } catch {
    throw new Error('Connessione non disponibile. Controlla la rete e riprova.')
  }
  let dati: unknown = null
  try {
    dati = await risposta.json()
  } catch {
    dati = null
  }
  const oggetto = (dati && typeof dati === 'object' ? dati : {}) as { ok?: boolean; message?: string }
  if (!risposta.ok || oggetto.ok === false) throw new Error(oggetto.message || ERRORE)
  return dati as T
}

async function leggiElencoGazzetta(url: string, init: RequestInit): Promise<GazzettaPayload> {
  const dati = await leggi<GazzettaPayload>(url, init)
  if (!dati || !Array.isArray(dati.items) || !Array.isArray(dati.sourceStates) || !dati.facets || !dati.archive) throw new Error(ERRORE)
  return dati
}

export function loadGazzetta(query: GazzettaQuery, signal?: AbortSignal): Promise<GazzettaPayload> {
  return leggiElencoGazzetta(`/api/v1/ui/gazzetta-ufficiale${gazzettaQueryString(query)}`, { signal })
}

export function loadGazzettaUltime(signal?: AbortSignal): Promise<GazzettaUltime> {
  return leggi<GazzettaUltime>('/api/v1/ui/gazzetta-ufficiale/ultime', { signal })
}

export function loadGazzettaTesto(id: string, signal?: AbortSignal): Promise<GazzettaTesto> {
  return leggi<GazzettaTesto>(`/api/v1/ui/gazzetta-ufficiale/atti/${encodeURIComponent(id)}/testo`, { signal })
}

export function loadGazzettaSommario(id: string, signal?: AbortSignal): Promise<{ items: GazzettaAtto[] }> {
  return leggi(`/api/v1/ui/gazzetta-ufficiale/atti/${encodeURIComponent(id)}/sommario`, { signal })
}

export function refreshGazzetta(query: GazzettaQuery): Promise<GazzettaPayload> {
  return leggiElencoGazzetta(`/api/v1/ui/gazzetta-ufficiale/aggiorna${gazzettaQueryString({ ...query, pagina: 1 })}`, {
    method: 'POST',
    headers: csrfHeader(),
  })
}

/** «GU Serie generale n. 261 del 09/11/2026» */
export function estremiGazzetta(atto: Pick<GazzettaAtto, 'seriesLabel' | 'issueNumber' | 'issueDate'>, dataIt: (valore: string) => string): string {
  return `GU ${atto.seriesLabel} n. ${atto.issueNumber} del ${dataIt(atto.issueDate)}`
}
