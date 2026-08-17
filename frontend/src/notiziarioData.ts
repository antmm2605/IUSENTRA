export type NotiziarioFilter = {
  id: string
  label: string
}

export type NotiziarioCase = {
  id: string
  label: string
}

export type NotiziarioQuickSource = {
  id: string
  label: string
  url: string
  requiresAuthentication: boolean
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
  publishedAt: string
  sourceName: string
  sourceCode: string
  sourceGroup: string
  sourceUrl: string
  matterName: string
  submatterName: string
  read: boolean
  readAt: string
  favorite: boolean
  linkedCaseId: string
  linkedCaseLabel: string
}

export type NotiziarioSourceState = {
  id: string
  label: string
  url: string
  ok: boolean
  count: number
  latestPublishedAt: string
  message: string
  preservedFromCache: boolean
}

export type NotiziarioPayload = {
  ok: boolean
  generatedAt: string
  refreshedAt: string
  refreshRequired: boolean
  sourceStates: NotiziarioSourceState[]
  items: NotiziarioItem[]
  filters: NotiziarioFilter[]
  quickSources: NotiziarioQuickSource[]
  cases: NotiziarioCase[]
  unreadCount: number
  message: string
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
  filters: [{ id: 'all', label: 'Tutte' }],
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

function normaliseItem(value: unknown): NotiziarioItem {
  const item = record(value)
  return {
    id: text(item.id),
    slug: text(item.slug),
    title: text(item.title) || 'Aggiornamento senza titolo',
    summary: text(item.summary),
    content: text(item.content),
    newsType: text(item.newsType) || 'focus',
    publishedAt: text(item.publishedAt),
    sourceName: text(item.sourceName) || 'Fonte istituzionale',
    sourceCode: text(item.sourceCode),
    sourceGroup: text(item.sourceGroup) || 'giustizia',
    sourceUrl: text(item.sourceUrl),
    matterName: text(item.matterName),
    submatterName: text(item.submatterName),
    read: boolean(item.read),
    readAt: text(item.readAt),
    favorite: boolean(item.favorite),
    linkedCaseId: text(item.linkedCaseId),
    linkedCaseLabel: text(item.linkedCaseLabel),
  }
}

function normalisePayload(value: unknown): NotiziarioPayload {
  const payload = record(value)
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
        url: text(item.url),
        ok: boolean(item.ok),
        count: Number(item.count || 0),
        latestPublishedAt: text(item.latestPublishedAt),
        message: text(item.message),
        preservedFromCache: boolean(item.preservedFromCache),
      }
    }).filter((item) => item.id && item.label),
    items: rows(payload.items).map(normaliseItem).filter((item) => item.id),
    filters: rows(payload.filters).map((value) => {
      const item = record(value)
      return { id: text(item.id), label: text(item.label) }
    }).filter((item) => item.id && item.label),
    quickSources: rows(payload.quickSources).map((value) => {
      const item = record(value)
      return {
        id: text(item.id),
        label: text(item.label),
        url: text(item.url),
        requiresAuthentication: boolean(item.requiresAuthentication),
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

export async function loadNotiziario(): Promise<NotiziarioPayload> {
  const response = await fetch('/api/v1/ui/notiziario', {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  const payload = normalisePayload(await readJson(response))
  if (!response.ok || !payload.ok) {
    throw new Error(payload.message || 'Notizie utili momentaneamente non disponibili.')
  }
  return payload
}

export async function refreshNotiziario(): Promise<NotiziarioPayload> {
  const response = await fetch('/api/v1/ui/notiziario/aggiorna', {
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
  const response = await fetch(`/api/v1/ui/notiziario/${encodeURIComponent(id)}/interazione`, {
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
  const response = await fetch(`/api/v1/ui/notiziario/fonti/${encodeURIComponent(source.id)}`, {
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
  return { ...emptyPayload }
}
