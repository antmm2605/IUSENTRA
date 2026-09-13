/**
 * Blocchi riconosciuti da una pagina acquisita e loro resa nel documento.
 *
 * Il riconoscimento restituisce la struttura della pagina, non un testo unico:
 * qui vive il modello di quei blocchi, la loro modifica da parte dell'avvocato
 * e la conversione finale in HTML per l'editor, così che titoli, elenchi e
 * tabelle arrivino nel documento con la forma che avevano sul foglio.
 */

export type OcrBlockKind = 'titolo' | 'paragrafo' | 'elenco' | 'tabella'

export type OcrBlock = {
  id: string
  kind: OcrBlockKind
  text: string
  rows: string[][]
  confidence: number
  page: number
}

export type OcrFigure = { page: number; box: [number, number, number, number]; coverage: number }

const KINDS: OcrBlockKind[] = ['titolo', 'paragrafo', 'elenco', 'tabella']

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
    blocks.push({ id: newId(), kind, text, rows, confidence: Number(item.confidenza ?? 0) || 0, page })
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

/** HTML da inserire nell'editor: la struttura riconosciuta, non un testo piatto. */
export function blocksToHtml(blocks: OcrBlock[]): string {
  return blocks
    .map((block) => {
      if (block.kind === 'tabella') return block.rows.length ? tableHtml(block.rows) : ''
      const text = block.text.trim()
      if (!text) return ''
      if (block.kind === 'titolo') return `<p><strong>${escapeHtml(text)}</strong></p>`
      if (block.kind === 'elenco') return `<ul><li>${escapeHtml(text.replace(/^(?:[-•·–—*]|\(?[a-zA-Z0-9]{1,3}[.)])\s+/, ''))}</li></ul>`
      return `<p>${escapeHtml(text)}</p>`
    })
    .filter(Boolean)
    .join('')
}

/** Testo semplice, per l'anteprima e per il conteggio dei caratteri. */
export function blocksToPlainText(blocks: OcrBlock[]): string {
  return blocks
    .map((block) => (block.kind === 'tabella' ? block.rows.map((row) => row.join(' | ')).join('\n') : block.text))
    .filter(Boolean)
    .join('\n\n')
}

export function countCharacters(blocks: OcrBlock[]): number {
  return blocksToPlainText(blocks).replace(/\s+/g, '').length
}

export function updateBlockText(blocks: OcrBlock[], id: string, text: string): OcrBlock[] {
  return blocks.map((block) => (block.id === id ? { ...block, text } : block))
}

export function updateBlockCell(blocks: OcrBlock[], id: string, row: number, column: number, value: string): OcrBlock[] {
  return blocks.map((block) => {
    if (block.id !== id) return block
    const rows = block.rows.map((cells, index) => (index === row ? cells.map((cell, position) => (position === column ? value : cell)) : cells))
    return { ...block, rows }
  })
}

export function changeBlockKind(blocks: OcrBlock[], id: string, kind: OcrBlockKind): OcrBlock[] {
  return blocks.map((block) => (block.id === id ? { ...block, kind } : block))
}

export function removeBlock(blocks: OcrBlock[], id: string): OcrBlock[] {
  return blocks.filter((block) => block.id !== id)
}
