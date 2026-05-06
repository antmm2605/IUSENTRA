import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'
import type { LegacyPostField } from './ui/LegacyPostForm'

export type PreventiviRecordKind = 'preventivo' | 'conferimento'

export type PreventiviRecord = {
  id: string
  kind: PreventiviRecordKind
  number: string
  subject: string
  customerName: string
  caseTitle: string
  amountDisplay: string
  issuedAt: string
  dueAt: string
  engagementAt: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  detailHref: string
  wizardHref: string
  legacyHref: string
}

export type PreventiviFormDefaults = {
  subject: string
  issuedAt: string
  dueAt: string
  engagementAt: string
  lawyer: string
  amount: string
  hourly: string
  note: string
  lineDescription: string
  lineAmount: string
  lineType: string
  withFund: boolean
  withVat: boolean
  practiceKind: string
  feeKind: string
  value: string
  complexity: string
  barNumber: string
  barCouncil: string
  openCaseGuided: boolean
  art13Notice: boolean
  adrClause: boolean
}

export type PreventiviFormDefinition = {
  id: string
  title: string
  description: string
  action: string
  method: 'POST'
  submitLabel: string
  enabled: boolean
  fields: LegacyPostField[]
  defaults: PreventiviFormDefaults
}

export type PreventiviPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: PreventiviRecord[]
  actions: AdminAction[]
  forms: PreventiviFormDefinition[]
  warnings: AdminWarning[]
}

const emptyDefaults: PreventiviFormDefaults = {
  subject: '',
  issuedAt: '',
  dueAt: '',
  engagementAt: '',
  lawyer: '',
  amount: '',
  hourly: '',
  note: '',
  lineDescription: '',
  lineAmount: '',
  lineType: 'ONORARIO',
  withFund: true,
  withVat: true,
  practiceKind: '',
  feeKind: '',
  value: '',
  complexity: '',
  barNumber: '',
  barCouncil: '',
  openCaseGuided: false,
  art13Notice: true,
  adrClause: true,
}

export const emptyPreventiviPage: PreventiviPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'legacy_routes',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: [],
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

function bool(value: unknown): boolean {
  return value === true
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

function normaliseMetric(raw: unknown): AdminMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: text(item.label) || 'Metrica',
    value: scalar(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AdminSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'distribution',
    items: list(item.items).map((rawItem) => {
      const entry = asRecord(rawItem)
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

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: safeHref(item.href, '/preventivi'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): AdminWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso tecnico disponibile.',
  }
}

function normaliseKind(value: unknown): PreventiviRecordKind {
  return text(value) === 'conferimento' ? 'conferimento' : 'preventivo'
}

function normaliseRecord(raw: unknown): PreventiviRecord {
  const item = asRecord(raw)
  const kind = normaliseKind(item.kind)
  return {
    id: text(item.id),
    kind,
    number: text(item.number),
    subject: text(item.subject) || 'Oggetto non indicato',
    customerName: text(item.customerName) || 'Cliente non indicato',
    caseTitle: text(item.caseTitle),
    amountDisplay: text(item.amountDisplay),
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    engagementAt: text(item.engagementAt),
    state: text(item.state),
    stateLabel: text(item.stateLabel) || text(item.state) || 'Stato non indicato',
    stateTone: tone(item.stateTone),
    detailHref: safeHref(item.detailHref),
    wizardHref: safeHref(item.wizardHref),
    legacyHref: safeHref(item.legacyHref),
  }
}

function normaliseField(raw: unknown): LegacyPostField | null {
  const item = asRecord(raw)
  const name = text(item.name)
  const allowedNames = new Set([
    'id_cliente',
    'id_fascicolo',
    'id_preventivo',
    'from_cliente',
    'id_pratica',
    'area_pratica',
  ])
  if (!allowedNames.has(name)) return null
  const rawType = text(item.type)
  const fieldType: LegacyPostField['type'] = rawType === 'select' || rawType === 'hidden' ? rawType : 'text'
  return {
    name,
    label: text(item.label) || name,
    type: fieldType,
    required: bool(item.required),
    value: text(item.value),
    options: list(item.options).map((option) => {
      const entry = asRecord(option)
      return {
        value: text(entry.value),
        label: text(entry.label) || text(entry.value),
        description: text(entry.description),
        enabled: entry.enabled !== false,
      }
    }),
  }
}

function normaliseDefaults(raw: unknown): PreventiviFormDefaults {
  const item = asRecord(raw)
  return {
    subject: text(item.subject),
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    engagementAt: text(item.engagementAt),
    lawyer: text(item.lawyer),
    amount: text(item.amount),
    hourly: text(item.hourly),
    note: text(item.note),
    lineDescription: text(item.lineDescription),
    lineAmount: text(item.lineAmount),
    lineType: text(item.lineType) || 'ONORARIO',
    withFund: item.withFund === false ? false : true,
    withVat: item.withVat === false ? false : true,
    practiceKind: text(item.practiceKind),
    feeKind: text(item.feeKind),
    value: text(item.value),
    complexity: text(item.complexity),
    barNumber: text(item.barNumber),
    barCouncil: text(item.barCouncil),
    openCaseGuided: bool(item.openCaseGuided),
    art13Notice: item.art13Notice === false ? false : true,
    adrClause: item.adrClause === false ? false : true,
  }
}

function normaliseForm(raw: unknown): PreventiviFormDefinition {
  const item = asRecord(raw)
  const id = text(item.id) || 'nuovo_preventivo'
  const defaultAction = id === 'nuovo_conferimento' ? '/preventivi/conferimento/nuovo' : '/preventivi/nuovo'
  return {
    id,
    title: text(item.title) || 'Form mandato',
    description: text(item.description),
    action: safeHref(item.action, defaultAction),
    method: 'POST',
    submitLabel: text(item.submitLabel) || 'Salva',
    enabled: item.enabled !== false,
    fields: list(item.fields).map(normaliseField).filter((field): field is LegacyPostField => Boolean(field)),
    defaults: { ...emptyDefaults, ...normaliseDefaults(item.defaults) },
  }
}

function normalisePage(raw: unknown): PreventiviPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'legacy_routes',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id || record.number),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: list(page.forms).map(normaliseForm),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getPreventiviPage(): Promise<PreventiviPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi', emptyPreventiviPage)
  return normalisePage(payload)
}

export async function getNuovoPreventivoPage(): Promise<PreventiviPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi/nuovo', emptyPreventiviPage)
  return normalisePage(payload)
}

export async function getNuovoConferimentoPage(): Promise<PreventiviPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi/conferimento/nuovo', emptyPreventiviPage)
  return normalisePage(payload)
}
