import { apiJson, apiPostJson } from './lib/apiClient'
import type { AdminAction, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'
import { sanitizeDisplayText } from './displayText'

export type FatturazioneContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  operational?: boolean
  canonical_calculation?: string
  legacy_contract?: string
}

export type FatturazioneRecord = {
  id: string
  number: string
  customerName: string
  caseTitle: string
  amountDisplay: string
  issuedAt: string
  dueAt: string
  paidAt: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  paymentMethod: string
  detailHref: string
  pdfHref: string
  xmlHref: string
}

export type FatturazioneDocumentRow = FatturazioneRecord

export type FatturazioneStatus = {
  value: string
  label: string
  tone: AdminTone
}

export type FatturazionePermissions = {
  canCreate: boolean
  canUpdateStatus: boolean
  canArchive: boolean
  canCancel: boolean
  canMarkPaid: boolean
  canDownloadPdf: boolean
  canDownloadXml: boolean
  canExport: boolean
}

export type FatturazioneDetail = FatturazioneRecord & {
  voci: Array<{
    descrizione: string
    quantita: string
    prezzoDisplay: string
  }>
}

export type UpdateFatturazioneStatusPayload = {
  stato: string
  data_pagamento?: string
  metodo_pagamento?: string
  note?: string
}

export type FatturazioneMutationItem = {
  id: string
  number: string
  amountDisplay: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  paidAt: string
  paymentMethod: string
}

export type FatturazioneMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: FatturazioneMutationItem | null
  status?: number
}

export type FatturazioneOption = {
  id: string
  value: string
  label: string
  description: string
}

export type FatturazioneMatter = FatturazioneOption & {
  idCliente: string
}

export type FatturazioneVoiceDefault = {
  descrizione: string
  quantita: string
  prezzo_unitario: string
  tipo: string
}

export type FatturazioneFiscalDefaults = {
  applica_iva: boolean
  applica_cassa: boolean
  applica_ritenuta: boolean
  applica_bollo: boolean
}

export type FatturazionePersonalizedTransmission = {
  identificativo_fiscale: string
  codice_invio: string
  telefono: string
  email: string
}

export type FatturazionePersonalizedParty = {
  id?: string
  partita_iva: string
  codice_fiscale: string
  nome_denominazione: string
  denominazione: string
  nome: string
  cognome: string
  indirizzo: string
  indirizzo_completo: string
  cap: string
  citta: string
  provincia: string
  nazione: string
  pec?: string
  email?: string
  telefono?: string
  codice_destinatario?: string
  iban?: string
  istituto_finanziario?: string
}

export type FatturazionePersonalizedDocument = {
  tipo_documento: string
  tipo_documento_label: string
  numero_documento: string
  data_documento: string
  causale_oggetto: string
  regime_fiscale: string
  regime_fiscale_label: string
  esigibilita_iva: string
  esigibilita_iva_label: string
  cassa_previdenziale: string
  cassa_previdenziale_label: string
  percentuale_spese_generali: string
  fascicolo_label?: string
}

export type FatturazionePersonalizedPayment = {
  modalita_pagamento: string
  modalita_pagamento_label: string
  modalita_pagamento_codice: string
  beneficiario: string
  istituto_finanziario: string
  iban: string
  bic_swift: string
  data_decorrenza: string
  giorni_termini: string
  importo_pagamento: string
}

export type FatturazionePersonalizedData = {
  transmission: FatturazionePersonalizedTransmission
  studio: FatturazionePersonalizedParty
  recipient: FatturazionePersonalizedParty
  document: FatturazionePersonalizedDocument
  payment: FatturazionePersonalizedPayment
}

export type FatturazioneFormDefaults = {
  id_cliente: string
  id_fascicolo: string
  data_emissione: string
  data_scadenza: string
  note: string
  voci: FatturazioneVoiceDefault[]
  opzioni_fiscali: FatturazioneFiscalDefaults
  percentuale_spese_generali: string
  metodo_pagamento: string
  dati_personalizzati: FatturazionePersonalizedData
  hidden: Record<string, string>
}

export type FatturazioneFormDefinition = {
  id: string
  title: string
  description: string
  readHref: string
  saveHref: string
  submitLabel: string
  enabled: boolean
  defaults: FatturazioneFormDefaults
  hidden: Record<string, string>
}

export type FatturazioneFiscalOption = {
  name: keyof FatturazioneFiscalDefaults
  label: string
  default: boolean
  description: string
}

export type FatturazionePageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: FatturazioneContract
  form: FatturazioneFormDefinition
  clients: FatturazioneOption[]
  matters: FatturazioneMatter[]
  clientProfiles: Record<string, FatturazionePersonalizedParty>
  matterProfiles: Record<string, {
    id: string
    titolo: string
    numero_rg: string
    tribunale: string
    giudice: string
    oggetto: string
  }>
  studioProfile: FatturazionePersonalizedParty
  nextNumber: string
  defaults: FatturazioneFormDefaults
  fiscal_options: FatturazioneFiscalOption[]
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: FatturazioneRecord[]
  documents: FatturazioneDocumentRow[]
  statuses: FatturazioneStatus[]
  permissions: FatturazionePermissions
  actions: AdminAction[]
  forms: FatturazioneFormDefinition[]
  warnings: AdminWarning[]
}

export type CreateFatturaVoice = {
  descrizione: string
  quantita: number
  prezzo_unitario: number
  tipo: string
}

export type CreateFatturaPayload = {
  id_cliente: string
  id_fascicolo: string
  data_emissione: string
  data_scadenza: string
  voci: CreateFatturaVoice[]
  note: string
  opzioni_fiscali: FatturazioneFiscalDefaults
  from_cliente?: string
  origine?: string
  id_preventivo?: string
  id_pratica?: string
  area_pratica?: string
  procedura_operativa_codice?: string
  tipo_compenso?: string
  tipo_procedimento?: string
  valore_controversia?: string
  complessita?: string
  log_calcolo?: string
  percentuale_spese_generali?: string
  metodo_pagamento?: string
  dati_personalizzati?: FatturazionePersonalizedData
}

export type CreateFatturaItem = {
  id: string
  number: string
  amountDisplay: string
  issuedAt: string
  dueAt: string
  state: string
  stateLabel: string
  stateTone: AdminTone
}

export type CreateFatturaResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: CreateFatturaItem | null
  redirect_href?: string
  status?: number
}

const emptyVoice: FatturazioneVoiceDefault = {
  descrizione: '',
  quantita: '1',
  prezzo_unitario: '',
  tipo: 'ONORARIO',
}

const emptyFiscalDefaults: FatturazioneFiscalDefaults = {
  applica_iva: true,
  applica_cassa: true,
  applica_ritenuta: false,
  applica_bollo: false,
}

const emptyParty: FatturazionePersonalizedParty = {
  partita_iva: '',
  codice_fiscale: '',
  nome_denominazione: '',
  denominazione: '',
  nome: '',
  cognome: '',
  indirizzo: '',
  indirizzo_completo: '',
  cap: '',
  citta: '',
  provincia: '',
  nazione: 'IT',
  pec: '',
  email: '',
  telefono: '',
  codice_destinatario: '',
  iban: '',
  istituto_finanziario: '',
}

const emptyPersonalizedData: FatturazionePersonalizedData = {
  transmission: {
    identificativo_fiscale: '',
    codice_invio: '',
    telefono: '',
    email: '',
  },
  studio: { ...emptyParty },
  recipient: { ...emptyParty },
  document: {
    tipo_documento: 'TD01',
    tipo_documento_label: 'Fattura',
    numero_documento: '',
    data_documento: '',
    causale_oggetto: '',
    regime_fiscale: 'RF01',
    regime_fiscale_label: 'Regime ordinario',
    esigibilita_iva: 'I',
    esigibilita_iva_label: 'Immediata',
    cassa_previdenziale: 'CAF',
    cassa_previdenziale_label: 'Avvocati',
    percentuale_spese_generali: '15',
    fascicolo_label: '',
  },
  payment: {
    modalita_pagamento: 'MP05',
    modalita_pagamento_label: 'Bonifico',
    modalita_pagamento_codice: 'MP05',
    beneficiario: '',
    istituto_finanziario: '',
    iban: '',
    bic_swift: '',
    data_decorrenza: '',
    giorni_termini: '30',
    importo_pagamento: '',
  },
}

const emptyDefaults: FatturazioneFormDefaults = {
  id_cliente: '',
  id_fascicolo: '',
  data_emissione: '',
  data_scadenza: '',
  note: '',
  voci: [emptyVoice],
  opzioni_fiscali: emptyFiscalDefaults,
  percentuale_spese_generali: '15',
  metodo_pagamento: 'Bonifico',
  dati_personalizzati: emptyPersonalizedData,
  hidden: {},
}

const emptyForm: FatturazioneFormDefinition = {
  id: 'nuova_parcella',
  title: 'Nuova parcella personalizzata',
  description: '',
  readHref: '/api/v1/ui/fatturazione/nuova',
  saveHref: '/api/v1/ui/fatturazione/nuova',
  submitLabel: 'Crea parcella',
  enabled: false,
  defaults: emptyDefaults,
  hidden: {},
}

const archiveWritesContract = 'json_api'

const emptyPermissions: FatturazionePermissions = {
  canCreate: false,
  canUpdateStatus: false,
  canArchive: false,
  canCancel: false,
  canMarkPaid: false,
  canDownloadPdf: false,
  canDownloadXml: false,
  canExport: false,
}

export const emptyFatturazionePage: FatturazionePageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: archiveWritesContract,
    route_owner: 'react_shell',
  },
  form: emptyForm,
  clients: [],
  matters: [],
  clientProfiles: {},
  matterProfiles: {},
  studioProfile: emptyParty,
  nextNumber: '',
  defaults: emptyDefaults,
  fiscal_options: [],
  metrics: [],
  sections: [],
  records: [],
  documents: [],
  statuses: [],
  permissions: emptyPermissions,
  actions: [],
  forms: [],
  warnings: [],
}

const createFallback: CreateFatturaResult = {
  ok: false,
  message: 'Salvataggio non completato.',
  errors: { server: 'Il servizio non ha restituito una risposta valida.' },
  item: null,
}

const mutationFallback: FatturazioneMutationResult = {
  ok: false,
  message: 'Operazione non completata.',
  errors: { server: 'Il servizio non ha restituito una risposta valida.' },
  item: null,
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function currentSearch(): string {
  if (typeof window === 'undefined') return ''
  return window.location.search || ''
}

function withCurrentSearch(path: string): string {
  const search = currentSearch()
  return search ? `${path}${search}` : path
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function bool(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') return value
  return fallback
}

function value(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function tone(value: unknown): AdminTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AdminTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  return href.startsWith('/') && href !== '#' ? href : fallback
}

function normaliseMetric(raw: unknown): AdminMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AdminSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'distribuzione',
    items: list(item.items).map((rawItem) => {
      const entry = asRecord(rawItem)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: display(entry.label) || 'Voce',
        value: value(entry.value),
        note: display(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: safeHref(item.href, '/fatturazione'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): AdminWarning {
  const item = asRecord(raw)
  return {
    code: display(item.code) || 'avviso',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseRecord(raw: unknown): FatturazioneRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    number: text(item.number),
    customerName: display(item.customerName) || 'Cliente non indicato',
    caseTitle: display(item.caseTitle),
    amountDisplay: display(item.amountDisplay),
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    paidAt: text(item.paidAt),
    state: text(item.state),
    stateLabel: display(item.stateLabel) || display(item.state) || 'Stato non indicato',
    stateTone: tone(item.stateTone),
    paymentMethod: display(item.paymentMethod),
    detailHref: safeHref(item.detailHref),
    pdfHref: safeHref(item.pdfHref),
    xmlHref: safeHref(item.xmlHref),
  }
}

function normaliseStatus(raw: unknown): FatturazioneStatus {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: display(item.label) || display(item.value),
    tone: tone(item.tone),
  }
}

function normalisePermissions(raw: unknown): FatturazionePermissions {
  const item = asRecord(raw)
  return {
    canCreate: bool(item.canCreate),
    canUpdateStatus: bool(item.canUpdateStatus),
    canArchive: bool(item.canArchive),
    canCancel: bool(item.canCancel),
    canMarkPaid: bool(item.canMarkPaid),
    canDownloadPdf: bool(item.canDownloadPdf),
    canDownloadXml: bool(item.canDownloadXml),
    canExport: bool(item.canExport),
  }
}

function normaliseOption(raw: unknown): FatturazioneOption {
  const item = asRecord(raw)
  const id = text(item.id) || text(item.value)
  return {
    id,
    value: text(item.value) || id,
    label: display(item.label) || 'Voce non indicata',
    description: display(item.description),
  }
}

function normaliseMatter(raw: unknown): FatturazioneMatter {
  const option = normaliseOption(raw)
  const item = asRecord(raw)
  return {
    ...option,
    idCliente: text(item.idCliente) || text(item.id_cliente),
  }
}

function normaliseVoice(raw: unknown): FatturazioneVoiceDefault {
  const item = asRecord(raw)
  return {
    descrizione: display(item.descrizione),
    quantita: text(item.quantita) || '1',
    prezzo_unitario: text(item.prezzo_unitario),
    tipo: text(item.tipo) || 'ONORARIO',
  }
}

function normaliseHidden(raw: unknown): Record<string, string> {
  const item = asRecord(raw)
  return Object.fromEntries(
    Object.entries(item)
      .map(([key, rawValue]) => [key, text(rawValue)] as const)
      .filter(([, rawValue]) => rawValue),
  )
}

function normaliseFiscalDefaults(raw: unknown): FatturazioneFiscalDefaults {
  const item = asRecord(raw)
  return {
    applica_iva: bool(item.applica_iva, true),
    applica_cassa: bool(item.applica_cassa, true),
    applica_ritenuta: bool(item.applica_ritenuta, false),
    applica_bollo: bool(item.applica_bollo, false),
  }
}

function normaliseParty(raw: unknown): FatturazionePersonalizedParty {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    partita_iva: text(item.partita_iva),
    codice_fiscale: text(item.codice_fiscale),
    nome_denominazione: display(item.nome_denominazione),
    denominazione: display(item.denominazione),
    nome: display(item.nome),
    cognome: display(item.cognome),
    indirizzo: display(item.indirizzo),
    indirizzo_completo: display(item.indirizzo_completo) || display(item.indirizzo),
    cap: text(item.cap),
    citta: display(item.citta),
    provincia: text(item.provincia).toUpperCase(),
    nazione: text(item.nazione) || 'IT',
    pec: text(item.pec),
    email: text(item.email),
    telefono: text(item.telefono),
    codice_destinatario: text(item.codice_destinatario),
    iban: text(item.iban),
    istituto_finanziario: display(item.istituto_finanziario),
  }
}

function normalisePersonalizedData(raw: unknown): FatturazionePersonalizedData {
  const item = asRecord(raw)
  const transmission = asRecord(item.transmission)
  const document = asRecord(item.document)
  const payment = asRecord(item.payment)
  return {
    transmission: {
      identificativo_fiscale: text(transmission.identificativo_fiscale),
      codice_invio: text(transmission.codice_invio),
      telefono: text(transmission.telefono),
      email: text(transmission.email),
    },
    studio: normaliseParty(item.studio),
    recipient: normaliseParty(item.recipient),
    document: {
      tipo_documento: text(document.tipo_documento) || 'TD01',
      tipo_documento_label: display(document.tipo_documento_label) || 'Fattura',
      numero_documento: text(document.numero_documento),
      data_documento: text(document.data_documento),
      causale_oggetto: text(document.causale_oggetto),
      regime_fiscale: text(document.regime_fiscale) || 'RF01',
      regime_fiscale_label: display(document.regime_fiscale_label) || 'Regime ordinario',
      esigibilita_iva: text(document.esigibilita_iva) || 'I',
      esigibilita_iva_label: display(document.esigibilita_iva_label) || 'Immediata',
      cassa_previdenziale: text(document.cassa_previdenziale) || 'CAF',
      cassa_previdenziale_label: display(document.cassa_previdenziale_label) || 'Avvocati',
      percentuale_spese_generali: text(document.percentuale_spese_generali) || '15',
      fascicolo_label: display(document.fascicolo_label),
    },
    payment: {
      modalita_pagamento: text(payment.modalita_pagamento) || 'MP05',
      modalita_pagamento_label: display(payment.modalita_pagamento_label) || 'Bonifico',
      modalita_pagamento_codice: text(payment.modalita_pagamento_codice) || 'MP05',
      beneficiario: display(payment.beneficiario),
      istituto_finanziario: display(payment.istituto_finanziario),
      iban: text(payment.iban),
      bic_swift: text(payment.bic_swift),
      data_decorrenza: text(payment.data_decorrenza),
      giorni_termini: text(payment.giorni_termini) || '30',
      importo_pagamento: text(payment.importo_pagamento),
    },
  }
}

function normaliseDefaults(raw: unknown): FatturazioneFormDefaults {
  const item = asRecord(raw)
  const voices = list(item.voci).map(normaliseVoice)
  return {
    id_cliente: text(item.id_cliente),
    id_fascicolo: text(item.id_fascicolo),
    data_emissione: text(item.data_emissione),
    data_scadenza: text(item.data_scadenza),
    note: text(item.note),
    voci: voices.length ? voices : [emptyVoice],
    opzioni_fiscali: normaliseFiscalDefaults(item.opzioni_fiscali),
    percentuale_spese_generali: text(item.percentuale_spese_generali) || '15',
    metodo_pagamento: text(item.metodo_pagamento) || 'Bonifico',
    dati_personalizzati: normalisePersonalizedData(item.dati_personalizzati),
    hidden: normaliseHidden(item.hidden),
  }
}

function normaliseForm(raw: unknown): FatturazioneFormDefinition {
  const item = asRecord(raw)
  const defaults = normaliseDefaults(item.defaults)
  return {
    id: text(item.id) || 'nuova_parcella',
    title: display(item.title) || 'Nuova parcella personalizzata',
    description: display(item.description),
    readHref: safeHref(item.readHref, '/api/v1/ui/fatturazione/nuova'),
    saveHref: safeHref(item.saveHref, '/api/v1/ui/fatturazione/nuova'),
    submitLabel: display(item.submitLabel) || 'Crea parcella',
    enabled: item.enabled !== false,
    defaults,
    hidden: normaliseHidden(item.hidden),
  }
}

function normaliseFiscalOption(raw: unknown): FatturazioneFiscalOption | null {
  const item = asRecord(raw)
  const name = text(item.name) as keyof FatturazioneFiscalDefaults
  if (!['applica_iva', 'applica_cassa', 'applica_ritenuta', 'applica_bollo'].includes(name)) return null
  return {
    name,
    label: display(item.label) || name,
    default: bool(item.default),
    description: display(item.description),
  }
}

function normalisePage(raw: unknown): FatturazionePageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const form = normaliseForm(page.form || list(page.forms)[0])
  const defaults = normaliseDefaults(page.defaults || form.defaults)
  const clientProfiles = Object.fromEntries(
    Object.entries(asRecord(page.clientProfiles)).map(([key, value]) => [key, normaliseParty(value)]),
  )
  const matterProfiles = Object.fromEntries(
    Object.entries(asRecord(page.matterProfiles)).map(([key, value]) => {
      const item = asRecord(value)
      return [key, {
        id: text(item.id) || key,
        titolo: display(item.titolo),
        numero_rg: text(item.numero_rg),
        tribunale: display(item.tribunale),
        giudice: display(item.giudice),
        oggetto: display(item.oggetto),
      }]
    }),
  )
  return {
    ok: page.ok === true,
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || archiveWritesContract,
      route_owner: text(contracts.route_owner) || 'react_shell',
      operational: bool(contracts.operational),
      canonical_calculation: text(contracts.canonical_calculation),
      legacy_contract: text(contracts.legacy_contract),
    },
    form,
    clients: list(page.clients).map(normaliseOption).filter((option) => option.value),
    matters: list(page.matters).map(normaliseMatter).filter((option) => option.value),
    clientProfiles,
    matterProfiles,
    studioProfile: normaliseParty(page.studioProfile),
    nextNumber: text(page.nextNumber),
    defaults,
    fiscal_options: list(page.fiscal_options)
      .map(normaliseFiscalOption)
      .filter((option): option is FatturazioneFiscalOption => Boolean(option)),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id || record.number),
    documents: list(page.documents).map(normaliseRecord).filter((record) => record.id || record.number),
    statuses: list(page.statuses).map(normaliseStatus).filter((status) => status.value),
    permissions: normalisePermissions(page.permissions),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: list(page.forms).map(normaliseForm),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseCreateResult(raw: unknown): CreateFatturaResult {
  const item = asRecord(raw)
  const created = asRecord(item.item)
  return {
    ok: item.ok === true,
    message: display(item.message) || (item.ok === true ? 'Parcella creata.' : 'Salvataggio non completato.'),
    errors: Object.fromEntries(
      Object.entries(asRecord(item.errors)).map(([key, rawValue]) => [key, display(rawValue)]),
    ),
    item: item.item && typeof item.item === 'object' ? {
      id: text(created.id),
      number: text(created.number),
      amountDisplay: display(created.amountDisplay),
      issuedAt: text(created.issuedAt),
      dueAt: text(created.dueAt),
      state: text(created.state),
      stateLabel: display(created.stateLabel),
      stateTone: tone(created.stateTone),
    } : null,
    redirect_href: safeHref(item.redirect_href),
    status: typeof item.status === 'number' ? item.status : undefined,
  }
}

function normaliseMutationItem(raw: unknown): FatturazioneMutationItem | null {
  if (!raw || typeof raw !== 'object') return null
  const item = asRecord(raw)
  return {
    id: text(item.id),
    number: text(item.number),
    amountDisplay: display(item.amountDisplay),
    state: text(item.state),
    stateLabel: display(item.stateLabel),
    stateTone: tone(item.stateTone),
    paidAt: text(item.paidAt),
    paymentMethod: display(item.paymentMethod),
  }
}

function normaliseMutationResult(raw: unknown): FatturazioneMutationResult {
  const item = asRecord(raw)
  return {
    ok: item.ok === true,
    message: display(item.message) || (item.ok === true ? 'Operazione completata.' : 'Operazione non completata.'),
    errors: Object.fromEntries(
      Object.entries(asRecord(item.errors)).map(([key, rawValue]) => [key, display(rawValue)]),
    ),
    item: normaliseMutationItem(item.item),
    status: typeof item.status === 'number' ? item.status : undefined,
  }
}

export async function getFatturazionePage(): Promise<FatturazionePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/fatturazione', emptyFatturazionePage)
  return normalisePage(payload)
}

export async function getFatturazioneDetail(idDocumento: string): Promise<{ ok: boolean; item: FatturazioneDetail | null; message: string; errors: Record<string, string> }> {
  const payload = await apiJson<unknown>(`/api/v1/ui/fatturazione/${encodeURIComponent(idDocumento)}`, { ok: false, item: null })
  const page = asRecord(payload)
  const rawItem = asRecord(page.item)
  const item = page.item ? {
    ...normaliseRecord(page.item),
    voci: list(rawItem.voci).map((voice) => {
      const row = asRecord(voice)
      return {
        descrizione: display(row.descrizione),
        quantita: text(row.quantita),
        prezzoDisplay: text(row.prezzoDisplay),
      }
    }),
  } : null
  return {
    ok: page.ok === true,
    item,
    message: display(page.message),
    errors: Object.fromEntries(Object.entries(asRecord(page.errors)).map(([key, rawValue]) => [key, display(rawValue)])),
  }
}

export async function getNuovaFatturaPage(): Promise<FatturazionePageData> {
  const payload = await apiJson<unknown>(withCurrentSearch('/api/v1/ui/fatturazione/nuova'), emptyFatturazionePage)
  return normalisePage(payload)
}

export async function createFattura(payload: CreateFatturaPayload): Promise<CreateFatturaResult> {
  const result = await apiPostJson<CreateFatturaResult>('/api/v1/ui/fatturazione/nuova', payload, createFallback)
  return normaliseCreateResult(result)
}

export async function createParcella(payload: CreateFatturaPayload): Promise<CreateFatturaResult> {
  return createFattura(payload)
}

export async function updateFatturazioneStatus(idDocumento: string, payload: UpdateFatturazioneStatusPayload): Promise<FatturazioneMutationResult> {
  const result = await apiPostJson<FatturazioneMutationResult>(`/api/v1/ui/fatturazione/${encodeURIComponent(idDocumento)}/stato`, payload, mutationFallback)
  return normaliseMutationResult(result)
}

export async function archiveFatturazioneDocument(): Promise<FatturazioneMutationResult> {
  return { ...mutationFallback, message: 'Archiviazione non disponibile nella configurazione corrente.' }
}

export async function cancelFatturazioneDocument(idDocumento: string): Promise<FatturazioneMutationResult> {
  const result = await apiPostJson<FatturazioneMutationResult>(`/api/v1/ui/fatturazione/${encodeURIComponent(idDocumento)}/annulla`, {}, mutationFallback)
  return normaliseMutationResult(result)
}

export async function markFatturazionePaid(idDocumento: string, payload: Omit<UpdateFatturazioneStatusPayload, 'stato'> = {}): Promise<FatturazioneMutationResult> {
  const result = await apiPostJson<FatturazioneMutationResult>(`/api/v1/ui/fatturazione/${encodeURIComponent(idDocumento)}/segna-pagata`, payload, mutationFallback)
  return normaliseMutationResult(result)
}
