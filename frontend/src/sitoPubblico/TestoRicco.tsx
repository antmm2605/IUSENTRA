import { Fragment, createElement, type ReactNode } from 'react'

/**
 * Testo dei contenuti del sito con le sole formattazioni ammesse dall'editor (em, u, sup, sub),
 * come `rich_inline_text` di pct/studio_site.py: tutto il resto è testo, mai HTML interpretato.
 */
const ETICHETTA = /(<\/?(?:em|u|sup|sub)>)/i
const AMMESSE = new Set(['em', 'u', 'sup', 'sub'])

type Nodo = { tag: string; figli: (Nodo | string)[] }

function albero(testo: string): Nodo {
  const radice: Nodo = { tag: '', figli: [] }
  const pila: Nodo[] = [radice]
  for (const parte of testo.split(ETICHETTA)) {
    if (!parte) continue
    const etichetta = /^<(\/?)(em|u|sup|sub)>$/i.exec(parte)
    if (!etichetta) {
      pila[pila.length - 1].figli.push(parte)
      continue
    }
    const nome = etichetta[2].toLowerCase()
    if (etichetta[1]) {
      // Chiusura: vale solo se chiude un'etichetta aperta; altrimenti si ignora.
      const indice = pila.map((nodo) => nodo.tag).lastIndexOf(nome)
      if (indice > 0) pila.length = indice
    } else if (AMMESSE.has(nome)) {
      const nodo: Nodo = { tag: nome, figli: [] }
      pila[pila.length - 1].figli.push(nodo)
      pila.push(nodo)
    }
  }
  return radice
}

function disegna(figli: (Nodo | string)[]): ReactNode[] {
  return figli.map((figlio, indice) => (typeof figlio === 'string'
    ? <Fragment key={indice}>{figlio}</Fragment>
    : createElement(figlio.tag, { key: indice }, ...disegna(figlio.figli))))
}

export function TestoRicco({ testo }: { testo?: string | null }) {
  return <>{disegna(albero(String(testo ?? '')).figli)}</>
}

/** Paragrafi separati da una riga vuota, righe con a capo (come `rich_paragraphs`). */
export function ParagrafiRicchi({ testo }: { testo?: string | null }) {
  const valore = String(testo ?? '').trim()
  if (!valore) return null
  return (
    <>
      {valore.split('\n\n').map((paragrafo, indice) => (
        <p key={indice}>
          {paragrafo.split(/\r?\n/).map((riga, numero) => (
            <Fragment key={numero}>{numero ? <br/> : null}<TestoRicco testo={riga}/></Fragment>
          ))}
        </p>
      ))}
    </>
  )
}
