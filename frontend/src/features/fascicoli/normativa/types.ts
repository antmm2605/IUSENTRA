/** Normativa del fascicolo: forma della risposta di `/api/v1/ui/fascicoli/<id>/normativa`. */
export type NormativaVoce = {
  id: string
  norma: string
  rubrica: string
  estratto: string
  url: string
  fonte: string
  verifica: string
  consultataIl: string
  letturaInterna: string
  archivio: { urn?: string; articolo?: string }
  /** true: testo nell’archivio; false: solo collegamento; null: da verificare all’apertura. */
  testoInArchivio?: boolean | null
  perche: string[]
}

export type NormativaGruppo = {
  id: 'procedura' | 'termini' | 'documenti'
  titolo: string
  descrizione: string
  voci: NormativaVoce[]
  vuoto: string
}

export type NormativaFascicolo = {
  versione: string
  contesto: { rito: string; deposito: string; ufficio: string; termini: number; documenti: number; catalogati: number }
  materie: string[]
  gruppi: NormativaGruppo[]
  totale: number
  fascicolo: { id: string; titolo: string }
}

export type TestoArchivio = { testo: string; versione: string; importatoIl: string; atto: string }

export type ArticoloTrovato = { id: number; number: string; title: string; act_title: string }
