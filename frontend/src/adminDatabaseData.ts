import type { Tone } from './data'

export type AdminDatabaseStatus = {
  code: string
  label: string
  tone: Tone
  message: string
}

export type AdminDatabaseModule = {
  id: string
  name: string
  label: string
  path: string
  exists: boolean
  records: number
  sizeBytes: number
  sizeLabel: string
  lastModified: string
  lastModifiedLabel: string
  migratableSqlite: boolean
  authoritative: boolean
  mirror: boolean
  kind: { label: string; tone: Tone }
  status: AdminDatabaseStatus
}

export type AdminDatabaseSqliteInfo = {
  exists: boolean
  error: string
  path: string
  role: string
  sizeLabel: string
  sizeBytes: number
  totalPages: number
  freePages: number
  fragmentationPct: number
  pageSize: number
  tables: Array<{ name: string; records: number }>
}

export type AdminDatabaseUsage = {
  available: boolean
  error: string
  totalEvents: number
  topActions: Array<{ id: string; label: string; count: number }>
  topUsers: Array<{ id: string; label: string; count: number }>
  peakHour: number | null
  errorRate: number
  recentErrors: Array<Record<string, unknown>>
}

export type AdminDatabaseSourceTruth = {
  selectedMode: string
  effectiveMode: string
  authoritative: string
  sqlAuthoritative: boolean
  jsonRole: string
  status: string
  studioDbPath: string
  tenantSlug: string
}

export type AdminDatabaseActions = {
  refresh: string
  verify: string
  repair: string
  optimize: string
  migrate: string
  precheckSqlite: string
  reconcileSqlite: string
  activateSqlite: string
  exportZip: string
  backup: string
  audit: string
}

export type AdminDatabasePageData = {
  source: string
  generatedAt: string
  sourceTruth: AdminDatabaseSourceTruth
  page: {
    title: string
    subtitle: string
    path: string
  }
  summary: {
    modulesMonitored: number
    modulesMigratableSqlite: number
    totalRecords: number
    totalSizeBytes: number
    totalSizeLabel: string
    sqliteFragmentationPct: number
    statusCounts: Record<string, number>
    generatedLabel: string
  }
  modules: AdminDatabaseModule[]
  sqlite: AdminDatabaseSqliteInfo
  usage: AdminDatabaseUsage
  actions: AdminDatabaseActions
  contracts: {
    mock_fallback: boolean
    writes: string
    route_owner: string
    legacy_fallback: string
  }
  warning: string
}

export type AdminDatabaseIntegrityResult = {
  ok: boolean
  n_problemi: number
  n_riparazioni: number
  problemi: Array<{
    livello: string
    modulo: string
    tipo: string
    descrizione: string
    id_risorsa: string
    campo: string
    suggerimento: string
  }>
  riparazioni: Array<{
    modulo: string
    tipo: string
    id_record: string
    campo: string
    azione: string
    dettagli: string
    riuscita: boolean
    valore_precedente: string
    valore_nuovo: string
    backup_file: string
  }>
  backup_files?: string[]
  errori?: string[]
  errore?: string
}

export type AdminDatabaseOptimizeResult = {
  ok: boolean
  json_mirror_only?: boolean
  messaggio?: string
  risultati: Array<{
    modulo: string
    operazione: string
    ok: boolean
    riuscita: boolean
    messaggio: string
    dettagli: string
    ms: number
    bytes_prima: number
    bytes_dopo: number
    risparmio_bytes: number
    risparmio_pct: number
  }>
  errore?: string
}

export type AdminDatabaseMigrationResult = {
  ok: boolean
  json_mirror_only?: boolean
  stato?: string
  messaggio: string
  percorso_db: string
  record_migrati: number
  per_modulo: Record<string, number>
  errori: string[]
  avvisi: string[]
  azione_consigliata?: string
  audit_migrazione?: {
    validation?: {
      ok?: boolean
      modules?: Record<string, {
        json_count?: number
        sqlite_count?: number
        status?: string
        missing_source_ids?: string[]
        payload_mismatches?: string[]
      }>
      errors?: string[]
      warnings?: string[]
    }
    precheck?: {
      ok?: boolean
      target_exists?: boolean
      target_db?: string
      modules?: Record<string, {
        json_count?: number
        existing_sqlite_count?: number
        only_database_count?: number
        only_source_count?: number
        conflict_count?: number
        missing_existing_ids?: string[]
        only_source_ids?: string[]
        payload_mismatches?: string[]
        status?: string
        reason?: string
      }>
      blockers?: string[]
    }
    reconciliation?: {
      executed?: boolean
      mode?: string
      backup_db?: string
      records_imported?: number
      already_present?: number
      conflicts?: Array<{ table?: string; reason?: string; key?: Record<string, unknown> }>
      tables?: Record<string, {
        imported?: number
        already_present?: number
        conflicts?: number
        preserved_existing?: number
        target_count?: number
      }>
    }
    staging?: boolean
  }
  durata_secondi?: number
  istruzione?: string
  errore?: string
}

const emptyActions: AdminDatabaseActions = {
  refresh: '/api/v1/ui/admin/database',
  verify: '/admin/database/verifica',
  repair: '/admin/database/verifica-ripara',
  optimize: '/admin/database/ottimizza',
  migrate: '/admin/database/migra',
  precheckSqlite: '/admin/database/preverifica-sqlite',
  reconcileSqlite: '/admin/database/riconcilia-sqlite',
  activateSqlite: '/admin/database/attiva-sqlite',
  exportZip: '/admin/database/export',
  backup: '/backup',
  audit: '/audit',
}

const emptySqlite: AdminDatabaseSqliteInfo = {
  exists: false,
  error: '',
  path: '',
  role: '',
  sizeLabel: 'n.d.',
  sizeBytes: 0,
  totalPages: 0,
  freePages: 0,
  fragmentationPct: 0,
  pageSize: 0,
  tables: [],
}

const emptySourceTruth: AdminDatabaseSourceTruth = {
  selectedMode: 'JSON',
  effectiveMode: 'JSON',
  authoritative: 'JSON',
  sqlAuthoritative: false,
  jsonRole: 'Fonte operativa',
  status: 'Da verificare',
  studioDbPath: '',
  tenantSlug: '',
}

const emptyUsage: AdminDatabaseUsage = {
  available: false,
  error: '',
  totalEvents: 0,
  topActions: [],
  topUsers: [],
  peakHour: null,
  errorRate: 0,
  recentErrors: [],
}

export const emptyAdminDatabasePage: AdminDatabasePageData = {
  source: 'vuoto',
  generatedAt: '',
  sourceTruth: emptySourceTruth,
  page: {
    title: 'Gestione Database',
    subtitle: 'Caricamento statistiche, integrità, migrazione SQLite ed export dei dati.',
    path: '/admin/database',
  },
  summary: {
    modulesMonitored: 0,
    modulesMigratableSqlite: 0,
    totalRecords: 0,
    totalSizeBytes: 0,
    totalSizeLabel: '0 B',
    sqliteFragmentationPct: 0,
    statusCounts: {},
    generatedLabel: 'n.d.',
  },
  modules: [],
  sqlite: emptySqlite,
  usage: emptyUsage,
  actions: emptyActions,
  contracts: {
    mock_fallback: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
    legacy_fallback: 'Percorso di recupero',
  },
  warning: '',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim()
  return raw || fallback
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  const raw = text(value).toLowerCase()
  return value === true || value === 1 || raw === 'true' || raw === '1' || raw === 'si' || raw === 'yes'
}

function tone(value: unknown): Tone {
  const raw = text(value, 'neutral').toLowerCase()
  if (['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw)) return raw as Tone
  return 'neutral'
}

function statusFromPayload(value: unknown): AdminDatabaseStatus {
  const item = isRecord(value) ? value : {}
  return {
    code: text(item.code, 'OK'),
    label: text(item.label, 'OK'),
    tone: tone(item.tone),
    message: text(item.message),
  }
}

function moduleFromPayload(value: unknown, index: number): AdminDatabaseModule {
  const item = isRecord(value) ? value : {}
  const kind = isRecord(item.kind) ? item.kind : {}
  const id = text(item.id, text(item.name, `modulo-${index}`))
  return {
    id,
    name: text(item.name, id),
    label: text(item.label, id),
    path: text(item.path),
    exists: bool(item.exists),
    records: number(item.records),
    sizeBytes: number(item.sizeBytes),
    sizeLabel: text(item.sizeLabel, '0 B'),
    lastModified: text(item.lastModified),
    lastModifiedLabel: text(item.lastModifiedLabel, 'n.d.'),
    migratableSqlite: bool(item.migratableSqlite),
    authoritative: bool(item.authoritative),
    mirror: bool(item.mirror),
    kind: {
      label: text(kind.label, 'JSON'),
      tone: tone(kind.tone),
    },
    status: statusFromPayload(item.status),
  }
}

function usageItemFromPayload(value: unknown, index: number): { id: string; label: string; count: number } {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `uso-${index}`),
    label: text(item.label, 'n.d.'),
    count: number(item.count),
  }
}

function normalisePayload(payload: unknown): AdminDatabasePageData {
  if (!isRecord(payload)) return emptyAdminDatabasePage
  const page = isRecord(payload.page) ? payload.page : {}
  const summary = isRecord(payload.summary) ? payload.summary : {}
  const sourceTruthPayload = isRecord(payload.sourceTruth) ? payload.sourceTruth : {}
  const sqlite = isRecord(payload.sqlite) ? payload.sqlite : {}
  const usage = isRecord(payload.usage) ? payload.usage : {}
  const actions = isRecord(payload.actions) ? payload.actions : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const statusCounts = isRecord(summary.statusCounts) ? summary.statusCounts : {}
  const tables = Array.isArray(sqlite.tables)
    ? sqlite.tables.map((item) => {
      const row = isRecord(item) ? item : {}
      return { name: text(row.name, 'n.d.'), records: number(row.records) }
    })
    : []
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt),
    sourceTruth: {
      selectedMode: text(sourceTruthPayload.selectedMode, emptySourceTruth.selectedMode),
      effectiveMode: text(sourceTruthPayload.effectiveMode, emptySourceTruth.effectiveMode),
      authoritative: text(sourceTruthPayload.authoritative, emptySourceTruth.authoritative),
      sqlAuthoritative: bool(sourceTruthPayload.sqlAuthoritative),
      jsonRole: text(sourceTruthPayload.jsonRole, emptySourceTruth.jsonRole),
      status: text(sourceTruthPayload.status, emptySourceTruth.status),
      studioDbPath: text(sourceTruthPayload.studioDbPath, emptySourceTruth.studioDbPath),
      tenantSlug: text(sourceTruthPayload.tenantSlug, emptySourceTruth.tenantSlug),
    },
    page: {
      title: text(page.title, emptyAdminDatabasePage.page.title),
      subtitle: text(page.subtitle, emptyAdminDatabasePage.page.subtitle),
      path: text(page.path, '/admin/database'),
    },
    summary: {
      modulesMonitored: number(summary.modulesMonitored),
      modulesMigratableSqlite: number(summary.modulesMigratableSqlite),
      totalRecords: number(summary.totalRecords),
      totalSizeBytes: number(summary.totalSizeBytes),
      totalSizeLabel: text(summary.totalSizeLabel, '0 B'),
      sqliteFragmentationPct: number(summary.sqliteFragmentationPct),
      statusCounts: Object.fromEntries(Object.entries(statusCounts).map(([key, value]) => [key, number(value)])),
      generatedLabel: text(summary.generatedLabel, 'n.d.'),
    },
    modules: Array.isArray(payload.modules) ? payload.modules.map(moduleFromPayload) : [],
    sqlite: {
      exists: bool(sqlite.exists),
      error: text(sqlite.error),
      path: text(sqlite.path),
      role: text(sqlite.role),
      sizeLabel: text(sqlite.sizeLabel, 'n.d.'),
      sizeBytes: number(sqlite.sizeBytes),
      totalPages: number(sqlite.totalPages),
      freePages: number(sqlite.freePages),
      fragmentationPct: number(sqlite.fragmentationPct),
      pageSize: number(sqlite.pageSize),
      tables,
    },
    usage: {
      available: bool(usage.available),
      error: text(usage.error),
      totalEvents: number(usage.totalEvents),
      topActions: Array.isArray(usage.topActions) ? usage.topActions.map(usageItemFromPayload) : [],
      topUsers: Array.isArray(usage.topUsers) ? usage.topUsers.map(usageItemFromPayload) : [],
      peakHour: usage.peakHour === null || usage.peakHour === undefined ? null : number(usage.peakHour),
      errorRate: number(usage.errorRate),
      recentErrors: Array.isArray(usage.recentErrors)
        ? usage.recentErrors.filter(isRecord)
        : [],
    },
    actions: {
      refresh: text(actions.refresh, emptyActions.refresh),
      verify: text(actions.verify, emptyActions.verify),
      repair: text(actions.repair, emptyActions.repair),
      optimize: text(actions.optimize, emptyActions.optimize),
      migrate: text(actions.migrate, emptyActions.migrate),
      precheckSqlite: text(actions.precheckSqlite, emptyActions.precheckSqlite),
      reconcileSqlite: text(actions.reconcileSqlite, emptyActions.reconcileSqlite),
      activateSqlite: text(actions.activateSqlite, emptyActions.activateSqlite),
      exportZip: text(actions.exportZip, emptyActions.exportZip),
      backup: text(actions.backup, emptyActions.backup),
      audit: text(actions.audit, emptyActions.audit),
    },
    contracts: {
      mock_fallback: bool(contracts.mock_fallback),
      writes: text(contracts.writes, 'operational_routes'),
      route_owner: text(contracts.route_owner, 'react_shell'),
      legacy_fallback: text(contracts.legacy_fallback, 'Percorso di recupero'),
    },
    warning: text(payload.warning),
  }
}

export async function getAdminDatabasePage(): Promise<AdminDatabasePageData> {
  const params = new URLSearchParams()
  params.set('path', window.location.pathname)
  params.set('_ts', String(Date.now()))
  const response = await fetch(`/api/v1/ui/admin/database?${params.toString()}`, {
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error('Database amministrativo non disponibile')
  return normalisePayload(await response.json())
}
