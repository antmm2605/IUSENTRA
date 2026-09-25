/**
 * Le voci della barra della revisione: livelli, caratteri, corpi e come si
 * chiamano le parti. Sono dati, non comandi: i comandi stanno in OcrReview.
 */

export const LIVELLI: { value: number; label: string }[] = [
  { value: 0, label: 'Testo del documento' },
  { value: 1, label: 'Titolo principale' },
  { value: 2, label: 'Titolo' },
  { value: 3, label: 'Sottotitolo' },
  { value: 4, label: 'Rubrica' },
]

/**
 * I caratteri che si offrono sempre, per famiglia: quelli dell'editor dei
 * documenti e il corredo di Microsoft Word, perche' un atto che arriva da
 * fuori studio usa quasi sempre uno di questi. A questi si aggiungono quelli
 * che il documento stesso usa: un carattere letto dal PDF deve poter restare,
 * anche se non e' fra i soliti.
 */
export const GRUPPI_CARATTERI: { gruppo: string; caratteri: string[] }[] = [
  {
    gruppo: 'Con grazie (atti e documenti)',
    caratteri: [
      'Times New Roman', 'Garamond', 'Georgia', 'Book Antiqua', 'Palatino Linotype', 'Cambria', 'Bookman Old Style',
      'Century Schoolbook', 'Constantia', 'Baskerville Old Face', 'Perpetua', 'Sylfaen', 'Rockwell',
      'Source Serif 4', 'Merriweather', 'Libre Baskerville', 'Spectral', 'Crimson Text',
    ],
  },
  {
    gruppo: 'Senza grazie',
    caratteri: [
      'Arial', 'Calibri', 'Aptos', 'Verdana', 'Tahoma', 'Segoe UI', 'Trebuchet MS', 'Century Gothic', 'Franklin Gothic',
      'Candara', 'Corbel', 'Gill Sans MT', 'Lucida Sans', 'Arial Narrow', 'Arial Black', 'Microsoft Sans Serif',
      'Bahnschrift', 'Inter', 'Manrope', 'Impact', 'Comic Sans MS',
    ],
  },
  {
    gruppo: 'A spaziatura fissa',
    caratteri: ['Courier New', 'Consolas', 'Lucida Console', 'IBM Plex Mono'],
  },
]

export const CARATTERI_COMUNI = GRUPPI_CARATTERI.flatMap((voce) => voce.caratteri)

/** I corpi da 2 a 48 punti: i piccoli per note e timbri, i grandi per intestazioni. */
export const CORPI = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10.5, 11, 11.5, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 44, 48]

/** Interlinea come multiplo del corpo, come in Word. Zero: quella del documento. */
export const INTERLINEE: { value: number; label: string }[] = [
  { value: 0, label: 'Interlinea del documento' },
  { value: 1, label: 'Interlinea singola' },
  { value: 1.15, label: 'Interlinea 1,15' },
  { value: 1.5, label: 'Interlinea 1,5' },
  { value: 2, label: 'Interlinea doppia' },
  { value: 2.5, label: 'Interlinea 2,5' },
  { value: 3, label: 'Interlinea tripla' },
]

/** Un passo di rientro: mezzo centimetro, e al massimo dieci. */
export const RIENTRO_PASSO_MM = 5
export const RIENTRO_MASSIMO_MM = 100

export const ETICHETTE_MARCATORE: Record<string, string> = {
  puntato: 'elenco puntato',
  numerato: 'elenco numerato',
  lettera: 'elenco per lettere',
  romano: 'elenco in numeri romani',
  decimale: 'elenco a livelli',
}

export function fiducia(valore: number): string {
  if (!valore) return ''
  return `${Math.round(valore * 100)}% di confidenza`
}
