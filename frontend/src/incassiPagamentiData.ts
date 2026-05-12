import { apiJson, apiPostJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type PaymentRow = {
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
  paymentHref: string
}

export type ReceiptRow = {
  id: string
  invoiceNumber: string
  customerName: string
  amountDisplay: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  paidAt: string
  method: string
}

export type PaymentProviderStatus = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type PaymentStatus = {
  value: string
  label: string
}

export type IncassiPagamentiPermissions = {
  canRegisterPayment: boolean
  canUpdateStatus: boolean
  canLinkInvoice: boolean
  canGeneratePaymentLink: boolean
  canOpenProviderSettings: boolean
  links: AdminAction[]
}

export type RegisterIncassoPayload = {
  id_parcella: string
  id_pagamento?: string
  metodo_pagamento: string
  data_pagamento: string
  note?: string
}

export type UpdatePagamentoStatusPayload = {
  stato: string
  metodo_pagamento?: string
  note?: string
}

export type LinkPagamentoInvoicePayload = {
  id_parcella: string
}

export type PaymentMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: Record<string, unknown> | null
}

export type IncassiPagamentiPageData = {
  ok?: boolean
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  payments: PaymentRow[]
  receipts: ReceiptRow[]
  providers: PaymentProviderStatus[]
  statuses: PaymentStatus[]
  actions: IncassiPagamentiPermissions
  records: PaymentRow[]
  warnings: AdminWarning[]
}

export type IncassoPagamentoRecord = PaymentRow

const emptyActions: IncassiPagamentiPermissions = {
  canRegisterPayment: false,
  canUpdateStatus: false,
  canLinkInvoice: false,
  canGeneratePaymentLink: false,
  canOpenProviderSettings: false,
  links: [],
}

export const emptyIncassiPagamentiPage: IncassiPagamentiPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  payments: [],
  receipts: [],
  providers: [],
  statuses: [],
  actions: emptyActions,
  records: [],
  warnings: [],
}

const emptyMutation: PaymentMutationResult = {
  ok: false,
  message: 'Operazione non completata.',
  errors: {},
  item: null,
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function currentSearch(): string {
  if (typeof window === 'undefined') return ''
  return window.location.search || ''
}

function withCurrentSearch(path: string): string {
  const search = currentSearch()
  return search ? `${path}${search}` : path
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function value(value: unknown): string | number {
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
    message: text(item.message) || 'Avviso disponibile.',
  }
}

function normalisePayment(raw: unknown): PaymentRow {
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
    paymentHref: safeHref(item.paymentHref),
  }
}

function normaliseReceipt(raw: unknown): ReceiptRow {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    invoiceNumber: text(item.invoiceNumber),
    customerName: text(item.customerName) || 'Cliente non indicato',
    amountDisplay: text(item.amountDisplay),
    state: text(item.state),
    stateLabel: text(item.stateLabel) || 'Pagata',
    stateTone: tone(item.stateTone),
    paidAt: text(item.paidAt),
    method: text(item.method),
  }
}

function normaliseProvider(raw: unknown): PaymentProviderStatus {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'canale',
    label: text(item.label) || 'Canale',
    value: value(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseActions(raw: unknown): IncassiPagamentiPermissions {
  const item = asRecord(raw)
  return {
    canRegisterPayment: bool(item.canRegisterPayment),
    canUpdateStatus: bool(item.canUpdateStatus),
    canLinkInvoice: bool(item.canLinkInvoice),
    canGeneratePaymentLink: bool(item.canGeneratePaymentLink),
    canOpenProviderSettings: bool(item.canOpenProviderSettings),
    links: list(item.links).map(normaliseAction).filter((action) => action.href),
  }
}

function normaliseStatus(raw: unknown): PaymentStatus {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: text(item.label) || text(item.value),
  }
}

function normalisePage(raw: unknown): IncassiPagamentiPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const payments = list(page.payments).map(normalisePayment).filter((record) => record.id || record.invoiceId)
  const records = payments.length ? payments : list(page.records).map(normalisePayment).filter((record) => record.id || record.invoiceId)
  return {
    ok: page.ok === true,
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'json_api',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    payments: records,
    receipts: list(page.receipts).map(normaliseReceipt).filter((record) => record.id),
    providers: list(page.providers).map(normaliseProvider),
    statuses: list(page.statuses).map(normaliseStatus).filter((status) => status.value),
    actions: normaliseActions(page.actions),
    records,
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseMutation(raw: unknown): PaymentMutationResult {
  const item = asRecord(raw)
  return {
    ok: item.ok === true,
    message: text(item.message) || (item.ok === true ? 'Operazione completata.' : 'Operazione non completata.'),
    errors: asRecord(item.errors) as Record<string, string>,
    item: Object.keys(asRecord(item.item)).length ? asRecord(item.item) : null,
  }
}

export async function getIncassiPagamentiPage(): Promise<IncassiPagamentiPageData> {
  const payload = await apiJson<unknown>(withCurrentSearch('/api/v1/ui/incassi-pagamenti'), emptyIncassiPagamentiPage)
  return normalisePage(payload)
}

export async function registerIncasso(payload: RegisterIncassoPayload): Promise<PaymentMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>('/api/v1/ui/incassi-pagamenti/incasso', payload, emptyMutation))
}

export async function updatePagamentoStatus(idPagamento: string, payload: UpdatePagamentoStatusPayload): Promise<PaymentMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>(`/api/v1/ui/incassi-pagamenti/${encodeURIComponent(idPagamento)}/stato`, payload, emptyMutation))
}

export async function linkPagamentoInvoice(idPagamento: string, payload: LinkPagamentoInvoicePayload): Promise<PaymentMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>(`/api/v1/ui/incassi-pagamenti/${encodeURIComponent(idPagamento)}/collega`, payload, emptyMutation))
}

export async function createOrGetPaymentLink(idPagamento: string, payload: { id_parcella: string }): Promise<PaymentMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>(`/api/v1/ui/incassi-pagamenti/${encodeURIComponent(idPagamento || 'nuovo')}/link-pagamento`, payload, emptyMutation))
}
