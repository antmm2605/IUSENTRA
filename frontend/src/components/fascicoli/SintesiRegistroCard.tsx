import { Database } from 'lucide-react'
import { formatDateIt, formatDateTimeIt } from '../../formatting'
import { etichettaStatoFascicolo, lettoriSintesi, riepilogoAttesaSintesi, type SintesiRegistro } from './lettureFascicolo'

// La scheda del registro delle letture: chi è il fascicolo per tutti i motori (cliente, pratica, ufficio,
// stato e date), che cosa contiene e, per ogni lettore, che cosa ha letto e quando. Tutto da una riga SQL.
export function SintesiRegistroCard({ sintesi }: { sintesi: SintesiRegistro | null | undefined }) {
  if (!sintesi) return null
  const rg = sintesi.numero_rg ? `R.G. ${sintesi.numero_rg}${sintesi.anno_rg ? `/${sintesi.anno_rg}` : ''}` : ''
  const date: Array<[string, string]> = [
    ['Apertura', sintesi.data_apertura],
    ['Definizione', sintesi.data_definizione],
    ['Archiviazione', sintesi.data_archiviazione],
    ['Prossima udienza', sintesi.prossima_udienza],
  ]
  const lettori = lettoriSintesi(sintesi)
  return (
    <details className="iu-fas-registro">
      <summary>
        <Database size={14}/> Registro del fascicolo
        <span>{sintesi.documenti_presenti} documenti · {sintesi.pec_collegate} PEC · {sintesi.allegati_pec} allegati{` · ${riepilogoAttesaSintesi(sintesi)}`}</span>
      </summary>
      <dl className="iu-fas-registro__identita">
        <div><dt>Cliente</dt><dd>{sintesi.cliente || 'n.d.'}</dd></div>
        <div><dt>Pratica</dt><dd>{sintesi.tipo_pratica ? sintesi.tipo_pratica.toLowerCase() : 'n.d.'}</dd></div>
        <div><dt>Ufficio</dt><dd>{[sintesi.ufficio, rg].filter(Boolean).join(' · ') || 'n.d.'}</dd></div>
        <div><dt>Stato</dt><dd>{etichettaStatoFascicolo(sintesi.stato) || 'n.d.'}</dd></div>
        {date.filter(([, valore]) => valore).map(([etichetta, valore]) => <div key={etichetta}><dt>{etichetta}</dt><dd>{formatDateIt(valore, valore)}</dd></div>)}
      </dl>
      {lettori.length ? (
        <table className="iu-fas-registro__lettori">
          <thead><tr><th scope="col">Motore</th><th scope="col">Letti</th><th scope="col">Da leggere</th><th scope="col">Ultima lettura</th></tr></thead>
          <tbody>
            {lettori.map((voce) => (
              <tr key={voce.id} className={voce.errori ? 'is-danger' : voce.da_leggere ? 'is-warning' : ''} title={voce.versione ? `Versione del lettore: ${voce.versione}` : undefined}>
                <th scope="row">{voce.etichetta}</th>
                <td>{voce.letti}{voce.errori ? ` (${voce.errori} non leggibili)` : ''}</td>
                <td>{voce.da_leggere}</td>
                <td>{voce.ultima_lettura ? formatDateTimeIt(voce.ultima_lettura, voce.ultima_lettura) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <small>Aggiornato {sintesi.aggiornato_il ? formatDateTimeIt(sintesi.aggiornato_il, sintesi.aggiornato_il) : 'n.d.'}: i motori leggono solo ciò che è nuovo o cambiato.</small>
    </details>
  )
}
