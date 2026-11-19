import { FilePenLine, FileText } from 'lucide-react'
import { Badge } from '../dashboard'
import { etichettaStatoBozza, riassuntoDaCompletare, type BozzaPasso } from './bozzePassi'

// «Bozza pronta — apri»: porta all'editor del testo della bozza; «Vedi il PDF» apre il documento del fascicolo.
export function BozzaPassoLink({ bozza }: { bozza: BozzaPasso }) {
  const stato = etichettaStatoBozza(bozza)
  return (
    <div className="iu-fas-lettura__bozza">
      <a className="iu-fas-lettura__bozza-apri" href={bozza.apri} title={`Apri nell'editor: ${bozza.titolo}`}>
        <FilePenLine size={13}/> {bozza.stato === 'pronta' ? 'Bozza pronta — apri' : 'Apri la bozza'}
      </a>
      {bozza.pdf ? <a className="iu-fas-lettura__bozza-apri" href={bozza.pdf} target="_blank" rel="noopener noreferrer" title={`Il PDF nel fascicolo: ${bozza.titolo}`}><FileText size={13}/> Vedi il PDF</a> : null}
      <Badge tone={stato.tono}>{stato.testo}</Badge>
      <small>{bozza.titolo} · modello «{bozza.modelloTitolo}» · {riassuntoDaCompletare(bozza)}</small>
      {bozza.daCompletare.length ? (
        <details>
          <summary>Dati da completare</summary>
          <ul>{bozza.daCompletare.map((voce) => <li key={voce}>{voce}</li>)}</ul>
        </details>
      ) : null}
    </div>
  )
}
