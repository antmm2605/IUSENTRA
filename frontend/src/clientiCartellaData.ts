import type { Tone } from './data'

export type CartellaClienteItem = {
  id: string
  title: string
  subtitle: string
  date?: string
  time?: string
  status?: string
  type?: string
  priority?: string
  amount?: string
  channel?: string
  href: string
  editHref?: string
  completeHref?: string
  tone: Tone
}

export type CartellaClienteMatter = CartellaClienteItem & {
  counterparty: string
  documents: number
  activities: number
}

export type CartellaCliente = {
  id: string
  name: string
  subtitle: string
  type: 'pf' | 'pg'
  status: string
  fiscalId: string
  phone: string
  email: string
  pec: string
  attorney: string
  privacyOk: boolean
  missingFields: string[]
  documentExpired: boolean
  href: string
  editHref: string
  folderHref: string
}

export type CartellaClienteData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes?: string; route_owner?: string; legacy_route?: string }
  cliente: CartellaCliente
  summary: {
    activeMatters: number
    archivedMatters: number
    documents: number
    deadlines: number
    overdueDeadlines: number
    appointments: number
    messages: number
    quotes: number
    engagements: number
    invoices: number
  }
  matters: { active: CartellaClienteMatter[]; archived: CartellaClienteMatter[] }
  deadlines: CartellaClienteItem[]
  appointments: CartellaClienteItem[]
  messages: CartellaClienteItem[]
  quotes: CartellaClienteItem[]
  engagements: CartellaClienteItem[]
  invoices: CartellaClienteItem[]
  timeline: CartellaClienteItem[]
  actions: Record<string, string>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function arrayText(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)).filter(Boolean) : []
}

function tone(value: unknown, fallback: Tone = 'neutral'): Tone {
  const raw = text(value) as Tone
  return ['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw) ? raw : fallback
}

const emptyCliente: CartellaCliente = {
  id: '',
  name: 'Cliente non disponibile',
  subtitle: '',
  type: 'pf',
  status: 'attivo',
  fiscalId: '',
  phone: '',
  email: '',
  pec: '',
  attorney: '',
  privacyOk: false,
  missingFields: [],
  documentExpired: false,
  href: '/clienti',
  editHref: '/clienti',
  folderHref: '/clienti',
}

export const emptyCartellaCliente: CartellaClienteData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: false, writes: 'operational_routes', route_owner: 'react_shell' },
  cliente: emptyCliente,
  summary: {
    activeMatters: 0,
    archivedMatters: 0,
    documents: 0,
    deadlines: 0,
    overdueDeadlines: 0,
    appointments: 0,
    messages: 0,
    quotes: 0,
    engagements: 0,
    invoices: 0,
  },
  matters: { active: [], archived: [] },
  deadlines: [],
  appointments: [],
  messages: [],
  quotes: [],
  engagements: [],
  invoices: [],
  timeline: [],
  actions: {},
}

function item(value: unknown, index: number): CartellaClienteItem {
  const row = isRecord(value) ? value : {}
  const id = text(row.id, `item-${index}`)
  return {
    id,
    title: text(row.title, 'Elemento operativo'),
    subtitle: text(row.subtitle),
    date: text(row.date),
    time: text(row.time),
    status: text(row.status),
    type: text(row.type),
    priority: text(row.priority),
    amount: text(row.amount),
    channel: text(row.channel),
    href: text(row.href, '#'),
    editHref: text(row.editHref),
    completeHref: text(row.completeHref),
    tone: tone(row.tone),
  }
}

function matter(value: unknown, index: number): CartellaClienteMatter {
  const row = isRecord(value) ? value : {}
  return {
    ...item(row, index),
    counterparty: text(row.counterparty),
    documents: number(row.documents),
    activities: number(row.activities),
  }
}

function cliente(value: unknown): CartellaCliente {
  if (!isRecord(value)) return emptyCliente
  const typeRaw = text(value.type).toLowerCase()
  return {
    id: text(value.id),
    name: text(value.name, 'Cliente senza nome'),
    subtitle: text(value.subtitle),
    type: typeRaw === 'pg' ? 'pg' : 'pf',
    status: text(value.status, 'attivo'),
    fiscalId: text(value.fiscalId),
    phone: text(value.phone),
    email: text(value.email),
    pec: text(value.pec),
    attorney: text(value.attorney, '-'),
    privacyOk: bool(value.privacyOk),
    missingFields: arrayText(value.missingFields),
    documentExpired: bool(value.documentExpired),
    href: text(value.href, '/clienti'),
    editHref: text(value.editHref, '/clienti'),
    folderHref: text(value.folderHref, '/clienti'),
  }
}

function normalisePayload(payload: unknown): CartellaClienteData {
  if (!isRecord(payload)) return emptyCartellaCliente
  const rawMatters = isRecord(payload.matters) ? payload.matters : {}
  const rawSummary = isRecord(payload.summary) ? payload.summary : {}
  const rawContracts = isRecord(payload.contracts) ? payload.contracts : {}
  const rawActions = isRecord(payload.actions) ? payload.actions : {}
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generated_at ?? payload.generatedAt),
    contracts: {
      mock_fallback: bool(rawContracts.mock_fallback),
      read_only: bool(rawContracts.read_only),
      writes: text(rawContracts.writes),
      route_owner: text(rawContracts.route_owner),
      legacy_route: text(rawContracts.legacy_route),
    },
    cliente: cliente(payload.cliente),
    summary: {
      activeMatters: number(rawSummary.activeMatters),
      archivedMatters: number(rawSummary.archivedMatters),
      documents: number(rawSummary.documents),
      deadlines: number(rawSummary.deadlines),
      overdueDeadlines: number(rawSummary.overdueDeadlines),
      appointments: number(rawSummary.appointments),
      messages: number(rawSummary.messages),
      quotes: number(rawSummary.quotes),
      engagements: number(rawSummary.engagements),
      invoices: number(rawSummary.invoices),
    },
    matters: {
      active: Array.isArray(rawMatters.active) ? rawMatters.active.map(matter) : [],
      archived: Array.isArray(rawMatters.archived) ? rawMatters.archived.map(matter) : [],
    },
    deadlines: Array.isArray(payload.deadlines) ? payload.deadlines.map(item) : [],
    appointments: Array.isArray(payload.appointments) ? payload.appointments.map(item) : [],
    messages: Array.isArray(payload.messages) ? payload.messages.map(item) : [],
    quotes: Array.isArray(payload.quotes) ? payload.quotes.map(item) : [],
    engagements: Array.isArray(payload.engagements) ? payload.engagements.map(item) : [],
    invoices: Array.isArray(payload.invoices) ? payload.invoices.map(item) : [],
    timeline: Array.isArray(payload.timeline) ? payload.timeline.map(item) : [],
    actions: Object.fromEntries(Object.entries(rawActions).map(([key, value]) => [key, text(value)])),
  }
}

export async function getCartellaClientePage(idCliente: string): Promise<CartellaClienteData> {
  if (!idCliente) return emptyCartellaCliente
  try {
    const response = await fetch(`/api/v1/ui/clienti/${encodeURIComponent(idCliente)}/cartella`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyCartellaCliente
    return normalisePayload(await response.json())
  } catch {
    return emptyCartellaCliente
  }
}
