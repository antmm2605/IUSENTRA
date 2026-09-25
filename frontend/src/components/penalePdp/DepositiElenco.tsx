import { useState } from 'react'
import { ChevronDown, ChevronRight, Plus } from 'lucide-react'
import { Badge } from '../dashboard'
import { DepositoDettaglio } from './DepositoDettaglio'
import { dataOra, type Quadro } from './types'

type Props = { fascicoloId: string; quadro: Quadro; aperto: string; onAggiorna: () => void; onNuovo: () => void }

/** I depositi del procedimento con lo stato del PDP (provv. DGSIA 11/07/2023 art. 7 co. 4). */
export function DepositiElenco({ fascicoloId, quadro, aperto, onAggiorna, onNuovo }: Props) {
  const [espanso, setEspanso] = useState(aperto)
  if (!quadro.depositi.length) {
    return (
      <div className="iu-pdp-vuoto">
        <p>Nessun deposito ancora. Preparane uno: IUSENTRA lo controlla e ti dà la scheda da copiare nel PDP.</p>
        <button type="button" onClick={onNuovo}><Plus size={14}/> Nuovo deposito</button>
      </div>
    )
  }
  return (
    <ul className="iu-pdp-depositi">
      {quadro.depositi.map((d) => {
        const aperta = espanso === d.id
        return (
          <li key={d.id} className={aperta ? 'is-aperto' : ''}>
            <button type="button" className="iu-pdp-deposito__testa" aria-expanded={aperta} onClick={() => setEspanso(aperta ? '' : d.id)}>
              {aperta ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}
              <span className="iu-pdp-deposito__atto">
                <strong>{d.attoNome}</strong>
                <small>{[d.ufficioEtichetta, d.registro, d.identificativo && `Invio ${d.identificativo}`, d.dataInvio && dataOra(d.dataInvio)].filter(Boolean).join(' · ')}</small>
              </span>
              <Badge tone={d.statoTono}>{d.statoEtichetta}</Badge>
            </button>
            {aperta ? <DepositoDettaglio fascicoloId={fascicoloId} quadro={quadro} deposito={d} onAggiorna={onAggiorna}/> : null}
          </li>
        )
      })}
    </ul>
  )
}
