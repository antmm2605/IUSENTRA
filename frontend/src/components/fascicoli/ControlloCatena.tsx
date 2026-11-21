import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Link2, RefreshCw } from 'lucide-react'
import { anelliDaMostrare, avvisiDaMostrare, primaLettera, statoDelControllo, type ControlloCatenaPayload } from './controlloCatena'
import './controlloCatena.css'

// Il controllo della catena del fascicolo, sempre visibile sotto il quadro: l'esito anello per anello
// (letture → termini e udienze → prossimi passi → economia → quadro) e, quando qualcosa non torna, che cosa e perché.
// Le incoerenze che il software ripara da solo restano nel registro e si vedono come «riparato dal software».
export function ControlloCatena({ fascicoloId, aggiornamento }: { fascicoloId: string; aggiornamento?: string }) {
  const [payload, setPayload] = useState<ControlloCatenaPayload | null>(null)
  useEffect(() => {
    if (!fascicoloId) return undefined
    const controller = new AbortController()
    fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/guardiano-catena`, { signal: controller.signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      .then((response) => (response.ok ? response.json() : { ok: false }))
      .then((dati: ControlloCatenaPayload) => { if (!controller.signal.aborted) setPayload(dati) })
      .catch(() => { if (!controller.signal.aborted) setPayload({ ok: false }) })
    return () => controller.abort()
  }, [fascicoloId, aggiornamento])
  const avvisi = avvisiDaMostrare(payload)
  const anelli = anelliDaMostrare(payload)
  const daVerificare = avvisi.length > 0
  return (
    <section className={`iu-controllo-catena${daVerificare ? ' iu-controllo-catena--avvisi' : ''}`} aria-label="Controllo della catena del fascicolo" data-stato={payload?.stato || ''}>
      <h4>{daVerificare ? <AlertTriangle size={15}/> : <Link2 size={15}/>} Controllo della catena</h4>
      <p className="iu-controllo-catena__stato">{payload?.stato === 'in_aggiornamento' ? <RefreshCw size={13}/> : null}{statoDelControllo(payload)}</p>
      <ol className="iu-controllo-catena__anelli">
        {anelli.map((anello) => (
          <li key={anello.codice} className={`iu-controllo-catena__anello iu-controllo-catena__anello--${anello.esito}`} title={primaLettera(anello.descrizione)}>
            {anello.esito === 'verificato' || anello.esito === 'riparato' ? <CheckCircle2 size={13}/> : anello.esito === 'da_verificare' ? <AlertTriangle size={13}/> : null}
            <strong>{anello.nome}</strong>
            <span>{anello.etichetta}</span>
          </li>
        ))}
      </ol>
      {daVerificare ? (
        <ul className="iu-controllo-catena__avvisi">
          {avvisi.map((avviso) => (
            <li key={`${avviso.codice}-${avviso.descrizione}`}>
              <strong>{primaLettera(avviso.descrizione)}.</strong> {primaLettera(avviso.perche)}{avviso.norma ? ` (${avviso.norma})` : ''}.
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

export default ControlloCatena
