/**
 * Annulla e ripeti nella revisione del testo riconosciuto.
 *
 * Correggere un atto e' fatto di tentativi: un rientro provato e tolto, una
 * sostituzione di troppo, un pezzo eliminato per sbaglio. Ogni cambio dei
 * blocchi entra nella storia; le lettere battute di seguito nello stesso pezzo
 * sono un cambio solo, come in Word, altrimenti annullare vorrebbe dire
 * tornare indietro di una lettera alla volta.
 */
import type { OcrBlock } from './ocrBlocks'

export const PASSI_MASSIMI = 200
/** Le battute nello stesso pezzo entro questo tempo sono un cambio solo. */
export const PAUSA_TRA_CAMBI_MS = 1500

export type Storia = {
  indietro: OcrBlock[][]
  avanti: OcrBlock[][]
  ultimo: { chiave: string; quando: number } | null
}

export function storiaVuota(): Storia {
  return { indietro: [], avanti: [], ultimo: null }
}

/** Registra lo stato di prima di un cambio. `chiave` unisce le battute di seguito. */
export function registra(storia: Storia, prima: OcrBlock[], chiave = '', ora = Date.now()): Storia {
  const unisci = Boolean(chiave && storia.ultimo?.chiave === chiave && ora - storia.ultimo.quando < PAUSA_TRA_CAMBI_MS)
  const indietro = unisci ? storia.indietro : [...storia.indietro, prima].slice(-PASSI_MASSIMI)
  return { indietro, avanti: [], ultimo: { chiave, quando: ora } }
}

export function annulla(storia: Storia, attuale: OcrBlock[]): { storia: Storia; blocchi: OcrBlock[] } | null {
  const precedente = storia.indietro[storia.indietro.length - 1]
  if (!precedente) return null
  return {
    storia: { indietro: storia.indietro.slice(0, -1), avanti: [...storia.avanti, attuale], ultimo: null },
    blocchi: precedente,
  }
}

export function ripeti(storia: Storia, attuale: OcrBlock[]): { storia: Storia; blocchi: OcrBlock[] } | null {
  const successivo = storia.avanti[storia.avanti.length - 1]
  if (!successivo) return null
  return {
    storia: { indietro: [...storia.indietro, attuale], avanti: storia.avanti.slice(0, -1), ultimo: null },
    blocchi: successivo,
  }
}
