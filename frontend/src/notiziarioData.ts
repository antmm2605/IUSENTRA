export type NotiziarioFilter = {
  id: string
  label: string
}

export type NotiziarioFacet = {
  id: string
  label: string
  count: number
}

export type NotiziarioCase = {
  id: string
  label: string
}

export type NotiziarioRelatedCase = {
  id: string
  label: string
  reason: string
}

export type NotiziarioQuickSource = {
  id: string
  label: string
  url: string
  requiresAuthentication: boolean
  directOpen: boolean
}

export type NotiziarioSourceReader = {
  ok: boolean
  id: string
  label: string
  url: string
  title: string
  sourceName: string
  blocks: string[]
  message: string
  fetchedAt: string
}

export type NotiziarioItem = {
  id: string
  slug: string
  title: string
  summary: string
  content: string
  newsType: string
  kind: string
  kindLabel: string
  publishedAt: string
  sourceName: string
  authority: string
  sourceCode: string
  sourceGroup: string
  sourceUrl: string
  officialReference: string
  matterName: string
  submatterName: string
  isNew: boolean
  relevance: number
  relevanceLabel: string
  relevanceRule: string
  relatedCases: NotiziarioRelatedCase[]
  relatedCasesTotal: number
  read: boolean
  readAt: string
  favorite: boolean
  linkedCaseId: string
  linkedCaseLabel: string
}

export type NotiziarioSourceState = {
  id: string
  label: string
  authority: string
  url: string
  ok: boolean
  checked: boolean
  count: number
  latestPublishedAt: string
  lastAttemptAt: string
  message: string
  frequencyMinutes: number
  preservedFromCache: boolean
}

export type NotiziarioPayload = {
  ok: boolean
  generatedAt: string
  refreshedAt: string
  refreshRequired: boolean
  sourceStates: NotiziarioSourceState[]
  items: NotiziarioItem[]
  total: number
  page: number
  hasMore: boolean
  filters: NotiziarioFilter[]
  facets: {
    sources: NotiziarioFacet[]
    kinds: NotiziarioFacet[]
    matters: NotiziarioFacet[]
  }
  relevantCount: number
  newCount: number
  serviceCount: number
  quickSources: NotiziarioQuickSource[]
  cases: NotiziarioCase[]
  unreadCount: number
  message: string
}

/** Filtri applicati dal server sull'archivio delle Notizie utili. */
export type NotiziarioQuery = {
  fonte: string
  tipo: string
  materia: string
  stato: 'all' | 'unread' | 'favorite'
  pertinenti: boolean
  nuove: boolean
  servizio: boolean
  q: string
  pagina: number
}

export const NOTIZIARIO_QUERY_INIZIALE: NotiziarioQuery = {
  fonte: '',
  tipo: '',
  materia: '',
  stato: 'all',
  pertinenti: false,
  nuove: false,
  servizio: false,
  q: '',
  pagina: 1,
}

type InteractionPatch = {
  read?: boolean
  favorite?: boolean
  linkedCaseId?: string
}

const emptyPayload: NotiziarioPayload = {
  ok: false,
  generatedAt: '',
  refreshedAt: '',
  refreshRequired: true,
  sourceStates: [],
  items: [],
  total: 0,
  page: 1,
  hasMore: false,
  filters: [{ id: 'all', label: 'Tutte' }],
  facets: { sources: [], kinds: [], matters: [] },
  relevantCount: 0,
  newCount: 0,
  serviceCount: 0,
  quickSources: [],
  cases: [],
  unreadCount: 0,
  message: '',
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
}

function boolean(value: unknown): boolean {
  return value === true
}

function rows(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function facets(value: unknown): NotiziarioFacet[] {
  return rows(value).map((entry) => {
    const item = record(entry)
    return { id: text(item.id), label: text(item.label), count: Number(item.count || 0) }
  }).filter((item) => item.id && item.label)
}

function normaliseItem(value: unknown): NotiziarioItem {
  const item = record(value)
  const kind = text(item.kind) || text(item.newsType)
  return {
    id: text(item.id),
    slug: text(item.slug),
    title: text(item.title) || 'Aggiornamento senza titolo',
    summary: text(item.summary),
    content: text(item.content),
    newsType: text(item.newsType) || 'focus',
    kind,
    kindLabel: text(item.kindLabel),
    publishedAt: text(item.publishedAt),
    sourceName: text(item.sourceName) || 'Fonte istituzionale',
    authority: text(item.authority),
    sourceCode: text(item.sourceCode),
    sourceGroup: text(item.sourceGroup) || 'giustizia',
    sourceUrl: text(item.sourceUrl),
    officialReference: text(item.officialReference),
    matterName: text(item.matterName),
    submatterName: text(item.submatterName),
    isNew: boolean(item.isNew),
    relevance: Number(item.relevance || 2),
    relevanceLabel: text(item.relevanceLabel),
    relevanceRule: text(item.relevanceRule),
    relatedCases: rows(item.relatedCases).map((entry) => {
      const related = record(entry)
      return { id: text(related.id), label: text(related.etichetta), reason: text(related.motivo) }
    }).filter((related) => related.id && related.label),
    relatedCasesTotal: Number(item.relatedCasesTotal || 0),
    read: boolean(item.read),
    readAt: text(item.readAt),
    favorite: boolean(item.favorite),
    linkedCaseId: text(item.linkedCaseId),
    linkedCaseLabel: text(item.linkedCaseLabel),
  }
}

function normalisePayload(value: unknown): NotiziarioPayload {
  const payload = record(value)
  const items = rows(payload.items).map(normaliseItem).filter((item) => item.id)
  const facetRecord = record(payload.facets)
  return {
    ok: boolean(payload.ok),
    generatedAt: text(payload.generatedAt),
    refreshedAt: text(payload.refreshedAt),
    refreshRequired: boolean(payload.refreshRequired),
    sourceStates: rows(payload.sourceStates).map((value) => {
      const item = record(value)
      return {
        id: text(item.id),
        label: text(item.label),
        authority: text(item.authority),
        url: text(item.url),
        ok: boolean(item.ok),
        checked: item.checked === undefined ? true : boolean(item.checked),
        count: Number(item.count || 0),
        latestPublishedAt: text(item.latestPublishedAt),
        lastAttemptAt: text(item.lastAttemptAt),
        message: text(item.message),
        frequencyMinutes: Number(item.frequencyMinutes || 0),
        preservedFromCache: boolean(item.preservedFromCache),
      }
    }).filter((item) => item.id && item.label),
    items,
    total: payload.total === undefined ? items.length : Number(payload.total || 0),
    page: Number(payload.page || 1),
    hasMore: boolean(payload.hasMore),
    filters: rows(payload.filters).map((value) => {
      const item = record(value)
      return { id: text(item.id), label: text(item.label) }
    }).filter((item) => item.id && item.label),
    facets: {
      sources: facets(facetRecord.sources),
      kinds: facets(facetRecord.kinds),
      matters: facets(facetRecord.matters),
    },
    relevantCount: Number(payload.relevantCount || 0),
    newCount: Number(payload.newCount || 0),
    serviceCount: Number(payload.serviceCount || 0),
    quickSources: rows(payload.quickSources).map((value) => {
      const item = record(value)
      return {
        id: text(item.id),
        label: text(item.label),
        url: text(item.url),
        requiresAuthentication: boolean(item.requiresAuthentication),
        directOpen: boolean(item.directOpen),
      }
    }).filter((item) => item.id && item.label && item.url),
    cases: rows(payload.cases).map((value) => {
      const item = record(value)
      return { id: text(item.id), label: text(item.label) }
    }).filter((item) => item.id && item.label),
    unreadCount: Number(payload.unreadCount || 0),
    message: text(payload.message),
  }
}

async function readJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/json')) return null
  try {
    return await response.json() as unknown
  } catch {
    return null
  }
}

const ERRORE_DI_RETE = 'Collegamento con il server non riuscito: controlla la connessione e riprova tra poco.'

/** Il browser segnala i problemi di rete con un messaggio tecnico in inglese («Failed to fetch»). */
async function richiesta(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init)
  } catch {
    throw new Error(ERRORE_DI_RETE)
  }
}

export function notiziarioQueryString(query: NotiziarioQuery): string {
  const params = new URLSearchParams()
  if (query.fonte) params.set('fonte', query.fonte)
  if (query.tipo) params.set('tipo', query.tipo)
  if (query.materia) params.set('materia', query.materia)
  if (query.stato !== 'all') params.set('stato', query.stato)
  if (query.pertinenti) params.set('pertinenti', '1')
  if (query.nuove) params.set('nuove', '1')
  if (query.servizio) params.set('servizio', '1')
  if (query.q.trim()) params.set('q', query.q.trim())
  if (query.pagina > 1) params.set('pagina', String(query.pagina))
  const value = params.toString()
  return value ? `?${value}` : ''
}

export async function loadNotiziario(query: NotiziarioQuery = NOTIZIARIO_QUERY_INIZIALE): Promise<NotiziarioPayload> {
  const response = await richiesta(`/api/v1/ui/notiziario${notiziarioQueryString(query)}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  const payload = normalisePayload(await readJson(response))
  if (!response.ok || !payload.ok) {
    throw new Error(payload.message || 'Notizie utili momentaneamente non disponibili.')
  }
  return payload
}

export async function refreshNotiziario(query: NotiziarioQuery = NOTIZIARIO_QUERY_INIZIALE): Promise<NotiziarioPayload> {
  const response = await richiesta(`/api/v1/ui/notiziario/aggiorna${notiziarioQueryString(query)}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  const payload = normalisePayload(await readJson(response))
  if (!response.ok || !payload.ok) {
    throw new Error(payload.message || 'Aggiornamento delle fonti non riuscito.')
  }
  return payload
}

export async function updateNotiziarioInteraction(id: string, patch: InteractionPatch): Promise<NotiziarioItem> {
  const response = await richiesta(`/api/v1/ui/notiziario/${encodeURIComponent(id)}/interazione`, {
    method: 'PATCH',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(patch),
  })
  const payload = record(await readJson(response))
  if (!response.ok || payload.ok !== true) {
    throw new Error(text(payload.message) || 'Modifica della notizia utile non salvata.')
  }
  return normaliseItem(payload.item)
}

export async function loadNotiziarioSource(source: NotiziarioQuickSource): Promise<NotiziarioSourceReader> {
  const response = await richiesta(`/api/v1/ui/notiziario/fonti/${encodeURIComponent(source.id)}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  const payload = record(await readJson(response))
  return {
    ok: response.ok && boolean(payload.ok),
    id: text(payload.id) || source.id,
    label: text(payload.label) || source.label,
    url: text(payload.url) || source.url,
    title: text(payload.title) || source.label,
    sourceName: text(payload.sourceName) || source.label,
    blocks: rows(payload.blocks).map(text).filter(Boolean),
    message: text(payload.message),
    fetchedAt: text(payload.fetchedAt),
  }
}

export function notiziarioEmptyPayload(): NotiziarioPayload {
  return { ...emptyPayload, facets: { sources: [], kinds: [], matters: [] } }
}
