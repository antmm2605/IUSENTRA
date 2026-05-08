import { apiJson, apiPostJson } from './lib/apiClient'
import {
  sanitizePayload,
  tone,
  type ReactOperationalContract,
  type RouteAction,
  type WarningItem,
} from './studioData'
import type { AdminTone } from './utentiData'

export type SitoStudioSite = {
  id: number
  tenantSlug: string
  studioName: string
  siteName: string
  publicSlug: string
  title: string
  description: string
  claim: string
  contactEmail: string
  contactPhone: string
  address: string
  city: string
  province: string
  zipCode: string
  published: boolean
  active: boolean
  updatedAt: string
  publicUrl: string
  showLegalTools: boolean
  showApplications: boolean
  showLegalNews: boolean
}

export type SitoPageItem = {
  id: string
  kind: 'page' | 'article' | 'service' | 'professional' | 'office' | 'unknown'
  title: string
  subtitle: string
  status: string
  statusTone: AdminTone
  meta: Array<{ label: string; value: string }>
}

export type SitoPreviewInfo = {
  href: string
  label: string
  safe: boolean
}

export type SitoMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: AdminTone
}

export type SitoContattoRow = {
  id: string
  fullName: string
  email: string
  phone: string
  subject: string
  message: string
  createdAt: string
  status: string
  statusLabel: string
  statusTone: AdminTone
  leadClienteId: string
  clientHref: string
  actions: {
    canLinkClient: boolean
    linkEndpoint: string
  }
}

export type SitoBookingRow = {
  id: string
  customerName: string
  email: string
  phone: string
  subject: string
  notes: string
  requestedAt: string
  createdAt: string
  officeName: string
  status: string
  statusLabel: string
  statusTone: AdminTone
  agendaEventId: string
  actions: {
    canUpdateStatus: boolean
    statusEndpoint: string
  }
}

export type SitoContattoStatus = {
  value: string
  label: string
  mutable: boolean
}

export type SitoContattiPermissions = {
  canRead: boolean
  canUpdateStatus: boolean
  canArchive: boolean
  canAddNote: boolean
  canAssign: boolean
  canLinkClient: boolean
  canLinkMatter: boolean
  canUpdateBookingStatus: boolean
  unsupportedReason: string
  rollback?: {
    label: string
    href: string
    method: 'GET'
  }
}

export type SitoContattoMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item?: SitoContattoRow | SitoBookingRow | null
}

export type SitoStudioPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: ReactOperationalContract
  site: SitoStudioSite
  pages: SitoPageItem[]
  metrics: SitoMetric[]
  preview: SitoPreviewInfo
  actions: RouteAction[]
  legacy_routes: RouteAction[]
  warnings: WarningItem[]
}

export type SitoStudioContattiPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: ReactOperationalContract
  contacts: SitoContattoRow[]
  bookings: SitoBookingRow[]
  statuses: SitoContattoStatus[]
  assignees: Array<{ id: string; label: string }>
  clients: Array<{ id: string; label: string }>
  matters: Array<{ id: string; label: string }>
  actions: SitoContattiPermissions
  warnings: WarningItem[]
}

export const emptySitoStudioPage: SitoStudioPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
    operational: true,
    builder: 'legacy_protected',
    publishing: 'legacy_protected',
  },
  site: {
    id: 0,
    tenantSlug: '',
    studioName: '',
    siteName: '',
    publicSlug: '',
    title: '',
    description: '',
    claim: '',
    contactEmail: '',
    contactPhone: '',
    address: '',
    city: '',
    province: '',
    zipCode: '',
    published: false,
    active: false,
    updatedAt: '',
    publicUrl: '',
    showLegalTools: false,
    showApplications: false,
    showLegalNews: false,
  },
  pages: [],
  metrics: [],
  preview: {
    href: '',
    label: '',
    safe: false,
  },
  actions: [],
  legacy_routes: [],
  warnings: [],
}

export const emptySitoStudioContattiPage: SitoStudioContattiPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
    operational: true,
    notifications: 'legacy_protected',
    automation: 'legacy_protected',
  },
  contacts: [],
  bookings: [],
  statuses: [],
  assignees: [],
  clients: [],
  matters: [],
  actions: {
    canRead: false,
    canUpdateStatus: false,
    canArchive: false,
    canAddNote: false,
    canAssign: false,
    canLinkClient: false,
    canLinkMatter: false,
    canUpdateBookingStatus: false,
    unsupportedReason: '',
  },
  warnings: [],
}

const unsupportedMutation: SitoContattoMutationResult = {
  ok: false,
  message: 'Azione non supportata dal backend legacy corrente.',
  errors: { action: 'Azione non supportata.' },
  item: null,
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

function normaliseContract(raw: unknown, writes: string): ReactOperationalContract {
  const item = asRecord(raw)
  return {
    mock_fallback: bool(item.mock_fallback),
    writes: text(item.writes) || writes,
    route_owner: text(item.route_owner) || 'react_shell',
    operational: item.operational === false ? false : true,
    builder: text(item.builder),
    publishing: text(item.publishing),
    notifications: text(item.notifications),
    automation: text(item.automation),
    legacy_contract: text(item.legacy_contract),
  }
}

function normaliseWarning(raw: unknown): WarningItem {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseMetric(raw: unknown): SitoMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: text(item.label) || 'Metrica',
    value: value(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseAction(raw: unknown): RouteAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: text(item.href),
    method: 'GET',
    tone: tone(item.tone),
    protected: bool(item.protected),
  }
}

function normaliseSite(raw: unknown): SitoStudioSite {
  const item = asRecord(raw)
  return {
    id: number(item.id),
    tenantSlug: text(item.tenantSlug),
    studioName: text(item.studioName),
    siteName: text(item.siteName),
    publicSlug: text(item.publicSlug),
    title: text(item.title),
    description: text(item.description),
    claim: text(item.claim),
    contactEmail: text(item.contactEmail),
    contactPhone: text(item.contactPhone),
    address: text(item.address),
    city: text(item.city),
    province: text(item.province),
    zipCode: text(item.zipCode),
    published: bool(item.published),
    active: bool(item.active),
    updatedAt: text(item.updatedAt),
    publicUrl: text(item.publicUrl),
    showLegalTools: bool(item.showLegalTools),
    showApplications: bool(item.showApplications),
    showLegalNews: bool(item.showLegalNews),
  }
}

function normalisePageItem(raw: unknown): SitoPageItem {
  const item = asRecord(raw)
  const kind = ['page', 'article', 'service', 'professional', 'office'].includes(String(item.kind))
    ? String(item.kind) as SitoPageItem['kind']
    : 'unknown'
  return {
    id: text(item.id),
    kind,
    title: text(item.title) || 'Elemento sito',
    subtitle: text(item.subtitle),
    status: text(item.status),
    statusTone: tone(item.statusTone),
    meta: list(item.meta).map((rawMeta) => {
      const meta = asRecord(rawMeta)
      return { label: text(meta.label), value: text(meta.value) }
    }).filter((entry) => entry.label || entry.value),
  }
}

function normaliseContact(raw: unknown): SitoContattoRow {
  const item = asRecord(raw)
  const actions = asRecord(item.actions)
  return {
    id: text(item.id),
    fullName: text(item.fullName),
    email: text(item.email),
    phone: text(item.phone),
    subject: text(item.subject),
    message: text(item.message),
    createdAt: text(item.createdAt),
    status: text(item.status),
    statusLabel: text(item.statusLabel) || text(item.status),
    statusTone: tone(item.statusTone),
    leadClienteId: text(item.leadClienteId),
    clientHref: text(item.clientHref),
    actions: {
      canLinkClient: bool(actions.canLinkClient),
      linkEndpoint: text(actions.linkEndpoint),
    },
  }
}

function normaliseBooking(raw: unknown): SitoBookingRow {
  const item = asRecord(raw)
  const actions = asRecord(item.actions)
  return {
    id: text(item.id),
    customerName: text(item.customerName),
    email: text(item.email),
    phone: text(item.phone),
    subject: text(item.subject),
    notes: text(item.notes),
    requestedAt: text(item.requestedAt),
    createdAt: text(item.createdAt),
    officeName: text(item.officeName),
    status: text(item.status),
    statusLabel: text(item.statusLabel) || text(item.status),
    statusTone: tone(item.statusTone),
    agendaEventId: text(item.agendaEventId),
    actions: {
      canUpdateStatus: bool(actions.canUpdateStatus),
      statusEndpoint: text(actions.statusEndpoint),
    },
  }
}

function normaliseStatus(raw: unknown): SitoContattoStatus {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: text(item.label),
    mutable: bool(item.mutable),
  }
}

function normaliseOption(raw: unknown): { id: string; label: string } {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    label: text(item.label),
  }
}

function normalisePermissions(raw: unknown): SitoContattiPermissions {
  const item = asRecord(raw)
  const rollback = asRecord(item.rollback)
  return {
    canRead: bool(item.canRead),
    canUpdateStatus: bool(item.canUpdateStatus),
    canArchive: bool(item.canArchive),
    canAddNote: bool(item.canAddNote),
    canAssign: bool(item.canAssign),
    canLinkClient: bool(item.canLinkClient),
    canLinkMatter: bool(item.canLinkMatter),
    canUpdateBookingStatus: bool(item.canUpdateBookingStatus),
    unsupportedReason: text(item.unsupportedReason),
    rollback: text(rollback.href)
      ? { label: text(rollback.label) || 'Rollback tecnico legacy', href: text(rollback.href), method: 'GET' }
      : undefined,
  }
}

function normaliseMutation(raw: unknown): SitoContattoMutationResult {
  const item = asRecord(sanitizePayload(raw))
  const row = item.item
  return {
    ok: bool(item.ok),
    message: text(item.message) || (bool(item.ok) ? 'Operazione completata.' : 'Operazione non completata.'),
    errors: Object.fromEntries(Object.entries(asRecord(item.errors)).map(([key, entry]) => [key, text(entry)])),
    item: row ? ('customerName' in asRecord(row) ? normaliseBooking(row) : normaliseContact(row)) : null,
  }
}

function normaliseSitoStudioPage(raw: unknown): SitoStudioPageData {
  const page = asRecord(sanitizePayload(raw))
  const preview = asRecord(page.preview)
  return {
    ok: bool(page.ok),
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContract(page.contracts, 'none'),
    site: normaliseSite(page.site),
    pages: list(page.pages).map(normalisePageItem),
    metrics: list(page.metrics).map(normaliseMetric),
    preview: {
      href: text(preview.href),
      label: text(preview.label),
      safe: bool(preview.safe),
    },
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    legacy_routes: list(page.legacy_routes).map(normaliseAction).filter((action) => action.href),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseSitoContattiPage(raw: unknown): SitoStudioContattiPageData {
  const page = asRecord(sanitizePayload(raw))
  return {
    ok: bool(page.ok),
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContract(page.contracts, 'json_api'),
    contacts: list(page.contacts).map(normaliseContact),
    bookings: list(page.bookings).map(normaliseBooking),
    statuses: list(page.statuses).map(normaliseStatus),
    assignees: list(page.assignees).map(normaliseOption),
    clients: list(page.clients).map(normaliseOption).filter((item) => item.id),
    matters: list(page.matters).map(normaliseOption).filter((item) => item.id),
    actions: normalisePermissions(page.actions),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getSitoStudioPage(): Promise<SitoStudioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/sito-studio', emptySitoStudioPage)
  return normaliseSitoStudioPage(payload)
}

export async function getSitoStudioContattiPage(): Promise<SitoStudioContattiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/sito-studio/contatti', emptySitoStudioContattiPage)
  return normaliseSitoContattiPage(payload)
}

export async function updateSitoContattoStatus(): Promise<SitoContattoMutationResult> {
  return unsupportedMutation
}

export async function archiveSitoContatto(): Promise<SitoContattoMutationResult> {
  return unsupportedMutation
}

export async function addSitoContattoNote(): Promise<SitoContattoMutationResult> {
  return unsupportedMutation
}

export async function assignSitoContatto(): Promise<SitoContattoMutationResult> {
  return unsupportedMutation
}

export async function linkSitoContatto(
  idContatto: string,
  payload: { mode?: 'create_lead'; cliente_id?: string } = { mode: 'create_lead' },
): Promise<SitoContattoMutationResult> {
  const result = await apiPostJson<unknown>(
    `/api/v1/ui/sito-studio/contatti/${encodeURIComponent(idContatto)}/collega`,
    payload,
    unsupportedMutation,
  )
  return normaliseMutation(result)
}

export async function updateSitoBookingStatus(
  idPrenotazione: string,
  status: 'approved' | 'rejected',
): Promise<SitoContattoMutationResult> {
  const result = await apiPostJson<unknown>(
    `/api/v1/ui/sito-studio/prenotazioni/${encodeURIComponent(idPrenotazione)}/stato`,
    { status },
    unsupportedMutation,
  )
  return normaliseMutation(result)
}
