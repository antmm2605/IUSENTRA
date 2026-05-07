import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning, LegacyFormDefinition } from './utentiData'
import type { LegacyPostField } from './ui/LegacyPostForm'

export type ProfiloRoleUser = {
  id: string
  username: string
  label: string
  active: boolean
  hasOverride: boolean
  permissionsHref: string
}

export type ProfiloRoleRecord = {
  id: string
  role: string
  label: string
  description: string
  tone: AdminTone
  usersCount: number
  permissionsCount: number
  users: ProfiloRoleUser[]
}

export type ProfiloPermissionGrant = {
  role: string
  granted: boolean
}

export type ProfiloPermissionRecord = {
  id: string
  category: string
  permission: string
  label: string
  grants: ProfiloPermissionGrant[]
}

export type ProfiloOverrideRecord = {
  id: string
  username: string
  label: string
  role: string
  extraPermissions: string[]
  deniedPermissions: string[]
  permissionsHref: string
}

export type ProfiliRecords = {
  roles: ProfiloRoleRecord[]
  permissions: ProfiloPermissionRecord[]
  overrides: ProfiloOverrideRecord[]
}

export type ProfiliPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: ProfiliRecords
  actions: AdminAction[]
  forms: LegacyFormDefinition[]
  warnings: AdminWarning[]
}

export const emptyProfiliPage: ProfiliPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'legacy_routes',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: { roles: [], permissions: [], overrides: [] },
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

function normaliseSectionItem(raw: unknown) {
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

function normaliseRoleUser(raw: unknown): ProfiloRoleUser {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    username: text(item.username),
    label: text(item.label),
    active: bool(item.active),
    hasOverride: bool(item.hasOverride),
    permissionsHref: text(item.permissionsHref),
  }
}

function normaliseRole(raw: unknown): ProfiloRoleRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.role),
    role: text(item.role),
    label: text(item.label) || text(item.role),
    description: text(item.description),
    tone: tone(item.tone),
    usersCount: number(item.usersCount),
    permissionsCount: number(item.permissionsCount),
    users: list(item.users).map(normaliseRoleUser),
  }
}

function normalisePermission(raw: unknown): ProfiloPermissionRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.permission),
    category: text(item.category),
    permission: text(item.permission),
    label: text(item.label),
    grants: list(item.grants).map((grant) => {
      const record = asRecord(grant)
      return { role: text(record.role), granted: bool(record.granted) }
    }),
  }
}

function normaliseOverride(raw: unknown): ProfiloOverrideRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    username: text(item.username),
    label: text(item.label),
    role: text(item.role),
    extraPermissions: list(item.extraPermissions).map((entry) => text(entry)).filter(Boolean),
    deniedPermissions: list(item.deniedPermissions).map((entry) => text(entry)).filter(Boolean),
    permissionsHref: text(item.permissionsHref),
  }
}

function normaliseField(raw: unknown): LegacyPostField {
  const item = asRecord(raw)
  const fieldType = ['text', 'email', 'password', 'select', 'checkbox', 'hidden'].includes(String(item.type))
    ? String(item.type) as LegacyPostField['type']
    : 'hidden'
  return {
    name: text(item.name),
    label: text(item.label),
    type: fieldType,
    required: bool(item.required),
    value: text(item.value),
  }
}

function normaliseForm(raw: unknown): LegacyFormDefinition {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'form',
    title: text(item.title),
    description: text(item.description),
    action: text(item.action),
    method: 'POST',
    csrfField: text(item.csrfField) || '_csrf_token',
    submitLabel: text(item.submitLabel) || 'Invia',
    enabled: item.enabled === false ? false : true,
    fields: list(item.fields).map(normaliseField).filter((field) => field.name),
  }
}

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: text(item.href) || '/profili',
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

function normalisePage(raw: unknown): ProfiliPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const records = asRecord(page.records)
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
    records: {
      roles: list(records.roles).map(normaliseRole),
      permissions: list(records.permissions).map(normalisePermission),
      overrides: list(records.overrides).map(normaliseOverride),
    },
    actions: list(page.actions).map(normaliseAction).filter((action) => action.method === 'GET' && action.href),
    forms: list(page.forms).map(normaliseForm).filter((form) => form.action),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getProfiliPage(): Promise<ProfiliPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/profili', emptyProfiliPage)
  return normalisePage(payload)
}
