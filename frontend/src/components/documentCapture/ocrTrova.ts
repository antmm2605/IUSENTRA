/**
 * Trova e sostituisci nel testo riconosciuto.
 *
 * L'errore del riconoscimento si ripete: lo stesso nome letto male in ogni
 * pagina, «l'» diventato «1'», un numero di ruolo sbagliato ovunque. Si
 * corregge una volta sola, in tutto il documento, anche nelle tabelle.
 */
import { updateBlockText } from './ocrBlockEdits'
import type { OcrBlock } from './ocrBlocks'

export type OpzioniRicerca = { maiuscole: boolean; paroleIntere: boolean }
export type Occorrenza = { blockId: string; inizio: number; fine: number }

function espressione(cerca: string, opzioni: OpzioniRicerca): RegExp | null {
  if (!cerca) return null
  const letterale = cerca.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const corpo = opzioni.paroleIntere ? `(?<![\\p{L}\\p{N}])${letterale}(?![\\p{L}\\p{N}])` : letterale
  return new RegExp(corpo, `gu${opzioni.maiuscole ? '' : 'i'}`)
}

/** Dove compare il testo cercato, pezzo per pezzo e nell'ordine del documento. */
export function occorrenze(blocks: OcrBlock[], cerca: string, opzioni: OpzioniRicerca): Occorrenza[] {
  const regola = espressione(cerca, opzioni)
  if (!regola) return []
  const trovate: Occorrenza[] = []
  for (const block of blocks) {
    const testi = block.kind === 'tabella' ? [block.rows.flat().join('\n')] : [block.text]
    for (const testo of testi) {
      for (const trovata of testo.matchAll(regola)) {
        trovate.push({ blockId: block.id, inizio: trovata.index ?? 0, fine: (trovata.index ?? 0) + trovata[0].length })
      }
    }
  }
  return trovate
}

/** Sostituisce ovunque; restituisce i blocchi nuovi e quante sostituzioni ha fatto. */
export function sostituisciTutto(
  blocks: OcrBlock[],
  cerca: string,
  sostituto: string,
  opzioni: OpzioniRicerca,
): { blocks: OcrBlock[]; quante: number } {
  const regola = espressione(cerca, opzioni)
  if (!regola) return { blocks, quante: 0 }
  let quante = 0
  const sostituisci = (testo: string) => testo.replace(regola, () => {
    quante += 1
    return sostituto
  })
  let nuovi = blocks
  for (const block of blocks) {
    if (block.kind === 'tabella') {
      const prima = quante
      const rows = block.rows.map((riga) => riga.map(sostituisci))
      if (quante !== prima) nuovi = nuovi.map((voce) => (voce.id === block.id ? { ...voce, rows } : voce))
      continue
    }
    const testo = sostituisci(block.text)
    if (testo !== block.text) nuovi = updateBlockText(nuovi, block.id, testo)
  }
  return { blocks: nuovi, quante }
}
