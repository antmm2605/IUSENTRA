import { formatDateTimeIt } from '../../formatting'
import { ActionButton } from './ActionButton'
import type { SourceCheck } from './types'

const labels: Record<string, string> = {
  da_controllare: 'Primo controllo delle fonti da eseguire',
  in_aggiornamento: 'Controllo delle fonti in corso',
  acquisizione_parziale: 'Controllo parziale, alcune fonti restano da leggere',
  fonte_non_raggiunta: 'Fonte non raggiunta, i dati precedenti sono conservati',
  da_aggiornare: 'Fonti da ricontrollare',
  fonti_acquisite: 'Fonti acquisite, canale di deposito da verificare',
}

export function ControlloFonti({ value, reload, busy }: { value: SourceCheck; reload: () => void; busy: boolean }) {
  const sources = [...new Map((value.fonti || []).map((source) => [source.url, source])).values()]
  return <details className="iu-mediazione-source-check">
    <summary>Controllo delle fonti: {labels[value.stato] || 'Verifica da completare'}</summary>
    <p>Il controllo confronta i collegamenti a moduli, istruzioni e contatti. Non modifica i documenti già salvati e non autorizza né esegue un deposito.</p>
    {value.ultimo_controllo ? <p>Ultimo controllo: {formatDateTimeIt(value.ultimo_controllo)}.</p> : null}
    {value.prossimo_controllo ? <p>Prossimo controllo previsto: {formatDateTimeIt(value.prossimo_controllo)}.</p> : null}
    {value.ultima_variazione ? <p>Variazione rilevata il {formatDateTimeIt(value.ultima_variazione)}. Le precedenti evidenze restano nello storico.</p> : null}
    {sources.length ? <ul>{sources.map((source) => <li key={source.url}>
      <a href={source.url} target="_blank" rel="noopener noreferrer">{source.url}</a>
      {source.status === 200 ? ' · fonte letta' : ' · risposta da verificare'}
    </li>)}</ul> : <p>Non risultano ancora pagine acquisite in questo controllo.</p>}
    {value.documentazione_api?.length ? <p>Sono stati trovati riferimenti a servizi applicativi: non sono ancora confermati come canali per il deposito.</p> : null}
    {value.problemi?.length ? <p>{value.problemi.length} verifiche non concluse. Nessun indirizzo incerto viene abilitato per l’invio.</p> : null}
    <ActionButton onClick={reload} disabled={busy} aria-busy={busy}>Rileggi stato delle fonti</ActionButton>
    <span role="status">{busy ? ' Lettura degli esiti in corso…' : ''}</span>
  </details>
}
