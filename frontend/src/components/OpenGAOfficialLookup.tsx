import { useState } from 'react'
import { officialDecisionNumber, type OpenGADecision } from '../opengaSearch'
import { OpenGAOfficialDocument } from './OpenGAOfficialDocument'
import { Button } from '../ui/Button'

export function OpenGAOfficialLookup({ decision }: { decision: OpenGADecision }) {
  const [message, setMessage] = useState('')
  const [opened, setOpened] = useState(false)
  const number = officialDecisionNumber(decision.numero_sentenza, decision.anno_sentenza)
  const reference = decision.organo_giudicante + ' — provvedimento ' + (number || decision.numero_sentenza) + '/' + decision.anno_sentenza + ' — ricorso ' + decision.numero_ricorso
  async function copyReference() {
    try {
      await navigator.clipboard.writeText(reference)
      setMessage('Estremi copiati.')
    } catch {
      setMessage('Copia non disponibile: puoi selezionare gli estremi qui sotto.')
    }
  }
  return <details className="iu-openga-official-lookup" onToggle={(event) => setOpened(event.currentTarget.open)}>
    <summary>Leggi il testo del provvedimento</summary>
    {opened && <OpenGAOfficialDocument decision={decision} />}
    <details><summary>Ricerca manuale sul portale ufficiale</summary>
    <p>Usa questi dati soltanto se vuoi cercare manualmente sul sito ufficiale:</p>
    <dl className="iu-legal-meta">
      <div><dt>Sede</dt><dd>{decision.organo_giudicante}</dd></div>
      <div><dt>Anno del provvedimento</dt><dd>{decision.anno_sentenza}</dd></div>
      <div><dt>Numero del provvedimento</dt><dd>{number || decision.numero_sentenza}</dd></div>
      <div><dt>Numero di ricorso</dt><dd>{decision.numero_ricorso}</dd></div>
    </dl>
    <p>{reference}</p>
    <div className="iu-od-action-row">
      <Button type="button" onClick={() => void copyReference()}>Copia i dati della ricerca</Button>
      <a href="https://www.giustizia-amministrativa.it/dcsnprr" target="_blank" rel="noopener noreferrer">Apri il modulo ufficiale</a>
    </div>
    <p role="status">{message}</p>
    <p>Questo comando apre il modulo di ricerca, non il documento. Per leggere il testo usa il lettore qui sopra.</p>
    </details>
  </details>
}
