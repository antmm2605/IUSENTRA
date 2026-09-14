/**
 * Marcatori delle voci di elenco: lettura dal server, rilettura dal testo corretto,
 * continuità dell'elenco e attributi HTML (tipo e numero di partenza).
 *
 * Specchio in JavaScript delle regole di `legal_ocr/formulario/elenchi.py`:
 * «c.» è una voce solo se continua un elenco per lettere, «i)» è la lettera i
 * dopo «h)» e il romano I in apertura, «v.» e «n.» sono abbreviazioni.
 */
import type { OcrBlock, OcrMarker } from './ocrBlocks'

const LETTERE_AMBIGUE = new Set('cdlmnpstv'.split(''))
const TIPI_MARCATORE: OcrMarker['tipo'][] = ['puntato', 'numerato', 'lettera', 'romano', 'decimale']

export function parseMarker(value: unknown): OcrMarker | null {
  if (!value || typeof value !== 'object') return null
  const voce = value as Record<string, unknown>
  const tipo = String(voce.tipo ?? '') as OcrMarker['tipo']
  if (!TIPI_MARCATORE.includes(tipo)) return null
  return {
    tipo,
    valore: Math.max(0, Math.trunc(Number(voce.valore ?? 0) || 0)),
    testo: String(voce.testo ?? '').trim(),
    livello: Math.max(1, Math.trunc(Number(voce.livello ?? 1) || 1)),
  }
}

/** Il marcatore riletto dal testo, quando l'avvocato lo ha cambiato a mano. */
export function markerFromText(text: string): OcrMarker | null {
  const riga = text.trimStart()
  let m = /^([-•·–—*▪■●○◦►➢✓])\s+(?=\S)/.exec(riga)
  if (m) return { tipo: 'puntato', valore: 0, testo: m[1], livello: 1 }
  m = /^(\d{1,2}(?:\.\d{1,2}){1,3})[.)]?\s+[^\d\s]/.exec(riga)
  if (m) { const parti = m[1].split('.'); return { tipo: 'decimale', valore: Number(parti[parti.length - 1]), testo: m[1], livello: parti.length } }
  m = /^\(?(\d{1,3})(?:[.)]|°)\s+(?=\S)/.exec(riga)
  if (m) return { tipo: 'numerato', valore: Number(m[1]), testo: m[0].trim(), livello: 1 }
  m = /^\(?([ivx]{1,6}|[IVX]{1,6})[.)]\s+(?=\S)/.exec(riga)
  if (m) return { tipo: 'romano', valore: romanoValore(m[1]), testo: m[0].trim(), livello: 1 }
  m = /^\(?([a-zA-Z])\)\s+(?=\S)/.exec(riga)
  if (m) return { tipo: 'lettera', valore: m[1].toLowerCase().charCodeAt(0) - 96, testo: m[0].trim(), livello: 1 }
  // Con il punto solo le minuscole che non sono abbreviazioni («c.» comma,
  // «v.» vedi, «n.» numero), e mai davanti a una cifra.
  m = /^([a-z])\.\s+(?=[^\d\s])/.exec(riga)
  if (m && !LETTERE_AMBIGUE.has(m[1])) return { tipo: 'lettera', valore: m[1].charCodeAt(0) - 96, testo: m[0].trim(), livello: 1 }
  return null
}

function romanoValore(valore: string): number {
  const pesi: Record<string, number> = { i: 1, v: 5, x: 10, l: 50 }
  let totale = 0
  let precedente = 0
  for (const carattere of valore.toLowerCase().split('').reverse()) {
    const peso = pesi[carattere] ?? 0
    totale += peso < precedente ? -peso : peso
    precedente = Math.max(precedente, peso)
  }
  return totale
}

/** Il segno effettivo della voce: quello letto, o riletto dal testo corretto. */
export function markerOf(block: OcrBlock): OcrMarker | null {
  if (block.kind !== 'elenco') return null
  return markerFromText(block.text) ?? block.marker
}

export function voceSenzaMarcatore(text: string, marker: OcrMarker | null): string {
  const riga = text.trim()
  if (!marker) return riga.replace(/^(?:[-•·–—*▪■●○◦►➢✓]|\(?[a-zA-Z0-9]{1,3}[.)]|\(?[ivxIVX]{1,6}[.)])\s+/, '')
  const senza = riga.replace(/^(?:[-•·–—*▪■●○◦►➢✓]|\(?\d{1,2}(?:\.\d{1,2}){1,3}[.)]?|\(?\d{1,3}(?:[.)]|°)|\(?[a-zA-Z]{1,6}[.)])\s+/, '')
  return senza
}

/** Vero se la voce «nuovo» continua l'elenco della voce «precedente». */
export function continuaElenco(precedente: OcrMarker | null, nuovo: OcrMarker | null): boolean {
  if (!precedente || !nuovo || precedente.tipo !== nuovo.tipo) return false
  if (nuovo.tipo === 'puntato') return true
  if (nuovo.tipo === 'decimale') return nuovo.livello === precedente.livello && nuovo.valore === precedente.valore + 1
  return nuovo.valore === precedente.valore + 1
}

/** Attributi HTML dell'elenco: tipo e numero di partenza, com'erano nell'atto. */
export function attributiElenco(marker: OcrMarker | null): { tag: 'ul' | 'ol'; attrs: string } {
  if (!marker || marker.tipo === 'puntato') return { tag: 'ul', attrs: '' }
  let tipo = ''
  if (marker.tipo === 'lettera') tipo = /^[A-Z]/.test(marker.testo) ? 'A' : 'a'
  if (marker.tipo === 'romano') tipo = /^[IVX]/.test(marker.testo) ? 'I' : 'i'
  const attrs = `${tipo ? ` type="${tipo}"` : ''}${marker.valore > 1 ? ` start="${marker.valore}"` : ''}`
  return { tag: 'ol', attrs }
}

