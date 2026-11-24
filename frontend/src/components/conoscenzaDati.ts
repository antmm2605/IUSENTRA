// Tipi e funzioni pure della sezione «Conoscenza» (schede di istituto per materia).

export type Fonte = {
  tipo: 'norma' | 'pronuncia'
  chiave: string
  citazione: string
  rubrica?: string
  comma?: string
  ancora?: string
  url?: string
  aggiornamento?: string
  versione?: string
  tipo_testo?: string
  data?: string
  norma?: string
  stato?: 'vigente' | 'abrogata'
  nota_abrogazione?: string
}
export type Voce = { testo: string; fonti: Fonte[]; provenienza: string; verifica: string; etichetta?: string; orientamento?: string; calcolo?: { quantita: number; unita: string; calcolatore: string; sospensione_feriale: boolean } }
export type Sezione = { stato: 'compilata' | 'mancante'; voci: Voce[]; motivo?: string }
export type Strumento = { tipo: string; id: string; titolo: string; collegamento: string }
export type Revisione = { revisione: number; data: string; motivo: string }
export type Scheda = {
  id: string; titolo: string; materia: string; istituto: string; sintesi: string; revisione: number; ultimo_controllo: string; generata_il: string
  stato_verifica: string; norme_abrogate?: { citazione: string; abrogata_da: string; decorrenza: string; sede_vigente: string }[]; sezioni: Record<string, Sezione>; strumenti: Strumento[]; lacune: string[]; fonti: Fonte[]; storia: Revisione[]; regole: string[]
}
export type VoceIndice = { id: string; titolo: string; materia: string; sintesi: string; fonti_dirette: number; stato: string; sezioni_compilate: number; sezioni_mancanti: string[]; revisione: number; ultimo_controllo: string; frammento?: string }
export type Catalogo = { materie: { materia: string; schede: VoceIndice[]; conteggi: Record<string, number> }[]; totale: number; conteggi: Record<string, number>; aggiornato_il: string; puo_annotare: boolean }
export type StatoAttuale = { stato: string; motivi: string[] }
export type Annotazione = { id: string; sezione: string; voce: string; testo: string; esito: string; attore: string; creato_il: string; revisione_scheda: number; voce_presente: boolean; scheda_cambiata_dopo: boolean }
export type Evento = { evento_id: string; ts: string; operazione: string; scheda: string; titolo: string; materia: string; esito: string; revisione?: number; revisione_precedente?: number; motivo?: string; generate?: number; aggiornate?: number; invariate?: number; rinominate?: number; ritirate?: number }
export type Norma = { citazione: string; rubrica: string; testo: string; inizio: number; fine: number; url: string; aggiornamento: string }

export const SEZIONI: [string, string][] = [
  ['presupposti', 'Presupposti'], ['eccezioni', 'Eccezioni e tranelli'], ['termini', 'Termini'], ['rimedi', 'Rimedi e forme'],
  ['giudice_rito', 'Giudice e rito'], ['prove_oneri', 'Prove e oneri'], ['documenti', 'Documenti e dati da verificare'],
  ['questioni', 'Questioni interpretative'], ['orientamenti', 'Giurisprudenza che cita le norme (orientamenti da valutare)'],
]
export const STATI: Record<string, { etichetta: string; tono: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  verificata: { etichetta: 'Verificata', tono: 'success' },
  lacune: { etichetta: 'Con lacune', tono: 'warning' },
  da_riesaminare: { etichetta: 'Da riesaminare', tono: 'danger' },
}
export const OPERAZIONI: Record<string, string> = {
  generazione: 'Generazione', aggiornamento: 'Aggiornamento', rinomina: 'Rinomina', ritiro: 'Ritiro', controllo: 'Controllo',
}

/** Data e ora in formato italiano (gg/mm/aaaa hh:mm) da una data ISO; vuoto se non leggibile. */
export function dataOraIt(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** Il testo della norma diviso in prima, passaggio citato, dopo (per evidenziare l'ancora). */
export function divisioneAncora(norma: Pick<Norma, 'testo' | 'inizio' | 'fine'>): [string, string, string] {
  const { testo, inizio, fine } = norma
  if (inizio < 0 || fine <= inizio || fine > testo.length) return [testo, '', '']
  return [testo.slice(0, inizio), testo.slice(inizio, fine), testo.slice(fine)]
}

export function chiaveFonte(f: Fonte): string {
  return `${f.tipo}:${f.chiave}`
}
