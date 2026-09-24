/**
 * La selezione dentro il foglio della revisione, in posizioni del testo.
 *
 * Il browser la dà come nodi e scarti dentro i nodi, e i nodi cambiano a ogni
 * ridisegno dei tratti. Il modello ragiona in caratteri dall'inizio del
 * pezzo: e' la sola misura che sopravvive al ridisegno, e con la quale si
 * rimette la selezione dov'era.
 */
import { useEffect, useState } from 'react'

export type SelezioneOcr = { blockId: string; inizio: number; fine: number }

/** L'attributo con cui ogni pezzo scrivibile dice di chi e'. */
export const ATTRIBUTO_BLOCCO = 'data-ocr-blocco'

function pezzoDi(nodo: Node | null): HTMLElement | null {
  const elemento = nodo instanceof HTMLElement ? nodo : nodo?.parentElement ?? null
  return elemento?.closest<HTMLElement>(`[${ATTRIBUTO_BLOCCO}]`) ?? null
}

function posizione(radice: HTMLElement, nodo: Node, scarto: number): number {
  const intervallo = document.createRange()
  intervallo.selectNodeContents(radice)
  intervallo.setEnd(nodo, scarto)
  return intervallo.toString().length
}

/** Inizio e fine della selezione dentro `radice`, se la selezione e' tutta li'. */
export function selezioneDentro(radice: HTMLElement): { inizio: number; fine: number } | null {
  const selezione = window.getSelection()
  if (!selezione || !selezione.rangeCount) return null
  const { anchorNode, focusNode, anchorOffset, focusOffset } = selezione
  if (!anchorNode || !focusNode || !radice.contains(anchorNode) || !radice.contains(focusNode)) return null
  const a = posizione(radice, anchorNode, anchorOffset)
  const b = posizione(radice, focusNode, focusOffset)
  return { inizio: Math.min(a, b), fine: Math.max(a, b) }
}

function puntoA(radice: HTMLElement, carattere: number): [Node, number] {
  const passi = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT)
  let resto = carattere
  let ultimo: Text | null = null
  for (let nodo = passi.nextNode() as Text | null; nodo; nodo = passi.nextNode() as Text | null) {
    if (resto <= nodo.length) return [nodo, resto]
    resto -= nodo.length
    ultimo = nodo
  }
  return ultimo ? [ultimo, ultimo.length] : [radice, 0]
}

/** Rimette la selezione fra due posizioni del testo, dopo un ridisegno. */
export function ripristinaSelezione(radice: HTMLElement, inizio: number, fine: number): void {
  const selezione = window.getSelection()
  if (!selezione) return
  const intervallo = document.createRange()
  intervallo.setStart(...puntoA(radice, inizio))
  intervallo.setEnd(...puntoA(radice, fine))
  selezione.removeAllRanges()
  selezione.addRange(intervallo)
}

/**
 * La selezione corrente del foglio.
 *
 * Quando si passa alla barra — il selettore del colore prende il fuoco — la
 * selezione del testo sparisce: qui resta quella di prima, perche' il colore
 * e' per quella. Si azzera solo se si va altrove.
 */
export function useSelezioneOcr(barra: string): SelezioneOcr | null {
  const [corrente, setCorrente] = useState<SelezioneOcr | null>(null)
  useEffect(() => {
    const aggiorna = () => {
      const selezione = window.getSelection()
      const radice = pezzoDi(selezione?.anchorNode ?? null)
      const nuova = radice && radice === pezzoDi(selezione?.focusNode ?? null) ? selezioneDentro(radice) : null
      if (!nuova || !radice) {
        if (!document.activeElement?.closest(barra)) setCorrente(null)
        return
      }
      const blockId = radice.getAttribute(ATTRIBUTO_BLOCCO) || ''
      setCorrente((prima) => (
        prima && prima.blockId === blockId && prima.inizio === nuova.inizio && prima.fine === nuova.fine
          ? prima
          : { blockId, ...nuova }
      ))
    }
    document.addEventListener('selectionchange', aggiorna)
    return () => document.removeEventListener('selectionchange', aggiorna)
  }, [barra])
  return corrente
}
