import type { Tone } from './data'
import type { ReactContracts } from './timesheetData'

export type WizardProSession = {
  id: string
  title: string
  status: string
  statusLabel: string
  step: number
  progress: number
  modifiedAt: string
  modifiedAtLabel: string
  completedAt: string
  completedAtLabel: string
  stepHref: string
  summaryHref: string
  archiveHref: string
  deleteHref: string
}

export type WizardProCase = {
  id: string
  number: string
  title: string
  client: string
  opponent: string
  matter: string
  court: string
  rg: string
  judge: string
  section: string
  hearingLabel: string
  hearingRaw: string
  hearingDays: number | null
  hearingMode: string
  hearingType: string
  statusLabel: string
  statusTone: Tone
  progress: number
  progressLabel: string
  documentsReady: number
  documentsMissing: number
  openActivities: number
  linkedDeadlines: number
  badges: Array<{ label: string; tone: Tone }>
  parts: Array<{ ruolo?: string; role?: string; nome?: string; name?: string }>
  activeSession: WizardProSession | null
  completedSession: WizardProSession | null
  href: string
  folderHref: string
  agendaHref: string
  deadlineHref: string
  startHref: string
  startPayload: { id_fascicolo: string; id_appuntamento: string }
}

export type WizardProSummary = {
  totalCases: number
  activeDrafts: number
  completed: number
  upcomingHearings: number
  documentsReady: number
  documentsMissing: number
  linkedDeadlines: number
}

export type WizardProActions = {
  start: string
  agenda: string
  deadlines: string
  newDeadline: string
  newAppointment: string
  lex: string
}

export type WizardProData = {
  source: string
  contracts: ReactContracts
  summary: WizardProSummary
  steps: string[]
  cases: WizardProCase[]
  selectedCase: WizardProCase | null
  recentDrafts: Array<{ session: WizardProSession | null; caseTitle: string; client: string; court: string }>
  recentCompleted: Array<{ session: WizardProSession | null; caseTitle: string; client: string; court: string }>
  filters: Record<string, string[]>
  actions: WizardProActions
}

export type WizardProStepStatus = {
  n: number
  label: string
  icon: string
  confirmed: boolean
  active: boolean
  href: string
  available: boolean
}

export type WizardProMatter = {
  id: string
  number: string
  title: string
  client: string
  opponent: string
  matter: string
  court: string
  rg: string
  judge: string
  section: string
  status: string
  statusLabel: string
  nextHearing: string
  nextHearingLabel: string
  documentsCount: number
  href: string
  documentsHref: string
  timesheetHref: string
  deadlineHref: string
}

export type WizardProAppointment = {
  id: string
  title: string
  date: string
  dateLabel: string
  place: string
  notes: string
  href: string
}

export type WizardProDocument = {
  index: number
  idDocument: string
  label: string
  type: string
  mandatory: boolean
  status: string
  statusLabel: string
  statusTone: Tone
  notes: string
  fileName: string
  signed: boolean
  href: string
}

export type WizardProDeadline = {
  id: string
  title: string
  date: string
  dateLabel: string
  priority: string
  completed: boolean
  href: string
}

export type WizardProActivity = {
  title: string
  date: string
  dateLabel: string
  description: string
  notes: string
}

export type WizardProFields = {
  step1_note: string
  note_preparazione: string
  argomenti_principali: string
  richieste_giudice: string
  eccezioni_da_sollevare: string
  precheck_firma_ok: boolean
  precheck_docs_pronti: boolean
  precheck_cliente_notificato: boolean
  precheck_trasporto_ok: boolean
  precheck_note: string
  esito: string
  esito_rinvio_data: string
  esito_note_verbale: string
  esito_azioni: string
  esito_aggiorna_fascicolo: boolean
}

export type WizardProStepData = {
  source: string
  contracts: ReactContracts
  session: WizardProSession | null
  currentStep: number
  currentStepLabel: string
  steps: WizardProStepStatus[]
  case: WizardProMatter | null
  appointment: WizardProAppointment | null
  parts: Array<{ role: string; name: string }>
  deadlines: WizardProDeadline[]
  activities: WizardProActivity[]
  caseDocuments: Array<{ id: string; name: string; type: string; signed: boolean; href: string }>
  documents: WizardProDocument[]
  missingDocuments: WizardProDocument[]
  fields: WizardProFields
  precheck: { completed: boolean; done: number; total: number }
  esiti: Array<{ value: string; label: string }>
  actions: {
    form: string
    next: string
    complete: string
    folder: string
    agenda: string
    deadlines: string
    signature: string
    timesheet: string
    lex: string
  }
  emptyStates: {
    noDocuments: boolean
    noMissingDocuments: boolean
    noActivities: boolean
    noDeadlines: boolean
  }
}

export type WizardProCompleteData = {
  source: string
  contracts: ReactContracts
  session: WizardProSession | null
  steps: WizardProStepStatus[]
  case: WizardProMatter | null
  appointment: WizardProAppointment | null
  parts: Array<{ role: string; name: string }>
  deadlines: WizardProDeadline[]
  activities: WizardProActivity[]
  documents: WizardProDocument[]
  fields: WizardProFields
  outcome: {
    value: string
    label: string
    tone: Tone
    postponementDate: string
    postponementDateLabel: string
    hearingNotes: string
    nextActions: string
    matterUpdated: boolean
  }
  actions: {
    folder: string
    agenda: string
    deadlines: string
    newDeadline: string
    timesheet: string
    archive: string
    delete: string
    lex: string
  }
}

const contracts: ReactContracts = { mock_fallback: false, read_only: false, writes: 'operational_routes', route_owner: 'react_shell' }

const fields: WizardProFields = {
  step1_note: '',
  note_preparazione: '',
  argomenti_principali: '',
  richieste_giudice: '',
  eccezioni_da_sollevare: '',
  precheck_firma_ok: false,
  precheck_docs_pronti: false,
  precheck_cliente_notificato: false,
  precheck_trasporto_ok: false,
  precheck_note: '',
  esito: '',
  esito_rinvio_data: '',
  esito_note_verbale: '',
  esito_azioni: '',
  esito_aggiorna_fascicolo: true,
}

const dashboardEmpty: WizardProData = {
  source: 'vuoto',
  contracts,
  summary: { totalCases: 0, activeDrafts: 0, completed: 0, upcomingHearings: 0, documentsReady: 0, documentsMissing: 0, linkedDeadlines: 0 },
  steps: ['Briefing', 'Documenti', 'Preparazione', 'Pre-partenza', 'Esito'],
  cases: [],
  selectedCase: null,
  recentDrafts: [],
  recentCompleted: [],
  filters: {},
  actions: {
    start: '/wizard-pro/nuovo',
    agenda: '/agenda',
    deadlines: '/scadenziario',
    newDeadline: '/scadenziario/nuova',
    newAppointment: '/agenda/nuovo',
    lex: '/lex?context=preparazione-udienza',
  },
}

const stepEmpty: WizardProStepData = {
  source: 'vuoto',
  contracts,
  session: null,
  currentStep: 1,
  currentStepLabel: 'Briefing',
  steps: [],
  case: null,
  appointment: null,
  parts: [],
  deadlines: [],
  activities: [],
  caseDocuments: [],
  documents: [],
  missingDocuments: [],
  fields,
  precheck: { completed: false, done: 0, total: 4 },
  esiti: [],
  actions: {
    form: '/wizard-pro/nuovo',
    next: '/wizard-pro/',
    complete: '/wizard-pro/',
    folder: '/fascicoli',
    agenda: '/agenda',
    deadlines: '/scadenziario',
    signature: '/guida/firma-digitale',
    timesheet: '/timesheet',
    lex: '/lex?context=preparazione-udienza',
  },
  emptyStates: { noDocuments: true, noMissingDocuments: true, noActivities: true, noDeadlines: true },
}

const completeEmpty: WizardProCompleteData = {
  source: 'vuoto',
  contracts,
  session: null,
  steps: [],
  case: null,
  appointment: null,
  parts: [],
  deadlines: [],
  activities: [],
  documents: [],
  fields,
  outcome: {
    value: '',
    label: '',
    tone: 'neutral',
    postponementDate: '',
    postponementDateLabel: '',
    hearingNotes: '',
    nextActions: '',
    matterUpdated: false,
  },
  actions: {
    folder: '/fascicoli',
    agenda: '/agenda',
    deadlines: '/scadenziario',
    newDeadline: '/scadenziario/nuova',
    timesheet: '/timesheet',
    archive: '/wizard-pro/',
    delete: '/wizard-pro/',
    lex: '/lex?context=preparazione-udienza-riepilogo',
  },
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
  if (!isRecord(value)) return contracts
  return {
    mock_fallback: Boolean(value.mock_fallback),
    read_only: Boolean(value.read_only),
    writes: text(value.writes, 'operational_routes'),
    route_owner: text(value.route_owner, 'react_shell'),
  }
}

function sessionFrom(value: unknown): WizardProSession | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  if (!id) return null
  return {
    id,
    title: text(value.title, 'Preparazione udienza'),
    status: text(value.status, 'in_corso'),
    statusLabel: text(value.statusLabel ?? value.status_label, 'In corso'),
    step: number(value.step, 1),
    progress: number(value.progress),
    modifiedAt: text(value.modifiedAt ?? value.modified_at),
    modifiedAtLabel: text(value.modifiedAtLabel ?? value.modified_at_label),
    completedAt: text(value.completedAt ?? value.completed_at),
    completedAtLabel: text(value.completedAtLabel ?? value.completed_at_label),
    stepHref: text(value.stepHref ?? value.step_href),
    summaryHref: text(value.summaryHref ?? value.summary_href),
    archiveHref: text(value.archiveHref ?? value.archive_href),
    deleteHref: text(value.deleteHref ?? value.delete_href),
  }
}

function caseFrom(value: unknown): WizardProCase | null {
  if (!isRecord(value)) return null
  const payload = isRecord(value.startPayload) ? value.startPayload : {}
  return {
    id: text(value.id),
    number: text(value.number),
    title: text(value.title, 'Fascicolo senza titolo'),
    client: text(value.client, 'Cliente da completare'),
    opponent: text(value.opponent, 'Controparte da completare'),
    matter: text(value.matter, 'Materia da completare'),
    court: text(value.court, 'Ufficio da definire'),
    rg: text(value.rg),
    judge: text(value.judge, 'Da completare'),
    section: text(value.section, 'Da completare'),
    hearingLabel: text(value.hearingLabel ?? value.hearing_label, 'Da pianificare'),
    hearingRaw: text(value.hearingRaw ?? value.hearing_raw),
    hearingDays: value.hearingDays === null || value.hearingDays === undefined ? null : number(value.hearingDays),
    hearingMode: text(value.hearingMode ?? value.hearing_mode, 'Da confermare'),
    hearingType: text(value.hearingType ?? value.hearing_type, 'Udienza'),
    statusLabel: text(value.statusLabel ?? value.status_label, 'Pratica'),
    statusTone: tone(value.statusTone ?? value.status_tone),
    progress: number(value.progress),
    progressLabel: text(value.progressLabel ?? value.progress_label, 'Preparazione'),
    documentsReady: number(value.documentsReady ?? value.documents_ready),
    documentsMissing: number(value.documentsMissing ?? value.documents_missing),
    openActivities: number(value.openActivities ?? value.open_activities),
    linkedDeadlines: number(value.linkedDeadlines ?? value.linked_deadlines),
    badges: Array.isArray(value.badges) ? value.badges.map((item) => isRecord(item) ? { label: text(item.label), tone: tone(item.tone) } : null).filter((item): item is { label: string; tone: Tone } => Boolean(item)) : [],
    parts: Array.isArray(value.parts) ? value.parts as WizardProCase['parts'] : [],
    activeSession: sessionFrom(value.activeSession ?? value.active_session),
    completedSession: sessionFrom(value.completedSession ?? value.completed_session),
    href: text(value.href),
    folderHref: text(value.folderHref ?? value.folder_href),
    agendaHref: text(value.agendaHref ?? value.agenda_href, '/agenda'),
    deadlineHref: text(value.deadlineHref ?? value.deadline_href, '/scadenziario'),
    startHref: text(value.startHref ?? value.start_href, '/wizard-pro/nuovo'),
    startPayload: {
      id_fascicolo: text(payload.id_fascicolo),
      id_appuntamento: text(payload.id_appuntamento),
    },
  }
}

function matterFrom(value: unknown): WizardProMatter | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  if (!id) return null
  return {
    id,
    number: text(value.number),
    title: text(value.title, 'Fascicolo senza titolo'),
    client: text(value.client, 'Cliente da completare'),
    opponent: text(value.opponent, 'Controparte da completare'),
    matter: text(value.matter),
    court: text(value.court, 'Ufficio da definire'),
    rg: text(value.rg),
    judge: text(value.judge, 'Da completare'),
    section: text(value.section, 'Da completare'),
    status: text(value.status),
    statusLabel: text(value.statusLabel ?? value.status_label),
    nextHearing: text(value.nextHearing ?? value.next_hearing),
    nextHearingLabel: text(value.nextHearingLabel ?? value.next_hearing_label),
    documentsCount: number(value.documentsCount ?? value.documents_count),
    href: text(value.href),
    documentsHref: text(value.documentsHref ?? value.documents_href),
    timesheetHref: text(value.timesheetHref ?? value.timesheet_href),
    deadlineHref: text(value.deadlineHref ?? value.deadline_href),
  }
}

function appointmentFrom(value: unknown): WizardProAppointment | null {
  if (!isRecord(value)) return null
  return {
    id: text(value.id),
    title: text(value.title, 'Udienza'),
    date: text(value.date),
    dateLabel: text(value.dateLabel ?? value.date_label),
    place: text(value.place),
    notes: text(value.notes),
    href: text(value.href, '/agenda'),
  }
}

function documentFrom(value: unknown): WizardProDocument | null {
  if (!isRecord(value)) return null
  return {
    index: number(value.index),
    idDocument: text(value.idDocument ?? value.id_document),
    label: text(value.label, 'Documento'),
    type: text(value.type),
    mandatory: Boolean(value.mandatory),
    status: text(value.status, 'da_portare'),
    statusLabel: text(value.statusLabel ?? value.status_label),
    statusTone: tone(value.statusTone ?? value.status_tone),
    notes: text(value.notes),
    fileName: text(value.fileName ?? value.file_name),
    signed: Boolean(value.signed),
    href: text(value.href),
  }
}

function deadlineFrom(value: unknown): WizardProDeadline | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  return {
    id,
    title: text(value.title, 'Scadenza'),
    date: text(value.date),
    dateLabel: text(value.dateLabel ?? value.date_label),
    priority: text(value.priority),
    completed: Boolean(value.completed),
    href: text(value.href, '/scadenziario'),
  }
}

function activityFrom(value: unknown): WizardProActivity | null {
  if (!isRecord(value)) return null
  return {
    title: text(value.title, 'Attivita'),
    date: text(value.date),
    dateLabel: text(value.dateLabel ?? value.date_label),
    description: text(value.description),
    notes: text(value.notes),
  }
}

function fieldsFrom(value: unknown): WizardProFields {
  if (!isRecord(value)) return fields
  return {
    step1_note: text(value.step1_note),
    note_preparazione: text(value.note_preparazione),
    argomenti_principali: text(value.argomenti_principali),
    richieste_giudice: text(value.richieste_giudice),
    eccezioni_da_sollevare: text(value.eccezioni_da_sollevare),
    precheck_firma_ok: Boolean(value.precheck_firma_ok),
    precheck_docs_pronti: Boolean(value.precheck_docs_pronti),
    precheck_cliente_notificato: Boolean(value.precheck_cliente_notificato),
    precheck_trasporto_ok: Boolean(value.precheck_trasporto_ok),
    precheck_note: text(value.precheck_note),
    esito: text(value.esito),
    esito_rinvio_data: text(value.esito_rinvio_data),
    esito_note_verbale: text(value.esito_note_verbale),
    esito_azioni: text(value.esito_azioni),
    esito_aggiorna_fascicolo: Boolean(value.esito_aggiorna_fascicolo),
  }
}

function stepsFrom(value: unknown): WizardProStepStatus[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return {
      n: number(row.n),
      label: text(row.label),
      icon: text(row.icon),
      confirmed: Boolean(row.confirmed),
      active: Boolean(row.active),
      href: text(row.href),
      available: Boolean(row.available),
    }
  }).filter((item) => item.n > 0)
}

function stringArrayFilters(value: unknown): Record<string, string[]> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(Object.entries(value).map(([key, list]) => [
    key,
    Array.isArray(list) ? list.map((item) => text(item)).filter(Boolean) : [],
  ]))
}

export async function getWizardProPage(): Promise<WizardProData> {
  try {
    const search = typeof window !== 'undefined' ? window.location.search : ''
    const response = await fetch(`/api/v1/ui/wizard-pro${search}`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
    if (!response.ok) return dashboardEmpty
    const payload = await response.json() as Record<string, unknown>
    const cases = Array.isArray(payload.cases) ? payload.cases.map(caseFrom).filter((item): item is WizardProCase => Boolean(item)) : []
    const summary = isRecord(payload.summary) ? payload.summary : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    return {
      source: text(payload.source, 'repository_reali'),
      contracts: contractsFrom(payload.contracts),
      summary: {
        totalCases: number(summary.totalCases ?? summary.total_cases),
        activeDrafts: number(summary.activeDrafts ?? summary.active_drafts),
        completed: number(summary.completed),
        upcomingHearings: number(summary.upcomingHearings ?? summary.upcoming_hearings),
        documentsReady: number(summary.documentsReady ?? summary.documents_ready),
        documentsMissing: number(summary.documentsMissing ?? summary.documents_missing),
        linkedDeadlines: number(summary.linkedDeadlines ?? summary.linked_deadlines),
      },
      steps: Array.isArray(payload.steps) ? payload.steps.map((item) => text(item)).filter(Boolean) : dashboardEmpty.steps,
      cases,
      selectedCase: caseFrom(payload.selectedCase ?? payload.selected_case) ?? cases[0] ?? null,
      recentDrafts: Array.isArray(payload.recentDrafts) ? payload.recentDrafts.map((item) => {
        const row = isRecord(item) ? item : {}
        return { session: sessionFrom(row.session), caseTitle: text(row.caseTitle ?? row.case_title), client: text(row.client), court: text(row.court) }
      }) : [],
      recentCompleted: Array.isArray(payload.recentCompleted) ? payload.recentCompleted.map((item) => {
        const row = isRecord(item) ? item : {}
        return { session: sessionFrom(row.session), caseTitle: text(row.caseTitle ?? row.case_title), client: text(row.client), court: text(row.court) }
      }) : [],
      filters: stringArrayFilters(payload.filters),
      actions: {
        start: text(actions.start, '/wizard-pro/nuovo'),
        agenda: text(actions.agenda, '/agenda'),
        deadlines: text(actions.deadlines, '/scadenziario'),
        newDeadline: text(actions.newDeadline ?? actions.new_deadline, '/scadenziario/nuova'),
        newAppointment: text(actions.newAppointment ?? actions.new_appointment, '/agenda/nuovo'),
        lex: text(actions.lex, '/lex?context=preparazione-udienza'),
      },
    }
  } catch {
    return dashboardEmpty
  }
}

export async function getWizardProStepPage(): Promise<WizardProStepData> {
  try {
    const rawPath = typeof window !== 'undefined' ? window.location.pathname : ''
    const path = rawPath.startsWith('/app-v2/') ? rawPath.slice('/app-v2'.length) : rawPath
    const match = path.match(/^\/wizard-pro\/([^/]+)\/step\/([1-5])$/)
    if (!match) return stepEmpty
    const response = await fetch(`/api/v1/ui/wizard-pro/session/${encodeURIComponent(match[1])}/step/${match[2]}`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
    if (!response.ok) return stepEmpty
    const payload = await response.json() as Record<string, unknown>
    const actions = isRecord(payload.actions) ? payload.actions : {}
    const precheck = isRecord(payload.precheck) ? payload.precheck : {}
    const emptyStates = isRecord(payload.emptyStates) ? payload.emptyStates : {}
    return {
      source: text(payload.source, 'repository_reali'),
      contracts: contractsFrom(payload.contracts),
      session: sessionFrom(payload.session),
      currentStep: number(payload.currentStep ?? payload.current_step, 1),
      currentStepLabel: text(payload.currentStepLabel ?? payload.current_step_label, 'Step'),
      steps: stepsFrom(payload.steps),
      case: matterFrom(payload.case),
      appointment: appointmentFrom(payload.appointment),
      parts: Array.isArray(payload.parts) ? payload.parts.map((item) => {
        const row = isRecord(item) ? item : {}
        return { role: text(row.role), name: text(row.name) }
      }).filter((item) => item.name) : [],
      deadlines: Array.isArray(payload.deadlines) ? payload.deadlines.map(deadlineFrom).filter((item): item is WizardProDeadline => Boolean(item)) : [],
      activities: Array.isArray(payload.activities) ? payload.activities.map(activityFrom).filter((item): item is WizardProActivity => Boolean(item)) : [],
      caseDocuments: Array.isArray(payload.caseDocuments) ? payload.caseDocuments.map((item) => {
        const row = isRecord(item) ? item : {}
        return { id: text(row.id), name: text(row.name), type: text(row.type), signed: Boolean(row.signed), href: text(row.href) }
      }).filter((item) => item.name) : [],
      documents: Array.isArray(payload.documents) ? payload.documents.map(documentFrom).filter((item): item is WizardProDocument => Boolean(item)) : [],
      missingDocuments: Array.isArray(payload.missingDocuments) ? payload.missingDocuments.map(documentFrom).filter((item): item is WizardProDocument => Boolean(item)) : [],
      fields: fieldsFrom(payload.fields),
      precheck: { completed: Boolean(precheck.completed), done: number(precheck.done), total: number(precheck.total, 4) },
      esiti: Array.isArray(payload.esiti) ? payload.esiti.map((item) => {
        const row = isRecord(item) ? item : {}
        return { value: text(row.value), label: text(row.label) }
      }).filter((item) => item.value) : [],
      actions: {
        form: text(actions.form),
        next: text(actions.next, '/wizard-pro/'),
        complete: text(actions.complete, '/wizard-pro/'),
        folder: text(actions.folder, '/fascicoli'),
        agenda: text(actions.agenda, '/agenda'),
        deadlines: text(actions.deadlines, '/scadenziario'),
        signature: text(actions.signature, '/guida/firma-digitale'),
        timesheet: text(actions.timesheet, '/timesheet'),
        lex: text(actions.lex, '/lex?context=preparazione-udienza'),
      },
      emptyStates: {
        noDocuments: Boolean(emptyStates.noDocuments),
        noMissingDocuments: Boolean(emptyStates.noMissingDocuments),
        noActivities: Boolean(emptyStates.noActivities),
        noDeadlines: Boolean(emptyStates.noDeadlines),
      },
    }
  } catch {
    return stepEmpty
  }
}

export async function getWizardProCompletePage(): Promise<WizardProCompleteData> {
  try {
    const rawPath = typeof window !== 'undefined' ? window.location.pathname : ''
    const path = rawPath.startsWith('/app-v2/') ? rawPath.slice('/app-v2'.length) : rawPath
    const match = path.match(/^\/wizard-pro\/([^/]+)\/completo$/)
    if (!match) return completeEmpty
    const response = await fetch(`/api/v1/ui/wizard-pro/session/${encodeURIComponent(match[1])}/completo`, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
    if (!response.ok) return completeEmpty
    const payload = await response.json() as Record<string, unknown>
    const actions = isRecord(payload.actions) ? payload.actions : {}
    const outcome = isRecord(payload.outcome) ? payload.outcome : {}
    return {
      source: text(payload.source, 'repository_reali'),
      contracts: contractsFrom(payload.contracts),
      session: sessionFrom(payload.session),
      steps: stepsFrom(payload.steps),
      case: matterFrom(payload.case),
      appointment: appointmentFrom(payload.appointment),
      parts: Array.isArray(payload.parts) ? payload.parts.map((item) => {
        const row = isRecord(item) ? item : {}
        return { role: text(row.role), name: text(row.name) }
      }).filter((item) => item.name) : [],
      deadlines: Array.isArray(payload.deadlines) ? payload.deadlines.map(deadlineFrom).filter((item): item is WizardProDeadline => Boolean(item)) : [],
      activities: Array.isArray(payload.activities) ? payload.activities.map(activityFrom).filter((item): item is WizardProActivity => Boolean(item)) : [],
      documents: Array.isArray(payload.documents) ? payload.documents.map(documentFrom).filter((item): item is WizardProDocument => Boolean(item)) : [],
      fields: fieldsFrom(payload.fields),
      outcome: {
        value: text(outcome.value),
        label: text(outcome.label),
        tone: tone(outcome.tone),
        postponementDate: text(outcome.postponementDate ?? outcome.postponement_date),
        postponementDateLabel: text(outcome.postponementDateLabel ?? outcome.postponement_date_label),
        hearingNotes: text(outcome.hearingNotes ?? outcome.hearing_notes),
        nextActions: text(outcome.nextActions ?? outcome.next_actions),
        matterUpdated: Boolean(outcome.matterUpdated ?? outcome.matter_updated),
      },
      actions: {
        folder: text(actions.folder, '/fascicoli'),
        agenda: text(actions.agenda, '/agenda'),
        deadlines: text(actions.deadlines, '/scadenziario'),
        newDeadline: text(actions.newDeadline ?? actions.new_deadline, '/scadenziario/nuova'),
        timesheet: text(actions.timesheet, '/timesheet'),
        archive: text(actions.archive, '/wizard-pro/'),
        delete: text(actions.delete, '/wizard-pro/'),
        lex: text(actions.lex, '/lex?context=preparazione-udienza-riepilogo'),
      },
    }
  } catch {
    return completeEmpty
  }
}
