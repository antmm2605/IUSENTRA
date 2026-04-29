import type { Tone } from './data'

export type AgendaView = 'day' | 'week' | 'month'
export type AgendaKind = 'tutti' | 'udienza' | 'appuntamento' | 'scadenza' | 'deposito' | 'call' | 'studio'
export type AgendaPriority = 'critica' | 'alta' | 'media' | 'bassa'
export type AgendaSyncStatus = 'sincronizzato' | 'locale' | 'da_sincronizzare' | 'errore'

export type AgendaEvent = {
  id: string
  title: string
  subtitle: string
  date: string
  start: string
  end: string
  timeLabel: string
  durationLabel: string
  kind: Exclude<AgendaKind, 'tutti'>
  priority: AgendaPriority
  tone: Tone
  location: string
  court: string
  matter: string
  client: string
  owner: string
  status: string
  source: string
  syncStatus: AgendaSyncStatus
  notes: string
  href: string
}

export type AgendaDay = {
  id: string
  iso: string
  label: string
  weekday: string
  month: string
  isToday: boolean
  isWeekend: boolean
  isOutsideMonth: boolean
  events: AgendaEvent[]
}

export type AgendaSummary = {
  today: number
  week: number
  hearings: number
  deadlines: number
  unsynced: number
  critical: number
  nextEvent?: AgendaEvent
}

export type AgendaPageData = {
  generatedAt: string
  source: string
  days: AgendaDay[]
  events: AgendaEvent[]
  summary: AgendaSummary
}

const IT_DATE = new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' })
const IT_WEEKDAY = new Intl.DateTimeFormat('it-IT', { weekday: 'short' })
const IT_MONTH = new Intl.DateTimeFormat('it-IT', { month: 'short' })

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asString(value: unknown, fallback = ''): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function asArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (isRecord(value) && Array.isArray(value.events)) return value.events
  if (isRecord(value) && Array.isArray(value.data)) return value.data
  if (isRecord(value) && Array.isArray(value.items)) return value.items
  return []
}

function parseDate(value: unknown): Date | null {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value
  const raw = asString(value)
  if (!raw) return null
  const normalised = raw.includes('T') ? raw : `${raw}T00:00:00`
  const parsed = new Date(normalised)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

export function toDateKey(value: Date): string {
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`
}

export function startOfWeek(value = new Date()): Date {
  const copy = new Date(value)
  copy.setHours(0, 0, 0, 0)
  const day = copy.getDay() || 7
  copy.setDate(copy.getDate() - day + 1)
  return copy
}

export function addDays(value: Date, days: number): Date {
  const copy = new Date(value)
  copy.setDate(copy.getDate() + days)
  return copy
}

export function addMonths(value: Date, months: number): Date {
  const copy = new Date(value)
  copy.setMonth(copy.getMonth() + months)
  return copy
}

export function agendaRange(anchor = new Date(), view: AgendaView = 'week'): { from: Date; to: Date } {
  const day = new Date(anchor)
  day.setHours(0, 0, 0, 0)
  if (view === 'day') return { from: day, to: day }
  if (view === 'month') {
    const firstOfMonth = new Date(day.getFullYear(), day.getMonth(), 1)
    const gridStart = startOfWeek(firstOfMonth)
    return { from: gridStart, to: addDays(gridStart, 41) }
  }
  const weekStart = startOfWeek(day)
  return { from: weekStart, to: addDays(weekStart, 6) }
}

export function rangeLabel(start: Date, end: Date): string {
  return `${IT_DATE.format(start)} - ${IT_DATE.format(end)}`
}

function formatTime(value: Date): string {
  return `${pad(value.getHours())}:${pad(value.getMinutes())}`
}

function durationLabel(start: Date, end: Date): string {
  const minutes = Math.max(15, Math.round((end.getTime() - start.getTime()) / 60000))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

function kindFrom(value: unknown): AgendaEvent['kind'] {
  const text = asString(value).toLowerCase()
  if (text.includes('udienza')) return 'udienza'
  if (text.includes('scaden') || text.includes('termine')) return 'scadenza'
  if (text.includes('deposit')) return 'deposito'
  if (text.includes('call') || text.includes('video') || text.includes('teams') || text.includes('meet')) return 'call'
  if (text.includes('studio') || text.includes('intern')) return 'studio'
  return 'appuntamento'
}

function priorityFrom(value: unknown): AgendaPriority {
  const text = asString(value).toLowerCase()
  if (text.includes('critic') || text.includes('urgent')) return 'critica'
  if (text.includes('alta')) return 'alta'
  if (text.includes('bassa')) return 'bassa'
  return 'media'
}

function syncFrom(value: unknown): AgendaSyncStatus {
  const text = asString(value).toLowerCase()
  if (text.includes('erro')) return 'errore'
  if (text.includes('sync') || text.includes('sincron')) return 'sincronizzato'
  if (text.includes('locale')) return 'locale'
  return 'da_sincronizzare'
}

function toneFor(kind: AgendaEvent['kind'], priority: AgendaPriority): Tone {
  if (priority === 'critica') return 'danger'
  if (priority === 'alta') return 'warning'
  if (kind === 'udienza') return 'orange'
  if (kind === 'deposito' || kind === 'scadenza') return 'danger'
  if (kind === 'call') return 'success'
  if (kind === 'studio') return 'purple'
  return 'primary'
}

function pickFirst(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    const value = record[key]
    if (value !== undefined && value !== null && String(value).trim() !== '') return value
  }
  return ''
}

function fallbackEnd(start: Date, rawEnd: unknown, rawDuration: unknown): Date {
  const parsed = parseDate(rawEnd)
  if (parsed && parsed.getTime() > start.getTime()) return parsed
  const minutes = Math.max(15, Number(rawDuration || 60))
  return new Date(start.getTime() + minutes * 60000)
}

export function normalizeAgendaEvent(item: unknown, index = 0): AgendaEvent | null {
  if (!isRecord(item)) return null
  const rawStart = pickFirst(item, ['start', 'data_ora', 'dataOra', 'datetime', 'inizio', 'date'])
  const start = parseDate(rawStart)
  if (!start) return null
  const end = fallbackEnd(start, pickFirst(item, ['end', 'fine', 'data_fine']), pickFirst(item, ['duration', 'durata_minuti']))
  const kind = kindFrom(pickFirst(item, ['kind', 'tipo', 'type', 'categoria', 'badge']))
  const priority = priorityFrom(pickFirst(item, ['priority', 'priorita', 'tone', 'badge']))
  const title = asString(pickFirst(item, ['title', 'titolo', 'oggetto', 'name']), 'Appuntamento')
  const court = asString(pickFirst(item, ['court', 'tribunale', 'ufficio']))
  const matter = asString(pickFirst(item, ['matter', 'procedimento', 'fascicolo', 'rg']))
  const client = asString(pickFirst(item, ['client', 'cliente', 'nome_cliente', 'parte']))
  const location = asString(pickFirst(item, ['location', 'luogo', 'aula', 'indirizzo']))
  const subtitle = [matter, court, location].filter(Boolean).join(' - ') || asString(pickFirst(item, ['subtitle', 'descrizione', 'note']))
  return {
    id: asString(pickFirst(item, ['id', 'uuid', 'pk']), `agenda-${index}`),
    title,
    subtitle,
    date: toDateKey(start),
    start: start.toISOString(),
    end: end.toISOString(),
    timeLabel: formatTime(start),
    durationLabel: durationLabel(start, end),
    kind,
    priority,
    tone: toneFor(kind, priority),
    location,
    court,
    matter,
    client,
    owner: asString(pickFirst(item, ['owner', 'responsabile', 'avvocato']), 'Studio'),
    status: asString(pickFirst(item, ['status', 'stato']), 'programmato'),
    source: asString(pickFirst(item, ['source', 'fonte']), 'agenda studio'),
    syncStatus: syncFrom(pickFirst(item, ['syncStatus', 'sync_status', 'sync', 'stato_sync'])),
    notes: asString(pickFirst(item, ['notes', 'note', 'descrizione'])),
    href: asString(pickFirst(item, ['href', 'url']), '/agenda'),
  }
}

export function buildAgendaPageData(events: AgendaEvent[], anchor = new Date(), source = 'api', view: AgendaView = 'week'): AgendaPageData {
  const todayKey = toDateKey(new Date())
  const range = agendaRange(anchor, view)
  const totalDays = Math.max(1, Math.round((range.to.getTime() - range.from.getTime()) / 86400000) + 1)
  const ordered = [...events].sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
  const days: AgendaDay[] = Array.from({ length: totalDays }, (_, index) => {
    const day = addDays(range.from, index)
    const iso = toDateKey(day)
    return {
      id: iso,
      iso,
      label: String(day.getDate()),
      weekday: IT_WEEKDAY.format(day).replace('.', ''),
      month: IT_MONTH.format(day).replace('.', ''),
      isToday: iso === todayKey,
      isWeekend: day.getDay() === 0 || day.getDay() === 6,
      isOutsideMonth: view === 'month' && day.getMonth() !== anchor.getMonth(),
      events: ordered.filter((event) => event.date === iso),
    }
  })
  const periodEvents = ordered.filter((event) => event.date >= toDateKey(range.from) && event.date <= toDateKey(range.to))
  return {
    generatedAt: new Date().toISOString(),
    source,
    days,
    events: ordered,
    summary: {
      today: ordered.filter((event) => event.date === todayKey).length,
      week: periodEvents.length,
      hearings: periodEvents.filter((event) => event.kind === 'udienza').length,
      deadlines: periodEvents.filter((event) => event.kind === 'scadenza' || event.kind === 'deposito').length,
      unsynced: periodEvents.filter((event) => event.syncStatus !== 'sincronizzato').length,
      critical: periodEvents.filter((event) => event.priority === 'critica' || event.priority === 'alta').length,
      nextEvent: ordered.find((event) => new Date(event.start).getTime() >= Date.now()),
    },
  }
}

export function eventTopPercent(event: AgendaEvent): number {
  const start = parseDate(event.start) ?? new Date()
  const minutes = start.getHours() * 60 + start.getMinutes()
  return Math.max(0, Math.min(100, ((minutes - 8 * 60) / (12 * 60)) * 100))
}

export function eventHeightPixels(event: AgendaEvent): number {
  const start = parseDate(event.start) ?? new Date()
  const end = parseDate(event.end) ?? new Date(start.getTime() + 60 * 60000)
  const minutes = Math.max(30, Math.round((end.getTime() - start.getTime()) / 60000))
  return Math.max(54, Math.min(132, Math.round((minutes / 60) * 70)))
}

function timeParts(value: string): { hours: number; minutes: number } | null {
  const [hourRaw, minuteRaw] = value.split(':')
  const hours = Number(hourRaw)
  const minutes = Number(minuteRaw)
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null
  return { hours, minutes }
}

function endpointUrl(path: string, from: string, to: string): string {
  const params = new URLSearchParams()
  if (path.includes('/api/v1/ui/agenda')) {
    params.set('from', from)
    params.set('to', to)
  } else {
    params.set('data_inizio', from)
    params.set('data_fine', to)
    params.set('per_page', '200')
  }
  return `${path}?${params.toString()}`
}

async function fetchAgendaEndpoint(path: string, from: string, to: string): Promise<{ items: unknown[]; source: string } | null> {
  const response = await fetch(endpointUrl(path, from, to), {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) return null
  const payload = await response.json() as unknown
  const source = isRecord(payload) ? asString(payload.source, path) : path
  return { items: asArray(payload), source }
}

export async function getAgendaPage(anchor = new Date(), view: AgendaView = 'week'): Promise<AgendaPageData> {
  const range = agendaRange(anchor, view)
  const from = toDateKey(range.from)
  const to = toDateKey(range.to)
  try {
    const result = await fetchAgendaEndpoint('/api/v1/ui/agenda', from, to)
      ?? await fetchAgendaEndpoint('/api/v1/agenda', from, to)
      ?? { items: [], source: 'empty' }
    const events = result.items.map((item, index) => normalizeAgendaEvent(item, index)).filter(Boolean) as AgendaEvent[]
    return buildAgendaPageData(events, anchor, result.source, view)
  } catch {
    return buildAgendaPageData([], anchor, 'errore_controllato', view)
  }
}

export function moveEventToDay(event: AgendaEvent, dayIso: string): AgendaEvent {
  return moveEventToDateTime(event, dayIso)
}

export function moveEventToDateTime(event: AgendaEvent, dayIso: string, time?: string): AgendaEvent {
  const start = parseDate(event.start) ?? new Date()
  const end = parseDate(event.end) ?? new Date(start.getTime() + 60 * 60000)
  const target = parseDate(dayIso) ?? new Date()
  const targetTime = time ? timeParts(time) : null
  const movedStart = new Date(target)
  movedStart.setHours(targetTime?.hours ?? start.getHours(), targetTime?.minutes ?? start.getMinutes(), 0, 0)
  const durationMs = Math.max(15 * 60000, end.getTime() - start.getTime())
  const movedEnd = new Date(movedStart.getTime() + durationMs)
  return {
    ...event,
    date: dayIso,
    start: movedStart.toISOString(),
    end: movedEnd.toISOString(),
    timeLabel: formatTime(movedStart),
    durationLabel: durationLabel(movedStart, movedEnd),
    syncStatus: 'da_sincronizzare',
  }
}
