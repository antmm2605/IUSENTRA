import { apiJson } from './lib/apiClient'
import type { LegacyPostField } from './ui/LegacyPostForm'

export type AdminTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type AdminContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  legacy_contract?: string
}

export type AdminMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type AdminSectionItem = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type AdminSection = {
  id: string
  title: string
  kind: string
  items: AdminSectionItem[]
  emptyMessage: string
}

export type UtenteRecord = {
  id: string
  username: string
  name: string
  email: string
  role: string
  roleLabel: string
  roleDescription: string
  roleTone: AdminTone
  active: boolean
  mustChangePassword: boolean
  lastAccess: string
  hasOverride: boolean
  extraPermissionsCount: number
  deniedPermissionsCount: number
  twoFactorEnabled: boolean
  editHref: string
  permissionsHref: string
}

export type AdminAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: AdminTone
}

export type LegacyFormDefinition = {
  id: string
  title: string
  description: string
  action: string
  method: 'POST'
  csrfField: string
  submitLabel: string
  enabled?: boolean
  fields: LegacyPostField[]
}

export type AdminWarning = {
  code: string
  message: string
}

export type RoleOption = {
  value: string
  label: string
  description: string
  tone: AdminTone
}

export type UtentiPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: UtenteRecord[]
  actions: AdminAction[]
  createEndpoint: string
  roles: RoleOption[]
  forms: unknown[]
  warnings: AdminWarning[]
}

export const emptyUtentiPage: UtentiPageData = {
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
  createEndpoint: '',
  roles: [],
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

function number(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
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

function normaliseSectionItem(raw: unknown): AdminSectionItem {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: text(item.label) || 'Voce',
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
    items: list(item.items).map(normaliseSectionItem),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseUser(raw: unknown): UtenteRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    username: text(item.username),
    name: text(item.name),
    email: text(item.email),
    role: text(item.role),
    roleLabel: text(item.roleLabel) || text(item.role),
    roleDescription: text(item.roleDescription),
    roleTone: tone(item.roleTone),
    active: bool(item.active),
    mustChangePassword: bool(item.mustChangePassword),
    lastAccess: text(item.lastAccess),
    hasOverride: bool(item.hasOverride),
    extraPermissionsCount: number(item.extraPermissionsCount),
    deniedPermissionsCount: number(item.deniedPermissionsCount),
    twoFactorEnabled: bool(item.twoFactorEnabled),
    editHref: text(item.editHref),
    permissionsHref: text(item.permissionsHref),
  }
}

function normaliseRole(raw: unknown): RoleOption {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: text(item.label) || text(item.value),
    description: text(item.description),
    tone: tone(item.tone),
  }
}

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: text(item.href) || '/utenti',
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

function normalisePage(raw: unknown): UtentiPageData {
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
    records: list(page.records).map(normaliseUser),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.method === 'GET' && action.href),
    createEndpoint: text(page.createEndpoint),
    roles: list(page.roles).map(normaliseRole).filter((role) => role.value),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function utentiEndpoint(): string {
  if (typeof window === 'undefined') return '/api/v1/ui/utenti'
  return window.location.pathname.toLowerCase() === '/utenti/nuovo'
    ? '/api/v1/ui/utenti?view=nuovo'
    : '/api/v1/ui/utenti'
}

export async function getUtentiPage(): Promise<UtentiPageData> {
  const payload = await apiJson<unknown>(utentiEndpoint(), emptyUtentiPage)
  return normalisePage(payload)
}
