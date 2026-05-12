import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type TemplateVariableMeta = {
  name: string
  label: string
  kind: string
  source: string
}

export type TemplateAttiRecord = {
  id: string
  kind: string
  title: string
  subtitle: string
  description: string
  category: string
  matter: string
  area: string
  branch: string
  channel: string
  portal: string
  stateLabel: string
  stateTone: AdminTone
  complianceLabel: string
  cartabiaState: string
  cartabiaLabel: string
  processArea: string
  requiresLawyerReview: boolean
  prefillStatus: string
  prefillAvailable: number
  prefillMissing: number
  blockingChecks: string[]
  recommendedChecks: string[]
  dataSources: string[]
  updatedAt: string
  tags: string[]
  requiredVariables: TemplateVariableMeta[]
  href: string
  primaryActionLabel: string
  detailHref: string
}

export type StudioStampPreview = {
  lines: Array<{ text: string; size: number; bold: boolean }>
  text: string
  scope: Record<string, boolean>
}

export type TemplateAttiPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: TemplateAttiRecord[]
  studioStamp: StudioStampPreview
  actions: AdminAction[]
  forms: []
  warnings: AdminWarning[]
}

export const emptyTemplateAttiPage: TemplateAttiPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: [],
  studioStamp: { lines: [], text: '', scope: {} },
  actions: [],
  forms: [],
  warnings: [],
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

function tone(value: unknown): AdminTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AdminTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  return href.startsWith('/') && href !== '#' ? href : fallback
}

function normaliseMetric(input: unknown): AdminMetric {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: text(item.label) || 'Metrica',
    value: scalar(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): AdminSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'distribution',
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

function normaliseAction(input: unknown): AdminAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: safeHref(item.href, '/template-atti'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): AdminWarning {
  const item = asRecord(input)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso tecnico disponibile.',
  }
}

function normaliseVariable(input: unknown): TemplateVariableMeta {
  const item = asRecord(input)
  return {
    name: text(item.name) || text(item.label) || 'variabile',
    label: text(item.label) || text(item.name) || 'Variabile',
    kind: text(item.kind) || 'metadato',
    source: text(item.source) || 'metadata',
  }
}

function normaliseRecord(input: unknown): TemplateAttiRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'template',
    kind: text(item.kind) || 'catalogo',
    title: text(item.title) || 'Template',
    subtitle: text(item.subtitle),
    description: text(item.description),
    category: text(item.category),
    matter: text(item.matter),
    area: text(item.area),
    branch: text(item.branch),
    channel: text(item.channel),
    portal: text(item.portal),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    complianceLabel: text(item.complianceLabel),
    cartabiaState: text(item.cartabiaState),
    cartabiaLabel: text(item.cartabiaLabel),
    processArea: text(item.processArea),
    requiresLawyerReview: item.requiresLawyerReview === true,
    prefillStatus: text(item.prefillStatus),
    prefillAvailable: Number(item.prefillAvailable || 0),
    prefillMissing: Number(item.prefillMissing || 0),
    blockingChecks: list(item.blockingChecks).map((value) => text(value)).filter(Boolean),
    recommendedChecks: list(item.recommendedChecks).map((value) => text(value)).filter(Boolean),
    dataSources: list(item.dataSources).map((value) => text(value)).filter(Boolean),
    updatedAt: text(item.updatedAt),
    tags: list(item.tags).map((tag) => text(tag)).filter(Boolean),
    requiredVariables: list(item.requiredVariables).map(normaliseVariable).filter((variable) => variable.name),
    href: safeHref(item.href, '/template-atti/catalogo'),
    primaryActionLabel: text(item.primaryActionLabel) || 'Compila con dati IUSENTRA',
    detailHref: safeHref(item.detailHref, ''),
  }
}

function normaliseStudioStamp(input: unknown): StudioStampPreview {
  const item = asRecord(input)
  return {
    lines: list(item.lines).map((lineInput) => {
      const line = asRecord(lineInput)
      return {
        text: text(line.text),
        size: Number(line.size || 9),
        bold: line.bold === true,
      }
    }).filter((line) => line.text),
    text: text(item.text),
    scope: asRecord(item.scope) as Record<string, boolean>,
  }
}

function normalisePage(input: unknown): TemplateAttiPageData {
  const page = asRecord(input)
  const contracts = asRecord(page.contracts)
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'none',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    studioStamp: normaliseStudioStamp(page.studioStamp),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getTemplateAttiPage(): Promise<TemplateAttiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/template-atti', emptyTemplateAttiPage)
  return normalisePage(payload)
}

export async function getTemplateAttiCatalogoPage(): Promise<TemplateAttiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/template-atti/catalogo', emptyTemplateAttiPage)
  return normalisePage(payload)
}
