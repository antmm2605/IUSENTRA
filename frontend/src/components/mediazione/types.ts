export type Row = Record<string, string>
export type Document = { id: string; nome: string; preview: string }
export type ModuleSource = { titolo: string; url: string; acquisito_il: string; organismo_numero: string; tipo: string; sha256: string }
export type OrganismModule = { documento: string; nome: string; fonte: ModuleSource; copie_compilate: string[] }
export type Procedure = {
  id?: string; versione: number; titolo: string; stato: string; regime: string; modalita: string
  organismo_numero: string; sede_id: string; parti: Row[]; incontri: Row[]; proroghe: Row[]
  controlli?: { id: string; ok: boolean; messaggio: string }[]
  calendario?: Record<string, string | boolean>
  modulo_fonte?: ModuleSource
  moduli_organismo?: OrganismModule[]
  allegati_documenti?: string[]
  [key: string]: unknown
}
export type Data = {
  ok: boolean; message?: string; can_write: boolean; id_fascicolo: string
  procedimenti: Procedure[]; documenti: Document[]; proposta: Partial<Procedure>
  fonti: { titolo: string; url: string }[]
  audit: { id: string; timestamp: string; attore: string; versione: number; azione: string }[]
}
export type Organism = {
  numero: string; nome: string; sito: string
  territori: { regione: string; provincia: string; comune: string }[]
}
export type OrganismDetail = {
  numero: string; nome: string; sito: string; risorse_verificate_il: string
  sedi: { id: string; region: string; province: string; city: string; address: string; postal_code: string; legal: boolean }[]
  risorse: { url: string; label: string; kind: string; source_url: string }[]
  controllo_fonti?: SourceCheck
}
export type SourceCheck = {
  stato: string; revisione: number; ultimo_controllo?: string; ultima_acquisizione?: string
  prossimo_controllo?: string; ultima_variazione?: string; invio_autorizzato: boolean
  fonti?: { url: string; status: number }[]
  problemi?: { error: string }[]
  documentazione_api?: { url: string; label: string }[]
}
export type Preview = { name: string; url: string; downloadUrl: string }
export const text = (p: Procedure, key: string) => typeof p[key] === 'string' ? p[key] as string : ''
export const states: Record<string, string> = { bozza: 'In preparazione', pronta: 'Pronta per il deposito', depositata: 'Depositata', in_corso: 'In corso', accordo: 'Conclusa con accordo', mancato_accordo: 'Conclusa senza accordo', ritirata: 'Ritirata' }
export const regimes: Record<string, string> = { volontaria: 'Volontaria', obbligatoria: 'Condizione di procedibilità', demandata: 'Demandata dal giudice', clausola: 'Clausola contrattuale o statutaria' }
export const modes: Record<string, string> = { presenza: 'In presenza', remoto: 'Partecipazione da remoto', telematica: 'Procedimento telematico' }
export const newProcedure = (proposta: Partial<Procedure>): Procedure => ({ versione: 0, titolo: '', stato: 'bozza', regime: 'volontaria', modalita: 'presenza', organismo_numero: '', sede_id: '', parti: [], incontri: [], proroghe: [], ...proposta })
