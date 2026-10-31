import { Plus } from 'lucide-react'
import { Badge } from '../dashboard'
import type { FascicoloAppointment, FascicoloDeadline } from '../../fascicoliData'
import { oggiRoma, vociAgendaFascicolo, type Voce } from './agendaFascicoloVoci'
import './AgendaFascicolo.css'

/**
 * Mini agenda del fascicolo: scadenze e appuntamenti in un'unica linea del tempo.
 *
 * Le voci sono le stesse dell'agenda principale e dello scadenziario (nessuna copia):
 * aprendole si modifica la voce originale e ciò che si crea da qui nasce già collegato
 * al fascicolo. Prima i prossimi impegni dal più vicino, poi i passati in un riquadro
 * richiudibile (richiesta dell'avvocato del 31/10/2026).
 */
function Riga({ voce, oggi }: { voce: Voce; oggi: string }) {
  const evidenza = voce.giorno === oggi ? 'oggi' : ''
  return (
    <a className={`iu-fas-deadline-row iu-agenda-fascicolo__voce${voce.passata ? ' is-passata' : ''}`} href={voce.href}>
      <Badge tone={voce.passata ? 'neutral' : voce.tono}>{voce.etichetta}</Badge>
      <strong>{voce.titolo}</strong>
      <span>{voce.quando}{voce.perentorio ? ' · perentorio' : ''}{evidenza ? ' · oggi' : ''}</span>
    </a>
  )
}

export function AgendaFascicolo({ fascicoloId, scadenze, appuntamenti, caricato }: {
  fascicoloId: string
  scadenze: FascicoloDeadline[]
  appuntamenti: FascicoloAppointment[]
  caricato: boolean
}) {
  const oggi = oggiRoma()
  const voci = vociAgendaFascicolo(scadenze, appuntamenti, oggi)
  const prossime = voci.filter((v) => !v.passata)
  const passate = voci.filter((v) => v.passata)
  const id = encodeURIComponent(fascicoloId)
  return (
    <div className="iu-agenda-fascicolo">
      <h3>Agenda del fascicolo</h3>
      <p className="iu-fas-section-intro">Scadenze e appuntamenti di questo fascicolo, gli stessi dell'agenda e dello scadenziario dello studio.</p>
      {prossime.map((voce) => <Riga key={voce.id} voce={voce} oggi={oggi} />)}
      {caricato && !prossime.length ? <p className="iu-empty">Nessun impegno in programma.</p> : null}
      {passate.length ? (
        <details className="iu-agenda-fascicolo__passate">
          <summary>Impegni passati ({passate.length})</summary>
          {passate.map((voce) => <Riga key={voce.id} voce={voce} oggi={oggi} />)}
        </details>
      ) : null}
      <div className="iu-agenda-fascicolo__azioni">
        <a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${id}`}><Plus size={14} /> Nuova scadenza</a>
        <a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${id}`}><Plus size={14} /> Nuovo appuntamento</a>
      </div>
    </div>
  )
}
