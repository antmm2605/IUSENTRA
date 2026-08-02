export type CoperturaFonte = {
  source_type: string
  status: 'complete' | 'stale' | 'unavailable' | 'never'
  watermark?: string
  last_success_at?: string
  note?: string
}

export type AttivitaPiano = {
  id: string
  titolo: string
  priorita: 'P0' | 'P1' | 'P2' | 'P3'
  ordine: number
  stato: string
  settore: string
  tipo_azione: string
  motivo: string
  scadenza: string
  scadenza_label: string
  fascicolo_id: string
  fascicolo: string
  cliente: string
  assegnato_a: string
  assegnato_label: string
  bloccante: boolean
  perentorio: boolean
  affidabilita: number
  da_rivedere: boolean
  fascia_proposta: string
  minuti_stimati: number
  in_backlog: boolean
  evidenze: number
  apri: string
  azioni: string[]
}

export const dailyPlanPriorityLabel: Record<AttivitaPiano['priorita'], string> = {
  P0: 'Immediata',
  P1: 'Entro il giorno',
  P2: 'Questa settimana',
  P3: 'Organizzativa',
}

export const dailyPlanStatusLabel: Record<string, string> = {
  proposed: 'Proposta',
  needs_review: 'Da confermare',
  accepted: 'Accettata',
  scheduled: 'Pianificata',
  in_progress: 'In corso',
  completed: 'Completata',
  delegated: 'Delegata',
  snoozed: 'Rinviata',
  rejected: 'Rifiutata',
  obsolete: 'Superata',
}

export const dailyPlanActionKindLabel: Record<string, string> = {
  deadline_fulfill: 'Gestione termine',
  pec_deadline: 'Termine PEC',
  pec_review: 'Presidio PEC',
  hearing_attend: 'Udienza',
  hearing_prepare: 'Preparazione udienza',
  hearing_link_missing: 'Collegamento udienza',
  calendar_conflict: 'Conflitto agenda',
  document_review: 'Verifica documento',
  relata_completion: 'Completamento relata',
  deposit_outcome_check: 'Verifica esito deposito',
  economic_entry: 'Presidio economico',
  invoice_draft_needed: 'Bozza parcella',
  quote_followup: 'Follow-up preventivo',
  payment_review: 'Verifica pagamento',
  duplicate_reconciliation: 'Riconciliazione duplicati',
}

export const dailyPlanSourceLabel: Record<string, string> = {
  pec: 'PEC',
  scadenziario: 'Scadenze',
  agenda: 'Agenda',
  case_presidio: 'Fascicoli',
  economic: 'Economia',
  deposit: 'Depositi telematici',
  notification: 'Notifiche legali',
  health: 'Verifica fonti',
}

export type EvidenzaAttivita = {
  source_type: string
  source_id: string
  label: string
  timestamp: string
  audit_ref: string
  href: string
  confidence: number
}

export type AttivitaDettaglio = AttivitaPiano & {
  spiegazione_priorita: string
  regola_priorita: string
  evidenze_dettaglio: EvidenzaAttivita[]
  segnali_origine: string[]
  nota_stato: string
  stato_aggiornato_da: string
  stato_aggiornato_il: string
  rinviata_fino_a: string
}

export type AgendaOggiEntry = {
  id: string
  titolo: string
  tipo: string
  data_ora: string
  durata_minuti: number
  avvocato: string
  luogo: string
  procedimento: string
  id_cliente: string
  stato: string
}

export type PianoGiornoPayload = {
  ok: boolean
  stato: 'pronto' | 'non_generato'
  data: string
  data_label: string
  utente: string
  versione_piano: string
  generato_il?: string
  generato_il_label?: string
  modalita_generazione?: string
  freschezza?: Record<string, { last_success_at: string; status: string }>
  copertura: CoperturaFonte[]
  copertura_completa: boolean
  riepilogo: {
    totale?: number
    per_priorita?: Record<string, number>
    backlog?: number
    da_rivedere?: number
    da_assegnare_studio?: number
  }
  sezioni: {
    da_fare_ora: AttivitaPiano[]
    pec: AttivitaPiano[]
    fascicoli: AttivitaPiano[]
    economico: AttivitaPiano[]
    da_assegnare: AttivitaPiano[]
  }
  agenda_oggi: AgendaOggiEntry[]
  avvisi: string[]
  sintesi: string
  sintesi_da_lex: boolean
  message?: string
}

export type BacklogPayload = {
  ok: boolean
  items: AttivitaPiano[]
  next_cursor: string
  total_matching: number
  truncated: boolean
}

export type AzioneEsito = {
  ok: boolean
  attivita?: AttivitaPiano
  proposta_creata?: boolean
  proposal_id?: string
  run_id?: string
  messaggio?: string
  detail?: string
  code?: string
  replayed?: boolean
}
