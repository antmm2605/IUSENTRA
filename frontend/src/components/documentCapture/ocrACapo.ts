/**
 * Gli a capo del documento nel foglio della revisione.
 *
 * Il riconoscimento dice dove, nel testo di un blocco, cominciava ogni riga
 * della pagina. Il foglio li rispetta: le righe cadono dove cadevano
 * sull'originale anche quando il carattere del browser non e' identico a
 * quello del PDF, e il riscontro con l'immagine si fa riga per riga.
 *
 * Gli a capo sono solo come si vede il testo: ogni riga e' un contenitore a
 * se', e il testo (textContent) resta quello del blocco, lettera per lettera.
 * Valgono finche' il testo e' quello letto: appena lo si corregge il blocco
 * torna a capo da solo, come un qualunque capoverso.
 */
import type { OcrBlock } from './ocrBlocks'
import type { OcrTratto } from './ocrTratti'

/** Posizioni (nel testo del blocco) dove comincia una riga del documento. */
export function aCapoValidi(block: OcrBlock): number[] {
  const aCapo = block.aCapo
  if (!aCapo || aCapo.testo !== block.text || block.kind === 'tabella') return []
  return aCapo.posizioni.filter((posizione) => posizione > 0 && posizione < block.text.length)
}

type Pezzo = { testo: string; tratto?: OcrTratto }

/** I pezzi del testo (tratti o testo intero) divisi nelle righe del documento. */
export function righeDeiPezzi(pezzi: Pezzo[], tagli: number[]): Pezzo[][] {
  const righe: Pezzo[][] = [[]]
  let inizio = 0
  let prossimo = 0
  for (const pezzo of pezzi) {
    let resto = pezzo.testo
    let posizione = inizio
    while (prossimo < tagli.length && tagli[prossimo] < posizione + resto.length) {
      const taglio = tagli[prossimo] - posizione
      if (taglio > 0) righe[righe.length - 1].push({ ...pezzo, testo: resto.slice(0, taglio) })
      righe.push([])
      resto = resto.slice(taglio)
      posizione = tagli[prossimo]
      prossimo += 1
    }
    if (resto) righe[righe.length - 1].push({ ...pezzo, testo: resto })
    inizio += pezzo.testo.length
  }
  return righe.filter((riga, indice) => riga.length || indice === 0)
}

/**
 * I nodi del testo di un blocco, con gli a capo del documento.
 *
 * Ogni riga del documento e' una riga del foglio. Le righe piene (quelle che
 * sulla pagina arrivano al margine destro) si giustificano, anche l'ultima di
 * un capoverso che continua nella pagina dopo; le altre restano come sono.
 * Il segno di una voce d'elenco sta nella sporgenza, come la tabulazione di
 * Word: il testo della prima riga comincia dove cominciano le altre.
 */
export function nodiDelTesto(block: OcrBlock, nodoDelTratto: (tratto: OcrTratto) => Node): Node[] {
  const pezzi: Pezzo[] = block.tratti?.length
    ? block.tratti.map((tratto) => ({ testo: tratto.testo, tratto }))
    : [{ testo: block.text }]
  const corpoDelBlocco = block.format.corpo
  const nodo = (pezzo: Pezzo): Node => {
    if (!pezzo.tratto) return document.createTextNode(pezzo.testo)
    const creato = nodoDelTratto({ ...pezzo.tratto, testo: pezzo.testo })
    // un corpo diverso da quello del blocco si scrive in proporzione: se si
    // cambia il corpo del blocco dalla barra, la riga piu' grande resta tale
    const corpo = pezzo.tratto.corpo
    if (corpo && corpoDelBlocco && Math.abs(corpo - corpoDelBlocco) >= 0.5 && creato instanceof HTMLElement) {
      creato.style.fontSize = `${Math.round((corpo / corpoDelBlocco) * 1000) / 1000}em`
      creato.classList.add('ha-corpo-proprio')
    }
    return creato
  }
  const tagli = aCapoValidi(block)
  const testoSegno = block.kind === 'elenco' ? /^\S+\s+/.exec(block.text)?.[0] : undefined
  if (!tagli.length && !testoSegno) return pezzi.map(nodo)
  const righe = righeDeiPezzi(pezzi, tagli)
  let segno: HTMLElement | null = null
  if (testoSegno && testoSegno.length < (tagli[0] ?? block.text.length)) {
    const [testa, coda] = righeDeiPezzi(righe[0], [testoSegno.length])
    segno = document.createElement('span')
    segno.className = 'iu-ocr-segno'
    segno.append(...testa.map(nodo))
    righe[0] = coda || []
  }
  if (!tagli.length) return [...(segno ? [segno] : []), ...righe[0].map(nodo)]
  const giustificato = block.format.allineamento === 'giustificato'
  const aSinistra = giustificato || block.format.allineamento === 'sinistra'
  const piene = block.aCapo?.piene?.length === righe.length ? block.aCapo.piene : undefined
  return righe.map((riga, indice) => {
    const contenitore = document.createElement('span')
    const ultima = indice === righe.length - 1
    const piena = aSinistra && (piene ? piene[indice] || (giustificato && !ultima) : giustificato && !ultima)
    contenitore.className = piena ? 'iu-ocr-riga is-piena' : 'iu-ocr-riga'
    if (indice === 0 && segno) contenitore.append(segno)
    contenitore.append(...riga.map(nodo))
    return contenitore
  })
}
