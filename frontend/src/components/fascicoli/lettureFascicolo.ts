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

export interface FattoDaConfermare {
  id: string
  campo: string
  etichetta: string
  valore: string
  valore_letto: string
  oggetto_id: string
  tipo: string
  contesto: string
  prove: { codice: string; esito: string; dettaglio: string }[]
}

export interface ArchivioLetture {
  totale: number
  per_verifica: Record<'verificata' | 'plausibile' | 'respinta' | 'corretta' | 'ignorata', number>
  udienze: number
  termini: number
  notifiche: number
  prove_notifica: number
  ruoli: number
  eventi: number
  per_motore: { documenti: number; pec: number }
  da_confermare: FattoDaConfermare[]
  lettura_automatica: { in_corso: boolean; da_leggere: number; completa: boolean; ultima_lettura: string; ultima_lettura_it: string; in_attesa?: OggettoInAttesa[] }
  collaudo_lettore: { eseguito: boolean; superato?: boolean; corretti?: number; totali?: number; eseguito_il_it?: string; casi_falliti?: string[] }
}

// Un oggetto del fascicolo che i motori devono ancora leggere, con il perché.
export interface OggettoInAttesa {
  tipo: string
  oggetto_id: string
  nome: string
  motore: string
  motivo: string
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
  archivio?: ArchivioLetture
}

export interface EsitoAggiornamentoLetture {
  messaggio: string
  restano: number
  ocr_accodati: number
  da_leggere_prima: number
}

const CAMPI: Record<string, string> = { udienza: 'data di udienza', termine: 'termine', data: 'data', scadenza: 'scadenza', deposito: 'data di deposito', notifica: 'data di notifica' }
const LETTORI_ARCHIVIO = new Set(['motore_documenti', 'motore_pec'])

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
  const automatica = letture.archivio?.lettura_automatica
  if (automatica?.completa) {
    return { testo: `Tutto letto e collaudato: ${letture.oggetti} tra documenti e PEC. Si rilegge solo ciò che cambia.`, tono: 'success' }
  }
  if (automatica?.da_leggere) {
    return { testo: `Da leggere nell'archivio: ${automatica.da_leggere} oggett${automatica.da_leggere === 1 ? 'o' : 'i'}.`, tono: 'warning' }
  }
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
  if (letture.archivio?.lettura_automatica?.completa) return []
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

export function lettoriDaMostrare(letture: LettureFascicolo): LettoreStato[] {
  if (!letture.archivio?.lettura_automatica?.completa) return letture.lettori
  const archivio = letture.lettori.filter((voce) => LETTORI_ARCHIVIO.has(voce.lettore))
  return archivio.length ? archivio : letture.lettori.filter((voce) => !voce.da_leggere || voce.letti)
}

export function anomalieOrdinate(anomalie: AnomaliaLettura[]): AnomaliaLettura[] {
  const peso = { alta: 0, media: 1, bassa: 2 }
  return [...anomalie].sort((a, b) => peso[a.gravita] - peso[b.gravita] || a.oggetto.localeCompare(b.oggetto))
}


// L'archivio in una riga: quanti dati i motori hanno letto e verificato, quanti aspettano conferma.
export function riassuntoArchivio(archivio: ArchivioLetture | undefined): { testo: string; tono: TonoLettura } {
  if (!archivio || !archivio.totale) {
    if (archivio?.lettura_automatica?.in_corso) return { testo: 'Lettura automatica in corso: i motori stanno leggendo documenti e PEC.', tono: 'info' }
    if (archivio?.lettura_automatica?.da_leggere) return { testo: `Lettura automatica in attesa: ${archivio.lettura_automatica.da_leggere} oggetti da leggere.`, tono: 'warning' }
    return { testo: 'Nessun dato letto: i motori non hanno ancora trovato date, ruoli o prove di notifica.', tono: 'neutral' }
  }
  const verificati = archivio.per_verifica.verificata + archivio.per_verifica.corretta
  const pezzi: string[] = []
  if (archivio.udienze) pezzi.push(`${archivio.udienze} udienz${archivio.udienze === 1 ? 'a' : 'e'}`)
  if (archivio.termini) pezzi.push(`${archivio.termini} termin${archivio.termini === 1 ? 'e' : 'i'}`)
  if (archivio.prove_notifica) pezzi.push(`${archivio.prove_notifica} prov${archivio.prove_notifica === 1 ? 'a' : 'e'} di notifica`)
  if (archivio.ruoli) pezzi.push(`${archivio.ruoli} numer${archivio.ruoli === 1 ? 'o' : 'i'} di ruolo`)
  const dettaglio = pezzi.length ? ` (${pezzi.join(', ')})` : ''
  const daConfermare = archivio.da_confermare.length
  if (daConfermare) return { testo: `${verificati} dati verificati dal software${dettaglio} · ${daConfermare} da confermare.`, tono: 'warning' }
  return { testo: `${verificati} dati verificati dal software${dettaglio}, nessuno da confermare.`, tono: verificati ? 'success' : 'neutral' }
}

export function fraseCollaudo(collaudo: ArchivioLetture['collaudo_lettore'] | undefined): { testo: string; tono: TonoLettura } {
  if (!collaudo || !collaudo.eseguito) return { testo: 'Collaudo del lettore non ancora eseguito: gira ogni notte con l\'OCR reale su pagine di prova.', tono: 'neutral' }
  const quando = collaudo.eseguito_il_it ? ` il ${collaudo.eseguito_il_it}` : ''
  if (collaudo.superato) return { testo: `Collaudo del lettore superato${quando}: ${collaudo.corretti}/${collaudo.totali} pagine di prova lette correttamente.`, tono: 'success' }
  const falliti = collaudo.casi_falliti?.length ? ` Non superato: ${collaudo.casi_falliti.join('; ')}.` : ''
  return { testo: `Collaudo del lettore NON superato${quando}: ${collaudo.corretti}/${collaudo.totali} pagine corrette.${falliti} Le date lette dall'OCR vanno controllate.`, tono: 'danger' }
}

export function fraseLetturaAutomatica(stato: ArchivioLetture['lettura_automatica'] | undefined): string {
  if (!stato) return ''
  if (stato.in_corso) return 'Lettura automatica in corso.'
  if (stato.da_leggere) {
    // Quale oggetto manca, non solo quanti: «1 oggetto da leggere» non dice all'avvocato che cosa fare.
    const attesa = (stato.in_attesa ?? []).slice(0, 3).map((voce) => `«${voce.nome}» (${voce.motivo})`).join(', ')
    const quali = attesa ? `: ${attesa}${(stato.in_attesa ?? []).length > 3 ? ` e altri ${(stato.in_attesa ?? []).length - 3}` : ''}` : ''
    return `Lettura automatica: ${stato.da_leggere} oggett${stato.da_leggere === 1 ? 'o' : 'i'} ancora da leggere${quali} (il prossimo giro parte da solo).`
  }
  return stato.ultima_lettura_it ? `Tutto letto e collaudato; ultima lettura automatica ${stato.ultima_lettura_it}. Si rilegge solo ciò che cambia.` : 'Tutto letto: si rilegge solo ciò che cambia.'
}
