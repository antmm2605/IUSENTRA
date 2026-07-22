import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  FileSearch,
  Filter,
  Landmark,
  ListChecks,
  MapPin,
  Maximize2,
  Minimize2,
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
import { SourceDocumentModal } from './SourceDocumentModal'
import { OperationalModal } from './OperationalModal'
import type { AgendaEvent, AgendaKind, AgendaView } from '../agendaData'
import { formatDateIt } from '../formatting'
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
  const haystack = [event.title, event.displayTitle, event.legalLabel, event.subtitle, event.client, event.court, event.matter, event.location, event.owner, ...event.detailLines].join(' ').toLowerCase()
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
  return value === 'day' || value === 'month' || value === 'week' ? value : 'week'
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
  return event.legalLabel || (event.kind === 'udienza' ? 'Udienza' : event.kind === 'deposito' ? 'Deposito' : event.kind === 'scadenza' ? 'Scadenza da presidiare' : 'Adempimento')
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

function agendaDetailLines(event: AgendaEvent): string[] {
  const details = event.detailLines?.length
    ? event.detailLines
    : [
        event.client ? `Cliente/parte: ${event.client}` : '',
        event.matter ? `Fascicolo/RG: ${event.matter}` : '',
        event.court ? `Ufficio: ${event.court}` : '',
        event.location ? `Luogo: ${event.location}` : '',
        event.notes ? `Dettaglio: ${event.notes}` : '',
      ].filter(Boolean)
  return details.slice(0, 7)
}

function remoteHearingHost(url: string): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

function layoutEvents(events: AgendaEvent[]): { event: AgendaEvent; clusteredEvents: AgendaEvent[] }[] {
  const sorted = [...events].sort((left, right) => new Date(left.start).getTime() - new Date(right.start).getTime())
  const groups: AgendaEvent[][] = []
  let visualEnd = Number.NEGATIVE_INFINITY

  for (const event of sorted) {
    const start = new Date(event.start).getTime()
    const actualEnd = new Date(event.end).getTime()
    const eventVisualEnd = Math.max(actualEnd, start + (125 * 60 * 1000))
    if (!groups.length || start >= visualEnd) {
      groups.push([event])
      visualEnd = eventVisualEnd
      continue
    }
    groups[groups.length - 1].push(event)
    visualEnd = Math.max(visualEnd, eventVisualEnd)
  }

  return groups.map((group) => ({ event: group[0], clusteredEvents: group }))
}

function clusterWhenLabel(events: AgendaEvent[]): string {
  const times = [...new Set(events.map((event) => event.timeLabel))]
  return times.length === 1 ? `alle ${times[0]}` : `tra ${times[0]} e ${times[times.length - 1]}`
}

function EventCard({
  event,
  clusteredEvents = [event],
  onOpenSource,
  onOpenDetail,
}:{
  event:AgendaEvent
  clusteredEvents?:AgendaEvent[]
  onOpenSource:(event:AgendaEvent)=>void
  onOpenDetail:(event:AgendaEvent)=>void
}) {
  const isCluster = clusteredEvents.length > 1
  const label = agendaLegalLabel(event)
  const title = agendaTitle(event)
  const subjectLine = agendaSubjectLine(event)
  const detailLines = agendaDetailLines(event)
  const whenLabel = `${new Date(event.start).toLocaleDateString('it-IT')} ${event.timeLabel}${event.durationLabel ? ` · ${event.durationLabel}` : ''}`
  const remoteUrl = event.remoteHearingVerified ? event.remoteHearingUrl : ''
  const clusterWhen = clusterWhenLabel(clusteredEvents)
  const tooltipLines = [
    event.client ? `Cliente/parte: ${event.client}` : '',
    event.matter ? `Fascicolo/RG: ${event.matter}` : '',
    `Quando: ${whenLabel}`,
    event.location ? `Luogo: ${event.location}` : '',
    event.remoteHearingPlatform ? `Piattaforma: ${event.remoteHearingPlatform}` : '',
    event.remoteHearingMeetingId ? `ID riunione: ${event.remoteHearingMeetingId}` : '',
    event.remoteHearingPasscode ? `Codice di accesso: ${event.remoteHearingPasscode}` : '',
    event.remoteHearingAccessInfo ? `Istruzioni: ${event.remoteHearingAccessInfo}` : '',
    event.completed ? 'Stato: completata' : '',
    ...detailLines.filter((line) => !/^Cliente\/parte:|^Fascicolo\/RG:|^Luogo:|^Link udienza audiovisiva:/i.test(line)),
  ].filter(Boolean).slice(0, remoteUrl ? 9 : 6)
  const accessibleLabel = isCluster
    ? `${clusteredEvents.length} eventi ${clusterWhen}: ${clusteredEvents.map((item) => `${item.timeLabel}, ${agendaLegalLabel(item)} ${agendaSubjectLine(item)}`).join('. ')}`
    : `${label}: ${title}. ${tooltipLines.join('. ')}${remoteUrl ? '. Collegamento audiovisivo disponibile' : ''}`
  const normalizedTitle = subjectLine.toLocaleLowerCase('it-IT')
  const contextLine = [event.matter, event.client]
    .filter((value, index, values) => value && values.indexOf(value) === index && !normalizedTitle.includes(value.toLocaleLowerCase('it-IT')))
    .join(' · ')
  const placeLine = [event.court, event.location].filter((value, index, values) => value && values.indexOf(value) === index).join(' · ')
  const naturalHeight = eventHeightPixels(event)
  const isCompact = !isCluster && naturalHeight < 78
  const isLate = new Date(event.start).getHours() >= 16
  const href = event.href || '/agenda'
  const clusterSummary = `${clusteredEvents.length} attività raggruppate`
  const renderClusterEventList = (mode: 'inline' | 'tooltip') => (
    <div className={`iu-ag-event__cluster-list ${mode === 'inline' ? 'iu-ag-event__cluster-list--inline' : ''}`} aria-label="Eventi raggruppati nell'agenda">
      {clusteredEvents.map((clusterEvent) => (
        <section key={`${mode}-${clusterEvent.id}`}>
          <a href={clusterEvent.href || '/agenda'} onClick={(clickEvent) => {
            if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
            clickEvent.preventDefault()
            onOpenDetail(clusterEvent)
          }}>
            <strong>{clusterEvent.timeLabel} · {agendaLegalLabel(clusterEvent)}</strong>
            <span>{agendaSubjectLine(clusterEvent)}</span>
          </a>
          <div>
            {clusterEvent.remoteHearingVerified && clusterEvent.remoteHearingUrl ? <a href={clusterEvent.remoteHearingUrl} target="_blank" rel="noreferrer"><Video size={13}/>Collegati</a> : null}
            {clusterEvent.sourceHref ? <button type="button" onClick={() => onOpenSource(clusterEvent)}><FileSearch size={13}/>Apri fonte</button> : null}
          </div>
        </section>
      ))}
    </div>
  )
  return (
    <article
      className={`iu-ag-event iu-ag-event--${event.tone} ${event.completed ? 'is-completed' : ''} ${isCompact ? 'is-compact' : ''} ${isCluster ? 'is-cluster' : ''} ${isLate ? 'is-late' : ''}`}
      draggable={!isCluster}
      onDragStart={(dragEvent) => {
        if (isCluster) {
          dragEvent.preventDefault()
          return
        }
        dragEvent.dataTransfer.effectAllowed = 'move'
        dragEvent.dataTransfer.setData('text/plain', event.id)
        dragEvent.dataTransfer.setData('application/x-iusentra-agenda-event', event.id)
      }}
      style={{ top: `${eventTopPercent(event)}%`, minHeight: isCluster ? 82 : isCompact ? Math.max(68, naturalHeight) : naturalHeight, left: '10px', width: 'calc(100% - 20px)' }}
    >
      <a className="iu-ag-event__target" href={href} aria-label={accessibleLabel} onClick={(clickEvent) => {
        if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
        clickEvent.preventDefault()
        onOpenDetail(event)
      }}>
        <span className="iu-ag-event__content">
          <strong>{event.completed ? <CheckCircle2 size={14}/> : eventIcon(event.kind)} <span>{isCluster ? `${clusteredEvents.length} eventi ${clusterWhen}` : label}</span></strong>
          <span className="iu-ag-event__meta">
            <span className="iu-ag-event__reference">{isCluster ? clusterSummary : subjectLine}</span>
            <span className="iu-ag-event__time">{isCluster ? `${clusteredEvents.length} attività` : event.timeLabel}{!isCluster && !isCompact && event.durationLabel ? ` · ${event.durationLabel}` : ''}</span>
          </span>
          {!isCluster && !isCompact && contextLine ? <small className="iu-ag-event__context">{contextLine}</small> : null}
          {!isCluster && !isCompact && placeLine ? <small className="iu-ag-event__place"><MapPin size={10}/>{placeLine}</small> : null}
        </span>
      </a>
      <div className="iu-ag-event__tooltip" role="tooltip">
        {isCluster ? (
          <>
            <b>{clusteredEvents.length} eventi {clusterWhen}</b>
            {renderClusterEventList('tooltip')}
          </>
        ) : (
          <>
            <b>{agendaHeadline(event)}</b>
            {tooltipLines.map((line) => <span key={line}>{line}</span>)}
            {remoteUrl ? (
              <a className="iu-ag-event__remote-link" href={remoteUrl} target="_blank" rel="noreferrer" title={remoteUrl}>
                <Video size={14}/>
                <span>Collegati all'udienza{remoteHearingHost(remoteUrl) ? ` · ${remoteHearingHost(remoteUrl)}` : ''}</span>
              </a>
            ) : null}
            {event.sourceHref ? (
              <button className="iu-ag-event__remote-link iu-ag-event__source-link" type="button" onClick={() => onOpenSource(event)} title={`Apri fonte: ${event.sourceLabel || 'fonte originaria'}`}>
                <FileSearch size={14}/>
                <span>Apri fonte{event.sourceLabel ? ` · ${event.sourceLabel}` : ''}</span>
                {event.sourceVerified ? <CheckCircle2 size={13}/> : null}
              </button>
            ) : null}
          </>
        )}
      </div>
    </article>
  )
}

function AgendaLegend() {
  return (
    <div className="iu-ag-legend" aria-label="Legenda colori agenda">
      <span><i className="is-hearing"/>Udienza</span>
      <span><i className="is-deadline"/>Scadenza o deposito</span>
      <span><i className="is-appointment"/>Appuntamento</span>
      <span><i className="is-studio"/>Attività di studio</span>
      <span><i className="is-completed"/>Completata</span>
    </div>
  )
}

function MonthEventChip({ event, onOpenDetail }:{event:AgendaEvent; onOpenDetail:(event:AgendaEvent)=>void}) {
  const label = agendaLegalLabel(event)
  const subjectLine = agendaSubjectLine(event)
  const href = event.href || '/agenda'
  return (
    <a
      className={`iu-ag-month-event iu-ag-event--${event.tone}`}
      draggable
      href={href}
      onClick={(clickEvent) => {
        if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
        clickEvent.preventDefault()
        onOpenDetail(event)
      }}
      onDragStart={(dragEvent) => {
        dragEvent.dataTransfer.effectAllowed = 'move'
        dragEvent.dataTransfer.setData('text/plain', event.id)
        dragEvent.dataTransfer.setData('application/x-iusentra-agenda-event', event.id)
      }}
    >
      <strong>{label}</strong>
      <span>{event.timeLabel}</span>
      <small>{subjectLine}</small>
    </a>
  )
}

function DayColumn({
  day,
  view,
  onCreateSlot,
  onDropEvent,
  onOpenSource,
  onOpenDetail,
}:{
  day:ReturnType<typeof buildAgendaPageData>['days'][number]
  view:AgendaView
  onCreateSlot:(dayIso:string, time:string)=>void
  onDropEvent:(eventId:string, dayIso:string, time?:string)=>void
  onOpenSource:(event:AgendaEvent)=>void
  onOpenDetail:(event:AgendaEvent)=>void
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
          {day.events.slice(0, 4).map((event) => <MonthEventChip event={event} onOpenDetail={onOpenDetail} key={event.id}/>)}
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
        {layoutEvents(day.events).map(({ event, clusteredEvents }) => <EventCard event={event} clusteredEvents={clusteredEvents} onOpenSource={onOpenSource} onOpenDetail={onOpenDetail} key={event.id}/>)}
        {!day.events.length ? <button className="iu-ag-drop" type="button" onClick={() => onCreateSlot(day.iso, '09:00')}><Move size={15}/> Spazio disponibile</button> : null}
      </div>
    </section>
  )
}

function AgendaInspector({ events, nextEvent, unsynced, onOpenDetail }:{events:AgendaEvent[]; nextEvent?:AgendaEvent; unsynced:number; onOpenDetail:(event:AgendaEvent)=>void}) {
  const critical = events.filter((event) => event.priority === 'critica' || event.priority === 'alta').slice(0, 4)
  const focusEvent = nextEvent || [...events].sort((left, right) => new Date(left.start).getTime() - new Date(right.start).getTime())[0]
  return (
    <aside className="iu-ag-inspector">
      <Panel title="Briefing agenda" subtitle="Priorità operative e prossime mosse" icon={<Sparkles size={17}/>}>
        <div className="iu-ag-brief">
          {focusEvent ? (
            <article>
              <span>{nextEvent ? 'Prossimo impegno' : 'Da presidiare nel periodo'}</span>
              <strong>{focusEvent.timeLabel} - {agendaLegalLabel(focusEvent)} · {agendaSubjectLine(focusEvent)}</strong>
              <small>{focusEvent.subtitle || focusEvent.location || 'Apri il dettaglio per le attività collegate.'}</small>
            </article>
          ) : <p className="iu-empty">Nessun impegno imminente.</p>}
          <div className="iu-ag-quick-actions">
            <Button variant="primary" href="/agenda/nuovo"><CalendarPlus size={15}/> Nuovo</Button>
            <Button href="/impostazioni/calendario"><CalendarSync size={15}/> Calendari</Button>
          </div>
        </div>
      </Panel>

      <Panel title="Priorità da non perdere" icon={<AlertTriangle size={17}/>} count={critical.length}>
        {critical.length ? (
          <div className="iu-ag-priority-list">
            {critical.map((event) => (
              <a href={event.href || '/agenda'} key={event.id} onClick={(clickEvent) => {
                if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
                clickEvent.preventDefault()
                onOpenDetail(event)
              }}>
                <Badge tone={event.tone}>{event.kind}</Badge>
                <strong>{agendaHeadline(event)}</strong>
                <span>{formatDateIt(event.date, event.date)} - {event.timeLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna urgenza nel periodo visibile.</p>}
      </Panel>

      <Panel title="Salute sincronizzazione" icon={<CalendarSync size={17}/>} count={unsynced}>
        <div className="iu-ag-sync-health">
          <strong>{unsynced ? `${unsynced} elementi da riallineare` : 'Calendari allineati'}</strong>
          <span>Ultimo controllo completato sui calendari collegati.</span>
          <a href="/impostazioni/calendario">Configura calendari -&gt;</a>
        </div>
      </Panel>
    </aside>
  )
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

function AgendaFocus({ event, onOpenSource }:{event:AgendaEvent; onOpenSource:(event:AgendaEvent)=>void}) {
  const isDeadline = event.source === 'scadenziario' || event.id.startsWith('scadenza-')
  const editHref = isDeadline ? event.href : `/agenda/${encodeURIComponent(event.id)}/modifica`
  const completeHref = isDeadline ? event.href : `/agenda/${encodeURIComponent(event.id)}/stato`
  const visibleDetails = event.detailLines.filter((line) => line.trim()).slice(0, 12)
  return (
    <section className="iu-ag-focus">
      <div>
        <a href="/agenda"><ArrowLeftIcon/>Torna all'agenda</a>
        <span>Dettaglio operativo</span>
        <h2>{agendaHeadline(event)}</h2>
        <p>{event.subtitle || event.notes || event.location || 'Verifica il fascicolo collegato prima dell’attività.'}</p>
        {visibleDetails.length ? (
          <ul className="iu-ag-focus__details">
            {visibleDetails.map((line) => <li key={line}>{line}</li>)}
          </ul>
        ) : null}
      </div>
      <dl>
        <div><dt>Data</dt><dd>{new Date(event.start).toLocaleDateString('it-IT')}</dd></div>
        <div><dt>Orario</dt><dd>{event.timeLabel} · {event.durationLabel}</dd></div>
        <div><dt>Cliente/parte</dt><dd>{event.client || 'Da collegare'}</dd></div>
        <div><dt>Fascicolo/RG</dt><dd>{event.matter || 'Da indicare'}</dd></div>
        <div><dt>Origine</dt><dd>{agendaSourceLabel(event.source, event)}</dd></div>
        {event.remoteHearingPlatform ? <div><dt>Piattaforma</dt><dd>{event.remoteHearingPlatform}</dd></div> : null}
        {event.remoteHearingMeetingId ? <div><dt>ID riunione</dt><dd>{event.remoteHearingMeetingId}</dd></div> : null}
        {event.remoteHearingPasscode ? <div><dt>Codice di accesso</dt><dd>{event.remoteHearingPasscode}</dd></div> : null}
        {event.remoteHearingAccessInfo ? <div><dt>Istruzioni</dt><dd>{event.remoteHearingAccessInfo}</dd></div> : null}
      </dl>
      <div className="iu-ag-focus__actions">
        {event.remoteHearingVerified && event.remoteHearingUrl ? <a href={event.remoteHearingUrl} target="_blank" rel="noreferrer"><Video size={15}/>Collegati all'udienza</a> : null}
        <a href={editHref}><Settings2 size={15}/>Modifica</a>
        {event.sourceHref ? (
          <button type="button" onClick={() => onOpenSource(event)} title={`Apri origine: ${event.sourceLabel || 'fonte originaria'}`}><FileSearch size={15}/>Apri origine</button>
        ) : (
          <a href={event.href || '/agenda'}><CalendarDays size={15}/>Apri origine</a>
        )}
        <a href={`/messaggi/nuovo?oggetto=${encodeURIComponent(agendaHeadline(event))}`}><MessageCircleIcon/>Avvisa cliente</a>
        <a href="#lex" data-lex-open data-lex-context="agenda" data-lex-label={`Contesto agenda: ${agendaHeadline(event)}`}><Sparkles size={15}/>Chiedi a Lex</a>
        {!isDeadline && event.completed ? (
          <span className="iu-ag-focus__completed" role="status"><CheckCircle2 size={15}/>Attività completata</span>
        ) : !isDeadline ? (
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
  const plannerRef = useRef<HTMLElement>(null)
  const [anchorDate, setAnchorDate] = useState(initialAgendaDate)
  const [view, setView] = useState<AgendaView>(initialAgendaView)
  const [kind, setKind] = useState<AgendaKind>(initialAgendaKind)
  const [query, setQuery] = useState(initialAgendaQuery)
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<AgendaEvent[]>([])
  const [dataDiagnostic, setDataDiagnostic] = useState('')
  const [dataSource, setDataSource] = useState('iniziale')
  const [moveStatus, setMoveStatus] = useState('')
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

  const refresh = () => {
    setLoading(true)
    getAgendaPage(anchorDate, view).then((payload) => {
      setEvents(payload.events)
      setDataDiagnostic(payload.diagnostic)
      setDataSource(payload.source)
    }).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getAgendaPage(anchorDate, view).then((payload) => {
      if (active) {
        setEvents(payload.events)
        setDataDiagnostic(payload.diagnostic)
        setDataSource(payload.source)
      }
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
  const highlightedEvent = agenda.summary.nextEvent || agenda.events[0]
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

  const closeAgendaDetail = () => {
    window.history.replaceState(window.history.state, '', `/agenda${window.location.search}`)
    setDetailPreview(null)
  }
  const weekStart = startOfWeek(anchorDate)
  const weekEnd = addDays(weekStart, 6)
  const visibleRange = agendaRange(anchorDate, view)
  const today = new Date()
  const displayDays = agenda.days
  const sourceLabel = loading ? 'Sincronizzazione agenda...' : 'Dati agenda aggiornati'
  const dateLabel = view === 'day'
    ? anchorDate.toLocaleDateString('it-IT')
    : view === 'month'
      ? anchorDate.toLocaleDateString('it-IT', { timeZone: 'Europe/Rome', month: 'long', year: 'numeric' })
      : rangeLabel(weekStart, weekEnd)
  const automationTarget = selectedEvent || agenda.summary.nextEvent || filteredEvents[0]
  const automationDate = automationTarget?.date || toDateKey(anchorDate)
  const canCreateTimesheet = Boolean(automationTarget?.matterId)

  const shiftPeriod = (direction: -1 | 1) => {
    setAnchorDate((current) => view === 'month'
      ? addMonths(current, direction)
      : addDays(current, view === 'day' ? direction : direction * 7))
  }

  const togglePlannerExpanded = async () => {
    if (plannerExpanded) {
      if (document.fullscreenElement === plannerRef.current) await document.exitFullscreen()
      setPlannerExpanded(false)
      return
    }
    if (plannerRef.current?.requestFullscreen) {
      try {
        await plannerRef.current.requestFullscreen()
        setPlannerExpanded(true)
        return
      } catch {
        // La classe espansa mantiene il planner operativo quando il browser nega il fullscreen nativo.
      }
    }
    setPlannerExpanded(true)
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

      <section
        ref={plannerRef}
        className={`iu-ag-planner ${plannerExpanded ? 'is-expanded' : ''}`}
        data-agenda-diagnostic={dataDiagnostic}
        data-agenda-filtered-count={filteredEvents.length}
        data-agenda-loaded-count={events.length}
        data-agenda-source={dataSource}
      >
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
        <button
          className="iu-ag-icon-btn"
          type="button"
          onClick={() => void togglePlannerExpanded()}
          aria-label={plannerExpanded ? 'Esci dalla visualizzazione a tutto schermo' : 'Espandi il planner a tutto schermo'}
          title={plannerExpanded ? 'Esci da tutto schermo' : 'Planner a tutto schermo'}
        >
          {plannerExpanded ? <Minimize2 size={17}/> : <Maximize2 size={17}/>}
        </button>
        <a className="iu-ag-icon-btn" href="/agenda/export.ics" aria-label="Scarica calendario"><Download size={17}/></a>
        <a className="iu-ag-icon-btn" href="/agenda/importa" aria-label="Importa calendario"><UploadCloud size={17}/></a>
      </section>

      <section className="iu-ag-status-line">
        <span className={loading ? '' : 'is-ok'}>{sourceLabel}</span>
        {highlightedEvent ? (
          <a
            className="iu-ag-highlight"
            href={highlightedEvent.href || '/agenda'}
            onClick={(clickEvent) => {
              if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
              clickEvent.preventDefault()
              openAgendaDetail(highlightedEvent)
            }}
          >
            <Clock3 size={14}/><b>In evidenza:</b> {agendaLegalLabel(highlightedEvent)} · {agendaSubjectLine(highlightedEvent)} · {highlightedEvent.timeLabel}
          </a>
        ) : null}
        <small><ListChecks size={14}/>{filteredEvents.length} {filteredEvents.length === 1 ? 'elemento' : 'elementi'} nel periodo selezionato.</small>
        {moveStatus ? <small className="iu-ag-move-status">{moveStatus}</small> : null}
      </section>
      <section className="iu-ag-layout">
        <div className="iu-ag-calendar-card">
          <header>
            <div>
              <strong>{view === 'day' ? 'Vista giorno' : view === 'month' ? 'Vista mese compatta' : 'Vista settimana'}</strong>
              <span>{rangeLabel(visibleRange.from, visibleRange.to)} - {displayDays.length} giorni visibili - {filteredEvents.length} {filteredEvents.length === 1 ? 'elemento' : 'elementi'}</span>
              <AgendaLegend />
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
            {displayDays.map((day) => <DayColumn day={day} key={day.id} view={view} onCreateSlot={openNewAppointment} onDropEvent={moveEvent} onOpenSource={setSourcePreview} onOpenDetail={openAgendaDetail}/>)}
          </div>
        </div>
        <AgendaInspector events={filteredEvents} nextEvent={agenda.summary.nextEvent} unsynced={agenda.summary.unsynced} onOpenDetail={openAgendaDetail}/>
      </section>

      <section className="iu-ag-kpis">
        <Kpi icon={<Clock3 size={19}/>} label="Oggi" value={agenda.summary.today} note="impegni in giornata"/>
        <Kpi icon={<CalendarCheck size={19}/>} label="Settimana" value={agenda.summary.week} note="eventi nel periodo"/>
        <Kpi icon={<Landmark size={19}/>} label="Udienze" value={agenda.summary.hearings} note="da presidiare"/>
        <Kpi icon={<ListChecks size={19}/>} label="Scadenze" value={agenda.summary.deadlines} note="termini e depositi"/>
        <Kpi icon={<Bell size={19}/>} label="Alert" value={agenda.summary.critical} note="priorità alta o critica"/>
      </section>
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
                <input type="hidden" name="descrizione" value={`Attività agenda - ${automationTarget ? agendaTitle(automationTarget) : 'impegno'}`}/>
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
      <OperationalModal
        open={Boolean(detailPreview)}
        ariaLabel="Dettaglio operativo agenda"
        eyebrow={<><CalendarCheck size={14}/> Dettaglio operativo</>}
        title={detailPreview ? `${agendaLegalLabel(detailPreview)} · ${agendaTitle(detailPreview)}` : ''}
        subtitle={detailPreview ? `${new Date(detailPreview.start).toLocaleDateString('it-IT')} · ${detailPreview.timeLabel}` : ''}
        onClose={closeAgendaDetail}
        boxClassName="iu-ag-source-modal__box--detail"
        bodyClassName="iu-ag-source-modal__body--detail"
      >
        {detailPreview ? <AgendaFocus event={detailPreview} onOpenSource={setSourcePreview}/> : null}
      </OperationalModal>
      <SourceDocumentModal
        source={sourcePreview ? {
          href: sourcePreview.sourceHref,
          label: sourcePreview.sourceLabel || agendaTitle(sourcePreview),
          context: `${agendaHeadline(sourcePreview)} · ${agendaSubjectLine(sourcePreview)}`,
          kind: sourcePreview.sourceKind,
        } : null}
        onClose={() => setSourcePreview(null)}
      />
    </main>
  )
}
