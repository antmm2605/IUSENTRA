/**
 * Il foglio della revisione come la pagina del documento: A4, con i margini
 * che il PDF aveva.
 *
 * Rileggere un testo che va a capo in punti diversi dall'originale vuol dire
 * perdere il segno a ogni riga. Con la stessa larghezza utile, lo stesso
 * carattere e lo stesso corpo, le righe del foglio cadono dove cadevano sulla
 * pagina: si scorre il foglio accanto all'immagine e le righe si corrispondono.
 *
 * I margini non si inventano: si leggono sulla pagina, da dove comincia e dove
 * finisce il testo. Le misure dei riquadri sono nelle unita' dell'immagine
 * della pagina; qui diventano millimetri di un A4.
 */
import type { CSSProperties } from 'react'
import type { OcrBlock } from './ocrBlocks'

/** Misure della pagina nelle stesse unita' dei riquadri dei blocchi. */
export type GeometriaPagina = { numero: number; larghezza: number; altezza: number }

/** Margini in millimetri. */
export type MarginiPagina = { alto: number; destro: number; basso: number; sinistro: number }

export const A4_MM = { larghezza: 210, altezza: 297 }

/** Quando la pagina non si puo' misurare (una foto senza anteprima): i margini di un atto. */
export const MARGINI_PREDEFINITI: MarginiPagina = { alto: 25, destro: 20, basso: 25, sinistro: 25 }

const MARGINE_MINIMO = 5
const MARGINE_MASSIMO = 45

function limita(valore: number): number {
  return Math.round(Math.min(MARGINE_MASSIMO, Math.max(MARGINE_MINIMO, valore)) * 10) / 10
}

/**
 * I margini della pagina, misurati sul testo.
 *
 * Il numero di pagina non conta: sta fuori dalla gabbia del testo, spesso a
 * pie' di pagina, e allargherebbe il margine basso di tutto l'atto.
 */
export function marginiDellaPagina(blocchi: OcrBlock[], geometria?: GeometriaPagina): MarginiPagina {
  const utili = blocchi.filter((blocco) => blocco.kind !== 'numero_pagina' && blocco.box)
  if (!geometria || geometria.larghezza <= 0 || geometria.altezza <= 0 || !utili.length) return MARGINI_PREDEFINITI
  const mmX = A4_MM.larghezza / geometria.larghezza
  const mmY = A4_MM.altezza / geometria.altezza
  const riquadri = utili.map((blocco) => blocco.box as [number, number, number, number])
  const sinistra = Math.min(...riquadri.map((riquadro) => riquadro[0]))
  const alto = Math.min(...riquadri.map((riquadro) => riquadro[1]))
  const destra = Math.max(...riquadri.map((riquadro) => riquadro[2]))
  const basso = Math.max(...riquadri.map((riquadro) => riquadro[3]))
  return {
    alto: limita(alto * mmY),
    destro: limita((geometria.larghezza - destra) * mmX),
    basso: limita((geometria.altezza - basso) * mmY),
    sinistro: limita(sinistra * mmX),
  }
}

/** I blocchi raggruppati per pagina, nell'ordine in cui arrivano. */
export function pagineDelFoglio(blocchi: OcrBlock[]): { numero: number; blocchi: OcrBlock[] }[] {
  const pagine: { numero: number; blocchi: OcrBlock[] }[] = []
  for (const blocco of blocchi) {
    const ultima = pagine[pagine.length - 1]
    if (ultima && ultima.numero === blocco.page) ultima.blocchi.push(blocco)
    else pagine.push({ numero: blocco.page, blocchi: [blocco] })
  }
  return pagine
}

function mm(valore: number): string {
  return `${Math.round(valore * 100) / 100}mm`
}

/** Il passo di riga piu' comune della pagina: vale per le parti di una riga sola. */
function passoTipico(blocchi: OcrBlock[]): number {
  const passi = blocchi.map((blocco) => blocco.righe?.interlinea || 0).filter((passo) => passo > 0).sort((a, b) => a - b)
  return passi.length ? passi[Math.floor(passi.length / 2)] : 0
}

/**
 * Dove sta ogni parte sulla pagina: stessa interlinea, stessa distanza dalla
 * parte sopra, stessi rientri del PDF.
 *
 * Il foglio scorre come un documento (le parti restano una sotto l'altra, e
 * correggendo il testo si allungano), ma gli spazi vengono dalla pagina: e'
 * cosi' che una riga del foglio sta all'altezza della stessa riga dell'immagine.
 * Una parte senza misure prende quelle della pagina; senza la pagina, niente.
 */
export function disposizioniDellaPagina(blocchi: OcrBlock[], geometria?: GeometriaPagina): (CSSProperties | undefined)[] {
  const utili = blocchi.filter((blocco) => blocco.kind !== 'numero_pagina' && blocco.box)
  if (!geometria || geometria.larghezza <= 0 || geometria.altezza <= 0 || !utili.length) return blocchi.map(() => undefined)
  const mmX = A4_MM.larghezza / geometria.larghezza
  const mmY = A4_MM.altezza / geometria.altezza
  const sinistra = Math.min(...utili.map((blocco) => blocco.box![0]))
  const destra = Math.max(...utili.map((blocco) => blocco.box![2]))
  const tipico = passoTipico(blocchi)
  let sopra: OcrBlock | null = null
  return blocchi.map((blocco) => {
    const stile: Record<string, string> = {}
    const passo = blocco.righe?.interlinea || tipico
    if (passo > 0) stile['--iu-ocr-interlinea'] = mm(passo * mmY)
    if (!blocco.box) return stile as CSSProperties
    const [x0, y0, x1] = blocco.box
    if (sopra?.box) {
      // Sotto l'ultima riga il foglio lascia un'interlinea intera, la pagina
      // solo l'altezza delle lettere: la differenza si toglie dallo spazio.
      const passoSopra = sopra.righe?.interlinea || tipico
      const lettere = sopra.righe?.altezza || 0
      const correzione = passoSopra > 0 && lettere > 0 ? lettere - passoSopra : 0
      const distanza = (y0 - sopra.box[3] + correzione) * mmY
      if (Math.abs(distanza) > 0.3) stile.marginTop = mm(Math.min(60, Math.max(-3, distanza)))
    }
    const alline = blocco.format.allineamento
    if ((blocco.kind === 'paragrafo' || blocco.kind === 'titolo') && (alline === 'sinistra' || alline === 'giustificato')) {
      const rientro = blocco.righe?.rientro || 0
      const aSinistra = (x0 - sinistra + Math.max(0, -rientro)) * mmX
      if (aSinistra > 0.5) stile.marginLeft = mm(aSinistra)
      if (Math.abs(rientro * mmX) > 0.5) stile.textIndent = mm(rientro * mmX)
      if (alline === 'giustificato' && (destra - x1) * mmX > 0.5) stile.marginRight = mm((destra - x1) * mmX)
    }
    // Piu' righe non giustificate (intestazioni centrate, indirizzi, firme):
    // gli a capo li ha messi l'autore. La parte resta larga quanto la riga piu'
    // lunga della pagina, cosi' le righe vanno a capo negli stessi punti.
    const lettere = blocco.righe?.altezza || 0
    const piuRighe = lettere > 0 && blocco.box[3] - y0 > lettere * 1.6
    if ((blocco.kind === 'paragrafo' || blocco.kind === 'titolo') && alline !== 'giustificato' && piuRighe) {
      stile.maxWidth = mm((x1 - x0) * mmX + 1.5)
      if (alline === 'centro') Object.assign(stile, { marginLeft: 'auto', marginRight: 'auto' })
      if (alline === 'destra') stile.marginLeft = 'auto'
    }
    sopra = blocco
    return stile as CSSProperties
  })
}
