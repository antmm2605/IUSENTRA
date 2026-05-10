import { apiJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'
import type { AdminTone } from './utentiData'

export type ReactOperationalContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  operational: boolean
  sensitive_settings?: string
  builder?: string
  publishing?: string
  notifications?: string
  automation?: string
  secrets_exposed?: boolean
  legacy_contract?: string
}

export type WarningItem = {
  code: string
  message: string
}

export type RouteAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: AdminTone
  protected?: boolean
}

export type OperationalModule = {
  id: string
  label: string
  href: string
  area: string
  status: string
  tone: AdminTone
  note: string
}

export type LegacyModule = OperationalModule

export type SystemHealth = {
  id: string
  label: string
  status: string
  tone: AdminTone
  note: string
  value: string | number
}

export type SecuritySummary = {
  canRead?: boolean
  canWriteUsers?: boolean
  canReadAudit?: boolean
  canConfigureAdmin?: boolean
  activeAccounts?: number
  inactiveAccounts?: number
  twoFactorEnabled?: number
  permissionOverrides?: number
  status?: string
  tone?: AdminTone
}

export type StudioProfile = {
  id: string
  username: string
  label: string
  role: string
  active: boolean
  permissions: Record<string, boolean>
}

export type StudioMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type StudioPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: ReactOperationalContract
  studio: {
    name: string
    public_site: Record<string, unknown>
  }
  session: StudioProfile
  modules: OperationalModule[]
  operational_routes: OperationalModule[]
  legacy_routes: LegacyModule[]
  health: SystemHealth[]
  metrics: StudioMetric[]
  actions: RouteAction[]
  warnings: WarningItem[]
}

export const emptyStudioPage: StudioPageData = {
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
  studio: {
    name: '',
    public_site: {},
  },
  session: {
    id: '',
    username: '',
    label: '',
    role: '',
    active: false,
    permissions: {},
  },
  modules: [],
  operational_routes: [],
  legacy_routes: [],
  health: [],
  metrics: [],
  actions: [],
  warnings: [],
}

const SENSITIVE_KEY = /(password|pwd|api[_-]?key|access[_-]?token|refresh[_-]?token|oauth[_-]?token|password[_-]?hash|provider[_-]?secret|webhook[_-]?secret|stack[_-]?trace|traceback|absolute[_-]?path|full[_-]?path)/i

export function sanitizePayload(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizePayload)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !SENSITIVE_KEY.test(key))
      .map(([key, entry]) => [key, sanitizePayload(entry)]),
  )
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
  return sanitizeDisplayText(text(value, fallback))
}

function bool(value: unknown): boolean {
  return value === true
}

function number(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function value(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

export function tone(value: unknown): AdminTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AdminTone
    : 'neutral'
}

export function buttonTone(value: AdminTone): 'primary' | 'neutral' | 'danger' | 'success' | 'warning' {
  return value === 'info' ? 'neutral' : value
}

function normaliseContract(raw: unknown): ReactOperationalContract {
  const item = asRecord(raw)
  return {
    mock_fallback: bool(item.mock_fallback),
    writes: text(item.writes) || 'none',
    route_owner: text(item.route_owner) || 'react_shell',
    operational: item.operational === false ? false : true,
    sensitive_settings: text(item.sensitive_settings),
    builder: text(item.builder),
    publishing: text(item.publishing),
    notifications: text(item.notifications),
    automation: text(item.automation),
    secrets_exposed: bool(item.secrets_exposed),
    legacy_contract: text(item.legacy_contract),
  }
}

function normaliseMetric(raw: unknown): StudioMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
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

function normaliseHealth(raw: unknown): SystemHealth {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'salute',
    label: display(item.label) || 'Salute sistema',
    status: display(item.status) || 'non indicato',
    tone: tone(item.tone),
    note: display(item.note),
    value: value(item.value),
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

function normaliseProfile(raw: unknown): StudioProfile {
  const item = asRecord(raw)
  const permissions = asRecord(item.permissions)
  return {
    id: text(item.id),
    username: text(item.username),
    label: display(item.label) || text(item.username),
    role: display(item.role),
    active: bool(item.active),
    permissions: Object.fromEntries(Object.entries(permissions).map(([key, entry]) => [key, bool(entry)])),
  }
}

function normalisePage(raw: unknown): StudioPageData {
  const page = asRecord(sanitizePayload(raw))
  const studio = asRecord(page.studio)
  return {
    ok: bool(page.ok),
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContract(page.contracts),
    studio: {
      name: text(studio.name) || 'Studio',
      public_site: asRecord(studio.public_site),
    },
    session: normaliseProfile(page.session),
    modules: list(page.modules).map(normaliseModule).filter((item) => item.href),
    operational_routes: list(page.operational_routes).map(normaliseModule).filter((item) => item.href),
    legacy_routes: list(page.legacy_routes).map(normaliseModule).filter((item) => item.href),
    health: list(page.health).map(normaliseHealth),
    metrics: list(page.metrics).map(normaliseMetric),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getStudioPage(): Promise<StudioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/studio', emptyStudioPage)
  return normalisePage(payload)
}
