import { apiJson } from './lib/apiClient'
import type { LegalAction, LegalMetric, LegalSection, LegalTone, LegalUiContract, LegalWarning } from './giurisprudenzaData'

export type LegalIntelligenceRecord = {
  id: string
  kind: string
  title: string
  subtitle: string
  sourceLabel: string
  sourceKind: string
  sourceHref: string
  date: string
  area: string
  branch: string
  approvalLabel: string
  approvalTone: LegalTone
  stateLabel: string
  stateTone: LegalTone
  territory: string
  registryNumber: string
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
    writes: 'legacy_routes',
    route_owner: 'react_shell',
    external_fetch: false,
    ai_generation: false,
    canonical_source: 'backend_legacy',
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

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
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

function normaliseMetric(input: unknown): LegalMetric {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: text(item.label) || 'Metrica',
    value: scalar(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): LegalSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'metadata',
    items: list(item.items).map((entryInput) => {
      const entry = asRecord(entryInput)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: text(entry.label) || 'Voce',
        value: scalar(entry.value),
        note: text(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(input: unknown): LegalAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: safeHref(item.href, '/legal-intelligence'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): LegalWarning {
  const item = asRecord(input)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso disponibile.',
  }
}

function normaliseRecord(input: unknown): LegalIntelligenceRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'record',
    kind: text(item.kind) || 'dashboard',
    title: text(item.title) || 'Voce Legal Intelligence',
    subtitle: text(item.subtitle),
    sourceLabel: text(item.sourceLabel) || 'Fonte',
    sourceKind: text(item.sourceKind),
    sourceHref: safeHref(item.sourceHref),
    date: text(item.date),
    area: text(item.area),
    branch: text(item.branch),
    approvalLabel: text(item.approvalLabel),
    approvalTone: tone(item.approvalTone),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    territory: text(item.territory),
    registryNumber: text(item.registryNumber),
    legacyHref: safeHref(item.legacyHref, '/legal-intelligence?_legacy=1'),
    evidenceType: text(item.evidenceType) || 'metadato',
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
      writes: text(contracts.writes) || 'legacy_routes',
      route_owner: text(contracts.route_owner) || 'react_shell',
      external_fetch: contracts.external_fetch === true,
      ai_generation: contracts.ai_generation === true,
      canonical_source: text(contracts.canonical_source) || 'backend_legacy',
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

export async function getRicercaLegalePage(): Promise<LegalIntelligencePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/ricerca-legale', emptyLegalIntelligencePage)
  return normalisePage(payload)
}
