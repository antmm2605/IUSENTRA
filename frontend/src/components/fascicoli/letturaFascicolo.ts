import type { RiscontriProcessualiData } from "./RiscontriProcessuali"
// Lettura del fascicolo: tipi del payload di /api/v1/ui/fascicoli/<id>/lettura e
// le trasformazioni pure che il pannello usa (urgenze, presìdi, scelta delle
// sezioni). Nessun accesso alla rete e nessun DOM: si prova con node --test.

export type UrgenzaPasso = 0 | 1 | 2 | 3

export interface FonteLettura {
  id: string
  norma: string
  titolo: string
  url: string
  verifica: string
  reader_url?: string
  estratto: string
}

export interface PassoLettura {
  urgenza: UrgenzaPasso
  azione: string
  motivo: string
  entro: string
  scaduto?: boolean
  fonte: string
  norma: string
  fonti: FonteLettura[]
  href: string
  template: string
}

export interface FaseLettura {
  codice: string
  descrizione: string
  prove: string[]
  incoerenze: string[]
  prossima_udienza: string
  stato_dichiarato: string
}

export interface EventoLettura {
  data: string
  data_it: string
  categoria: string
  titolo: string
  dettaglio: string
  esito: string
  fonte: string
}

export interface SchedaFase {
  codice: string
  nome: string
  descrizione?: string
  prova?: string
  fonti: string[]
  adempimenti?: { azione: string; termine: string; fonti: string[]; template?: string; parte?: string }[]
}

export interface SchedaProcedurale {
  codice?: string
  canale?: string
  nome: string
  base: string
  fasi: SchedaFase[]
  tempistiche?: { evento: string; termine: string; fonti: string[] }[]
  fonti: FonteLettura[]
}

export interface VerificheAutomatiche {
  in_corso?: boolean
  eseguita_il?: string
  eseguita_il_it?: string
  completata_il?: string
  esiti?: {
    pec?: { esaminate: number; collegate: number; job_eseguiti: number; da_confermare: { id: string; oggetto: string; corrispondenza: string; motivo?: string }[] }
    notifiche?: { esaminati: number; riallineati: number }
    depositi?: { pendenti: number; esito: string; controllati?: number; aggiornati?: number; errori?: number; polling?: { esito: string; controllati?: number; aggiornati?: number; pendenti?: number; errori?: number } }
    documenti?: { documenti: number; letti?: number; indicizzati: number; errori: number; da_acquisire?: number; esito: string; indice_pronti?: number; indice_totale?: number; indice_errori?: number }
  }
  errori?: Record<string, string>
  lacune_conoscenza?: LacunaConoscenza[]
}

export interface LacunaConoscenza {
  tipo: 'rito' | 'canale' | 'norma'
  chiave: string
  descrizione: string
}

export type EsitoDispositivo = { sentenza: string; documento_id?: string; data: string; esito: string; per_il_cliente: string; motivo_esito?: string; brano_dispositivo?: string }

export function hrefFonteDispositivo(fascicoloId: string, documentoId: string | undefined): string {
  if (!fascicoloId || !documentoId) return ''
  return `/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/${encodeURIComponent(documentoId)}/visualizza`
}

const ESITI_SENTENZA: Record<string, string> = {
  accoglimento: 'Accoglimento', accoglimento_parziale: 'Accoglimento parziale', rigetto: 'Rigetto',
  inammissibile: 'Inammissibilità', improcedibile: 'Improcedibilità', estinzione: 'Estinzione',
  cessata_materia: 'Cessazione della materia del contendere', incompetenza: 'Incompetenza',
  difetto_giurisdizione: 'Difetto di giurisdizione',
}
const ESITI_CLIENTE: Record<string, string> = {
  favorevole: 'favorevole al cliente', sfavorevole: 'sfavorevole al cliente', parziale: 'parzialmente favorevole al cliente',
}

export function descriviEsitoDispositivo(esito?: EsitoDispositivo | null): string {
  if (!esito || !ESITI_SENTENZA[esito.esito]) return ''
  const difettoInteresse = esito.esito === 'improcedibile' && esito.motivo_esito === 'difetto_interesse_sopravvenuto'
  const dispositivo = difettoInteresse ? 'Improcedibilità per sopravvenuto difetto di interesse' : ESITI_SENTENZA[esito.esito]
  return [dispositivo, difettoInteresse ? '' : ESITI_CLIENTE[esito.per_il_cliente], esito.data && `decisione del ${esito.data}`]
    .filter(Boolean).join(' · ')
}

export interface LetturaFascicolo {
  aggiornamento_pendente?: boolean
  versione: string
  generata_il: string
  intestazione: {
    numero: string; titolo: string; rg: string; ufficio: string; cliente: string; controparte: string
    stato: string; stato_codice: string; da_archiviare: boolean; valore_causa: string; area: string; rito: string
    parti: Record<string, string[]>
  }
  oggetto: { oggetto_dichiarato: string; atti_principali: { etichetta: string; nome: string; data: string }[]; domanda: { etichetta: string; data: string; petitum: string } | null }
  cronologia: EventoLettura[]
  depositi: {
    totale: number
    messaggi_archiviati?: { atto: string; data: string; documento_id: string }[]
    importati?: unknown[]
    perfezionati: unknown[]
    in_corso: unknown[]
    falliti: unknown[]
    tutti: {
      atto: string; data: string; fase: string; attesa: string; perfezionato: boolean
      fase_procedurale: string; prova_attesa: string
      reinvio_accettato?: {
        nuova_busta: string
        pec_richiesta: string
        pec_rifiuto: string
        pec_consegna: string
        pec_accettazione: string
      } | null
    }[]
  }
  scadenze?: { totale: number; scadute: number; prossimi30: number; successive: number }
  notifiche: { prove_documentali?: number; totale: number; perfezionate: unknown[]; aperte: unknown[]; fallite: unknown[]; tutte: { atto: string; data: string; stato_etichetta: string; fase_procedurale: string; destinatari: string[] }[] }
  pec: { conteggio?: ConteggioPec; totale: number; collegate: number; per_corrispondenza: Record<string, number>; da_controllare: PecDaControllare[]; termini_da_registrare: unknown[]; udienze_da_registrare: unknown[]; ultima: { data: string; oggetto: string; mittente: string } | null }
  documenti: { errori_lettura?: number; da_leggere_lettura?: number | null; totale: number; catalogati: number; confermati: number; proposti?: number; automatici?: number; da_verificare: unknown[]; non_indicizzati: unknown[]; da_acquisire?: unknown[]; conteggi: Record<string, number> }
  economico: {
    presente: boolean; preventivato_it: string; conferito_it: string; fatturato_it: string; incassato_it: string; saldo_aperto_it: string
    parcelle_scadute: { numero: string; totale_it: string; scadenza: string }[]; importo_scaduto_it: string; ha_incarico: boolean
    liquidato?: number; liquidato_it?: string; liquidazione_incasso?: '' | 'incassata' | 'parziale' | 'non_incassata'
    liquidazione?: { stato?: string; stato_etichetta?: string; data?: string; fonte?: string; fonte_href?: string }
    anticipazioni_da_recuperare?: number; anticipazioni_da_recuperare_it?: string
    bonifici?: { numero: string; totale_it: string; pagata_il: string }[]; incassato_bonifico_it?: string
    presidio_stato_etichetta?: string; sentenze_lette?: number
  }
  fase: FaseLettura
  percorso?: EsitoDispositivo | null
  prossimi_passi: PassoLettura[]
  stato_passi: { attivi: boolean; motivo: string }
  lacune: string[]
  letture_in_corso?: { totale: number; fonti: { tipo?: string; id?: string; nome: string; motivo?: string }[] }
  conoscenza: { versione: string; rito: SchedaProcedurale | Record<string, never>; deposito: SchedaProcedurale | Record<string, never>; notifiche: SchedaProcedurale[]; lacune?: LacunaConoscenza[] }
  verifiche?: VerificheAutomatiche
  narrativa: string
  ragionamento?: Pick<RiscontriProcessualiData, "conclusioni" | "impronta">
}

type PecDaControllare = {
  id: string
  data: string
  oggetto: string
  mittente: string
  motivi_controllo: string[]
  eventi?: { evento: string }[]
  termini?: { id: string; tipo: string; scadenza: string; norma: string; registrato: boolean; proposta_superata?: boolean }[]
  udienze?: { id: string; data: string; ora: string }[]
}

export const ESITI_DEPOSITI: Record<string, string> = {
  nessun_deposito_in_corso: 'nessun deposito in attesa di ricevute',
  pec_non_configurata: 'casella PEC dello studio non configurata: le ricevute non si leggono da sole',
  controllate: 'ricevute controllate',
  polling_fallito: 'controllo delle ricevute non riuscito',
}

// Un solo conteggio delle PEC (pct/fascicolo_pec_conteggio.py): collegate, da controllare, collegamento da confermare.
export interface ConteggioPec { collegate: number; da_controllare: number; da_confermare: number; esaminate: number; testo: string }

export interface RigaVerifica {
  presidio: string
  esito: string
  tono: TonoLettura
}

// Le righe della sezione «Verifiche automatiche»: che cosa ha controllato ogni presidio.
export function righeVerifiche(verifiche: VerificheAutomatiche | undefined, conteggio?: ConteggioPec): RigaVerifica[] {
  if (!verifiche?.eseguita_il) return []
  const esiti = verifiche.esiti || {}
  const righe: RigaVerifica[] = []
  if (esiti.pec) {
    const daConfermare = esiti.pec.da_confermare?.length || 0
    righe.push({ presidio: 'Presidio PEC', esito: conteggio ? `${esiti.pec.esaminate} messaggi esaminati · ${conteggio.testo}` : `${esiti.pec.esaminate} messaggi esaminati · ${esiti.pec.collegate} collegati al fascicolo${daConfermare ? ` · ${daConfermare} da confermare` : ''}`, tono: daConfermare ? 'warning' : 'success' })
  }
  if (esiti.notifiche) righe.push({ presidio: 'Presidio notifiche', esito: `${esiti.notifiche.esaminati} presidi esaminati · ${esiti.notifiche.riallineati} riallineati alle prove`, tono: 'success' })
  if (esiti.depositi) {
    const base = ESITI_DEPOSITI[esiti.depositi.esito] || esiti.depositi.esito
    const dettaglio = esiti.depositi.esito === 'controllate' ? `: ${esiti.depositi.controllati || 0} controllati, ${esiti.depositi.aggiornati || 0} aggiornati` : ''
    righe.push({ presidio: 'Presidio depositi', esito: `${base}${dettaglio}`, tono: esiti.depositi.esito === 'pec_non_configurata' || esiti.depositi.esito === 'polling_fallito' ? 'warning' : 'success' })
    if (esiti.depositi.polling) {
      const polling = esiti.depositi.polling
      righe.push({ presidio: 'Controllo ricevute dello studio', esito: polling.esito === 'controllate' ? `${polling.controllati || 0} depositi controllati · ${polling.aggiornati || 0} aggiornati · ${polling.pendenti || 0} pendenti in questo fascicolo` : (ESITI_DEPOSITI[polling.esito] || polling.esito), tono: polling.esito === 'polling_fallito' || polling.esito === 'pec_non_configurata' || polling.errori ? 'warning' : 'success' })
    }
  }
  if (esiti.documenti) {
    righe.push({
      presidio: 'Presidio documentale',
      esito: esiti.documenti.esito === 'tutti_letti' ? `tutti i ${esiti.documenti.documenti} documenti letti dall’archivio` : `${esiti.documenti.letti ?? 0} letti su ${esiti.documenti.documenti} · ${esiti.documenti.indicizzati} indicizzati ora · ${esiti.documenti.errori} non leggibili${esiti.documenti.da_acquisire ? ` · ${esiti.documenti.da_acquisire} da acquisire dal portale` : ''}`,
      tono: esiti.documenti.errori ? 'warning' : 'success',
    })
    if (esiti.documenti.indice_totale !== undefined) righe.push({ presidio: 'Indice dei documenti', esito: `${esiti.documenti.indice_pronti || 0} pronti su ${esiti.documenti.indice_totale}${esiti.documenti.indice_errori ? ` · ${esiti.documenti.indice_errori} errori` : ''}`, tono: esiti.documenti.indice_pronti !== esiti.documenti.indice_totale || esiti.documenti.indice_errori ? 'warning' : 'success' })
  }
  for (const [nome, errore] of Object.entries(verifiche.errori || {})) righe.push({ presidio: `Verifica ${nome}`, esito: `non completata: ${errore}`, tono: 'danger' })
  return righe
}

export type TonoLettura = 'danger' | 'warning' | 'info' | 'success' | 'neutral'

export const URGENZE: Record<UrgenzaPasso, { etichetta: string; tono: TonoLettura }> = {
  0: { etichetta: 'Subito', tono: 'danger' },
  1: { etichetta: 'Entro pochi giorni', tono: 'warning' },
  2: { etichetta: 'Prossimamente', tono: 'info' },
  3: { etichetta: 'Di governo', tono: 'neutral' },
}

export function etichettaUrgenza(urgenza: number): { etichetta: string; tono: TonoLettura } {
  const chiave = (urgenza >= 0 && urgenza <= 3 ? urgenza : 3) as UrgenzaPasso
  return URGENZE[chiave]
}

export const FASI_ETICHETTE: Record<string, string> = {
  stragiudiziale: 'Stragiudiziale o preparatoria',
  preparatoria: 'Atto redatto, da notificare',
  atto_notificato: 'Atto notificato',
  iscritta_a_ruolo: 'Iscritta a ruolo',
  trattazione: 'Trattazione',
  istruttoria: 'Istruttoria',
  decisoria: 'Decisoria',
  decisa: 'Decisa',
  estinta: 'Processo estinto',
  esecutiva: 'Esecutiva',
  chiusa: 'Chiusa',
}

export function etichettaFase(codice: string): string {
  return FASI_ETICHETTE[codice] || codice.replace(/_/g, ' ')
}

export function tonoFase(codice: string): TonoLettura {
  if (codice === 'chiusa') return 'neutral'
  if (codice === 'decisa' || codice === 'esecutiva' || codice === 'estinta') return 'warning'
  if (codice === 'stragiudiziale' || codice === 'preparatoria') return 'info'
  return 'success'
}

export interface PresidioCard {
  id: 'documenti' | 'depositi' | 'notifiche' | 'pec' | 'scadenze' | 'economico'
  titolo: string
  valore: string
  nota: string
  tono: TonoLettura
  href: string
}

// Le sei card dei presìdi: ognuna dice un numero, il suo significato e dove si agisce.
export function presidiCards(lettura: LetturaFascicolo): PresidioCard[] {
  const documenti = lettura.documenti
  const depositi = lettura.depositi
  const notifiche = lettura.notifiche
  const pec = lettura.pec
  const economico = lettura.economico
  const scadenzePassi = lettura.prossimi_passi.filter((passo) => passo.fonte === 'scadenziario')
  const scadute = lettura.scadenze?.scadute ?? scadenzePassi.filter((passo) => passo.scaduto).length
  const totaleScadenze = lettura.scadenze?.totale ?? scadenzePassi.length
  const proveNotifica = notifiche.prove_documentali || 0
  const daVerificare = documenti.da_verificare.length
  const daAcquisire = documenti.da_acquisire?.length || 0
  const erroriLettura = documenti.errori_lettura || 0
  const daLeggere = documenti.da_leggere_lettura ?? documenti.non_indicizzati.length
  const daCatalogare = Math.max(0, documenti.totale - documenti.catalogati)
  const proposti = documenti.proposti || 0
  const automatici = documenti.automatici || 0
  // Stesso calcolo del pannello «Catalogazione documentale»: automatici (certi dal contenuto), confermati, proposti.
  const certi = [automatici ? `${automatici} catalogati in automatico` : '', `${documenti.confermati} confermati`, proposti ? `${proposti} proposti da confermare` : ''].filter(Boolean).join(' · ')
  return [
    {
      id: 'documenti',
      titolo: 'Documentazione',
      valore: `${documenti.catalogati}/${documenti.totale}`,
      // Confermati dall'avvocato e proposti dal catalogo si contano separati: una proposta non è una conferma.
      nota: erroriLettura ? `${erroriLettura} letture non riuscite · ${daLeggere} da indicizzare · ${certi}` : daAcquisire ? `${daAcquisire} da acquisire dal portale · ${certi}` : daLeggere ? `${daLeggere} da indicizzare · ${certi}` : daVerificare ? `${daVerificare} da classificare · ${certi}` : daCatalogare ? `${daCatalogare} da verificare nel catalogo documentale · ${certi}` : documenti.totale ? (proposti ? `tutti letti · ${certi}` : 'tutti letti e catalogati' + (automatici ? ' · ' + automatici + ' in automatico' : '') + (documenti.confermati ? ' · ' + documenti.confermati + ' confermati' : '')) : 'nessun documento',
      tono: erroriLettura ? 'danger' : daAcquisire || daVerificare || daCatalogare ? 'warning' : daLeggere || proposti ? 'info' : documenti.totale ? 'success' : 'neutral',
      href: '#catalogazione-documentale',
    },
    {
      id: 'depositi',
      titolo: 'Depositi telematici',
      valore: String(depositi.totale || depositi.messaggi_archiviati?.length || 0),
      nota: depositi.falliti.length ? `${depositi.falliti.length} da ripetere · ${depositi.in_corso.length} in corso` : depositi.in_corso.length ? `${depositi.in_corso.length} in corso · ${depositi.perfezionati.length} accettati` : depositi.perfezionati.length ? `${depositi.perfezionati.length} accettati dalla cancelleria${depositi.importati?.length ? ` · ${depositi.importati.length} dal fascicolo d'ufficio` : ''}` : depositi.importati?.length ? `${depositi.importati.length} atti acquisiti dal fascicolo d'ufficio` : depositi.messaggi_archiviati?.length ? 'messaggi archiviati · esiti delle buste non collegati' : 'nessuna busta registrata',
      tono: depositi.falliti.length ? 'danger' : depositi.in_corso.length ? 'warning' : depositi.perfezionati.length ? 'success' : 'neutral',
      href: '#comunicazioni-notifica',
    },
    {
      id: 'notifiche',
      titolo: 'Presidio notifiche',
      valore: String(notifiche.totale || proveNotifica),
      nota: notifiche.fallite.length ? `${notifiche.fallite.length} non consegnate · ${notifiche.aperte.length} aperte` : notifiche.aperte.length ? `${notifiche.aperte.length} aperte · ${notifiche.perfezionate.length} perfezionate` : notifiche.totale ? `${notifiche.perfezionate.length} perfezionate` : proveNotifica ? 'documenti di notifica presenti nell’archivio' : 'nessuna notifica registrata',
      tono: notifiche.fallite.length ? 'danger' : notifiche.aperte.length ? 'warning' : notifiche.totale || proveNotifica ? 'success' : 'neutral',
      href: '#comunicazioni-notifica',
    },
    {
      id: 'pec',
      titolo: 'Presidio PEC',
      valore: String(pec.conteggio ? pec.conteggio.collegate : pec.totale),
      nota: pec.conteggio?.da_confermare ? pec.conteggio.testo : pec.da_controllare.length ? `${pec.da_controllare.length} da controllare · ${pec.termini_da_registrare.length} termini da registrare` : pec.totale ? `${pec.collegate} collegate · ${pec.totale - pec.collegate} per ruolo o assistito` : 'nessuna PEC per ruolo o assistito',
      tono: pec.conteggio?.da_confermare || pec.da_controllare.length || pec.termini_da_registrare.length || pec.udienze_da_registrare.length ? 'warning' : pec.totale ? 'success' : 'neutral',
      href: '#comunicazioni-notifica',
    },
    {
      id: 'scadenze',
      titolo: 'Scadenziario',
      valore: String(totaleScadenze),
      nota: lettura.scadenze
        ? [scadute ? String(scadute) + (scadute === 1 ? ' scaduta' : ' scadute') : '', String(lettura.scadenze.prossimi30) + ' nei prossimi 30 giorni', lettura.scadenze.successive ? String(lettura.scadenze.successive) + ' successive' : ''].filter(Boolean).join(' · ')
        : lettura.fase.prossima_udienza ? 'prossimo appuntamento o termine ' + lettura.fase.prossima_udienza : 'nessuna scadenza registrata',
      tono: scadute ? 'danger' : totaleScadenze ? 'info' : 'neutral',
      href: '#udienze',
    },
    {
      id: 'economico',
      titolo: 'Presidio economico',
      valore: economico.liquidato ? (economico.liquidato_it || '') : economico.presente && (economico.ha_incarico || economico.fatturato_it) ? (economico.saldo_aperto_it || '€ 0,00') : '—',
      nota: economico.liquidato
        ? `liquidato dal giudice · ${economico.liquidazione_incasso === 'incassata' ? 'bonificato sul conto' : economico.liquidazione_incasso === 'parziale' ? `incassato ${economico.incassato_it}` : 'non ancora bonificato'}`
        : !economico.presente ? 'nessun dato economico' : economico.parcelle_scadute.length ? `saldo aperto · ${economico.parcelle_scadute.length} parcelle scadute per ${economico.importo_scaduto_it}` : !economico.ha_incarico ? 'saldo aperto · preventivo e conferimento da formalizzare' : `saldo aperto · fatturato ${economico.fatturato_it || '€ 0,00'}`,
      tono: economico.liquidato ? (economico.liquidazione_incasso === 'incassata' ? 'success' : economico.liquidazione_incasso === 'parziale' ? 'warning' : 'danger') : economico.parcelle_scadute.length ? 'danger' : !economico.presente ? 'neutral' : !economico.ha_incarico ? 'warning' : 'success',
      href: '#conto-economico',
    },
  ]
}

// Un passo porta la norma in una riga; i dettagli (titolo, estratto, URL
// ufficiale) restano nelle fonti, che il pannello apre a richiesta.
export function normeDelPasso(passo: PassoLettura): string {
  return passo.norma || (passo.fonti || []).map((fonte) => fonte.norma).join('; ')
}

export function passiOrdinati(lettura: LetturaFascicolo): PassoLettura[] {
  return [...lettura.prossimi_passi].sort((a, b) => Number(Boolean(a.scaduto)) - Number(Boolean(b.scaduto)) || a.urgenza - b.urgenza)
}

export function riassuntoStatoPassi(lettura: LetturaFascicolo): string {
  if (!lettura.stato_passi.attivi && !lettura.prossimi_passi.length) return lettura.stato_passi.motivo || 'Nessun passaggio da eseguire.'
  if (!lettura.prossimi_passi.length) return 'Nessun adempimento risulta aperto: il fascicolo è allineato.'
  const subito = lettura.prossimi_passi.filter((passo) => passo.urgenza === 0 && !passo.scaduto).length
  const pochiGiorni = lettura.prossimi_passi.filter((passo) => passo.urgenza === 1 && !passo.scaduto).length
  const pezzi = [`${lettura.prossimi_passi.length} ${lettura.prossimi_passi.length === 1 ? 'passaggio' : 'passaggi'}`]
  const scaduti = lettura.prossimi_passi.filter((passo) => passo.scaduto).length
  if (scaduti) pezzi.push(`${scaduti} ${scaduti === 1 ? 'scaduto' : 'scaduti'} da verificare`)
  if (subito) pezzi.push(`${subito} da fare subito`)
  if (pochiGiorni) pezzi.push(`${pochiGiorni} entro pochi giorni`)
  return pezzi.join(' · ')
}

// URL della pagina Strumenti legali con il template del termine preselezionato.
export function hrefCalcoloTermine(passo: PassoLettura): string {
  if (!passo.template) return ''
  return `/strumenti-legali?strumento=termini-processuali&template=${encodeURIComponent(passo.template)}`
}

export interface RigaEconomica { etichetta: string; valore: string; nota?: string; tono?: TonoLettura; fonte?: { nome: string; href: string } }

// Le righe del presidio economico: la stessa fonte di Fatturazione, letta con gli importi.
export function righeEconomico(economico: LetturaFascicolo['economico']): RigaEconomica[] {
  if (!economico?.presente) return []
  const righe: RigaEconomica[] = []
  if (economico.preventivato_it) righe.push({ etichetta: 'Preventivato', valore: economico.preventivato_it })
  if (economico.conferito_it) righe.push({ etichetta: 'Conferito', valore: economico.conferito_it })
  if (economico.liquidato) {
    const stato = economico.liquidazione_incasso === 'incassata' ? 'bonificata sul conto dello studio' : economico.liquidazione_incasso === 'parziale' ? `incassata in parte (${economico.incassato_it})` : 'non ancora bonificata sul conto dello studio'
    const fonte = economico.liquidazione?.fonte || (economico.liquidazione?.data ? `sentenza del ${economico.liquidazione.data}` : '')
    const liquidazione = economico.liquidazione
    const daRegistrare = liquidazione?.stato === 'da_registrare' || (!liquidazione?.stato && liquidazione?.stato_etichetta === 'Da registrare')
    const collegamento = fonte && liquidazione?.fonte_href ? { nome: fonte, href: liquidazione.fonte_href } : undefined
    righe.push({
      etichetta: 'Liquidato dal giudice', valore: economico.liquidato_it || '', fonte: collegamento,
      nota: [collegamento ? '' : fonte, daRegistrare ? 'da registrare nel presidio' : '', stato].filter(Boolean).join(' · '),
      tono: economico.liquidazione_incasso === 'incassata' ? 'success' : economico.liquidazione_incasso === 'parziale' ? 'warning' : 'danger',
    })
  }
  righe.push({ etichetta: 'Fatturato', valore: economico.fatturato_it || '€ 0,00' })
  righe.push({ etichetta: 'Incassato', valore: economico.incassato_it || '€ 0,00', nota: economico.bonifici?.length ? `di cui ${economico.bonifici.length} bonific${economico.bonifici.length === 1 ? 'o' : 'i'} per ${economico.incassato_bonifico_it}` : undefined })
  righe.push({ etichetta: 'Saldo aperto', valore: economico.saldo_aperto_it || '€ 0,00', tono: economico.parcelle_scadute.length ? 'danger' : undefined, nota: economico.parcelle_scadute.length ? `${economico.parcelle_scadute.length} parcell${economico.parcelle_scadute.length === 1 ? 'a scaduta' : 'e scadute'} per ${economico.importo_scaduto_it}` : undefined })
  if (economico.anticipazioni_da_recuperare) righe.push({ etichetta: 'Anticipazioni da recuperare', valore: economico.anticipazioni_da_recuperare_it || '', tono: 'warning' })
  if (!economico.ha_incarico) righe.push({ etichetta: 'Incarico', valore: 'da formalizzare', nota: 'preventivo e conferimento non collegati (art. 13 L. 247/2012)', tono: 'warning' })
  return righe
}
