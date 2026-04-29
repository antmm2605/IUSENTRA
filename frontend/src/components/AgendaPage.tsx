import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Bell,
  BriefcaseBusiness,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CalendarSync,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  Filter,
  Landmark,
  ListChecks,
  MapPin,
  Move,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  UploadCloud,
  UsersRound,
  Video,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import type { AgendaEvent, AgendaKind, AgendaView } from '../agendaData'
import {
  addDays,
  buildAgendaPageData,
  eventHeightPixels,
  eventTopPercent,
  getAgendaPage,
  moveEventToDay,
  rangeLabel,
  startOfWeek,
  toDateKey,
} from '../agendaData'

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
  week: 'Sett.',
  month: 'Mese',
}

const timelineHours = Array.from({ length: 12 }, (_, index) => `${String(index + 8).padStart(2, '0')}:00`)

function isSameText(event: AgendaEvent, query: string): boolean {
  if (!query.trim()) return true
  const haystack = [event.title, event.subtitle, event.client, event.court, event.matter, event.location, event.owner].join(' ').toLowerCase()
  return haystack.includes(query.trim().toLowerCase())
}

function eventIcon(kind: AgendaEvent['kind']) {
  if (kind === 'udienza') return <Landmark size={14}/>
  if (kind === 'deposito' || kind === 'scadenza') return <AlertTriangle size={14}/>
  if (kind === 'call') return <Video size={14}/>
  if (kind === 'studio') return <UsersRound size={14}/>
  return <CalendarDays size={14}/>
}

function Kpi({ icon, label, value, note }:{icon:ReactNode; label:string; value:string|number; note:string}) {
  return (
    <article className="iu-ag-kpi">
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function EventCard({ event }:{event:AgendaEvent}) {
  return (
    <a
      className={`iu-ag-event iu-ag-event--${event.tone}`}
      draggable
      href={event.href || '/agenda'}
      onDragStart={(dragEvent) => dragEvent.dataTransfer.setData('text/plain', event.id)}
      style={{ top: `${eventTopPercent(event)}%`, minHeight: eventHeightPixels(event) }}
    >
      <span className="iu-ag-event__time">{event.timeLabel}</span>
      <strong>{eventIcon(event.kind)} {event.title}</strong>
      <small>{event.subtitle || event.client || event.location}</small>
      <em>{event.durationLabel}</em>
    </a>
  )
}

function DayColumn({ day, onDropEvent }:{day:ReturnType<typeof buildAgendaPageData>['days'][number]; onDropEvent:(eventId:string, dayIso:string)=>void}) {
  return (
    <section
      className={`iu-ag-day ${day.isToday ? 'is-today' : ''} ${day.isWeekend ? 'is-weekend' : ''}`}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        const eventId = event.dataTransfer.getData('text/plain')
        if (eventId) onDropEvent(eventId, day.iso)
      }}
    >
      <header>
        <span>{day.weekday}</span>
        <strong>{day.label}</strong>
        <small>{day.month}</small>
      </header>
      <div className="iu-ag-day__body">
        {timelineHours.map((hour) => <i key={hour}><span>{hour}</span></i>)}
        {day.events.map((event) => <EventCard event={event} key={event.id}/>)}
        {!day.events.length ? <div className="iu-ag-drop"><Move size={15}/> Spazio disponibile</div> : null}
      </div>
    </section>
  )
}

function AgendaInspector({ events, nextEvent, unsynced }:{events:AgendaEvent[]; nextEvent?:AgendaEvent; unsynced:number}) {
  const critical = events.filter((event) => event.priority === 'critica' || event.priority === 'alta').slice(0, 4)
  return (
    <aside className="iu-ag-inspector">
      <Panel title="Briefing agenda" subtitle="Priorita operative e prossime mosse" icon={<Sparkles size={17}/>}>
        <div className="iu-ag-brief">
          {nextEvent ? (
            <article>
              <span>Prossimo impegno</span>
              <strong>{nextEvent.timeLabel} - {nextEvent.title}</strong>
              <small>{nextEvent.subtitle || nextEvent.location}</small>
            </article>
          ) : <p className="iu-empty">Nessun impegno imminente.</p>}
          <div className="iu-ag-quick-actions">
            <Button variant="primary" href="/agenda/nuovo"><CalendarPlus size={15}/> Nuovo</Button>
            <Button href="/impostazioni/calendario"><CalendarSync size={15}/> Calendari</Button>
          </div>
        </div>
      </Panel>

      <Panel title="Priorita da non perdere" icon={<AlertTriangle size={17}/>} count={critical.length}>
        {critical.length ? (
          <div className="iu-ag-priority-list">
            {critical.map((event) => (
              <a href={event.href || '/agenda'} key={event.id}>
                <Badge tone={event.tone}>{event.kind}</Badge>
                <strong>{event.title}</strong>
                <span>{event.date} - {event.timeLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna urgenza nel periodo visibile.</p>}
      </Panel>

      <Panel title="Salute sincronizzazione" icon={<CalendarSync size={17}/>} count={unsynced}>
        <div className="iu-ag-sync-health">
          <strong>{unsynced ? `${unsynced} elementi da riallineare` : 'Calendari allineati'}</strong>
          <span>iCal, SINC e calendari esterni restano sotto controllo senza nascondere gli eventi locali.</span>
          <a href="/impostazioni/calendario">Configura calendari -&gt;</a>
        </div>
      </Panel>
    </aside>
  )
}

export function AgendaPage() {
  const [anchorDate, setAnchorDate] = useState(() => new Date())
  const [view, setView] = useState<AgendaView>('week')
  const [kind, setKind] = useState<AgendaKind>('tutti')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<AgendaEvent[]>([])

  const refresh = () => {
    setLoading(true)
    getAgendaPage(anchorDate).then((payload) => {
      setEvents(payload.events)
    }).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getAgendaPage(anchorDate).then((payload) => {
      if (active) setEvents(payload.events)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [anchorDate])

  const filteredEvents = useMemo(() => events.filter((event) => {
    const kindOk = kind === 'tutti' || event.kind === kind
    return kindOk && isSameText(event, query)
  }), [events, kind, query])

  const agenda = useMemo(() => buildAgendaPageData(filteredEvents, anchorDate), [filteredEvents, anchorDate])
  const weekStart = startOfWeek(anchorDate)
  const weekEnd = addDays(weekStart, 6)
  const today = new Date()
  const displayDays = view === 'day'
    ? agenda.days.filter((day) => day.iso === toDateKey(anchorDate))
    : agenda.days
  const sourceLabel = loading ? 'Sincronizzazione agenda...' : 'Dati agenda aggiornati'

  const moveEvent = (eventId: string, dayIso: string) => {
    setEvents((current) => current.map((event) => event.id === eventId ? moveEventToDay(event, dayIso) : event))
  }

  return (
    <main className="iu-content iu-agenda-page">
      <section className="iu-ag-hero">
        <div>
          <span className="iu-ag-eyebrow"><CalendarDays size={16}/> Agenda</span>
          <h1>Agenda</h1>
          <p>Appuntamenti, udienze, scadenze, sincronizzazioni e priorita dello studio in una vista unica.</p>
        </div>
        <div className="iu-ag-hero__actions">
          <Button href="/workspace-intelligente"><Sparkles size={15}/> Cabina</Button>
          <Button href="/impostazioni/calendario"><CalendarSync size={15}/> Calendari</Button>
          <Button variant="primary" href="/agenda/nuovo"><Plus size={16}/> Nuovo appuntamento</Button>
        </div>
      </section>

      <section className="iu-ag-toolbar" aria-label="Comandi agenda">
        <div className="iu-ag-view-switch" role="group" aria-label="Vista calendario">
          {(Object.keys(viewLabels) as AgendaView[]).map((item) => (
            <button className={view === item ? 'is-active' : ''} type="button" onClick={() => setView(item)} key={item}>{viewLabels[item]}</button>
          ))}
        </div>
        <div className="iu-ag-date-nav">
          <button type="button" onClick={() => setAnchorDate(addDays(anchorDate, view === 'day' ? -1 : -7))} aria-label="Periodo precedente"><ChevronLeft size={16}/></button>
          <button type="button" onClick={() => setAnchorDate(today)}>Oggi</button>
          <button type="button" onClick={() => setAnchorDate(addDays(anchorDate, view === 'day' ? 1 : 7))} aria-label="Periodo successivo"><ChevronRight size={16}/></button>
          <strong>{view === 'day' ? anchorDate.toLocaleDateString('it-IT') : rangeLabel(weekStart, weekEnd)}</strong>
        </div>
        <label className="iu-ag-search">
          <Search size={17}/>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca in agenda..."/>
        </label>
        <label className="iu-ag-filter">
          <Filter size={16}/>
          <select value={kind} onChange={(event) => setKind(event.target.value as AgendaKind)}>
            {(Object.keys(kindLabels) as AgendaKind[]).map((item) => <option value={item} key={item}>{kindLabels[item]}</option>)}
          </select>
        </label>
        <button className="iu-ag-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna agenda"><RefreshCw size={17}/></button>
        <a className="iu-ag-icon-btn" href="/agenda/export.ics" aria-label="Scarica calendario"><Download size={17}/></a>
        <a className="iu-ag-icon-btn" href="/agenda/importa" aria-label="Importa calendario"><UploadCloud size={17}/></a>
      </section>

      <section className="iu-ag-status-line">
        <span className={loading ? '' : 'is-ok'}>{sourceLabel}</span>
        <small><Move size={14}/> Trascina nella vista per preparare uno spostamento provvisorio.</small>
      </section>

      <section className="iu-ag-kpis">
        <Kpi icon={<Clock3 size={19}/>} label="Oggi" value={agenda.summary.today} note="impegni in giornata"/>
        <Kpi icon={<CalendarCheck size={19}/>} label="Settimana" value={agenda.summary.week} note="eventi nel periodo"/>
        <Kpi icon={<Landmark size={19}/>} label="Udienze" value={agenda.summary.hearings} note="da presidiare"/>
        <Kpi icon={<ListChecks size={19}/>} label="Scadenze" value={agenda.summary.deadlines} note="termini e depositi"/>
        <Kpi icon={<Bell size={19}/>} label="Alert" value={agenda.summary.critical} note="priorita alta o critica"/>
      </section>

      <section className="iu-ag-layout">
        <div className="iu-ag-calendar-card">
          <header>
            <div>
              <strong>{view === 'day' ? 'Vista giorno' : view === 'month' ? 'Vista mese compatta' : 'Vista settimana'}</strong>
              <span>{displayDays.length} giorni visibili - {filteredEvents.length} elementi</span>
            </div>
            <div>
              <Badge tone={agenda.summary.unsynced ? 'warning' : 'success'}>{agenda.summary.unsynced ? `${agenda.summary.unsynced} da sincronizzare` : 'allineata'}</Badge>
              <a href="/impostazioni/calendario"><Settings2 size={16}/> Preferenze</a>
            </div>
          </header>
          <div className="iu-ag-week" style={{ gridTemplateColumns: `repeat(${displayDays.length}, minmax(188px, 1fr))` }}>
            {displayDays.map((day) => <DayColumn day={day} key={day.id} onDropEvent={moveEvent}/>)}
          </div>
        </div>
        <AgendaInspector events={filteredEvents} nextEvent={agenda.summary.nextEvent} unsynced={agenda.summary.unsynced}/>
      </section>

      <section className="iu-ag-lower-grid">
        <Panel title="Preparazione udienza guidata" subtitle="Controlli prima dell'impegno" icon={<BriefcaseBusiness size={17}/>}>
          <div className="iu-ag-checks">
            <span><CalendarCheck size={16}/> Verifica orario, aula e collegamento fascicolo</span>
            <span><MapPin size={16}/> Conferma luogo o collegamento da remoto</span>
            <span><ListChecks size={16}/> Allinea scadenze, note e documenti da portare</span>
          </div>
        </Panel>
        <Panel title="Automazioni consigliate" subtitle="Azioni utili per l'agenda professionale" icon={<Sparkles size={17}/>}>
          <div className="iu-ag-automations">
            <a href="/messaggi/nuovo">Promemoria cliente</a>
            <a href="/timesheet">Crea voce timesheet</a>
            <a href="/scadenziario/nuova">Genera scadenza collegata</a>
            <a href="/lex?context=agenda">Brief Lex sul fascicolo</a>
          </div>
        </Panel>
      </section>

      <FloatingLex />
    </main>
  )
}
