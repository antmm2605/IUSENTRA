import type { Tone } from './data'
import type { ReactContracts } from './timesheetData'

export type SharedAccess = {
  idUser: string
  username: string
  name: string
  role: string
  roleLabel: string
  roleTone: Tone
  sharedBy: string
  sharedAt: string
  sharedAtLabel: string
  deadline: string
  deadlineLabel: string
  daysToDeadline: number | null
  expired: boolean
  expiring: boolean
  notes: string
  tags: string[]
}

export type SharedClient = {
  id: string
  name: string
  type: string
  href: string
  collaboratorsHref: string
}

export type ManagedFolder = {
  client: SharedClient
  collaboratorsCount: number
  accesses: SharedAccess[]
  roleCounts: Record<string, number>
  expiredCount: number
  expiringCount: number
  activeLinks: Array<{
    id: string
    role: string
    roleLabel: string
    expiresAt: string
    expiresLabel: string
    createdBy: string
    oneShot: boolean
    description: string
  }>
  openHref: string
  manageHref: string
}

export type ReceivedFolder = {
  client: SharedClient
  access: SharedAccess
  openHref: string
  manageHref: string
}

export type ReceivedMatter = {
  id: string
  title: string
  number: string
  client: SharedClient
  access: SharedAccess
  href: string
}

export type CartelleCondiviseData = {
  source: string
  generatedAt: string
  contracts: ReactContracts
  mode: 'gestore' | 'collaboratore'
  permissions: {
    canReadClients: boolean
    canWriteClients: boolean
    canCleanExpired: boolean
  }
  stats: {
    sharedFolders: number
    totalAccesses: number
    expiredAccesses: number
    expiring7Days: number
    activeTemporaryLinks: number
    sharedMatters: number
    perRole: Record<string, number>
  }
  managedFolders: ManagedFolder[]
  receivedFolders: ReceivedFolder[]
  receivedMatters: ReceivedMatter[]
  warnings: Array<{ tone: Tone; label: string; count: number }>
  roleOptions: Array<{ value: string; label: string; tone: Tone }>
  actions: {
    clients: string
    audit: string
    gdpr: string
    cleanupExpired: string
    statistics: string
    lex: string
  }
  emptyStates: {
    noManagedFolders: boolean
    noReceivedFolders: boolean
    noExpiringAccesses: boolean
  }
}

const emptyContracts: ReactContracts = { mock_fallback: false, writes: 'operational_routes', route_owner: 'react_shell' }

const emptyClient: SharedClient = { id: '', name: 'Cliente non disponibile', type: '', href: '', collaboratorsHref: '' }

const emptyData: CartelleCondiviseData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: emptyContracts,
  mode: 'collaboratore',
  permissions: { canReadClients: false, canWriteClients: false, canCleanExpired: false },
  stats: {
    sharedFolders: 0,
    totalAccesses: 0,
    expiredAccesses: 0,
    expiring7Days: 0,
    activeTemporaryLinks: 0,
    sharedMatters: 0,
    perRole: {},
  },
  managedFolders: [],
  receivedFolders: [],
  receivedMatters: [],
  warnings: [],
  roleOptions: [],
  actions: {
    clients: '/clienti',
    audit: '/audit',
    gdpr: '/privacy/registro',
    cleanupExpired: '/api/v1/condivisioni/pulizia-scaduti',
    statistics: '/api/v1/condivisioni/statistiche',
    lex: '/lex?context=cartelle-condivise',
  },
  emptyStates: { noManagedFolders: true, noReceivedFolders: true, noExpiringAccesses: true },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim() || fallback
}

function number(value: unknown, fallback = 0): number {
  const parsed = Number(value ?? fallback)
  return Number.isFinite(parsed) ? parsed : fallback
}

function tone(value: unknown): Tone {
  const raw = text(value, 'neutral')
  return ['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw) ? raw as Tone : 'neutral'
}

function contractsFrom(value: unknown): ReactContracts {
  if (!isRecord(value)) return emptyContracts
  return {
    mock_fallback: Boolean(value.mock_fallback),
    writes: text(value.writes, 'operational_routes'),
    route_owner: text(value.route_owner, 'react_shell'),
    read_only: Boolean(value.read_only),
  }
}

function perRoleFrom(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, number(item)]))
}

function clientFrom(value: unknown): SharedClient {
  if (!isRecord(value)) return emptyClient
  return {
    id: text(value.id),
    name: text(value.name, 'Cliente non disponibile'),
    type: text(value.type),
    href: text(value.href),
    collaboratorsHref: text(value.collaboratorsHref ?? value.collaborators_href),
  }
}

function accessFrom(value: unknown): SharedAccess {
  const item = isRecord(value) ? value : {}
  const rawDays = item.daysToDeadline ?? item.days_to_deadline
  return {
    idUser: text(item.idUser ?? item.id_user),
    username: text(item.username),
    name: text(item.name, 'Collaboratore'),
    role: text(item.role),
    roleLabel: text(item.roleLabel ?? item.role_label),
    roleTone: tone(item.roleTone ?? item.role_tone),
    sharedBy: text(item.sharedBy ?? item.shared_by),
    sharedAt: text(item.sharedAt ?? item.shared_at),
    sharedAtLabel: text(item.sharedAtLabel ?? item.shared_at_label),
    deadline: text(item.deadline),
    deadlineLabel: text(item.deadlineLabel ?? item.deadline_label, 'Nessuna scadenza'),
    daysToDeadline: rawDays === null || rawDays === undefined ? null : number(rawDays),
    expired: Boolean(item.expired),
    expiring: Boolean(item.expiring),
    notes: text(item.notes),
    tags: Array.isArray(item.tags) ? item.tags.map((tag) => text(tag)).filter(Boolean) : [],
  }
}

function managedFolderFrom(value: unknown): ManagedFolder | null {
  if (!isRecord(value)) return null
  return {
    client: clientFrom(value.client),
    collaboratorsCount: number(value.collaboratorsCount ?? value.collaborators_count),
    accesses: Array.isArray(value.accesses) ? value.accesses.map(accessFrom) : [],
    roleCounts: perRoleFrom(value.roleCounts ?? value.role_counts),
    expiredCount: number(value.expiredCount ?? value.expired_count),
    expiringCount: number(value.expiringCount ?? value.expiring_count),
    activeLinks: Array.isArray(value.activeLinks) ? value.activeLinks.map((link) => {
      const item = isRecord(link) ? link : {}
      return {
        id: text(item.id),
        role: text(item.role),
        roleLabel: text(item.roleLabel ?? item.role_label),
        expiresAt: text(item.expiresAt ?? item.expires_at),
        expiresLabel: text(item.expiresLabel ?? item.expires_label),
        createdBy: text(item.createdBy ?? item.created_by),
        oneShot: Boolean(item.oneShot ?? item.one_shot),
        description: text(item.description),
      }
    }) : [],
    openHref: text(value.openHref ?? value.open_href),
    manageHref: text(value.manageHref ?? value.manage_href),
  }
}

function receivedFolderFrom(value: unknown): ReceivedFolder | null {
  if (!isRecord(value)) return null
  return {
    client: clientFrom(value.client),
    access: accessFrom(value.access),
    openHref: text(value.openHref ?? value.open_href),
    manageHref: text(value.manageHref ?? value.manage_href),
  }
}

function receivedMatterFrom(value: unknown): ReceivedMatter | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  return {
    id,
    title: text(value.title, 'Fascicolo condiviso'),
    number: text(value.number),
    client: clientFrom(value.client),
    access: accessFrom(value.access),
    href: text(value.href),
  }
}

export async function getCartelleCondivisePage(): Promise<CartelleCondiviseData> {
  try {
    const response = await fetch('/api/v1/ui/cartelle-condivise', {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyData
    const payload = await response.json() as Record<string, unknown>
    const permissions = isRecord(payload.permissions) ? payload.permissions : {}
    const stats = isRecord(payload.stats) ? payload.stats : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    const emptyStates = isRecord(payload.emptyStates) ? payload.emptyStates : {}
    return {
      source: text(payload.source, 'repository_reali'),
      generatedAt: text(payload.generatedAt ?? payload.generated_at),
      contracts: contractsFrom(payload.contracts),
      mode: text(payload.mode) === 'gestore' ? 'gestore' : 'collaboratore',
      permissions: {
        canReadClients: Boolean(permissions.canReadClients ?? permissions.can_read_clients),
        canWriteClients: Boolean(permissions.canWriteClients ?? permissions.can_write_clients),
        canCleanExpired: Boolean(permissions.canCleanExpired ?? permissions.can_clean_expired),
      },
      stats: {
        sharedFolders: number(stats.sharedFolders ?? stats.shared_folders),
        totalAccesses: number(stats.totalAccesses ?? stats.total_accesses),
        expiredAccesses: number(stats.expiredAccesses ?? stats.expired_accesses),
        expiring7Days: number(stats.expiring7Days ?? stats.expiring_7_days),
        activeTemporaryLinks: number(stats.activeTemporaryLinks ?? stats.active_temporary_links),
        sharedMatters: number(stats.sharedMatters ?? stats.shared_matters),
        perRole: perRoleFrom(stats.perRole ?? stats.per_role),
      },
      managedFolders: Array.isArray(payload.managedFolders) ? payload.managedFolders.map(managedFolderFrom).filter((item): item is ManagedFolder => Boolean(item)) : [],
      receivedFolders: Array.isArray(payload.receivedFolders) ? payload.receivedFolders.map(receivedFolderFrom).filter((item): item is ReceivedFolder => Boolean(item)) : [],
      receivedMatters: Array.isArray(payload.receivedMatters) ? payload.receivedMatters.map(receivedMatterFrom).filter((item): item is ReceivedMatter => Boolean(item)) : [],
      warnings: Array.isArray(payload.warnings) ? payload.warnings.map((warning) => {
        const item = isRecord(warning) ? warning : {}
        return { tone: tone(item.tone), label: text(item.label), count: number(item.count) }
      }).filter((warning) => warning.label) : [],
      roleOptions: Array.isArray(payload.roleOptions) ? payload.roleOptions.map((role) => {
        const item = isRecord(role) ? role : {}
        return { value: text(item.value), label: text(item.label), tone: tone(item.tone) }
      }).filter((role) => role.value) : [],
      actions: {
        clients: text(actions.clients, '/clienti'),
        audit: text(actions.audit, '/audit'),
        gdpr: text(actions.gdpr, '/privacy/registro'),
        cleanupExpired: text(actions.cleanupExpired ?? actions.cleanup_expired, '/api/v1/condivisioni/pulizia-scaduti'),
        statistics: text(actions.statistics, '/api/v1/condivisioni/statistiche'),
        lex: text(actions.lex, '/lex?context=cartelle-condivise'),
      },
      emptyStates: {
        noManagedFolders: Boolean(emptyStates.noManagedFolders),
        noReceivedFolders: Boolean(emptyStates.noReceivedFolders),
        noExpiringAccesses: Boolean(emptyStates.noExpiringAccesses),
      },
    }
  } catch {
    return emptyData
  }
}
