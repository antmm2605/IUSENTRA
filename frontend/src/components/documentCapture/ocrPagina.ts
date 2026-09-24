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
import { aCapoValidi } from './ocrACapo'

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
  // Il margine destro e' dove arrivano le righe giustificate: un timbro di
  // firma fuori dalla colonna non lo sposta.
  const giustificati = utili.filter((blocco) => blocco.format.allineamento === 'giustificato').map((blocco) => blocco.box![2]).sort((a, b) => a - b)
  const destra = giustificati.length ? giustificati[Math.floor(giustificati.length / 2)] : Math.max(...riquadri.map((riquadro) => riquadro[2]))
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
  // Le distanze orizzontali si misurano dalla gabbia del foglio (i margini
  // come li disegna il CSS), non dal testo: cosi' i due conti coincidono.
  const margini = marginiDellaPagina(blocchi, geometria)
  const gabbiaSinistra = margini.sinistro
  const gabbiaDestra = A4_MM.larghezza - margini.destro
  const tipico = passoTipico(blocchi)
  const sporgenze = blocchi.map((blocco) => (blocco.kind === 'elenco' ? -(blocco.righe?.rientro || 0) : 0)).filter((valore) => valore > 0).sort((a, b) => a - b)
  const sporgenzaTipica = sporgenze.length ? sporgenze[Math.floor(sporgenze.length / 2)] : 0
  let sopra: OcrBlock | null = null
  return blocchi.map((blocco) => {
    const stile: Record<string, string> = {}
    const passo = blocco.righe?.interlinea || tipico
    if (passo > 0) stile['--iu-ocr-interlinea'] = mm(passo * mmY)
    if (!blocco.box) return stile as CSSProperties
    const [x0, y0, x1] = blocco.box
    // Il foglio misura dalle righe (interlinea intera), la pagina dalle
    // lettere: fra le due c'e' mezza interlinea sopra e mezza sotto ogni riga.
    const mezzaInterlinea = (parte: OcrBlock) => {
      const passoParte = parte.righe?.interlinea || tipico
      const lettere = parte.righe?.altezza || 0
      return passoParte > 0 && lettere > 0 ? (passoParte - lettere) / 2 : 0
    }
    if (sopra?.box) {
      const distanza = (y0 - sopra.box[3] - mezzaInterlinea(sopra) - mezzaInterlinea(blocco)) * mmY
      // Sempre, anche piccola (gli scarti minimi, sommati su una pagina,
      // spostano le ultime righe), e negativa quando due parti stanno
      // affiancate (l'intestazione a sinistra, il timbro della firma a
      // destra): la seconda risale accanto alla prima.
      if (distanza !== 0) stile.marginTop = mm(Math.min(250, Math.max(-250, distanza)))
    } else {
      // la prima parte: il margine alto del foglio ha un minimo e un massimo,
      // la pagina no
      const scarto = (y0 - mezzaInterlinea(blocco)) * mmY - margini.alto
      if (scarto !== 0) stile.marginTop = mm(scarto)
    }
    const alline = blocco.format.allineamento
    const testuale = blocco.kind === 'paragrafo' || blocco.kind === 'titolo' || blocco.kind === 'elenco'
    if (testuale && (alline === 'sinistra' || alline === 'giustificato')) {
      // una voce d'elenco di una riga sola non dice la sporgenza: vale quella delle altre
      let rientro = blocco.righe?.rientro || 0
      if (blocco.kind === 'elenco' && rientro >= 0 && sporgenzaTipica > 0) rientro = -sporgenzaTipica
      const aSinistra = (x0 + Math.max(0, -rientro)) * mmX - gabbiaSinistra
      if (aSinistra > 0.3) stile.marginLeft = mm(aSinistra)
      if (Math.abs(rientro * mmX) > 0.3) stile.textIndent = mm(rientro * mmX)
      if (rientro < 0) stile['--iu-ocr-sporgenza'] = mm(-rientro * mmX)
      const aDestra = gabbiaDestra - x1 * mmX
      if (alline === 'giustificato' && aDestra > 0.5) stile.marginRight = mm(aDestra)
    }
    if (testuale && alline === 'destra') {
      // anche negativo: un timbro di firma sta oltre il margine della colonna
      const aDestra = gabbiaDestra - x1 * mmX
      if (Math.abs(aDestra) > 0.3) stile.marginRight = mm(aDestra)
    }
    if ((testuale || blocco.kind === 'numero_pagina') && alline === 'centro') {
      // una riga centrata non sempre sta al centro della gabbia (un rientro del
      // paragrafo la sposta): si sposta di quanto era spostata sulla pagina
      const scarto = ((x0 + x1) / 2) * mmX - (gabbiaSinistra + gabbiaDestra) / 2
      if (Math.abs(scarto) > 0.5 && Math.abs(scarto) < 25) Object.assign(stile, { position: 'relative', left: mm(scarto) })
    }
    // Con gli a capo del documento (ocrACapo) le righe sono gia' quelle: la
    // larghezza serve solo quando non ci sono.
    const lettere = blocco.righe?.altezza || 0
    const piuRighe = lettere > 0 && blocco.box[3] - y0 > lettere * 1.6
    if (testuale && alline !== 'giustificato' && piuRighe && !aCapoValidi(blocco).length) {
      stile.maxWidth = mm((x1 - x0) * mmX + 1.5)
      if (alline === 'centro') Object.assign(stile, { marginLeft: 'auto', marginRight: 'auto' })
      if (alline === 'destra') stile.marginLeft = 'auto'
    }
    sopra = blocco
    return stile as CSSProperties
  })
}
