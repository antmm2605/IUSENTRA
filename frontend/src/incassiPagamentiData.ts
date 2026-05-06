import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type IncassoPagamentoRecord = {
  id: string
  invoiceId: string
  invoiceNumber: string
  customerName: string
  amountDisplay: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  providerLabel: string
  createdAt: string
  dueAt: string
  paidAt: string
  invoiceHref: string
}

export type IncassiPagamentiPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: IncassoPagamentoRecord[]
  actions: AdminAction[]
  forms: []
  warnings: AdminWarning[]
}

export const emptyIncassiPagamentiPage: IncassiPagamentiPageData = {
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
    href: safeHref(item.href, '/incassi-pagamenti'),
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

function normaliseRecord(raw: unknown): IncassoPagamentoRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    invoiceId: text(item.invoiceId),
    invoiceNumber: text(item.invoiceNumber),
    customerName: text(item.customerName) || 'Cliente non indicato',
    amountDisplay: text(item.amountDisplay),
    state: text(item.state),
    stateLabel: text(item.stateLabel) || text(item.state) || 'Stato non indicato',
    stateTone: tone(item.stateTone),
    providerLabel: text(item.providerLabel) || 'non indicato',
    createdAt: text(item.createdAt),
    dueAt: text(item.dueAt),
    paidAt: text(item.paidAt),
    invoiceHref: safeHref(item.invoiceHref),
  }
}

function normalisePage(raw: unknown): IncassiPagamentiPageData {
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
    records: list(page.records).map(normaliseRecord).filter((record) => record.id || record.invoiceId),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getIncassiPagamentiPage(): Promise<IncassiPagamentiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/incassi-pagamenti', emptyIncassiPagamentiPage)
  return normalisePage(payload)
}
