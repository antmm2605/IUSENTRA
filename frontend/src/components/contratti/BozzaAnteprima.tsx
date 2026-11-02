import { Fragment } from 'react'
import type { Bozza } from '../../contrattiData'

function ConSegnaposti({ testo }: { testo: string }) {
  const pezzi = testo.split(/(\[[^\]]+\])/g)
  return <>{pezzi.map((pezzo, indice) => (pezzo.startsWith('[') && pezzo.endsWith(']') ? <mark key={indice}>{pezzo}</mark> : <Fragment key={indice}>{pezzo}</Fragment>))}</>
}

export function BozzaAnteprima({ bozza }: { bozza: Bozza | null }) {
  if (!bozza) return <p className="iu-ctr-nota">Bozza non disponibile.</p>
  const premesse = bozza.premesse.filter((p) => p.trim())
  return (
    <article className="iu-ctr-bozza" aria-label="Anteprima della bozza">
      <h3>{bozza.titolo}</h3>
      <p>Tra</p>
      {bozza.comparenti.map((c, indice) => (
        <Fragment key={c.ruolo}>
          <p><ConSegnaposti testo={c.testo + (indice === 0 ? ';' : '.')} /></p>
          {indice === 0 ? <p>e</p> : null}
        </Fragment>
      ))}
      {premesse.length ? (
        <>
          <p><strong>Premesso che</strong></p>
          <ul>{premesse.map((p, i) => <li key={i}>{p};</li>)}</ul>
          <p>tutto ciò premesso, che costituisce parte integrante del contratto, si conviene e si stipula quanto segue.</p>
        </>
      ) : <p>si conviene e si stipula quanto segue.</p>}
      {bozza.articoli.map((a) => (
        <section key={a.chiave} className={a.da_completare ? 'is-da-completare' : ''}>
          <h4>Art. {a.numero} – {a.titolo} <small>{a.norma}</small></h4>
          <p><ConSegnaposti testo={a.testo} /></p>
        </section>
      ))}
      {bozza.allegati.filter((a) => a.trim()).length ? (
        <>
          <h4>Allegati</h4>
          <ol>{bozza.allegati.filter((a) => a.trim()).map((a, i) => <li key={i}>{a}</li>)}</ol>
        </>
      ) : null}
      <p><ConSegnaposti testo={bozza.luogo_data} /></p>
      <div className="iu-ctr-firme">{bozza.firme.map((f) => <div key={f}><span>{f}</span><span className="iu-ctr-linea" /></div>)}</div>
      {bozza.approvazione_specifica ? <p className="iu-ctr-nota">Seguono le sottoscrizioni per specifica approvazione ai sensi degli artt. 1341 e 1342 c.c.</p> : null}
    </article>
  )
}
