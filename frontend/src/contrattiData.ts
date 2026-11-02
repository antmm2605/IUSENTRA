import { apiJson, apiPostJson } from './lib/apiClient'

const BASE = '/api/v1/ui/contratti'

export type Fatti = Record<string, boolean | string | number>

export type VoceCatalogo = {
  id: string
  nome: string
  qualificazione: string
  forma: string
  riferimenti: string[]
  guidato: boolean
  pubblico_ufficiale: boolean
}

export type Area = { id: string; titolo: string; voci: VoceCatalogo[] }

export type Novita = { id: string; titolo: string; norma: string; decorrenza: string; aree: string[] }

export type Catalogo = {
  ok: boolean
  message?: string
  aree: Area[]
  totale: number
  data_ricognizione: string
  stato_verifica: string
  fonte_ufficiale_consultazione: string
  stati: string[]
  regole_comuni: {
    regole_comuni: [string, string][]
    dimensione_internazionale: [string, string][]
    scheda_controllo: [string, string, string][]
    novita_2026: Novita[]
  }
}

export type Domanda = { id: string; testo: string; tipo: string; opzioni: string[] }
export type Variante = { id: string; nome: string; riferimenti: string[]; forma: string }

export type Famiglia = {
  ok: boolean
  message?: string
  contratto: {
    id: string
    nome: string
    area: string
    riferimenti: string[]
    qualificazione: string
    forma: string
    note: string
    varianti: Variante[]
    domande: Domanda[]
  }
  domande_comuni: Domanda[]
  ruoli: string[]
  campi: { id: string; etichetta: string }[]
  clausole: { chiave: string; titolo: string; norma: string }[]
}

export type Esito = { id: string; esito: string; messaggio: string; norma: string }

export type Valutazione = {
  ok?: boolean
  variante: { id: string; nome: string } | null
  bloccanti: Esito[]
  punti_avvocato: Esito[]
  adempimenti: Esito[]
  avvisi: Esito[]
  controlli_sospesi: Esito[]
  domande_aperte: string[]
  forma: { forma: string; richiede_pubblico_ufficiale: boolean; nota: string }
  novita: Novita[]
  scheda: Record<string, unknown>
  pronto_per_redazione: boolean
}

export type Articolo = { numero: number; chiave: string; titolo: string; testo: string; norma: string; da_completare: boolean }

export type Bozza = {
  titolo: string
  luogo_data: string
  comparenti: { ruolo: string; testo: string }[]
  premesse: string[]
  articoli: Articolo[]
  firme: string[]
  approvazione_specifica: boolean
  allegati: string[]
  da_completare: string[]
  pronta: boolean
}

export type Parte = { nome?: string; codice_fiscale?: string; sede?: string; pec?: string; rappresentante?: string }

export type DatiPratica = { parti?: Parte[]; campi?: Record<string, string>; premesse?: string[]; allegati?: string[] }

export type Decisione = { valutato: boolean; nota: string }

export type DocumentoPratica = { documento_id: string; nome: string; fascicolo_id: string; stato: string; il: string }

export type Pratica = {
  id: string
  contratto_id: string
  contratto_nome: string
  titolo: string
  fascicolo_id: string
  cliente: string
  fatti: Fatti
  dati: DatiPratica
  decisioni: Record<string, Decisione>
  note: string
  stato: string
  creata_il: string
  aggiornata_il: string
  storico: { il: string; autore: string }[]
  documenti: DocumentoPratica[]
}

export type SintesiPratica = Pick<Pratica, 'id' | 'titolo' | 'contratto_id' | 'contratto_nome' | 'stato' | 'fascicolo_id' | 'cliente' | 'aggiornata_il'>

export type FascicoloScelta = { id: string; numero: string; titolo: string; cliente: string }

export type RispostaPratica = { ok: boolean; message?: string; pratica?: Pratica; valutazione?: Valutazione; bozza?: Bozza }

export const ETICHETTE_STATO: Record<string, string> = {
  bozza: 'Bozza',
  in_revisione: 'In revisione',
  approvato: 'Approvato',
  firmato: 'Firmato',
  archiviato: 'Archiviato',
}

export const ETICHETTE_FORMA: Record<string, string> = {
  libera: 'Forma libera',
  scritta: 'Forma scritta',
  scritta_ad_substantiam: 'Scritta a pena di nullità',
  scrittura_autenticata: 'Scrittura privata autenticata',
  atto_pubblico: 'Atto pubblico',
}

export const ETICHETTE_QUALIFICAZIONE: Record<string, string> = {
  tipico: 'Tipico',
  atipico: 'Atipico',
  misto: 'Misto',
  accessorio: 'Accessorio',
  atto_collegato: 'Atto collegato',
}

export type RottaContratti =
  | { modo: 'catalogo' }
  | { modo: 'nuovo'; contrattoId: string }
  | { modo: 'pratica'; praticaId: string }

export function rottaContratti(pathname: string): RottaContratti | null {
  const path = pathname.replace(/\/+$/, '')
  if (/^\/contratti$/i.test(path)) return { modo: 'catalogo' }
  const nuovo = path.match(/^\/contratti\/nuovo\/([a-z0-9_]+)$/i)
  if (nuovo) return { modo: 'nuovo', contrattoId: nuovo[1] }
  const pratica = path.match(/^\/contratti\/pratiche\/([a-z0-9]+)$/i)
  if (pratica) return { modo: 'pratica', praticaId: pratica[1] }
  return null
}

const NON_DISPONIBILE = { ok: false, message: 'Servizio contratti non raggiungibile.' }

export function dataOraItaliana(iso: string): string {
  if (!iso) return ''
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return iso
  return data.toLocaleString('it-IT', { timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function dataItaliana(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return match ? `${match[3]}/${match[2]}/${match[1]}` : iso
}

export const getCatalogo = () => apiJson<Catalogo>(`${BASE}/catalogo`, { ...NON_DISPONIBILE, aree: [], totale: 0 } as unknown as Catalogo)
export const getFamiglia = (id: string) => apiJson<Famiglia>(`${BASE}/famiglie/${encodeURIComponent(id)}`, NON_DISPONIBILE as Famiglia)
export const getPratiche = () => apiJson<{ ok: boolean; pratiche: SintesiPratica[] }>(`${BASE}/pratiche`, { ok: false, pratiche: [] })
export const getPratica = (id: string) => apiJson<RispostaPratica>(`${BASE}/pratiche/${encodeURIComponent(id)}`, NON_DISPONIBILE)
export const getFascicoli = (q: string) => apiJson<{ ok: boolean; fascicoli: FascicoloScelta[] }>(`${BASE}/fascicoli?q=${encodeURIComponent(q)}`, { ok: false, fascicoli: [] }, { activity: false })

export const valutaFatti = (id: string, fatti: Fatti) =>
  apiPostJson<Valutazione & { ok: boolean; message?: string }>(`${BASE}/famiglie/${encodeURIComponent(id)}/valutazione`, { fatti }, NON_DISPONIBILE as unknown as Valutazione & { ok: boolean }, { activity: false })

export const creaPratica = (corpo: { contratto_id: string; titolo: string; fascicolo_id: string; cliente: string }) =>
  apiPostJson<RispostaPratica>(`${BASE}/pratiche`, corpo, NON_DISPONIBILE, { activity: 'Creazione della pratica…' })

export const salvaPratica = (id: string, corpo: Partial<Pratica>) =>
  apiPostJson<RispostaPratica>(`${BASE}/pratiche/${encodeURIComponent(id)}`, corpo, NON_DISPONIBILE, { method: 'PUT', activity: 'Salvataggio…' })

export const eliminaPratica = (id: string) =>
  apiPostJson<{ ok: boolean; message?: string }>(`${BASE}/pratiche/${encodeURIComponent(id)}`, {}, NON_DISPONIBILE, { method: 'DELETE', activity: 'Eliminazione…' })

export const salvaNelFascicolo = (id: string) =>
  apiPostJson<{ ok: boolean; message?: string; documento?: DocumentoPratica }>(`${BASE}/pratiche/${encodeURIComponent(id)}/fascicolo`, {}, NON_DISPONIBILE, { activity: 'Salvataggio nel fascicolo…' })

export const urlBozzaDocx = (id: string) => `${BASE}/pratiche/${encodeURIComponent(id)}/bozza.docx`
export const urlNotaDocx = (id: string) => `${BASE}/pratiche/${encodeURIComponent(id)}/nota.docx`

export const anteprimaBozza = (id: string, dati: DatiPratica, fatti: Fatti) =>
  apiPostJson<{ ok: boolean; message?: string; bozza?: Bozza }>(`${BASE}/famiglie/${encodeURIComponent(id)}/bozza`, { dati, fatti }, NON_DISPONIBILE, { activity: false })
