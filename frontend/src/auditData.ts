import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type AuditTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type AuditContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  legacy_contract?: string
}

export type AuditMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AuditTone
}

export type AuditItem = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AuditTone
}

export type AuditSection = {
  id: string
  title: string
  kind: string
  items: AuditItem[]
  emptyMessage: string
}

export type AuditRecord = {
  id: string
  timestamp: string
  userId: string
  username: string
  action: string
  resourceType: string
  resourceId: string
  details: string
  ip: string
  result: string
  resultTone: AuditTone
  resourceState: string
  resourceTone: AuditTone
  resourceLabel: string
  resourceNote: string
  resourceUrl: string
  resourceBadgeLabel: string
  payloadSanitized: boolean
}

export type AuditEventDetail = AuditRecord & {
  payload: Record<string, unknown>
  rawAvailable: boolean
}

export type AuditAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: AuditTone
}

export type AuditPermissions = {
  canMarkRead: boolean
  canResolve: boolean
  canAddNote: boolean
  canExport: boolean
  links: AuditAction[]
}

export type AuditWarning = {
  code: string
  message: string
}

export type AuditPageData = {
  ok?: boolean
  source: string
  generated_at: string
  contracts: AuditContract
  metrics: AuditMetric[]
  sections: AuditSection[]
  events: AuditRecord[]
  filters: Record<string, string>
  records: AuditRecord[]
  actions: AuditPermissions
  warnings: AuditWarning[]
}

export type AuditMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: AuditEventDetail | null
}

const AUDIT_ENDPOINT = '/api/v1/ui/audit'
const REGISTRO_ATTIVITA_ENDPOINT = '/api/v1/ui/registro-attivita'

const emptyActions: AuditPermissions = {
  canMarkRead: false,
  canResolve: false,
  canAddNote: false,
  canExport: false,
  links: [],
}

export const emptyAuditPage: AuditPageData = {
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
  events: [],
  filters: {},
  records: [],
  actions: emptyActions,
  warnings: [],
}

const emptyMutation: AuditMutationResult = {
  ok: false,
  message: 'Operazione audit non completata.',
  errors: {},
  item: null,
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function value(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function bool(value: unknown): boolean {
  return value === true
}

function tone(value: unknown): AuditTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AuditTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  return href.startsWith('/') && href !== '#' ? href : fallback
}

function normaliseMetric(raw: unknown): AuditMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseItem(raw: unknown): AuditItem {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: display(item.label) || 'Voce',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AuditSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'distribuzione',
    items: list(item.items).map(normaliseItem),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseRecord(raw: unknown): AuditRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.timestamp) || 'evento',
    timestamp: text(item.timestamp),
    userId: text(item.userId),
    username: display(item.username) || 'Utente non indicato',
    action: display(item.action) || 'azione non indicata',
    resourceType: display(item.resourceType),
    resourceId: text(item.resourceId),
    details: display(item.details),
    ip: text(item.ip),
    result: display(item.result) || 'OK',
    resultTone: tone(item.resultTone),
    resourceState: display(item.resourceState),
    resourceTone: tone(item.resourceTone),
    resourceLabel: display(item.resourceLabel),
    resourceNote: display(item.resourceNote),
    resourceUrl: safeHref(item.resourceUrl),
    resourceBadgeLabel: display(item.resourceBadgeLabel),
    payloadSanitized: item.payloadSanitized !== false,
  }
}

function normaliseDetail(raw: unknown): AuditEventDetail | null {
  const item = asRecord(raw)
  if (!Object.keys(item).length) return null
  return {
    ...normaliseRecord(item),
    payload: asRecord(item.payload),
    rawAvailable: bool(item.rawAvailable),
  }
}

function normaliseAction(raw: unknown): AuditAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: safeHref(item.href, '/audit'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseActions(raw: unknown): AuditPermissions {
  const item = asRecord(raw)
  return {
    canMarkRead: bool(item.canMarkRead),
    canResolve: bool(item.canResolve),
    canAddNote: bool(item.canAddNote),
    canExport: bool(item.canExport),
    links: list(item.links).map(normaliseAction).filter((action) => action.href),
  }
}

function normaliseWarning(raw: unknown): AuditWarning {
  const item = asRecord(raw)
  return {
    code: display(item.code) || 'avviso',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normalisePage(raw: unknown): AuditPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const events = list(page.events).map(normaliseRecord)
  const records = events.length ? events : list(page.records).map(normaliseRecord)
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
    events: records,
    filters: Object.fromEntries(Object.entries(asRecord(page.filters)).map(([key, val]) => [key, text(val)])),
    records,
    actions: normaliseActions(page.actions),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseMutation(raw: unknown): AuditMutationResult {
  const item = asRecord(raw)
  return {
    ok: item.ok === true,
    message: display(item.message) || (item.ok === true ? 'Operazione completata.' : 'Operazione non completata.'),
    errors: Object.fromEntries(Object.entries(asRecord(item.errors)).map(([key, rawValue]) => [key, display(rawValue)])),
    item: normaliseDetail(item.item),
  }
}

export async function getAuditPage(): Promise<AuditPageData> {
  const payload = await apiJson<unknown>(AUDIT_ENDPOINT, emptyAuditPage)
  return normalisePage(payload)
}

export async function getRegistroAttivitaPage(): Promise<AuditPageData> {
  const payload = await apiJson<unknown>(REGISTRO_ATTIVITA_ENDPOINT, emptyAuditPage)
  return normalisePage(payload)
}

export async function getAuditEventDetail(idEvento: string): Promise<AuditMutationResult> {
  return normaliseMutation(await apiJson<unknown>(`${AUDIT_ENDPOINT}/${encodeURIComponent(idEvento)}`, emptyMutation))
}

export async function markAuditEventRead(idEvento: string): Promise<AuditMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>(`${AUDIT_ENDPOINT}/${encodeURIComponent(idEvento)}/letto`, {}, emptyMutation))
}

export async function resolveAuditEvent(idEvento: string): Promise<AuditMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>(`${AUDIT_ENDPOINT}/${encodeURIComponent(idEvento)}/risolto`, {}, emptyMutation))
}

export async function addAuditEventNote(idEvento: string, note: string): Promise<AuditMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>(`${AUDIT_ENDPOINT}/${encodeURIComponent(idEvento)}/nota`, { note }, emptyMutation))
}
