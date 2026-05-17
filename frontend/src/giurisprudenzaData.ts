import { apiJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type LegalTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type LegalUiContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  external_fetch: boolean
  ai_generation: boolean
  canonical_source: string
  legacy_contract?: string
}

export type LegalMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: LegalTone
}

export type LegalSectionItem = {
  id: string
  label: string
  value: string | number
  note: string
  tone: LegalTone
}

export type LegalSection = {
  id: string
  title: string
  kind: string
  items: LegalSectionItem[]
  emptyMessage: string
}

export type LegalAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: LegalTone
}

export type LegalWarning = {
  code: string
  message: string
}

export type GiurisprudenzaSource = {
  id: string
  label: string
  kind: string
  coverage: string
  accessMode: string
  sourceHref: string
  legacyHref: string
  lastRunAt: string
  stateLabel: string
  stateTone: LegalTone
  resolutionNote: string
  count: number
  evidenceType: string
}

export type PracticeLink = {
  id: string
  label: string
  href: string
}

export type GiurisprudenzaRecord = {
  id: string
  title: string
  subtitle: string
  sourceId: string
  sourceLabel: string
  sourceKind: string
  authority: string
  office: string
  date: string
  area: string
  branch: string
  subbranch: string
  grade: string
  jurisdiction: string
  caseNumber: string
  ecli: string
  orientation: string
  orientationKind: string
  verificationLabel: string
  verificationTone: LegalTone
  citationLabel: string
  tags: string[]
  legacyHref: string
  practiceLinks: PracticeLink[]
  evidenceType: string
  sourceHref: string
  summary: string
  principle: string
  abstract: string
  practicalUse: string
  reliabilityNote: string
  officialSource: boolean
  fullTextAvailable: boolean
}

export type GiurisprudenzaPageData = {
  source: string
  generated_at: string
  contracts: LegalUiContract
  metrics: LegalMetric[]
  sections: LegalSection[]
  records: GiurisprudenzaRecord[]
  actions: LegalAction[]
  forms: []
  warnings: LegalWarning[]
  sources: GiurisprudenzaSource[]
  filters: Record<string, string>
}

export const emptyGiurisprudenzaPage: GiurisprudenzaPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
    external_fetch: false,
    ai_generation: false,
    canonical_source: 'backend_storico',
  },
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
  sources: [],
  filters: {},
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function integer(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.trunc(value)
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseInt(value, 10)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function tone(value: unknown): LegalTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as LegalTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  if (href.startsWith('/') && href !== '#') return href
  if (href.startsWith('https://') || href.startsWith('http://')) return href
  return fallback
}

function normaliseMetric(input: unknown): LegalMetric {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSectionItem(input: unknown): LegalSectionItem {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: display(item.label) || 'Voce',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): LegalSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'informazioni',
    items: list(item.items).map(normaliseSectionItem),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(input: unknown): LegalAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: safeHref(item.href, '/giurisprudenza'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): LegalWarning {
  const item = asRecord(input)
  return {
    code: display(item.code) || 'warning',
    message: display(item.message) || 'Avviso disponibile.',
  }
}

function normalisePracticeLink(input: unknown): PracticeLink {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'collegamento',
    label: display(item.label) || 'Fascicolo collegato',
    href: safeHref(item.href),
  }
}

function normaliseSource(input: unknown): GiurisprudenzaSource {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'fonte',
    label: display(item.label) || 'Fonte',
    kind: display(item.kind),
    coverage: display(item.coverage),
    accessMode: display(item.accessMode),
    sourceHref: safeHref(item.sourceHref),
    legacyHref: safeHref(item.legacyHref),
    lastRunAt: display(item.lastRunAt),
    stateLabel: display(item.stateLabel),
    stateTone: tone(item.stateTone),
    resolutionNote: display(item.resolutionNote),
    count: integer(item.count),
    evidenceType: display(item.evidenceType) || 'fonte',
  }
}

function normaliseRecord(input: unknown): GiurisprudenzaRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'provvedimento',
    title: display(item.title) || 'Provvedimento',
    subtitle: display(item.subtitle),
    sourceId: text(item.sourceId),
    sourceLabel: display(item.sourceLabel) || 'Fonte',
    sourceKind: display(item.sourceKind),
    authority: display(item.authority),
    office: display(item.office),
    date: display(item.date),
    area: display(item.area),
    branch: display(item.branch),
    subbranch: display(item.subbranch),
    grade: display(item.grade),
    jurisdiction: display(item.jurisdiction),
    caseNumber: display(item.caseNumber),
    ecli: display(item.ecli),
    orientation: display(item.orientation),
    orientationKind: display(item.orientationKind),
    verificationLabel: display(item.verificationLabel),
    verificationTone: tone(item.verificationTone),
    citationLabel: display(item.citationLabel),
    tags: list(item.tags).map((tag) => display(tag)).filter(Boolean),
    legacyHref: safeHref(item.legacyHref, '/giurisprudenza'),
    practiceLinks: list(item.practiceLinks).map(normalisePracticeLink).filter((link) => link.href || link.label),
    evidenceType: display(item.evidenceType) || 'informazione',
    sourceHref: safeHref(item.sourceHref),
    summary: display(item.summary),
    principle: display(item.principle),
    abstract: display(item.abstract),
    practicalUse: display(item.practicalUse),
    reliabilityNote: display(item.reliabilityNote),
    officialSource: item.officialSource === true,
    fullTextAvailable: item.fullTextAvailable === true,
  }
}

function normalisePage(input: unknown): GiurisprudenzaPageData {
  const page = asRecord(input)
  const contracts = asRecord(page.contracts)
  const filtersPayload = asRecord(page.filters)
  const filters: Record<string, string> = {}
  for (const [key, value] of Object.entries(filtersPayload)) {
    const cleaned = text(value)
    if (cleaned) filters[key] = cleaned
  }
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true,
      writes: text(contracts.writes) || 'none',
      route_owner: text(contracts.route_owner) || 'react_shell',
      external_fetch: contracts.external_fetch === true,
      ai_generation: contracts.ai_generation === true,
      canonical_source: text(contracts.canonical_source) || 'backend_storico',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
    sources: list(page.sources).map(normaliseSource).filter((source) => source.id),
    filters,
  }
}

export async function getGiurisprudenzaPage(): Promise<GiurisprudenzaPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/giurisprudenza', emptyGiurisprudenzaPage)
  return normalisePage(payload)
}
