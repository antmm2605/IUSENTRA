import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type ProfiloTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type ProfiloContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  operational: boolean
  legacy_contract?: string
}

export type ProfiloRoleUser = {
  id: string
  username: string
  label: string
  role: string
  active: boolean
  hasOverride: boolean
}

export type ProfiloRole = {
  id: string
  role: string
  label: string
  description: string
  tone: ProfiloTone
  usersCount: number
  permissionsCount: number
  permissions: string[]
  users: ProfiloRoleUser[]
}

export type ProfiloPermission = {
  id: string
  category: string
  permission: string
  label: string
}

export type ProfiloPermissionGrant = {
  role: string
  granted: boolean
}

export type ProfiloMatrixRow = {
  id: string
  category: string
  permission: string
  label: string
  grants: ProfiloPermissionGrant[]
}

export type ProfiloOverride = {
  id: string
  username: string
  label: string
  role: string
  active: boolean
  hasOverride: boolean
  extraPermissions: string[]
  deniedPermissions: string[]
  effectivePermissions: string[]
}

export type ProfiloMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: ProfiloTone
}

export type ProfiloWarning = {
  code: string
  message: string
}

export type ProfiloRollbackAction = {
  label: string
  href: string
  method: 'GET'
}

export type ProfiloActions = {
  canWrite: boolean
  read: string
  save: string
  users: string
  rollback: ProfiloRollbackAction | null
}

export type ProfiliPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: ProfiloContract
  roles: ProfiloRole[]
  permissions: ProfiloPermission[]
  matrix: ProfiloMatrixRow[]
  overrides: ProfiloOverride[]
  actions: ProfiloActions
  warnings: ProfiloWarning[]
  metrics: ProfiloMetric[]
}

export type SaveProfiliPayload = {
  action: 'update_user_override'
  userId: string
  extraPermissions: string[]
  deniedPermissions: string[]
}

export type SaveProfiliResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  updated: ProfiloOverride | null
  payload?: ProfiliPageData
  status?: number
}

const emptyActions: ProfiloActions = {
  canWrite: false,
  read: '/api/v1/ui/profili',
  save: '/api/v1/ui/profili',
  users: '/utenti',
  rollback: null,
}

export const emptyProfiliPage: ProfiliPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
    operational: true,
  },
  roles: [],
  permissions: [],
  matrix: [],
  overrides: [],
  actions: emptyActions,
  warnings: [],
  metrics: [],
}

const emptySaveResult: SaveProfiliResult = {
  ok: false,
  message: 'Salvataggio non completato.',
  errors: { _form: 'Risposta non disponibile dal server.' },
  updated: null,
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

function stringList(value: unknown): string[] {
  return list(value).map((item) => text(item)).filter(Boolean)
}

function tone(value: unknown): ProfiloTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as ProfiloTone
    : 'neutral'
}

function normaliseMetric(raw: unknown): ProfiloMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseRoleUser(raw: unknown): ProfiloRoleUser {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    username: text(item.username),
    label: display(item.label),
    role: text(item.role),
    active: bool(item.active),
    hasOverride: bool(item.hasOverride),
  }
}

function normaliseRole(raw: unknown): ProfiloRole {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.role),
    role: text(item.role),
    label: display(item.label) || display(item.role),
    description: display(item.description),
    tone: tone(item.tone),
    usersCount: number(item.usersCount),
    permissionsCount: number(item.permissionsCount),
    permissions: stringList(item.permissions),
    users: list(item.users).map(normaliseRoleUser),
  }
}

function normalisePermission(raw: unknown): ProfiloPermission {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.permission),
    category: display(item.category),
    permission: text(item.permission),
    label: display(item.label),
  }
}

function normaliseMatrixRow(raw: unknown): ProfiloMatrixRow {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.permission),
    category: display(item.category),
    permission: text(item.permission),
    label: display(item.label),
    grants: list(item.grants).map((grant) => {
      const record = asRecord(grant)
      return { role: text(record.role), granted: bool(record.granted) }
    }),
  }
}

function normaliseOverride(raw: unknown): ProfiloOverride {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    username: text(item.username),
    label: display(item.label),
    role: text(item.role),
    active: bool(item.active),
    hasOverride: bool(item.hasOverride),
    extraPermissions: stringList(item.extraPermissions),
    deniedPermissions: stringList(item.deniedPermissions),
    effectivePermissions: stringList(item.effectivePermissions),
  }
}

function normaliseWarning(raw: unknown): ProfiloWarning {
  const item = asRecord(raw)
  return {
    code: display(item.code) || 'warning',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseActions(raw: unknown): ProfiloActions {
  const item = asRecord(raw)
  const rollback = asRecord(item.rollback)
  const rollbackHref = text(rollback.href)
  return {
    canWrite: bool(item.canWrite),
    read: text(item.read) || emptyActions.read,
    save: text(item.save) || emptyActions.save,
    users: text(item.users) || emptyActions.users,
    rollback: rollbackHref
      ? {
        label: display(rollback.label) || 'Percorso di recupero',
        href: rollbackHref,
        method: 'GET',
      }
      : null,
  }
}

function normaliseContracts(raw: unknown): ProfiloContract {
  const contracts = asRecord(raw)
  return {
    mock_fallback: bool(contracts.mock_fallback),
    writes: text(contracts.writes) || 'json_api',
    route_owner: text(contracts.route_owner) || 'react_shell',
    operational: contracts.operational === false ? false : true,
    legacy_contract: text(contracts.legacy_contract),
  }
}

function errors(raw: unknown): Record<string, string> {
  const item = asRecord(raw)
  const output: Record<string, string> = {}
  for (const [key, val] of Object.entries(item)) {
    const message = text(val)
    if (message) output[key] = sanitizeDisplayText(message)
  }
  return output
}

function normalisePage(raw: unknown): ProfiliPageData {
  const page = asRecord(raw)
  const legacyRecords = asRecord(page.records)
  const roles = list(page.roles).length ? list(page.roles) : list(legacyRecords.roles)
  const matrix = list(page.matrix).length ? list(page.matrix) : list(legacyRecords.permissions)
  const permissions = list(page.permissions).length ? list(page.permissions) : matrix
  const overrides = list(page.overrides).length ? list(page.overrides) : list(legacyRecords.overrides)
  return {
    ok: page.ok === true,
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContracts(page.contracts),
    roles: roles.map(normaliseRole),
    permissions: permissions.map(normalisePermission),
    matrix: matrix.map(normaliseMatrixRow),
    overrides: overrides.map(normaliseOverride),
    actions: normaliseActions(page.actions),
    warnings: list(page.warnings).map(normaliseWarning),
    metrics: list(page.metrics).map(normaliseMetric),
  }
}

function normaliseSaveResult(raw: unknown): SaveProfiliResult {
  const item = asRecord(raw)
  const payload = item.payload ? normalisePage(item.payload) : undefined
  return {
    ok: bool(item.ok),
    message: display(item.message) || emptySaveResult.message,
    errors: errors(item.errors),
    updated: item.updated ? normaliseOverride(item.updated) : null,
    payload,
    status: number(item.status) || undefined,
  }
}

export function allProfiloUsers(data: ProfiliPageData): ProfiloRoleUser[] {
  const seen = new Set<string>()
  const users: ProfiloRoleUser[] = []
  for (const role of data.roles) {
    for (const user of role.users) {
      const key = user.id || user.username
      if (!key || seen.has(key)) continue
      seen.add(key)
      users.push({ ...user, role: user.role || role.role })
    }
  }
  return users.sort((a, b) => (a.label || a.username).localeCompare(b.label || b.username, 'it'))
}

export async function getProfiliPage(): Promise<ProfiliPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/profili', emptyProfiliPage)
  return normalisePage(payload)
}

export async function saveProfiliPermissions(payload: SaveProfiliPayload): Promise<SaveProfiliResult> {
  const response = await apiPostJson<SaveProfiliResult>('/api/v1/ui/profili', payload, emptySaveResult)
  return normaliseSaveResult(response)
}

export async function saveUserPermissionOverride(payload: SaveProfiliPayload): Promise<SaveProfiliResult> {
  return saveProfiliPermissions(payload)
}

export async function saveProfiloRole(payload: SaveProfiliPayload): Promise<SaveProfiliResult> {
  return saveProfiliPermissions(payload)
}
