import { CheckCircle2, XCircle } from 'lucide-react'
import type { VerificaRicevuta } from './types'

/** Confronto fra la ricevuta di accettazione del PDP e il deposito preparato in IUSENTRA. */
export function VerificaRicevutaPanel({ verifica }: { verifica?: VerificaRicevuta }) {
  if (!verifica?.messaggio) return null
  const tutto = verifica.corrispondenti === verifica.totale
  return (
    <div className="iu-pdp-verifica">
      <p className={tutto ? 'iu-pdp-ok' : 'iu-pdp-avviso'}>{verifica.messaggio}</p>
      {verifica.voci?.length ? (
        <ul>
          {verifica.voci.map((v) => (
            <li key={v.campo} className={v.ok ? 'is-ok' : 'is-diverso'}>
              {v.ok ? <CheckCircle2 size={14} aria-label="corrisponde"/> : <XCircle size={14} aria-label="non corrisponde"/>}
              <span className="iu-pdp-verifica__campo">{v.etichetta}</span>
              <span>{v.letto}{!v.ok ? <em> · atteso {v.atteso}</em> : null}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
