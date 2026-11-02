// Forma dei passaggi spiegabili e delle regole dello studio servite da
// /api/v1/ui/fascicoli/<id>/passaggi e /api/v1/ui/regole-studio (pct/passaggi).

export type StatoPassaggio = 'eseguito' | 'proposto' | 'da_confermare' | 'da_chiedere' | 'escluso_dallo_studio'

export type NormaPassaggio = {
  id: string
  norma: string
  titolo?: string
  url?: string
  reader_url?: string
  verifica?: string
  estratto?: string
}

export type CampoPassaggio = {
  etichetta: string
  valore: string
  vincolato: boolean
  motivoVincolo: string
  valoreSoftware: string
  regolaStudioId: string
}

export type RiferimentoRegola = {
  id: string
  etichetta: string
  descrizione: string
  ambito: string
  autore: string
  motivo: string
  rifiuto?: { vincolo: string; motivo: string; norme: NormaPassaggio[] }
}

export type Passaggio = {
  chiave: string
  produttore: string
  ordine: number
  titolo: string
  stato: StatoPassaggio
  statoEtichetta: string
  statoSoftware: StatoPassaggio
  regola: { id: string; descrizione: string }
  norme: NormaPassaggio[]
  prove: Array<{ tipo: string; estratto: string; fonte: string; riferimento: string }>
  dati: Array<{ etichetta: string; valore: string; fonte: string }>
  campi: Record<string, CampoPassaggio>
  vincoli: string[]
  confidenza: number | null
  contesto: { fascicoloId: string; ufficio: string; giudice: string; materia: string }
  href: string
  regoleStudioApplicate: RiferimentoRegola[]
  regoleStudioRifiutate: RiferimentoRegola[]
}

export type AzioneRegola = 'modifica_valore' | 'non_proporre' | 'chiedi_sempre' | 'non_chiedere_conferma'
export type AmbitoRegola = 'fascicolo' | 'giudice' | 'ufficio' | 'tipo'

export type RegolaStudio = {
  id: string
  regolaId: string
  produttore: string
  azione: AzioneRegola
  azioneEtichetta: string
  campo: string
  valore: string
  ambito: AmbitoRegola
  ambitoEtichetta: string
  fascicoloId: string
  ufficio: string
  giudice: string
  materia: string
  motivo: string
  autoreNome: string
  attiva: boolean
  creataIl: string
  etichetta: string
  descrizione: string
  applicazioni?: number
  passaggioOriginale: { titolo?: string; produttore?: string }
}

export type Correzione = {
  chiave: string
  azione: AzioneRegola
  ambito: AmbitoRegola
  campo?: string
  valore?: string
  motivo?: string
}

export type EsitoCorrezione = {
  ok: boolean
  errore?: string
  rifiutata?: boolean
  rifiuto?: { vincolo: string; motivo: string; norme: NormaPassaggio[] }
  regola?: RegolaStudio
}
