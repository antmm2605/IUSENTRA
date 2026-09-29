export type Fonte = { norma?: string; estratto?: string; url?: string }
export type Passo = { n: number; chiave: string; titolo: string; descrizione: string; fatto: boolean }
export type DocumentoUdienza = { indice: number; etichetta: string; stato: string; statoEtichetta: string; firmato: boolean; href: string }
export type Verifica = { id: string; testo: string; fatta: boolean; fonte: Fonte }
export type TermineAssegnato = { descrizione: string; data: string; perentorio: boolean; id_scadenza?: string }

export type SchedaUdienza = {
  ok: boolean; message?: string; id: string; titolo: string; stato: string; completata: boolean; passoCorrente: number; passi: Passo[]
  udienza: { dataOra: string; quando: string; luogo: string; ufficio: string; giudice: string; sezione: string; rg: string; collegamento: string; agendaHref: string }
  causa: { cliente: string; controparte: string; avvocatoControparte: string; oggetto: string; fascicolo: { etichetta?: string; href?: string }; idCliente: string }
  termini: Array<{ titolo: string; data: string; perentorio: boolean; href: string }>
  attivita: Array<{ data: string; titolo: string; descrizione: string }>
  tipoUdienza: string; tipi: Array<{ value: string; label: string; senzaPresenza: boolean }>; verifiche: Verifica[]
  avvisoAssenza: { testo: string; fonte: Fonte }
  documenti: DocumentoUdienza[]
  campi: Record<string, string | boolean>
  esito: { valore: string; rinvioData: string; rinvioOra: string; noteVerbale: string; azioni: string; termini: TermineAssegnato[]; rinvioAgendaHref: string }
  esiti: Array<{ value: string; label: string }>
  messaggioClienteHref: string; puoModificare?: boolean
}

export const dataIt = (iso: string) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : '')
