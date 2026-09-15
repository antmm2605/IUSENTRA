// Registro delle letture del fascicolo: tipi del payload di
// /api/v1/ui/fascicoli/<id>/letture e trasformazioni pure per il pannello.
// Nessun accesso alla rete e nessun DOM: si prova con node --test.

import type { TonoLettura } from './letturaFascicolo'

export type StatoLetturaOggetto = 'letto' | 'da_leggere' | 'da_rileggere' | 'errore' | 'in_corso' | 'non_leggibile'

export interface LettoreStato {
  lettore: string
  etichetta: string
  versione: string
  letti: number
  da_leggere: number
  errori: number
  ultima_lettura: string
  ultima_lettura_it: string
  completa: boolean
}

export interface OggettoLettura {
  tipo: 'documento' | 'pec' | 'allegato_pec'
  oggetto_id: string
  nome: string
  etichetta: string
  sha256: string
  impronta: string
  data_oggetto: string
  letture: Record<string, StatoLetturaOggetto>
}

export interface AnomaliaLettura {
  id: string
  tipo: string
  oggetto_id: string
  oggetto: string
  lettore: string
  lettore_etichetta: string
  campo: string
  valore_letto: string
  valore_proposto: string
  contesto: string
  motivo: string
  codice: string
  gravita: 'alta' | 'media' | 'bassa'
  stato: string
  creata_il_it: string
}

export interface NovitaLetture {
  prima_vista: boolean
  visto_il: string
  visto_il_it: string
  nuovi: OggettoLettura[]
  cambiati: OggettoLettura[]
  rimossi: { tipo: string; oggetto_id: string }[]
}

export interface LettureFascicolo {
  impronta: string
  oggetti: number
  tutto_letto: boolean
  lettori: LettoreStato[]
  per_oggetto: OggettoLettura[]
  novita: NovitaLetture
  anomalie: AnomaliaLettura[]
  anomalie_aperte: number
}

export interface EsitoAggiornamentoLetture {
  messaggio: string
  restano: number
  ocr_accodati: number
  da_leggere_prima: number
}

const CAMPI: Record<string, string> = { udienza: 'data di udienza', termine: 'termine', data: 'data', scadenza: 'scadenza', deposito: 'data di deposito', notifica: 'data di notifica' }

export function etichettaCampo(campo: string): string {
  return CAMPI[campo] || campo.replace(/_/g, ' ')
}

export function tonoGravita(gravita: AnomaliaLettura['gravita']): TonoLettura {
  if (gravita === 'alta') return 'danger'
  if (gravita === 'media') return 'warning'
  return 'info'
}

// Il riassunto in una riga: «tutto letto», oppure quanti oggetti aspettano quali lettori.
export function riassuntoLetture(letture: LettureFascicolo): { testo: string; tono: TonoLettura } {
  if (!letture.oggetti) return { testo: 'Nessun documento o PEC da leggere.', tono: 'neutral' }
  const inAttesa = letture.lettori.filter((voce) => voce.da_leggere > 0 || voce.errori > 0)
  if (!inAttesa.length) return { testo: `Tutto letto: ${letture.oggetti} tra documenti e PEC, nessuna rilettura necessaria.`, tono: 'success' }
  const errori = inAttesa.reduce((totale, voce) => totale + voce.errori, 0)
  const pezzi = inAttesa.map((voce) => `${voce.da_leggere + voce.errori} per ${voce.etichetta.toLowerCase()}`)
  return { testo: `Da leggere: ${pezzi.join(', ')}${errori ? ` · ${errori} non leggibili` : ''}.`, tono: errori ? 'danger' : 'warning' }
}

// Le novità dall'ultima apertura di questo utente, già in frase.
export function fraseNovita(novita: NovitaLetture): string {
  if (novita.prima_vista) return ''
  const pezzi: string[] = []
  const conta = (voci: OggettoLettura[], singolare: string, plurale: string) => {
    if (!voci.length) return
    const documenti = voci.filter((voce) => voce.tipo === 'documento').length
    const pec = voci.length - documenti
    const parti: string[] = []
    if (documenti) parti.push(`${documenti} document${documenti === 1 ? 'o' : 'i'}`)
    if (pec) parti.push(`${pec} PEC`)
    pezzi.push(`${voci.length === 1 ? singolare : plurale} ${parti.join(' e ')}`)
  }
  conta(novita.nuovi, 'nuovo', 'nuovi')
  conta(novita.cambiati, 'cambiato', 'cambiati')
  if (novita.rimossi.length) pezzi.push(`${novita.rimossi.length} rimoss${novita.rimossi.length === 1 ? 'o' : 'i'}`)
  if (!pezzi.length) return `Nessuna novità dall'ultima apertura${novita.visto_il_it ? ` (${novita.visto_il_it})` : ''}.`
  return `Dall'ultima apertura${novita.visto_il_it ? ` (${novita.visto_il_it})` : ''}: ${pezzi.join(' · ')}.`
}

// Gli oggetti che aspettano almeno un lettore, con l'elenco dei lettori mancanti.
export function oggettiInAttesa(letture: LettureFascicolo): { oggetto: OggettoLettura; lettori: string[] }[] {
  const etichette = new Map(letture.lettori.map((voce) => [voce.lettore, voce.etichetta]))
  return letture.per_oggetto
    .map((oggetto) => ({
      oggetto,
      lettori: Object.entries(oggetto.letture)
        .filter(([, stato]) => stato !== 'letto' && stato !== 'non_leggibile')
        .map(([lettore]) => etichette.get(lettore) || lettore),
    }))
    .filter((voce) => voce.lettori.length)
}

export function anomalieOrdinate(anomalie: AnomaliaLettura[]): AnomaliaLettura[] {
  const peso = { alta: 0, media: 1, bassa: 2 }
  return [...anomalie].sort((a, b) => peso[a.gravita] - peso[b.gravita] || a.oggetto.localeCompare(b.oggetto))
}
