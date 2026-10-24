import { useState } from 'react'
import type { OpenGADecision } from '../opengaSearch'
import { Button } from '../ui/Button'

export function OpenGAOfficialLookup({ decision }: { decision: OpenGADecision }) {
  const [message, setMessage] = useState('')
  const number = /^\\d{9}$/.test(decision.numero_sentenza) && decision.numero_sentenza.startsWith(String(decision.anno_sentenza))
    ? decision.numero_sentenza.slice(String(decision.anno_sentenza).length).replace(/^0+(?=\\d)/, '')
    : decision.numero_sentenza
  const reference = decision.organo_giudicante + ' — provvedimento ' + decision.numero_sentenza + '/' + decision.anno_sentenza + ' — ricorso ' + decision.numero_ricorso
  async function copyReference() {
    try {
      await navigator.clipboard.writeText(reference)
      setMessage('Estremi copiati.')
    } catch {
      setMessage('Copia non disponibile: puoi selezionare gli estremi qui sotto.')
    }
  }
  return <details className="iu-openga-official-lookup">
    <summary>Trova il testo sul sito ufficiale</summary>
    <p>Il testo non è incluso in questo risultato. Apri il modulo ufficiale e cerca con questi dati:</p>
    <dl className="iu-legal-meta">
      <div><dt>Sede</dt><dd>{decision.organo_giudicante}</dd></div>
      <div><dt>Anno del provvedimento</dt><dd>{decision.anno_sentenza}</dd></div>
      <div><dt>Numero del provvedimento</dt><dd>{number || decision.numero_sentenza}</dd></div>
      <div><dt>Numero di ricorso</dt><dd>{decision.numero_ricorso}</dd></div>
    </dl>
    <p>{reference}</p>
    <div className="iu-od-action-row">
      <Button type="button" onClick={() => void copyReference()}>Copia gli estremi</Button>
      <a href="https://www.giustizia-amministrativa.it/dcsnprr" target="_blank" rel="noopener noreferrer">Apri il modulo ufficiale</a>
    </div>
    <p role="status">{message}</p>
    <p>Il modulo si apre in una nuova scheda. Il collegamento diretto al documento non è disponibile nel catalogo.</p>
  </details>
}
