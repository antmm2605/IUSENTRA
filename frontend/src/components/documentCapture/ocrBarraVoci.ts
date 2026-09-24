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
 * I caratteri che si offrono sempre: quelli dell'editor dei documenti, più
 * quelli che il documento stesso usa. Un carattere letto dal PDF deve poter
 * restare, anche se non è fra i soliti.
 */
export const CARATTERI_COMUNI = ['Times New Roman', 'Arial', 'Calibri', 'Garamond', 'Georgia', 'Book Antiqua', 'Courier New']
export const CORPI = [8, 9, 10, 10.5, 11, 11.5, 12, 13, 14, 16, 18, 20, 24]

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
