import type { Tone } from './data'
import { sanitizeDisplayText } from './displayText'

export type ReactContracts = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  read_only?: boolean
}

export type TimesheetOption = {
  id: string
  label: string
  href?: string
  idCliente?: string
}

export type TimesheetStatusOption = {
  value: string
  label: string
  tone: Tone
}

export type TimesheetEntry = {
  id: string
  date: string
  dateLabel: string
  description: string
  idCliente: string
  clientName: string
  clientHref: string
  idFascicolo: string
  fascicoloLabel: string
  fascicoloHref: string
  user: string
  minutes: number
  hours: number
  hoursLabel: string
  hourlyRate: number
  hourlyRateLabel: string
  totalValue: number
  totalValueLabel: string
  billable: boolean
  billableLabel: string
  status: string
  statusLabel: string
  statusTone: Tone
  origin: string
  notes: string
  context: string
  stateAction: string
  eligibleForInvoice: boolean
}

export type TimesheetSummary = {
  totalEntries: number
  totalMinutes: number
  totalHours: number
  totalHoursLabel: string
  totalValue: number
  totalValueLabel: string
  open: number
  validated: number
  invoiced: number
  billable: number
  notBillable: number
}

export type TimesheetBilling = {
  ready: boolean
  issues: string[]
  count: number
  hours: number
  hoursLabel: string
  value: number
  valueLabel: string
  entryIds: string[]
  idCliente: string
  idFascicolo: string
  nextAction: string
  action: string
}

export type TimesheetData = {
  source: string
  generatedAt: string
  contracts: ReactContracts
  filters: Record<string, string>
  summary: TimesheetSummary
  entries: TimesheetEntry[]
  options: {
    clients: TimesheetOption[]
    matters: TimesheetOption[]
    statuses: TimesheetStatusOption[]
    users: Array<{ value: string; label: string }>
  }
  billing: TimesheetBilling
  actions: {
    create: string
    billing: string
    statistics: string
    agenda: string
    clients: string
    matters: string
    lex: string
  }
  emptyStates: {
    noEntries: boolean
    noFilteredEntries: boolean
    noValidableEntries: boolean
    noBillableEntries: boolean
  }
}

const emptyContracts: ReactContracts = { mock_fallback: false, writes: 'operational_routes', route_owner: 'react_shell' }

const emptyTimesheetData: TimesheetData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: emptyContracts,
  filters: {},
  summary: {
    totalEntries: 0,
    totalMinutes: 0,
    totalHours: 0,
    totalHoursLabel: '0 min',
    totalValue: 0,
    totalValueLabel: '€ 0,00',
    open: 0,
    validated: 0,
    invoiced: 0,
    billable: 0,
    notBillable: 0,
  },
  entries: [],
  options: { clients: [], matters: [], statuses: [], users: [] },
  billing: {
    ready: false,
    issues: [],
    count: 0,
    hours: 0,
    hoursLabel: '0 min',
    value: 0,
    valueLabel: '€ 0,00',
    entryIds: [],
    idCliente: '',
    idFascicolo: '',
    nextAction: '',
    action: '/timesheet/genera-parcella',
  },
  actions: {
    create: '/timesheet/nuovo',
    billing: '/fatturazione/',
    statistics: '/statistiche/?view=produttivita',
    agenda: '/agenda',
    clients: '/clienti',
    matters: '/fascicoli',
    lex: '#lex',
  },
  emptyStates: {
    noEntries: true,
    noFilteredEntries: false,
    noValidableEntries: true,
    noBillableEntries: true,
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(String(value ?? fallback).trim() || fallback)
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

function optionFrom(value: unknown): TimesheetOption | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  if (!id) return null
  return {
    id,
    label: text(value.label, id),
    href: text(value.href),
    idCliente: text(value.idCliente ?? value.id_cliente),
  }
}

function statusFrom(value: unknown): TimesheetStatusOption | null {
  if (!isRecord(value)) return null
  const valueId = text(value.value)
  if (!valueId) return null
  return { value: valueId, label: text(value.label, valueId), tone: tone(value.tone) }
}

function entryFrom(value: unknown): TimesheetEntry | null {
  if (!isRecord(value)) return null
  const id = text(value.id)
  if (!id) return null
  return {
    id,
    date: text(value.date),
    dateLabel: text(value.dateLabel ?? value.date_label),
    description: text(value.description, 'Attivita senza descrizione'),
    idCliente: text(value.idCliente ?? value.id_cliente),
    clientName: text(value.clientName ?? value.client_name, 'Cliente non collegato'),
    clientHref: text(value.clientHref ?? value.client_href),
    idFascicolo: text(value.idFascicolo ?? value.id_fascicolo),
    fascicoloLabel: text(value.fascicoloLabel ?? value.fascicolo_label, 'Fascicolo non collegato'),
    fascicoloHref: text(value.fascicoloHref ?? value.fascicolo_href),
    user: text(value.user, 'Operatore'),
    minutes: number(value.minutes),
    hours: number(value.hours),
    hoursLabel: text(value.hoursLabel ?? value.hours_label, '0 min'),
    hourlyRate: number(value.hourlyRate ?? value.hourly_rate),
    hourlyRateLabel: text(value.hourlyRateLabel ?? value.hourly_rate_label, '€ 0,00'),
    totalValue: number(value.totalValue ?? value.total_value),
    totalValueLabel: text(value.totalValueLabel ?? value.total_value_label, '€ 0,00'),
    billable: Boolean(value.billable),
    billableLabel: text(value.billableLabel ?? value.billable_label),
    status: text(value.status),
    statusLabel: text(value.statusLabel ?? value.status_label),
    statusTone: tone(value.statusTone ?? value.status_tone),
    origin: text(value.origin),
    notes: text(value.notes),
    context: text(value.context),
    stateAction: text(value.stateAction ?? value.state_action),
    eligibleForInvoice: Boolean(value.eligibleForInvoice ?? value.eligible_for_invoice),
  }
}

function summaryFrom(value: unknown): TimesheetSummary {
  if (!isRecord(value)) return emptyTimesheetData.summary
  return {
    totalEntries: number(value.totalEntries ?? value.total_entries),
    totalMinutes: number(value.totalMinutes ?? value.total_minutes),
    totalHours: number(value.totalHours ?? value.total_hours),
    totalHoursLabel: text(value.totalHoursLabel ?? value.total_hours_label, '0 min'),
    totalValue: number(value.totalValue ?? value.total_value),
    totalValueLabel: text(value.totalValueLabel ?? value.total_value_label, '€ 0,00'),
    open: number(value.open),
    validated: number(value.validated),
    invoiced: number(value.invoiced),
    billable: number(value.billable),
    notBillable: number(value.notBillable ?? value.not_billable),
  }
}

function billingFrom(value: unknown): TimesheetBilling {
  if (!isRecord(value)) return emptyTimesheetData.billing
  return {
    ready: Boolean(value.ready),
    issues: Array.isArray(value.issues) ? value.issues.map((item) => text(item)).filter(Boolean) : [],
    count: number(value.count),
    hours: number(value.hours),
    hoursLabel: text(value.hoursLabel ?? value.hours_label, '0 min'),
    value: number(value.value),
    valueLabel: text(value.valueLabel ?? value.value_label, '€ 0,00'),
    entryIds: Array.isArray(value.entryIds) ? value.entryIds.map((item) => text(item)).filter(Boolean) : [],
    idCliente: text(value.idCliente ?? value.id_cliente),
    idFascicolo: text(value.idFascicolo ?? value.id_fascicolo),
    nextAction: text(value.nextAction ?? value.next_action),
    action: text(value.action, '/timesheet/genera-parcella'),
  }
}

function filtersFrom(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, text(item)]))
}

export async function getTimesheetPage(): Promise<TimesheetData> {
  try {
    const search = typeof window !== 'undefined' ? window.location.search : ''
    const response = await fetch(`/api/v1/ui/timesheet${search}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyTimesheetData
    const payload = await response.json() as Record<string, unknown>
    const options = isRecord(payload.options) ? payload.options : {}
    const actions = isRecord(payload.actions) ? payload.actions : {}
    const emptyStates = isRecord(payload.emptyStates) ? payload.emptyStates : {}
    return {
      source: text(payload.source, 'repository_reali'),
      generatedAt: text(payload.generatedAt ?? payload.generated_at),
      contracts: contractsFrom(payload.contracts),
      filters: filtersFrom(payload.filters),
      summary: summaryFrom(payload.summary),
      entries: Array.isArray(payload.entries) ? payload.entries.map(entryFrom).filter((item): item is TimesheetEntry => Boolean(item)) : [],
      options: {
        clients: Array.isArray(options.clients) ? options.clients.map(optionFrom).filter((item): item is TimesheetOption => Boolean(item)) : [],
        matters: Array.isArray(options.matters) ? options.matters.map(optionFrom).filter((item): item is TimesheetOption => Boolean(item)) : [],
        statuses: Array.isArray(options.statuses) ? options.statuses.map(statusFrom).filter((item): item is TimesheetStatusOption => Boolean(item)) : [],
        users: Array.isArray(options.users) ? options.users.map((item) => isRecord(item) ? { value: text(item.value), label: text(item.label) } : null).filter((item): item is { value: string; label: string } => Boolean(item)) : [],
      },
      billing: billingFrom(payload.billing),
      actions: {
        create: text(actions.create, '/timesheet/nuovo'),
        billing: text(actions.billing, '/fatturazione/'),
        statistics: text(actions.statistics, '/statistiche/?view=produttivita'),
        agenda: text(actions.agenda, '/agenda'),
        clients: text(actions.clients, '/clienti'),
        matters: text(actions.matters, '/fascicoli'),
        lex: text(actions.lex, '#lex'),
      },
      emptyStates: {
        noEntries: Boolean(emptyStates.noEntries),
        noFilteredEntries: Boolean(emptyStates.noFilteredEntries),
        noValidableEntries: Boolean(emptyStates.noValidableEntries),
        noBillableEntries: Boolean(emptyStates.noBillableEntries),
      },
    }
  } catch {
    return emptyTimesheetData
  }
}
