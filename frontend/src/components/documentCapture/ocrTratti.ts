/**
 * I tratti di un capoverso: dove, dentro la riga, il formato cambia.
 *
 * Il formato del blocco dice com'è scritto il capoverso nel suo insieme; i
 * tratti dicono quello che succede dentro la frase — il nome della parte in
 * neretto, il «rigetta» sottolineato, l'indirizzo PEC in blu. Messi in fila
 * ridanno esattamente il testo del blocco. Arrivano solo dal testo vero di un
 * PDF (vedi `legal_ocr/tratti.py`): da una scansione il formato di una singola
 * parola non si legge con sicurezza.
 *
 * Quando ci sono, sono loro a dire neretto, corsivo, sottolineato, barrato e
 * colore; il formato del blocco resta il riassunto che la barra mostra, e un
 * comando della barra agisce su tutti i tratti del pezzo.
 */
import type { OcrFormat } from './ocrBlocks'

export type OcrTratto = {
  testo: string
  grassetto: boolean
  corsivo: boolean
  sottolineato: boolean
  barrato: boolean
  colore: string
}

const CHIAVI_TRATTO = ['grassetto', 'corsivo', 'sottolineato', 'barrato', 'colore'] as const

function stessoStile(primo: OcrTratto, secondo: OcrTratto): boolean {
  return CHIAVI_TRATTO.every((chiave) => primo[chiave] === secondo[chiave])
}

/** Tratti contigui con lo stesso stile diventano uno: il documento resta pulito. */
function unisci(tratti: OcrTratto[]): OcrTratto[] {
  const fuori: OcrTratto[] = []
  for (const tratto of tratti) {
    if (!tratto.testo) continue
    const ultimo = fuori[fuori.length - 1]
    if (ultimo && stessoStile(ultimo, tratto)) fuori[fuori.length - 1] = { ...ultimo, testo: ultimo.testo + tratto.testo }
    else fuori.push({ ...tratto })
  }
  return fuori
}

/** I tratti dalla risposta del server: valgono solo se ridanno il testo, lettera per lettera. */
export function parseTratti(value: unknown, testo: string): OcrTratto[] {
  if (!Array.isArray(value)) return []
  const letti = value.flatMap((raw) => {
    if (!raw || typeof raw !== 'object') return []
    const voce = raw as Record<string, unknown>
    const colore = String(voce.colore ?? '').trim().toLowerCase()
    return [{
      testo: String(voce.testo ?? ''),
      grassetto: Boolean(voce.grassetto),
      corsivo: Boolean(voce.corsivo),
      sottolineato: Boolean(voce.sottolineato),
      barrato: Boolean(voce.barrato),
      colore: /^#[0-9a-f]{6}$/.test(colore) ? colore : '',
    }]
  })
  // il testo del blocco arriva ripulito dagli spazi ai bordi: anche i tratti
  if (letti.length) {
    letti[0] = { ...letti[0], testo: letti[0].testo.trimStart() }
    const ultimo = letti.length - 1
    letti[ultimo] = { ...letti[ultimo], testo: letti[ultimo].testo.trimEnd() }
  }
  const tratti = unisci(letti)
  return tratti.length > 1 && tratti.map((tratto) => tratto.testo).join('') === testo ? tratti : []
}

/** I tratti di un pezzo del testo, fra due posizioni. */
export function trattiTra(tratti: OcrTratto[], inizio: number, fine: number): OcrTratto[] {
  const fuori: OcrTratto[] = []
  let posizione = 0
  for (const tratto of tratti) {
    const da = Math.max(inizio, posizione)
    const a = Math.min(fine, posizione + tratto.testo.length)
    if (a > da) fuori.push({ ...tratto, testo: tratto.testo.slice(da - posizione, a - posizione) })
    posizione += tratto.testo.length
  }
  return fuori
}

/**
 * I tratti dopo una correzione del testo.
 *
 * Quello che resta uguale in testa e in coda tiene il proprio stile; quello
 * che si scrive prende lo stile della lettera prima, come in un elaboratore
 * di testi: correggere una parola in neretto la lascia in neretto.
 */
export function trattiDopoLaCorrezione(tratti: OcrTratto[], prima: string, dopo: string): OcrTratto[] {
  if (!tratti.length || prima === dopo) return tratti
  const stili: OcrTratto[] = []
  for (const tratto of tratti) for (let indice = 0; indice < tratto.testo.length; indice += 1) stili.push(tratto)
  if (stili.length !== prima.length) return []
  let testa = 0
  while (testa < prima.length && testa < dopo.length && prima[testa] === dopo[testa]) testa += 1
  let coda = 0
  while (coda < prima.length - testa && coda < dopo.length - testa && prima[prima.length - 1 - coda] === dopo[dopo.length - 1 - coda]) coda += 1
  const modello = stili[testa - 1] ?? stili[testa] ?? tratti[0]
  const nuovi = [
    ...stili.slice(0, testa),
    ...Array.from({ length: dopo.length - testa - coda }, () => modello),
    ...stili.slice(prima.length - coda),
  ]
  return unisci(nuovi.map((stile, indice) => ({ ...stile, testo: dopo[indice] })))
}

/** Un comando della barra agisce su tutto il pezzo: su ogni tratto. */
export function trattiConFormato(tratti: OcrTratto[], patch: Partial<OcrFormat>): OcrTratto[] {
  const cambi: Partial<OcrTratto> = {}
  for (const chiave of CHIAVI_TRATTO) {
    if (chiave in patch) Object.assign(cambi, { [chiave]: patch[chiave] })
  }
  return Object.keys(cambi).length ? unisci(tratti.map((tratto) => ({ ...tratto, ...cambi }))) : tratti
}
