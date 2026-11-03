import { Download } from 'lucide-react'
import { Badge } from './dashboard'

// Provvedimenti notificati dallo studio: la copia informatica originale si scarica dal Portale dei Servizi
// Telematici con l'accesso dell'avvocato (CNS/CIE/SPID); il gestionale prepara gli estremi e segue lo stato.
export type CopiaPst = {
  chiave: string
  fascicoloId: string
  titolo: string
  tipoAtto: string
  ufficio: string
  registro: string
  ruolo: string
  url: string
  stato: 'da_scaricare' | 'scaricata'
  statoEtichetta: string
  avvertenza: string
}

export function copiePstDaPayload(valore: unknown): CopiaPst[] {
  return Array.isArray(valore) ? valore.filter((voce): voce is CopiaPst => Boolean(voce && typeof voce === 'object' && 'chiave' in voce)) : []
}

export function CopiePstPanel({ copie, conFascicolo = false }: { copie: CopiaPst[]; conFascicolo?: boolean }) {
  if (!copie.length) return null
  return (
    <div className="iu-fas-letture__parti" aria-label="Copie originali da scaricare dal PST">
      <h5><Download size={14}/> Copia originale da scaricare dal PST ({copie.length})</h5>
      <ul>
        {copie.map((copia) => (
          <li key={copia.chiave} className={copia.stato === 'scaricata' ? 'is-success' : 'is-warning'}>
            <div className="iu-fas-letture__parte-testo">
              <Badge tone={copia.stato === 'scaricata' ? 'success' : 'warning'}>{copia.statoEtichetta}</Badge>
              <b>{copia.tipoAtto}</b>
              <span>{[copia.ufficio, copia.registro, copia.ruolo ? `R.G. ${copia.ruolo}` : ''].filter(Boolean).join(' · ')}</span>
              {conFascicolo ? <small><a href={`/fascicoli/${encodeURIComponent(copia.fascicoloId)}`}>Apri il fascicolo</a></small> : null}
              <small><a href={copia.url} target="_blank" rel="noreferrer">Apri il Portale dei Servizi Telematici</a></small>
              <small>{copia.avvertenza}</small>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
