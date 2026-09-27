import {
  elenco,
  leggiPubblico,
  messaggiDa,
  numero,
  oggetto,
  percorsoInterno,
  scriviPubblico,
  testo,
  vero,
  type Grezzo,
  type MessaggioPagina,
  type RispostaPubblica,
} from './pubblicoTokenApi'

/** Portale del cliente con link personale (`/portale/<token>`): dati e azioni. */

export type Sezione = 'home' | 'privacy' | 'documenti' | 'economici' | 'anagrafica'

export const SEZIONI: Sezione[] = ['home', 'privacy', 'documenti', 'economici', 'anagrafica']

export type Permessi = {
  vediAnagrafica: boolean
  modificaAnagrafica: boolean
  vediFascicoli: boolean
  vediEconomici: boolean
  accettaPreventivi: boolean
  firmaConferimenti: boolean
  vediAppuntamenti: boolean
  vediScadenze: boolean
  caricaDocumenti: boolean
  firmaPrivacy: boolean
  maxUploadMb: number
}

export type Intestazione = {
  studioNome: string
  clienteNome: string
  permessi: Permessi
  privacyFirmata: boolean
  dataFirmaPrivacy: string
}

export type AzioneRichiesta = { kind: 'preventivo' | 'conferimento'; id: string; title: string; subtitle: string; buttonLabel: string }

export type Tracker = {
  currentLabel: string
  percent: number
  steps: { label: string; complete: boolean }[]
  lastEvent: string
  nextEvent: string
}

export type Fascicolo = { id: string; titolo: string; stato: string; tipo: string; numeroRg: string; tribunale: string; tracker: Tracker | null }
export type Appuntamento = { titolo: string; giorno: string; mese: string; ora: string; luogo: string }
export type Scadenza = { titolo: string; data: string; priorita: string; perentorio: boolean }
export type Statistiche = { preventivi: number; conferimenti: number; parcelle: number; totale: number }
export type VoceCronologia = { kind: string; numero: string; titolo: string; data: string; fascicoloLabel: string; totale: string }

export type DatiHome = {
  intestazione: Intestazione
  oggi: string
  azioni: AzioneRichiesta[]
  fascicoli: Fascicolo[]
  appuntamenti: Appuntamento[]
  scadenze: Scadenza[]
  stats: Statistiche
  cronologia: VoceCronologia[]
}

export type RiepilogoCalcolo = { praticaLabel: string; regola: string; gradoSede: string; complianceLabel: string; complianceTone: string; tableCode: string }
export type RiepilogoWorkflow = { channelLabel: string; nextStepLabel: string; riferimenti: string[] }

export type DocumentoEconomico = {
  kind: 'preventivo' | 'conferimento' | 'parcella'
  id: string
  numero: string
  stato: string
  data: string
  scadenza: string
  totale: string
  descrizione: string
  calcolo: RiepilogoCalcolo | null
  workflow: RiepilogoWorkflow | null
  canAccept: boolean
  canSign: boolean
  pdfUrl: string
}

export type DatiEconomici = {
  intestazione: Intestazione
  stats: Statistiche
  azioni: AzioneRichiesta[]
  preventivi: DocumentoEconomico[]
  conferimenti: DocumentoEconomico[]
  parcelle: DocumentoEconomico[]
}

export type DatiDocumenti = { intestazione: Intestazione; fascicoli: { id: string; titolo: string; numeroRg: string }[] }

export type DatiAnagrafica = {
  intestazione: Intestazione
  anagrafica: { nomeCompleto: string; tipo: 'PF' | 'PG'; dataNascita: string; codiceFiscale: string; partitaIva: string; indirizzo: string }
  recapiti: { cellulare: string; telefono: string; email: string }
}

export type DatiSezione =
  | { sezione: 'home'; dati: DatiHome }
  | { sezione: 'privacy'; dati: Intestazione }
  | { sezione: 'documenti'; dati: DatiDocumenti }
  | { sezione: 'economici'; dati: DatiEconomici }
  | { sezione: 'anagrafica'; dati: DatiAnagrafica }

export type StatoSezione =
  | { tipo: 'caricamento' }
  | { tipo: 'pronto'; contenuto: DatiSezione }
  | { tipo: 'scaduto' }
  | { tipo: 'negato'; messaggio: string }
  | { tipo: 'errore'; messaggio: string }

// ------------------------------------------------------------------ indirizzi

const SUFFISSI: Record<Sezione, string> = {
  home: '',
  privacy: '/privacy',
  documenti: '/documenti',
  economici: '/economici',
  anagrafica: '/anagrafica',
}

function tokenUrl(token: string): string {
  return encodeURIComponent(token)
}

export function percorsoSezione(token: string, sezione: Sezione): string {
  return `/portale/${tokenUrl(token)}${SUFFISSI[sezione]}`
}

function api(token: string, suffisso = ''): string {
  return `/api/v1/pubblico/portale/${tokenUrl(token)}${suffisso}`
}

export function sezioneDaPercorso(pathname: string): Sezione {
  const parti = pathname.split('/').filter(Boolean)
  const ultima = parti.length >= 3 ? parti[2] : ''
  return (SEZIONI as string[]).includes(ultima) ? (ultima as Sezione) : 'home'
}

export function sezioneValida(value: unknown): Sezione {
  const raw = testo(value)
  return (SEZIONI as string[]).includes(raw) ? (raw as Sezione) : 'home'
}

// ------------------------------------------------------------------ normalizzazione

function permessi(raw: unknown): Permessi {
  const p = oggetto(raw)
  return {
    vediAnagrafica: vero(p.vedi_anagrafica),
    modificaAnagrafica: vero(p.modifica_anagrafica),
    vediFascicoli: vero(p.vedi_fascicoli),
    vediEconomici: vero(p.vedi_economici),
    accettaPreventivi: vero(p.accetta_preventivi),
    firmaConferimenti: vero(p.firma_conferimenti),
    vediAppuntamenti: vero(p.vedi_appuntamenti),
    vediScadenze: vero(p.vedi_scadenze),
    caricaDocumenti: vero(p.carica_documenti),
    firmaPrivacy: vero(p.firma_privacy),
    maxUploadMb: numero(p.max_upload_mb, 10),
  }
}

export function intestazione(raw: Grezzo): Intestazione {
  const privacy = oggetto(raw.privacy)
  return {
    studioNome: testo(raw.studio_nome),
    clienteNome: testo(oggetto(raw.cliente).nome_completo),
    permessi: permessi(raw.permessi),
    privacyFirmata: vero(privacy.firmata),
    dataFirmaPrivacy: testo(privacy.data_firma),
  }
}

function azione(raw: unknown): AzioneRichiesta {
  const a = oggetto(raw)
  return {
    kind: testo(a.kind) === 'conferimento' ? 'conferimento' : 'preventivo',
    id: testo(a.id),
    title: testo(a.title),
    subtitle: testo(a.subtitle),
    buttonLabel: testo(a.button_label),
  }
}

function tracker(raw: unknown): Tracker | null {
  const t = oggetto(raw)
  if (!Object.keys(t).length) return null
  return {
    currentLabel: testo(t.current_label),
    percent: Math.max(0, Math.min(100, numero(t.percent))),
    steps: elenco(t.steps).map((s) => ({ label: testo(oggetto(s).label), complete: vero(oggetto(s).complete) })),
    lastEvent: testo(t.last_event),
    nextEvent: testo(t.next_event),
  }
}

function statistiche(raw: unknown): Statistiche {
  const s = oggetto(raw)
  return { preventivi: numero(s.preventivi), conferimenti: numero(s.conferimenti), parcelle: numero(s.parcelle), totale: numero(s.totale) }
}

function home(raw: Grezzo): DatiHome {
  const economici = oggetto(raw.economici)
  return {
    intestazione: intestazione(raw),
    oggi: testo(raw.oggi),
    azioni: elenco(raw.azioni_richieste).map(azione),
    fascicoli: elenco(raw.fascicoli).map((item) => {
      const f = oggetto(item)
      return {
        id: testo(f.id), titolo: testo(f.titolo), stato: testo(f.stato), tipo: testo(f.tipo),
        numeroRg: testo(f.numero_rg), tribunale: testo(f.tribunale), tracker: tracker(f.tracker),
      }
    }),
    appuntamenti: elenco(raw.appuntamenti).map((item) => {
      const a = oggetto(item)
      return { titolo: testo(a.titolo), giorno: testo(a.giorno), mese: testo(a.mese), ora: testo(a.ora), luogo: testo(a.luogo) }
    }),
    scadenze: elenco(raw.scadenze).map((item) => {
      const s = oggetto(item)
      return { titolo: testo(s.titolo), data: testo(s.data), priorita: testo(s.priorita), perentorio: vero(s.perentorio) }
    }),
    stats: statistiche(economici.stats),
    cronologia: elenco(economici.cronologia).map((item) => {
      const v = oggetto(item)
      return {
        kind: testo(v.kind), numero: testo(v.numero), titolo: testo(v.titolo), data: testo(v.data),
        fascicoloLabel: testo(v.fascicolo_label), totale: testo(v.totale),
      }
    }),
  }
}

function calcolo(raw: unknown): RiepilogoCalcolo | null {
  const c = oggetto(raw)
  if (!Object.keys(c).length) return null
  return {
    praticaLabel: testo(c.pratica_label), regola: testo(c.regola), gradoSede: testo(c.grado_sede),
    complianceLabel: testo(c.compliance_label), complianceTone: testo(c.compliance_tone), tableCode: testo(c.table_code),
  }
}

function workflow(raw: unknown): RiepilogoWorkflow | null {
  const w = oggetto(raw)
  if (!Object.keys(w).length) return null
  return { channelLabel: testo(w.channel_label), nextStepLabel: testo(w.next_step_label), riferimenti: elenco(w.riferimenti).map(testo).filter(Boolean) }
}

function documento(raw: unknown): DocumentoEconomico {
  const d = oggetto(raw)
  const kind = testo(d.kind)
  return {
    kind: kind === 'conferimento' || kind === 'parcella' ? kind : 'preventivo',
    id: testo(d.id), numero: testo(d.numero), stato: testo(d.stato), data: testo(d.data), scadenza: testo(d.scadenza),
    totale: testo(d.totale), descrizione: testo(d.descrizione), calcolo: calcolo(d.calcolo), workflow: workflow(d.workflow),
    canAccept: vero(d.can_accept), canSign: vero(d.can_sign), pdfUrl: percorsoInterno(d.pdf_url),
  }
}

function economici(raw: Grezzo): DatiEconomici {
  return {
    intestazione: intestazione(raw),
    stats: statistiche(raw.stats),
    azioni: elenco(raw.azioni_richieste).map(azione),
    preventivi: elenco(raw.preventivi).map(documento),
    conferimenti: elenco(raw.conferimenti).map(documento),
    parcelle: elenco(raw.parcelle).map(documento),
  }
}

function documenti(raw: Grezzo): DatiDocumenti {
  return {
    intestazione: intestazione(raw),
    fascicoli: elenco(raw.fascicoli).map((item) => {
      const f = oggetto(item)
      return { id: testo(f.id), titolo: testo(f.titolo), numeroRg: testo(f.numero_rg) }
    }),
  }
}

export function anagrafica(raw: Grezzo): DatiAnagrafica {
  const a = oggetto(raw.anagrafica)
  const r = oggetto(raw.recapiti)
  return {
    intestazione: intestazione(raw),
    anagrafica: {
      nomeCompleto: testo(a.nome_completo), tipo: testo(a.tipo) === 'PG' ? 'PG' : 'PF', dataNascita: testo(a.data_nascita),
      codiceFiscale: testo(a.codice_fiscale), partitaIva: testo(a.partita_iva), indirizzo: testo(a.indirizzo),
    },
    recapiti: { cellulare: testo(r.cellulare), telefono: testo(r.telefono), email: testo(r.email) },
  }
}

function contenuto(sezione: Sezione, raw: Grezzo): DatiSezione {
  switch (sezione) {
    case 'privacy':
      return { sezione, dati: intestazione(raw) }
    case 'documenti':
      return { sezione, dati: documenti(raw) }
    case 'economici':
      return { sezione, dati: economici(raw) }
    case 'anagrafica':
      return { sezione, dati: anagrafica(raw) }
    default:
      return { sezione: 'home', dati: home(raw) }
  }
}

/** Stato della schermata da una risposta: 410 link scaduto, 403 sezione negata. */
export function statoDaRisposta(risposta: RispostaPubblica, sezione: Sezione): StatoSezione {
  if (risposta.status === 410) return { tipo: 'scaduto' }
  if (risposta.status === 403) return { tipo: 'negato', messaggio: risposta.messaggio || 'Sezione non disponibile per questo accesso.' }
  if (risposta.status !== 200) {
    return { tipo: 'errore', messaggio: risposta.messaggio || 'Dati del portale non disponibili. Ricarica la pagina o contatta lo studio.' }
  }
  return { tipo: 'pronto', contenuto: contenuto(sezione, risposta.dati) }
}

export async function caricaSezione(token: string, sezione: Sezione, signal?: AbortSignal): Promise<StatoSezione> {
  return statoDaRisposta(await leggiPubblico(api(token, SUFFISSI[sezione]), signal), sezione)
}

// ------------------------------------------------------------------ azioni

export type EsitoAzione = { status: number; ok: boolean; messaggio: string; messaggi: MessaggioPagina[]; sezione: string; dati: Grezzo }

function esito(risposta: RispostaPubblica): EsitoAzione {
  return {
    status: risposta.status,
    ok: risposta.status === 200 && risposta.dati.ok !== false,
    messaggio: risposta.messaggio,
    messaggi: messaggiDa(risposta.dati.messaggi),
    sezione: testo(risposta.dati.sezione),
    dati: risposta.dati,
  }
}

export async function firmaConsensoPrivacy(token: string): Promise<EsitoAzione> {
  return esito(await scriviPubblico(api(token, '/privacy'), { consenso: true }))
}

export async function inviaDocumenti(token: string, files: File[], idFascicolo: string, note: string): Promise<EsitoAzione> {
  const form = new FormData()
  for (const file of files) form.append('files[]', file, file.name)
  form.append('id_fascicolo', idFascicolo)
  form.append('note', note)
  return esito(await scriviPubblico(api(token, '/documenti/upload'), form))
}

export async function eseguiAzioneEconomica(token: string, azioneRichiesta: Pick<AzioneRichiesta, 'kind' | 'id'>): Promise<EsitoAzione> {
  const id = encodeURIComponent(azioneRichiesta.id)
  const suffisso = azioneRichiesta.kind === 'conferimento' ? `/conferimenti/${id}/firma` : `/preventivi/${id}/accetta`
  return esito(await scriviPubblico(api(token, suffisso), {}))
}

export async function salvaRecapiti(token: string, recapiti: DatiAnagrafica['recapiti']): Promise<EsitoAzione> {
  return esito(await scriviPubblico(api(token, '/anagrafica'), recapiti))
}

export function elencoStringhe(value: unknown): string[] {
  return elenco(value).map(testo).filter(Boolean)
}
