// Bozze dei prossimi passi: tipi del payload di /api/v1/ui/fascicoli/<id>/bozze-passi e
// abbinamento puro bozza → passo (stessa azione e stessa data «entro» della Lettura).
// Le bozze le prepara il server in sfondo: qui si mostrano e basta.
import type { PassoLettura } from './letturaFascicolo'

export type StatoBozza = 'pronta' | 'modificata' | 'dati_cambiati' | 'superata'

export interface BozzaPasso {
  chiave: string
  tipo: string
  titolo: string
  modello: string
  modelloTitolo: string
  norma: string
  daCompletare: string[]
  passi: { azione: string; entro: string }[]
  stato: StatoBozza
  statoEtichetta: string
  documentoId: string
  apri: string
  pdf?: string
  preparataIl: string
  aggiornataIl: string
  datiCambiatiIl: string
}

export interface BozzePayload {
  ok?: boolean
  bozze?: BozzaPasso[]
  avviso?: string
}

export function bozzeAttive(bozze: BozzaPasso[]): BozzaPasso[] {
  return bozze.filter((bozza) => bozza.stato !== 'superata')
}

export function bozzeDelPasso(bozze: BozzaPasso[], passo: Pick<PassoLettura, 'azione' | 'entro'>): BozzaPasso[] {
  return bozzeAttive(bozze).filter((bozza) => bozza.passi.some((voce) => voce.azione === passo.azione && voce.entro === (passo.entro || '')))
}

// Le bozze che nessun passo visibile mostra (es. credito da riscuotere su un fascicolo definito).
export function bozzeSenzaPasso(bozze: BozzaPasso[], passi: Pick<PassoLettura, 'azione' | 'entro'>[]): BozzaPasso[] {
  return bozzeAttive(bozze).filter((bozza) => !passi.some((passo) => bozzeDelPasso([bozza], passo).length > 0))
}

export function etichettaStatoBozza(bozza: BozzaPasso): { testo: string; tono: 'success' | 'primary' | 'warning' } {
  if (bozza.stato === 'dati_cambiati') {
    return { testo: `Modificata da te · dati del fascicolo cambiati${bozza.datiCambiatiIl ? ` il ${bozza.datiCambiatiIl}` : ''}: verifica la bozza`, tono: 'warning' }
  }
  if (bozza.stato === 'modificata') return { testo: 'Modificata da te', tono: 'primary' }
  return { testo: `Preparata il ${bozza.aggiornataIl || bozza.preparataIl}`, tono: 'success' }
}

export function riassuntoDaCompletare(bozza: BozzaPasso): string {
  const quanti = bozza.daCompletare.length
  if (!quanti) return 'Tutti i dati compilati dalle fonti del fascicolo'
  return quanti === 1 ? '1 dato da completare' : `${quanti} dati da completare`
}
