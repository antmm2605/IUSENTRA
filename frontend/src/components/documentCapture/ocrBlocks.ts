/**
 * Blocchi riconosciuti da una pagina acquisita e loro resa nel documento.
 *
 * Il riconoscimento restituisce la struttura della pagina, non un testo unico:
 * qui vive il modello di quei blocchi, la loro modifica da parte dell'avvocato
 * e la conversione finale in HTML per l'editor, così che titoli, elenchi e
 * tabelle arrivino nel documento con la forma che avevano sul foglio.
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
}

import { attributiElenco, continuaElenco, markerOf, parseMarker, voceSenzaMarcatore } from './ocrMarkers'

export { markerFromText, markerOf } from './ocrMarkers'
// Elenchi nel documento: <ul> per le voci puntate, <ol type="a|I" start="n"> per lettere,
// numeri romani e numeri che non partono da uno (vedi attributiElenco in ocrMarkers).

export const FORMATO_PREDEFINITO: OcrFormat = {
  livello: 0,
  grassetto: false,
  corsivo: false,
  allineamento: 'sinistra',
  scala: 1,
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
  }
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

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character] as string
  ))
}

function tableHtml(rows: string[][]): string {
  const width = rows.reduce((max, row) => Math.max(max, row.length), 0)
  const cell = (row: string[], index: number, tag: 'td' | 'th') => `<${tag}>${escapeHtml(row[index] ?? '')}</${tag}>`
  const [header, ...body] = rows
  const headHtml = `<thead><tr>${Array.from({ length: width }, (_, index) => cell(header, index, 'th')).join('')}</tr></thead>`
  const bodyHtml = body.length
    ? `<tbody>${body.map((row) => `<tr>${Array.from({ length: width }, (_, index) => cell(row, index, 'td')).join('')}</tr>`).join('')}</tbody>`
    : ''
  return `<table border="1" cellspacing="0" cellpadding="4">${headHtml}${bodyHtml}</table>`
}

/**
 * Interruzione di pagina del documento riconosciuto.
 *
 * È il marcatore dell'editor: lo riconoscono la pagina, l'export PDF e la
 * conversione in Word, così le pagine dell'originale restano pagine.
 */
export const INTERRUZIONE_PAGINA_HTML = '<hr class="iu-ted-page-break" data-iu-page-break="true">'

/**
 * HTML da inserire nell'editor: la struttura riconosciuta, non un testo piatto.
 *
 * Le voci di elenco consecutive dello stesso tipo diventano un solo elenco,
 * con il tipo (numeri, lettere, romani) e il numero di partenza dell'atto:
 * cosi' «3) … 4) … 5)» non riparte da uno nel documento.
 */
export function blocksToHtml(blocks: OcrBlock[]): string {
  const pezzi: string[] = []
  let paginaPrecedente = blocks[0]?.page ?? 1
  let elencoAperto: { tag: 'ul' | 'ol'; marker: OcrMarker | null } | null = null
  const chiudiElenco = () => {
    if (elencoAperto) pezzi.push(`</${elencoAperto.tag}>`)
    elencoAperto = null
  }
  for (const block of blocks) {
    if (block.kind === 'numero_pagina') continue
    if (block.page !== paginaPrecedente) {
      chiudiElenco()
      pezzi.push(INTERRUZIONE_PAGINA_HTML)
      paginaPrecedente = block.page
    }
    if (block.kind === 'elenco') {
      const testo = block.text.trim()
      if (!testo) continue
      const marker = markerOf(block)
      if (!elencoAperto || !continuaElenco(elencoAperto.marker, marker)) {
        chiudiElenco()
        const { tag, attrs } = attributiElenco(marker)
        pezzi.push(`<${tag}${attrs}>`)
        elencoAperto = { tag, marker }
      } else {
        elencoAperto = { tag: elencoAperto.tag, marker }
      }
      pezzi.push(`<li>${inlineHtml(voceSenzaMarcatore(testo, marker), block.format || FORMATO_PREDEFINITO)}</li>`)
      continue
    }
    chiudiElenco()
    const html = blockHtml(block)
    if (html) pezzi.push(html)
  }
  chiudiElenco()
  return pezzi.join('')
}

function blockHtml(block: OcrBlock): string {
  if (block.kind === 'tabella') return block.rows.length ? tableHtml(block.rows) : ''
  const text = block.text.trim()
  if (!text) return ''
  const formato = block.format || FORMATO_PREDEFINITO
  const contenuto = inlineHtml(text, formato)
  if (formato.livello >= 1 && formato.livello <= 4) return `<h${formato.livello}>${contenuto}</h${formato.livello}>`
  // Il titolo riconosciuto senza misura di corpo resta in grassetto.
  if (block.kind === 'titolo') return `<p${allineamentoHtml(formato)}><strong>${contenuto}</strong></p>`
  return `<p${allineamentoHtml(formato)}>${contenuto}</p>`
}

/** Grassetto e corsivo del blocco, nell'HTML consentito dal documento. */
function inlineHtml(text: string, formato: OcrFormat): string {
  let html = escapeHtml(text)
  if (formato.grassetto && formato.livello === 0) html = `<strong>${html}</strong>`
  if (formato.corsivo) html = `<em>${html}</em>`
  return html
}

/** Allineamento come stile del capoverso: è l'unico stile che il documento accetta. */
function allineamentoHtml(formato: OcrFormat): string {
  if (formato.allineamento === 'centro') return ' style="text-align:center"'
  if (formato.allineamento === 'destra') return ' style="text-align:right"'
  if (formato.allineamento === 'giustificato') return ' style="text-align:justify"'
  return ''
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
} from './ocrBlockEdits'
