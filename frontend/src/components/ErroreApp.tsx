import { ArrowLeft, Home, LogIn, SearchX, ShieldX } from 'lucide-react'
import './ErroreApp.css'

/**
 * Pagine d'errore 403 e 404 fuori dalla cornice dello studio (utenti collegati e non).
 * Codice, titolo e messaggio arrivano dal server (data-* della shell `errore_shell.html`).
 */
export default function ErroreApp() {
  const dataset = document.getElementById('errore-react-root')?.dataset ?? {}
  const codice = dataset.errore === '403' ? 403 : 404
  const titolo = dataset.titolo || (codice === 403 ? 'Accesso negato' : 'Pagina non trovata')
  const messaggio = dataset.messaggio || ''
  const autenticato = dataset.autenticato === '1'
  const Icona = codice === 403 ? ShieldX : SearchX
  const puoTornare = typeof window !== 'undefined' && window.history.length > 1
  return (
    <main className="iu-errore-pagina">
      <section className={`iu-errore-pagina__scheda iu-errore-pagina__scheda--${codice}`} aria-labelledby="errore-titolo">
        <span className="iu-errore-pagina__icona" aria-hidden="true"><Icona size={30}/></span>
        <p className="iu-errore-pagina__codice">Errore {codice}</p>
        <h1 id="errore-titolo">{titolo}</h1>
        {messaggio ? <p className="iu-errore-pagina__messaggio">{messaggio}</p> : null}
        <p className="iu-errore-pagina__indirizzo">Indirizzo richiesto: <code>{window.location.pathname}</code></p>
        <nav className="iu-errore-pagina__azioni" aria-label="Dove andare">
          {autenticato
            ? <a className="iu-errore-pagina__primario" href="/"><Home size={16}/>Torna alla panoramica</a>
            : <a className="iu-errore-pagina__primario" href={`/login?next=${encodeURIComponent(window.location.pathname)}`}><LogIn size={16}/>Accedi allo studio</a>}
          {puoTornare ? <button type="button" onClick={() => window.history.back()}><ArrowLeft size={16}/>Pagina precedente</button> : null}
        </nav>
      </section>
    </main>
  )
}
