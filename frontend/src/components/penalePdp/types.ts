export type Tono = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export type Voce = { codice: string; descrizione: string }

export type Registro = {
  id: string; ufficio: string; ufficioEtichetta: string; ufficioNome: string; registro: string
  numero: string; anno: string; magistrato: string; corrente: boolean; protocollo: string
}

export type Soggetto = {
  id: string; nome: string; iniziali: string; ruolo: string; ruoloEtichetta: string; codiceFiscale: string; natura: string; fonte: string
}

export type Esito = { codice: string; livello: 'errore' | 'avviso' | 'ok' | 'info'; messaggio: string; file: string }

export type FileDeposito = {
  ruolo: string; nome: string; oggetto: string; documentoId: string; tipoAtto: string; dimensione: number; sha256: string
  firmatari: Array<{ nome: string; codiceFiscale: string; formato: string; scaduto: boolean }>
}

export type VoceVerifica = { campo: string; etichetta: string; atteso: string; letto: string; ok: boolean }
export type VerificaRicevuta = { verificabile?: boolean; corrispondenti?: number; totale?: number; messaggio?: string; voci?: VoceVerifica[] }

export type Deposito = {
  id: string; atto: string; attoNome: string; principale: boolean; ufficio: string; ufficioEtichetta: string; registro: string
  soggetti: Array<{ id?: string; nome: string; ruolo: string; ruoloEtichetta?: string }>
  file: FileDeposito[]; dati: Record<string, unknown>
  controlli: { pronto?: boolean; errori?: number; avvisi?: number; esiti?: Esito[]; procuraSpeciale?: boolean }
  stato: string; statoEtichetta: string; statoTono: Tono; definitivo: boolean; identificativo: string; dataInvio: string
  dataArrivo: string; motivazione: string; ricevutaId: string; esitoId: string
  verificaRicevuta: VerificaRicevuta
  fonte: string; creatoIl: string; aggiornatoIl: string
}

export type Canale = { obbligatorio: boolean; etichetta: string; dal: string; nota: string; fonte: string }

export type Quadro = {
  ok: boolean; message?: string
  fascicolo: { id: string; titolo: string; tribunale: string; rg: string }
  procedimento: {
    id: string; autorizzato: boolean; fonteAutorizzazione: string; autorizzatoIl: string; avocatoPg: boolean
    ufficio: string; ufficioEtichetta: string; avvocato: string; cfAvvocato: string
  }
  canale: Canale | null
  registri: Registro[]
  soggetti: Soggetto[]
  depositi: Deposito[]
  udienze: Array<{ id: string; quando: string; ufficio: string; aula: string; luogo: string; causale: string; inAgenda: boolean }>
  documenti: Array<{ id: string; nome: string; dimensione: number; firmato: boolean; data: string }>
  avvisoIndagini: boolean
  uffici: Voce[]; ruoli: Voce[]; fasi: Voce[]; registriTipi: Voce[]
  stati: Array<{ codice: string; etichetta: string; descrizione: string }>
  link: { pdp: string; avvisi: string; accessoAtti: string }
}

export type AttoCatalogo = { codice: string; nome: string; principale: boolean; fase: string; norma: string; confermaRicezione: boolean }

export type Campo = { chiave: string; etichetta: string; tipo: string; obbligatorio: boolean; opzioni: string[]; nota: string }

export type SchedaAtto = {
  codice: string; nome: string; menu: string; norma: string; principale: boolean; fase: string
  uffici: string[]; ruoli: string[] | null; confermaRicezione: boolean; procuraSpeciale: string
  unSoloSoggetto: boolean; contestuali: boolean; campi: Campo[]; fonte: string
}

export type SchedaPortale = {
  sezioni: Array<{ titolo: string; voci: Array<{ etichetta: string; valore: string; nota?: string }> }>
  canale: Canale
}

export type FileScelto = { documentoId: string; ruolo: string; oggetto: string; tipoAtto: string }

export const RUOLI_FILE: Array<{ valore: string; etichetta: string }> = [
  { valore: 'principale', etichetta: 'Atto principale (firmato)' },
  { valore: 'contestuale', etichetta: 'Atto contestuale (firmato)' },
  { valore: 'abilitante', etichetta: 'Atto abilitante' },
  { valore: 'allegato', etichetta: 'Allegato' },
]

export function dataOra(iso: string): string {
  if (!iso) return ''
  const [giorno, ora] = iso.split('T')
  const [a, m, g] = giorno.split('-')
  return `${g}/${m}/${a}${ora ? ` ${ora.slice(0, 5)}` : ''}`
}

export function dimensione(byte: number): string {
  if (byte >= 1024 * 1024) return `${(byte / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(byte / 1024))} KB`
}

export type ProcedimentoPdp = {
  id: string; titolo: string; cliente: string; tribunale: string; href: string; accessoAttiHref: string
  protocollo: string; ufficio: string; ufficioEtichetta: string; autorizzato: boolean; canale: Canale | null
  conteggi: Record<string, number>; prossimaUdienza: string
  ultimo: { atto: string; stato: string; statoEtichetta: string; statoTono: Tono; identificativo: string; dataInvio: string; motivazione: string } | null
  azione: { codice: string; testo: string; tono: Tono }
}

export type PanoramicaPdp = {
  ok: boolean; generatoIl: string
  totali: { procedimenti: number; nonAutorizzati: number; inPreparazione: number; inAttesaEsito: number; daRifare: number; accolti: number; rigettati: number; udienze: number }
  procedimenti: ProcedimentoPdp[]
  calendario: Array<{ dal: string; uffici: string[]; inVigore: boolean }>
  fonteCalendario: string
  link: { pdp: string; avvisi: string }
}
