import type { ReactNode } from 'react'

export type SearchType =
  | 'all'
  | 'fascicoli'
  | 'clienti'
  | 'scadenze'
  | 'documenti'
  | 'comunicazioni'
  | 'economia'
  | 'telematico'

export type StudioSearchResult = {
  id: string
  type: Exclude<SearchType, 'all'>
  entityType: string
  entityId: string
  title: string
  subtitle: string
  meta: string
  status?: string
  updatedAt: string
  tags: string[]
  description: string
  href: string
  fascicoloHref?: string
}

export type StudioSearchStats = {
  total: number
  perType: Record<string, number>
  ftsEnabled: boolean
  lastIndexedAt: string
}

export type StudioSearchPayload = {
  ok: boolean
  query: string
  tookMs: number
  total: number
  results: StudioSearchResult[]
  stats: StudioSearchStats
  error?: string
}

export type StudioSearchFilter = {
  key: SearchType
  label: string
  icon: ReactNode
}

const emptyStats: StudioSearchStats = {
  total: 0,
  perType: {},
  ftsEnabled: false,
  lastIndexedAt: '',
}

export const emptyStudioSearchPayload: StudioSearchPayload = {
  ok: true,
  query: '',
  tookMs: 0,
  total: 0,
  results: [],
  stats: emptyStats,
}

const typeMap: Record<string, Exclude<SearchType, 'all'>> = {
  fascicolo: 'fascicoli',
  pratica: 'fascicoli',
  cliente: 'clienti',
  soggetto: 'clienti',
  parte: 'clienti',
  appuntamento: 'scadenze',
  agenda: 'scadenze',
  scadenza: 'scadenze',
  termine: 'scadenze',
  documento: 'documenti',
  atto: 'documenti',
  comunicazione: 'comunicazioni',
  email: 'comunicazioni',
  pec: 'comunicazioni',
  messaggio: 'comunicazioni',
  preventivo: 'economia',
  conferimento: 'economia',
  fattura: 'economia',
  parcella: 'economia',
  pagamento: 'economia',
  deposito: 'telematico',
  telematico: 'telematico',
  portale: 'telematico',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : String(value)
}

function asNumber(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map(asString).filter(Boolean)
}

function normalizeType(entityType: string): Exclude<SearchType, 'all'> {
  return typeMap[entityType] || 'documenti'
}

function formatDateLabel(value: string): string {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parsed)
}

export function formatLastIndexed(value: string): string {
  if (!value) return 'Indice non ancora popolato'
  return `Ultimo indice: ${formatDateLabel(value)}`
}

function resultStatus(entityType: string, metadata: Record<string, unknown>): string | undefined {
  const raw = asString(metadata.stato || metadata.status || metadata.priorita || metadata.priority)
  if (raw) return raw.toLowerCase()
  if (entityType === 'scadenza') return 'aperto'
  return undefined
}

function resultTags(entityType: string, metadata: Record<string, unknown>): string[] {
  const badges = asStringArray(metadata.badges)
  const tags = asStringArray(metadata.tags)
  const source = asString(metadata.source || metadata.fonte || metadata.categoria)
  return Array.from(new Set([entityType, source, ...badges, ...tags].filter(Boolean))).slice(0, 5)
}

function mapResult(item: unknown): StudioSearchResult {
  const row = asRecord(item)
  const metadata = asRecord(row.metadata)
  const entityType = asString(row.entity_type || row.type || row.tipo || 'documento')
  const entityId = asString(row.entity_id || row.id)
  const href = asString(row.source_url || row.url || '#') || '#'
  const date = asString(row.date || metadata.date || metadata.updated_at || metadata.data)
  const snippet = asString(row.snippet || row.description || row.body)
  const subtitle = asString(row.subtitle || row.sottotitolo || metadata.subtitle || metadata.sottotitolo)
  return {
    id: `${entityType}-${entityId || asString(row.id)}`,
    type: normalizeType(entityType),
    entityType,
    entityId,
    title: asString(row.title || row.titolo || 'Risultato indicizzato'),
    subtitle,
    meta: asString(metadata.meta || metadata.riferimento || date || row.source_module || entityType),
    status: resultStatus(entityType, metadata),
    updatedAt: date ? formatDateLabel(date) : 'Indice studio',
    tags: resultTags(entityType, metadata),
    description: snippet || subtitle || 'Elemento indicizzato nella Ricerca Studio.',
    href,
    fascicoloHref: asString(row.fascicolo_id) ? `/fascicoli/${asString(row.fascicolo_id)}` : href,
  }
}

function mapStats(value: unknown): StudioSearchStats {
  const stats = asRecord(value)
  const rawPerType = asRecord(stats.per_type)
  const perType = Object.fromEntries(Object.entries(rawPerType).map(([key, count]) => [key, asNumber(count)]))
  return {
    total: asNumber(stats.total),
    perType,
    ftsEnabled: Boolean(stats.fts_enabled),
    lastIndexedAt: asString(stats.last_indexed_at),
  }
}

export function mapStudioSearchPayload(value: unknown): StudioSearchPayload {
  const payload = asRecord(value)
  const results = Array.isArray(payload.results) ? payload.results.map(mapResult) : []
  return {
    ok: payload.ok !== false,
    query: asString(payload.query),
    tookMs: asNumber(payload.took_ms),
    total: asNumber(payload.total ?? results.length),
    results,
    stats: mapStats(payload.stats),
    error: asString(payload.error),
  }
}

export async function searchStudio(query: string, type: SearchType, limit = 40): Promise<StudioSearchPayload> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  if (type !== 'all') params.set('type', type)
  const response = await fetch(`/api/global-search?${params.toString()}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    return { ...emptyStudioSearchPayload, ok: false, query, error: 'Ricerca non disponibile.' }
  }
  return mapStudioSearchPayload(await response.json())
}

export async function loadStudioSearchStats(): Promise<StudioSearchStats> {
  const payload = await searchStudio('', 'all', 1)
  return payload.stats
}

export async function reindexStudioSearch(): Promise<StudioSearchStats> {
  const response = await fetch('/api/global-search/reindex', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) return emptyStats
  const payload = asRecord(await response.json())
  return mapStats(payload.stats)
}
