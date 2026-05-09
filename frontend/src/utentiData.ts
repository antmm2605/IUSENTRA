import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type UtentiTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type UtentiContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  operational?: boolean
  legacy_contract?: string
}

export type UtentiMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: UtentiTone
}

export type UtentiSectionItem = {
  id: string
  label: string
  value: string | number
  note: string
  tone: UtentiTone
}

export type UtentiSection = {
  id: string
  title: string
  kind: string
  items: UtentiSectionItem[]
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
  roleTone: UtentiTone
  active: boolean
  mustChangeCredential: boolean
  lastAccess: string
  hasOverride: boolean
  extraPermissionsCount: number
  deniedPermissionsCount: number
  twoFactorEnabled: boolean
  isCurrentUser: boolean
}

export type UtenteRole = {
  value: string
  label: string
  description: string
  tone: UtentiTone
}

export type UtentiRollbackAction = {
  label: string
  href: string
  method: 'GET'
}

export type AdminAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: UtentiTone
}

export type LegacyFormField = {
  name: string
  label: string
  type: 'text' | 'email' | 'password' | 'select' | 'checkbox' | 'hidden'
  required?: boolean
  autocomplete?: string
  minLength?: number
  value?: string
  placeholder?: string
  options?: Array<{
    value: string
    label: string
    description?: string
    enabled?: boolean
  }>
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
  fields: LegacyFormField[]
}

export type UtentiPermissions = {
  canCreate: boolean
  canUpdate: boolean
  canDisable: boolean
  canResetPassword: boolean
  canChangeRole: boolean
  canUpdateProfile: boolean
  read: boolean
  create: string
  profiles: string
  statusEndpoint: string
  roleEndpoint: string
  resetPasswordEndpoint: string
  profileEndpoint: string
  rollback?: UtentiRollbackAction
}

export type UtentiWarning = {
  code: string
  message: string
}

export type UtentiPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: UtentiContract
  metrics: UtentiMetric[]
  sections: UtentiSection[]
  users: UtenteRecord[]
  records: UtenteRecord[]
  actions: UtentiPermissions
  createEndpoint: string
  roles: UtenteRole[]
  forms: unknown[]
  warnings: UtentiWarning[]
}

export type UpdateUtenteStatusPayload = {
  active: boolean
}

export type UpdateUtenteRolePayload = {
  role: string
}

export type ResetUtentePasswordPayload = {
  temporaryPassword: string
  confirm: boolean
}

export type UpdateUtenteProfilePayload = {
  name: string
  email: string
}

export type CreateUtentePayload = {
  username: string
  ruolo: string
  nome_completo: string
  email: string
  password: string
}

export type UtenteMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  user: UtenteRecord | null
  payload?: UtentiPageData
}

export type AdminTone = UtentiTone
export type AdminContract = UtentiContract
export type AdminMetric = UtentiMetric
export type AdminSectionItem = UtentiSectionItem
export type AdminSection = UtentiSection
export type AdminWarning = UtentiWarning
export type RoleOption = UtenteRole

export const emptyUtentiPage: UtentiPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
    operational: true,
  },
  metrics: [],
  sections: [],
  users: [],
  records: [],
  actions: {
    canCreate: false,
    canUpdate: false,
    canDisable: false,
    canResetPassword: false,
    canChangeRole: false,
    canUpdateProfile: false,
    read: false,
    create: '',
    profiles: '',
    statusEndpoint: '',
    roleEndpoint: '',
    resetPasswordEndpoint: '',
    profileEndpoint: '',
  },
  createEndpoint: '',
  roles: [],
  forms: [],
  warnings: [],
}

const emptyMutation: UtenteMutationResult = {
  ok: false,
  message: 'Operazione non completata.',
  errors: { _form: 'Il servizio non ha restituito un esito utilizzabile.' },
  user: null,
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

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function tone(value: unknown): UtentiTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as UtentiTone
    : 'neutral'
}

function endpointPattern(value: unknown, fallback: string): string {
  const raw = text(value)
  return raw || fallback
}

function endpointFromPattern(pattern: string, userId: string, fallback: string): string {
  const safePattern = pattern || fallback
  return safePattern.replace('{id_utente}', encodeURIComponent(userId))
}

function normaliseMetric(raw: unknown): UtentiMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSectionItem(raw: unknown): UtentiSectionItem {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: display(item.label) || 'Voce',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): UtentiSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'Distribuzione',
    items: list(item.items).map(normaliseSectionItem),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
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
    roleLabel: display(item.roleLabel) || display(item.role),
    roleDescription: display(item.roleDescription),
    roleTone: tone(item.roleTone),
    active: bool(item.active),
    mustChangeCredential: bool(item.mustChangeCredential) || bool(item.mustChangePassword),
    lastAccess: text(item.lastAccess),
    hasOverride: bool(item.hasOverride),
    extraPermissionsCount: number(item.extraPermissionsCount),
    deniedPermissionsCount: number(item.deniedPermissionsCount),
    twoFactorEnabled: bool(item.twoFactorEnabled),
    isCurrentUser: bool(item.isCurrentUser),
  }
}

function normaliseRole(raw: unknown): UtenteRole {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: display(item.label) || display(item.value),
    description: display(item.description),
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): UtentiWarning {
  const item = asRecord(raw)
  return {
    code: display(item.code) || 'warning',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseRollback(raw: unknown): UtentiRollbackAction | undefined {
  const item = asRecord(raw)
  const href = text(item.href)
  if (!href) return undefined
  return {
    label: display(item.label) || 'Percorso di recupero',
    href,
    method: 'GET',
  }
}

function normaliseActions(raw: unknown): UtentiPermissions {
  const item = asRecord(raw)
  return {
    canCreate: bool(item.canCreate),
    canUpdate: bool(item.canUpdate),
    canDisable: bool(item.canDisable),
    canResetPassword: bool(item.canResetPassword),
    canChangeRole: bool(item.canChangeRole),
    canUpdateProfile: bool(item.canUpdateProfile) || bool(item.canUpdate),
    read: bool(item.read),
    create: text(item.create),
    profiles: text(item.profiles),
    statusEndpoint: endpointPattern(item.statusEndpoint, '/api/v1/ui/utenti/{id_utente}/stato'),
    roleEndpoint: endpointPattern(item.roleEndpoint, '/api/v1/ui/utenti/{id_utente}/ruolo'),
    resetPasswordEndpoint: endpointPattern(item.resetPasswordEndpoint, '/api/v1/ui/utenti/{id_utente}/reset-password'),
    profileEndpoint: endpointPattern(item.profileEndpoint, '/api/v1/ui/utenti/{id_utente}/profilo'),
    rollback: normaliseRollback(item.rollback),
  }
}

function normalisePage(raw: unknown): UtentiPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const users = (list(page.users).length ? list(page.users) : list(page.records)).map(normaliseUser)
  return {
    ok: page.ok === true,
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true,
      writes: text(contracts.writes) || 'json_api',
      route_owner: text(contracts.route_owner) || 'react_shell',
      operational: contracts.operational !== false,
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    users,
    records: users,
    actions: normaliseActions(page.actions),
    createEndpoint: text(page.createEndpoint),
    roles: list(page.roles).map(normaliseRole).filter((role) => role.value),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseMutation(raw: unknown): UtenteMutationResult {
  const item = asRecord(raw)
  const errors = asRecord(item.errors)
  const userRaw = item.user || item.item
  const result: UtenteMutationResult = {
    ok: item.ok === true,
    message: display(item.message) || (item.ok === true ? 'Operazione completata.' : 'Operazione non completata.'),
    errors: Object.fromEntries(Object.entries(errors).map(([key, value]) => [key, display(value)])),
    user: userRaw ? normaliseUser(userRaw) : null,
  }
  if (item.payload) {
    result.payload = normalisePage(item.payload)
  }
  return result
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

export async function createUtente(payload: CreateUtentePayload, endpoint = '/api/v1/ui/utenti/nuovo'): Promise<UtenteMutationResult> {
  const response = await apiPostJson<unknown>(endpoint || '/api/v1/ui/utenti/nuovo', payload, emptyMutation)
  return normaliseMutation(response)
}

export async function updateUtenteStatus(
  userId: string,
  payload: UpdateUtenteStatusPayload,
  endpointPatternValue = '/api/v1/ui/utenti/{id_utente}/stato',
): Promise<UtenteMutationResult> {
  const endpoint = endpointFromPattern(endpointPatternValue, userId, '/api/v1/ui/utenti/{id_utente}/stato')
  const response = await apiPostJson<unknown>(endpoint, payload, emptyMutation)
  return normaliseMutation(response)
}

export async function updateUtenteRole(
  userId: string,
  payload: UpdateUtenteRolePayload,
  endpointPatternValue = '/api/v1/ui/utenti/{id_utente}/ruolo',
): Promise<UtenteMutationResult> {
  const endpoint = endpointFromPattern(endpointPatternValue, userId, '/api/v1/ui/utenti/{id_utente}/ruolo')
  const response = await apiPostJson<unknown>(endpoint, payload, emptyMutation)
  return normaliseMutation(response)
}

export async function resetUtentePassword(
  userId: string,
  payload: ResetUtentePasswordPayload,
  endpointPatternValue = '/api/v1/ui/utenti/{id_utente}/reset-password',
): Promise<UtenteMutationResult> {
  const endpoint = endpointFromPattern(endpointPatternValue, userId, '/api/v1/ui/utenti/{id_utente}/reset-password')
  const response = await apiPostJson<unknown>(endpoint, payload, emptyMutation)
  return normaliseMutation(response)
}

export async function updateUtenteProfile(
  userId: string,
  payload: UpdateUtenteProfilePayload,
  endpointPatternValue = '/api/v1/ui/utenti/{id_utente}/profilo',
): Promise<UtenteMutationResult> {
  const endpoint = endpointFromPattern(endpointPatternValue, userId, '/api/v1/ui/utenti/{id_utente}/profilo')
  const response = await apiPostJson<unknown>(endpoint, payload, emptyMutation)
  return normaliseMutation(response)
}
