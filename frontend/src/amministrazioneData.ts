import { apiJson } from './lib/apiClient'
import {
  sanitizePayload,
  tone,
  type LegacyModule,
  type OperationalModule,
  type ReactOperationalContract,
  type RouteAction,
  type SecuritySummary,
  type WarningItem,
} from './studioData'
import type { AdminTone } from './utentiData'
import { sanitizeDisplayText } from './displayText'

export type AdminHubMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type AdminHubSectionItem = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type AdminHubSection = {
  id: string
  title: string
  kind: string
  items: AdminHubSectionItem[]
  emptyMessage: string
}

export type AmministrazionePageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: ReactOperationalContract
  security: SecuritySummary
  users: Record<string, unknown>
  profiles: Record<string, unknown>
  audit: Record<string, unknown>
  database: Record<string, unknown>
  modules: OperationalModule[]
  operational_routes: OperationalModule[]
  legacy_routes: LegacyModule[]
  metrics: AdminHubMetric[]
  sections: AdminHubSection[]
  actions: RouteAction[]
  warnings: WarningItem[]
}

export const emptyAmministrazionePage: AmministrazionePageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
    operational: true,
    sensitive_settings: 'legacy_protected',
    secrets_exposed: false,
  },
  security: {},
  users: {},
  profiles: {},
  audit: {},
  database: {},
  modules: [],
  operational_routes: [],
  legacy_routes: [],
  metrics: [],
  sections: [],
  actions: [],
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

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback).replace(/[_-]+/g, ' '))
}

function bool(value: unknown): boolean {
  return value === true
}

function value(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim().replace(/[_-]+/g, ' '))
  return ''
}

function normaliseContract(raw: unknown): ReactOperationalContract {
  const item = asRecord(raw)
  return {
    mock_fallback: bool(item.mock_fallback),
    writes: display(item.writes) || 'none',
    route_owner: display(item.route_owner) || 'pagina operativa',
    operational: item.operational === false ? false : true,
    sensitive_settings: display(item.sensitive_settings),
    secrets_exposed: bool(item.secrets_exposed),
    legacy_contract: display(item.legacy_contract),
  }
}

function normaliseMetric(raw: unknown): AdminHubMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AdminHubSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'distribuzione',
    items: list(item.items).map((rawItem) => {
      const entry = asRecord(rawItem)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: display(entry.label) || 'Voce',
        value: value(entry.value),
        note: display(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseModule(raw: unknown): OperationalModule {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'modulo',
    label: display(item.label) || 'Modulo',
    href: text(item.href),
    area: display(item.area),
    status: display(item.status) || 'stato non indicato',
    tone: tone(item.tone),
    note: display(item.note),
  }
}

function normaliseAction(raw: unknown): RouteAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: text(item.href),
    method: 'GET',
    tone: tone(item.tone),
    protected: bool(item.protected),
  }
}

function normaliseWarning(raw: unknown): WarningItem {
  const item = asRecord(raw)
  return {
    code: display(item.code) || 'avviso',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseSecurity(raw: unknown): SecuritySummary {
  const item = asRecord(raw)
  return {
    canRead: bool(item.canRead),
    canWriteUsers: bool(item.canWriteUsers),
    canReadAudit: bool(item.canReadAudit),
    canConfigureAdmin: bool(item.canConfigureAdmin),
    activeAccounts: typeof item.activeAccounts === 'number' ? item.activeAccounts : 0,
    inactiveAccounts: typeof item.inactiveAccounts === 'number' ? item.inactiveAccounts : 0,
    twoFactorEnabled: typeof item.twoFactorEnabled === 'number' ? item.twoFactorEnabled : 0,
    permissionOverrides: typeof item.permissionOverrides === 'number' ? item.permissionOverrides : 0,
    status: display(item.status),
    tone: tone(item.tone),
  }
}

function normalisePage(raw: unknown): AmministrazionePageData {
  const page = asRecord(sanitizePayload(raw))
  return {
    ok: bool(page.ok),
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContract(page.contracts),
    security: normaliseSecurity(page.security),
    users: asRecord(page.users),
    profiles: asRecord(page.profiles),
    audit: asRecord(page.audit),
    database: asRecord(page.database),
    modules: list(page.modules).map(normaliseModule).filter((item) => item.href),
    operational_routes: list(page.operational_routes).map(normaliseModule).filter((item) => item.href),
    legacy_routes: list(page.legacy_routes).map(normaliseModule).filter((item) => item.href),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getAmministrazionePage(): Promise<AmministrazionePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/amministrazione', emptyAmministrazionePage)
  return normalisePage(payload)
}
