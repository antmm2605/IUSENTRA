import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { leggiNormativa } from './normativaApi'
import { NormativaRicerca } from './NormativaRicerca'
import { NormativaVoceCard } from './NormativaVoceCard'
import type { NormativaFascicolo } from './types'

/** Contenuto del pannello «Normativa»: contesto della pratica, tre gruppi di norme, ricerca. */
export function FascicoloNormativaPanel({ fascicoloId }: { fascicoloId: string }) {
  const [dati, setDati] = useState<NormativaFascicolo | null>(null)
  const [errore, setErrore] = useState('')
  const [tentativo, setTentativo] = useState(0)

  useEffect(() => {
    const controllo = new AbortController()
    setErrore('')
    leggiNormativa(fascicoloId, controllo.signal)
      .then((data) => setDati(data.normativa))
      .catch((error) => {
        if (controllo.signal.aborted) return
        const status = (error as { status?: number })?.status
        setErrore(status === 403 ? 'Non hai il permesso per consultare questo fascicolo.' : status === 404 ? 'Fascicolo non trovato.' : 'Normativa del fascicolo non disponibile: riprova fra poco.')
      })
    return () => controllo.abort()
  }, [fascicoloId, tentativo])

  if (errore) return (
    <div className="iu-fas-normativa">
      <p className="iu-fas-normativa__nota" role="alert">{errore}</p>
      <button type="button" className="iu-fas-normativa__espandi" onClick={() => setTentativo((n) => n + 1)}><RefreshCw size={13} aria-hidden="true"/> Riprova</button>
    </div>
  )
  if (!dati) return <div className="iu-fas-normativa"><p className="iu-fas-normativa__nota" role="status">Raccolta delle norme del fascicolo…</p></div>
  const { contesto } = dati
  const dettagli = [contesto.rito, contesto.deposito, contesto.ufficio].filter(Boolean)
  return (
    <div className="iu-fas-normativa">
      <p className="iu-fas-normativa__intro">
        Le norme di questa pratica, prese dai registri ufficiali del software con la data di consultazione. {dettagli.length ? <b>{dettagli.join(' · ')}</b> : null}
      </p>
      <nav className="iu-fas-normativa__indice" aria-label="Gruppi di norme">
        {/* Pulsanti, non ancore: l'indirizzo del fascicolo (#sezione) resta quello della pagina. */}
        {dati.gruppi.map((gruppo) => (
          <button type="button" key={gruppo.id} onClick={() => document.getElementById(`normativa-${gruppo.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
            {gruppo.titolo} <b>{gruppo.voci.length}</b>
          </button>
        ))}
      </nav>
      {dati.gruppi.map((gruppo) => (
        <section key={gruppo.id} id={`normativa-${gruppo.id}`} className="iu-fas-normativa__gruppo" aria-labelledby={`normativa-${gruppo.id}-titolo`}>
          <header>
            <h3 id={`normativa-${gruppo.id}-titolo`}>{gruppo.titolo}</h3>
            <span>{gruppo.descrizione}</span>
          </header>
          {gruppo.voci.length
            ? <ul className="iu-fas-normativa__voci">{gruppo.voci.map((voce) => <NormativaVoceCard key={voce.id} voce={voce} fascicoloId={fascicoloId}/>)}</ul>
            : <p className="iu-fas-normativa__nota">{gruppo.vuoto}</p>}
        </section>
      ))}
      <NormativaRicerca materie={dati.materie}/>
    </div>
  )
}
