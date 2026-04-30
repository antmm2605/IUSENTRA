import type { Tone } from './data'

export type WizardProCase = {
  id: string
  title: string
  client: string
  opponent: string
  matter: string
  court: string
  rg: string
  hearingLabel: string
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
  activeSession?: WizardProSession | null
  completedSession?: WizardProSession | null
  href: string
  folderHref: string
  agendaHref: string
  deadlineHref: string
  startHref: string
  startPayload: { id_fascicolo: string; id_appuntamento: string }
}

export type WizardProSession = {
  id: string
  title: string
  status: string
  step: number
  progress: number
  modifiedAt: string
  completedAt: string
  stepHref: string
  summaryHref: string
  archiveHref: string
  deleteHref: string
}

export type WizardProData = {
  source: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes: string; route_owner: string }
  summary: { totalCases: number; activeDrafts: number; completed: number; upcomingHearings: number }
  steps: string[]
  cases: WizardProCase[]
  selectedCase: WizardProCase | null
  recentDrafts: Array<{ session: WizardProSession | null; caseTitle: string; client: string; court: string }>
  recentCompleted: Array<{ session: WizardProSession | null; caseTitle: string; client: string; court: string }>
  actions: {
    start: string
    legacy: string
    agenda: string
    deadlines: string
    newDeadline: string
    newAppointment: string
    lex: string
  }
}

const emptyWizardProData: WizardProData = {
  source: 'vuoto',
  contracts: { mock_fallback: false, read_only: false, writes: 'operational_routes', route_owner: 'react_shell' },
  summary: { totalCases: 0, activeDrafts: 0, completed: 0, upcomingHearings: 0 },
  steps: ['Briefing', 'Documenti', 'Preparazione', 'Pre-partenza', 'Esito'],
  cases: [],
  selectedCase: null,
  recentDrafts: [],
  recentCompleted: [],
  actions: {
    start: '/wizard-pro/nuovo',
    legacy: '/wizard-pro/?_legacy=1',
    agenda: '/agenda',
    deadlines: '/scadenziario',
    newDeadline: '/scadenziario/nuova',
    newAppointment: '/agenda/nuovo',
    lex: '/lex?context=preparazione-udienza',
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

function sessionFrom(value: unknown): WizardProSession | null {
  if (!isRecord(value)) return null
  return {
    id: text(value.id),
    title: text(value.title, 'Preparazione udienza'),
    status: text(value.status, 'in_corso'),
    step: number(value.step, 1),
    progress: number(value.progress),
    modifiedAt: text(value.modifiedAt ?? value.modified_at),
    completedAt: text(value.completedAt ?? value.completed_at),
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
    title: text(value.title, 'Fascicolo senza titolo'),
    client: text(value.client, 'Cliente da completare'),
    opponent: text(value.opponent, 'Controparte da completare'),
    matter: text(value.matter, 'Materia da completare'),
    court: text(value.court, 'Ufficio da definire'),
    rg: text(value.rg),
    hearingLabel: text(value.hearingLabel ?? value.hearing_label, 'Da pianificare'),
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
    badges: Array.isArray(value.badges) ? value.badges.map((item) => isRecord(item) ? { label: text(item.label), tone: tone(item.tone) } : null).filter(Boolean) as Array<{ label: string; tone: Tone }> : [],
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

export async function getWizardProPage(): Promise<WizardProData> {
  try {
    const search = typeof window !== 'undefined' ? window.location.search : ''
    const response = await fetch(`/api/v1/ui/wizard-pro${search}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptyWizardProData
    const payload = await response.json()
    const cases = Array.isArray(payload.cases) ? payload.cases.map(caseFrom).filter(Boolean) as WizardProCase[] : []
    return {
      source: text(payload.source, 'repository_reali'),
      contracts: isRecord(payload.contracts) ? {
        mock_fallback: Boolean(payload.contracts.mock_fallback),
        read_only: Boolean(payload.contracts.read_only),
        writes: text(payload.contracts.writes, 'operational_routes'),
        route_owner: text(payload.contracts.route_owner, 'react_shell'),
      } : emptyWizardProData.contracts,
      summary: isRecord(payload.summary) ? {
        totalCases: number(payload.summary.totalCases ?? payload.summary.total_cases),
        activeDrafts: number(payload.summary.activeDrafts ?? payload.summary.active_drafts),
        completed: number(payload.summary.completed),
        upcomingHearings: number(payload.summary.upcomingHearings ?? payload.summary.upcoming_hearings),
      } : emptyWizardProData.summary,
      steps: Array.isArray(payload.steps) ? payload.steps.map((item: unknown) => text(item)).filter(Boolean) : emptyWizardProData.steps,
      cases,
      selectedCase: caseFrom(payload.selectedCase ?? payload.selected_case) ?? cases[0] ?? null,
      recentDrafts: Array.isArray(payload.recentDrafts) ? payload.recentDrafts as WizardProData['recentDrafts'] : [],
      recentCompleted: Array.isArray(payload.recentCompleted) ? payload.recentCompleted as WizardProData['recentCompleted'] : [],
      actions: isRecord(payload.actions) ? {
        start: text(payload.actions.start, '/wizard-pro/nuovo'),
        legacy: text(payload.actions.legacy, '/wizard-pro/?_legacy=1'),
        agenda: text(payload.actions.agenda, '/agenda'),
        deadlines: text(payload.actions.deadlines, '/scadenziario'),
        newDeadline: text(payload.actions.newDeadline ?? payload.actions.new_deadline, '/scadenziario/nuova'),
        newAppointment: text(payload.actions.newAppointment ?? payload.actions.new_appointment, '/agenda/nuovo'),
        lex: text(payload.actions.lex, '/lex?context=preparazione-udienza'),
      } : emptyWizardProData.actions,
    }
  } catch {
    return emptyWizardProData
  }
}
