import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'
import type { LegacyPostField } from './ui/LegacyPostForm'

export type TariffarioRecord = {
  id: string
  title: string
  subtitle: string
  meta: string
  stateLabel: string
  stateTone: AdminTone
  href: string
}

export type TariffarioFormDefinition = {
  id: string
  title: string
  description: string
  action: string
  method: 'POST'
  submitLabel: string
  enabled: boolean
  fields: LegacyPostField[]
}

export type TariffarioPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: TariffarioRecord[]
  actions: AdminAction[]
  forms: TariffarioFormDefinition[]
  warnings: AdminWarning[]
}

export const emptyTariffarioPage: TariffarioPageData = {
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

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
  return ''
}

function bool(value: unknown): boolean {
  return value === true
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
    href: safeHref(item.href, '/tariffario'),
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

function normaliseRecord(raw: unknown): TariffarioRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'record',
    title: text(item.title) || 'Voce tariffaria',
    subtitle: text(item.subtitle),
    meta: text(item.meta),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    href: safeHref(item.href, '/tariffario'),
  }
}

function normaliseField(raw: unknown): LegacyPostField | null {
  const item = asRecord(raw)
  const name = text(item.name)
  const allowedNames = new Set([
    'materia',
    'regola_tariffaria',
    'grado',
    'valore',
    'complessita',
    'spese_generali',
    'perc_spese_generali',
    'bonus_telematico',
  ])
  if (!allowedNames.has(name)) return null
  const rawType = text(item.type)
  const fieldType: LegacyPostField['type'] =
    rawType === 'select' || rawType === 'hidden' || rawType === 'checkbox' ? rawType : 'text'
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

function normaliseForm(raw: unknown): TariffarioFormDefinition {
  const item = asRecord(raw)
  return {
    id: text(item.id) || 'tariffario_form',
    title: text(item.title) || 'Form tariffario',
    description: text(item.description),
    action: safeHref(item.action, '/tariffario'),
    method: 'POST',
    submitLabel: text(item.submitLabel) || 'Invia',
    enabled: item.enabled !== false,
    fields: list(item.fields).map(normaliseField).filter((field): field is LegacyPostField => Boolean(field)),
  }
}

function normalisePage(raw: unknown): TariffarioPageData {
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
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: list(page.forms).map(normaliseForm).filter((form) => form.action),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getTariffarioPage(): Promise<TariffarioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/tariffario', emptyTariffarioPage)
  return normalisePage(payload)
}
