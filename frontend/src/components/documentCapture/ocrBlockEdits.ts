/**
 * Modifiche ai blocchi riconosciuti durante la revisione: testo, celle, natura,
 * formato, eliminazione; e le letture di servizio (testo semplice, conteggio).
 */
import type { OcrBlock, OcrBlockKind, OcrFormat } from './ocrBlocks'
import { trattiConFormato, trattiConFormatoTra, trattiDelBlocco, trattiDopoLaCorrezione } from './ocrTratti'

/** Il testo nuovo, con i tratti riallineati: una correzione non cancella il neretto. */
function conTesto(block: OcrBlock, text: string): OcrBlock {
  return { ...block, text, tratti: trattiDopoLaCorrezione(block.tratti ?? [], block.text, text) }
}

/** Testo semplice, per l'anteprima e per il conteggio dei caratteri. */
export function blocksToPlainText(blocks: OcrBlock[]): string {
  return blocks
    .filter((block) => block.kind !== 'numero_pagina')
    .map((block) => (block.kind === 'tabella' ? block.rows.map((row) => row.join(' | ')).join('\n') : block.text))
    .filter(Boolean)
    .join('\n\n')
}

export function applyPlainTextToBlocks(blocks: OcrBlock[], plainText: string): OcrBlock[] {
  const parti = String(plainText ?? '')
    .replace(/\r\n?/g, '\n')
    .split(/\n{2,}/)
    .map((parte) => parte.trim())
  let indice = 0
  return blocks.map((block) => {
    if (block.kind === 'tabella' || block.kind === 'numero_pagina') return block
    const text = parti[indice] ?? ''
    indice += 1
    return conTesto(block, text)
  })
}

export function countCharacters(blocks: OcrBlock[]): number {
  return blocksToPlainText(blocks).replace(/\s+/g, '').length
}

export function updateBlockText(blocks: OcrBlock[], id: string, text: string): OcrBlock[] {
  return blocks.map((block) => (block.id === id ? conTesto(block, text) : block))
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

/** Cambia il formato di un blocco durante la revisione. */
export function updateBlockFormat(blocks: OcrBlock[], id: string, patch: Partial<OcrFormat>): OcrBlock[] {
  return blocks.map((block) => (
    block.id === id
      ? { ...block, format: { ...block.format, ...patch }, tratti: trattiConFormato(block.tratti ?? [], patch) }
      : block
  ))
}

/**
 * Il formato su una parte del testo: la parola selezionata, non il capoverso.
 *
 * Se dopo il cambio il testo torna tutto uguale, i tratti tornano a essere il
 * formato del blocco: il documento non si porta dietro tratti che non dicono
 * niente, e la barra mostra di nuovo lo stato del pezzo intero.
 */
export function updateSelectionFormat(blocks: OcrBlock[], id: string, inizio: number, fine: number, patch: Partial<OcrFormat>): OcrBlock[] {
  return blocks.map((block) => {
    if (block.id !== id) return block
    const tratti = trattiConFormatoTra(trattiDelBlocco(block.tratti, block.text, block.format), inizio, fine, patch)
    if (tratti.length !== 1) return { ...block, tratti }
    const [unico] = tratti
    const { grassetto, corsivo, sottolineato, barrato, colore } = unico
    return { ...block, tratti: [], format: { ...block.format, grassetto, corsivo, sottolineato, barrato, colore } }
  })
}

/** Blocchi di una pagina, per la vista affiancata all'immagine. */
export function blocksOfPage(blocks: OcrBlock[], page: number): OcrBlock[] {
  return blocks.filter((block) => block.page === page)
}
