import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'
import type { LegacyPostField } from './ui/LegacyPostForm'

export type FatturazioneRecord = {
  id: string
  number: string
  customerName: string
  caseTitle: string
  amountDisplay: string
  issuedAt: string
  dueAt: string
  paidAt: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  paymentMethod: string
  detailHref: string
  pdfHref: string
  xmlHref: string
}

export type FatturazioneFormDefaults = {
  issuedAt: string
  dueAt: string
  description: string
  quantity: string
  unitAmount: string
  notes: string
  withFund: boolean
  withVat: boolean
  withWithholding: boolean
  withStamp: boolean
}

export type FatturazioneFormDefinition = {
  id: string
  title: string
  description: string
  action: string
  method: 'POST'
  submitLabel: string
  enabled: boolean
  fields: LegacyPostField[]
  defaults: FatturazioneFormDefaults
}

export type FatturazionePageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: FatturazioneRecord[]
  actions: AdminAction[]
  forms: FatturazioneFormDefinition[]
  warnings: AdminWarning[]
}

const emptyDefaults: FatturazioneFormDefaults = {
  issuedAt: '',
  dueAt: '',
  description: '',
  quantity: '1',
  unitAmount: '',
  notes: '',
  withFund: true,
  withVat: true,
  withWithholding: false,
  withStamp: false,
}

export const emptyFatturazionePage: FatturazionePageData = {
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

function value(value: unknown): string | number {
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
    value: value(item.value),
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
        value: value(entry.value),
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
    href: safeHref(item.href, '/fatturazione'),
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

function normaliseRecord(raw: unknown): FatturazioneRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    number: text(item.number),
    customerName: text(item.customerName) || 'Cliente non indicato',
    caseTitle: text(item.caseTitle),
    amountDisplay: text(item.amountDisplay),
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    paidAt: text(item.paidAt),
    state: text(item.state),
    stateLabel: text(item.stateLabel) || text(item.state) || 'Stato non indicato',
    stateTone: tone(item.stateTone),
    paymentMethod: text(item.paymentMethod),
    detailHref: safeHref(item.detailHref),
    pdfHref: safeHref(item.pdfHref),
    xmlHref: safeHref(item.xmlHref),
  }
}

function normaliseField(raw: unknown): LegacyPostField | null {
  const item = asRecord(raw)
  const name = text(item.name)
  const allowedNames = new Set([
    'id_cliente',
    'id_fascicolo',
    'from_cliente',
    'origine',
    'id_preventivo',
    'id_pratica',
    'area_pratica',
    'tipo_compenso',
    'tipo_procedimento',
    'valore_controversia',
    'complessita',
    'log_calcolo',
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

function normaliseDefaults(raw: unknown): FatturazioneFormDefaults {
  const item = asRecord(raw)
  return {
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    description: text(item.description),
    quantity: text(item.quantity) || '1',
    unitAmount: text(item.unitAmount),
    notes: text(item.notes),
    withFund: item.withFund === false ? false : true,
    withVat: item.withVat === false ? false : true,
    withWithholding: bool(item.withWithholding),
    withStamp: bool(item.withStamp),
  }
}

function normaliseForm(raw: unknown): FatturazioneFormDefinition {
  const item = asRecord(raw)
  return {
    id: text(item.id) || 'nuova_parcella',
    title: text(item.title) || 'Nuova parcella',
    description: text(item.description),
    action: safeHref(item.action, '/fatturazione/nuova'),
    method: 'POST',
    submitLabel: text(item.submitLabel) || 'Crea parcella',
    enabled: item.enabled !== false,
    fields: list(item.fields).map(normaliseField).filter((field): field is LegacyPostField => Boolean(field)),
    defaults: normaliseDefaults(item.defaults),
  }
}

function normalisePage(raw: unknown): FatturazionePageData {
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

export async function getFatturazionePage(): Promise<FatturazionePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/fatturazione', emptyFatturazionePage)
  return normalisePage(payload)
}

export async function getNuovaFatturaPage(): Promise<FatturazionePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/fatturazione/nuova', emptyFatturazionePage)
  return normalisePage(payload)
}
