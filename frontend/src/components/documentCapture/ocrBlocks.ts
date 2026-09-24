/**
 * Blocchi riconosciuti da una pagina acquisita e loro resa nel documento.
 *
 * Il riconoscimento restituisce la struttura della pagina, non un testo unico:
 * qui vive il modello di quei blocchi e la lettura della risposta del server.
 * La resa in HTML per l'editor sta in ocrHtml, e da li' esce anche di qui.
 */

export type OcrBlockKind = 'titolo' | 'paragrafo' | 'elenco' | 'tabella' | 'numero_pagina'

export type OcrAlignment = 'sinistra' | 'centro' | 'destra' | 'giustificato'

/** Com'era scritto il blocco sul foglio: misurato dal server, non deciso qui. */
export type OcrFormat = {
  livello: number
  grassetto: boolean
  corsivo: boolean
  allineamento: OcrAlignment
  scala: number
  /** Colore del testo, `#rrggbb`. Vuoto quando è il nero del documento. */
  colore: string
  /** Carattere, già una famiglia dell'editor. Vuoto: quello del documento. */
  famiglia: string
  /** Corpo in punti come lo dichiara il documento. Zero: quello del documento. */
  corpo: number
  /** Nel PDF sono linee disegnate sopra il testo: vere solo se misurate. */
  sottolineato: boolean
  barrato: boolean
}

/** Il segno che apre una voce di elenco, come lo ha letto il server. */
export type OcrMarker = {
  tipo: 'puntato' | 'numerato' | 'lettera' | 'romano' | 'decimale'
  valore: number
  testo: string
  livello: number
}

export type OcrBlock = {
  id: string
  kind: OcrBlockKind
  text: string
  rows: string[][]
  confidence: number
  page: number
  format: OcrFormat
  /** Riquadro sulla pagina, per ritrovare il blocco nell'immagine. */
  box: [number, number, number, number] | null
  /** Marcatore della voce di elenco: il testo del blocco lo comprende ancora. */
  marker: OcrMarker | null
  /** Dove il formato cambia dentro il testo (vedi ocrTratti). Assenti: vale il formato del blocco. */
  tratti?: OcrTratto[]
  /** Misure delle righe sulla pagina, nelle unita' del riquadro (vedi ocrPagina). */
  righe?: OcrMisureRighe
  /** Dove cominciavano le righe del documento, per il testo letto (vedi ocrACapo). */
  aCapo?: { testo: string; posizioni: number[]; piene?: boolean[] }
}

/** Passo fra le righe, altezza delle lettere e rientro della prima riga. */
export type OcrMisureRighe = { interlinea: number; altezza: number; rientro: number }

/** Le posizioni del server contano i caratteri; quelle del browser le unita' UTF-16. */
function parseACapo(payload: unknown, testo: string, piene: unknown): OcrBlock['aCapo'] {
  if (!Array.isArray(payload) || !payload.length) return undefined
  const caratteri = Array.from(testo)
  const unita: number[] = [0]
  for (const carattere of caratteri) unita.push(unita[unita.length - 1] + carattere.length)
  const posizioni = payload
    .map((valore) => Math.trunc(Number(valore)))
    .filter((valore) => Number.isFinite(valore) && valore > 0 && valore < caratteri.length)
    .map((valore) => unita[valore])
  if (!posizioni.length) return undefined
  const ordinate = Array.from(new Set(posizioni)).sort((a, b) => a - b)
  const righePiene = Array.isArray(piene) && piene.length === ordinate.length + 1 ? piene.map((valore) => valore === true) : undefined
  return { testo, posizioni: ordinate, piene: righePiene }
}

function parseMisureRighe(payload: unknown): OcrMisureRighe | undefined {
  if (!payload || typeof payload !== 'object') return undefined
  const voce = payload as Record<string, unknown>
  const altezza = Number(voce.altezza) || 0
  if (altezza <= 0) return undefined
  return { interlinea: Math.max(0, Number(voce.interlinea) || 0), altezza, rientro: Number(voce.rientro) || 0 }
}

import { parseMarker } from './ocrMarkers'
import { parseTratti, type OcrTratto } from './ocrTratti'

export { markerFromText, markerOf } from './ocrMarkers'
export { INTERRUZIONE_PAGINA_HTML, blocksToHtml } from './ocrHtml'
export type { OcrTratto } from './ocrTratti'

export const FORMATO_PREDEFINITO: OcrFormat = {
  livello: 0,
  grassetto: false,
  corsivo: false,
  allineamento: 'sinistra',
  scala: 1,
  colore: '',
  famiglia: '',
  corpo: 0,
  sottolineato: false,
  barrato: false,
}

const ALLINEAMENTI: OcrAlignment[] = ['sinistra', 'centro', 'destra', 'giustificato']

export const CLASSI_ALLINEAMENTO: Record<OcrAlignment, string> = {
  sinistra: 'iu-ocr-al--sinistra',
  centro: 'iu-ocr-al--centro',
  destra: 'iu-ocr-al--destra',
  giustificato: 'iu-ocr-al--giustificato',
}

function parseFormat(value: unknown): OcrFormat {
  if (!value || typeof value !== 'object') return { ...FORMATO_PREDEFINITO }
  const voce = value as Record<string, unknown>
  const livello = Number(voce.livello ?? 0)
  const allineamento = String(voce.allineamento ?? '') as OcrAlignment
  return {
    livello: Number.isFinite(livello) ? Math.min(4, Math.max(0, Math.trunc(livello))) : 0,
    grassetto: Boolean(voce.grassetto),
    corsivo: Boolean(voce.corsivo),
    allineamento: ALLINEAMENTI.includes(allineamento) ? allineamento : 'sinistra',
    scala: Number(voce.scala ?? 1) || 1,
    colore: coloreValido(voce.colore),
    famiglia: famigliaValida(voce.famiglia),
    corpo: corpoValido(voce.corpo),
    sottolineato: Boolean(voce.sottolineato),
    barrato: Boolean(voce.barrato),
  }
}

/** Un colore si accetta solo nella forma che il documento sa rendere. */
function coloreValido(value: unknown): string {
  const testo = String(value ?? '').trim().toLowerCase()
  return /^#[0-9a-f]{6}$/.test(testo) ? testo : ''
}

/** Un nome di carattere e basta: finisce in uno stile, non deve poterne uscire. */
export function famigliaValida(value: unknown): string {
  const testo = String(value ?? '').trim()
  return /^[A-Za-z0-9][A-Za-z0-9 -]{0,59}$/.test(testo) ? testo : ''
}

/** Il corpo in punti, al mezzo punto, dentro quello che un atto usa davvero. */
export function corpoValido(value: unknown): number {
  const numero = Math.round(Number(value) * 2) / 2
  return Number.isFinite(numero) && numero >= 4 && numero <= 96 ? numero : 0
}

function parseBox(value: unknown): [number, number, number, number] | null {
  if (!Array.isArray(value) || value.length !== 4) return null
  const numeri = value.map((item) => Number(item) || 0)
  return [numeri[0], numeri[1], numeri[2], numeri[3]]
}

export type OcrFigure = { page: number; box: [number, number, number, number]; coverage: number }

const KINDS: OcrBlockKind[] = ['titolo', 'paragrafo', 'elenco', 'tabella', 'numero_pagina']

function newId(): string {
  try { return crypto.randomUUID() } catch { return `b${Math.random().toString(36).slice(2)}` }
}

function asRows(value: unknown): string[][] {
  if (!Array.isArray(value)) return []
  return value
    .map((row) => (Array.isArray(row) ? row.map((cell) => String(cell ?? '').trim()) : []))
    .filter((row) => row.length > 0)
}

/** Blocchi dalla risposta del server, con i valori normalizzati. */
export function parseBlocks(payload: unknown, page: number): OcrBlock[] {
  if (!Array.isArray(payload)) return []
  const blocks: OcrBlock[] = []
  for (const raw of payload) {
    if (!raw || typeof raw !== 'object') continue
    const item = raw as Record<string, unknown>
    const kind = KINDS.includes(String(item.tipo) as OcrBlockKind) ? (String(item.tipo) as OcrBlockKind) : 'paragrafo'
    const rows = kind === 'tabella' ? asRows(item.righe) : []
    const text = String(item.testo ?? '').trim()
    if (kind === 'tabella' ? rows.length === 0 : text.length === 0) continue
    blocks.push({
      id: newId(),
      kind,
      text,
      rows,
      confidence: Number(item.confidenza ?? 0) || 0,
      page,
      format: parseFormat(item.formato),
      box: parseBox(item.riquadro),
      marker: kind === 'elenco' ? parseMarker(item.marcatore) : null,
      tratti: kind === 'tabella' ? [] : parseTratti(item.tratti, text),
      righe: kind === 'tabella' ? undefined : parseMisureRighe(item.righe_misure),
      aCapo: kind === 'tabella' ? undefined : parseACapo(item.a_capo, text, item.righe_piene),
    })
  }
  return blocks
}

export function parseFigures(payload: unknown, page: number): OcrFigure[] {
  if (!Array.isArray(payload)) return []
  return payload.flatMap((raw) => {
    const item = (raw ?? {}) as Record<string, unknown>
    const box = Array.isArray(item.riquadro) ? item.riquadro.map((value) => Number(value) || 0) : []
    if (box.length !== 4) return []
    return [{ page, box: box as [number, number, number, number], coverage: Number(item.copertura ?? 0) || 0 }]
  })
}

export {
  blocksOfPage,
  applyPlainTextToBlocks,
  blocksToPlainText,
  changeBlockKind,
  countCharacters,
  removeBlock,
  updateBlockCell,
  updateBlockFormat,
  updateBlockText,
  updateSelectionFormat,
} from './ocrBlockEdits'
