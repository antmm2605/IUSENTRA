import { apiJson } from './lib/apiClient'

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
}

export type AuditAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: AuditTone
}

export type AuditWarning = {
  code: string
  message: string
}

export type AuditPageData = {
  source: string
  generated_at: string
  contracts: AuditContract
  metrics: AuditMetric[]
  sections: AuditSection[]
  records: AuditRecord[]
  actions: AuditAction[]
  warnings: AuditWarning[]
}

const AUDIT_ENDPOINT = '/api/v1/ui/audit'
const REGISTRO_ATTIVITA_ENDPOINT = '/api/v1/ui/registro-attivita'

export const emptyAuditPage: AuditPageData = {
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
  actions: [],
  warnings: [],
}

function currentEndpoint(): string {
  if (typeof window === 'undefined') return AUDIT_ENDPOINT
  return window.location.pathname.toLowerCase().includes('registro-attivita')
    ? REGISTRO_ATTIVITA_ENDPOINT
    : AUDIT_ENDPOINT
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function value(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
  return ''
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function tone(value: unknown): AuditTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AuditTone
    : 'neutral'
}

function normaliseMetric(raw: unknown): AuditMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: text(item.label) || 'Metrica',
    value: value(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseItem(raw: unknown): AuditItem {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: text(item.label) || 'Voce',
    value: value(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AuditSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'distribution',
    items: list(item.items).map(normaliseItem),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseRecord(raw: unknown): AuditRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.timestamp) || 'evento',
    timestamp: text(item.timestamp),
    userId: text(item.userId),
    username: text(item.username) || 'Utente non indicato',
    action: text(item.action) || 'azione non indicata',
    resourceType: text(item.resourceType),
    resourceId: text(item.resourceId),
    details: text(item.details),
    ip: text(item.ip),
    result: text(item.result) || 'OK',
    resultTone: tone(item.resultTone),
    resourceState: text(item.resourceState),
    resourceTone: tone(item.resourceTone),
    resourceLabel: text(item.resourceLabel),
    resourceNote: text(item.resourceNote),
    resourceUrl: text(item.resourceUrl),
    resourceBadgeLabel: text(item.resourceBadgeLabel),
  }
}

function normaliseAction(raw: unknown): AuditAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: text(item.href) || '/audit',
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): AuditWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso tecnico disponibile.',
  }
}

function normalisePage(raw: unknown): AuditPageData {
  const page = asRecord(raw)
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
    records: list(page.records).map(normaliseRecord),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.method === 'GET' && action.href),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getAuditPage(): Promise<AuditPageData> {
  const payload = await apiJson<unknown>(currentEndpoint(), emptyAuditPage)
  return normalisePage(payload)
}
