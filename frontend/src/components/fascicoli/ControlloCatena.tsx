import { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { avvisiDaMostrare, primaLettera, statoDelControllo, type ControlloCatenaPayload } from './controlloCatena'
import './controlloCatena.css'

// Gli avvisi del guardiano della catena: che cosa non torna fra modello della causa, scadenziario, agenda, quadro e
// bozze, e perché. Le incoerenze che il software ripara da solo non compaiono: restano nel registro dei controlli.
export function ControlloCatena({ fascicoloId, aggiornamento }: { fascicoloId: string; aggiornamento?: string }) {
  const [payload, setPayload] = useState<ControlloCatenaPayload | null>(null)
  useEffect(() => {
    if (!fascicoloId) return undefined
    const controller = new AbortController()
    fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/guardiano-catena`, { signal: controller.signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      .then((response) => (response.ok ? response.json() : null))
      .then((dati: ControlloCatenaPayload | null) => { if (!controller.signal.aborted) setPayload(dati) })
      .catch(() => { if (!controller.signal.aborted) setPayload(null) })
    return () => controller.abort()
  }, [fascicoloId, aggiornamento])
  const avvisi = avvisiDaMostrare(payload)
  const stato = statoDelControllo(payload)
  if (!avvisi.length && !stato) return null
  return (
    <section className="iu-controllo-catena" aria-label="Controllo della catena del fascicolo">
      {avvisi.length ? (
        <>
          <h4><AlertTriangle size={15}/> Da verificare nel fascicolo</h4>
          <ul>
            {avvisi.map((avviso) => (
              <li key={`${avviso.codice}-${avviso.descrizione}`}>
                <strong>{primaLettera(avviso.descrizione)}.</strong> {primaLettera(avviso.perche)}{avviso.norma ? ` (${avviso.norma})` : ''}.
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {stato ? <p className="iu-controllo-catena__stato"><RefreshCw size={13}/> {stato}</p> : null}
    </section>
  )
}

export default ControlloCatena
