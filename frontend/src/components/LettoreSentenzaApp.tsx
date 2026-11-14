import { useEffect, useState } from 'react'
import { leggiDocumento, percorsoInterno, urlEsternoSicuro, type DocumentoLettore } from './lettoreSentenzaDati'
import './LettoreSentenzaApp.css'

/**
 * Lettore dei provvedimenti (corpus dello studio, SentenzeWeb, traduzioni di servizio, testo ufficiale
 * acquisito da OpenGA). Sostituisce i lettori Jinja: ogni testo esterno è un nodo di testo React,
 * mai HTML interpretato; nessun dato del provvedimento è nella pagina, solo nel JSON no-store.
 */
export function LettoreSentenza({ documento }: { documento: DocumentoLettore }) {
  const indice = documento.blocchi.filter((blocco) => blocco.tipo === 'titolo' && blocco.ancora)
  const fonteUrl = urlEsternoSicuro(documento.fonteUrl)
  const originaleUrl = percorsoInterno(documento.originaleUrl)
  return (
    <main className="iu-lettore">
      <header className="iu-lettore__testata">
        <p className="iu-lettore__occhiello">{documento.occhiello}</p>
        <h1>{documento.titolo}</h1>
        {documento.righe.filter(Boolean).map((riga) => <p key={riga}>{riga}</p>)}
        <p className="iu-lettore__provenienza">{documento.provenienza}</p>
        {documento.fonteTesto ? <p>Fonte della versione conservata: <code>{documento.fonteTesto}</code></p> : null}
        {fonteUrl ? <p><a href={fonteUrl} target="_blank" rel="noopener noreferrer">Apri la fonte di questa versione ↗</a></p> : null}
        {documento.avvisi.map((avviso) => <p key={avviso} className="iu-lettore__avviso" role="note">{avviso}</p>)}
        <nav className="iu-lettore__azioni" aria-label="Azioni del lettore">
          {originaleUrl ? <a href={originaleUrl}>Leggi il testo originale</a> : null}
          {documento.testoSempliceUrl ? <a href={documento.testoSempliceUrl}>Apri testo semplice</a> : null}
          <button type="button" onClick={() => window.print()}>Stampa</button>
        </nav>
      </header>
      {indice.length ? (
        <nav className="iu-lettore__indice" aria-label="Sezioni del provvedimento">
          {indice.map((blocco) => <a key={blocco.ancora} href={`#${blocco.ancora}`}>{blocco.testo}</a>)}
        </nav>
      ) : null}
      {documento.parti?.length ? (
        <article className="iu-lettore__testo" aria-label="Traduzione con originale a confronto">
          {documento.parti.map((parte, indiceParte) => (
            <section key={indiceParte} className="iu-lettore__parte">
              <h2>Passaggio {indiceParte + 1}</h2>
              {parte.avviso ? <p className="iu-lettore__avviso" role="note">{parte.avviso}</p> : null}
              <div className="iu-lettore__colonne">
                <details open>
                  <summary>Originale ({documento.linguaOriginale || 'lingua non indicata'})</summary>
                  <p lang={documento.linguaOriginale || undefined}>{parte.originale}</p>
                </details>
                <section lang="it">
                  <h3>Traduzione italiana</h3>
                  <p>{parte.traduzione}</p>
                </section>
              </div>
            </section>
          ))}
        </article>
      ) : (
        <article className="iu-lettore__testo" aria-label="Testo del provvedimento">
          {documento.blocchi.map((blocco, indiceBlocco) => blocco.tipo === 'titolo'
            ? <h2 key={indiceBlocco} id={blocco.ancora || undefined}>{blocco.testo}</h2>
            : <p key={indiceBlocco}>{blocco.testo}</p>)}
        </article>
      )}
      <footer className="iu-lettore__piede">
        {documento.nota ? <p>{documento.nota}</p> : null}
        {documento.integrita.length ? (
          <details>
            <summary>Provenienza e integrità</summary>
            {documento.integrita.filter((voce) => voce.valore).map((voce) => <p key={voce.etichetta}>{voce.etichetta}: <code>{voce.valore}</code></p>)}
          </details>
        ) : null}
      </footer>
    </main>
  )
}

export default function LettoreSentenzaApp() {
  const [documento, setDocumento] = useState<DocumentoLettore | null>(null)
  const [errore, setErrore] = useState('')
  useEffect(() => {
    const controllo = new AbortController()
    leggiDocumento(controllo.signal)
      .then((dati) => { setDocumento(dati); document.title = `${dati.titolo} - IUSENTRA` })
      .catch((reason: unknown) => { if (!controllo.signal.aborted) setErrore(reason instanceof Error ? reason.message : 'Testo del provvedimento non disponibile.') })
    return () => controllo.abort()
  }, [])
  if (errore) return <main className="iu-lettore"><p className="iu-lettore__avviso" role="alert">{errore}</p></main>
  if (!documento) return <main className="iu-lettore" aria-busy="true"><p>Caricamento del testo del provvedimento…</p></main>
  return <LettoreSentenza documento={documento}/>
}
