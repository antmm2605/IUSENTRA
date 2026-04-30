import type { Tone } from './data'

export type ScadenziarioView =
  | 'aperte'
  | 'critiche'
  | 'alte'
  | 'completate'
  | 'scadute'
  | 'imminenti'
  | 'avanzate'
  | 'operative'
  | 'da_presidiare'
  | 'tutte'

export type ScadenziarioPriority = 'CRITICA' | 'ALTA' | 'MEDIA' | 'BASSA'
export type ScadenziarioStatus = 'APERTO' | 'COMPLETATO' | 'ANNULLATO' | 'SCADUTO'
export type ScadenziarioActionKind = 'link' | 'filter' | 'bulk_complete' | 'lex'

export type ScadenziarioFacet = {
  value: string
  label: string
  count: number
}

export type ScadenziarioSummary = {
  total: number
  open: number
  critical: number
  high: number
  completed: number
  overdue: number
  within7: number
  advanced: number
  operative: number
  peremptory: number
}

export type ScadenziarioRow = {
  id: string
  date: string
  dateLabel: string
  title: string
  description: string
  type: string
  typeLabel: string
  priority: ScadenziarioPriority
  priorityLabel: string
  tone: Tone
  status: ScadenziarioStatus
  statusLabel: string
  days: number | null
  daysLabel: string
  overdue: boolean
  dueToday: boolean
  peremptory: boolean
  advanced: boolean
  operative: boolean
  operationalDueAt: string
  operationalDueLabel: string
  fascicoloId: string
  fascicoloLabel: string
  ownerLabel: string
  sourceEventAt: string
  sourceEventLabel: string
  officeLabel: string
  traceCount: number
  href: string
  editHref: string
  completeHref: string
  deleteHref: string
}

export type ScadenziarioActionCard = {
  id: string
  title: string
  description: string
  value: number | string
  tone: Tone
  icon: 'alert' | 'calendar' | 'check' | 'calculator' | 'export' | 'lex' | 'archive'
  action: {
    kind: ScadenziarioActionKind
    label: string
    href?: string
    view?: ScadenziarioView
  }
}

export type ScadenziarioPageData = {
  generatedAt: string
  source: string
  contracts: {
    mock_fallback: boolean
    read_only: boolean
    writes: string
    route_owner: string
  }
  query: {
    view: ScadenziarioView
    q: string
    type: string
    priority: string
    from: string
    to: string
    peremptory: boolean
    advanced: boolean
    operative: boolean
  }
  summary: ScadenziarioSummary
  items: ScadenziarioRow[]
  overduePreview: ScadenziarioRow[]
  nextItems: ScadenziarioRow[]
  operativeCards: ScadenziarioActionCard[]
  facets: {
    views: ScadenziarioFacet[]
    types: ScadenziarioFacet[]
    priorities: ScadenziarioFacet[]
    statuses: ScadenziarioFacet[]
  }
  actions: {
    new: string
    exportCsv: string
    exportPdf: string
    exportIcs: string
    agenda: string
    calendarSettings: string
    lex: string
    bulkComplete: string
  }
}

export type ScadenziarioQuery = {
  view?: ScadenziarioView
  q?: string
  type?: string
  priority?: string
  from?: string
  to?: string
  peremptory?: boolean
  advanced?: boolean
  operative?: boolean
}

export const emptyScadenziarioPage: ScadenziarioPageData = {
  generatedAt: '',
  source: 'empty',
  contracts: {
    mock_fallback: false,
    read_only: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
  },
  query: {
    view: 'aperte',
    q: '',
    type: '',
    priority: '',
    from: '',
    to: '',
    peremptory: false,
    advanced: false,
    operative: false,
  },
  summary: {
    total: 0,
    open: 0,
    critical: 0,
    high: 0,
    completed: 0,
    overdue: 0,
    within7: 0,
    advanced: 0,
    operative: 0,
    peremptory: 0,
  },
  items: [],
  overduePreview: [],
  nextItems: [],
  operativeCards: [],
  facets: {
    views: [
      { value: 'aperte', label: 'Aperte', count: 0 },
      { value: 'critiche', label: 'Critiche', count: 0 },
      { value: 'alte', label: 'Alta priorità', count: 0 },
      { value: 'completate', label: 'Completate', count: 0 },
      { value: 'scadute', label: 'Scadute', count: 0 },
      { value: 'imminenti', label: 'Entro 7 gg', count: 0 },
      { value: 'avanzate', label: 'Avanzate', count: 0 },
      { value: 'operative', label: 'Operative', count: 0 },
    ],
    types: [{ value: '', label: 'Tutti i tipi', count: 0 }],
    priorities: [{ value: '', label: 'Tutte le priorità', count: 0 }],
    statuses: [{ value: '', label: 'Tutti gli stati', count: 0 }],
  },
  actions: {
    new: '/scadenziario/nuova',
    exportCsv: '/scadenziario/export.csv',
    exportPdf: '/scadenziario/pdf',
    exportIcs: '/scadenziario/export.ics',
    agenda: '/app-v2/agenda',
    calendarSettings: '/impostazioni/calendario',
    lex: '/lex?context=scadenziario',
    bulkComplete: '/scadenziario/bulk-completa',
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asString(value: unknown, fallback = ''): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value ?? fallback)
  return Number.isFinite(parsed) ? parsed : fallback
}

function asBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') return value
  return ['1', 'true', 'yes', 'on', 'si', 'sì'].includes(String(value ?? '').trim().toLowerCase())
}

function asArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (isRecord(value) && Array.isArray(value.items)) return value.items
  if (isRecord(value) && Array.isArray(value.data)) return value.data
  return []
}

function safeView(value: unknown): ScadenziarioView {
  const text = asString(value, 'aperte')
  const allowed: ScadenziarioView[] = ['aperte', 'critiche', 'alte', 'completate', 'scadute', 'imminenti', 'avanzate', 'operative', 'da_presidiare', 'tutte']
  return allowed.includes(text as ScadenziarioView) ? text as ScadenziarioView : 'aperte'
}

function safePriority(value: unknown): ScadenziarioPriority {
  const text = asString(value, 'MEDIA').toUpperCase()
  if (text === 'CRITICA' || text === 'ALTA' || text === 'MEDIA' || text === 'BASSA') return text
  return 'MEDIA'
}

function safeStatus(value: unknown): ScadenziarioStatus {
  const text = asString(value, 'APERTO').toUpperCase()
  if (text === 'APERTO' || text === 'COMPLETATO' || text === 'ANNULLATO' || text === 'SCADUTO') return text
  return 'APERTO'
}

function toneFromPriority(priority: ScadenziarioPriority, status: ScadenziarioStatus, overdue: boolean): Tone {
  if (status === 'COMPLETATO') return 'success'
  if (status === 'SCADUTO' || overdue || priority === 'CRITICA') return 'danger'
  if (priority === 'ALTA') return 'warning'
  if (priority === 'BASSA') return 'success'
  return 'primary'
}

function priorityLabel(priority: ScadenziarioPriority): string {
  if (priority === 'CRITICA') return 'Critica'
  if (priority === 'ALTA') return 'Alta'
  if (priority === 'BASSA') return 'Bassa'
  return 'Media'
}

function statusLabel(status: ScadenziarioStatus): string {
  if (status === 'COMPLETATO') return 'Completata'
  if (status === 'ANNULLATO') return 'Annullata'
  if (status === 'SCADUTO') return 'Scaduta'
  return 'Aperta'
}

function normalizeFacet(value: unknown): ScadenziarioFacet | null {
  if (!isRecord(value)) return null
  return {
    value: asString(value.value),
    label: asString(value.label, asString(value.value, 'Filtro')),
    count: asNumber(value.count),
  }
}

function normalizeFacets(value: unknown, fallback: ScadenziarioFacet[]): ScadenziarioFacet[] {
  const rows = asArray(value).map(normalizeFacet).filter(Boolean) as ScadenziarioFacet[]
  return rows.length ? rows : fallback
}

function normalizeRow(value: unknown, index = 0): ScadenziarioRow {
  const item = isRecord(value) ? value : {}
  const status = safeStatus(item.status)
  const priority = safePriority(item.priority)
  const daysRaw = item.days === null || item.days === undefined ? null : asNumber(item.days)
  const overdue = asBoolean(item.overdue) || status === 'SCADUTO' || (typeof daysRaw === 'number' && daysRaw < 0)
  const dueToday = asBoolean(item.dueToday) || daysRaw === 0
  const tone = asString(item.tone) as Tone || toneFromPriority(priority, status, overdue)
  return {
    id: asString(item.id, `scadenza-${index}`),
    date: asString(item.date),
    dateLabel: asString(item.dateLabel, asString(item.date, '-')),
    title: asString(item.title, 'Scadenza senza titolo'),
    description: asString(item.description),
    type: asString(item.type, 'ALTRO'),
    typeLabel: asString(item.typeLabel, asString(item.type, 'Altro')),
    priority,
    priorityLabel: asString(item.priorityLabel, priorityLabel(priority)),
    tone,
    status,
    statusLabel: asString(item.statusLabel, statusLabel(status)),
    days: daysRaw,
    daysLabel: asString(item.daysLabel, typeof daysRaw === 'number' ? `${daysRaw} gg` : '-'),
    overdue,
    dueToday,
    peremptory: asBoolean(item.peremptory),
    advanced: asBoolean(item.advanced),
    operative: asBoolean(item.operative),
    operationalDueAt: asString(item.operationalDueAt),
    operationalDueLabel: asString(item.operationalDueLabel, asString(item.operationalDueAt, '-')),
    fascicoloId: asString(item.fascicoloId),
    fascicoloLabel: asString(item.fascicoloLabel, '-'),
    ownerLabel: asString(item.ownerLabel, '-'),
    sourceEventAt: asString(item.sourceEventAt),
    sourceEventLabel: asString(item.sourceEventLabel),
    officeLabel: asString(item.officeLabel),
    traceCount: asNumber(item.traceCount),
    href: asString(item.href, `/scadenziario/${asString(item.id, '')}`),
    editHref: asString(item.editHref, `/scadenziario/${asString(item.id, '')}/modifica`),
    completeHref: asString(item.completeHref, `/scadenziario/${asString(item.id, '')}/completa`),
    deleteHref: asString(item.deleteHref, `/scadenziario/${asString(item.id, '')}/elimina`),
  }
}

function normalizeSummary(value: unknown): ScadenziarioSummary {
  if (!isRecord(value)) return emptyScadenziarioPage.summary
  return {
    total: asNumber(value.total),
    open: asNumber(value.open),
    critical: asNumber(value.critical),
    high: asNumber(value.high),
    completed: asNumber(value.completed),
    overdue: asNumber(value.overdue),
    within7: asNumber(value.within7),
    advanced: asNumber(value.advanced),
    operative: asNumber(value.operative),
    peremptory: asNumber(value.peremptory),
  }
}

function normalizeCard(value: unknown, index = 0): ScadenziarioActionCard | null {
  if (!isRecord(value)) return null
  const action = isRecord(value.action) ? value.action : {}
  const kind = asString(action.kind, 'link') as ScadenziarioActionKind
  return {
    id: asString(value.id, `card-${index}`),
    title: asString(value.title, 'Card operativa'),
    description: asString(value.description),
    value: value.value === undefined ? '' : (asString(value.value) || asNumber(value.value)),
    tone: asString(value.tone, 'primary') as Tone,
    icon: asString(value.icon, 'calendar') as ScadenziarioActionCard['icon'],
    action: {
      kind: ['link', 'filter', 'bulk_complete', 'lex'].includes(kind) ? kind : 'link',
      label: asString(action.label, 'Apri'),
      href: asString(action.href),
      view: action.view ? safeView(action.view) : undefined,
    },
  }
}

function normalizeCards(value: unknown): ScadenziarioActionCard[] {
  return asArray(value).map(normalizeCard).filter(Boolean) as ScadenziarioActionCard[]
}

function queryParams(query: ScadenziarioQuery): string {
  const params = new URLSearchParams()
  if (query.view) params.set('vista', query.view)
  if (query.q?.trim()) params.set('q', query.q.trim())
  if (query.type) params.set('tipo', query.type)
  if (query.priority) params.set('priorita', query.priority)
  if (query.from) params.set('dal', query.from)
  if (query.to) params.set('al', query.to)
  if (query.peremptory) params.set('perentorio', '1')
  if (query.advanced) params.set('avanzate', '1')
  if (query.operative) params.set('operative', '1')
  return params.toString()
}

export async function getScadenziarioPage(query: ScadenziarioQuery = {}): Promise<ScadenziarioPageData> {
  try {
    const qs = queryParams(query)
    const response = await fetch(`/api/v1/ui/scadenziario${qs ? `?${qs}` : ''}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyScadenziarioPage
    const payload = await response.json() as unknown
    if (!isRecord(payload)) return emptyScadenziarioPage
    const facets = isRecord(payload.facets) ? payload.facets : {}
    const queryPayload = isRecord(payload.query) ? payload.query : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    return {
      generatedAt: asString(payload.generatedAt),
      source: asString(payload.source, 'repository_reali'),
      contracts: isRecord(payload.contracts) ? {
        mock_fallback: asBoolean(payload.contracts.mock_fallback),
        read_only: asBoolean(payload.contracts.read_only),
        writes: asString(payload.contracts.writes, 'operational_routes'),
        route_owner: asString(payload.contracts.route_owner, 'react_shell'),
      } : emptyScadenziarioPage.contracts,
      query: {
        view: safeView(queryPayload.view),
        q: asString(queryPayload.q),
        type: asString(queryPayload.type),
        priority: asString(queryPayload.priority),
        from: asString(queryPayload.from),
        to: asString(queryPayload.to),
        peremptory: asBoolean(queryPayload.peremptory),
        advanced: asBoolean(queryPayload.advanced),
        operative: asBoolean(queryPayload.operative),
      },
      summary: normalizeSummary(payload.summary),
      items: asArray(payload.items).map(normalizeRow),
      overduePreview: asArray(payload.overduePreview).map(normalizeRow),
      nextItems: asArray(payload.nextItems).map(normalizeRow),
      operativeCards: normalizeCards(payload.operativeCards),
      facets: {
        views: normalizeFacets(facets.views, emptyScadenziarioPage.facets.views),
        types: normalizeFacets(facets.types, emptyScadenziarioPage.facets.types),
        priorities: normalizeFacets(facets.priorities, emptyScadenziarioPage.facets.priorities),
        statuses: normalizeFacets(facets.statuses, emptyScadenziarioPage.facets.statuses),
      },
      actions: {
        new: asString(actions.new, emptyScadenziarioPage.actions.new),
        exportCsv: asString(actions.exportCsv, emptyScadenziarioPage.actions.exportCsv),
        exportPdf: asString(actions.exportPdf, emptyScadenziarioPage.actions.exportPdf),
        exportIcs: asString(actions.exportIcs, emptyScadenziarioPage.actions.exportIcs),
        agenda: asString(actions.agenda, emptyScadenziarioPage.actions.agenda),
        calendarSettings: asString(actions.calendarSettings, emptyScadenziarioPage.actions.calendarSettings),
        lex: asString(actions.lex, emptyScadenziarioPage.actions.lex),
        bulkComplete: asString(actions.bulkComplete, emptyScadenziarioPage.actions.bulkComplete),
      },
    }
  } catch {
    return emptyScadenziarioPage
  }
}
