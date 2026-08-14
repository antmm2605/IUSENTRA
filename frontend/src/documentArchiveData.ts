export type DocumentArchiveScope = 'attivi' | 'cestino'

export type DocumentArchiveFacet = {
  value: string
  label: string
  count: number
}

export type DocumentArchiveRow = {
  id: string
  matterId: string
  matterRef: string
  matterTitle: string
  matterStatus: string
  matterArchived: boolean
  name: string
  originalName: string
  type: string
  typeLabel: string
  format: string
  size: string
  sizeBytes: number
  uploadedAt: string
  uploadedAtIso: string
  documentDate: string
  documentDateIso: string
  notes: string
  tags: string[]
  source: string
  inTrash: boolean
  deletedAt: string
  deletedAtIso: string
  deletedBy: string
  actions: {
    matter: string
    preview: string
    download: string
    edit: string
    sign: string
    rename: string
    delete: string
    restore: string
    permanentDelete: string
  }
}
export type DocumentArchiveData = {
  source: string
  message: string
  summary: { active: number; trash: number; matters: number; formats: number }
  filters: { scope: DocumentArchiveScope; q: string; type: string; format: string; matter: string }
  facets: { types: DocumentArchiveFacet[]; formats: DocumentArchiveFacet[]; matters: DocumentArchiveFacet[] }
  pagination: { page: number; perPage: number; pages: number; total: number; from: number; to: number }
  items: DocumentArchiveRow[]
  actions: { newDocument: string; openMatters: string; searchStudio: string }
}

export type DocumentArchiveQuery = {
  scope: DocumentArchiveScope
  q: string
  type: string
  format: string
  matter: string
  page: number
}

const emptyData: DocumentArchiveData = {
  source: 'vuoto',
  message: '',
  summary: { active: 0, trash: 0, matters: 0, formats: 0 },
  filters: { scope: 'attivi', q: '', type: '', format: '', matter: '' },
  facets: { types: [], formats: [], matters: [] },
  pagination: { page: 1, perPage: 50, pages: 1, total: 0, from: 0, to: 0 },
  items: [],
  actions: {
    newDocument: '/template-atti/editor',
    openMatters: '/fascicoli',
    searchStudio: '/global-search?tipo=documenti',
  },
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown, fallback = ''): string {
  const current = typeof value === 'string' || typeof value === 'number' ? String(value).trim() : ''
  return current || fallback
}

function number(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 1 || value === '1' || value === 'true'
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function facets(value: unknown): DocumentArchiveFacet[] {
  return array(value).map((entry) => {
    const row = record(entry)
    return { value: text(row.value), label: text(row.label, text(row.value)), count: number(row.count) }
  }).filter((item) => item.value)
}

export function normalizeDocumentArchiveData(value: unknown): DocumentArchiveData {
  const payload = record(value)
  const summary = record(payload.summary)
  const filtersPayload = record(payload.filters)
  const facetsPayload = record(payload.facets)
  const pagination = record(payload.pagination)
  const actions = record(payload.actions)
  const scope = text(filtersPayload.scope, 'attivi') === 'cestino' ? 'cestino' : 'attivi'
  return {
    source: text(payload.source, emptyData.source),
    message: text(payload.message),
    summary: {
      active: number(summary.active),
      trash: number(summary.trash),
      matters: number(summary.matters),
      formats: number(summary.formats),
    },
    filters: {
      scope,
      q: text(filtersPayload.q),
      type: text(filtersPayload.type),
      format: text(filtersPayload.format),
      matter: text(filtersPayload.matter),
    },
    facets: {
      types: facets(facetsPayload.types),
      formats: facets(facetsPayload.formats),
      matters: facets(facetsPayload.matters),
    },
    pagination: {
      page: Math.max(1, number(pagination.page) || 1),
      perPage: Math.max(20, number(pagination.perPage) || 50),
      pages: Math.max(1, number(pagination.pages) || 1),
      total: number(pagination.total),
      from: number(pagination.from),
      to: number(pagination.to),
    },
    items: array(payload.items).map((entry, index) => {
      const row = record(entry)
      const rowActions = record(row.actions)
      return {
        id: text(row.id, `doc-${index}`),
        matterId: text(row.matterId),
        matterRef: text(row.matterRef),
        matterTitle: text(row.matterTitle, 'Fascicolo'),
        matterStatus: text(row.matterStatus),
        matterArchived: bool(row.matterArchived),
        name: text(row.name, 'Documento'),
        originalName: text(row.originalName),
        type: text(row.type, 'ALTRO'),
        typeLabel: text(row.typeLabel, 'Altro documento'),
        format: text(row.format, 'ALTRO'),
        size: text(row.size),
        sizeBytes: number(row.sizeBytes),
        uploadedAt: text(row.uploadedAt),
        uploadedAtIso: text(row.uploadedAtIso),
        documentDate: text(row.documentDate),
        documentDateIso: text(row.documentDateIso),
        notes: text(row.notes),
        tags: array(row.tags).map((tag) => text(tag)).filter(Boolean),
        source: text(row.source, 'Studio'),
        inTrash: bool(row.inTrash),
        deletedAt: text(row.deletedAt),
        deletedAtIso: text(row.deletedAtIso),
        deletedBy: text(row.deletedBy),
        actions: {
          matter: text(rowActions.matter),
          preview: text(rowActions.preview),
          download: text(rowActions.download),
          edit: text(rowActions.edit),
          sign: text(rowActions.sign),
          rename: text(rowActions.rename),
          delete: text(rowActions.delete),
          restore: text(rowActions.restore),
          permanentDelete: text(rowActions.permanentDelete),
        },
      }
    }),
    actions: {
      newDocument: text(actions.newDocument, emptyData.actions.newDocument),
      openMatters: text(actions.openMatters, emptyData.actions.openMatters),
      searchStudio: text(actions.searchStudio, emptyData.actions.searchStudio),
    },
  }
}

export async function loadDocumentArchive(query: DocumentArchiveQuery): Promise<DocumentArchiveData> {
  const params = new URLSearchParams({ scope: query.scope, page: String(query.page) })
  if (query.q.trim()) params.set('q', query.q.trim())
  if (query.type) params.set('tipo', query.type)
  if (query.format) params.set('formato', query.format)
  if (query.matter) params.set('fascicolo', query.matter)
  params.set('_ts', String(Date.now()))
  try {
    const response = await fetch(`/api/v1/ui/editor-professionale?${params.toString()}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) throw new Error('Archivio documentale non disponibile.')
    return normalizeDocumentArchiveData(await response.json())
  } catch (error) {
    return {
      ...emptyData,
      filters: { ...emptyData.filters, ...query },
      message: error instanceof Error ? error.message : 'Archivio documentale non disponibile.',
    }
  }
}
