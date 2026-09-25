export type Voce = { codice: string; descrizione: string }

export type Riga = {
  etichetta: string
  valore: string
  stato: 'ok' | 'manca' | 'facoltativo' | 'verifica'
  nota: string
  copia: boolean
  excel?: string
  descrizione?: string
}

export type Sezione = { titolo: string; righe: Riga[] }

export type Scheda = {
  tipo: string
  nome: string
  link: string
  sezioni: Sezione[]
  mancanti: string[]
  daVerificare: string[]
  pronto: boolean
}

export type Esito = { codice: string; livello: 'errore' | 'avviso'; messaggio: string }

export type DocumentoPat = {
  id: string
  nome: string
  ruolo: string
  dimensione: number
  sha256: string
  firma: string
  nomeProposto: string
  descrizione: string
  bloccante: boolean
  esiti: Esito[]
  sceltaAvvocato: boolean
}

export type ParteFormweb = {
  id: string
  ruolo: string
  tipologia: string
  cognome: string
  nome: string
  denominazione: string
  codiceFiscale: string
  pec: string
  fonte: string
  sceltaAvvocato?: boolean
}

export type Procedimento = {
  sede?: string
  tipoRicorso?: string
  nrg?: string
  posizione?: string
  oggetto?: string
  pnrr?: boolean
  anteCausam?: boolean
  cassazionista?: boolean
  cuTipologia?: string
  esenzione?: string
  valore?: number | null
  istanze?: string[]
  attoImpugnato?: { organo?: string; tipo?: string; numero?: string; anno?: string }
}

export type EsitoRiepilogo = {
  firma: string
  titolo: string
  sede: string
  impronte: string[]
  documenti: Array<{ nome: string; sha256: string; atteso: boolean; nelRiepilogo: boolean }>
  estranee: string[]
  leggibile: boolean
  conforme: boolean
}

export type DepositoPat = {
  id: string
  tipo: string
  stato: string
  creatoIl: string
  aggiornatoIl: string
  identificativo?: string
  note?: string
  riepilogo?: EsitoRiepilogo
}

export type QuadroPat = {
  ok: boolean
  fascicolo: { id: string; titolo: string; oggetto: string; ufficio: string }
  procedimento: Procedimento
  avvocato: { nome: string; pec: string; codiceFiscale: string }
  parti: ParteFormweb[]
  contributo: { importo: number | null; nota: string; versamento?: string; esenzione?: string }
  documenti: DocumentoPat[]
  depositi: DepositoPat[]
  scheda: Scheda
  tipiRicorso: Voce[]
  linkPortale: string
  tipoSuggerito?: string
  letti?: {
    nrg?: DatoLetto & { rg: string; altri?: string[] }
    sede?: DatoLetto
  }
}

export type DatoLetto = { valore: string; verifica: string; documenti: string[] }

export type CatalogoPat = {
  ok: boolean
  sedi: Array<Voce & { ambito: string }>
  depositi: Array<{ id: string; nome: string; percorso: string; passi: string[]; nrg: boolean; link: string }>
  tipiRicorsoTar: Voce[]
  tipiRicorsoCds: Voce[]
  esenzioniTar: Voce[]
  esenzioniCds: Voce[]
  istanze: string[]
  contributo: string[]
}

export type Connessione = { ok: boolean; raggiungibile: boolean; stato: number; millisecondi: number; messaggio: string }
