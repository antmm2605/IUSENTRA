import type React from 'react'
import type { AgendaDay, AgendaEvent, AgendaView } from '../../../agendaData'
import {
  contestoImpegno,
  daLavorare,
  genereImpegno,
  giorniConImpegni,
  giornoEsteso,
  ordina,
  quantiImpegni,
  senzaOra,
  titoloImpegno,
} from './agendaRuoloModel'

type Props = {
  view: AgendaView
  days: AgendaDay[]
  selectedId: string
  onOpen: (event: AgendaEvent) => void
  onOpenDay: (iso: string) => void
  /** Nuovo impegno dall'orario libero della vista giorno. */
  onCreateSlot: (dayIso: string, time: string) => void
  /** Spostamento trascinando la voce su un altro giorno o su un'altra ora (salvato dall'agenda). */
  onDropEvent: (eventId: string, dayIso: string, time?: string) => void
}

const TIPO_TRASCINAMENTO = 'application/x-iusentra-agenda-event'

function accettaTrascinamento(evento: React.DragEvent) {
  if (evento.dataTransfer.types.includes(TIPO_TRASCINAMENTO)) evento.preventDefault()
}

function Segni({ event }: { event: AgendaEvent }) {
  const remoto = Boolean(event.remoteHearingUrl || event.remoteHearingDetected)
  const piattaforma = event.remoteHearingPlatform && !/^altra$/i.test(event.remoteHearingPlatform) ? ` · ${event.remoteHearingPlatform}` : ''
  const perentorio = /perentori/i.test(`${event.notes} ${event.title} ${event.detailLines.join(' ')}`)
  return (
    <span className="iu-ruolo-segni">
      {daLavorare(event) ? <span className="iu-ruolo-sigillo">{event.pendingCount === 1 ? '1 proposta' : `${event.pendingCount} proposte`}</span> : null}
      {event.completed ? <span className="iu-ruolo-segno iu-ruolo-segno--ok">Svolto</span> : null}
      {perentorio && !event.completed ? <span className="iu-ruolo-segno iu-ruolo-segno--perentorio">Perentorio</span> : null}
      {remoto ? <span className="iu-ruolo-segno iu-ruolo-segno--remoto">Da remoto{piattaforma}</span> : null}
    </span>
  )
}

function Voce({ event, aperta, onOpen }: { event: AgendaEvent; aperta: boolean; onOpen: (event: AgendaEvent) => void }) {
  const trascinabile = !event.completed && !event.id.startsWith('scadenza-')
  const { cliente, resto } = contestoImpegno(event)
  const pec = genereImpegno(event) === 'cancelleria'
  return (
    <button type="button" className={`iu-ruolo-voce ${aperta ? 'is-aperta' : ''} ${event.completed ? 'is-svolta' : ''}`}
      onClick={() => onOpen(event)} aria-current={aperta ? 'true' : undefined}
      draggable={trascinabile} onDragStart={(e) => { if (trascinabile) e.dataTransfer.setData(TIPO_TRASCINAMENTO, event.id) }}>
      <time>{senzaOra(event) ? <>Entro<small>la giornata</small></> : <>{event.timeLabel}{pec ? <small>PEC</small> : null}</>}</time>
      <span className={`iu-ruolo-banda iu-ruolo-c-${genereImpegno(event)}`} aria-hidden="true"/>
      <span>
        <strong className="iu-ruolo-titolo">{titoloImpegno(event)}</strong>
        {cliente || resto ? <span className="iu-ruolo-contesto">{cliente ? <b>{cliente}</b> : null}{cliente && resto ? ' · ' : ''}{resto}</span> : null}
      </span>
      <Segni event={event}/>
    </button>
  )
}

function Giornata({ day, selectedId, onOpen, mostraVuota, onDropEvent }: { day: AgendaDay; selectedId: string; onOpen: (e: AgendaEvent) => void; mostraVuota: boolean; onDropEvent: Props['onDropEvent'] }) {
  if (!day.events.length && !mostraVuota) return null
  return (
    <article className={`iu-ruolo-giorno ${day.isToday ? 'is-oggi' : ''}`} aria-label={giornoEsteso(day.iso)}
      onDragOver={accettaTrascinamento} onDrop={(e) => { const id = e.dataTransfer.getData(TIPO_TRASCINAMENTO); if (id) onDropEvent(id, day.iso) }}>
      <header><h2>{giornoEsteso(day.iso)}</h2><small>{day.isToday ? 'oggi · ' : ''}{quantiImpegni(day.events.length)}</small></header>
      {day.events.length
        ? ordina(day.events).map((event) => <Voce key={event.id} event={event} aperta={event.id === selectedId} onOpen={onOpen}/>)
        : <p className="iu-ruolo-vuoto">Nessun impegno: giornata libera.</p>}
    </article>
  )
}

function VistaGiorno({ day, selectedId, onOpen, onCreateSlot, onDropEvent }: { day: AgendaDay; selectedId: string; onOpen: (e: AgendaEvent) => void; onCreateSlot: Props['onCreateSlot']; onDropEvent: Props['onDropEvent'] }) {
  const entro = ordina(day.events.filter(senzaOra))
  const conOra = ordina(day.events.filter((event) => !senzaOra(event)))
  const oreImpegni = conOra.map((event) => Number(event.timeLabel.slice(0, 2)))
  const prima = Math.min(8, ...oreImpegni)
  const ultima = Math.max(19, ...oreImpegni)
  const adesso = day.isToday ? new Date().getHours() : -1
  const ore = Array.from({ length: ultima - prima + 1 }, (_, i) => prima + i)
  return (
    <>
      <article className={`iu-ruolo-giorno ${day.isToday ? 'is-oggi' : ''}`}>
        <header><h2>{giornoEsteso(day.iso)}</h2><small>{quantiImpegni(day.events.length)}</small></header>
      </article>
      {entro.length ? <section className="iu-ruolo-entro" aria-label="Entro la giornata"><h4>Entro la giornata</h4>
        {entro.map((event) => <Voce key={event.id} event={event} aperta={event.id === selectedId} onOpen={onOpen}/>)}</section> : null}
      {ore.map((ora) => (
        <div className={`iu-ruolo-ora ${ora === adesso ? 'is-adesso' : ''}`} key={ora}
          onDragOver={accettaTrascinamento}
          onDrop={(e) => { const id = e.dataTransfer.getData(TIPO_TRASCINAMENTO); if (id) onDropEvent(id, day.iso, `${String(ora).padStart(2, '0')}:00`) }}>
          <span>{String(ora).padStart(2, '0')}:00</span>
          <div>
            {conOra.filter((event) => Number(event.timeLabel.slice(0, 2)) === ora)
              .map((event) => <Voce key={event.id} event={event} aperta={event.id === selectedId} onOpen={onOpen}/>)}
            <button type="button" className="iu-ag-slot iu-ruolo-slot" onClick={() => onCreateSlot(day.iso, `${String(ora).padStart(2, '0')}:00`)}
              aria-label={`Nuovo impegno alle ${String(ora).padStart(2, '0')}:00`}>Nuovo impegno alle {String(ora).padStart(2, '0')}:00</button>
          </div>
        </div>
      ))}
    </>
  )
}

function VistaMese({ days, onOpenDay }: { days: AgendaDay[]; onOpenDay: (iso: string) => void }) {
  return (
    <div className="iu-ruolo-mese">
      {['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'].map((nome) => <div className="iu-ruolo-nome" key={nome}>{nome}</div>)}
      {days.map((day) => {
        const eventi = ordina(day.events)
        return (
          <button type="button" key={day.id} className={`iu-ruolo-cella ${day.isOutsideMonth ? 'is-fuori' : ''} ${day.isToday ? 'is-oggi' : ''}`}
            onClick={() => onOpenDay(day.iso)} aria-label={`${giornoEsteso(day.iso)}: ${quantiImpegni(eventi.length)}`}>
            <span className="iu-ruolo-num">{day.label}</span>
            {eventi.slice(0, 3).map((event) => (
              <span key={event.id} className={`iu-ruolo-pillola ${daLavorare(event) ? 'is-lavoro' : ''}`}>
                <i className={`iu-ruolo-c-${genereImpegno(event)}`}/>{senzaOra(event) ? 'Entro' : event.timeLabel} {(event.client || titoloImpegno(event)).split(' ')[0]}
              </span>
            ))}
            {eventi.length > 3 ? <span className="iu-ruolo-altre">altri {eventi.length - 3}</span> : null}
          </button>
        )
      })}
    </div>
  )
}

export function AgendaRuolo({ view, days, selectedId, onOpen, onOpenDay, onCreateSlot, onDropEvent }: Props) {
  if (view === 'month') return <VistaMese days={days} onOpenDay={onOpenDay}/>
  if (view === 'day') {
    return days[0]
      ? <VistaGiorno day={days[0]} selectedId={selectedId} onOpen={onOpen} onCreateSlot={onCreateSlot} onDropEvent={onDropEvent}/>
      : <p className="iu-ruolo-nessuna">Nessun impegno.</p>
  }
  const elenco = view === 'timeline'
  const visibili = elenco ? giorniConImpegni(days) : days
  if (!visibili.length) return <p className="iu-ruolo-nessuna">Nessun impegno corrisponde ai filtri.</p>
  return <>{visibili.map((day) => <Giornata key={day.id} day={day} selectedId={selectedId} onOpen={onOpen} mostraVuota={!elenco} onDropEvent={onDropEvent}/>)}</>
}
