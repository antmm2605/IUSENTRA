import type { Tone } from './data'
import { csrfHeader } from './api/csrf'

export type ScadenziarioView =
  | 'aperte'
  | 'critiche'
  | 'alte'
  | 'completate'
  | 'scadute'
  | 'imminenti'
  | 'avanzate'
  | 'operative'
  | 'pec'
  | 'da_presidiare'
  | 'tutte'

export type ScadenziarioPriority = 'CRITICA' | 'ALTA' | 'MEDIA' | 'BASSA'
export type ScadenziarioStatus = 'APERTO' | 'COMPLETATO' | 'ANNULLATO' | 'SCADUTO'
export type ScadenziarioActionKind = 'link' | 'filter' | 'bulk_complete' | 'lex'

export type ScadenziarioFacet = {
  value: string
  label: string
  count: number
}

export type ScadenziarioSummary = {
  total: number
  open: number
  critical: number
  high: number
  completed: number
  overdue: number
  within7: number
  advanced: number
  operative: number
  pec: number
  pec_open: number
  pec_overdue: number
  pec_future: number
  peremptory: number
}

export type DeadlineGuardianReason = {
  code: string
  label: string
  weight: number
  action: string
}

export type DeadlineGuardianItem = {
  id: string
  title: string
  date: string
  days: number | null
  peremptory: boolean
  fascicoloId: string
  ownerAssigned: boolean
  score: number
  band: string
  label: string
  tone: Tone
  primaryReason: string
  nextAction: string
  reasons: DeadlineGuardianReason[]
  href: string
}

export type DeadlineGuardian = {
  referenceDate: string
  summary: {
    total: number
    critical: number
    high: number
    medium: number
    unassigned: number
    sourceReview: number
  }
  items: DeadlineGuardianItem[]
  message: string
}

export type ScadenziarioRow = {
  id: string
  date: string
  dateLabel: string
  title: string
  description: string
  detailDescription: string
  type: string
  typeLabel: string
  priority: ScadenziarioPriority
  priorityLabel: string
  tone: Tone
  status: ScadenziarioStatus
  statusLabel: string
  days: number | null
  daysLabel: string
  overdue: boolean
  dueToday: boolean
  peremptory: boolean
  advanced: boolean
  operative: boolean
  operationalDueAt: string
  operationalDueLabel: string
  fascicoloId: string
  fascicoloLabel: string
  clientLabel: string
  ownerLabel: string
  sourceEventAt: string
  sourceEventLabel: string
  sourceEventType: string
  sourceEventTypeLabel: string
  sourceHref: string
  sourceLabel: string
  sourceKind: string
  sourceVerified: boolean
  officeLabel: string
  officeModeLabel: string
  officePatronLabel: string
  officeVerifiedAt: string
  octoberObservanceBlocks: boolean
  traceCount: number
  hearingMode: string
  hearingModeSource: string
  hearingTime: string
  remoteHearingDetected: boolean
  remoteHearingMode: string
  remoteHearingUrl: string
  remoteHearingSource: string
  remoteHearingVerified: boolean
  remoteHearingIntegrity: string
  remoteHearingTime: string
  remoteHearingPlatform: string
  remoteHearingMeetingId: string
  remoteHearingPasscode: string
  remoteHearingAccessInfo: string
  remoteHearingPdfRequired: boolean
  href: string
  editHref: string
  completeHref: string
  deleteHref: string
}

export type ScadenziarioDraftProposal = ScadenziarioRow & {
  sourceOrigin: 'pec' | 'registro'
  sourceOriginLabel: string
  sourceSnippet: string
  sourceSnippetLabel: string
  sourceDocumentName: string
  sourceConfidence: number
  confirmHref: string
  discardHref: string
}

export type ScadenziarioActionCard = {
  id: string
  title: string
  description: string
  value: number | string
  tone: Tone
  icon: 'alert' | 'calendar' | 'check' | 'calculator' | 'export' | 'lex' | 'archive'
  action: {
    kind: ScadenziarioActionKind
    label: string
    href?: string
    view?: ScadenziarioView
  }
}

export type DeadlineCalculatorTemplate = {
  code: string
  name: string
  displayName: string
  matter_type: string
  base_value: number
  period_type: 'days' | 'months'
  direction: 'forward' | 'backward'
  suspend_august: boolean
  ferial_suspension_policy: 'applies' | 'excluded' | 'partial' | 'manual_review'
  free_term: boolean
  urgent: boolean
  extend_saturday: boolean
  extend_holiday: boolean
  reference_law: string
  cartabia_compliant: boolean
  metadata: Record<string, unknown>
  version: number
}

export type DeadlineCalculatorResult = {
  calculationId: string
  deadline: string
  rawDeadline: string
  inputDate: string
  direction: 'forward' | 'backward'
  confidence: string
  requiresLegalReview: boolean
  template: DeadlineCalculatorTemplate
  templateVersion: number
  rulesetVersion: string
  calendarVersion: string
  engineVersion: string
  rulesApplied: string[]
  steps: { code: string; label: string; date: string }[]
  explanation: string
  resultHash: string
  audit?: { id: string; createdAt: string; immutableHash: string; isOverride: boolean }
  notificationPlan: { daysLeft: number; date: string; channel: string; status: string; idempotencyKey: string }[]
}

export type DeadlineCalculatorState = {
  templates: DeadlineCalculatorTemplate[]
  engineVersion: string
  rulesetVersion: string
  calendarVersion: string
  legalSources: { code: string; label: string; url: string }[]
  endpoints: {
    calculate: string
    explain: string
    validate: string
      audit: string
      override: string
      createDeadline: string
      pdfPreview: string
      pdfImport: string
    }
  scheduler: {
    thresholds: number[]
    channel: string
    mode: string
  }
}

export type ScadenziarioPageData = {
  generatedAt: string
  source: string
  contracts: {
    mock_fallback: boolean
    read_only: boolean
    writes: string
    route_owner: string
  }
  query: {
    view: ScadenziarioView
    q: string
    type: string
    priority: string
    from: string
    to: string
    peremptory: boolean
    advanced: boolean
    operative: boolean
    guidaPratica: string
    fascicoloId: string
    focusId: string
    compact: boolean
    includeCalculator: boolean
  }
  summary: ScadenziarioSummary
  items: ScadenziarioRow[]
  guardian: DeadlineGuardian
  draftProposals: ScadenziarioDraftProposal[]
  overduePreview: ScadenziarioRow[]
  nextItems: ScadenziarioRow[]
  operativeCards: ScadenziarioActionCard[]
  calculator: DeadlineCalculatorState
  facets: {
    views: ScadenziarioFacet[]
    types: ScadenziarioFacet[]
    priorities: ScadenziarioFacet[]
    statuses: ScadenziarioFacet[]
  }
  actions: {
    new: string
    exportCsv: string
    exportPdf: string
    exportIcs: string
    agenda: string
    calendarSettings: string
    lex: string
    bulkComplete: string
  }
}

export type ScadenziarioQuery = {
  view?: ScadenziarioView
  q?: string
  type?: string
  priority?: string
  from?: string
  to?: string
  peremptory?: boolean
  advanced?: boolean
  operative?: boolean
  guidaPratica?: string
  fascicoloId?: string
  focusId?: string
  compact?: boolean
  includeCalculator?: boolean
}

export type PdfDeadlineCandidate = {
  id: string
  fascicoloId: string
  fascicoloLabel: string
  documentId: string
  documentName: string
  documentHref: string
  page: number
  dueDate: string
  title: string
  description: string
  context: string
  type: string
  typeLabel: string
  confidence: number
  urls: string[]
  duplicate: boolean
  existingDeadlineId: string
  selected: boolean
  warnings: string[]
}

export type PdfDeadlinePreview = {
  ok: boolean
  candidates: PdfDeadlineCandidate[]
  summary: {
    scannedFascicoli: number
    scannedDocuments: number
    skippedDocuments: number
    newCandidates: number
    duplicates: number
    warnings: number
  }
  warnings: string[]
}

export type PdfDeadlineImportResult = {
  ok: boolean
  message: string
  created: number
  skipped: number
  items: { id: string; title: string; href: string }[]
}

export const emptyScadenziarioPage: ScadenziarioPageData = {
  generatedAt: '',
  source: 'empty',
  contracts: {
    mock_fallback: false,
    read_only: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
  },
  query: {
    view: 'aperte',
    q: '',
    type: '',
    priority: '',
    from: '',
    to: '',
    peremptory: false,
    advanced: false,
    operative: false,
    guidaPratica: '',
    fascicoloId: '',
    focusId: '',
    compact: false,
    includeCalculator: false,
  },
  summary: {
    total: 0,
    open: 0,
    critical: 0,
    high: 0,
    completed: 0,
    overdue: 0,
    within7: 0,
    advanced: 0,
    operative: 0,
    pec: 0,
    pec_open: 0,
    pec_overdue: 0,
    pec_future: 0,
    peremptory: 0,
  },
  items: [],
  guardian: {
    referenceDate: '',
    summary: { total: 0, critical: 0, high: 0, medium: 0, unassigned: 0, sourceReview: 0 },
    items: [],
    message: 'Il Guardiano valuta le scadenze aperte dello studio.',
  },
  draftProposals: [],
  overduePreview: [],
  nextItems: [],
  operativeCards: [],
  calculator: {
    templates: [],
    engineVersion: '',
    rulesetVersion: '',
    calendarVersion: '',
    legalSources: [],
    endpoints: {
      calculate: '/api/v1/ui/scadenziario/termini/calculate',
      explain: '/api/v1/ui/scadenziario/termini/explain',
      validate: '/api/v1/ui/scadenziario/termini/validate',
      audit: '/api/v1/ui/scadenziario/termini/audit',
      override: '/api/v1/ui/scadenziario/termini/override',
      createDeadline: '/api/v1/ui/scadenziario/termini/crea-scadenza',
      pdfPreview: '/api/v1/ui/scadenziario/pdf-scadenze/anteprima',
      pdfImport: '/api/v1/ui/scadenziario/pdf-scadenze/importa',
    },
    scheduler: {
      thresholds: [30, 15, 7, 1, 0],
      channel: 'PEC',
      mode: 'pianificazione_idempotente_con_audit',
    },
  },
  facets: {
    views: [
      { value: 'aperte', label: 'Aperte', count: 0 },
      { value: 'critiche', label: 'Critiche', count: 0 },
      { value: 'alte', label: 'Alta priorità', count: 0 },
      { value: 'completate', label: 'Completate', count: 0 },
      { value: 'scadute', label: 'Scadute', count: 0 },
      { value: 'imminenti', label: 'Entro 7 gg', count: 0 },
      { value: 'avanzate', label: 'Avanzate', count: 0 },
      { value: 'operative', label: 'Operative', count: 0 },
      { value: 'pec', label: 'Da PEC', count: 0 },
    ],
    types: [{ value: '', label: 'Tutti i tipi', count: 0 }],
    priorities: [{ value: '', label: 'Tutte le priorità', count: 0 }],
    statuses: [{ value: '', label: 'Tutti gli stati', count: 0 }],
  },
  actions: {
    new: '/scadenziario/nuova',
    exportCsv: '/scadenziario/export.csv',
    exportPdf: '/scadenziario/pdf',
    exportIcs: '/scadenziario/export.ics',
    agenda: '/agenda',
    calendarSettings: '/impostazioni/calendario',
    lex: '#lex',
    bulkComplete: '/scadenziario/bulk-completa',
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asString(value: unknown, fallback = ''): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value ?? fallback)
  return Number.isFinite(parsed) ? parsed : fallback
}

function asBoolean(value: unknown): boolean {
  if (typeof value === 'boolean') return value
  return ['1', 'true', 'yes', 'on', 'si', 'sì'].includes(String(value ?? '').trim().toLowerCase())
}

function asArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (isRecord(value) && Array.isArray(value.items)) return value.items
  if (isRecord(value) && Array.isArray(value.data)) return value.data
  return []
}

function safeView(value: unknown): ScadenziarioView {
  const text = asString(value, 'aperte')
  const allowed: ScadenziarioView[] = ['aperte', 'critiche', 'alte', 'completate', 'scadute', 'imminenti', 'avanzate', 'operative', 'pec', 'da_presidiare', 'tutte']
  return allowed.includes(text as ScadenziarioView) ? text as ScadenziarioView : 'aperte'
}

function safePriority(value: unknown): ScadenziarioPriority {
  const text = asString(value, 'MEDIA').toUpperCase()
  if (text === 'CRITICA' || text === 'ALTA' || text === 'MEDIA' || text === 'BASSA') return text
  return 'MEDIA'
}

function safeStatus(value: unknown): ScadenziarioStatus {
  const text = asString(value, 'APERTO').toUpperCase()
  if (text === 'APERTO' || text === 'COMPLETATO' || text === 'ANNULLATO' || text === 'SCADUTO') return text
  return 'APERTO'
}

function toneFromPriority(priority: ScadenziarioPriority, status: ScadenziarioStatus, overdue: boolean): Tone {
  if (status === 'COMPLETATO') return 'success'
  if (status === 'SCADUTO' || overdue || priority === 'CRITICA') return 'danger'
  if (priority === 'ALTA') return 'warning'
  if (priority === 'BASSA') return 'success'
  return 'primary'
}

function priorityLabel(priority: ScadenziarioPriority): string {
  if (priority === 'CRITICA') return 'Critica'
  if (priority === 'ALTA') return 'Alta'
  if (priority === 'BASSA') return 'Bassa'
  return 'Media'
}

function statusLabel(status: ScadenziarioStatus): string {
  if (status === 'COMPLETATO') return 'Completata'
  if (status === 'ANNULLATO') return 'Annullata'
  if (status === 'SCADUTO') return 'Scaduta'
  return 'Aperta'
}

function normalizeFacet(value: unknown): ScadenziarioFacet | null {
  if (!isRecord(value)) return null
  return {
    value: asString(value.value),
    label: asString(value.label, asString(value.value, 'Filtro')),
    count: asNumber(value.count),
  }
}

function normalizeFacets(value: unknown, fallback: ScadenziarioFacet[]): ScadenziarioFacet[] {
  const rows = asArray(value).map(normalizeFacet).filter(Boolean) as ScadenziarioFacet[]
  return rows.length ? rows : fallback
}

function normalizeRow(value: unknown, index = 0): ScadenziarioRow {
  const item = isRecord(value) ? value : {}
  const status = safeStatus(item.status)
  const priority = safePriority(item.priority)
  const daysRaw = item.days === null || item.days === undefined ? null : asNumber(item.days)
  const overdue = asBoolean(item.overdue) || status === 'SCADUTO' || (typeof daysRaw === 'number' && daysRaw < 0)
  const dueToday = asBoolean(item.dueToday) || daysRaw === 0
  const tone = asString(item.tone) as Tone || toneFromPriority(priority, status, overdue)
  return {
    id: asString(item.id, `scadenza-${index}`),
    date: asString(item.date),
    dateLabel: asString(item.dateLabel, asString(item.date, '-')),
    title: asString(item.title, 'Scadenza senza titolo'),
    description: asString(item.description),
    detailDescription: asString(item.detailDescription, asString(item.description)),
    type: asString(item.type, 'ALTRO'),
    typeLabel: asString(item.typeLabel, asString(item.type, 'Altro')),
    priority,
    priorityLabel: asString(item.priorityLabel, priorityLabel(priority)),
    tone,
    status,
    statusLabel: asString(item.statusLabel, statusLabel(status)),
    days: daysRaw,
    daysLabel: asString(item.daysLabel, typeof daysRaw === 'number' ? `${daysRaw} gg` : '-'),
    overdue,
    dueToday,
    peremptory: asBoolean(item.peremptory),
    advanced: asBoolean(item.advanced),
    operative: asBoolean(item.operative),
    operationalDueAt: asString(item.operationalDueAt),
    operationalDueLabel: asString(item.operationalDueLabel, asString(item.operationalDueAt, '-')),
    fascicoloId: asString(item.fascicoloId),
    fascicoloLabel: asString(item.fascicoloLabel, '-'),
    clientLabel: asString(item.clientLabel ?? item.client_label, '-'),
    ownerLabel: asString(item.ownerLabel, '-'),
    sourceEventAt: asString(item.sourceEventAt),
    sourceEventLabel: asString(item.sourceEventLabel),
    sourceEventType: asString(item.sourceEventType),
    sourceEventTypeLabel: asString(item.sourceEventTypeLabel),
    sourceHref: asString(item.sourceHref),
    sourceLabel: asString(item.sourceLabel),
    sourceKind: asString(item.sourceKind),
    sourceVerified: asBoolean(item.sourceVerified),
    officeLabel: asString(item.officeLabel),
    officeModeLabel: asString(item.officeModeLabel),
    officePatronLabel: asString(item.officePatronLabel),
    officeVerifiedAt: asString(item.officeVerifiedAt),
    octoberObservanceBlocks: asBoolean(item.octoberObservanceBlocks),
    traceCount: asNumber(item.traceCount),
    hearingMode: asString(item.hearingMode),
    hearingModeSource: asString(item.hearingModeSource),
    hearingTime: asString(item.hearingTime),
    remoteHearingDetected: asBoolean(item.remoteHearingDetected),
    remoteHearingMode: asString(item.remoteHearingMode),
    remoteHearingUrl: asString(item.remoteHearingUrl),
    remoteHearingSource: asString(item.remoteHearingSource),
    remoteHearingVerified: asBoolean(item.remoteHearingVerified),
    remoteHearingIntegrity: asString(item.remoteHearingIntegrity),
    remoteHearingTime: asString(item.remoteHearingTime),
    remoteHearingPlatform: asString(item.remoteHearingPlatform),
    remoteHearingMeetingId: asString(item.remoteHearingMeetingId),
    remoteHearingPasscode: asString(item.remoteHearingPasscode),
    remoteHearingAccessInfo: asString(item.remoteHearingAccessInfo),
    remoteHearingPdfRequired: asBoolean(item.remoteHearingPdfRequired),
    href: asString(item.href, `/scadenziario/${asString(item.id, '')}`),
    editHref: asString(item.editHref, `/scadenziario/${asString(item.id, '')}/modifica`),
    completeHref: asString(item.completeHref, `/scadenziario/${asString(item.id, '')}/completa`),
    deleteHref: asString(item.deleteHref, `/scadenziario/${asString(item.id, '')}/elimina`),
  }
}

const emptyPdfDeadlinePreview: PdfDeadlinePreview = {
  ok: true,
  candidates: [],
  summary: {
    scannedFascicoli: 0,
    scannedDocuments: 0,
    skippedDocuments: 0,
    newCandidates: 0,
    duplicates: 0,
    warnings: 0,
  },
  warnings: [],
}

function normalizePdfDeadlineCandidate(value: unknown): PdfDeadlineCandidate | null {
  if (!isRecord(value)) return null
  return {
    id: asString(value.id),
    fascicoloId: asString(value.fascicoloId ?? value.fascicolo_id),
    fascicoloLabel: asString(value.fascicoloLabel ?? value.fascicolo_label, 'Fascicolo'),
    documentId: asString(value.documentId ?? value.document_id),
    documentName: asString(value.documentName ?? value.document_name, 'Documento PDF'),
    documentHref: asString(value.documentHref ?? value.document_href),
    page: asNumber(value.page),
    dueDate: asString(value.dueDate ?? value.due_date),
    title: asString(value.title, 'Scadenza da PDF'),
    description: asString(value.description),
    context: asString(value.context),
    type: asString(value.type, 'ALTRO'),
    typeLabel: asString(value.typeLabel ?? value.type_label, 'Scadenza'),
    confidence: asNumber(value.confidence),
    urls: asArray(value.urls).map((item) => asString(item)).filter(Boolean),
    duplicate: asBoolean(value.duplicate),
    existingDeadlineId: asString(value.existingDeadlineId ?? value.existing_deadline_id),
    selected: value.selected === undefined ? !asBoolean(value.duplicate) : asBoolean(value.selected),
    warnings: asArray(value.warnings).map((item) => asString(item)).filter(Boolean),
  }
}

function normalizePdfDeadlinePreview(value: unknown): PdfDeadlinePreview {
  const payload = isRecord(value) ? value : {}
  const summary = isRecord(payload.summary) ? payload.summary : {}
  return {
    ok: payload.ok === undefined ? true : asBoolean(payload.ok),
    candidates: asArray(payload.candidates).map(normalizePdfDeadlineCandidate).filter(Boolean) as PdfDeadlineCandidate[],
    summary: {
      scannedFascicoli: asNumber(summary.scannedFascicoli ?? summary.scanned_fascicoli),
      scannedDocuments: asNumber(summary.scannedDocuments ?? summary.scanned_documents),
      skippedDocuments: asNumber(summary.skippedDocuments ?? summary.skipped_documents),
      newCandidates: asNumber(summary.newCandidates ?? summary.new_candidates),
      duplicates: asNumber(summary.duplicates),
      warnings: asNumber(summary.warnings),
    },
    warnings: asArray(payload.warnings).map((item) => asString(item)).filter(Boolean),
  }
}

function normalizeSummary(value: unknown): ScadenziarioSummary {
  if (!isRecord(value)) return emptyScadenziarioPage.summary
  return {
    total: asNumber(value.total),
    open: asNumber(value.open),
    critical: asNumber(value.critical),
    high: asNumber(value.high),
    completed: asNumber(value.completed),
    overdue: asNumber(value.overdue),
    within7: asNumber(value.within7),
    advanced: asNumber(value.advanced),
    operative: asNumber(value.operative),
    pec: asNumber(value.pec),
    pec_open: asNumber(value.pec_open),
    pec_overdue: asNumber(value.pec_overdue),
    pec_future: asNumber(value.pec_future),
    peremptory: asNumber(value.peremptory),
  }
}

function normalizeGuardian(value: unknown): DeadlineGuardian {
  const payload = isRecord(value) ? value : {}
  const summary = isRecord(payload.summary) ? payload.summary : {}
  return {
    referenceDate: asString(payload.referenceDate ?? payload.reference_date),
    summary: {
      total: asNumber(summary.total), critical: asNumber(summary.critical), high: asNumber(summary.high), medium: asNumber(summary.medium), unassigned: asNumber(summary.unassigned), sourceReview: asNumber(summary.sourceReview ?? summary.source_review),
    },
    items: asArray(payload.items).map((value, index) => {
      const item = isRecord(value) ? value : {}
      return {
        id: asString(item.id, `guardian-${index}`), title: asString(item.title, 'Scadenza senza titolo'), date: asString(item.date), days: item.days === null || item.days === undefined ? null : asNumber(item.days),
        peremptory: asBoolean(item.peremptory), fascicoloId: asString(item.fascicoloId ?? item.fascicolo_id), ownerAssigned: asBoolean(item.ownerAssigned ?? item.owner_assigned),
        score: asNumber(item.score), band: asString(item.band, 'medio'), label: asString(item.label, 'Da presidiare'), tone: asString(item.tone, 'info') as Tone,
        primaryReason: asString(item.primaryReason ?? item.primary_reason), nextAction: asString(item.nextAction ?? item.next_action),
        reasons: asArray(item.reasons).map((value) => {
          const reason = isRecord(value) ? value : {}
          return { code: asString(reason.code), label: asString(reason.label), weight: asNumber(reason.weight), action: asString(reason.action) }
        }),
        href: asString(item.href, '/scadenziario'),
      }
    }),
    message: asString(payload.message, emptyScadenziarioPage.guardian.message),
  }
}

function normalizeCard(value: unknown, index = 0): ScadenziarioActionCard | null {
  if (!isRecord(value)) return null
  const action = isRecord(value.action) ? value.action : {}
  const kind = asString(action.kind, 'link') as ScadenziarioActionKind
  return {
    id: asString(value.id, `card-${index}`),
    title: asString(value.title, 'Card operativa'),
    description: asString(value.description),
    value: value.value === undefined ? '' : (asString(value.value) || asNumber(value.value)),
    tone: asString(value.tone, 'primary') as Tone,
    icon: asString(value.icon, 'calendar') as ScadenziarioActionCard['icon'],
    action: {
      kind: ['link', 'filter', 'bulk_complete', 'lex'].includes(kind) ? kind : 'link',
      label: asString(action.label, 'Apri'),
      href: asString(action.href),
      view: action.view ? safeView(action.view) : undefined,
    },
  }
}

function normalizeCards(value: unknown): ScadenziarioActionCard[] {
  return asArray(value).map(normalizeCard).filter(Boolean) as ScadenziarioActionCard[]
}

function normalizeTemplate(value: unknown): DeadlineCalculatorTemplate | null {
  if (!isRecord(value)) return null
  const period = asString(value.period_type, 'days')
  const direction = asString(value.direction, 'forward')
  const policy = asString(value.ferial_suspension_policy, 'applies')
  return {
    code: asString(value.code),
    name: asString(value.name, 'Termine processuale'),
    displayName: asString(value.displayName || value.display_name || value.name, 'Termine processuale'),
    matter_type: asString(value.matter_type, 'civil'),
    base_value: asNumber(value.base_value, 30),
    period_type: period === 'months' ? 'months' : 'days',
    direction: direction === 'backward' ? 'backward' : 'forward',
    suspend_august: asBoolean(value.suspend_august),
    ferial_suspension_policy: (['applies', 'excluded', 'partial', 'manual_review'].includes(policy) ? policy : 'applies') as DeadlineCalculatorTemplate['ferial_suspension_policy'],
    free_term: asBoolean(value.free_term),
    urgent: asBoolean(value.urgent),
    extend_saturday: value.extend_saturday === undefined ? true : asBoolean(value.extend_saturday),
    extend_holiday: value.extend_holiday === undefined ? true : asBoolean(value.extend_holiday),
    reference_law: asString(value.reference_law),
    cartabia_compliant: value.cartabia_compliant === undefined ? true : asBoolean(value.cartabia_compliant),
    metadata: isRecord(value.metadata) ? value.metadata : {},
    version: asNumber(value.version, 1),
  }
}

function normalizeCalculator(value: unknown): DeadlineCalculatorState {
  const payload = isRecord(value) ? value : {}
  const endpoints = isRecord(payload.endpoints) ? payload.endpoints : {}
  const scheduler = isRecord(payload.scheduler) ? payload.scheduler : {}
  return {
    templates: asArray(payload.templates).map(normalizeTemplate).filter(Boolean) as DeadlineCalculatorTemplate[],
    engineVersion: asString(payload.engineVersion),
    rulesetVersion: asString(payload.rulesetVersion),
    calendarVersion: asString(payload.calendarVersion),
    legalSources: asArray(payload.legalSources).filter(isRecord).map((source) => ({
      code: asString(source.code),
      label: asString(source.label),
      url: asString(source.url),
    })),
    endpoints: {
      calculate: asString(endpoints.calculate, emptyScadenziarioPage.calculator.endpoints.calculate),
      explain: asString(endpoints.explain, emptyScadenziarioPage.calculator.endpoints.explain),
      validate: asString(endpoints.validate, emptyScadenziarioPage.calculator.endpoints.validate),
      audit: asString(endpoints.audit, emptyScadenziarioPage.calculator.endpoints.audit),
      override: asString(endpoints.override, emptyScadenziarioPage.calculator.endpoints.override),
      createDeadline: asString(endpoints.createDeadline, emptyScadenziarioPage.calculator.endpoints.createDeadline),
      pdfPreview: asString(endpoints.pdfPreview, emptyScadenziarioPage.calculator.endpoints.pdfPreview),
      pdfImport: asString(endpoints.pdfImport, emptyScadenziarioPage.calculator.endpoints.pdfImport),
    },
    scheduler: {
      thresholds: asArray(scheduler.thresholds).map((item) => asNumber(item)).filter((item) => item >= 0),
      channel: asString(scheduler.channel, 'PEC'),
      mode: asString(scheduler.mode, 'pianificazione_idempotente_con_audit'),
    },
  }
}

function normalizeCalculationResult(value: unknown): DeadlineCalculatorResult | null {
  const payload = isRecord(value) ? value : {}
  const template = normalizeTemplate(payload.template)
  if (!template) return null
  const audit = isRecord(payload.audit) ? payload.audit : undefined
  return {
    calculationId: asString(payload.calculationId),
    deadline: asString(payload.deadline),
    rawDeadline: asString(payload.rawDeadline),
    inputDate: asString(payload.inputDate),
    direction: asString(payload.direction, 'forward') === 'backward' ? 'backward' : 'forward',
    confidence: asString(payload.confidence, 'media'),
    requiresLegalReview: asBoolean(payload.requiresLegalReview),
    template,
    templateVersion: asNumber(payload.templateVersion, template.version),
    rulesetVersion: asString(payload.rulesetVersion),
    calendarVersion: asString(payload.calendarVersion),
    engineVersion: asString(payload.engineVersion),
    rulesApplied: asArray(payload.rulesApplied).map((item) => asString(item)).filter(Boolean),
    steps: asArray(payload.steps).filter(isRecord).map((step) => ({ code: asString(step.code), label: asString(step.label), date: asString(step.date) })),
    explanation: asString(payload.explanation),
    resultHash: asString(payload.resultHash),
    audit: audit ? { id: asString(audit.id), createdAt: asString(audit.createdAt), immutableHash: asString(audit.immutableHash), isOverride: asBoolean(audit.isOverride) } : undefined,
    notificationPlan: asArray(payload.notificationPlan).filter(isRecord).map((row) => ({
      daysLeft: asNumber(row.daysLeft),
      date: asString(row.date),
      channel: asString(row.channel, 'PEC'),
      status: asString(row.status),
      idempotencyKey: asString(row.idempotencyKey),
    })),
  }
}

function queryParams(query: ScadenziarioQuery): string {
  const params = new URLSearchParams()
  if (query.view) params.set('vista', query.view)
  if (query.q?.trim()) params.set('q', query.q.trim())
  if (query.type) params.set('tipo', query.type)
  if (query.priority) params.set('priorita', query.priority)
  if (query.from) params.set('dal', query.from)
  if (query.to) params.set('al', query.to)
  if (query.peremptory) params.set('perentorio', '1')
  if (query.advanced) params.set('avanzate', '1')
  if (query.operative) params.set('operative', '1')
  if (query.guidaPratica) params.set('guida_pratica', query.guidaPratica)
  if (query.fascicoloId) params.set('id_fascicolo', query.fascicoloId)
  if (query.focusId) params.set('focus_id', query.focusId)
  if (query.compact) params.set('compatto', '1')
  if (query.includeCalculator === false) params.set('calcolatore', '0')
  return params.toString()
}

export async function getScadenziarioPage(query: ScadenziarioQuery = {}): Promise<ScadenziarioPageData> {
  try {
    const qs = queryParams(query)
    const response = await fetch(`/api/v1/ui/scadenziario${qs ? `?${qs}` : ''}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyScadenziarioPage
    const payload = await response.json() as unknown
    if (!isRecord(payload)) return emptyScadenziarioPage
    const facets = isRecord(payload.facets) ? payload.facets : {}
    const queryPayload = isRecord(payload.query) ? payload.query : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    return {
      generatedAt: asString(payload.generatedAt),
      source: asString(payload.source, 'repository_reali'),
      contracts: isRecord(payload.contracts) ? {
        mock_fallback: asBoolean(payload.contracts.mock_fallback),
        read_only: asBoolean(payload.contracts.read_only),
        writes: asString(payload.contracts.writes, 'operational_routes'),
        route_owner: asString(payload.contracts.route_owner, 'react_shell'),
      } : emptyScadenziarioPage.contracts,
      query: {
        view: safeView(queryPayload.view),
        q: asString(queryPayload.q),
        type: asString(queryPayload.type),
        priority: asString(queryPayload.priority),
        from: asString(queryPayload.from),
        to: asString(queryPayload.to),
        peremptory: asBoolean(queryPayload.peremptory),
        advanced: asBoolean(queryPayload.advanced),
        operative: asBoolean(queryPayload.operative),
        guidaPratica: asString(queryPayload.guidaPratica ?? queryPayload.guida_pratica),
        fascicoloId: asString(queryPayload.fascicoloId ?? queryPayload.id_fascicolo),
        focusId: asString(queryPayload.focusId ?? queryPayload.focus_id),
        compact: asBoolean(queryPayload.compact),
        includeCalculator: asBoolean(queryPayload.includeCalculator ?? queryPayload.include_calculator),
      },
      summary: normalizeSummary(payload.summary),
      items: asArray(payload.items).map(normalizeRow),
      guardian: normalizeGuardian(payload.guardian),
      draftProposals: asArray(payload.draftProposals).map((raw) => {
        const item = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
        return {
          ...normalizeRow(raw),
          sourceOrigin: asString(item.sourceOrigin) === 'registro' ? 'registro' as const : 'pec' as const,
          sourceOriginLabel: asString(item.sourceOriginLabel) || 'PEC',
          sourceSnippet: asString(item.sourceSnippet),
          sourceSnippetLabel: asString(item.sourceSnippetLabel),
          sourceDocumentName: asString(item.sourceDocumentName),
          sourceConfidence: asNumber(item.sourceConfidence),
          confirmHref: asString(item.confirmHref),
          discardHref: asString(item.discardHref),
        }
      }),
      overduePreview: asArray(payload.overduePreview).map(normalizeRow),
      nextItems: asArray(payload.nextItems).map(normalizeRow),
      operativeCards: normalizeCards(payload.operativeCards),
      calculator: normalizeCalculator(payload.calculator),
      facets: {
        views: normalizeFacets(facets.views, emptyScadenziarioPage.facets.views),
        types: normalizeFacets(facets.types, emptyScadenziarioPage.facets.types),
        priorities: normalizeFacets(facets.priorities, emptyScadenziarioPage.facets.priorities),
        statuses: normalizeFacets(facets.statuses, emptyScadenziarioPage.facets.statuses),
      },
      actions: {
        new: asString(actions.new, emptyScadenziarioPage.actions.new),
        exportCsv: asString(actions.exportCsv, emptyScadenziarioPage.actions.exportCsv),
        exportPdf: asString(actions.exportPdf, emptyScadenziarioPage.actions.exportPdf),
        exportIcs: asString(actions.exportIcs, emptyScadenziarioPage.actions.exportIcs),
        agenda: asString(actions.agenda, emptyScadenziarioPage.actions.agenda),
        calendarSettings: asString(actions.calendarSettings, emptyScadenziarioPage.actions.calendarSettings),
        lex: asString(actions.lex, emptyScadenziarioPage.actions.lex),
        bulkComplete: asString(actions.bulkComplete, emptyScadenziarioPage.actions.bulkComplete),
      },
    }
  } catch {
    return emptyScadenziarioPage
  }
}

export async function getDeadlineCalculator(filters: { guidaPratica?: string } = {}): Promise<DeadlineCalculatorState> {
  try {
    const params = new URLSearchParams()
    if (filters.guidaPratica) params.set('guida_pratica', filters.guidaPratica)
    const query = params.toString()
    const response = await fetch(`/api/v1/ui/scadenziario/termini/templates${query ? `?${query}` : ''}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyScadenziarioPage.calculator
    const payload = await response.json() as unknown
    return normalizeCalculator(payload)
  } catch {
    return emptyScadenziarioPage.calculator
  }
}

export async function calculateProcessDeadline(endpoint: string, body: Record<string, unknown>): Promise<DeadlineCalculatorResult> {
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(body),
  })
  const payload = await response.json() as unknown
  const record = isRecord(payload) ? payload : {}
  if (!response.ok || record.ok === false) throw new Error(asString(record.errore, 'Calcolo termine non riuscito'))
  const result = normalizeCalculationResult(record.result)
  if (!result) throw new Error('Risposta calcolo non valida')
  return result
}

export async function createProcessDeadline(endpoint: string, body: Record<string, unknown>): Promise<{ id: string; href: string; messaggio: string }> {
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(body),
  })
  const payload = await response.json() as unknown
  const record = isRecord(payload) ? payload : {}
  if (!response.ok || record.ok === false) throw new Error(asString(record.errore, 'Creazione scadenza non riuscita'))
  return {
    id: asString(record.id),
    href: asString(record.href, '/scadenziario'),
    messaggio: asString(record.messaggio, 'Scadenza creata.'),
  }
}

export async function previewPdfDeadlines(endpoint: string, options: { fascicoloId?: string; maxDocuments?: number } = {}): Promise<PdfDeadlinePreview> {
  const params = new URLSearchParams()
  if (options.fascicoloId) params.set('fascicoloId', options.fascicoloId)
  if (options.maxDocuments !== undefined) params.set('maxDocuments', String(options.maxDocuments))
  const response = await fetch(`${endpoint}${params.toString() ? `?${params.toString()}` : ''}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  const payload = await response.json() as unknown
  const record = isRecord(payload) ? payload : {}
  if (!response.ok || record.ok === false) throw new Error(asString(record.errore ?? record.message, 'Scansione PDF non completata'))
  return normalizePdfDeadlinePreview(record)
}

export async function importPdfDeadlines(endpoint: string, selectedIds: string[], options: { fascicoloId?: string; maxDocuments?: number } = {}): Promise<PdfDeadlineImportResult> {
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...csrfHeader(),
    },
    body: JSON.stringify({
      selectedIds,
      fascicoloId: options.fascicoloId || '',
      maxDocuments: options.maxDocuments || 0,
    }),
  })
  const payload = await response.json() as unknown
  const record = isRecord(payload) ? payload : {}
  if (!response.ok || record.ok === false) throw new Error(asString(record.errore ?? record.message, 'Importazione PDF non completata'))
  return {
    ok: asBoolean(record.ok),
    message: asString(record.message, 'Importazione completata.'),
    created: asNumber(record.created),
    skipped: asNumber(record.skipped),
    items: asArray(record.items).filter(isRecord).map((item) => ({
      id: asString(item.id),
      title: asString(item.title),
      href: asString(item.href, '/scadenziario'),
    })),
  }
}
