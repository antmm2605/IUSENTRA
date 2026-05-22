import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Bell,
  BriefcaseBusiness,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CalendarSync,
  CheckCircle2,
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
import { JsonPostForm } from './JsonPostForm'
import type { AgendaEvent, AgendaKind, AgendaView } from '../agendaData'
import {
  addDays,
  addMonths,
  agendaRange,
  buildAgendaPageData,
  eventHeightPixels,
  eventTopPercent,
  getAgendaPage,
  moveEventToDay,
  moveEventToDateTime,
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

const timelineSlots = Array.from({ length: 24 }, (_, index) => {
  const minutes = 8 * 60 + index * 30
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
})

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

function createAppointmentHref(dayIso: string, time = '09:00'): string {
  const params = new URLSearchParams({ data: dayIso, ora: time })
  return `/agenda/nuovo?${params.toString()}`
}

function messageReminderHref(event?: AgendaEvent): string {
  const params = new URLSearchParams()
  params.set('from', 'agenda')
  params.set('oggetto', event ? `Promemoria: ${event.title}` : 'Promemoria agenda')
  if (event?.clientId) params.set('id_cliente', event.clientId)
  if (event?.client) params.set('destinatario_nome', event.client)
  return `/messaggi/nuovo?${params.toString()}`
}

function linkedDeadlineHref(event?: AgendaEvent): string {
  const params = new URLSearchParams()
  if (event?.matterId) params.set('id_fascicolo', event.matterId)
  if (event?.title) params.set('titolo', `Scadenza collegata - ${event.title}`)
  if (event?.date) params.set('data', event.date)
  return `/scadenziario/nuova${params.toString() ? `?${params.toString()}` : ''}`
}

function routeAgendaId(): string {
  const match = window.location.pathname.match(/^\/agenda\/([^/]+)/)
  if (!match || ['nuovo', 'importa'].includes(match[1])) return ''
  return decodeURIComponent(match[1])
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

function EventCard({ event }:{event:AgendaEvent}) {
  return (
    <a
      className={`iu-ag-event iu-ag-event--${event.tone}`}
      draggable
      href={event.href || '/agenda'}
      onDragStart={(dragEvent) => {
        dragEvent.dataTransfer.effectAllowed = 'move'
        dragEvent.dataTransfer.setData('text/plain', event.id)
        dragEvent.dataTransfer.setData('application/x-iusentra-agenda-event', event.id)
      }}
      style={{ top: `${eventTopPercent(event)}%`, minHeight: eventHeightPixels(event) }}
    >
      <span className="iu-ag-event__time">{event.timeLabel}</span>
      <strong>{eventIcon(event.kind)} {event.title}</strong>
      <small>{event.subtitle || event.client || event.location}</small>
      <em>{event.durationLabel}</em>
    </a>
  )
}

function MonthEventChip({ event }:{event:AgendaEvent}) {
  return (
    <a
      className={`iu-ag-month-event iu-ag-event--${event.tone}`}
      draggable
      href={event.href || '/agenda'}
      onDragStart={(dragEvent) => {
        dragEvent.dataTransfer.effectAllowed = 'move'
        dragEvent.dataTransfer.setData('text/plain', event.id)
        dragEvent.dataTransfer.setData('application/x-iusentra-agenda-event', event.id)
      }}
    >
      <span>{event.timeLabel}</span>
      <strong>{event.title}</strong>
    </a>
  )
}

function DayColumn({
  day,
  view,
  onCreateSlot,
  onDropEvent,
}:{
  day:ReturnType<typeof buildAgendaPageData>['days'][number]
  view:AgendaView
  onCreateSlot:(dayIso:string, time:string)=>void
  onDropEvent:(eventId:string, dayIso:string, time?:string)=>void
}) {
  if (view === 'month') {
    return (
      <section
        className={`iu-ag-day iu-ag-day--month ${day.isToday ? 'is-today' : ''} ${day.isWeekend ? 'is-weekend' : ''} ${day.isOutsideMonth ? 'is-outside-month' : ''}`}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault()
          const eventId = event.dataTransfer.getData('application/x-iusentra-agenda-event') || event.dataTransfer.getData('text/plain')
          if (eventId) onDropEvent(eventId, day.iso)
        }}
      >
        <button className="iu-ag-month-head" type="button" onClick={() => onCreateSlot(day.iso, '09:00')} aria-label={`Nuovo appuntamento il ${day.iso}`}>
          <span>{day.weekday}</span>
          <strong>{day.label}</strong>
          <small>{day.month}</small>
        </button>
        <div className="iu-ag-month-events">
          {day.events.slice(0, 4).map((event) => <MonthEventChip event={event} key={event.id}/>)}
          {day.events.length > 4 ? <a className="iu-ag-more" href={`/agenda?data=${day.iso}`}>+{day.events.length - 4} altri</a> : null}
          {!day.events.length ? <button className="iu-ag-month-empty" type="button" onClick={() => onCreateSlot(day.iso, '09:00')}><Move size={14}/> Nuovo alle 09:00</button> : null}
        </div>
      </section>
    )
  }

  return (
    <section
      className={`iu-ag-day ${day.isToday ? 'is-today' : ''} ${day.isWeekend ? 'is-weekend' : ''}`}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        const eventId = event.dataTransfer.getData('application/x-iusentra-agenda-event') || event.dataTransfer.getData('text/plain')
        if (eventId) onDropEvent(eventId, day.iso)
      }}
    >
      <header>
        <span>{day.weekday}</span>
        <strong>{day.label}</strong>
        <small>{day.month}</small>
      </header>
      <div className="iu-ag-day__body">
        {timelineSlots.map((slot) => (
          <button
            className="iu-ag-slot"
            type="button"
            key={slot}
            onClick={() => onCreateSlot(day.iso, slot)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault()
              event.stopPropagation()
              const eventId = event.dataTransfer.getData('application/x-iusentra-agenda-event') || event.dataTransfer.getData('text/plain')
              if (eventId) onDropEvent(eventId, day.iso, slot)
            }}
            aria-label={`Nuovo appuntamento il ${day.iso} alle ${slot}`}
          >
            <span>{slot.endsWith(':00') ? slot : ''}</span>
          </button>
        ))}
        {day.events.map((event) => <EventCard event={event} key={event.id}/>)}
        {!day.events.length ? <button className="iu-ag-drop" type="button" onClick={() => onCreateSlot(day.iso, '09:00')}><Move size={15}/> Spazio disponibile</button> : null}
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

function AgendaFocus({ event }:{event:AgendaEvent}) {
  const isDeadline = event.source === 'scadenziario' || event.id.startsWith('scadenza-')
  const editHref = isDeadline ? event.href : `/agenda/${encodeURIComponent(event.id)}/modifica`
  const completeHref = isDeadline ? event.href : `/agenda/${encodeURIComponent(event.id)}/stato`
  return (
    <section className="iu-ag-focus">
      <div>
        <a href="/agenda"><ArrowLeftIcon/>Torna all'agenda</a>
        <span>Elemento selezionato</span>
        <h2>{event.title}</h2>
        <p>{event.subtitle || event.notes || event.location || 'Impegno agenda senza note aggiuntive.'}</p>
      </div>
      <dl>
        <div><dt>Data</dt><dd>{new Date(event.start).toLocaleDateString('it-IT')}</dd></div>
        <div><dt>Orario</dt><dd>{event.timeLabel} · {event.durationLabel}</dd></div>
        <div><dt>Cliente</dt><dd>{event.client || 'Non collegato'}</dd></div>
        <div><dt>Fonte</dt><dd>{event.source}</dd></div>
      </dl>
      <div className="iu-ag-focus__actions">
        <a href={editHref}><Settings2 size={15}/>Modifica</a>
        <a href={event.href || '/agenda'}><CalendarDays size={15}/>Apri origine</a>
        <a href={`/messaggi/nuovo?oggetto=${encodeURIComponent(event.title)}`}><MessageCircleIcon/>Avvisa cliente</a>
        <a href="#lex" data-lex-open data-lex-context="agenda" data-lex-label={`Contesto agenda: ${event.title}`}><Sparkles size={15}/>Chiedi a Lex</a>
        {!isDeadline ? (
          <JsonPostForm action={completeHref}>
            <input type="hidden" name="stato" value="COMPLETATO"/>
            <button type="submit"><CheckCircle2 size={15}/>Segna completato</button>
          </JsonPostForm>
        ) : null}
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
  const [anchorDate, setAnchorDate] = useState(() => new Date())
  const [view, setView] = useState<AgendaView>('week')
  const [kind, setKind] = useState<AgendaKind>('tutti')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<AgendaEvent[]>([])
  const [moveStatus, setMoveStatus] = useState('')
  const selectedId = routeAgendaId()

  const refresh = () => {
    setLoading(true)
    getAgendaPage(anchorDate, view).then((payload) => {
      setEvents(payload.events)
    }).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getAgendaPage(anchorDate, view).then((payload) => {
      if (active) setEvents(payload.events)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [anchorDate, view])

  const filteredEvents = useMemo(() => events.filter((event) => {
    const kindOk = kind === 'tutti' || event.kind === kind
    return kindOk && isSameText(event, query)
  }), [events, kind, query])

  const agenda = useMemo(() => buildAgendaPageData(filteredEvents, anchorDate, 'client', view), [filteredEvents, anchorDate, view])
  const selectedEvent = selectedId ? events.find((event) => event.id === selectedId || event.id === `scadenza-${selectedId}`) : undefined
  const weekStart = startOfWeek(anchorDate)
  const weekEnd = addDays(weekStart, 6)
  const visibleRange = agendaRange(anchorDate, view)
  const today = new Date()
  const displayDays = agenda.days
  const sourceLabel = loading ? 'Sincronizzazione agenda...' : 'Dati agenda aggiornati'
  const dateLabel = view === 'day'
    ? anchorDate.toLocaleDateString('it-IT')
    : view === 'month'
      ? anchorDate.toLocaleDateString('it-IT', { month: 'long', year: 'numeric' })
      : rangeLabel(weekStart, weekEnd)
  const automationTarget = selectedEvent || agenda.summary.nextEvent || filteredEvents[0]
  const automationDate = automationTarget?.date || toDateKey(anchorDate)
  const canCreateTimesheet = Boolean(automationTarget?.matterId)

  const shiftPeriod = (direction: -1 | 1) => {
    setAnchorDate((current) => view === 'month'
      ? addMonths(current, direction)
      : addDays(current, view === 'day' ? direction : direction * 7))
  }

  const openNewAppointment = (dayIso: string, time: string) => {
    window.location.href = createAppointmentHref(dayIso, time)
  }

  const persistMove = async (event: AgendaEvent) => {
    if (!isWritableAgendaEvent(event)) {
      setMoveStatus('Spostamento applicato solo alla vista: la fonte non e modificabile da Agenda.')
      return
    }
    try {
      const response = await fetch(`/api/agenda/${encodeURIComponent(event.id)}/sposta`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ data_ora: localDateTimePayload(event.start) }),
      })
      if (!response.ok) throw new Error('spostamento non salvato')
      setMoveStatus('Spostamento salvato nell agenda reale.')
    } catch {
      setMoveStatus('Spostamento preparato nella vista, ma il salvataggio non e riuscito.')
    }
  }

  const moveEvent = (eventId: string, dayIso: string, time?: string) => {
    const sourceEvent = events.find((event) => event.id === eventId)
    if (!sourceEvent) return
    const movedEvent = time ? moveEventToDateTime(sourceEvent, dayIso, time) : moveEventToDay(sourceEvent, dayIso)
    setEvents((current) => current.map((event) => event.id === eventId ? movedEvent : event))
    setMoveStatus(`Spostato a ${movedEvent.timeLabel} del ${new Date(`${dayIso}T12:00:00`).toLocaleDateString('it-IT')}.`)
    void persistMove(movedEvent)
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
          <Button href="/workspace-intelligente"><Sparkles size={15}/> Regia</Button>
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
          <button type="button" onClick={() => shiftPeriod(-1)} aria-label="Periodo precedente"><ChevronLeft size={16}/></button>
          <button type="button" onClick={() => setAnchorDate(today)}>Oggi</button>
          <button type="button" onClick={() => shiftPeriod(1)} aria-label="Periodo successivo"><ChevronRight size={16}/></button>
          <strong>{dateLabel}</strong>
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
        <small><Move size={14}/> Orari cliccabili e drag & drop su giorno, settimana e mese.</small>
        {moveStatus ? <small className="iu-ag-move-status">{moveStatus}</small> : null}
      </section>

      {selectedEvent ? <AgendaFocus event={selectedEvent}/> : null}

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
              <span>{rangeLabel(visibleRange.from, visibleRange.to)} - {displayDays.length} giorni visibili - {filteredEvents.length} elementi</span>
            </div>
            <div>
              <Badge tone={agenda.summary.unsynced ? 'warning' : 'success'}>{agenda.summary.unsynced ? `${agenda.summary.unsynced} da sincronizzare` : 'allineata'}</Badge>
              <a href="/impostazioni/calendario"><Settings2 size={16}/> Preferenze</a>
            </div>
          </header>
          <div
            className={`iu-ag-week ${view === 'month' ? 'iu-ag-week--month' : view === 'week' ? 'iu-ag-week--week' : 'iu-ag-week--day'}`}
            style={{ gridTemplateColumns: view === 'month' ? undefined : `repeat(${displayDays.length}, minmax(var(--iu-ag-day-min-width, 118px), 1fr))` }}
          >
            {displayDays.map((day) => <DayColumn day={day} key={day.id} view={view} onCreateSlot={openNewAppointment} onDropEvent={moveEvent}/>)}
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
            <a href={messageReminderHref(automationTarget)}>Promemoria cliente</a>
            {canCreateTimesheet ? (
              <JsonPostForm action="/timesheet/nuovo">
                <input type="hidden" name="from_page" value="fascicolo"/>
                <input type="hidden" name="focus" value="workflow"/>
                <input type="hidden" name="id_fascicolo" value={automationTarget?.matterId || ''}/>
                <input type="hidden" name="descrizione" value={`Attività agenda - ${automationTarget?.title || 'impegno'}`}/>
                <input type="hidden" name="data_attivita" value={automationDate}/>
                <input type="hidden" name="minuti" value="30"/>
                <input type="hidden" name="valore_unitario" value="80"/>
                <input type="hidden" name="fatturabile" value="1"/>
                <input type="hidden" name="contesto" value="agenda-react"/>
                <button type="submit">Crea voce timesheet</button>
              </JsonPostForm>
            ) : (
              <button type="button" className="is-disabled" aria-disabled="true" title="Seleziona un evento collegato a un fascicolo per creare il timesheet.">Crea voce timesheet</button>
            )}
            <a href={linkedDeadlineHref(automationTarget)}>Genera scadenza collegata</a>
            <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex'))}>Brief Lex sul fascicolo</button>
          </div>
        </Panel>
      </section>

      <FloatingLex />
    </main>
  )
}
