import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import type { Deposito } from './types'

const ICONE = { errore: XCircle, avviso: AlertTriangle, ok: CheckCircle2, info: Info }
const ORDINE = { errore: 0, avviso: 1, ok: 2, info: 3 }

/** L'esito dei controlli, dagli errori che bloccano il PDP alle semplici informazioni. */
export function EsitoControlli({ controlli }: { controlli: Deposito['controlli'] }) {
  const esiti = [...(controlli.esiti || [])].sort((a, b) => ORDINE[a.livello] - ORDINE[b.livello])
  return (
    <div className="iu-pdp-controlli">
      <p className={controlli.pronto ? 'iu-pdp-ok' : 'iu-pdp-errore'}>
        {controlli.pronto
          ? `Pronto per il PDP${controlli.avvisi ? ` · ${controlli.avvisi} avvisi da guardare` : ''}.`
          : `${controlli.errori} ${controlli.errori === 1 ? 'problema blocca' : 'problemi bloccano'} il deposito: il PDP lo rifiuterebbe.`}
      </p>
      <ul>
        {esiti.map((e, i) => {
          const Icona = ICONE[e.livello] || Info
          return (
            <li key={`${e.codice}-${i}`} className={`is-${e.livello}`}>
              <Icona size={14}/> <span>{e.messaggio}</span>{e.file ? <small>{e.file}</small> : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
