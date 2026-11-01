import { CalendarDays, Plus } from 'lucide-react'
import type { MouseEvent } from 'react'
import { Badge } from '../dashboard'
import type { FascicoloAppointment, FascicoloDeadline } from '../../fascicoliData'
import { oggiRoma, prossimiImpegni, vociAgendaFascicolo } from './agendaFascicoloVoci'
import './AgendaFascicolo.css'

/**
 * Agenda compatta in testa al fascicolo (richiesta dell'avvocato del 01/11/2026): i prossimi impegni
 * del fascicolo a colpo d'occhio, senza aprire «Udienze e scadenze». Sono le stesse voci dell'agenda
 * e dello scadenziario dello studio; l'elenco completo, con i passati, resta nella sezione dedicata.
 */
export function AgendaFascicoloCompatta({ fascicoloId, scadenze, appuntamenti, stato, onTutti }: {
  fascicoloId: string
  scadenze: FascicoloDeadline[]
  appuntamenti: FascicoloAppointment[]
  stato: 'idle' | 'loading' | 'loaded' | 'error' | string
  onTutti: (event: MouseEvent<HTMLAnchorElement>) => void
}) {
  const oggi = oggiRoma()
  const { voci, altri } = prossimiImpegni(vociAgendaFascicolo(scadenze, appuntamenti, oggi))
  const id = encodeURIComponent(fascicoloId)
  return (
    <section className="iu-agenda-compatta" aria-label="Prossimi impegni del fascicolo">
      <header>
        <strong><CalendarDays size={16}/> Prossimi impegni</strong>
        <a className="iu-fas-inline-link" href="#udienze" onClick={onTutti}>Tutti{altri ? ` (+${altri})` : ''}</a>
      </header>
      {stato === 'loading' || stato === 'idle' ? <p className="iu-empty" role="status">Caricamento delle scadenze…</p> : null}
      {stato === 'error' ? <p className="iu-empty" role="alert">Scadenze non caricate: apri «Udienze e scadenze» per riprovare.</p> : null}
      {stato === 'loaded' && !voci.length ? <p className="iu-empty">Nessun impegno in programma.</p> : null}
      {voci.map((voce) => (
        <a key={voce.id} className={`iu-agenda-compatta__voce${voce.giorno === oggi ? ' is-oggi' : ''}`} href={voce.href}>
          <span className="iu-agenda-compatta__quando">{voce.quando}{voce.giorno === oggi ? ' · oggi' : ''}</span>
          <span className="iu-agenda-compatta__titolo">{voce.titolo}</span>
          <Badge tone={voce.tono}>{voce.perentorio ? 'perentorio' : voce.etichetta}</Badge>
        </a>
      ))}
      <div className="iu-agenda-fascicolo__azioni">
        <a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${id}`}><Plus size={14}/> Scadenza</a>
        <a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${id}`}><Plus size={14}/> Appuntamento</a>
      </div>
    </section>
  )
}
