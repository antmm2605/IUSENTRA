import { apiJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'
import type { LegalAction, LegalMetric, LegalSection, LegalTone, LegalUiContract, LegalWarning } from './giurisprudenzaData'

export type LegalIntelligenceRecord = {
  id: string
  kind: string
  title: string
  subtitle: string
  sourceLabel: string
  sourceKind: string
  sourceHref: string
  sourceExcerpt: string
  sourceContext: string[]
  officialContext: string
  contextSummary: string
  keyPoints: string[]
  operationalChecks: string[]
  contextStatus: string
  contextSource: string
  contextCompleted: boolean
  practicalUse: string
  reliabilityNote: string
  followUpQuery: string
  date: string
  area: string
  branch: string
  approvalLabel: string
  approvalTone: LegalTone
  stateLabel: string
  stateTone: LegalTone
  territory: string
  registryNumber: string
  taxCode: string
  vatNumber: string
  email: string
  website: string
  organismoType: string
  registryKind: string
  registrySection: string
  statusDate: string
  isActive: boolean
  legacyHref: string
  evidenceType: string
}

export type LegalIntelligencePageData = {
  source: string
  generated_at: string
  contracts: LegalUiContract
  metrics: LegalMetric[]
  sections: LegalSection[]
  records: LegalIntelligenceRecord[]
  actions: LegalAction[]
  forms: []
  warnings: LegalWarning[]
  filters: Record<string, string>
}

export const emptyLegalIntelligencePage: LegalIntelligencePageData = {
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

function textList(value: unknown): string[] {
  return list(value)
    .map((item) => display(item))
    .filter(Boolean)
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

function normaliseSection(input: unknown): LegalSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'informazioni',
    items: list(item.items).map((entryInput) => {
      const entry = asRecord(entryInput)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: display(entry.label) || 'Voce',
        value: scalar(entry.value),
        note: display(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(input: unknown): LegalAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: safeHref(item.href, '/ricerca-legale'),
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

function normaliseRecord(input: unknown): LegalIntelligenceRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'record',
    kind: display(item.kind) || 'dashboard',
    title: display(item.title) || 'Voce ricerca legale',
    subtitle: display(item.subtitle),
    sourceLabel: display(item.sourceLabel) || 'Fonte',
    sourceKind: display(item.sourceKind),
    sourceHref: safeHref(item.sourceHref),
    sourceExcerpt: display(item.sourceExcerpt) || display(item.subtitle),
    sourceContext: textList(item.sourceContext),
    officialContext: display(item.officialContext),
    contextSummary: display(item.contextSummary),
    keyPoints: textList(item.keyPoints),
    operationalChecks: textList(item.operationalChecks),
    contextStatus: display(item.contextStatus),
    contextSource: display(item.contextSource),
    contextCompleted: item.contextCompleted === true,
    practicalUse: display(item.practicalUse),
    reliabilityNote: display(item.reliabilityNote),
    followUpQuery: display(item.followUpQuery),
    date: display(item.date),
    area: display(item.area),
    branch: display(item.branch),
    approvalLabel: display(item.approvalLabel),
    approvalTone: tone(item.approvalTone),
    stateLabel: display(item.stateLabel),
    stateTone: tone(item.stateTone),
    territory: display(item.territory),
    registryNumber: display(item.registryNumber),
    taxCode: display(item.taxCode),
    vatNumber: display(item.vatNumber),
    email: display(item.email),
    website: display(item.website),
    organismoType: display(item.organismoType),
    registryKind: display(item.registryKind),
    registrySection: display(item.registrySection),
    statusDate: display(item.statusDate),
    isActive: item.isActive === true,
    legacyHref: safeHref(item.legacyHref, '/ricerca-legale'),
    evidenceType: display(item.evidenceType) || 'informazione',
  }
}

function normalisePage(input: unknown): LegalIntelligencePageData {
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
    filters,
  }
}

export async function getLegalIntelligencePage(): Promise<LegalIntelligencePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/legal-intelligence', emptyLegalIntelligencePage)
  return normalisePage(payload)
}

export async function getLegalIntelligenceNewsPage(): Promise<LegalIntelligencePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/legal-intelligence/news', emptyLegalIntelligencePage)
  return normalisePage(payload)
}

export async function getLegalIntelligenceMediazionePage(): Promise<LegalIntelligencePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/legal-intelligence/mediazione', emptyLegalIntelligencePage)
  return normalisePage(payload)
}

export async function getRicercaLegalePage(params: { q?: string } = {}): Promise<LegalIntelligencePageData> {
  const search = new URLSearchParams()
  if (params.q?.trim()) search.set('q', params.q.trim())
  const suffix = search.toString() ? `?${search.toString()}` : ''
  const payload = await apiJson<unknown>(`/api/v1/ui/ricerca-legale${suffix}`, emptyLegalIntelligencePage)
  return normalisePage(payload)
}
