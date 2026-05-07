import { apiJson, apiPostJson } from './lib/apiClient'

export type BackupTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type BackupContracts = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  operational: boolean
  restore_migrated: boolean
}

export type BackupComponentOption = {
  id: string
  label: string
  available: boolean
  enabled: boolean
}

export type BackupStatus = {
  total: number
  completed: number
  failed: number
  corrupted: number
  totalSizeMb: number
  lastBackupAt: string
  automaticEnabled: boolean
  frequency: string
  scheduledTime: string
  maxBackups: number
  configuredComponents: BackupComponentOption[]
}

export type BackupRow = {
  id: string
  createdAt: string
  type: string
  state: string
  stateLabel: string
  stateTone: BackupTone
  fileName: string
  sizeMb: number
  filesCount: number
  components: string[]
  encrypted: boolean
  note: string
  error: string
  downloadHref: string
  restoreHref: string
}

export type BackupIntegrity = {
  available: boolean
  state: string
  label: string
  lastCheckedAt: string
  checkedBackupId: string
  corruptedCount: number
}

export type BackupPermissions = {
  canCreate: boolean
  canVerify: boolean
  canDownload: boolean
  canRestore: boolean
  createEndpoint: string
  verifyEndpoint: string
  legacyHref: string
}

export type BackupWarning = {
  code: string
  message: string
}

export type BackupPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: BackupContracts
  status: BackupStatus
  backups: BackupRow[]
  integrity: BackupIntegrity
  actions: BackupPermissions
  warnings: BackupWarning[]
}

export type CreateBackupPayload = {
  type: string
  components: string[]
  note: string
  confirm: boolean
}

export type VerifyBackupPayload = {
  backupId: string
  confirm: boolean
}

export type BackupMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  backup: BackupRow | null
  integrity: BackupIntegrity | null
}

const emptyStatus: BackupStatus = {
  total: 0,
  completed: 0,
  failed: 0,
  corrupted: 0,
  totalSizeMb: 0,
  lastBackupAt: '',
  automaticEnabled: false,
  frequency: '',
  scheduledTime: '',
  maxBackups: 0,
  configuredComponents: [],
}

const emptyIntegrity: BackupIntegrity = {
  available: false,
  state: 'empty',
  label: '',
  lastCheckedAt: '',
  checkedBackupId: '',
  corruptedCount: 0,
}

export const emptyBackupPage: BackupPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
    operational: true,
    restore_migrated: false,
  },
  status: emptyStatus,
  backups: [],
  integrity: emptyIntegrity,
  actions: {
    canCreate: false,
    canVerify: false,
    canDownload: false,
    canRestore: false,
    createEndpoint: '/api/v1/ui/backup/crea',
    verifyEndpoint: '/api/v1/ui/backup/verifica',
    legacyHref: '/backup?_legacy=1',
  },
  warnings: [],
}

const emptyMutationResult: BackupMutationResult = {
  ok: false,
  message: 'Operazione non completata.',
  errors: { _form: 'Errore di rete o risposta non valida.' },
  backup: null,
  integrity: null,
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

function tone(value: unknown): BackupTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as BackupTone
    : 'neutral'
}

function normaliseComponent(raw: unknown): BackupComponentOption {
  const item = asRecord(raw)
  const id = text(item.id)
  return {
    id,
    label: text(item.label) || id,
    available: item.available === false ? false : true,
    enabled: item.enabled === false ? false : true,
  }
}

function normaliseStatus(raw: unknown): BackupStatus {
  const item = asRecord(raw)
  return {
    total: number(item.total),
    completed: number(item.completed),
    failed: number(item.failed),
    corrupted: number(item.corrupted),
    totalSizeMb: number(item.totalSizeMb),
    lastBackupAt: text(item.lastBackupAt),
    automaticEnabled: bool(item.automaticEnabled),
    frequency: text(item.frequency),
    scheduledTime: text(item.scheduledTime),
    maxBackups: number(item.maxBackups),
    configuredComponents: list(item.configuredComponents).map(normaliseComponent).filter((component) => component.id),
  }
}

function normaliseBackup(raw: unknown): BackupRow {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    createdAt: text(item.createdAt),
    type: text(item.type),
    state: text(item.state),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    fileName: text(item.fileName),
    sizeMb: number(item.sizeMb),
    filesCount: number(item.filesCount),
    components: list(item.components).map((entry) => text(entry)).filter(Boolean),
    encrypted: bool(item.encrypted),
    note: text(item.note),
    error: text(item.error),
    downloadHref: text(item.downloadHref),
    restoreHref: text(item.restoreHref),
  }
}

function normaliseIntegrity(raw: unknown): BackupIntegrity {
  const item = asRecord(raw)
  return {
    available: bool(item.available),
    state: text(item.state),
    label: text(item.label),
    lastCheckedAt: text(item.lastCheckedAt),
    checkedBackupId: text(item.checkedBackupId),
    corruptedCount: number(item.corruptedCount),
  }
}

function normaliseActions(raw: unknown): BackupPermissions {
  const item = asRecord(raw)
  return {
    canCreate: bool(item.canCreate),
    canVerify: bool(item.canVerify),
    canDownload: bool(item.canDownload),
    canRestore: bool(item.canRestore),
    createEndpoint: text(item.createEndpoint) || '/api/v1/ui/backup/crea',
    verifyEndpoint: text(item.verifyEndpoint) || '/api/v1/ui/backup/verifica',
    legacyHref: text(item.legacyHref) || '/backup?_legacy=1',
  }
}

function normaliseWarning(raw: unknown): BackupWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'avviso',
    message: text(item.message) || 'Avviso operativo disponibile.',
  }
}

function normalisePage(raw: unknown): BackupPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  return {
    ok: bool(page.ok),
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: bool(contracts.mock_fallback),
      writes: text(contracts.writes) || 'json_api',
      route_owner: text(contracts.route_owner) || 'react_shell',
      operational: contracts.operational === false ? false : true,
      restore_migrated: bool(contracts.restore_migrated),
    },
    status: normaliseStatus(page.status),
    backups: list(page.backups).map(normaliseBackup).filter((backup) => backup.id),
    integrity: normaliseIntegrity(page.integrity),
    actions: normaliseActions(page.actions),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseMutation(raw: unknown): BackupMutationResult {
  const item = asRecord(raw)
  const rawErrors = asRecord(item.errors)
  const errors = Object.fromEntries(
    Object.entries(rawErrors).map(([key, value]) => [key, text(value)]).filter(([, value]) => value),
  )
  const backup = item.backup ? normaliseBackup(item.backup) : null
  const integrity = item.integrity ? normaliseIntegrity(item.integrity) : null
  return {
    ok: bool(item.ok),
    message: text(item.message) || emptyMutationResult.message,
    errors,
    backup: backup && backup.id ? backup : null,
    integrity,
  }
}

export async function getBackupPage(): Promise<BackupPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/backup', emptyBackupPage)
  return normalisePage(payload)
}

export async function createBackup(
  payload: CreateBackupPayload,
  endpoint = '/api/v1/ui/backup/crea',
): Promise<BackupMutationResult> {
  const result = await apiPostJson<unknown>(endpoint, payload, emptyMutationResult)
  return normaliseMutation(result)
}

export async function verifyBackupIntegrity(
  payload: VerifyBackupPayload,
  endpoint = '/api/v1/ui/backup/verifica',
): Promise<BackupMutationResult> {
  const result = await apiPostJson<unknown>(endpoint, payload, emptyMutationResult)
  return normaliseMutation(result)
}
