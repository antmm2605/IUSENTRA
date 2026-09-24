/**
 * Dai blocchi riconosciuti all'HTML del documento.
 *
 * Il riconoscimento restituisce la struttura della pagina — titoli, capoversi,
 * voci di elenco, tabelle — e qui quella struttura diventa il documento: e' il
 * solo posto in cui si decide come un blocco si scrive, cosi' che l'editor,
 * l'export PDF e la conversione in Word vedano sempre la stessa forma.
 *
 * Elenchi nel documento: <ul> per le voci puntate, <ol type="a|I" start="n"> per
 * lettere, numeri romani e numeri che non partono da uno (vedi attributiElenco
 * in ocrMarkers).
 */
import { attributiElenco, continuaElenco, markerOf, voceSenzaMarcatore } from './ocrMarkers'
import type { OcrBlock, OcrFormat, OcrMarker } from './ocrBlocks'

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
      pezzi.push(`<li>${inlineHtml(voceSenzaMarcatore(testo, marker), block.format)}</li>`)
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
  const formato = block.format
  const contenuto = inlineHtml(text, formato)
  if (formato.livello >= 1 && formato.livello <= 4) return `<h${formato.livello}${stileDelParagrafo(formato)}>${contenuto}</h${formato.livello}>`
  // Il titolo riconosciuto senza misura di corpo resta in grassetto.
  if (block.kind === 'titolo') return `<p${stileDelParagrafo(formato)}><strong>${contenuto}</strong></p>`
  return `<p${stileDelParagrafo(formato)}>${contenuto}</p>`
}

/** Grassetto e corsivo del blocco, nell'HTML consentito dal documento. */
function inlineHtml(text: string, formato: OcrFormat): string {
  let html = escapeHtml(text)
  if (formato.grassetto && formato.livello === 0) html = `<strong>${html}</strong>`
  if (formato.corsivo) html = `<em>${html}</em>`
  return html
}

/**
 * Lo stile del capoverso: allineamento, colore, carattere e corpo.
 *
 * Si dichiara solo quello che il documento aveva di suo. Il colore c'è quando
 * è un colore davvero — l'azzurro di una carta intestata, il rosso di un
 * richiamo — e il nero non si scrive: ogni capoverso si porterebbe dietro un
 * «color:#000000» che non aggiunge niente e che poi qualcuno deve togliere.
 * Carattere e corpo arrivano solo quando il documento li dichiara (il testo
 * vero di un PDF): da una scansione non si leggono, e restano quelli del
 * documento in cui il testo viene inserito.
 */
function stileDelParagrafo(formato: OcrFormat): string {
  const pezzi: string[] = []
  if (formato.allineamento === 'centro') pezzi.push('text-align:center')
  else if (formato.allineamento === 'destra') pezzi.push('text-align:right')
  else if (formato.allineamento === 'giustificato') pezzi.push('text-align:justify')
  if (formato.colore) pezzi.push(`color:${formato.colore}`)
  if (formato.famiglia) pezzi.push(`font-family:'${formato.famiglia}'`)
  if (formato.corpo) pezzi.push(`font-size:${formato.corpo}pt`)
  return pezzi.length ? ` style="${pezzi.join(';')}"` : ''
}
