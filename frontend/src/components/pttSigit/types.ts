export type Riga = {
  etichetta: string
  valore: string
  stato: 'ok' | 'manca' | 'facoltativo' | 'verifica'
  nota: string
  copia: boolean
}

export type Scheda = {
  tipo: string
  nome: string
  link: string
  sezioni: Array<{ titolo: string; righe: Riga[] }>
  mancanti: string[]
  daVerificare: string[]
  pronto: boolean
}

export type Esito = { codice: string; livello: 'errore' | 'avviso'; messaggio: string }

export type DocumentoPtt = {
  id: string
  nome: string
  ruolo: 'atto' | 'allegato' | 'escludi'
  tipologia: string
  descrizione: string
  dimensione: number
  firma: string
  sha256: string
  esiti: Esito[]
  bloccante: boolean
  sceltaAvvocato: boolean
}

export type AttoImpugnato = {
  tipo?: string
  numero?: string
  ufficio?: string
  dataNotifica?: string
  periodo?: string
  tributo?: string
  sanzioni?: string
  indeterminabile?: boolean
  materia?: string
  tributo_tipo?: string
}

export type ProcedimentoPtt = {
  corte?: string
  grado?: string
  posizione?: 'ricorrente' | 'resistente'
  rg?: string
  atto?: string
  notificaRicorso?: string
  pubblicaUdienza?: string
  sospensione?: boolean
  prova?: boolean
  atti?: AttoImpugnato[]
  cutModalita?: string
  cutEsenzione?: string
  cutEstremi?: string
  cutData?: string
  sentenza?: { corte?: string; numero?: string; sezione?: string; anno?: string; data?: string }
  note?: string
}

export type Termine = { id: string; titolo: string; scadenza: string; norma: string; perentorio: boolean; giorni: number }

export type DepositoPtt = {
  id: string
  tipo: string
  stato: string
  creatoIl: string
  aggiornatoIl: string
  ricevuta?: string
  rg?: string
  note?: string
}

export type Sede = { codice: string; grado: string; nome: string; citta: string; provincia: string; regione: string; staccata: boolean; codiceF23: string; pec: string; fonte: string }

export type CatalogoPtt = {
  ok: boolean
  portale: string
  telecontenzioso: string
  registrazione: string
  consultazione: string
  assistenza: string
  numeroVerde: string
  sedi: Sede[]
  depositi: Array<{ id: string; nome: string; grado: string; principale: string; rg: boolean; passi: string[] }>
  attiPrincipali: string[]
  altriAtti: string[]
  allegati: string[]
  naturaGiuridica: Array<{ codice: string; descrizione: string }>
  attiImpugnati: string[]
  materie: string[]
  tributi: string[]
  tipiEnte: string[]
  pubblicaUdienza: string[]
  modalitaCut: string[]
  statiNir: string[]
}

export type PartePtt = { id: string; denominazione: string; codiceFiscale: string; natura?: string; tipoEnte?: string; pec: string; provincia?: string }

export type QuadroPtt = {
  ok: boolean
  fascicolo: { id: string; titolo: string; oggetto: string; ufficio: string }
  procedimento: ProcedimentoPtt
  propostaCorte: string
  avvocato: { nome: string; pec: string; codiceFiscale: string }
  parti: { ricorrenti: PartePtt[]; resistenti: PartePtt[] }
  cut: { righe: Array<{ atto: number; valore: number | null; indeterminabile: boolean; cut: number; nota: string }>; base: number; maggiorazione: number; totale: number; nota: string }
  termini: Termine[]
  documenti: DocumentoPtt[]
  depositi: DepositoPtt[]
  tipoSuggerito: string
  scheda: Scheda
  linkPortale: string
  telecontenzioso: string
}

export type Controllo = {
  file: Array<{ id: string; nome: string; ruolo: string; dimensione: number; esiti: Esito[]; bloccante: boolean }>
  deposito: Esito[]
  conforme: boolean
  controllatoIl: string
}

export type Connessione = { raggiungibile: boolean; millisecondi: number; messaggio: string; verificatoIl: string; url: string }
