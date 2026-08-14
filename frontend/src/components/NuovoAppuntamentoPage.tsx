import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Bell,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  Info,
  Landmark,
  MapPin,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from 'lucide-react'
import type { Tone } from '../data'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'
import { Badge } from './dashboard'
import './NuovoAppuntamentoPage.css'

type AppointmentType = 'UDIENZA' | 'CONSULTAZIONE' | 'DEPOSITO' | 'SCADENZA' | 'RIUNIONE' | 'ALTRO'

type AppointmentForm = {
  titolo: string
  tipo: AppointmentType
  data: string
  ora: string
  durata: string
  reminder: string
  luogo: string
  cliente: string
  cf_cliente: string
  id_cliente: string
  from_cliente: string
  procedimento: string
  tribunale: string
  avvocato: string
  note: string
}

type ClientSuggestion = {
  id?: string
  nome?: string
  cognome?: string
  ragione_sociale?: string
  nome_completo?: string
  codice_fiscale?: string
  email?: string
  procedimento?: string
  numero_procedimento?: string
  tribunale?: string
  avvocato?: string
}

const textKeys = [
  'nome_completo',
  'nomeCompleto',
  'denominazione',
  'ragione_sociale',
  'ragioneSociale',
  'titolo',
  'title',
  'label',
  'name',
  'value',
] as const

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asText(value: unknown, fallback = ''): string {
  try {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value).trim()
    if (Array.isArray(value)) {
      return value
        .map((item) => asText(item))
        .filter(Boolean)
        .join(' ')
        .trim() || fallback
    }
    if (isRecord(value)) {
      for (const key of textKeys) {
        const text = asText(value[key])
        if (text) return text
      }
    }
  } catch {
    return fallback
  }
  return fallback
}

function firstText(record: Record<string, unknown>, keys: string[], fallback = ''): string {
  for (const key of keys) {
    const text = asText(record[key])
    if (text) return text
  }
  return fallback
}

function nestedRecord(record: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = record[key]
  return isRecord(value) ? value : {}
}

async function safeJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.toLowerCase().includes('application/json')) return null
  try {
    return await response.json() as unknown
  } catch {
    return null
  }
}

type AgendaApiItem = {
  id: string
  titolo: string
  data_ora: string
  durata_minuti?: number
  stato?: string
  luogo?: string
}

type CompletionCheck = {
  id: string
  label: string
  help: string
  ok: boolean
  required?: boolean
}
type SubmitState = { saving: boolean; tone: 'success' | 'danger' | 'neutral'; message: string }

type AppointmentTypeMeta = {
  value: AppointmentType
  label: string
  description: string
  duration: string
  reminder: string
  tone: Tone
}

const appointmentTypes: AppointmentTypeMeta[] = [
  {
    value: 'UDIENZA',
    label: 'Udienza',
    description: 'Comparizione, camera di consiglio o trattazione con ufficio giudiziario.',
    duration: '60',
    reminder: '60',
    tone: 'primary',
  },
  {
    value: 'CONSULTAZIONE',
    label: 'Consultazione',
    description: 'Incontro con cliente, assistito o potenziale cliente.',
    duration: '45',
    reminder: '30',
    tone: 'success',
  },
  {
    value: 'RIUNIONE',
    label: 'Riunione',
    description: 'Meeting interno, controparte, CTU, mediatore o collaboratori.',
    duration: '60',
    reminder: '30',
    tone: 'purple',
  },
  {
    value: 'DEPOSITO',
    label: 'Deposito',
    description: 'Attivita telematica, deposito atto o adempimento collegato.',
    duration: '30',
    reminder: '120',
    tone: 'warning',
  },
  {
    value: 'SCADENZA',
    label: 'Scadenza',
    description: 'Promemoria operativo con effetto su termini e agenda.',
    duration: '15',
    reminder: '1440',
    tone: 'danger',
  },
  {
    value: 'ALTRO',
    label: 'Altro',
    description: 'Impegno generico dello studio.',
    duration: '30',
    reminder: '60',
    tone: 'neutral',
  },
]

const officeKinds = [
  'Tribunale',
  'Procura',
  "Corte d'Appello",
  'Cassazione',
  'G.d.P.',
  'Minori',
  'Sorv.',
  'TAR',
  'CdS',
  'CGARS',
  'CGT',
  'CPT',
]

function initialForm(): AppointmentForm {
  const params = new URLSearchParams(window.location.search)
  const oraParam = params.get('ora') ?? '09:00'
  const requestedType = String(params.get('tipo') || '').toUpperCase()
  const typeMeta = appointmentTypes.find((item) => item.value === requestedType) ?? appointmentTypes[0]
  return {
    titolo: params.get('titolo') ?? '',
    tipo: typeMeta.value,
    data: params.get('data') ?? '',
    ora: /^\d{2}:\d{2}$/.test(oraParam) ? oraParam : '09:00',
    durata: typeMeta.duration,
    reminder: typeMeta.reminder,
    luogo: '',
    cliente: '',
    cf_cliente: '',
    id_cliente: params.get('id_cliente') ?? '',
    from_cliente: params.get('from_cliente') ?? '',
    procedimento: '',
    tribunale: '',
    avvocato: '',
    note: '',
  }
}

function editAppointmentId(): string {
  const match = window.location.pathname.match(/^\/agenda\/([^/]+)\/modifica$/)
  return match ? decodeURIComponent(match[1]) : ''
}

function clientName(client: Partial<ClientSuggestion> | null | undefined): string {
  if (!client) return ''
  return (
    asText(client.nome_completo) ||
    [asText(client.nome), asText(client.cognome)].filter(Boolean).join(' ').trim() ||
    asText(client.ragione_sociale) ||
    ''
  )
}

function normaliseClientSuggestion(value: unknown): ClientSuggestion | null {
  if (!isRecord(value)) return null
  const cliente = isRecord(value.cliente) ? value.cliente : value
  const recapiti = nestedRecord(cliente, 'recapiti')
  const contatti = nestedRecord(cliente, 'contatti')
  const procedimenti = Array.isArray(cliente.procedimenti) ? cliente.procedimenti.filter(isRecord) : []
  const primoProcedimento = procedimenti.find((item) => firstText(item, ['numero_rg', 'numeroRg', 'numero_procedimento', 'procedimento', 'rg'])) || {}
  const numeroProcedimento = firstText(cliente, ['numero_procedimento', 'numeroProcedimento', 'procedimento', 'rg']) ||
    firstText(primoProcedimento, ['numero_procedimento', 'numeroProcedimento', 'procedimento', 'numero_rg', 'numeroRg', 'rg'])
  const annoProcedimento = firstText(primoProcedimento, ['anno', 'anno_rg', 'annoRg'])
  const procedimento = numeroProcedimento && annoProcedimento && !numeroProcedimento.includes('/')
    ? `RG ${numeroProcedimento}/${annoProcedimento}`
    : numeroProcedimento
  const suggestion: ClientSuggestion = {
    id: firstText(cliente, ['id', 'uuid', 'pk', 'id_cliente', 'idCliente']),
    nome: firstText(cliente, ['nome', 'first_name', 'firstName']),
    cognome: firstText(cliente, ['cognome', 'last_name', 'lastName']),
    ragione_sociale: firstText(cliente, ['ragione_sociale', 'ragioneSociale', 'denominazione']),
    nome_completo: firstText(cliente, ['nome_completo', 'nomeCompleto', 'display_name', 'displayName', 'label', 'name']),
    codice_fiscale: firstText(cliente, ['codice_fiscale', 'codiceFiscale', 'cf_cliente', 'partita_iva', 'partitaIva', 'identificativo_fiscale']),
    email: firstText(cliente, ['email', 'mail']) || firstText(recapiti, ['email', 'mail']) || firstText(contatti, ['email', 'mail']),
    procedimento,
    numero_procedimento: firstText(cliente, ['numero_procedimento', 'numeroProcedimento']) || procedimento,
    tribunale: firstText(cliente, ['tribunale', 'ufficio', 'court']) || firstText(primoProcedimento, ['tribunale', 'ufficio', 'court']),
    avvocato: firstText(cliente, ['avvocato', 'avvocato_referente', 'responsabile']) || firstText(primoProcedimento, ['avvocato', 'avvocato_referente', 'responsabile']),
  }
  return clientName(suggestion) || suggestion.id ? suggestion : null
}

function clientSuggestionsFromPayload(payload: unknown): ClientSuggestion[] {
  const source = Array.isArray(payload)
    ? payload
    : isRecord(payload) && Array.isArray(payload.data)
      ? payload.data
      : isRecord(payload) && Array.isArray(payload.items)
        ? payload.items
        : isRecord(payload) && Array.isArray(payload.clienti)
          ? payload.clienti
          : isRecord(payload) && Array.isArray(payload.results)
            ? payload.results
            : isRecord(payload) && Array.isArray(payload.rows)
              ? payload.rows
              : isRecord(payload)
                ? [payload]
                : []
  return source
    .map((item) => normaliseClientSuggestion(item))
    .filter((item): item is ClientSuggestion => Boolean(item))
    .slice(0, 8)
}

function normaliseAgendaApiItem(value: unknown, index: number): AgendaApiItem | null {
  if (!isRecord(value)) return null
  const dataOra = firstText(value, ['data_ora', 'dataOra', 'datetime', 'inizio', 'start', 'data'])
  if (!dataOra) return null
  return {
    id: firstText(value, ['id', 'uuid', 'pk'], `agenda-${index}`),
    titolo: firstText(value, ['titolo', 'title', 'oggetto', 'name'], 'Appuntamento'),
    data_ora: dataOra.includes('T') ? dataOra : `${dataOra}T00:00:00`,
    durata_minuti: Number(value.durata_minuti ?? value.durataMinuti ?? value.duration ?? 60),
    stato: firstText(value, ['stato', 'status']),
    luogo: firstText(value, ['luogo', 'location', 'aula']),
  }
}

function agendaItemsFromPayload(payload: unknown): AgendaApiItem[] {
  const source = Array.isArray(payload)
    ? payload
    : isRecord(payload) && Array.isArray(payload.data)
      ? payload.data
      : isRecord(payload) && Array.isArray(payload.items)
        ? payload.items
        : isRecord(payload) && Array.isArray(payload.events)
          ? payload.events
          : []
  return source
    .map((item, index) => normaliseAgendaApiItem(item, index))
    .filter((item): item is AgendaApiItem => Boolean(item))
}

function recordsFromPayload(payload: unknown): Record<string, unknown>[] {
  const source = Array.isArray(payload)
    ? payload
    : isRecord(payload) && Array.isArray(payload.data)
      ? payload.data
      : isRecord(payload) && Array.isArray(payload.items)
        ? payload.items
        : isRecord(payload) && Array.isArray(payload.events)
          ? payload.events
          : []
  return source.filter(isRecord)
}

function formFromAgendaRecord(record: Record<string, unknown>, current: AppointmentForm): AppointmentForm {
  const dataOra = firstText(record, ['data_ora', 'dataOra', 'datetime', 'inizio', 'start', 'data'])
  const safeDataOra = dataOra.includes('T') ? dataOra : dataOra ? `${dataOra}T${current.ora}:00` : ''
  const tipo = firstText(record, ['tipo', 'kind', 'type'], current.tipo).toUpperCase()
  const allowedType = appointmentTypes.some((item) => item.value === tipo) ? tipo as AppointmentType : current.tipo
  return {
    ...current,
    titolo: firstText(record, ['titolo', 'title', 'oggetto', 'name'], current.titolo),
    tipo: allowedType,
    data: safeDataOra.slice(0, 10) || current.data,
    ora: safeDataOra.slice(11, 16) || current.ora,
    durata: String(record.durata_minuti ?? record.durataMinuti ?? record.duration ?? current.durata),
    reminder: String(record.reminder_minuti ?? record.reminderMinuti ?? current.reminder),
    luogo: firstText(record, ['luogo', 'location', 'aula'], current.luogo),
    cliente: firstText(record, ['cliente', 'client', 'nome_cliente'], current.cliente),
    cf_cliente: firstText(record, ['cf_cliente', 'codice_fiscale'], current.cf_cliente).toUpperCase(),
    id_cliente: firstText(record, ['id_cliente', 'client_id'], current.id_cliente),
    procedimento: firstText(record, ['procedimento', 'matter', 'rg'], current.procedimento),
    tribunale: firstText(record, ['tribunale', 'court', 'ufficio'], current.tribunale),
    avvocato: firstText(record, ['avvocato', 'owner', 'responsabile'], current.avvocato),
    note: firstText(record, ['note', 'notes', 'descrizione'], current.note),
  }
}

function minutesFromTime(value: string): number | null {
  const [hourRaw, minuteRaw] = value.split(':')
  const hour = Number(hourRaw)
  const minute = Number(minuteRaw)
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) return null
  return hour * 60 + minute
}

function formatDateLabel(date: string): string {
  if (!date) return 'Data da impostare'
  try {
    return new Date(`${date}T12:00:00`).toLocaleDateString('it-IT', {
      timeZone: 'Europe/Rome',
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  } catch {
    return date
  }
}

function formatRange(form: AppointmentForm): string {
  if (!form.ora) return 'Ora da impostare'
  const start = minutesFromTime(form.ora)
  const duration = Math.max(Number(form.durata || 60), 1)
  if (start === null) return form.ora
  const end = start + duration
  const h1 = String(Math.floor(start / 60)).padStart(2, '0')
  const m1 = String(start % 60).padStart(2, '0')
  const h2 = String(Math.floor((end % (24 * 60)) / 60)).padStart(2, '0')
  const m2 = String(end % 60).padStart(2, '0')
  return `${h1}:${m1} - ${h2}:${m2}`
}

function buildSuggestedTitle(form: AppointmentForm): string {
  const cliente = form.cliente.trim()
  const procedimento = form.procedimento.trim()
  const tribunale = form.tribunale.trim()

  if (form.tipo === 'UDIENZA') {
    return [
      'Udienza',
      procedimento || '',
      cliente ? `- ${cliente}` : '',
      tribunale ? `(${tribunale})` : '',
    ].filter(Boolean).join(' ')
  }

  if (form.tipo === 'CONSULTAZIONE') return `Consultazione${cliente ? ` - ${cliente}` : ''}`
  if (form.tipo === 'RIUNIONE') return `Riunione${cliente ? ` - ${cliente}` : ''}`
  if (form.tipo === 'DEPOSITO') return `Deposito${procedimento ? ` ${procedimento}` : ''}${cliente ? ` - ${cliente}` : ''}`
  if (form.tipo === 'SCADENZA') return `Scadenza${procedimento ? ` ${procedimento}` : ''}${cliente ? ` - ${cliente}` : ''}`
  return cliente ? `Appuntamento - ${cliente}` : 'Appuntamento studio'
}

function formatAgendaItemRange(item: AgendaApiItem): string {
  try {
    const start = new Date(asText(item.data_ora))
    const end = new Date(start.getTime() + Math.max(Number(item.durata_minuti ?? 60), 1) * 60000)
    return `${start.toLocaleTimeString('it-IT', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit' })} - ${end.toLocaleTimeString('it-IT', { timeZone: 'Europe/Rome', hour: '2-digit', minute: '2-digit' })}`
  } catch {
    return asText(item.data_ora, 'Orario non disponibile')
  }
}

function Field({
  label,
  required,
  icon,
  children,
  wide = false,
}: {
  label: string
  required?: boolean
  icon?: ReactNode
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div className={`iu-appt-field ${wide ? 'is-wide' : ''}`}>
      <span className="iu-appt-label">
        {icon}
        {label}
        {required ? <b>*</b> : null}
      </span>
      {children}
    </div>
  )
}

export function NuovoAppuntamentoPage() {
  const editId = editAppointmentId()
  const [form, setForm] = useState<AppointmentForm>(() => initialForm())
  const [clientMatches, setClientMatches] = useState<ClientSuggestion[]>([])
  const [clientDropdownOpen, setClientDropdownOpen] = useState(false)
  const [clientLoading, setClientLoading] = useState(false)
  const [dayEvents, setDayEvents] = useState<AgendaApiItem[]>([])
  const [agendaLoading, setAgendaLoading] = useState(false)
  const [showValidation, setShowValidation] = useState(false)
  const [submitState, setSubmitState] = useState<SubmitState>({ saving: false, tone: 'neutral', message: '' })
  const courtInputRef = useRef<HTMLInputElement>(null)

  const typeMeta = appointmentTypes.find((item) => item.value === form.tipo) ?? appointmentTypes[0]
  const suggestedTitle = useMemo(() => buildSuggestedTitle(form), [form])
  const isEditMode = Boolean(editId)
  const formAction = isEditMode ? `/agenda/${encodeURIComponent(editId)}/modifica` : '/agenda/nuovo'

  const qualityChecks = useMemo<CompletionCheck[]>(() => [
    {
      id: 'titolo',
      label: 'Titolo operativo',
      help: 'Deve permettere di riconoscere subito fascicolo, cliente o attivita.',
      ok: form.titolo.trim().length >= 4,
      required: true,
    },
    {
      id: 'quando',
      label: 'Data e ora',
      help: 'Necessarie per agenda, reminder e feed iCal/WebCal.',
      ok: Boolean(form.data && form.ora),
      required: true,
    },
    {
      id: 'durata',
      label: 'Durata credibile',
      help: 'Valore minimo 5 minuti, utile per evitare sovrapposizioni.',
      ok: Number(form.durata) >= 5,
      required: true,
    },
    {
      id: 'cliente',
      label: 'Cliente collegato',
      help: 'Consigliato per recuperare la pratica dalla Ricerca Studio e da Lex.',
      ok: Boolean(form.cliente.trim()),
    },
    {
      id: 'cf',
      label: 'Codice fiscale pulito',
      help: 'Se presente, resta in maiuscolo e agganciabile alle anagrafiche.',
      ok: !form.cf_cliente || /^[A-Z0-9]{11,16}$/.test(form.cf_cliente),
    },
    {
      id: 'ufficio',
      label: 'Ufficio giudiziario',
      help: 'Per le udienze conviene indicare tribunale, procura, TAR o altro ufficio.',
      ok: form.tipo !== 'UDIENZA' || Boolean(form.tribunale.trim()),
    },
    {
      id: 'reminder',
      label: 'Promemoria presidiato',
      help: 'Un avviso prima dell impegno riduce il rischio di dimenticanze.',
      ok: Number(form.reminder) > 0,
    },
  ], [form])

  const completion = qualityChecks.filter((check) => check.ok).length
  const requiredOk = qualityChecks.filter((check) => check.required).every((check) => check.ok)

  const conflicts = useMemo(() => {
    const start = minutesFromTime(form.ora)
    const duration = Math.max(Number(form.durata || 60), 1)
    if (!form.data || start === null || !Number.isFinite(duration)) return []
    const end = start + duration

    return dayEvents.filter((item) => {
      if (item.stato === 'ANNULLATO' || item.stato === 'COMPLETATO') return false
      const itemDataOra = asText(item.data_ora)
      const itemDate = itemDataOra.slice(0, 10)
      const itemTime = itemDataOra.slice(11, 16)
      if (itemDate !== form.data || !itemTime) return false
      const itemStart = minutesFromTime(itemTime)
      if (itemStart === null) return false
      const itemEnd = itemStart + Math.max(Number(item.durata_minuti ?? 60), 1)
      return itemStart < end && itemEnd > start
    })
  }, [dayEvents, form.data, form.durata, form.ora])

  const canSubmit = requiredOk && conflicts.length === 0
  const cancelHref = form.from_cliente || form.id_cliente ? `/clienti/${form.from_cliente || form.id_cliente}` : '/agenda'
  const safeClientMatches = useMemo(() => clientMatches, [clientMatches])

  const update = (field: keyof AppointmentForm, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  useEffect(() => {
    if (!editId) return
    let alive = true
    fetch('/api/agenda', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then((response) => response.ok ? safeJson(response) : [])
      .then((payload) => {
        if (!alive) return
        const record = recordsFromPayload(payload).find((item) => firstText(item, ['id', 'uuid', 'pk']) === editId)
        if (record) setForm((current) => formFromAgendaRecord(record, current))
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [editId])

  useEffect(() => {
    if (editId) return
    let alive = true
    fetch('/api/v1/ui/agenda/nuovo/defaults', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then((response) => response.ok ? safeJson(response) : null)
      .then((payload) => {
        if (!alive || !isRecord(payload)) return
        const avvocato = firstText(payload, ['avvocato', 'responsabile'])
        if (!avvocato) return
        setForm((current) => current.avvocato ? current : { ...current, avvocato })
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [editId])

  useEffect(() => {
    if (!form.id_cliente) return
    let alive = true
    fetch(`/api/clienti/${encodeURIComponent(form.id_cliente)}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then((response) => response.ok ? safeJson(response) : null)
      .then((payload) => normaliseClientSuggestion(payload))
      .then((client) => {
        if (!alive || !client) return
        setForm((current) => ({
          ...current,
          cliente: clientName(client) || current.cliente,
          cf_cliente: (client.codice_fiscale || current.cf_cliente || '').toUpperCase(),
          procedimento: client.procedimento || client.numero_procedimento || current.procedimento,
          tribunale: client.tribunale || current.tribunale,
          avvocato: client.avvocato || current.avvocato,
        }))
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [form.id_cliente])

  useEffect(() => {
    const query = form.cliente.trim()
    if (query.length < 2) {
      setClientMatches([])
      setClientDropdownOpen(false)
      return
    }

    let alive = true
    const timer = window.setTimeout(() => {
      setClientLoading(true)
      const params = new URLSearchParams({ q: query, autocomplete: '1', limit: '8' })
      fetch(`/api/clienti?${params.toString()}`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      })
        .then((response) => response.ok ? safeJson(response) : [])
        .then((data) => {
          if (!alive) return
          setClientMatches(clientSuggestionsFromPayload(data))
          setClientDropdownOpen(true)
        })
        .catch(() => {
          if (!alive) return
          setClientMatches([])
          setClientDropdownOpen(true)
        })
        .finally(() => {
          if (alive) setClientLoading(false)
        })
    }, 180)

    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [form.cliente])

  useEffect(() => {
    if (!form.data) {
      setDayEvents([])
      return
    }

    let alive = true
    setAgendaLoading(true)
    fetch(`/api/agenda?da=${encodeURIComponent(form.data)}&a=${encodeURIComponent(form.data)}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then((response) => response.ok ? safeJson(response) : [])
      .then((data) => {
        if (alive) setDayEvents(agendaItemsFromPayload(data))
      })
      .catch(() => {
        if (alive) setDayEvents([])
      })
      .finally(() => {
        if (alive) setAgendaLoading(false)
      })

    return () => {
      alive = false
    }
  }, [form.data])

  const selectClient = (client: ClientSuggestion) => {
    const safeClient = normaliseClientSuggestion(client)
    if (!safeClient) return
    const name = clientName(safeClient)
    if (!name && !safeClient.id) return
    setForm((current) => ({
      ...current,
      cliente: name || current.cliente,
      id_cliente: safeClient.id || current.id_cliente,
      cf_cliente: (safeClient.codice_fiscale || current.cf_cliente || '').toUpperCase(),
      procedimento: safeClient.procedimento || safeClient.numero_procedimento || current.procedimento,
      tribunale: safeClient.tribunale || current.tribunale,
      avvocato: safeClient.avvocato || current.avvocato,
    }))
    setClientDropdownOpen(false)
  }

  const applyTypePreset = (nextType: AppointmentType) => {
    const preset = appointmentTypes.find((item) => item.value === nextType) ?? appointmentTypes[0]
    setForm((current) => {
      const next = {
        ...current,
        tipo: nextType,
        durata: preset.duration,
        reminder: preset.reminder,
      }
      return {
        ...next,
        titolo: current.titolo.trim() ? current.titolo : buildSuggestedTitle(next),
      }
    })
  }

  const applyOfficeKind = (kind: string) => {
    const value = kind === 'Cassazione' ? 'Corte di Cassazione' : `${kind} di `
    update('tribunale', value)
    window.setTimeout(() => courtInputRef.current?.focus(), 0)
  }

  const applySuggestedTitle = () => {
    update('titolo', suggestedTitle)
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSubmit) {
      setShowValidation(true)
      setSubmitState({ saving: false, tone: 'danger', message: 'Completa i campi obbligatori e risolvi le sovrapposizioni.' })
      return
    }
    setSubmitState({ saving: true, tone: 'neutral', message: 'Salvataggio in corso...' })
    try {
      const result = await submitFormJson(formAction, new FormData(event.currentTarget))
      setSubmitState({ saving: false, tone: 'success', message: result.message || 'Appuntamento salvato.' })
      redirectAfterSuccess(result, cancelHref)
    } catch (error) {
      setSubmitState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }

  return (
    <main className="iu-appointment-page" aria-label={isEditMode ? 'Modifica appuntamento' : 'Nuovo appuntamento'}>
      <section className="iu-appt-hero">
        <div className="iu-appt-hero__main">
          <span className="iu-appt-eyebrow">
            <CalendarPlus size={16} />
            Agenda studio
          </span>
          <h1>{isEditMode ? 'Modifica appuntamento' : 'Nuovo appuntamento'}</h1>
          <p>{isEditMode ? "Aggiorna l'impegno mantenendo controlli, sovrapposizioni e collegamenti allo studio." : 'Inserimento rapido, leggibile e controllato per udienze, consultazioni, riunioni, depositi e scadenze.'}</p>
        </div>
        <div className="iu-appt-hero__actions">
          <a className="iu-appt-ghost" href="/agenda">
            <ArrowLeft size={16} />
            Agenda
          </a>
          <a className="iu-appt-ghost" href="/impostazioni/calendario">
            <CalendarCheck size={16} />
            Sincronizza calendari
          </a>
        </div>
      </section>

      <div className="iu-appt-layout">
        <form className="iu-appt-form" onSubmit={handleSubmit}>
          <input type="hidden" name="id_cliente" value={form.id_cliente} />
          <input type="hidden" name="from_cliente" value={form.from_cliente} />

          <section className="iu-appt-card">
            <header className="iu-appt-card__head">
              <div>
                <CalendarDays size={18} />
                <span>
                  <strong>Dati appuntamento</strong>
                  <small>Campi principali e collegamenti operativi</small>
                </span>
              </div>
              <Badge tone={typeMeta.tone}>{typeMeta.label}</Badge>
            </header>

            <div className="iu-appt-typegrid" aria-label="Tipi di appuntamento">
              {appointmentTypes.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  className={`iu-appt-type ${form.tipo === item.value ? 'is-active' : ''}`}
                  onClick={() => applyTypePreset(item.value)}
                >
                  <span>{item.label}</span>
                  <small>{item.description}</small>
                </button>
              ))}
            </div>

            <div className="iu-appt-form-grid">
              <Field label="Titolo" required icon={<FileText size={16} />} wide>
                <div className="iu-appt-titleline">
                  <input
                    name="titolo"
                    value={form.titolo}
                    onChange={(event) => update('titolo', event.currentTarget.value)}
                    placeholder="es. Udienza RG 1234/2024 - Rossi c/ Bianchi"
                    required
                  />
                  <button type="button" onClick={applySuggestedTitle}>
                    <Sparkles size={15} />
                    Completa
                  </button>
                </div>
              </Field>

              <Field label="Tipo" required icon={<Info size={16} />}>
                <select
                  name="tipo"
                  value={form.tipo}
                  onChange={(event) => applyTypePreset(event.currentTarget.value as AppointmentType)}
                  required
                >
                  {appointmentTypes.map((item) => (
                    <option key={item.value} value={item.value}>{item.value}</option>
                  ))}
                </select>
              </Field>

              <Field label="Data" required icon={<CalendarDays size={16} />}>
                <input
                  name="data"
                  type="date"
                  value={form.data}
                  onChange={(event) => update('data', event.currentTarget.value)}
                  required
                />
              </Field>

              <Field label="Ora" required icon={<Clock3 size={16} />}>
                <input
                  name="ora"
                  type="time"
                  value={form.ora}
                  onChange={(event) => update('ora', event.currentTarget.value)}
                  required
                />
              </Field>

              <Field label="Durata (minuti)" icon={<Clock3 size={16} />}>
                <input
                  name="durata"
                  type="number"
                  min="5"
                  step="5"
                  value={form.durata}
                  onChange={(event) => update('durata', event.currentTarget.value)}
                />
              </Field>

              <Field label="Promemoria (min prima)" icon={<Bell size={16} />}>
                <input
                  name="reminder"
                  type="number"
                  min="0"
                  value={form.reminder}
                  onChange={(event) => update('reminder', event.currentTarget.value)}
                />
              </Field>

              <Field label="Luogo / Aula" icon={<MapPin size={16} />}>
                <input
                  name="luogo"
                  value={form.luogo}
                  onChange={(event) => update('luogo', event.currentTarget.value)}
                  placeholder="es. Aula 3 - Piano 2, Studio, Teams"
                />
              </Field>

              <Field label="Cliente" icon={<UserRound size={16} />}>
                <div className="iu-appt-client-combo">
                  <Search size={16} />
                  <input
                    name="cliente"
                    value={form.cliente}
                    onFocus={() => {
                      if (form.cliente.trim().length > 1) setClientDropdownOpen(true)
                    }}
                    onBlur={() => window.setTimeout(() => setClientDropdownOpen(false), 160)}
                    onChange={(event) => {
                      const value = event.currentTarget.value
                      setForm((current) => ({
                        ...current,
                        cliente: value,
                        id_cliente: '',
                        cf_cliente: '',
                        procedimento: '',
                        tribunale: '',
                      }))
                    }}
                    placeholder="Digita per cercare..."
                    autoComplete="off"
                  />
                  {form.cliente ? (
                    <button
                      type="button"
                      aria-label="Svuota cliente"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => setForm((current) => ({
                        ...current,
                        cliente: '',
                        cf_cliente: '',
                        id_cliente: '',
                        procedimento: '',
                        tribunale: '',
                      }))}
                    >
                      <X size={14} />
                    </button>
                  ) : null}
                  {clientDropdownOpen ? (
                    <div className="iu-appt-client-menu">
                      {clientLoading ? <span>Ricerca clienti...</span> : null}
                      {!clientLoading && !safeClientMatches.length ? <span>Nessun cliente trovato</span> : null}
                      {safeClientMatches.map((client, index) => {
                        const name = clientName(client)
                        const detail = asText(client.codice_fiscale) || asText(client.email) || 'Anagrafica studio'
                        return (
                          <button
                            key={client.id || name || `cliente-${index}`}
                            type="button"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => selectClient(client)}
                          >
                            <strong>{name || 'Cliente senza nome'}</strong>
                            <small>{detail}</small>
                          </button>
                        )
                      })}
                    </div>
                  ) : null}
                </div>
              </Field>

              <Field label="Codice fiscale cliente" icon={<ShieldCheck size={16} />}>
                <input
                  className="iu-appt-uppercase"
                  name="cf_cliente"
                  value={form.cf_cliente}
                  onChange={(event) => update('cf_cliente', event.currentTarget.value.toUpperCase().replace(/\s/g, '').slice(0, 16))}
                  placeholder="RSSMRA80A01H501Z"
                  maxLength={16}
                />
              </Field>

              <Field label="Numero procedimento" icon={<FileText size={16} />}>
                <input
                  name="procedimento"
                  value={form.procedimento}
                  onChange={(event) => update('procedimento', event.currentTarget.value)}
                  placeholder="RG 1234/2024"
                />
              </Field>

              <Field label="Tribunale / Ufficio" icon={<Landmark size={16} />}>
                <div className="iu-appt-office">
                  <div className="iu-appt-office__chips" aria-label="Scorciatoie ufficio giudiziario">
                    {officeKinds.map((kind) => (
                      <button key={kind} type="button" onClick={() => applyOfficeKind(kind)}>
                        {kind}
                      </button>
                    ))}
                  </div>
                  <input
                    ref={courtInputRef}
                    name="tribunale"
                    value={form.tribunale}
                    onChange={(event) => update('tribunale', event.currentTarget.value)}
                    placeholder="Cerca per citta o nome..."
                  />
                </div>
              </Field>

              <Field label="Avvocato responsabile" icon={<UserRound size={16} />}>
                <input
                  name="avvocato"
                  value={form.avvocato}
                  onChange={(event) => update('avvocato', event.currentTarget.value)}
                  placeholder="Avv. Mario Rossi"
                />
              </Field>

              <Field label="Note" icon={<FileText size={16} />} wide>
                <textarea
                  name="note"
                  value={form.note}
                  onChange={(event) => update('note', event.currentTarget.value)}
                  placeholder="Note libere, collegamenti al fascicolo, indicazioni per collaboratori..."
                  rows={4}
                />
              </Field>
            </div>

            {showValidation && !canSubmit ? (
              <div className="iu-appt-validation" role="alert">
                <AlertTriangle size={16} />
                Completa i campi obbligatori e risolvi eventuali sovrapposizioni prima di salvare.
              </div>
            ) : null}

            <div className="iu-appt-submitbar">
              <a className="iu-appt-cancel" href={cancelHref}>Annulla</a>
              <button className="iu-appt-outline" type="button" onClick={applySuggestedTitle}>
                <Sparkles size={16} />
                Completa titolo
              </button>
              <button className="iu-appt-submit" type="submit" disabled={!canSubmit || submitState.saving}>
                <Send size={16} />
                {submitState.saving ? 'Salvataggio...' : isEditMode ? 'Salva modifiche' : 'Aggiungi appuntamento'}
              </button>
            </div>
            {submitState.message ? (
              <p className={`iu-appt-validation iu-appt-validation--${submitState.tone}`} role={submitState.tone === 'danger' ? 'alert' : 'status'}>
                {submitState.tone === 'danger' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
                {submitState.message}
              </p>
            ) : null}
          </section>
        </form>

        <aside className="iu-appt-side" aria-label="Controlli appuntamento">
          <section className="iu-appt-side-card iu-appt-preview">
            <header>
              <span>
                <CalendarCheck size={17} />
                Anteprima
              </span>
              <Badge tone={canSubmit ? 'success' : 'warning'}>{completion}/{qualityChecks.length}</Badge>
            </header>
            <h2>{form.titolo || suggestedTitle}</h2>
            <dl>
              <div>
                <dt>Quando</dt>
                <dd>{formatDateLabel(form.data)}</dd>
              </div>
              <div>
                <dt>Orario</dt>
                <dd>{formatRange(form)}</dd>
              </div>
              <div>
                <dt>Cliente</dt>
                <dd>{form.cliente || 'Non collegato'}</dd>
              </div>
              <div>
                <dt>Ufficio</dt>
                <dd>{form.tribunale || 'Non indicato'}</dd>
              </div>
            </dl>

            <div className={`iu-appt-conflict-box ${conflicts.length ? 'has-conflicts' : ''}`}>
              {agendaLoading ? (
                <p>Controllo disponibilita...</p>
              ) : conflicts.length ? (
                <>
                  <strong><AlertTriangle size={15} /> Sovrapposizione rilevata</strong>
                  {conflicts.map((item) => (
                    <span key={asText(item.id)}>{formatAgendaItemRange(item)} - {asText(item.titolo, 'Appuntamento')}</span>
                  ))}
                </>
              ) : (
                <strong><CheckCircle2 size={15} /> Nessuna sovrapposizione nota</strong>
              )}
            </div>
          </section>

          <section className="iu-appt-side-card">
            <header>
              <span>
                <ShieldCheck size={17} />
                Checklist qualita
              </span>
            </header>
            <div className="iu-appt-checks">
              {qualityChecks.map((check) => (
                <div className={check.ok ? 'is-ok' : ''} key={check.id}>
                  {check.ok ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  <span>
                    <strong>{check.label}{check.required ? ' *' : ''}</strong>
                    <small>{check.help}</small>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="iu-appt-side-card">
            <header>
              <span>
                <Info size={17} />
                Cosa e integrato
              </span>
            </header>
            <ul className="iu-appt-integrations">
              <li><ChevronRight size={14} /> Salvataggio immediato senza uscire dalla pagina</li>
              <li><ChevronRight size={14} /> Ricerca cliente collegata alle anagrafiche reali</li>
              <li><ChevronRight size={14} /> Controllo sovrapposizioni sul giorno selezionato</li>
              <li><ChevronRight size={14} /> Feed WebCal/iCal gia compatibili con l agenda</li>
              <li><ChevronRight size={14} /> Contesto appuntamento pronto per Lex e regia operativa</li>
            </ul>
          </section>
        </aside>
      </div>

    </main>
  )
}
