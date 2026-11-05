import { beginActivity } from '../ui/activity'
import { useBusyActivity } from '../ui/useBusyActivity'
import { SourceAlternatives } from './SourceAlternatives'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { publishMutationRefresh } from '../operationalRefresh'
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bell,
  BriefcaseBusiness,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  CalendarPlus,
  CalendarSync,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  FilePenLine,
  FileSearch,
  Filter,
  Landmark,
  ListChecks,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  UsersRound,
  Video,
  Trash2,
} from 'lucide-react'
import { AgendaResearchFilters, emptyAgendaFilters, matchesAgendaFilters, type AgendaFilters } from './AgendaResearchFilters'
import './AgendaResearch.css'
import { AgendaRuolo } from '../features/agenda/ruolo/AgendaRuolo'
import { AgendaScheda } from '../features/agenda/ruolo/AgendaScheda'
import { corrispondeFiltro, daLavorare, type FiltroRapido } from '../features/agenda/ruolo/agendaRuoloModel'
import '../features/agenda/ruolo/agendaRuolo.css'
const AgendaProceduralTools = lazy(() => import('./AgendaProceduralTools'))
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import { SourceDocumentModal } from './SourceDocumentModal'
import { OperationalModal } from './OperationalModal'
import type { AgendaEvent, AgendaKind, AgendaView } from '../agendaData'
import { formatDateIt } from '../formatting'
import { AGENDA_ACTIVITY_PREFIX, agendaActivityText, agendaDeadlineCalculatorHref, agendaProposedSteps, type AgendaProposedStep } from '../features/agenda/agendaDetailActions'
import { cleanAccessInfo, plausiblePasscode, readablePlatform } from '../features/scadenziario/deadlineDetailFacts'
import {
  addDays,
  addMonths,
  buildAgendaPageData,
  getAgendaPage,
  moveEventToDay,
  moveEventToDateTime,
  rangeLabel,
  startOfWeek,
  toDateKey,
} from '../agendaData'

const AgendaPreparation = lazy(() => import('./ControlloStudioAgendaDetail'))

const kindLabels: Record<AgendaKind, string> = {
  tutti: 'Tutti',
  udienza: 'Udienze',
  appuntamento: 'Appuntamenti',
  scadenza: 'Scadenze',
  deposito: 'Depositi',
  call: 'Call',
  studio: 'Studio',
}

const viewLabels: Record<AgendaView, string> = {
  day: 'Giorno',
  week: 'Settimana',
  month: 'Mese',
  timeline: 'Elenco',
}

function isSameText(event: AgendaEvent, query: string): boolean {
  if (!query.trim()) return true
  const haystack = [event.title, event.displayTitle, event.legalLabel, event.subtitle, event.client, event.court, event.matter, event.location, event.owner, ...event.detailLines].join(' ').toLowerCase()
  return haystack.includes(query.trim().toLowerCase())
}

function newAgendaHref(tipo: string, titolo = ''): string {
  const params = new URLSearchParams({ tipo, data: toDateKey(new Date()) })
  if (titolo) params.set('titolo', titolo)
  return `/agenda/nuovo?${params.toString()}`
}

function NewAgendaMenu() {
  return (
    <details className="iu-ag-new-menu">
      <summary><Plus size={16}/> Nuovo <ChevronDown size={15}/></summary>
      <nav aria-label="Nuova voce agenda">
        <a href={newAgendaHref('UDIENZA')}><Landmark size={16}/><span><strong>Udienza</strong><small>Comparizione o trattazione</small></span></a>
        <a href={newAgendaHref('CONSULTAZIONE')}><CalendarPlus size={16}/><span><strong>Appuntamento</strong><small>Cliente o assistito</small></span></a>
        <a href={newAgendaHref('DEPOSITO')}><BriefcaseBusiness size={16}/><span><strong>Adempimento</strong><small>Attività collegata alla pratica</small></span></a>
        <a href={newAgendaHref('ALTRO', 'Promemoria')}><Bell size={16}/><span><strong>Promemoria</strong><small>Nota operativa con avviso</small></span></a>
        <a href={newAgendaHref('ALTRO')}><UsersRound size={16}/><span><strong>Attività di studio</strong><small>Impegno interno</small></span></a>
        <a href="/scadenziario/nuova"><AlertTriangle size={16}/><span><strong>Scadenza</strong><small>Termine da presidiare</small></span></a>
      </nav>
    </details>
  )
}

function createAppointmentHref(dayIso: string, time = '09:00'): string {
  const params = new URLSearchParams({ data: dayIso, ora: time })
  return `/agenda/nuovo?${params.toString()}`
}

function messageReminderHref(event?: AgendaEvent): string {
  const params = new URLSearchParams()
  params.set('from', 'agenda')
  params.set('oggetto', event ? `Promemoria: ${agendaLegalLabel(event)} - ${agendaTitle(event)}` : 'Promemoria agenda')
  if (event?.clientId) params.set('id_cliente', event.clientId)
  if (event?.client) params.set('destinatario_nome', event.client)
  return `/messaggi/nuovo?${params.toString()}`
}

function linkedDeadlineHref(event?: AgendaEvent): string {
  const params = new URLSearchParams()
  if (event?.matterId) params.set('id_fascicolo', event.matterId)
  if (event?.title) params.set('titolo', `Scadenza collegata - ${agendaLegalLabel(event)} - ${agendaTitle(event)}`)
  if (event?.date) params.set('data', event.date)
  return `/scadenziario/nuova${params.toString() ? `?${params.toString()}` : ''}`
}

function routeAgendaId(): string {
  const match = window.location.pathname.match(/^\/agenda\/([^/]+)/)
  if (!match || ['nuovo', 'importa'].includes(match[1])) return ''
  return decodeURIComponent(match[1])
}

function initialAgendaDate(): Date {
  const params = new URLSearchParams(window.location.search)
  const raw = params.get('data') || params.get('date') || ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const parsed = new Date(`${raw}T12:00:00`)
    if (!Number.isNaN(parsed.getTime())) return parsed
  }
  return new Date()
}

function initialAgendaView(): AgendaView {
  const value = new URLSearchParams(window.location.search).get('vista')
  return value === 'day' || value === 'month' || value === 'week' || value === 'timeline' ? value : 'week'
}

function initialAgendaKind(): AgendaKind {
  const value = new URLSearchParams(window.location.search).get('tipo')
  return value && Object.prototype.hasOwnProperty.call(kindLabels, value) ? value as AgendaKind : 'tutti'
}

function initialAgendaQuery(): string {
  return new URLSearchParams(window.location.search).get('q') || ''
}

function localDateTimePayload(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:00`
}

function isWritableAgendaEvent(event: AgendaEvent): boolean {
  return event.source === 'agenda'
}

function agendaTitle(event: AgendaEvent): string {
  return event.displayTitle || event.title || event.legalLabel || 'Evento agenda'
}

function agendaLegalLabel(event: AgendaEvent): string {
  const label = event.legalLabel || (event.kind === 'udienza' ? 'Udienza' : event.kind === 'deposito' ? 'Deposito' : event.kind === 'scadenza' ? 'Scadenza da presidiare' : 'Adempimento')
  // Udienza superata da un rinvio comunicato via PEC: resta visibile ma dichiarata.
  const status = event.status.toUpperCase()
  if (status === 'BOZZA') return `${label} (proposta da confermare)`
  return status === 'RINVIATO' && !/rinviat|rinvio|modificat/i.test(label) ? `${label} (rinviata)` : label
}

function sameAgendaText(left: string, right: string): boolean {
  return left.trim().toLocaleLowerCase('it-IT') === right.trim().toLocaleLowerCase('it-IT')
}

function agendaHeadline(event: AgendaEvent): string {
  const label = agendaLegalLabel(event)
  const title = agendaTitle(event)
  return sameAgendaText(label, title) ? label : `${label} · ${title}`
}

function agendaSubjectLine(event: AgendaEvent): string {
  const contextParts = [event.client, event.matter]
    .map((value) => value.trim())
    .filter((value, index, values) => value && values.indexOf(value) === index)
  if (contextParts.length) return contextParts.join(' · ')
  const label = agendaLegalLabel(event).toLocaleLowerCase('it-IT')
  const title = agendaTitle(event)
  const titleKey = title.toLocaleLowerCase('it-IT')
  const parts = titleKey !== label ? [title] : []
  if (!parts.length) {
    const fallback = [event.subtitle, event.originTitle]
      .map((value) => value.trim())
      .find((value) => value && !sameAgendaText(value, agendaLegalLabel(event)) && !sameAgendaText(value, title))
    return fallback || 'Dettaglio da verificare'
  }
  return parts.join(' · ') || event.subtitle || event.originTitle || 'Dettaglio da verificare'
}

function agendaSourceLabel(source: string, event?: AgendaEvent): string {
  if (event?.sourceKind === 'pec' || event?.sourceHref?.includes('/email/')) return 'PEC'
  if (event?.sourceKind === 'documento' || event?.sourceHref?.includes('/documenti/')) return 'Documento'
  const normalized = source.toLowerCase()
  if (normalized.includes('scadenziario')) return 'Scadenziario'
  if (normalized.includes('pec')) return 'PEC'
  if (normalized.includes('agenda')) return 'Agenda interna'
  if (normalized.includes('calend')) return 'Calendario sincronizzato'
  return 'Registro operativo'
}

function AgendaDeleteAction({ event }:{event:AgendaEvent}) {
  const [confirming, setConfirming] = useState(false)
  if (!confirming) {
    return <button type="button" onClick={() => setConfirming(true)}><Trash2 size={15}/>Elimina</button>
  }
  return (
    <div className="iu-ag-delete-confirm" role="group" aria-label={`Elimina ${agendaHeadline(event)}`}>
      <span>Confermi l'eliminazione?</span>
      <JsonPostForm action={`/agenda/${encodeURIComponent(event.id)}/elimina`} redirectTo="/agenda" successMessage="Voce eliminata dall'agenda.">
        <button className="is-danger" type="submit"><Trash2 size={15}/>Elimina</button>
      </JsonPostForm>
      <button type="button" onClick={() => setConfirming(false)}>Annulla</button>
    </div>
  )
}

function AgendaSourceCard({ event, onOpenSource }:{event:AgendaEvent; onOpenSource:(event:AgendaEvent)=>void}) {
  const kindLabel = agendaSourceLabel(event.source, event)
  if (!event.sourceHref) {
    if (event.sourceCandidates?.length) return <SourceAlternatives candidates={event.sourceCandidates} onOpen={source => onOpenSource({ ...event, sourceHref: source.href, sourceLabel: source.label, sourceVerified: false, sourceCandidates: [] })}/>
    return (
      <div className="iu-ag-focus__source is-missing">
        <span><FileSearch size={14}/> Fonte</span>
        <strong>{kindLabel}</strong>
        <small>{event.sourceLabel === 'Più fonti PEC: collegamento da verificare' ? 'Fonti storiche non disponibili: collegamento da verificare.' : 'Nessun documento sorgente collegato a questo impegno.'}</small>
        {event.href ? <a href={event.href}>Apri origine</a> : null}
      </div>
    )
  }
  return (
    <div className="iu-ag-focus__source">
      <span><FileSearch size={14}/> Fonte</span>
      <button type="button" className="iu-ag-focus__source-link" onClick={() => onOpenSource(event)} title="Visualizza la fonte completa sopra il dettaglio">
        <strong>{event.sourceLabel || kindLabel}</strong>
        <small>{kindLabel}{event.sourceVerified ? ' · verificata' : ' · da verificare'}</small>
      </button>
      <div className="iu-ag-focus__source-actions">
        <button type="button" onClick={() => onOpenSource(event)}><FileSearch size={14}/>Visualizza fonte</button>
        {event.sourceVerified ? <em><ShieldCheck size={13}/> Fonte verificata</em> : null}
      </div>
    </div>
  )
}

function AgendaProposedActions({ event, steps, onOpenSource }:{event:AgendaEvent; steps:AgendaProposedStep[]; onOpenSource:(event:AgendaEvent)=>void}) {
  if (!steps.length) return null
  return (
    <section className="iu-ag-focus__proposed" aria-label="Attività proposte">
      <header>
        <strong><ListChecks size={15}/> Attività proposte</strong>
        <small>Esegui da qui quello che l’impegno richiede.</small>
      </header>
      <ol>
        {steps.map((step, index) => (
          <li key={step.id}>
            <span>{index + 1}</span>
            <p>{step.label}</p>
            {step.id === 'fonte' ? (
              <button type="button" onClick={() => onOpenSource(event)}><FileSearch size={14}/>{step.actionLabel}</button>
            ) : (
              <a href={step.href}>{step.id === 'atti' ? <FilePenLine size={14}/> : step.id === 'fascicolo' ? <BriefcaseBusiness size={14}/> : step.id === 'quando' ? <CalendarClock size={14}/> : step.id === 'termine' ? <CalendarCheck size={14}/> : <Bell size={14}/>}{step.actionLabel}</a>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}

function AzioniImpegno({ event, onPrepare }: { event: AgendaEvent; onPrepare: (event: AgendaEvent) => void }) {
  return (
    <div className="iu-ruolo-azioni" aria-label="Azioni sull'impegno">
      {event.kind === 'udienza' && event.matterId ? <button type="button" onClick={() => onPrepare(event)}>Prepara l’udienza</button> : null}
      <a href={messageReminderHref(event)}>Promemoria al cliente</a>
      {event.matterId ? (
        <JsonPostForm action="/timesheet/nuovo">
          <input type="hidden" name="from_page" value="fascicolo"/>
          <input type="hidden" name="focus" value="workflow"/>
          <input type="hidden" name="id_fascicolo" value={event.matterId}/>
          <input type="hidden" name="descrizione" value={`Attività agenda - ${agendaTitle(event)}`}/>
          <input type="hidden" name="data_attivita" value={event.date}/>
          <input type="hidden" name="minuti" value="30"/>
          <input type="hidden" name="valore_unitario" value="80"/>
          <input type="hidden" name="fatturabile" value="1"/>
          <input type="hidden" name="contesto" value="agenda-react"/>
          <button type="submit">Crea voce timesheet</button>
        </JsonPostForm>
      ) : (
        null
      )}
      <a href={linkedDeadlineHref(event)}>Genera scadenza collegata</a>
      <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex'))}>Brief Lex sul fascicolo</button>
    </div>
  )
}

export function AgendaFocus({
  event,
  onOpenSource,
  position,
  total,
  onNavigate,
  onPrepare,
}:{
  event:AgendaEvent
  onOpenSource:(event:AgendaEvent)=>void
  position?:number
  total?:number
  onNavigate?:(delta:-1|1)=>void
  onPrepare?:(event:AgendaEvent)=>void
}) {
  const isDeadline = event.source === 'scadenziario' || event.id.startsWith('scadenza-')
  const editHref = isDeadline ? event.href : `/agenda/${encodeURIComponent(event.id)}/modifica`
  const completeHref = isDeadline ? event.href : `/agenda/${encodeURIComponent(event.id)}/stato`
  const activity = agendaActivityText(event)
  const proposedSteps = agendaProposedSteps(event, activity, { editHref, isDeadline, clientReminderHref: messageReminderHref(event) })
  const visibleDetails = event.detailLines.map(line => line.replace(/\s*ARCHIVIO_FATTO:[\w-]+/g, '').replace(/Stato: PROGRAMMATO/g, 'Stato: Programmato').replace(/Stato: COMPLETATO/g, 'Stato: Completato').replace(/Stato: ANNULLATO/g, 'Stato: Annullato').replace(/Stato: RINVIATO/g, 'Stato: Rinviato').trim()).filter((line) => line.trim() && !AGENDA_ACTIVITY_PREFIX.test(line.trim())).slice(0, 12)
  const remotePlatform = readablePlatform(event.remoteHearingPlatform, Boolean(event.remoteHearingUrl))
  const remotePasscode = plausiblePasscode(event.remoteHearingPasscode)
  const remoteAccessInfo = cleanAccessInfo(event.remoteHearingAccessInfo)
  return (
    <section className="iu-ag-focus">
      <div>
        <a href="/agenda"><ArrowLeftIcon/>Torna all'agenda</a>
        {onNavigate && total && total > 1 ? (
          <nav className="iu-ag-focus__nav" aria-label="Scorri gli impegni del periodo">
            <button type="button" onClick={() => onNavigate(-1)} aria-label="Impegno precedente"><ChevronLeft size={15}/>Precedente</button>
            <em>{(position ?? 0) + 1} di {total}</em>
            <button type="button" onClick={() => onNavigate(1)} aria-label="Impegno successivo">Successivo<ChevronRight size={15}/></button>
          </nav>
        ) : null}
        <span>Dettaglio operativo</span>
        <h2>{agendaHeadline(event)}</h2>
        <p>{event.subtitle || event.notes || event.location || 'Verifica il fascicolo collegato prima dell’attività.'}</p>
        {activity ? <p className="iu-ag-focus__activity"><b>Attività per l’avvocato:</b> {activity}</p> : null}
        <AgendaProposedActions event={event} steps={proposedSteps} onOpenSource={onOpenSource}/>
        {visibleDetails.length ? (
          <ul className="iu-ag-focus__details">
            {visibleDetails.map((line) => <li key={line}>{line}</li>)}
          </ul>
        ) : null}
      </div>
      <div className="iu-ag-focus__side">
      <AgendaSourceCard event={event} onOpenSource={onOpenSource}/>
      <dl>
        <div><dt>Data</dt><dd>{formatDateIt(event.start)}</dd></div>
        <div><dt>Orario</dt><dd>{event.timeLabel} · {event.durationLabel}</dd></div>
        <div><dt>Cliente/parte</dt><dd>{event.client || 'Da collegare'}</dd></div>
        <div><dt>Fascicolo/RG</dt><dd>{event.matter || 'Da indicare'}</dd></div>
        <div><dt>Origine</dt><dd>{agendaSourceLabel(event.source, event)}</dd></div>
        {remotePlatform ? <div><dt>Piattaforma</dt><dd>{remotePlatform}</dd></div> : null}
        {event.remoteHearingMeetingId ? <div><dt>ID riunione</dt><dd>{event.remoteHearingMeetingId}</dd></div> : null}
        {remotePasscode ? <div><dt>Codice di accesso</dt><dd>{remotePasscode}</dd></div> : null}
        {remoteAccessInfo ? <div><dt>Istruzioni</dt><dd>{remoteAccessInfo}</dd></div> : null}
      </dl>
      <Suspense fallback={<p role="status">Caricamento del supporto operativo…</p>}>
        <AgendaProceduralTools key={event.id} fascicoloId={event.matterId || ''} fascicoloTitle={event.matter || ''}/>
      </Suspense>
      </div>
      <div className="iu-ag-focus__actions">
        {onPrepare && event.kind === 'udienza' ? <button type="button" onClick={() => onPrepare(event)}><BriefcaseBusiness size={15}/>Prepara l’udienza</button> : null}
        {event.remoteHearingVerified && event.remoteHearingUrl ? <a href={event.remoteHearingUrl} target="_blank" rel="noreferrer"><Video size={15}/>Collegati all'udienza</a> : null}
        {event.matterId ? <a href={`/fascicoli/${encodeURIComponent(event.matterId)}`}><BriefcaseBusiness size={15}/>Apri fascicolo</a> : null}
        <a href={editHref}><Settings2 size={15}/>Modifica</a>
        {!isDeadline ? <a href={`${editHref}#quando`}><CalendarClock size={15}/>Rinvia</a> : null}
        {event.sourceHref ? (
          <button type="button" onClick={() => onOpenSource(event)} title={`Apri origine: ${event.sourceLabel || 'fonte originaria'}`}><FileSearch size={15}/>Apri origine</button>
        ) : (
          <a href={event.href || '/agenda'}><CalendarDays size={15}/>Apri origine</a>
        )}
        <a href={`/messaggi/nuovo?oggetto=${encodeURIComponent(agendaHeadline(event))}`}><MessageCircleIcon/>Avvisa cliente</a>
        {event.matterId ? <a href={`/notifiche-legali?id_fascicolo=${encodeURIComponent(event.matterId)}&fase=notifica`}><Bell size={15}/>Prepara notifica</a> : null}
        <a href={agendaDeadlineCalculatorHref(event)}><CalendarCheck size={15}/>Calcola termine</a>
        <a href="#lex" data-lex-open data-lex-context="agenda" data-lex-label={`Contesto agenda: ${agendaHeadline(event)}`}><Sparkles size={15}/>Chiedi a Lex</a>
        {!isDeadline && event.completed ? (
          <span className="iu-ag-focus__completed" role="status"><CheckCircle2 size={15}/>Attività completata</span>
        ) : !isDeadline ? (
          <JsonPostForm action={completeHref}>
            <input type="hidden" name="stato" value="COMPLETATO"/>
            <button type="submit"><CheckCircle2 size={15}/>Segna completato</button>
          </JsonPostForm>
        ) : null}
        {!isDeadline ? <AgendaDeleteAction event={event}/> : null}
      </div>
    </section>
  )
}

function ArrowLeftIcon() {
  return <ChevronLeft size={15}/>
}

function MessageCircleIcon() {
  return <Bell size={15}/>
}

export function AgendaPage() {
  const plannerRef = useRef<HTMLElement>(null)
  const calendarGridRef = useRef<HTMLDivElement>(null)
  const calendarHeadsRef = useRef<HTMLDivElement>(null)
  const calendarHeadTrackRef = useRef<HTMLDivElement>(null)
  const [anchorDate, setAnchorDate] = useState(initialAgendaDate)
  const [view, setView] = useState<AgendaView>(initialAgendaView)
  const [kind, setKind] = useState<AgendaKind>(initialAgendaKind)
  const [query, setQuery] = useState(initialAgendaQuery)
  const [filters, setFilters] = useState<AgendaFilters>(emptyAgendaFilters)
  const [quickFilter, setQuickFilter] = useState('periodo')
  const [filtro, setFiltro] = useState<FiltroRapido>('tutti')
  const [filtriAvanzati, setFiltriAvanzati] = useState(false)
  const [groupPreview, setGroupPreview] = useState<AgendaEvent[]>([])
  const [prepareEvent, setPrepareEvent] = useState<AgendaEvent | null>(null)
  const [loading, setLoading] = useState(true)
  const [foregroundLoading, setForegroundLoading] = useState(true)
  useBusyActivity(foregroundLoading, 'Caricamento dell’agenda…')
  const [events, setEvents] = useState<AgendaEvent[]>([])
  const [dataDiagnostic, setDataDiagnostic] = useState('')
  const [dataSource, setDataSource] = useState('iniziale')
  const [moveStatus, setMoveStatus] = useState('')
  const loadingRequest = useRef(0)
  const movingEvents = useRef(new Set<string>())
  const [plannerExpanded, setPlannerExpanded] = useState(false)
  const [sourcePreview, setSourcePreview] = useState<AgendaEvent | null>(null)
  const [detailPreview, setDetailPreview] = useState<AgendaEvent | null>(null)
  const selectedId = routeAgendaId()

  useEffect(() => {
    const syncFullscreenState = () => setPlannerExpanded(document.fullscreenElement === plannerRef.current)
    document.addEventListener('fullscreenchange', syncFullscreenState)
    return () => document.removeEventListener('fullscreenchange', syncFullscreenState)
  }, [])

  useEffect(() => {
    document.body.classList.toggle('iu-agenda-planner-expanded', plannerExpanded)
    return () => document.body.classList.remove('iu-agenda-planner-expanded')
  }, [plannerExpanded])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    params.set('vista', view)
    params.set('data', toDateKey(anchorDate))
    if (kind === 'tutti') params.delete('tipo')
    else params.set('tipo', kind)
    if (query.trim()) params.set('q', query.trim())
    else params.delete('q')
    const search = params.toString()
    const nextHref = `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`
    const currentHref = `${window.location.pathname}${window.location.search}${window.location.hash}`
    if (nextHref !== currentHref) window.history.replaceState(window.history.state, '', nextHref)
  }, [anchorDate, view, kind, query])

  const refresh = (silent = false) => {
    const request = ++loadingRequest.current
    setForegroundLoading(!silent)
    setLoading(true)
    return getAgendaPage(anchorDate, view).then((payload) => {
      if (request !== loadingRequest.current) return
      if (payload.source !== 'errore_controllato') setEvents(payload.events)
      setDataDiagnostic(payload.diagnostic)
      setDataSource(payload.source)
    }).finally(() => { if (request === loadingRequest.current) { setLoading(false); setForegroundLoading(false) } })
  }

  useEffect(() => {
    void refresh()
    return () => { loadingRequest.current += 1 }
  }, [anchorDate, view])

  useOperationalRefresh(['agenda', 'scadenze', 'fascicoli'], () => refresh(true))
  const researchedEvents = useMemo(() => events.filter((event) =>
    isSameText(event, query) && matchesAgendaFilters(event, filters)), [events, query, filters])
  const filteredEvents = useMemo(() => researchedEvents.filter((event) => {
    if (kind !== 'tutti' && event.kind !== kind) return false
    if (quickFilter === 'oggi') return event.date === toDateKey(new Date())
    if (quickFilter === 'udienze') return event.kind === 'udienza'
    if (quickFilter === 'scadenze') return event.kind === 'scadenza' || event.kind === 'deposito'
    if (quickFilter === 'alert') return event.priority === 'alta' || event.priority === 'critica'
    return corrispondeFiltro(event, filtro)
  }), [researchedEvents, kind, quickFilter, filtro])
  const agenda = useMemo(() => buildAgendaPageData(filteredEvents, anchorDate, 'client', view), [filteredEvents, anchorDate, view])
  const highlightEvents = useMemo(
    () => [...filteredEvents].sort((left, right) => new Date(left.start).getTime() - new Date(right.start).getTime()),
    [filteredEvents],
  )
  const selectedEvent = selectedId ? events.find((event) => event.id === selectedId || event.id === `scadenza-${selectedId}`) : undefined

  useEffect(() => {
    if (selectedEvent) setDetailPreview(selectedEvent)
  }, [selectedEvent])

  useEffect(() => {
    const syncDetailFromRoute = () => {
      const routeId = routeAgendaId()
      if (!routeId) {
        setDetailPreview(null)
        return
      }
      setDetailPreview(events.find((event) => event.id === routeId || event.id === `scadenza-${routeId}`) || null)
    }
    window.addEventListener('popstate', syncDetailFromRoute)
    return () => window.removeEventListener('popstate', syncDetailFromRoute)
  }, [events])

  const openAgendaDetail = (event: AgendaEvent) => {
    window.history.pushState(window.history.state, '', `/agenda/${encodeURIComponent(event.id)}${window.location.search}`)
    setDetailPreview(event)
  }


  const weekStart = startOfWeek(anchorDate)
  const weekEnd = addDays(weekStart, 6)
  const today = new Date()
  const displayDays = agenda.days
  useEffect(() => {
    const grid = calendarGridRef.current
    const track = calendarHeadTrackRef.current
    if (!grid || !track || view === 'month' || view === 'timeline') return
    const align = () => { track.style.width = `${grid.scrollWidth}px`; if (calendarHeadsRef.current) calendarHeadsRef.current.scrollLeft = grid.scrollLeft }
    const observer = new ResizeObserver(align)
    observer.observe(grid)
    align()
    return () => observer.disconnect()
  }, [view, displayDays.length, plannerExpanded])
  const agendaUnavailable = dataSource === 'errore_controllato' || dataSource === 'parziale'
  const sourceLabel = loading ? 'Aggiornamento agenda…' : dataSource === 'errore_controllato'
    ? 'Agenda non aggiornata. Riprova tra poco.' : dataSource === 'parziale'
      ? 'Alcune attività non sono disponibili. Riprova.' : 'Dati agenda aggiornati'
  const dateLabel = view === 'day'
    ? anchorDate.toLocaleDateString('it-IT')
    : view === 'month' || view === 'timeline'
      ? anchorDate.toLocaleDateString('it-IT', { timeZone: 'Europe/Rome', month: 'long', year: 'numeric' })
      : rangeLabel(weekStart, weekEnd)

  const shiftPeriod = (direction: -1 | 1) => {
    setAnchorDate((current) => view === 'month' || view === 'timeline'
      ? addMonths(current, direction)
      : addDays(current, view === 'day' ? direction : direction * 7))
  }


  const openNewAppointment = (dayIso: string, time: string) => {
    window.location.href = createAppointmentHref(dayIso, time)
  }

  const persistMove = async (event: AgendaEvent) => {
    if (!isWritableAgendaEvent(event)) {
      setMoveStatus('Questa attività si modifica dalla sua fonte. La data in agenda è invariata.')
      return
    }
    if (movingEvents.current.has(event.id)) return
    movingEvents.current.add(event.id)
    setMoveStatus('Salvataggio dello spostamento…')
    const endpoint = `/api/agenda/${encodeURIComponent(event.id)}/sposta`
    const finish = beginActivity('Salvataggio dello spostamento…')
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ data_ora: localDateTimePayload(event.start) }),
      })
      const result: unknown = await response.json()
      if (!response.ok || !result || typeof result !== 'object' || Array.isArray(result)
        || (result as Record<string, unknown>).ok !== true) throw new Error('Spostamento non confermato')
      setMoveStatus('Spostamento salvato. L’agenda si aggiorna automaticamente.')
      publishMutationRefresh(endpoint)
    } catch {
      setMoveStatus('Salvataggio non confermato. Verifica la data nell’agenda aggiornata e riprova.')
      void refresh()
    } finally {
      movingEvents.current.delete(event.id)
      finish()
    }
  }

  const moveEvent = (eventId: string, dayIso: string, time?: string) => {
    const sourceEvent = events.find((event) => event.id === eventId)
    if (!sourceEvent) return
    const movedEvent = time ? moveEventToDateTime(sourceEvent, dayIso, time) : moveEventToDay(sourceEvent, dayIso)
    void persistMove(movedEvent)
  }

  const openPreparation = (event: AgendaEvent) => {
    if (window.parent !== window && new URLSearchParams(window.location.search).get('embed') === 'source') {
      window.dispatchEvent(new CustomEvent('iusentra:open-work-window', { detail: {
        href: `/wizard-pro/?id_appuntamento=${encodeURIComponent(event.id)}&id_fascicolo=${encodeURIComponent(event.matterId)}`,
        title: `Preparazione udienza · ${agendaSubjectLine(event)}`,
      } }))
    } else setPrepareEvent(event)
  }

  const contextualPanels = <>
      {prepareEvent ? <Suspense fallback={<div role="status">Apertura preparazione…</div>}><AgendaPreparation
        voce={{ id: `agenda-${prepareEvent.id}`, area: 'agenda', area_etichetta: 'Agenda', titolo: prepareEvent.title, dettaglio: '', data: prepareEvent.date, ora: prepareEvent.timeLabel,
          gravita: 'normale', etichetta: '', fascicolo: { id: prepareEvent.matterId }, data_riferimento: '', tipo_data_riferimento: '', importo: 0, azioni: [], fascia: '' }}
        azione={{ etichetta: 'Prepara l’udienza', href: `/wizard-pro/?id_appuntamento=${encodeURIComponent(prepareEvent.id)}&id_fascicolo=${encodeURIComponent(prepareEvent.matterId)}`, endpoint: '', conferma: '', principale: true }}
        onClose={() => setPrepareEvent(null)} onUpdated={refresh}/></Suspense> : null}
      <SourceDocumentModal
        source={sourcePreview ? {
          href: sourcePreview.sourceHref,
          label: sourcePreview.sourceLabel || agendaTitle(sourcePreview),
          context: `${agendaHeadline(sourcePreview)} · ${agendaSubjectLine(sourcePreview)}`,
          kind: sourcePreview.sourceKind,
        } : null}
        onClose={() => setSourcePreview(null)}
      />
  </>

  if (new URLSearchParams(window.location.search).get('embed') === 'source' && selectedId) {
    return <main className="iu-agenda-context-detail" aria-label="Dettaglio operativo agenda">
      {loading ? <p role="status">Caricamento dell’impegno selezionato…</p> : selectedEvent ? <AgendaFocus event={selectedEvent} onOpenSource={setSourcePreview} onPrepare={openPreparation} /> : <section role="alert"><p>L’impegno selezionato non è disponibile in questo momento.</p><button type="button" className="iu-button" onClick={() => { void refresh() }}>Riprova</button></section>}
      {contextualPanels}
    </main>
  }

  const filtriRapidi: Array<[FiltroRapido, string]> = [['lavoro', 'Da lavorare'], ['udienza', 'Udienze'], ['termine', 'Termini'], ['notifica', 'Notifiche'], ['cancelleria', 'Comunicazioni']]
  const contaFiltro = (valore: FiltroRapido) => researchedEvents.filter((event) => corrispondeFiltro(event, valore)).length
  const schedaEvent = detailPreview || highlightEvents.find(daLavorare) || agenda.summary.nextEvent || highlightEvents[0] || null
  const apriGiorno = (iso: string) => { setAnchorDate(new Date(`${iso.slice(0, 10)}T12:00:00`)); setView('day') }

  return (
    <main className="iu-content iu-agenda-page iu-ruolo-pagina">
      <section className="iu-ruolo-comandi" aria-label="Periodo e vista"
        data-agenda-diagnostic={dataDiagnostic} data-agenda-filtered-count={filteredEvents.length}
        data-agenda-loaded-count={events.length} data-agenda-source={dataSource}>
        <h1>Agenda</h1>
        <div className="iu-ruolo-periodo">
          <button type="button" onClick={() => shiftPeriod(-1)} aria-label="Periodo precedente"><ChevronLeft size={16}/></button>
          <button type="button" onClick={() => setAnchorDate(today)}>Oggi</button>
          <button type="button" onClick={() => shiftPeriod(1)} aria-label="Periodo successivo"><ChevronRight size={16}/></button>
          <strong>{dateLabel}</strong>
        </div>
        <div className="iu-ruolo-viste" role="group" aria-label="Vista">
          {(Object.keys(viewLabels) as AgendaView[]).map((item) => (
            <button type="button" key={item} aria-pressed={view === item} onClick={() => setView(item)}>{viewLabels[item]}</button>
          ))}
        </div>
        <label className="iu-ruolo-cerca">
          <Search size={16}/>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca cliente, fascicolo, RG" aria-label="Cerca in agenda"/>
        </label>
        <div className="iu-ruolo-altro">
          <button className="iu-ruolo-icona" type="button" onClick={() => setFiltriAvanzati((v) => !v)} aria-pressed={filtriAvanzati} aria-label="Filtri avanzati" title="Filtri avanzati"><Filter size={16}/></button>
          <button className="iu-ruolo-icona" type="button" onClick={() => { void refresh() }} aria-label="Aggiorna agenda" title="Aggiorna agenda"><RefreshCw size={16}/></button>
          <details className="iu-ruolo-menu">
            <summary className="iu-ruolo-icona" aria-label="Altre funzioni dell'agenda">Altro</summary>
            <div className="iu-ruolo-menu__voci">
              <a href="/polisWeb"><Landmark size={15}/> Aggiorna dagli uffici giudiziari</a>
              <a href="/impostazioni/calendario"><CalendarSync size={15}/> Calendari collegati</a>
              <button type="button" onClick={() => window.print()}><Printer size={15}/> Stampa l’agenda</button>
              <a href="/agenda/export.ics"><Download size={15}/> Scarica il calendario</a>
              <a href="/agenda/importa"><UploadCloud size={15}/> Importa un calendario</a>
            </div>
          </details>
          <NewAgendaMenu/>
        </div>
      </section>

      <section className="iu-ruolo-filtri" aria-label="Filtri rapidi">
        {filtriRapidi.map(([valore, nome]) => (
          <button type="button" key={valore} className={`iu-ruolo-filtro ${valore === 'lavoro' ? 'iu-ruolo-filtro--lavoro' : ''}`}
            aria-pressed={filtro === valore} onClick={() => { setFiltro((attuale) => attuale === valore ? 'tutti' : valore); setQuickFilter('periodo'); setKind('tutti') }}>
            <i className={`iu-ruolo-c-${valore === 'lavoro' ? 'oro' : valore}`}/>{nome} <em>{contaFiltro(valore)}</em>
          </button>
        ))}
        <span className={`iu-ruolo-stato ${agendaUnavailable ? 'is-errore' : ''}`} role={agendaUnavailable ? 'alert' : 'status'}>
          {sourceLabel}{agenda.summary.unsynced ? ` · ${agenda.summary.unsynced} da sincronizzare` : ''}{moveStatus ? ` · ${moveStatus}` : ''}
        </span>
        {agendaUnavailable ? <button type="button" className="iu-ruolo-icona" onClick={() => void refresh()} disabled={loading}>Riprova</button> : null}
      </section>

      {filtriAvanzati ? <AgendaResearchFilters events={events} value={filters} onChange={setFilters} count={filteredEvents.length}
        onReset={() => { setFilters(emptyAgendaFilters); setQuery(''); setKind('tutti'); setQuickFilter('periodo'); setFiltro('tutti') }}/> : null}

      <section className="iu-ruolo-corpo">
        <div className="iu-ruolo-vista" aria-label={`Vista ${viewLabels[view].toLowerCase()}`}>
          <AgendaRuolo view={view} days={displayDays} selectedId={schedaEvent?.id || ''} onOpen={openAgendaDetail} onOpenDay={apriGiorno}
            onCreateSlot={openNewAppointment} onDropEvent={moveEvent}/>
        </div>
        <AgendaScheda event={schedaEvent} onChanged={() => { void refresh(true) }} onOpenSource={setSourcePreview}
          azioni={schedaEvent ? <AzioniImpegno event={schedaEvent} onPrepare={openPreparation}/> : null}/>
      </section>

      <FloatingLex />
      <OperationalModal open={Boolean(groupPreview.length)} ariaLabel="Attività coincidenti" eyebrow="Agenda" title={`${groupPreview.length} attività da affrontare`}
        subtitle={groupPreview[0] ? formatDateIt(groupPreview[0].start) : ''} onClose={() => setGroupPreview([])}>
        <div className="iu-ag-case-list">{groupPreview.map((event) => <button type="button" key={event.id} onClick={() => openAgendaDetail(event)}>
          <time>{event.timeLabel}</time><span><strong>{agendaLegalLabel(event)}</strong><small>{agendaSubjectLine(event)}</small><small>{event.court || event.location}</small></span><ChevronRight size={18}/>
        </button>)}</div>
      </OperationalModal>
      {contextualPanels}
    </main>
  )
}
