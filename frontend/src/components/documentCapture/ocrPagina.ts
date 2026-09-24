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
