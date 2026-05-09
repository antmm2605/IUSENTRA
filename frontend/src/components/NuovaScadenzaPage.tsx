import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Bell,
  BookOpen,
  Building2,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronRight,
  Clock3,
  ExternalLink,
  FileText,
  Info,
  Landmark,
  ListChecks,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import type { Tone } from '../data'
import { sanitizeDisplayText } from '../displayText'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'
import { Badge } from './dashboard'
import './NuovaScadenzaPage.css'

type DeadlineType =
  | 'UDIENZA'
  | 'DEPOSITO_MEMORIA'
  | 'DEPOSITO_ATTO'
  | 'NOTIFICA'
  | 'IMPUGNAZIONE'
  | 'RISPOSTA_ECCEZIONE'
  | 'PAGAMENTO'
  | 'PRESCRIZIONE'
  | 'DECADENZA'
  | 'ADEMPIMENTO'
  | 'TERMINE_PERENTORIO'
  | 'TERMINE_ORDINATORIO'
  | 'ALTRO'

type DeadlineForm = {
  titolo: string
  tipo: DeadlineType
  preset: string
  deadline_profile_code: string
  source_event_at: string
  data_scadenza: string
  data_decorrenza: string
  perentorio: boolean
  id_fascicolo: string
  id_utente: string
  descrizione: string
  note: string
  judicial_office_id: string
  office_patron_name: string
  office_patron_day: string
  office_patron_month: string
  office_operating_mode: string
  office_source_url: string
  office_verified_at: string
  operational_lead_business_days: string
  october_observance_blocks: boolean
  id_cliente: string
  from_cliente: string
}

type DeadlinePreset = {
  key: string
  label: string
  description?: string
  title_template?: string
  deadline_profile_code?: string
  profile_code?: string
  tipo?: string
  type?: string
  source_event_type?: string
  [key: string]: unknown
}

type DeadlineProfile = {
  code: string
  label: string
  unit?: string
  quantity?: number
  notes?: string
}

type SelectOption = {
  id?: string
  value?: string
  label: string
  subtitle?: string
  badge?: string
}

type OfficeModeOption = {
  value: string
  label: string
}

type ContextPayload = {
  mode?: 'new' | 'edit'
  id_scadenza?: string
  preset_list?: DeadlinePreset[]
  profili_termine?: DeadlineProfile[]
  tipi?: SelectOption[]
  fascicoli?: SelectOption[]
  utenti?: SelectOption[]
  office_modes?: OfficeModeOption[]
  office_kinds?: string[]
  defaults?: Partial<DeadlineForm>
  studio?: {
    nome?: string
    patron_name?: string
    patron_day?: number | string
    patron_month?: number | string
  }
  actions?: {
    write_endpoint?: string
    calculate_endpoint?: string
    legacy_fallback?: string
    detail?: string
    list?: string
  }
}

type CalculationResult = {
  data_scadenza?: string
  raw_due_at?: string
  legal_due_at?: string
  operational_due_at?: string | null
  office_mode_on_legal_due_date?: string
  trace?: string[]
  operational_notes?: string[] | string
  judicial_office_name?: string
  profile_code?: string
  profile_label?: string
}

type CheckItem = {
  id: string
  label: string
  help: string
  ok: boolean
  required?: boolean
  tone?: Tone
}
type SubmitState = { saving: boolean; tone: 'success' | 'danger' | 'neutral'; message: string }

const fallbackTypes: SelectOption[] = [
  { value: 'UDIENZA', label: 'UDIENZA' },
  { value: 'DEPOSITO_MEMORIA', label: 'DEPOSITO_MEMORIA' },
  { value: 'DEPOSITO_ATTO', label: 'DEPOSITO_ATTO' },
  { value: 'NOTIFICA', label: 'NOTIFICA' },
  { value: 'IMPUGNAZIONE', label: 'IMPUGNAZIONE' },
  { value: 'RISPOSTA_ECCEZIONE', label: 'RISPOSTA_ECCEZIONE' },
  { value: 'PAGAMENTO', label: 'PAGAMENTO' },
  { value: 'PRESCRIZIONE', label: 'PRESCRIZIONE' },
  { value: 'DECADENZA', label: 'DECADENZA' },
  { value: 'ADEMPIMENTO', label: 'ADEMPIMENTO' },
  { value: 'TERMINE_PERENTORIO', label: 'TERMINE_PERENTORIO' },
  { value: 'TERMINE_ORDINATORIO', label: 'TERMINE_ORDINATORIO' },
  { value: 'ALTRO', label: 'ALTRO' },
]

const fallbackOfficeModes: OfficeModeOption[] = [
  { value: 'open', label: 'Aperto' },
  { value: 'closed', label: 'Chiuso' },
  { value: 'urgent_only', label: 'Solo atti urgenti' },
  { value: 'limited_hours', label: 'Orari limitati' },
]

const defaultOfficeKinds = [
  'Tutti',
  'Tribunale',
  'Procura',
  'Proc.Gen.',
  "Corte d'App.",
  'Cassazione',
  'Assise',
  'G.d.P.',
  'Minori',
  'Sorv.',
  'TAR',
  'CdS',
  'CGARS',
  'CGT',
  'CPT',
]

const typeTone: Record<string, Tone> = {
  UDIENZA: 'primary',
  DEPOSITO_MEMORIA: 'warning',
  DEPOSITO_ATTO: 'warning',
  NOTIFICA: 'info',
  IMPUGNAZIONE: 'danger',
  RISPOSTA_ECCEZIONE: 'purple',
  PAGAMENTO: 'success',
  PRESCRIZIONE: 'danger',
  DECADENZA: 'danger',
  ADEMPIMENTO: 'primary',
  TERMINE_PERENTORIO: 'danger',
  TERMINE_ORDINATORIO: 'neutral',
  ALTRO: 'neutral',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asText(value: unknown, fallback = ''): string {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value).trim()
  return fallback
}

function displayText(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(asText(value, fallback))
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

function initialForm(): DeadlineForm {
  const params = new URLSearchParams(window.location.search)
  return {
    titolo: '',
    tipo: 'UDIENZA',
    preset: params.get('preset') ?? '',
    deadline_profile_code: params.get('deadline_profile_code') ?? '',
    source_event_at: params.get('source_event_at') ?? '',
    data_scadenza: params.get('data_scadenza') ?? '',
    data_decorrenza: params.get('data_decorrenza') ?? '',
    perentorio: params.get('perentorio') === '1',
    id_fascicolo: params.get('id_fascicolo') ?? '',
    id_utente: params.get('id_utente') ?? '',
    descrizione: '',
    note: '',
    judicial_office_id: '',
    office_patron_name: '',
    office_patron_day: '',
    office_patron_month: '',
    office_operating_mode: 'open',
    office_source_url: '',
    office_verified_at: '',
    operational_lead_business_days: '2',
    october_observance_blocks: false,
    id_cliente: params.get('id_cliente') ?? '',
    from_cliente: params.get('from_cliente') ?? '',
  }
}

function editDeadlineId(): string {
  const match = window.location.pathname.match(/^\/scadenziario\/([^/]+)\/modifica$/)
  return match ? decodeURIComponent(match[1]) : ''
}

function formatDateLabel(value: string | undefined | null): string {
  const raw = String(value || '').slice(0, 10)
  if (!raw) return '—'
  try {
    return new Date(`${raw}T12:00:00`).toLocaleDateString('it-IT', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return raw
  }
}

function formatDateTimeLabel(value: string | undefined | null): string {
  const raw = String(value || '')
  if (!raw) return '—'
  try {
    const parsed = new Date(raw)
    return parsed.toLocaleString('it-IT', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return raw
  }
}

function normalisePayload(payload: unknown): ContextPayload {
  if (!isRecord(payload)) return {}
  return payload as ContextPayload
}

function selectedLabel(options: SelectOption[], value: string): string {
  const item = options.find((option) => (option.value || option.id || '') === value)
  return displayText(item?.label || value || '—')
}

function presetProfile(preset: DeadlinePreset | undefined): string {
  if (!preset) return ''
  return asText(preset.deadline_profile_code) || asText(preset.profile_code) || asText(preset.profile)
}

function presetType(preset: DeadlinePreset | undefined): DeadlineType | '' {
  const value = (asText(preset?.tipo) || asText(preset?.type)).toUpperCase()
  return fallbackTypes.some((item) => item.value === value) ? value as DeadlineType : ''
}

function buildSuggestedTitle(form: DeadlineForm, preset?: DeadlinePreset): string {
  const presetTitle = asText(preset?.title_template) || asText(preset?.titolo)
  if (presetTitle) return presetTitle
  const kind = form.tipo.replaceAll('_', ' ').toLowerCase()
  const due = form.data_scadenza ? ` del ${formatDateLabel(form.data_scadenza)}` : ''
  return `${kind.charAt(0).toUpperCase()}${kind.slice(1)}${due}`.trim()
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
    <div className={`iu-deadline-field ${wide ? 'is-wide' : ''}`}>
      <span className="iu-deadline-label">
        {icon}
        {label}
        {required ? <b>*</b> : null}
      </span>
      {children}
    </div>
  )
}

function SummaryTile({ label, value, note, tone = 'neutral' }: { label: string; value: string; note?: string; tone?: Tone }) {
  return (
    <div className={`iu-deadline-summary-tile is-${tone}`}>
      <span>{label}</span>
      <strong>{value || '—'}</strong>
      {note ? <small>{note}</small> : null}
    </div>
  )
}

function OperationalCard({
  icon,
  title,
  text,
  href,
  disabled,
}: {
  icon: ReactNode
  title: string
  text: string
  href: string
  disabled?: boolean
}) {
  const body = (
    <>
      <span>{icon}</span>
      <div>
        <strong>{title}</strong>
        <small>{text}</small>
      </div>
      <ChevronRight size={16} />
    </>
  )
  if (disabled) return <span className="iu-deadline-op-card is-disabled">{body}</span>
  return <a className="iu-deadline-op-card" href={href}>{body}</a>
}

export function NuovaScadenzaPage() {
  const editId = editDeadlineId()
  const [form, setForm] = useState<DeadlineForm>(() => initialForm())
  const [context, setContext] = useState<ContextPayload>({})
  const [contextLoading, setContextLoading] = useState(true)
  const [calcLoading, setCalcLoading] = useState(false)
  const [calcResult, setCalcResult] = useState<CalculationResult | null>(null)
  const [calcError, setCalcError] = useState('')
  const [showValidation, setShowValidation] = useState(false)
  const [submitState, setSubmitState] = useState<SubmitState>({ saving: false, tone: 'neutral', message: '' })
  const [officeQuery, setOfficeQuery] = useState('')
  const officeInputRef = useRef<HTMLInputElement>(null)

  const presets = context.preset_list || []
  const profiles = context.profili_termine || []
  const deadlineTypes = context.tipi?.length ? context.tipi : fallbackTypes
  const matters = context.fascicoli || []
  const users = context.utenti || []
  const officeModes = context.office_modes?.length ? context.office_modes : fallbackOfficeModes
  const officeKinds = context.office_kinds?.length ? context.office_kinds : defaultOfficeKinds
  const activePreset = presets.find((preset) => preset.key === form.preset)
  const selectedProfile = profiles.find((profile) => profile.code === form.deadline_profile_code)
  const selectedMatter = matters.find((item) => (item.id || item.value || '') === form.id_fascicolo)
  const selectedOwner = users.find((item) => (item.id || item.value || '') === form.id_utente)
  const summaryDue = calcResult?.data_scadenza || form.data_scadenza

  const update = <K extends keyof DeadlineForm>(field: K, value: DeadlineForm[K]) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  useEffect(() => {
    let alive = true
    setContextLoading(true)
    const params = new URLSearchParams()
    if (editId) params.set('id_scadenza', editId)
    fetch(`/api/v1/ui/scadenziario/nuova${params.toString() ? `?${params.toString()}` : ''}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then((response) => response.ok ? safeJson(response) : null)
      .then((payload) => {
        if (!alive) return
        const next = normalisePayload(payload)
        setContext(next)
        setForm((current) => ({
          ...current,
          ...Object.fromEntries(
            Object.entries(next.defaults || {}).filter(([, value]) => value !== undefined && value !== ''),
          ),
          office_patron_name: current.office_patron_name || asText(next.studio?.patron_name),
          office_patron_day: current.office_patron_day || asText(next.studio?.patron_day),
          office_patron_month: current.office_patron_month || asText(next.studio?.patron_month),
        }))
      })
      .catch(() => undefined)
      .finally(() => {
        if (alive) setContextLoading(false)
      })
    return () => {
      alive = false
    }
  }, [editId])

  const qualityChecks = useMemo<CheckItem[]>(() => [
    {
      id: 'titolo',
      label: 'Titolo riconoscibile',
      help: 'Serve a capire subito atto, udienza, fascicolo o attività.',
      ok: form.titolo.trim().length >= 4,
      required: true,
      tone: 'primary',
    },
    {
      id: 'tipo',
      label: 'Tipo termine',
      help: 'Classifica correttamente deposito, impugnazione, udienza o altro adempimento.',
      ok: Boolean(form.tipo),
      required: true,
      tone: 'primary',
    },
    {
      id: 'calcolo',
      label: 'Data scadenza presente',
      help: 'Può arrivare dal motore di calcolo oppure da inserimento manuale controllato.',
      ok: Boolean(summaryDue),
      required: true,
      tone: summaryDue ? 'success' : 'warning',
    },
    {
      id: 'decorrenza',
      label: 'Decorrenza o evento origine',
      help: 'Rende spiegabile il calcolo e aiuta audit e revisione.',
      ok: Boolean(form.source_event_at || form.data_decorrenza),
      tone: 'warning',
    },
    {
      id: 'fascicolo',
      label: 'Fascicolo collegato',
      help: 'Consigliato per cabina fascicolo, notifiche e ricerca studio.',
      ok: Boolean(form.id_fascicolo),
      tone: 'purple',
    },
    {
      id: 'responsabile',
      label: 'Responsabile assegnato',
      help: 'Evita scadenze senza presidio operativo.',
      ok: Boolean(form.id_utente),
      tone: 'orange',
    },
    {
      id: 'ufficio',
      label: 'Calendario ufficio verificato',
      help: 'Patrono, fonte e modalità ufficio incidono sul calcolo professionale.',
      ok: Boolean(form.office_patron_name || form.office_source_url || form.judicial_office_id),
      tone: 'info',
    },
    {
      id: 'trace',
      label: 'Trace disponibile',
      help: 'Mostra perché una data è stata spostata, anticipata o mantenuta.',
      ok: Boolean(calcResult?.trace?.length),
      tone: 'success',
    },
  ], [calcResult?.trace?.length, form, summaryDue])

  const requiredOk = qualityChecks.filter((check) => check.required).every((check) => check.ok)
  const completion = qualityChecks.filter((check) => check.ok).length
  const canSubmit = requiredOk && !calcLoading
  const isEditMode = context.mode === 'edit' || Boolean(editId)
  const writeEndpoint = context.actions?.write_endpoint || (isEditMode && editId ? `/scadenziario/${encodeURIComponent(editId)}/modifica` : '/scadenziario/nuova')
  const cancelHref = context.actions?.detail || (form.from_cliente || form.id_cliente ? `/clienti/${form.from_cliente || form.id_cliente}` : '/scadenziario')
  const calculatedNotes = Array.isArray(calcResult?.operational_notes)
    ? calcResult?.operational_notes || []
    : asText(calcResult?.operational_notes) ? [asText(calcResult?.operational_notes)] : []

  const applyPreset = (key: string) => {
    const preset = presets.find((item) => item.key === key)
    setCalcResult(null)
    setCalcError('')
    setForm((current) => {
      const profile = presetProfile(preset)
      const nextType = presetType(preset) || current.tipo
      const next = {
        ...current,
        preset: key,
        deadline_profile_code: profile || current.deadline_profile_code,
        tipo: nextType,
      }
      return {
        ...next,
        titolo: current.titolo.trim() ? current.titolo : buildSuggestedTitle(next, preset),
      }
    })
  }

  const applySuggestedTitle = () => {
    setForm((current) => ({ ...current, titolo: buildSuggestedTitle(current, activePreset) }))
  }

  const applyOfficeKind = (kind: string) => {
    const next = kind === 'Tutti' ? '' : kind === 'Cassazione' ? 'Corte di Cassazione' : `${kind} di `
    setOfficeQuery(next)
    update('judicial_office_id', next)
    window.setTimeout(() => officeInputRef.current?.focus(), 0)
  }

  const calculateDeadline = async () => {
    setCalcError('')
    if (!form.source_event_at) {
      setCalcError('Inserisci evento origine per usare il motore di calcolo.')
      return
    }
    if (!form.preset && !form.deadline_profile_code) {
      setCalcError('Seleziona un preset o un profilo termine.')
      return
    }
    setCalcLoading(true)
    try {
      const response = await fetch('/scadenziario/calcola-termine', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          preset: form.preset,
          deadline_profile_code: form.deadline_profile_code,
          source_event_at: form.source_event_at,
          data_decorrenza: form.data_decorrenza,
          judicial_office_id: form.judicial_office_id,
          office_patron_name: form.office_patron_name,
          office_patron_day: form.office_patron_day,
          office_patron_month: form.office_patron_month,
          office_operating_mode: form.office_operating_mode,
          office_source_url: form.office_source_url,
          office_verified_at: form.office_verified_at,
          operational_lead_business_days: form.operational_lead_business_days,
          october_observance_blocks: form.october_observance_blocks,
        }),
      })
      const payload = await safeJson(response)
      if (!response.ok || !isRecord(payload)) {
        const message = isRecord(payload) ? asText(payload.errore, 'Calcolo non riuscito.') : 'Calcolo non riuscito.'
        throw new Error(message)
      }
      const result = payload as CalculationResult
      setCalcResult(result)
      setForm((current) => ({
        ...current,
        data_scadenza: result.data_scadenza || current.data_scadenza,
        data_decorrenza: current.data_decorrenza || current.source_event_at.slice(0, 10),
        deadline_profile_code: result.profile_code || current.deadline_profile_code,
      }))
    } catch (error) {
      setCalcError(error instanceof Error ? error.message : 'Calcolo non riuscito.')
      setCalcResult(null)
    } finally {
      setCalcLoading(false)
    }
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSubmit) {
      setShowValidation(true)
      setSubmitState({ saving: false, tone: 'danger', message: 'Completa i dati necessari prima del salvataggio.' })
      return
    }
    setSubmitState({ saving: true, tone: 'neutral', message: 'Salvataggio in corso...' })
    try {
      const result = await submitFormJson(writeEndpoint, new FormData(event.currentTarget))
      setSubmitState({ saving: false, tone: 'success', message: result.message || 'Scadenza salvata.' })
      redirectAfterSuccess(result, cancelHref)
    } catch (error) {
      setSubmitState({ saving: false, tone: 'danger', message: error instanceof Error ? error.message : 'Salvataggio non riuscito.' })
    }
  }

  return (
    <main className="iu-deadline-page" aria-label={isEditMode ? 'Modifica scadenza' : 'Nuova scadenza'}>
      <section className="iu-deadline-hero">
        <div className="iu-deadline-hero__main">
          <span className="iu-deadline-eyebrow"><CalendarPlus size={16} /> Scadenziario professionale</span>
          <h1>{isEditMode ? 'Modifica scadenza' : 'Nuova scadenza'}</h1>
          <p>{isEditMode ? 'Aggiorna una scadenza esistente mantenendo validazioni e tracciamento.' : 'Calcolo termini con preset processuali, calendario nazionale, patroni studio/ufficio, anticipo operativo e verifica del percorso.'}</p>
        </div>
        <div className="iu-deadline-hero__actions">
          <a className="iu-deadline-ghost" href="/scadenziario"><ArrowLeft size={16} /> Scadenziario</a>
          <a className="iu-deadline-ghost" href="/agenda"><CalendarDays size={16} /> Agenda</a>
        </div>
      </section>

      <div className="iu-deadline-layout">
        <form className="iu-deadline-form" onSubmit={handleSubmit}>
          <input type="hidden" name="id_cliente" value={form.id_cliente} />
          <input type="hidden" name="from_cliente" value={form.from_cliente} />
          {form.october_observance_blocks ? <input type="hidden" name="october_observance_blocks" value="1" /> : null}

          <section className="iu-deadline-card iu-deadline-calculator-card">
            <header className="iu-deadline-card__head">
              <div>
                <Sparkles size={18} />
                <span>
                  <strong>Calcolo professionale del termine</strong>
                  <small>Preset processuale, profilo avanzato ed evento generatore</small>
                </span>
              </div>
              {contextLoading ? <Badge tone="neutral">Carico</Badge> : <Badge tone="success">Attivo</Badge>}
            </header>

            <div className="iu-deadline-form-grid">
              <Field label="Preset processuale" icon={<ListChecks size={16} />}>
                <select name="preset" value={form.preset} onChange={(event) => applyPreset(event.currentTarget.value)}>
                  <option value="">Nessun preset rapido</option>
                  {presets.map((preset) => (
                    <option key={preset.key} value={preset.key}>{displayText(preset.label)}</option>
                  ))}
                </select>
                <small className="iu-deadline-hint">Usa i preset per impugnazioni, memorie e termini processuali ricorrenti.</small>
              </Field>

              <Field label="Profilo termine" icon={<BookOpen size={16} />}>
                <select
                  name="deadline_profile_code"
                  value={form.deadline_profile_code}
                  onChange={(event) => {
                    update('deadline_profile_code', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                >
                  <option value="">Seleziona un profilo</option>
                  {profiles.map((profile) => (
                    <option key={profile.code} value={profile.code}>{displayText(profile.label)}</option>
                  ))}
                </select>
                <small className="iu-deadline-hint">Usalo quando vuoi il motore avanzato senza preset processuale.</small>
              </Field>

              <Field label="Evento origine" required icon={<Clock3 size={16} />}>
                <input
                  name="source_event_at"
                  type="datetime-local"
                  value={form.source_event_at}
                  onChange={(event) => {
                    update('source_event_at', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                />
                <small className="iu-deadline-hint">Data e ora da cui parte il termine: notifica, deposito, comunicazione o udienza.</small>
              </Field>

              <Field label="Anticipo operativo" icon={<Bell size={16} />}>
                <input
                  name="operational_lead_business_days"
                  type="number"
                  min="0"
                  max="30"
                  value={form.operational_lead_business_days}
                  onChange={(event) => {
                    update('operational_lead_business_days', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                />
                <small className="iu-deadline-hint">Giorni lavorativi interni da anticipare per lavorare senza affanno.</small>
              </Field>

              <div className="iu-deadline-switch-row">
                <label>
                  <input
                    type="checkbox"
                    checked={form.october_observance_blocks}
                    onChange={(event) => {
                      update('october_observance_blocks', event.currentTarget.checked)
                      setCalcResult(null)
                    }}
                  />
                  <span>4 ottobre bloccante</span>
                </label>
                <button type="button" className="iu-deadline-outline" onClick={calculateDeadline} disabled={calcLoading}>
                  {calcLoading ? <Loader2 size={16} className="iu-spin" /> : <Sparkles size={16} />}
                  Calcola termine
                </button>
              </div>

              {calcError ? (
                <div className="iu-deadline-alert"><AlertTriangle size={16} /> {calcError}</div>
              ) : null}
            </div>
          </section>

          <section className="iu-deadline-card">
            <header className="iu-deadline-card__head">
              <div>
                <Landmark size={18} />
                <span>
                  <strong>Calendario dell'ufficio competente</strong>
                  <small>Patrono, fonte e modalità nel giorno del patrono</small>
                </span>
              </div>
              <Badge tone="primary">Ufficio</Badge>
            </header>

            <div className="iu-deadline-office-kinds">
              {officeKinds.map((kind) => (
                <button key={kind} type="button" onClick={() => applyOfficeKind(kind)} className={officeQuery.startsWith(kind) ? 'is-active' : ''}>{kind}</button>
              ))}
            </div>

            <div className="iu-deadline-form-grid">
              <Field label="Ufficio giudiziario" icon={<Search size={16} />} wide>
                <input
                  ref={officeInputRef}
                  name="judicial_office_id"
                  value={form.judicial_office_id || officeQuery}
                  onChange={(event) => {
                    setOfficeQuery(event.currentTarget.value)
                    update('judicial_office_id', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                  placeholder="Cerca per città o nome..."
                />
              </Field>

              <Field label="Patrono ufficio" icon={<BadgeCheck size={16} />}>
                <input
                  name="office_patron_name"
                  value={form.office_patron_name}
                  onChange={(event) => {
                    update('office_patron_name', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                  placeholder="es. Santa Rosalia"
                />
              </Field>

              <Field label="Giorno" icon={<CalendarCheck size={16} />}>
                <input
                  name="office_patron_day"
                  type="number"
                  min="1"
                  max="31"
                  value={form.office_patron_day}
                  onChange={(event) => {
                    update('office_patron_day', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                />
              </Field>

              <Field label="Mese" icon={<CalendarCheck size={16} />}>
                <input
                  name="office_patron_month"
                  type="number"
                  min="1"
                  max="12"
                  value={form.office_patron_month}
                  onChange={(event) => {
                    update('office_patron_month', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                />
              </Field>

              <Field label="Modalità ufficio" icon={<Building2 size={16} />}>
                <select
                  name="office_operating_mode"
                  value={form.office_operating_mode}
                  onChange={(event) => {
                    update('office_operating_mode', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                >
                  {officeModes.map((mode) => <option key={mode.value} value={mode.value}>{displayText(mode.label)}</option>)}
                </select>
              </Field>

              <Field label="Fonte ufficio / avviso" icon={<ExternalLink size={16} />} wide>
                <input
                  name="office_source_url"
                  value={form.office_source_url}
                  onChange={(event) => update('office_source_url', event.currentTarget.value)}
                  placeholder="https://..."
                />
              </Field>

              <Field label="Ultima verifica" icon={<ShieldCheck size={16} />}>
                <input
                  name="office_verified_at"
                  type="date"
                  value={form.office_verified_at}
                  onChange={(event) => update('office_verified_at', event.currentTarget.value)}
                />
              </Field>
            </div>
          </section>

          <section className="iu-deadline-card">
            <header className="iu-deadline-card__head">
              <div>
                <FileText size={18} />
                <span>
                  <strong>Dati scadenza</strong>
                  <small>Titolo, tipo, fascicolo, responsabile, descrizione e note</small>
                </span>
              </div>
              <Badge tone={typeTone[form.tipo] || 'neutral'}>{form.tipo}</Badge>
            </header>

            <div className="iu-deadline-form-grid">
              <Field label="Titolo" required icon={<FileText size={16} />} wide>
                <div className="iu-deadline-titleline">
                  <input
                    name="titolo"
                    value={form.titolo}
                    onChange={(event) => update('titolo', event.currentTarget.value)}
                    placeholder="es. Deposito memoria art. 171-ter n. 1"
                    required
                  />
                  <button type="button" onClick={applySuggestedTitle}><Sparkles size={15} /> Completa</button>
                </div>
              </Field>

              <Field label="Tipo" required icon={<Info size={16} />}>
                <select
                  name="tipo"
                  value={form.tipo}
                  onChange={(event) => update('tipo', event.currentTarget.value as DeadlineType)}
                  required
                >
                  {deadlineTypes.map((item) => <option key={item.value || item.id || item.label} value={item.value || item.id || item.label}>{displayText(item.label)}</option>)}
                </select>
              </Field>

              <Field label="Data scadenza manuale" icon={<CalendarDays size={16} />}>
                <input
                  name="data_scadenza"
                  type="date"
                  value={form.data_scadenza}
                  onChange={(event) => {
                    update('data_scadenza', event.currentTarget.value)
                    setCalcResult(null)
                  }}
                />
                <small className="iu-deadline-hint">Usata solo se non attivi il motore di calcolo.</small>
              </Field>

              <Field label="Data decorrenza" icon={<CalendarDays size={16} />}>
                <input
                  name="data_decorrenza"
                  type="date"
                  value={form.data_decorrenza}
                  onChange={(event) => update('data_decorrenza', event.currentTarget.value)}
                />
              </Field>

              <div className="iu-deadline-toggle-field">
                <label>
                  <input
                    type="checkbox"
                    name="perentorio"
                    value="1"
                    checked={form.perentorio}
                    onChange={(event) => update('perentorio', event.currentTarget.checked)}
                  />
                  <span>Termine perentorio</span>
                </label>
                <small>Attivalo quando la perdita del termine produce effetti sostanziali o processuali.</small>
              </div>

              <Field label="Fascicolo" icon={<Building2 size={16} />}>
                <select name="id_fascicolo" value={form.id_fascicolo} onChange={(event) => update('id_fascicolo', event.currentTarget.value)}>
                  <option value="">Nessun fascicolo</option>
                  {matters.map((item) => <option key={item.id || item.value || item.label} value={item.id || item.value}>{displayText(item.label)}</option>)}
                </select>
              </Field>

              <Field label="Responsabile" icon={<UserRound size={16} />}>
                <select name="id_utente" value={form.id_utente} onChange={(event) => update('id_utente', event.currentTarget.value)}>
                  <option value="">Nessun responsabile</option>
                  {users.map((item) => <option key={item.id || item.value || item.label} value={item.id || item.value}>{displayText(item.label)}</option>)}
                </select>
              </Field>

              <Field label="Descrizione" icon={<FileText size={16} />} wide>
                <textarea
                  name="descrizione"
                  value={form.descrizione}
                  onChange={(event) => update('descrizione', event.currentTarget.value)}
                  placeholder="Contesto operativo, atto da predisporre, fonte del termine..."
                />
              </Field>

              <Field label="Note" icon={<Info size={16} />} wide>
                <textarea
                  name="note"
                  value={form.note}
                  onChange={(event) => update('note', event.currentTarget.value)}
                  placeholder="Annotazioni interne, verifiche, contatti o passaggi da eseguire..."
                />
              </Field>
            </div>

            {showValidation && !canSubmit ? (
              <div className="iu-deadline-validation"><AlertTriangle size={16} /> Completa i campi obbligatori prima di creare la scadenza.</div>
            ) : null}

            <div className="iu-deadline-submitbar">
              <a className="iu-deadline-cancel" href={cancelHref}>Annulla</a>
              <button className="iu-deadline-outline" type="button" onClick={calculateDeadline} disabled={calcLoading}>
                {calcLoading ? <Loader2 size={16} className="iu-spin" /> : <Sparkles size={16} />}
                Ricalcola
              </button>
              <button className="iu-deadline-submit" type="submit" disabled={!canSubmit || submitState.saving}>
                <CheckCircle2 size={17} /> {submitState.saving ? 'Salvataggio...' : isEditMode ? 'Salva modifiche' : 'Crea scadenza'}
              </button>
            </div>
            {submitState.message ? (
              <p className={`iu-deadline-validation iu-deadline-validation--${submitState.tone}`} role={submitState.tone === 'danger' ? 'alert' : 'status'}>
                {submitState.tone === 'danger' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
                {submitState.message}
              </p>
            ) : null}
          </section>
        </form>

        <aside className="iu-deadline-side" aria-label="Riepilogo nuova scadenza">
          <section className="iu-deadline-side-card">
            <header><span><Clock3 size={17} /> Riepilogo del calcolo</span><Badge tone="primary">{completion}/{qualityChecks.length}</Badge></header>
            <div className="iu-deadline-summary-grid">
              <SummaryTile label="Scadenza legale" value={formatDateLabel(calcResult?.legal_due_at || summaryDue)} tone={summaryDue ? 'danger' : 'neutral'} />
              <SummaryTile label="Scadenza operativa" value={formatDateLabel(calcResult?.operational_due_at || '')} note="Anticipo interno" tone="warning" />
              <SummaryTile label="Scadenza grezza" value={formatDateTimeLabel(calcResult?.raw_due_at || '')} tone="neutral" />
              <SummaryTile label="Modalità ufficio" value={calcResult?.office_mode_on_legal_due_date || selectedLabel(officeModes.map((item) => ({ value: item.value, label: item.label })), form.office_operating_mode)} tone="info" />
            </div>
            <div className="iu-deadline-studio-box">
              <strong>{context.studio?.nome || 'Studio'}</strong>
              <span>Patrono interno: {context.studio?.patron_name || 'non configurato'} {context.studio?.patron_day && context.studio?.patron_month ? `(${String(context.studio.patron_day).padStart(2, '0')}/${String(context.studio.patron_month).padStart(2, '0')})` : ''}</span>
            </div>
          </section>

          <section className="iu-deadline-side-card">
            <header><span><Sparkles size={17} /> Card operative</span></header>
            <div className="iu-deadline-operational-grid">
              <OperationalCard
                icon={<Building2 size={18} />}
                title="Apri fascicolo"
                text={displayText(selectedMatter?.subtitle || selectedMatter?.label || 'Collega un fascicolo per attivare la cabina')}
                href={form.id_fascicolo ? `/fascicoli/${encodeURIComponent(form.id_fascicolo)}` : '/fascicoli'}
                disabled={!form.id_fascicolo}
              />
              <OperationalCard
                icon={<CalendarPlus size={18} />}
                title="Agenda operativa"
                text="Crea appuntamento collegato alla data operativa o legale"
                href={`/agenda/nuovo${summaryDue ? `?data=${encodeURIComponent(summaryDue.slice(0, 10))}` : ''}`}
              />
              <OperationalCard icon={<CalendarDays size={18} />} title="Esporta calendario" text="Feed iCal scadenziario per calendari esterni" href="/scadenziario/export.ics" />
              <OperationalCard icon={<ListChecks size={18} />} title="Controlli atti" text="Checklist deposito e controlli preliminari" href="/deposito/checklist" />
              <OperationalCard icon={<Sparkles size={18} />} title="Chiedi a Lex" text="Analisi operativa della scadenza e prossima azione" href="#lex" />
            </div>
          </section>

          <section className="iu-deadline-side-card">
            <header><span><ShieldCheck size={17} /> Checklist qualità</span></header>
            <div className="iu-deadline-checks">
              {qualityChecks.map((check) => (
                <div key={check.id} className={check.ok ? 'is-ok' : ''}>
                  {check.ok ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
                  <span>
                    <strong>{displayText(check.label)}{check.required ? ' *' : ''}</strong>
                    <small>{check.help}</small>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="iu-deadline-side-card">
            <header><span><BookOpen size={17} /> Trace del calcolo</span></header>
            <ol className="iu-deadline-trace">
              {calcResult?.trace?.length ? calcResult.trace.map((item, index) => <li key={`${item}-${index}`}>{item}</li>) : <li>Seleziona profilo o preset e inserisci l'evento origine per vedere il trace.</li>}
            </ol>
            {calculatedNotes.length ? (
              <div className="iu-deadline-notes">
                {calculatedNotes.map((note) => <span key={note}>{note}</span>)}
              </div>
            ) : null}
          </section>

          <section className="iu-deadline-side-card">
            <header><span><Info size={17} /> Dati collegati</span></header>
            <dl className="iu-deadline-context-list">
              <div><dt>Preset</dt><dd>{displayText(activePreset?.label || '—')}</dd></div>
              <div><dt>Profilo</dt><dd>{displayText(selectedProfile?.label || '—')}</dd></div>
              <div><dt>Fascicolo</dt><dd>{displayText(selectedMatter?.label || '—')}</dd></div>
              <div><dt>Responsabile</dt><dd>{displayText(selectedOwner?.label || '—')}</dd></div>
            </dl>
          </section>
        </aside>
      </div>

    </main>
  )
}
