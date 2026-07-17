import type { Tone } from './data'
import { sanitizeDisplayText } from './displayText'
import { csrfToken } from './formSubmit'
import { formatEuroIt } from './formatting'

export type FascicoloTipo = 'tutti' | 'civile' | 'penale' | 'amministrativo' | 'tributario' | 'stragiudiziale' | 'consulenza' | 'lavoro' | 'famiglia' | 'successioni' | 'altro'
export type FascicoloStato = 'tutti' | 'aperto' | 'in_corso' | 'definito' | 'da_archiviare' | 'archiviato' | 'sospeso'
export type FascicoloPaymentKind = 'contributo_unificato' | 'spese_esborsi' | 'fondo_spese' | 'liquidazione_giudice' | 'parcella'
export type FascicoloPaymentStatus = 'non_previsto' | 'da_registrare' | 'pagato' | 'parziale' | 'da_emettere'

export type Facet<T extends string> = { value: T; label: string; count: number }
export type SelectOption = { value: string; label: string }
export type ActionLink = { label: string; href: string; tone?: Tone; method?: 'get' | 'post'; confirm?: string }
export type KeyValue = { label: string; value: string; mono?: boolean; href?: string; tone?: Tone }

export type FascicoloPaymentHistoryItem = {
  at: string
  by: string
  fromStatus: FascicoloPaymentStatus | ''
  toStatus: FascicoloPaymentStatus | ''
  fromImporto: string
  toImporto: string
  note: string
}

export type FascicoloPaymentItem = {
  kind: FascicoloPaymentKind
  label: string
  displayLabel: string
  natura: string
  status: FascicoloPaymentStatus
  statusLabel: string
  tone: Tone
  pagato: boolean
  previsto: boolean
  importo: number | null
  importoLabel: string
  valuta: string
  dataPagamento: string
  dataPagamentoIso: string
  metodo: string
  note: string
  documentoFonte: string
  origine: string
  updatedAt: string
  updatedAtLabel: string
  updatedBy: string
  updateAction: string
  history: FascicoloPaymentHistoryItem[]
}

export type FascicoloProformaPresidio = {
  status: 'presente' | 'da_preparare' | 'sentenza_da_acquisire' | 'importi_da_confermare' | 'doppione_da_riconciliare' | 'non_applicabile'
  statusLabel: string
  tone: Tone
  message: string
  href: string
  existingCount: number
  existingDraftCount: number
  total: number
  totalLabel: string
  evidence: string
  requiresAction: boolean
}

export type FascicoloPaymentSummary = {
  stato: 'completo' | 'parziale' | 'da_presidiare' | 'non_previsto'
  statoLabel: string
  tone: Tone
  totaleRegistrato: number
  totaleRegistratoLabel: string
  anticipazioniDaRecuperare: number
  anticipazioniDaRecuperareLabel: string
  parcelleDaEmettere: number
  mancanti: number
  updatedAt: string
  updatedAtLabel: string
  updatedBy: string
  items: Record<FascicoloPaymentKind, FascicoloPaymentItem>
  proformaPresidio: FascicoloProformaPresidio
  analysis: {
    status: string
    statusLabel: string
    tone: Tone
    reason: string
    fingerprint: string
    lastAnalyzedAt: string
    relatedDuplicateFascicoli: number
    unresolvedKinds: string[]
  }
}

export type FascicoloPaymentUpdatePayload = {
  status: FascicoloPaymentStatus
  importo?: number | string | null
  dataPagamento?: string
  metodo?: string
  note?: string
  natura?: string
  documento_fonte?: string
  documento_id?: string
}

export type FascicoloPaymentUpdateResult = {
  ok: boolean
  message: string
  payment: FascicoloPaymentItem
  paymentSummary: FascicoloPaymentSummary
  fascicolo?: { id: string }
  errors?: Record<string, string>
}

export type FascicoloProformaGenerationResult = {
  ok: boolean
  existing: boolean
  message: string
  proformaId: string
  proformaNumber: string
  redirectHref: string
  paymentSummary: FascicoloPaymentSummary
}

export type FascicoloProformaBasis = {
  sourceKind: 'parcella' | 'liquidazione_giudice'
  status: FascicoloPaymentStatus
  importo: number
  dataPagamento?: string
  metodo?: string
  note?: string
}

export type FascicoloRow = {
  id: string
  ref: string
  internalRef: string
  title: string
  subtitle: string
  type: Exclude<FascicoloTipo, 'tutti'>
  client: string
  court: string
  rg: string
  rgNumber: number
  rgYear: number
  rgMissing: boolean
  rgStatusLabel: string
  rgSourceLabel: string
  nextDeadline: string
  nextDeadlineIso: string
  status: Exclude<FascicoloStato, 'tutti'>
  documents: number
  unreadCommunications: number
  alerts: number
  openedAt: string
  closedAt: string
  updatedAt: string
  href: string
  operationalHref: string
  editHref: string
  operationalEditHref: string
  exportPdfHref: string
  deleteHref: string
  archiveZipHref: string
  restoreAction: string
  tone: Tone
  relataStatus: string
  relataStatusLabel: string
  relataTone: Tone
  relataHref: string
  relataPrimaryHref: string
  relataPrimaryLabel: string
  relataReleaseDetected: boolean
  relataCount: number
  duplicateCount: number
  duplicateIds: string[]
  duplicateKey: string
  duplicateLabel: string
  duplicateHref: string
  paymentSummary: FascicoloPaymentSummary
  archive?: {
    outcome: string
    archivedAt: string
    reason: string
    notes: string
    zipAvailable: boolean
    zipSize: string
    hash: string
  }
}

export type FascicoliSummary = {
  total: number
  active: number
  inProgress: number
  toArchive: number
  archived: number
  suspended: number
  deadlines7: number
  deadlines30: number
  documents: number
  documentsToClassify: number
  unreadCommunications: number
  missingRg: number
  economicToReview: number
  economicAnalysisDue: number
  invoicesToIssue: number
  invoiceDraftsToReview: number
  invoicesPresent: number
  invoiceWorkTotal: number
  registeredAmount: number
  advancesToRecover: number
  duplicatePractices: number
  duplicatePracticeRows: number
}

export type FascicoliPagination = {
  page: number
  pageSize: number
  total: number
  pages: number
}

export type FascicoloPaymentFilter = 'tutti' | FascicoloPaymentStatus

export type FascicoliPageParams = {
  page?: number
  pageSize?: number
  q?: string
  client?: string
  rg?: string
  type?: FascicoloTipo
  status?: FascicoloStato
  court?: string
  sort?: string
  view?: 'operativa' | 'economica' | string
  alertsOnly?: boolean
  paymentsOnly?: boolean
  missingRgOnly?: boolean
  duplicatesOnly?: boolean
  cu?: FascicoloPaymentFilter
  fondoSpese?: FascicoloPaymentFilter
  liquidazione?: FascicoloPaymentFilter
  parcella?: FascicoloPaymentFilter
}

export type FascicoliPageData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes: 'operational_routes' | 'api' }
  summary: FascicoliSummary
  items: FascicoloRow[]
  pagination: FascicoliPagination
  facets: {
    types: Array<Facet<FascicoloTipo>>
    statuses: Array<Facet<FascicoloStato>>
  }
  deadlines: Array<{ id: string; matterId: string; matterRef: string; title: string; date: string; dateIso: string; href: string; tone: Tone }>
}

export type FascicoloDocument = {
  id: string
  name: string
  type: string
  rawType: string
  size: string
  uploadedAt: string
  documentDate: string
  notes: string
  tags: string[]
  signed: boolean
  statusLabel: string
  statusTone: Tone
  source: string
  portalName: string
  portalClass: string
  portalSender: string
  portalDate: string
  hash: string
  catalogRole: string
  catalogLabel: string
  catalogSection: string
  catalogConfidence: number
  catalogEvidence: string
  depositRole: string
  depositCandidate?: boolean
  actions: {
    preview: string
    download: string
    edit: string
    sign: string
    pdfa: string
    attest: string
    metadata: string
    rename: string
    delete: string
  }
}

export type FascicoloActivity = {
  id: string
  type: string
  title: string
  date: string
  description: string
  result: string
  place: string
  notes: string
  lawyer: string
  documentId: string
  depositId: string
  hearingTime?: string
  remoteHearingDetected?: boolean
  remoteHearingMode?: string
  remoteHearingUrl?: string
  remoteHearingVerified?: boolean
  remoteHearingPlatform?: string
  remoteHearingMeetingId?: string
  remoteHearingPasscode?: string
  remoteHearingAccessInfo?: string
  remoteHearingSource?: string
  updateAction: string
  deleteAction: string
  tone: Tone
}

export type FascicoloDeadline = {
  id: string
  title: string
  date: string
  dateIso: string
  type: string
  priority: string
  status: string
  peremptory: boolean
  notes: string
  href: string
  tone: Tone
}

export type FascicoloAppointment = {
  id: string
  title: string
  date: string
  time: string
  place: string
  court: string
  type: string
  href: string
  tone: Tone
}

export type FascicoloDepositReceiptStep = {
  id: string
  label: string
  done: boolean
  tone: Tone
}

export type FascicoloDeposit = {
  id: string
  timestamp: string
  sentAt: string
  acceptedAt: string
  acceptedBy: string
  registeredBy: string
  registeredAt: string
  roleNumber: string
  receiptMessageId: string
  sourceMessageId: string
  status: string
  actType: string
  pec: string
  message: string
  checks: string
  source: string
  externalId: string
  mainFile: string
  documentsCount: number
  portalDocuments: Array<{ name: string; type: string; date: string; sender: string; imported: boolean; available: boolean }>
  simulated: boolean
  receiptSteps: FascicoloDepositReceiptStep[]
  checkReceiptsAction: string
  nextSimulationAction: string
  tone: Tone
}

export type FascicoloNotificationRelataDocument = {
  id: string
  name: string
  kind: string
  kindLabel: string
  status: string
  statusLabel: string
  href: string
}

export type FascicoloNotificationRelataRelease = {
  fascicoloId: string
  fascicoloNumero: string
  fascicoloTitolo: string
  ufficio: string
  numeroRg: string
  annoRg: string
  depositoId: string
  idDepositoEsterno: string
  documentoId: string
  nome: string
  tipo: string
  dataDeposito: string
  mittente: string
  fontePortale: string
  servizioPortale: string
  riferimentoPortale: string
  notificaRichiesta: boolean
}

export type FascicoloNotificationRelataStep = {
  id: string
  label: string
  status: string
  detail: string
}

export type FascicoloNotificationRelata = {
  status: string
  statusLabel: string
  tone: Tone
  releaseDetected: boolean
  notificationAlreadySent: boolean
  proofComplete: boolean
  pendingPortalDocuments: number
  portalDocuments: number
  relataDocuments: number
  signedRelataDocuments: number
  proofDocuments: number
  acquisitionHref: string
  prepareHref: string
  depositHref: string
  primaryHref: string
  primaryLabel: string
  systemNotification: string
  releasedDocuments: FascicoloNotificationRelataRelease[]
  documents: FascicoloNotificationRelataDocument[]
  steps: FascicoloNotificationRelataStep[]
}

export type FascicoloAuditEvent = {
  eventId: string
  kind: string
  kindLabel: string
  eventTsUtc: string
  eventHash: string
  eventHashShort: string
  prevEventHash: string
  signed: boolean
  signatureAlg: string
  worm: boolean
  snapshotId: string
  inSnapshot: boolean
  tsaVerified: boolean
  tone: Tone
  proofHref: string
}

export type FascicoloAuditTrail = {
  enabled: boolean
  available: boolean
  status: string
  message: string
  events: FascicoloAuditEvent[]
  summary: {
    total: number
    signed: number
    worm: number
    snapshotted: number
    tsaVerified: number
  }
  actions: {
    bundle: string
  }
}

export type FascicoloParty = { id: string; name: string; role: string; taxCode: string; email: string; pec: string; phone: string; href: string }
export type FascicoloHistory = { date: string; description: string; from: string; to: string; notes: string; lawyer: string }
export type FascicoloMoney = { id: string; label: string; value: string; note: string; href: string; tone: Tone }
export type FascicoloSentenzeEconomicheItem = { label: string; hint: string; value: string; tone: Tone }
export type FascicoloSentenzeEconomiche = {
  totals: {
    sentenze_lette: number
    sentenze_verificate: number
    da_verificare: number
    crediti_cliente: number
    crediti_avvocato_antistatario: number
    spese_liquidate_totale: number
    contributo_unificato_alert: number
  }
  worklist: FascicoloSentenzeEconomicheItem[]
  kpi: { label: string; value: string; tone: Tone }
}
export type FascicoloPerson = { id: string; name: string; taxCode: string; vat: string; email: string; pec: string; phone: string; address: string; href: string }
export type FascicoloSourceSnapshot = {
  portale: string
  importLogId: string
  acquisitoIl: string
  externalId: string
  numero: string
  anno: number
  ufficioNome: string
  ufficioCodice: string
  procedimento: string
  subProcedimento: string
  sezione: string
  stato: string
  oggetto: string
  dataIscrizione: string
  dataUdienza: string
  ultimaAttivita: string
  parti: string[]
  controparti: string[]
  difensori: string[]
  counts: Record<string, number>
}

export type FascicoloFull = FascicoloRow & {
  clientId: string
  object: string
  counterparty: string
  counterpartyTaxCode: string
  judge: string
  section: string
  leadLawyer: string
  dominus: string
  value: string
  valueRaw: string
  quotedValue: string
  agreedFee: string
  procedureType: string
  practiceId: string
  practiceArea: string
  proceduraOperativaCodice: string
  codiceOggettoPst: string
  codiceGuidaPratica: string
  fonteCodiceOggetto: string
  fileFonteCodiceOggetto: string
  riferimentoCartaceo: string
  attorePrincipale: string
  istruttorePmGip: string
  cancelliere: string
  ctu: string
  ctp: string
  statoPraticaOperativa: string
  personalizzabile: boolean
  fascicoloVeloce: boolean
  documentiInizialiCount: number
  emailInizialiCount: number
  dataAperturaIso: string
  dataChiusuraIso: string
  firstHearing: string
  citationNotification: string
  nextHearing: string
  notes: string
  reservedNotes: string
  source: string
  sourceExternalId: string
  lastSyncAt: string
  syncStatus: string
  importLogId: string
  sourceSnapshot: FascicoloSourceSnapshot
  hasConflicts: boolean
  documentSyncEnabled: boolean
  eventsSyncEnabled: boolean
  complianceControlsEnabled: boolean
  archiveReady: boolean
}

export type RegiaOperativaData = {
  source: string
  mock_fallback: boolean
  page_state: string
  header: {
    title: string
    practiceType: string
    area: string
    channel: string
    registry: string
    workflow: string
    operationalState: string
    completion: number
    nextAction: string
  }
  profile: Record<string, unknown>
  economics: Record<string, unknown>
  checklist: Array<Record<string, unknown>>
  documentSlots: Array<Record<string, unknown>>
  validation: {
    status: string
    ready: boolean
    lastCheck: string
    blockers: Array<Record<string, unknown>>
    warnings: Array<Record<string, unknown>>
    results: Array<Record<string, unknown>>
  }
  deposit: Record<string, unknown>
  timeline: Array<Record<string, unknown>>
  evidencePack: Record<string, unknown>
  actions: Record<string, unknown>
}

export type LexIndexingSummary = {
  total_documents: number
  ready: number
  queued: number
  indexing: number
  errors: number
  stale: number
  not_indexed: number
  archived: number
  last_indexed_at: string | null
  status: 'ready' | 'partial' | 'working' | 'error' | 'stale'
  warnings: string[]
}

export type FascicoloDocumentPresidioAction = {
  id: string
  type: string
  title: string
  label: string
  date: string
  dateIso: string
  time: string
  tone: Tone
  priority: string
  peremptory: boolean
  requiresCommunicationDate: boolean
  source: string
  documentId: string
  description: string
}

export type FascicoloDocumentPresidio = {
  status: string
  tone: Tone
  summary: string
  nextAction: FascicoloDocumentPresidioAction | null
  actions: FascicoloDocumentPresidioAction[]
  warnings: string[]
  sources: Array<{ documentId: string; name: string }>
}

export type FascicoloOperationalPresidioAction = {
  id: string
  sector: string
  title: string
  label: string
  reason: string
  href: string
  date: string
  dateIso: string
  priority: string
  tone: Tone
  source: string
  legalBasis: string
  blocking: boolean
  evidence: string
}

export type FascicoloOperationalPresidioSector = {
  id: string
  label: string
  status: string
  statusLabel: string
  tone: Tone
  summary: string
  href: string
  actions: FascicoloOperationalPresidioAction[]
  evidence: string[]
  questions: string[]
}

export type FascicoloOperationalPresidio = {
  schemaVersion: number
  status: string
  statusLabel: string
  tone: Tone
  summary: string
  nextAction: FascicoloOperationalPresidioAction | null
  actions: FascicoloOperationalPresidioAction[]
  sectors: FascicoloOperationalPresidioSector[]
  questions: string[]
  generatedAt: string
}

export type FascicoloDepositOffice = {
  name: string
  code: string
  ministerialCode: string
  district: string
  pec: string
  kind: string
  verified: boolean
  message: string
}

export type FascicoloDepositInputOption = {
  value: string
  label: string
}

export type FascicoloDepositInputField = {
  id: string
  label: string
  type: string
  required: boolean
  group: string
  options: FascicoloDepositInputOption[]
  note: string
}

export type FascicoloDepositCatalogEntry = {
  key: string
  label: string
  macro: string
  category: string
  path: string
  prefix: string
  channel: string
  registry: { code: string; label: string }
  quickOrganizer: { rawKey: string; prefix: string; datiattoMethodsCount: number; datiattoRootsCount: number }
  payload: {
    tipo_atto: string
    codice_registro: string
    tipo_deposito_telematico_key: string
    tipo_deposito_telematico_label: string
    tipo_deposito_telematico_channel: string
    tipo_deposito_telematico_registry: string
    tipo_deposito_telematico_policy: string
    tipo_deposito_telematico_schema_status: string
  }
  rules: {
    policy_code: string
    channel_kind: string
    official_channel: string
    registry_code: string
    registry_label: string
    transport_kind: string
    requires_datiatto: boolean
    requires_indice_busta: boolean
    requires_atto_enc: boolean
    requires_pst_cer: boolean
    requires_local_signer: boolean
    requires_local_pec: boolean
    requires_relata: boolean
    requires_receipts: boolean
    server_smtp_allowed: boolean
    can_prepare_in_pct_panel: boolean
    real_send_allowed_from_pct_panel: boolean
    real_send_blocker: string
  }
  schema: {
    status: string
    label: string
    supported: boolean
    requiresSpecificGenerator: boolean
    supportedMinisterialRoot: string
    evidenceMethodsCount: number
    evidenceRootsCount: number
    evidenceMethods: string[]
    evidenceRoots: string[]
    generatorClass: string
    ministerialRoot: string
    inputFields: FascicoloDepositInputField[]
  }
  ui: {
    service: string
    transport: string
    behavior: string
    controls: string[]
    documents: string[]
  }
}

export type FascicoloDepositCatalogMacroarea = {
  id: string
  label: string
  total: number
  service: string
  categories: Array<{ id: string; label: string; total: number; optionKeys: string[] }>
}

export type FascicoloDepositCatalog = {
  schemaVersion: number
  source: string
  sourceOfTruth: string
  jsonAuthoritative: boolean
  tenantScope: string
  generatedAt: string
  counts: { totalDepositTypes: number; macroareas: Record<string, number>; categories: Record<string, number> }
  officialSources: Array<{ id: string; label: string; url: string; note: string }>
  referenceData: {
    titoliEsecutivi: FascicoloDepositInputOption[]
    ruoliProvvedimentoCassazione: FascicoloDepositInputOption[]
    materieCassazione: FascicoloDepositInputOption[]
    classiImmobiliari: FascicoloDepositInputOption[]
  }
  macroareas: FascicoloDepositCatalogMacroarea[]
  entries: FascicoloDepositCatalogEntry[]
}

export type FascicoloDepositReadiness = {
  contributoUnificato: {
    ready: boolean
    mode: 'esente' | 'pagato' | 'prenotato_a_debito' | 'da_definire'
    label: string
    amount: number | null
    amountLabel: string
    source: string
    message: string
  }
  anagraficaProcedimento: {
    ready: boolean
    label: string
    missing: string[]
    message: string
  }
  valoreCausa: {
    ready: boolean
    value: number | null
    valueLabel: string
    derivedFromExemption: boolean
    message: string
  }
}

export type FascicoloDepositPreparation = {
  saved: boolean
  typeKey: string
  typeLabel: string
  policy: string
  updatedAt: string
  updatedBy: string
  datiattoExtra: Record<string, unknown>
  documents: Array<{
    documentId: string
    selected: boolean
    role: string
    alreadySigned: boolean
    requiresSignature: boolean
  }>
}

export type FascicoloDetailData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes: 'operational_routes' | 'api' }
  notFound?: boolean
  requestError?: string
  fascicolo: FascicoloFull
  quickCounts: Record<string, number>
  lexIndexing: LexIndexingSummary
  profile: KeyValue[]
  documents: FascicoloDocument[]
  activities: FascicoloActivity[]
  deadlines: FascicoloDeadline[]
  appointments: FascicoloAppointment[]
  documentPresidio: FascicoloDocumentPresidio
  operationalPresidio: FascicoloOperationalPresidio
  deposits: FascicoloDeposit[]
  requests: FascicoloActivity[]
  parties: FascicoloParty[]
  history: FascicoloHistory[]
  client?: FascicoloPerson
  economics: FascicoloMoney[]
  sentenzeEconomiche: FascicoloSentenzeEconomiche | null
  workflow: Array<{ label: string; value: string; note: string; tone: Tone; href: string }>
  regia: RegiaOperativaData
  notificationRelata: FascicoloNotificationRelata
  telematic: Array<{ label: string; value: string; note: string; href: string; tone: Tone }>
  quality: Array<{ label: string; value: string; ok: boolean; tone: Tone }>
  depositOffice: FascicoloDepositOffice
  depositCatalog: FascicoloDepositCatalog
  depositReadiness: FascicoloDepositReadiness
  depositPreparation: FascicoloDepositPreparation
  signature: { visibleSignatureMode: string; visibleSignaturePlace: string; visibleSignatureDatetimeMode: string }
  auditTrail: FascicoloAuditTrail
  actions: {
    changeState: string
    define: string
    archive: string
    restore: string
    delete: string
    uploadDocument: string
    importPortal: string
    addActivity: string
    complianceOn: string
    complianceOff: string
    exportPdf: string
    archiveZip: string
    auditBundle: string
    refreshLexIndex: string
    retryLexIndexErrors: string
  }
  options: {
    states: SelectOption[]
    documentTypes: SelectOption[]
    activityTypes: SelectOption[]
    activityResults: SelectOption[]
  }
}

export type FascicoloDetailSection = 'documenti' | 'attivita' | 'scadenze' | 'depositi' | 'regia' | 'relata' | 'audit' | 'lex'

export type FascicoloFormGuardrailIssue = {
  code: string
  message: string
  field?: string
}

export type FascicoloFormGuardrails = {
  available: boolean
  title: string
  portal: 'PCT' | 'PDP' | 'PAT' | 'PTT' | string
  channel: string
  channelLabel: string
  mode: 'opening' | 'deposit' | string
  blocking: FascicoloFormGuardrailIssue[]
  warnings: FascicoloFormGuardrailIssue[]
  requiredOpeningFields: string[]
  nextStep?: {
    label: string
    href: string
  }
}

export type FascicoloFormClient = {
  id: string
  label: string
  taxCode: string
  vat: string
  email: string
  pec: string
  phone: string
  type: string
  href: string
}

export type FascicoloFormSubject = {
  id: string
  label: string
  taxCode: string
  vat: string
  email: string
  pec: string
  phone: string
  type: string
  qualification: string
  href: string
}

export type JudicialOfficeOption = {
  value: string
  label: string
  code: string
  ministerialCode: string
  district: string
  pec: string
  kind: string
  services: string[]
}

export type FascicoloFormData = {
  source: string
  generatedAt: string
  mode: 'new' | 'edit'
  action: string
  backHref: string
  detailHref: string
  query: Record<string, string>
  clients: FascicoloFormClient[]
  subjects: FascicoloFormSubject[]
  judicialOffices: JudicialOfficeOption[]
  types: SelectOption[]
  states: SelectOption[]
  fascicolo?: Partial<FascicoloFull> & Record<string, string | number | boolean | undefined>
  workflow?: { title: string; badges: string[]; summary: string; checklist: string[]; values: KeyValue[] }
  correction?: { active: boolean; title: string; help: string; highlight: string }
  guardrails?: FascicoloFormGuardrails
}

export type FascicoliExportData = {
  source: string
  generatedAt: string
  summary: FascicoliSummary
  formats: Array<{ id: string; label: string; description: string; href: string; tone: Tone }>
  fields: Array<{ key: string; label: string; checked: boolean }>
  presets: Array<{ label: string; description: string; href: string; tone: Tone }>
  recent: FascicoloRow[]
  facets: FascicoliPageData['facets']
}

const emptySummary: FascicoliSummary = {
  total: 0,
  active: 0,
  inProgress: 0,
  toArchive: 0,
  archived: 0,
  suspended: 0,
  deadlines7: 0,
  deadlines30: 0,
  documents: 0,
  documentsToClassify: 0,
  unreadCommunications: 0,
    missingRg: 0,
    economicToReview: 0,
    economicAnalysisDue: 0,
    invoicesToIssue: 0,
  invoiceDraftsToReview: 0,
  invoicesPresent: 0,
  invoiceWorkTotal: 0,
  registeredAmount: 0,
  advancesToRecover: 0,
  duplicatePractices: 0,
  duplicatePracticeRows: 0,
}

const paymentKindLabels: Record<FascicoloPaymentKind, string> = {
  contributo_unificato: 'Contributo unificato',
  spese_esborsi: 'Spese/esborsi',
  fondo_spese: 'Spese/esborsi',
  liquidazione_giudice: 'Liquidazione giudice',
  parcella: 'Parcella',
}

const paymentDefaultStatus: Record<FascicoloPaymentKind, FascicoloPaymentStatus> = {
  contributo_unificato: 'da_registrare',
  spese_esborsi: 'non_previsto',
  fondo_spese: 'non_previsto',
  liquidazione_giudice: 'non_previsto',
  parcella: 'da_emettere',
}

const paymentStatusLabels: Record<FascicoloPaymentStatus, string> = {
  non_previsto: 'Non previsto',
  da_registrare: 'Da registrare',
  pagato: 'Pagato',
  parziale: 'Parziale',
  da_emettere: 'Da emettere',
}

const paymentStatusTones: Record<FascicoloPaymentStatus, Tone> = {
  non_previsto: 'neutral',
  da_registrare: 'warning',
  pagato: 'success',
  parziale: 'orange',
  da_emettere: 'warning',
}

export const fascicoloPaymentKinds: FascicoloPaymentKind[] = ['contributo_unificato', 'spese_esborsi', 'fondo_spese', 'liquidazione_giudice', 'parcella']

function emptyPaymentItem(kind: FascicoloPaymentKind, id = ''): FascicoloPaymentItem {
  const status = paymentDefaultStatus[kind]
  return {
    kind,
    label: paymentKindLabels[kind],
    displayLabel: paymentKindLabels[kind],
    natura: '',
    status,
    statusLabel: paymentStatusLabels[status],
    tone: paymentStatusTones[status],
    pagato: false,
    previsto: status !== 'non_previsto',
    importo: null,
    importoLabel: '',
    valuta: 'EUR',
    dataPagamento: '',
    dataPagamentoIso: '',
    metodo: '',
    note: '',
    documentoFonte: '',
    origine: '',
    updatedAt: '',
    updatedAtLabel: '',
    updatedBy: '',
    updateAction: id ? `/api/v1/ui/fascicoli/${encodeURIComponent(id)}/pagamenti/${kind}` : '',
    history: [],
  }
}

function createEmptyPaymentSummary(id = ''): FascicoloPaymentSummary {
  const items = Object.fromEntries(fascicoloPaymentKinds.map((kind) => [kind, emptyPaymentItem(kind, id)])) as Record<FascicoloPaymentKind, FascicoloPaymentItem>
  return {
    stato: 'da_presidiare',
    statoLabel: 'Da presidiare',
    tone: 'warning',
    totaleRegistrato: 0,
    totaleRegistratoLabel: '€ 0,00',
    anticipazioniDaRecuperare: 0,
    anticipazioniDaRecuperareLabel: '€ 0,00',
    parcelleDaEmettere: 1,
    mancanti: 3,
    updatedAt: '',
    updatedAtLabel: '',
    updatedBy: '',
    items,
    proformaPresidio: {
      status: 'non_applicabile',
      statusLabel: 'Non ancora dovuta',
      tone: 'neutral',
      message: '',
      href: id ? `/fatturazione/nuova?id_fascicolo=${encodeURIComponent(id)}` : '/fatturazione/nuova',
      existingCount: 0,
      existingDraftCount: 0,
      total: 0,
      totalLabel: '€ 0,00',
      evidence: '',
      requiresAction: false,
    },
    analysis: {
      status: 'da_analizzare',
      statusLabel: 'Da analizzare',
      tone: 'warning',
      reason: '',
      fingerprint: '',
      lastAnalyzedAt: '',
      relatedDuplicateFascicoli: 0,
      unresolvedKinds: [],
    },
  }
}

export const emptyPaymentSummary = createEmptyPaymentSummary()

export const emptyFascicoliPage: FascicoliPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes' },
  summary: emptySummary,
  items: [],
  pagination: { page: 1, pageSize: 5, total: 0, pages: 0 },
  facets: {
    types: [{ value: 'tutti', label: 'Tutti i tipi', count: 0 }],
    statuses: [{ value: 'tutti', label: 'Tutti gli stati', count: 0 }],
  },
  deadlines: [],
}

export const emptyRegiaOperativa: RegiaOperativaData = {
  source: 'repository reale',
  mock_fallback: false,
  page_state: 'vuoto',
  header: {
    title: '',
    practiceType: '',
    area: '',
    channel: '',
    registry: '',
    workflow: '',
    operationalState: '',
    completion: 0,
    nextAction: '',
  },
  profile: {},
  economics: {},
  checklist: [],
  documentSlots: [],
  validation: { status: '', ready: false, lastCheck: '', blockers: [], warnings: [], results: [] },
  deposit: {},
  timeline: [],
  evidencePack: {},
  actions: {},
}

export const emptyNotificationRelata: FascicoloNotificationRelata = {
  status: 'monitoraggio',
  statusLabel: 'Monitoraggio attivo',
  tone: 'neutral',
  releaseDetected: false,
  notificationAlreadySent: false,
  proofComplete: false,
  pendingPortalDocuments: 0,
  portalDocuments: 0,
  relataDocuments: 0,
  signedRelataDocuments: 0,
  proofDocuments: 0,
  acquisitionHref: '/portali/pst/acquisizione?focus=documenti',
  prepareHref: '/notifiche-legali#notifica',
  depositHref: '/notifiche-legali#deposito',
  primaryHref: '/portali/pst/acquisizione?focus=documenti',
  primaryLabel: 'Verifica portale',
  systemNotification: 'Monitoraggio relata notifica attivo.',
  releasedDocuments: [],
  documents: [],
  steps: [],
}

export const emptyDepositOffice: FascicoloDepositOffice = {
  name: '',
  code: '',
  ministerialCode: '',
  district: '',
  pec: '',
  kind: '',
  verified: false,
  message: 'Ufficio destinatario da verificare prima del deposito.',
}

export const emptyDepositCatalog: FascicoloDepositCatalog = {
  schemaVersion: 0,
  source: '',
  sourceOfTruth: '',
  jsonAuthoritative: false,
  tenantScope: '',
  generatedAt: '',
  counts: { totalDepositTypes: 0, macroareas: {}, categories: {} },
  officialSources: [],
  referenceData: { titoliEsecutivi: [], ruoliProvvedimentoCassazione: [], materieCassazione: [], classiImmobiliari: [] },
  macroareas: [],
  entries: [],
}

export const emptyDepositReadiness: FascicoloDepositReadiness = {
  contributoUnificato: { ready: false, mode: 'da_definire', label: 'Da definire', amount: null, amountLabel: '', source: '', message: 'Definisci il contributo unificato.' },
  anagraficaProcedimento: { ready: false, label: 'Da completare', missing: [], message: 'Controlla i dati del procedimento.' },
  valoreCausa: { ready: false, value: null, valueLabel: '', derivedFromExemption: false, message: 'Inserisci il valore della causa.' },
}

export const emptyDepositPreparation: FascicoloDepositPreparation = {
  saved: false,
  typeKey: '',
  typeLabel: '',
  policy: '',
  updatedAt: '',
  updatedBy: '',
  datiattoExtra: {},
  documents: [],
}

export const emptyDocumentPresidio: FascicoloDocumentPresidio = {
  status: 'non_disponibile',
  tone: 'neutral',
  summary: 'Nessun presidio documentale caricato.',
  nextAction: null,
  actions: [],
  warnings: [],
  sources: [],
}

export const emptyOperationalPresidio: FascicoloOperationalPresidio = {
  schemaVersion: 1,
  status: 'non_disponibile',
  statusLabel: 'Da caricare',
  tone: 'neutral',
  summary: 'Presidio operativo non ancora caricato.',
  nextAction: null,
  actions: [],
  sectors: [],
  questions: [],
  generatedAt: '',
}

export const emptyFascicoloDetail: FascicoloDetailData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes' },
  requestError: '',
  fascicolo: {
    id: '', ref: 'n.d.', internalRef: 'n.d.', title: 'Fascicolo non trovato', subtitle: '', type: 'altro', client: 'n.d.', court: 'n.d.', rg: 'n.d.',
    rgNumber: 0, rgYear: 0, rgMissing: false, rgStatusLabel: '', rgSourceLabel: '', nextDeadline: 'n.d.', nextDeadlineIso: '', status: 'aperto', documents: 0, unreadCommunications: 0, alerts: 0, openedAt: '', closedAt: '', updatedAt: '',
    href: '/fascicoli', operationalHref: '/fascicoli', editHref: '/fascicoli', operationalEditHref: '/fascicoli', exportPdfHref: '', deleteHref: '', archiveZipHref: '', restoreAction: '', tone: 'neutral',
    relataStatus: '', relataStatusLabel: '', relataTone: 'warning', relataHref: '', relataPrimaryHref: '', relataPrimaryLabel: '', relataReleaseDetected: false, relataCount: 0,
    duplicateCount: 0, duplicateIds: [], duplicateKey: '', duplicateLabel: '', duplicateHref: '',
    paymentSummary: emptyPaymentSummary,
    clientId: '', object: '', counterparty: '', counterpartyTaxCode: '', judge: '', section: '', leadLawyer: '', dominus: '', value: '', valueRaw: '', quotedValue: '', agreedFee: '',
    procedureType: '', practiceId: '', practiceArea: '', proceduraOperativaCodice: '', codiceOggettoPst: '', codiceGuidaPratica: '', fonteCodiceOggetto: '', fileFonteCodiceOggetto: '',
    riferimentoCartaceo: '', attorePrincipale: '', istruttorePmGip: '', cancelliere: '', ctu: '', ctp: '',
    statoPraticaOperativa: '', personalizzabile: false, fascicoloVeloce: false, documentiInizialiCount: 0, emailInizialiCount: 0, dataAperturaIso: '', dataChiusuraIso: '',
    firstHearing: '', citationNotification: '', nextHearing: '', notes: '', reservedNotes: '',
    source: '', sourceExternalId: '', lastSyncAt: '', syncStatus: '', importLogId: '',
    sourceSnapshot: { portale: '', importLogId: '', acquisitoIl: '', externalId: '', numero: '', anno: 0, ufficioNome: '', ufficioCodice: '', procedimento: '', subProcedimento: '', sezione: '', stato: '', oggetto: '', dataIscrizione: '', dataUdienza: '', ultimaAttivita: '', parti: [], controparti: [], difensori: [], counts: {} },
    hasConflicts: false, documentSyncEnabled: false,
    eventsSyncEnabled: false, complianceControlsEnabled: true, archiveReady: false,
  },
  quickCounts: {}, lexIndexing: { total_documents: 0, ready: 0, queued: 0, indexing: 0, errors: 0, stale: 0, not_indexed: 0, archived: 0, last_indexed_at: null, status: 'ready', warnings: [] }, profile: [], documents: [], activities: [], deadlines: [], appointments: [], documentPresidio: emptyDocumentPresidio, operationalPresidio: emptyOperationalPresidio, deposits: [], requests: [], parties: [], history: [],
  economics: [], sentenzeEconomiche: null, workflow: [], notificationRelata: emptyNotificationRelata, telematic: [], quality: [],
  depositOffice: emptyDepositOffice,
  depositCatalog: emptyDepositCatalog,
  depositReadiness: emptyDepositReadiness,
  depositPreparation: emptyDepositPreparation,
  regia: emptyRegiaOperativa,
  signature: { visibleSignatureMode: 'laterale', visibleSignaturePlace: '', visibleSignatureDatetimeMode: 'data_ora' },
  auditTrail: {
    enabled: false,
    available: false,
    status: '',
    message: '',
    events: [],
    summary: { total: 0, signed: 0, worm: 0, snapshotted: 0, tsaVerified: 0 },
    actions: { bundle: '' },
  },
  actions: { changeState: '', define: '', archive: '', restore: '', delete: '', uploadDocument: '', importPortal: '', addActivity: '', complianceOn: '', complianceOff: '', exportPdf: '', archiveZip: '', auditBundle: '', refreshLexIndex: '', retryLexIndexErrors: '' },
  options: { states: [], documentTypes: [], activityTypes: [], activityResults: [] },
}

export const emptyFascicoloForm: FascicoloFormData = {
  source: 'vuoto', generatedAt: '', mode: 'new', action: '/fascicoli/nuovo', backHref: '/fascicoli', detailHref: '/fascicoli',
  query: {}, clients: [], subjects: [], judicialOffices: [], types: [], states: [],
}

export const emptyFascicoliExport: FascicoliExportData = {
  source: 'vuoto', generatedAt: '', summary: emptySummary, formats: [], fields: [], presets: [], recent: [], facets: emptyFascicoliPage.facets,
}

const typeLabels: Record<Exclude<FascicoloTipo, 'tutti'>, string> = {
  civile: 'Civile', penale: 'Penale', amministrativo: 'Amministrativo', tributario: 'Tributario', stragiudiziale: 'Stragiudiziale',
  consulenza: 'Consulenza', lavoro: 'Lavoro', famiglia: 'Famiglia', successioni: 'Successioni', altro: 'Altro',
}

const statusLabels: Record<Exclude<FascicoloStato, 'tutti'>, string> = {
  aperto: 'Aperto', in_corso: 'In corso', definito: 'Definito', da_archiviare: 'Da archiviare', archiviato: 'Archiviato', sospeso: 'Sospeso',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(String(value ?? fallback).trim())
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === '1' || value === 1
}

function normaliseType(value: unknown): Exclude<FascicoloTipo, 'tutti'> {
  const raw = text(value).toLowerCase()
  if (raw.includes('civ')) return 'civile'
  if (raw.includes('pen') || raw.includes('rgnr')) return 'penale'
  if (raw.includes('amm') || raw.includes('tar') || raw.includes('consiglio')) return 'amministrativo'
  if (raw.includes('trib') || raw.includes('sigit') || raw.includes('ptt')) return 'tributario'
  if (raw.includes('stragiud') || raw.includes('mediazione') || raw.includes('negoziazione')) return 'stragiudiziale'
  if (raw.includes('consul')) return 'consulenza'
  if (raw.includes('lavor')) return 'lavoro'
  if (raw.includes('fam')) return 'famiglia'
  if (raw.includes('success')) return 'successioni'
  return 'altro'
}

function normaliseStatus(value: unknown): Exclude<FascicoloStato, 'tutti'> {
  const raw = text(value).toLowerCase().replace(/\s+/g, '_')
  if (raw.includes('da_arch') || raw.includes('archiviare')) return 'da_archiviare'
  if (raw.includes('archivi')) return 'archiviato'
  if (raw.includes('defin') || raw.includes('chius')) return 'definito'
  if (raw.includes('sosp')) return 'sospeso'
  if (raw.includes('corso')) return 'in_corso'
  return 'aperto'
}

export function statusTone(status: FascicoloRow['status']): Tone {
  if (status === 'definito') return 'info'
  if (status === 'in_corso') return 'success'
  if (status === 'da_archiviare') return 'warning'
  if (status === 'archiviato') return 'neutral'
  if (status === 'sospeso') return 'orange'
  return 'primary'
}

export function normalizePaymentStatus(value: unknown, fallback: FascicoloPaymentStatus = 'da_registrare'): FascicoloPaymentStatus {
  const raw = text(value).toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_')
  if (raw === 'non_previsto' || raw === 'non_prevista' || raw === 'escluso') return 'non_previsto'
  if (raw === 'pagato' || raw === 'pagata' || raw === 'si' || raw === 'sì' || raw === 'paid') return 'pagato'
  if (raw === 'parziale' || raw === 'acconto') return 'parziale'
  if (raw === 'da_emettere' || raw === 'non_emessa') return 'da_emettere'
  if (raw === 'da_registrare' || raw === 'non_pagato' || raw === 'no' || raw === 'mancante') return 'da_registrare'
  return fallback
}

function paymentAmount(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return Number.isFinite(value) ? Math.round(value * 100) / 100 : null
  const raw = text(value)
  if (!raw) return null
  let cleaned = raw.replace(/EUR/gi, '').replace(/€/g, '').replace(/\s+/g, '')
  if (cleaned.includes(',')) cleaned = cleaned.replace(/\./g, '').replace(',', '.')
  const parsed = Number(cleaned)
  return Number.isFinite(parsed) ? Math.round(parsed * 100) / 100 : null
}

function paymentStatusOrEmpty(value: unknown): FascicoloPaymentStatus | '' {
  const raw = text(value)
  if (!raw) return ''
  return normalizePaymentStatus(raw)
}

function normalizePaymentHistory(value: unknown): FascicoloPaymentHistoryItem[] {
  return asArray(value).map((entry) => {
    const row = isRecord(entry) ? entry : {}
    return {
      at: text(row.at ?? row.quando),
      by: text(row.by ?? row.operatore),
      fromStatus: paymentStatusOrEmpty(row.fromStatus ?? row.stato_precedente),
      toStatus: paymentStatusOrEmpty(row.toStatus ?? row.stato_nuovo),
      fromImporto: text(row.fromImporto ?? row.importo_precedente),
      toImporto: text(row.toImporto ?? row.importo_nuovo),
      note: text(row.note),
    }
  }).filter((row) => row.at || row.by || row.note || row.toStatus)
}

function normalizeProformaPresidio(value: unknown, id = ''): FascicoloProformaPresidio {
  const row = isRecord(value) ? value : {}
  const rawStatus = text(row.status ?? row.stato)
  const allowed = ['presente', 'da_preparare', 'sentenza_da_acquisire', 'importi_da_confermare', 'doppione_da_riconciliare', 'non_applicabile'] as const
  const status = allowed.includes(rawStatus as typeof allowed[number]) ? rawStatus as FascicoloProformaPresidio['status'] : 'non_applicabile'
  const fallbackLabel = status === 'presente'
    ? 'Proforma presente'
    : status === 'da_preparare'
      ? 'Bozza automatica'
      : status === 'sentenza_da_acquisire'
        ? 'Sentenza da acquisire'
        : status === 'importi_da_confermare'
          ? 'Importi da confermare'
          : status === 'doppione_da_riconciliare'
            ? 'Doppione da verificare'
            : 'Non ancora dovuta'
  return {
    status,
    statusLabel: text(row.statusLabel ?? row.status_label, fallbackLabel),
    tone: (text(row.tone, status === 'presente' ? 'success' : status === 'non_applicabile' ? 'neutral' : 'warning') as Tone),
    message: text(row.message ?? row.messaggio),
    href: text(row.href, id ? `/fatturazione/nuova?id_fascicolo=${encodeURIComponent(id)}` : '/fatturazione/nuova'),
    existingCount: number(row.existingCount ?? row.existing_count),
    existingDraftCount: number(row.existingDraftCount ?? row.existing_draft_count),
    total: number(row.total ?? row.totale),
    totalLabel: text(row.totalLabel ?? row.total_label, '€ 0,00'),
    evidence: text(row.evidence ?? row.evidenza),
    requiresAction: bool(row.requiresAction ?? row.requires_action),
  }
}

export function normalizePaymentItem(value: unknown, kind: FascicoloPaymentKind, id = ''): FascicoloPaymentItem {
  const row = isRecord(value) ? value : {}
  const status = normalizePaymentStatus(row.status ?? row.stato, paymentDefaultStatus[kind])
  const importo = paymentAmount(row.importo ?? row.amount)
  const label = text(row.displayLabel ?? row.display_label ?? row.label, paymentKindLabels[kind])
  return {
    kind,
    label,
    displayLabel: label,
    natura: text(row.natura ?? row.nature),
    status,
    statusLabel: text(row.statusLabel ?? row.status_label, paymentStatusLabels[status]),
    tone: (text(row.tone, paymentStatusTones[status]) as Tone) || paymentStatusTones[status],
    pagato: bool(row.pagato) || status === 'pagato',
    previsto: row.previsto === undefined ? status !== 'non_previsto' : bool(row.previsto),
    importo,
    importoLabel: text(row.importoLabel ?? row.importo_label, importo === null ? '' : formatEuroIt(importo)),
    valuta: text(row.valuta ?? row.currency, 'EUR'),
    dataPagamento: text(row.dataPagamento ?? row.data_pagamento),
    dataPagamentoIso: text(row.dataPagamentoIso ?? row.data_pagamento_iso ?? row.data_pagamento),
    metodo: text(row.metodo ?? row.method),
    note: text(row.note),
    documentoFonte: text(row.documentoFonte ?? row.documento_fonte ?? row.sourceDocument ?? row.source_document),
    origine: text(row.origine ?? row.origin),
    updatedAt: text(row.updatedAt ?? row.updated_at),
    updatedAtLabel: text(row.updatedAtLabel ?? row.updated_at_label),
    updatedBy: text(row.updatedBy ?? row.updated_by),
    updateAction: text(row.updateAction ?? row.update_action, id ? `/api/v1/ui/fascicoli/${encodeURIComponent(id)}/pagamenti/${kind}` : ''),
    history: normalizePaymentHistory(row.history ?? row.storico),
  }
}

export function normalizePaymentSummary(value: unknown, id = ''): FascicoloPaymentSummary {
  if (!isRecord(value)) return createEmptyPaymentSummary(id)
  const rawItems = isRecord(value.items) ? value.items : {}
  const items = Object.fromEntries(
    fascicoloPaymentKinds.map((kind) => [kind, normalizePaymentItem(rawItems[kind], kind, id)]),
  ) as Record<FascicoloPaymentKind, FascicoloPaymentItem>
  const statoRaw = text(value.stato)
  const stato = statoRaw === 'completo' || statoRaw === 'parziale' || statoRaw === 'non_previsto' ? statoRaw : 'da_presidiare'
  const analysis = isRecord(value.analysis ?? value.analisi) ? (value.analysis ?? value.analisi) as Record<string, unknown> : {}
  return {
    stato,
    statoLabel: text(value.statoLabel ?? value.stato_label, stato === 'completo' ? 'Completo' : stato === 'parziale' ? 'Parziale' : stato === 'non_previsto' ? 'Non previsto' : 'Da presidiare'),
    tone: (text(value.tone, stato === 'completo' ? 'success' : stato === 'non_previsto' ? 'neutral' : 'warning') as Tone),
    totaleRegistrato: number(value.totaleRegistrato ?? value.totale_registrato),
    totaleRegistratoLabel: text(value.totaleRegistratoLabel ?? value.totale_registrato_label, '€ 0,00'),
    anticipazioniDaRecuperare: number(value.anticipazioniDaRecuperare ?? value.anticipazioni_da_recuperare),
    anticipazioniDaRecuperareLabel: text(value.anticipazioniDaRecuperareLabel ?? value.anticipazioni_da_recuperare_label, '€ 0,00'),
    parcelleDaEmettere: number(value.parcelleDaEmettere ?? value.parcelle_da_emettere),
    mancanti: number(value.mancanti),
    updatedAt: text(value.updatedAt ?? value.updated_at),
    updatedAtLabel: text(value.updatedAtLabel ?? value.updated_at_label),
    updatedBy: text(value.updatedBy ?? value.updated_by),
    items,
    proformaPresidio: normalizeProformaPresidio(value.proformaPresidio ?? value.proforma_presidio, id),
    analysis: {
      status: text(analysis.status ?? analysis.stato),
      statusLabel: text(analysis.statusLabel ?? analysis.status_label, 'Da analizzare'),
      tone: (text(analysis.tone, 'warning') as Tone) || 'warning',
      reason: text(analysis.reason ?? analysis.motivo),
      fingerprint: text(analysis.fingerprint ?? analysis.impronta),
      lastAnalyzedAt: text(analysis.lastAnalyzedAt ?? analysis.last_analyzed_at),
      relatedDuplicateFascicoli: number(analysis.relatedDuplicateFascicoli ?? analysis.related_duplicate_fascicoli),
      unresolvedKinds: asArray(analysis.unresolvedKinds ?? analysis.unresolved_kinds ?? analysis.da_verificare).map((item) => text(item)).filter(Boolean),
    },
  }
}

function normalizeArchive(value: unknown): FascicoloRow['archive'] | undefined {
  if (!isRecord(value)) return undefined
  return {
    outcome: text(value.outcome ?? value.esito_finale),
    archivedAt: text(value.archivedAt ?? value.data_archiviazione),
    reason: text(value.reason ?? value.motivo),
    notes: text(value.notes ?? value.note_archivio),
    zipAvailable: bool(value.zipAvailable ?? value.zip_available),
    zipSize: text(value.zipSize ?? value.dimensione_zip),
    hash: text(value.hash ?? value.hash_zip),
  }
}

export function normalizeItem(value: unknown, index: number): FascicoloRow {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `fascicolo-${index}`)
  const type = normaliseType(item.type ?? item.tipo)
  const status = normaliseStatus(item.status ?? item.stato)
  const rg = text(item.rg ?? item.numero_rg ?? item.n_causa, 'n.d.')
  const title = text(item.title ?? item.titolo ?? item.oggetto, 'Fascicolo senza titolo')
  const client = text(item.client ?? item.cliente ?? item.nome_cliente, 'Cliente non collegato')
  return {
    id,
    ref: text(item.ref ?? item.riferimento ?? item.numero, rg || id),
    internalRef: text(item.internalRef ?? item.internal_ref ?? item.interno, 'n.d.'),
    title,
    subtitle: text(item.subtitle ?? item.sottotitolo ?? item.descrizione ?? item.object, ''),
    type,
    client,
    court: text(item.court ?? item.tribunale ?? item.ufficio, 'Ufficio non impostato'),
    rg,
    rgNumber: number(item.rgNumber ?? item.rg_number ?? item.numeroRg ?? item.numero_rg),
    rgYear: number(item.rgYear ?? item.rg_year ?? item.annoRg ?? item.anno_rg),
    rgMissing: bool(item.rgMissing ?? item.rg_missing),
    rgStatusLabel: text(item.rgStatusLabel ?? item.rg_status_label),
    rgSourceLabel: text(item.rgSourceLabel ?? item.rg_source_label),
    nextDeadline: text(item.nextDeadline ?? item.prossima_scadenza_label ?? item.next_deadline, 'n.d.'),
    nextDeadlineIso: text(item.nextDeadlineIso ?? item.prossima_scadenza ?? item.next_deadline_iso, ''),
    status,
    documents: number(item.documents ?? item.docs ?? item.documenti),
    unreadCommunications: number(item.unreadCommunications ?? item.comunicazioni_non_lette ?? item.unread_communications),
    alerts: number(item.alerts ?? item.alert ?? item.criticita),
    openedAt: text(item.openedAt ?? item.data_apertura),
    closedAt: text(item.closedAt ?? item.data_chiusura),
    updatedAt: text(item.updatedAt ?? item.modificato_il),
    href: text(item.href, `/fascicoli/${encodeURIComponent(id)}`),
    operationalHref: text(item.operationalHref ?? item.operational_href, `/fascicoli/${encodeURIComponent(id)}`),
    editHref: text(item.editHref ?? item.edit_href, `/fascicoli/${encodeURIComponent(id)}/modifica`),
    operationalEditHref: text(item.operationalEditHref ?? item.operational_edit_href, `/fascicoli/${encodeURIComponent(id)}/modifica`),
    exportPdfHref: text(item.exportPdfHref ?? item.export_pdf_href, `/fascicoli/${encodeURIComponent(id)}/pdf`),
    deleteHref: text(item.deleteHref ?? item.delete_href, `/fascicoli/${encodeURIComponent(id)}/elimina`),
    archiveZipHref: text(item.archiveZipHref ?? item.archive_zip_href, `/fascicoli/${encodeURIComponent(id)}/archivio/scarica`),
    restoreAction: text(item.restoreAction ?? item.restore_action, `/fascicoli/${encodeURIComponent(id)}/ripristina`),
    tone: (text(item.tone) as Tone) || statusTone(status),
    relataStatus: text(item.relataStatus ?? item.relata_status, ''),
    relataStatusLabel: text(item.relataStatusLabel ?? item.relata_status_label, ''),
    relataTone: (text(item.relataTone ?? item.relata_tone, 'warning') as Tone) || 'warning',
    relataHref: text(item.relataHref ?? item.relata_href, ''),
    relataPrimaryHref: text(item.relataPrimaryHref ?? item.relata_primary_href, ''),
    relataPrimaryLabel: text(item.relataPrimaryLabel ?? item.relata_primary_label, ''),
    relataReleaseDetected: bool(item.relataReleaseDetected ?? item.relata_release_detected),
    relataCount: number(item.relataCount ?? item.relata_count),
    duplicateCount: number(item.duplicateCount ?? item.duplicate_count),
    duplicateIds: asArray(item.duplicateIds ?? item.duplicate_ids).map((value) => text(value)).filter(Boolean),
    duplicateKey: text(item.duplicateKey ?? item.duplicate_key),
    duplicateLabel: text(item.duplicateLabel ?? item.duplicate_label),
    duplicateHref: text(item.duplicateHref ?? item.duplicate_href),
    paymentSummary: normalizePaymentSummary(item.paymentSummary ?? item.payment_summary, id),
    archive: normalizeArchive(item.archive ?? item.archivio),
  }
}

function normalizeSummary(value: unknown, items: FascicoloRow[]): FascicoliSummary {
  if (isRecord(value)) {
    return {
      total: number(value.total ?? items.length),
      active: number(value.active ?? value.attivi),
      inProgress: number(value.inProgress ?? value.in_corso),
      toArchive: number(value.toArchive ?? value.da_archiviare),
      archived: number(value.archived ?? value.archiviati),
      suspended: number(value.suspended ?? value.sospesi),
      deadlines7: number(value.deadlines7 ?? value.scadenze_7),
      deadlines30: number(value.deadlines30 ?? value.scadenze_30),
      documents: number(value.documents ?? value.documenti),
      documentsToClassify: number(value.documentsToClassify ?? value.documenti_da_classificare),
      unreadCommunications: number(value.unreadCommunications ?? value.comunicazioni_non_lette),
      missingRg: number(value.missingRg ?? value.missing_rg),
      economicToReview: number(value.economicToReview ?? value.economic_to_review),
      economicAnalysisDue: number(value.economicAnalysisDue ?? value.economic_analysis_due),
      invoicesToIssue: number(value.invoicesToIssue ?? value.invoices_to_issue),
      invoiceDraftsToReview: number(value.invoiceDraftsToReview ?? value.invoice_drafts_to_review),
      invoicesPresent: number(value.invoicesPresent ?? value.invoices_present),
      invoiceWorkTotal: number(value.invoiceWorkTotal ?? value.invoice_work_total ?? value.invoicesToIssue ?? value.invoices_to_issue),
      registeredAmount: number(value.registeredAmount ?? value.registered_amount),
      advancesToRecover: number(value.advancesToRecover ?? value.advances_to_recover),
      duplicatePractices: number(value.duplicatePractices ?? value.duplicate_practices),
      duplicatePracticeRows: number(value.duplicatePracticeRows ?? value.duplicate_practice_rows),
    }
  }
  const economicToReview = items.filter((item) => item.paymentSummary.stato === 'da_presidiare' || item.paymentSummary.stato === 'parziale').length
  const duplicateKeys = new Set(items.filter((item) => item.duplicateCount > 1 && item.duplicateKey).map((item) => item.duplicateKey))
  const invoicesToIssue = items.reduce((total, item) => total + item.paymentSummary.parcelleDaEmettere, 0)
  const invoiceDraftsToReview = items.reduce((total, item) => total + item.paymentSummary.proformaPresidio.existingDraftCount, 0)
  const invoicesPresent = items.reduce((total, item) => total + item.paymentSummary.proformaPresidio.existingCount, 0)
  const economicAnalysisDue = items.reduce(
    (total, item) => total + (['da_analizzare', 'da_rianalizzare', 'aggiornato_con_rilievi'].includes(item.paymentSummary.analysis.status) ? 1 : 0),
    0,
  )
  return {
    total: items.length,
    active: items.filter((item) => item.status !== 'archiviato').length,
    inProgress: items.filter((item) => item.status === 'in_corso').length,
    toArchive: items.filter((item) => item.status === 'definito' || item.status === 'da_archiviare').length,
    archived: items.filter((item) => item.status === 'archiviato').length,
    suspended: items.filter((item) => item.status === 'sospeso').length,
    deadlines7: items.filter((item) => item.nextDeadlineIso).length,
    deadlines30: items.filter((item) => item.nextDeadlineIso).length,
    documents: items.reduce((total, item) => total + item.documents, 0),
    documentsToClassify: items.reduce((total, item) => total + item.alerts, 0),
    unreadCommunications: items.reduce((total, item) => total + item.unreadCommunications, 0),
    missingRg: items.filter((item) => item.rgMissing).length,
    economicToReview,
    economicAnalysisDue,
    invoicesToIssue,
    invoiceDraftsToReview,
    invoicesPresent,
    invoiceWorkTotal: invoicesToIssue + invoiceDraftsToReview,
    registeredAmount: items.reduce((total, item) => total + item.paymentSummary.totaleRegistrato, 0),
    advancesToRecover: items.reduce((total, item) => total + item.paymentSummary.anticipazioniDaRecuperare, 0),
    duplicatePractices: duplicateKeys.size,
    duplicatePracticeRows: items.filter((item) => item.duplicateCount > 1).length,
  }
}

function normalizeFacets(value: unknown, items: FascicoloRow[]): FascicoliPageData['facets'] {
  if (isRecord(value) && Array.isArray(value.types) && Array.isArray(value.statuses)) {
    return value as FascicoliPageData['facets']
  }
  const typeCounts = new Map<FascicoloTipo, number>([['tutti', items.length]])
  const statusCounts = new Map<FascicoloStato, number>([['tutti', items.length]])
  items.forEach((item) => {
    typeCounts.set(item.type, (typeCounts.get(item.type) || 0) + 1)
    statusCounts.set(item.status, (statusCounts.get(item.status) || 0) + 1)
  })
  return {
    types: [{ value: 'tutti', label: 'Tutti i tipi', count: items.length }, ...Object.entries(typeLabels).map(([value, label]) => ({ value: value as FascicoloTipo, label, count: typeCounts.get(value as FascicoloTipo) || 0 }))],
    statuses: [{ value: 'tutti', label: 'Tutti gli stati', count: items.length }, ...Object.entries(statusLabels).map(([value, label]) => ({ value: value as FascicoloStato, label, count: statusCounts.get(value as FascicoloStato) || 0 }))],
  }
}

function normalizePagination(value: unknown, items: FascicoloRow[], summary: FascicoliSummary): FascicoliPagination {
  if (isRecord(value)) {
    const pageSize = Math.max(1, number(value.pageSize ?? value.page_size) || 5)
    const total = Math.max(0, number(value.total ?? summary.total ?? items.length))
    const pages = Math.max(0, number(value.pages) || (total ? Math.ceil(total / pageSize) : 0))
    const page = Math.min(Math.max(1, number(value.page) || 1), Math.max(1, pages || 1))
    return { page, pageSize, total, pages }
  }
  const total = Math.max(0, summary.total || items.length)
  const pageSize = items.length || 5
  return { page: 1, pageSize, total, pages: total ? Math.ceil(total / pageSize) : 0 }
}

function normalizePagePayload(payload: unknown): FascicoliPageData {
  if (!isRecord(payload)) return emptyFascicoliPage
  const rawItems = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.fascicoli) ? payload.fascicoli : []
  const items = rawItems.map(normalizeItem)
  const summary = normalizeSummary(payload.summary, items)
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at, ''),
    contracts: isRecord(payload.contracts) ? {
      mock_fallback: bool(payload.contracts.mock_fallback),
      read_only: payload.contracts.read_only !== false,
      writes: text(payload.contracts.writes, 'operational_routes') as 'operational_routes' | 'api',
    } : { mock_fallback: false, read_only: true, writes: 'operational_routes' },
    summary,
    items,
    pagination: normalizePagination(payload.pagination, items, summary),
    facets: normalizeFacets(payload.facets, items),
    deadlines: asArray(payload.deadlines).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return {
        id: text(row.id, `deadline-${index}`),
        matterId: text(row.matterId ?? row.id_fascicolo),
        matterRef: text(row.matterRef ?? row.fascicolo),
        title: text(row.title ?? row.titolo, 'Scadenza'),
        date: text(row.date ?? row.data, 'n.d.'),
        dateIso: text(row.dateIso ?? row.date_iso ?? row.data_scadenza),
        href: text(row.href, '/scadenziario'),
        tone: (text(row.tone, 'warning') as Tone),
      }
    }),
  }
}

function normalizeKeyValues(value: unknown): KeyValue[] {
  return asArray(value).map((entry) => {
    const row = isRecord(entry) ? entry : {}
    return { label: text(row.label), value: text(row.value, 'n.d.'), mono: bool(row.mono), href: text(row.href), tone: (text(row.tone, 'neutral') as Tone) }
  }).filter((row) => row.label)
}

function normalizeOptions(value: unknown): SelectOption[] {
  return asArray(value).map((entry) => {
    const row = isRecord(entry) ? entry : {}
    return { value: text(row.value), label: text(row.label ?? row.value) }
  }).filter((row) => row.value)
}

function normalizeRegia(value: unknown): RegiaOperativaData {
  if (!isRecord(value)) return emptyRegiaOperativa
  const header = isRecord(value.header) ? value.header : {}
  const validation = isRecord(value.validation) ? value.validation : {}
  return {
    source: text(value.source, 'repository reale'),
    mock_fallback: bool(value.mock_fallback),
    page_state: text(value.page_state, 'operativa'),
    header: {
      title: text(header.title),
      practiceType: text(header.practiceType),
      area: text(header.area),
      channel: text(header.channel),
      registry: text(header.registry),
      workflow: text(header.workflow),
      operationalState: text(header.operationalState),
      completion: number(header.completion),
      nextAction: text(header.nextAction),
    },
    profile: isRecord(value.profile) ? value.profile : {},
    economics: isRecord(value.economics) ? value.economics : {},
    checklist: asArray(value.checklist).map((entry) => isRecord(entry) ? entry : {}),
    documentSlots: asArray(value.documentSlots).map((entry) => isRecord(entry) ? entry : {}),
    validation: {
      status: text(validation.status),
      ready: bool(validation.ready),
      lastCheck: text(validation.lastCheck),
      blockers: asArray(validation.blockers).map((entry) => isRecord(entry) ? entry : {}),
      warnings: asArray(validation.warnings).map((entry) => isRecord(entry) ? entry : {}),
      results: asArray(validation.results).map((entry) => isRecord(entry) ? entry : {}),
    },
    deposit: isRecord(value.deposit) ? value.deposit : {},
    timeline: asArray(value.timeline).map((entry) => isRecord(entry) ? entry : {}),
    evidencePack: isRecord(value.evidencePack) ? value.evidencePack : {},
    actions: isRecord(value.actions) ? value.actions : {},
  }
}

function normalizeAuditTrail(value: unknown): FascicoloAuditTrail {
  if (!isRecord(value)) return emptyFascicoloDetail.auditTrail
  const summary = isRecord(value.summary) ? value.summary : {}
  const actions = isRecord(value.actions) ? value.actions : {}
  return {
    enabled: bool(value.enabled),
    available: bool(value.available),
    status: text(value.status),
    message: text(value.message),
    events: asArray(value.events).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return {
        eventId: text(row.eventId ?? row.event_id, `audit-${index}`),
        kind: text(row.kind),
        kindLabel: text(row.kindLabel ?? row.kind_label, 'Evento tracciato'),
        eventTsUtc: text(row.eventTsUtc ?? row.event_ts_utc),
        eventHash: text(row.eventHash ?? row.event_hash),
        eventHashShort: text(row.eventHashShort ?? row.event_hash_short ?? row.eventHash ?? row.event_hash),
        prevEventHash: text(row.prevEventHash ?? row.prev_event_hash),
        signed: bool(row.signed),
        signatureAlg: text(row.signatureAlg ?? row.signature_alg),
        worm: bool(row.worm),
        snapshotId: text(row.snapshotId ?? row.snapshot_id),
        inSnapshot: bool(row.inSnapshot ?? row.in_snapshot),
        tsaVerified: bool(row.tsaVerified ?? row.tsa_verified),
        tone: text(row.tone, 'primary') as Tone,
        proofHref: text(row.proofHref ?? row.proof_href),
      }
    }),
    summary: {
      total: number(summary.total),
      signed: number(summary.signed),
      worm: number(summary.worm),
      snapshotted: number(summary.snapshotted),
      tsaVerified: number(summary.tsaVerified ?? summary.tsa_verified),
    },
    actions: {
      bundle: text(actions.bundle),
    },
  }
}

function normalizeNotificationRelata(value: unknown): FascicoloNotificationRelata {
  if (!isRecord(value)) return emptyNotificationRelata
  const releaseRows = asArray(value.releasedDocuments ?? value.released_documents).map((entry, index) => {
    const row = isRecord(entry) ? entry : {}
    return {
      fascicoloId: text(row.fascicoloId ?? row.fascicolo_id),
      fascicoloNumero: text(row.fascicoloNumero ?? row.fascicolo_numero),
      fascicoloTitolo: text(row.fascicoloTitolo ?? row.fascicolo_titolo),
      ufficio: text(row.ufficio),
      numeroRg: text(row.numeroRg ?? row.numero_rg),
      annoRg: text(row.annoRg ?? row.anno_rg),
      depositoId: text(row.depositoId ?? row.deposito_id),
      idDepositoEsterno: text(row.idDepositoEsterno ?? row.id_deposito_esterno),
      documentoId: text(row.documentoId ?? row.documento_id, `release-${index}`),
      nome: text(row.nome ?? row.name, 'Documento d\'ufficio'),
      tipo: text(row.tipo ?? row.type),
      dataDeposito: text(row.dataDeposito ?? row.data_deposito),
      mittente: text(row.mittente ?? row.sender),
      fontePortale: text(row.fontePortale ?? row.fonte_portale),
      servizioPortale: text(row.servizioPortale ?? row.servizio_portale),
      riferimentoPortale: text(row.riferimentoPortale ?? row.riferimento_portale),
      notificaRichiesta: bool(row.notificaRichiesta ?? row.notifica_richiesta),
    }
  })
  const documentRows = asArray(value.documents).map((entry, index) => {
    const row = isRecord(entry) ? entry : {}
    return {
      id: text(row.id, `relata-doc-${index}`),
      name: text(row.name ?? row.nome, 'Documento'),
      kind: text(row.kind ?? row.tipo),
      kindLabel: text(row.kindLabel ?? row.kind_label ?? row.tipo_label),
      status: text(row.status ?? row.stato),
      statusLabel: text(row.statusLabel ?? row.status_label ?? row.stato_label),
      href: text(row.href),
    }
  })
  const stepRows = asArray(value.steps).map((entry, index) => {
    const row = isRecord(entry) ? entry : {}
    return {
      id: text(row.id, `relata-step-${index}`),
      label: text(row.label, 'Passaggio'),
      status: text(row.status, 'in_attesa'),
      detail: text(row.detail ?? row.dettaglio),
    }
  })
  return {
    status: text(value.status, emptyNotificationRelata.status),
    statusLabel: text(value.statusLabel ?? value.status_label, emptyNotificationRelata.statusLabel),
    tone: text(value.tone, emptyNotificationRelata.tone) as Tone,
    releaseDetected: bool(value.releaseDetected ?? value.release_detected),
    notificationAlreadySent: bool(value.notificationAlreadySent ?? value.notification_already_sent),
    proofComplete: bool(value.proofComplete ?? value.proof_complete),
    pendingPortalDocuments: number(value.pendingPortalDocuments ?? value.pending_portal_documents),
    portalDocuments: number(value.portalDocuments ?? value.portal_documents),
    relataDocuments: number(value.relataDocuments ?? value.relata_documents),
    signedRelataDocuments: number(value.signedRelataDocuments ?? value.signed_relata_documents),
    proofDocuments: number(value.proofDocuments ?? value.proof_documents),
    acquisitionHref: text(value.acquisitionHref ?? value.acquisition_href, emptyNotificationRelata.acquisitionHref),
    prepareHref: text(value.prepareHref ?? value.prepare_href, emptyNotificationRelata.prepareHref),
    depositHref: text(value.depositHref ?? value.deposit_href, emptyNotificationRelata.depositHref),
    primaryHref: text(value.primaryHref ?? value.primary_href, emptyNotificationRelata.primaryHref),
    primaryLabel: text(value.primaryLabel ?? value.primary_label, emptyNotificationRelata.primaryLabel),
    systemNotification: text(value.systemNotification ?? value.system_notification, emptyNotificationRelata.systemNotification),
    releasedDocuments: releaseRows,
    documents: documentRows,
    steps: stepRows,
  }
}

function normalizeSourceSnapshot(value: unknown): FascicoloSourceSnapshot {
  const row = isRecord(value) ? value : {}
  const countsRaw = isRecord(row.counts) ? row.counts : {}
  const counts: Record<string, number> = {}
  Object.entries(countsRaw).forEach(([key, count]) => {
    counts[key] = number(count)
  })
  return {
    portale: text(row.portale),
    importLogId: text(row.importLogId ?? row.import_log_id),
    acquisitoIl: text(row.acquisitoIl ?? row.acquisito_il),
    externalId: text(row.externalId ?? row.external_id),
    numero: text(row.numero),
    anno: number(row.anno),
    ufficioNome: text(row.ufficioNome ?? row.ufficio_nome),
    ufficioCodice: text(row.ufficioCodice ?? row.ufficio_codice),
    procedimento: text(row.procedimento),
    subProcedimento: text(row.subProcedimento ?? row.sub_procedimento),
    sezione: text(row.sezione),
    stato: text(row.stato),
    oggetto: text(row.oggetto),
    dataIscrizione: text(row.dataIscrizione ?? row.data_iscrizione),
    dataUdienza: text(row.dataUdienza ?? row.data_udienza),
    ultimaAttivita: text(row.ultimaAttivita ?? row.ultima_attivita),
    parti: asArray(row.parti).map((item) => text(item)).filter(Boolean),
    controparti: asArray(row.controparti).map((item) => text(item)).filter(Boolean),
    difensori: asArray(row.difensori).map((item) => text(item)).filter(Boolean),
    counts,
  }
}

function normalizeDocumentPresidioAction(value: unknown, index: number): FascicoloDocumentPresidioAction {
  const row = isRecord(value) ? value : {}
  return {
    id: text(row.id, `presidio-${index}`),
    type: text(row.type ?? row.tipo),
    title: text(row.title ?? row.titolo ?? row.label, 'Adempimento documentale'),
    label: text(row.label ?? row.title ?? row.titolo, 'Adempimento documentale'),
    date: text(row.date ?? row.data),
    dateIso: text(row.dateIso ?? row.date_iso ?? row.data_iso),
    time: text(row.time ?? row.ora),
    tone: text(row.tone, 'warning') as Tone,
    priority: text(row.priority ?? row.priorita, 'important'),
    peremptory: bool(row.peremptory ?? row.perentorio),
    requiresCommunicationDate: bool(row.requiresCommunicationDate ?? row.requires_communication_date),
    source: text(row.source ?? row.fonte, 'Documento fascicolo'),
    documentId: text(row.documentId ?? row.document_id),
    description: text(row.description ?? row.descrizione),
  }
}

function normalizeDocumentPresidio(value: unknown): FascicoloDocumentPresidio {
  if (!isRecord(value)) return emptyDocumentPresidio
  const actions = asArray(value.actions ?? value.azioni).map(normalizeDocumentPresidioAction)
  const nextRaw = value.nextAction ?? value.next_action
  return {
    status: text(value.status ?? value.stato, emptyDocumentPresidio.status),
    tone: text(value.tone, emptyDocumentPresidio.tone) as Tone,
    summary: text(value.summary ?? value.sintesi, emptyDocumentPresidio.summary),
    nextAction: isRecord(nextRaw) ? normalizeDocumentPresidioAction(nextRaw, 0) : null,
    actions,
    warnings: asArray(value.warnings ?? value.avvisi).map((item) => text(item)).filter(Boolean),
    sources: asArray(value.sources ?? value.fonti).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return { documentId: text(row.documentId ?? row.document_id, `doc-${index}`), name: text(row.name ?? row.nome, 'Documento fascicolo') }
    }),
  }
}

function normalizeOperationalPresidioAction(value: unknown, index: number): FascicoloOperationalPresidioAction {
  const row = isRecord(value) ? value : {}
  return {
    id: text(row.id, `presidio-operativo-${index}`),
    sector: text(row.sector ?? row.settore),
    title: text(row.title ?? row.titolo ?? row.label, 'Azione operativa'),
    label: text(row.label ?? row.title ?? row.titolo, 'Azione operativa'),
    reason: text(row.reason ?? row.motivo ?? row.description ?? row.descrizione),
    href: text(row.href),
    date: text(row.date ?? row.data),
    dateIso: text(row.dateIso ?? row.date_iso ?? row.data_iso),
    priority: text(row.priority ?? row.priorita, 'P2'),
    tone: text(row.tone, 'warning') as Tone,
    source: text(row.source ?? row.fonte),
    legalBasis: text(row.legalBasis ?? row.legal_basis ?? row.norma),
    blocking: bool(row.blocking ?? row.bloccante),
    evidence: text(row.evidence ?? row.prova),
  }
}

function normalizeOperationalPresidioSector(value: unknown, index: number): FascicoloOperationalPresidioSector {
  const row = isRecord(value) ? value : {}
  return {
    id: text(row.id, `settore-${index}`),
    label: text(row.label, 'Settore operativo'),
    status: text(row.status ?? row.stato),
    statusLabel: text(row.statusLabel ?? row.status_label ?? row.stato_label, 'Da verificare'),
    tone: text(row.tone, 'neutral') as Tone,
    summary: text(row.summary ?? row.sintesi),
    href: text(row.href),
    actions: asArray(row.actions ?? row.azioni).map(normalizeOperationalPresidioAction),
    evidence: asArray(row.evidence ?? row.prove).map((item) => text(item)).filter(Boolean),
    questions: asArray(row.questions ?? row.domande).map((item) => text(item)).filter(Boolean),
  }
}

function normalizeOperationalPresidio(value: unknown): FascicoloOperationalPresidio {
  if (!isRecord(value)) return emptyOperationalPresidio
  const actions = asArray(value.actions ?? value.azioni).map(normalizeOperationalPresidioAction)
  const nextRaw = value.nextAction ?? value.next_action
  return {
    schemaVersion: number(value.schemaVersion ?? value.schema_version) || 1,
    status: text(value.status ?? value.stato, emptyOperationalPresidio.status),
    statusLabel: text(value.statusLabel ?? value.status_label ?? value.stato_label, emptyOperationalPresidio.statusLabel),
    tone: text(value.tone, emptyOperationalPresidio.tone) as Tone,
    summary: text(value.summary ?? value.sintesi, emptyOperationalPresidio.summary),
    nextAction: isRecord(nextRaw) ? normalizeOperationalPresidioAction(nextRaw, 0) : null,
    actions,
    sectors: asArray(value.sectors ?? value.settori).map(normalizeOperationalPresidioSector),
    questions: asArray(value.questions ?? value.domande).map((item) => text(item)).filter(Boolean),
    generatedAt: text(value.generatedAt ?? value.generated_at),
  }
}

function normalizeDetailPayload(payload: unknown): FascicoloDetailData {
  if (!isRecord(payload)) return emptyFascicoloDetail
  const base = normalizeItem(payload.fascicolo ?? {}, 0)
  const fullPayload = isRecord(payload.fascicolo) ? payload.fascicolo : {}
  const full: FascicoloFull = {
    ...emptyFascicoloDetail.fascicolo,
    ...base,
    clientId: text(fullPayload.clientId ?? fullPayload.client_id ?? fullPayload.id_cliente),
    object: text(fullPayload.object ?? fullPayload.oggetto),
    counterparty: text(fullPayload.counterparty ?? fullPayload.controparte),
    counterpartyTaxCode: text(fullPayload.counterpartyTaxCode ?? fullPayload.cf_controparte),
    judge: text(fullPayload.judge ?? fullPayload.giudice),
    section: text(fullPayload.section ?? fullPayload.sezione),
    leadLawyer: text(fullPayload.leadLawyer ?? fullPayload.avvocato_referente),
    dominus: text(fullPayload.dominus ?? fullPayload.avvocato_dominus),
    value: text(fullPayload.value ?? fullPayload.valore_causa),
    valueRaw: text(fullPayload.valueRaw ?? fullPayload.value_raw ?? fullPayload.valore_causa),
    quotedValue: text(fullPayload.quotedValue ?? fullPayload.valore_preventivato),
    agreedFee: text(fullPayload.agreedFee ?? fullPayload.compenso_pattuito),
    procedureType: text(fullPayload.procedureType ?? fullPayload.tipo_procedimento),
    practiceId: text(fullPayload.practiceId ?? fullPayload.id_pratica),
    practiceArea: text(fullPayload.practiceArea ?? fullPayload.area_pratica),
    proceduraOperativaCodice: text(fullPayload.proceduraOperativaCodice ?? fullPayload.procedura_operativa_codice),
    codiceOggettoPst: text(fullPayload.codiceOggettoPst ?? fullPayload.codice_oggetto_pst),
    codiceGuidaPratica: text(fullPayload.codiceGuidaPratica ?? fullPayload.codice_guida_pratica),
    fonteCodiceOggetto: text(fullPayload.fonteCodiceOggetto ?? fullPayload.fonte_codice_oggetto),
    fileFonteCodiceOggetto: text(fullPayload.fileFonteCodiceOggetto ?? fullPayload.file_fonte_codice_oggetto),
    riferimentoCartaceo: text(fullPayload.riferimentoCartaceo ?? fullPayload.riferimento_cartaceo),
    attorePrincipale: text(fullPayload.attorePrincipale ?? fullPayload.attore_principale),
    istruttorePmGip: text(fullPayload.istruttorePmGip ?? fullPayload.istruttore_pm_gip),
    cancelliere: text(fullPayload.cancelliere),
    ctu: text(fullPayload.ctu),
    ctp: text(fullPayload.ctp),
    statoPraticaOperativa: text(fullPayload.statoPraticaOperativa ?? fullPayload.stato_pratica_operativa),
    personalizzabile: bool(fullPayload.personalizzabile),
    fascicoloVeloce: bool(fullPayload.fascicoloVeloce ?? fullPayload.fascicolo_veloce),
    documentiInizialiCount: number(fullPayload.documentiInizialiCount ?? fullPayload.documenti_iniziali_count),
    emailInizialiCount: number(fullPayload.emailInizialiCount ?? fullPayload.email_iniziali_count),
    dataAperturaIso: text(fullPayload.dataAperturaIso ?? fullPayload.data_apertura),
    dataChiusuraIso: text(fullPayload.dataChiusuraIso ?? fullPayload.data_chiusura),
    firstHearing: text(fullPayload.firstHearing ?? fullPayload.data_prima_udienza),
    citationNotification: text(fullPayload.citationNotification ?? fullPayload.data_notifica_citazione),
    nextHearing: text(fullPayload.nextHearing ?? fullPayload.data_prossima_udienza),
    notes: text(fullPayload.notes ?? fullPayload.note),
    reservedNotes: text(fullPayload.reservedNotes ?? fullPayload.note_riservate),
    source: text(fullPayload.source),
    sourceExternalId: text(fullPayload.sourceExternalId ?? fullPayload.source_external_id),
    lastSyncAt: text(fullPayload.lastSyncAt ?? fullPayload.last_sync_at),
    syncStatus: text(fullPayload.syncStatus ?? fullPayload.sync_status),
    importLogId: text(fullPayload.importLogId ?? fullPayload.import_log_id),
    sourceSnapshot: normalizeSourceSnapshot(fullPayload.sourceSnapshot ?? fullPayload.source_snapshot),
    hasConflicts: bool(fullPayload.hasConflicts ?? fullPayload.has_conflicts),
    documentSyncEnabled: bool(fullPayload.documentSyncEnabled ?? fullPayload.document_sync_enabled),
    eventsSyncEnabled: bool(fullPayload.eventsSyncEnabled ?? fullPayload.events_sync_enabled),
    complianceControlsEnabled: fullPayload.complianceControlsEnabled === undefined ? true : bool(fullPayload.complianceControlsEnabled ?? fullPayload.compliance_controls_enabled),
    archiveReady: bool(fullPayload.archiveReady ?? fullPayload.archivio_pronto),
  }
  const options = isRecord(payload.options) ? payload.options : {}
  const lexIndexingRaw = payload.lexIndexing ?? payload.lex_indexing
  const lexIndexingSource = isRecord(lexIndexingRaw) ? lexIndexingRaw : {}
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: isRecord(payload.contracts) ? {
      mock_fallback: bool(payload.contracts.mock_fallback), read_only: payload.contracts.read_only !== false, writes: text(payload.contracts.writes, 'operational_routes') as 'operational_routes' | 'api',
    } : emptyFascicoloDetail.contracts,
    notFound: bool(payload.notFound ?? payload.not_found),
    requestError: text(payload.requestError ?? payload.request_error ?? payload.errore ?? payload.error),
    fascicolo: full,
    quickCounts: isRecord(payload.quickCounts ?? payload.quick_counts) ? payload.quickCounts as Record<string, number> : {},
    lexIndexing: {
      total_documents: number(lexIndexingSource.total_documents ?? lexIndexingSource.totalDocuments),
      ready: number(lexIndexingSource.ready),
      queued: number(lexIndexingSource.queued),
      indexing: number(lexIndexingSource.indexing),
      errors: number(lexIndexingSource.errors),
      stale: number(lexIndexingSource.stale),
      not_indexed: number(lexIndexingSource.not_indexed ?? lexIndexingSource.notIndexed),
      archived: number(lexIndexingSource.archived),
      last_indexed_at: text(lexIndexingSource.last_indexed_at ?? lexIndexingSource.lastIndexedAt) || null,
      status: text(lexIndexingSource.status, 'ready') as LexIndexingSummary['status'],
      warnings: asArray(lexIndexingSource.warnings).map((item) => text(item)).filter(Boolean).slice(0, 12),
    },
    profile: normalizeKeyValues(payload.profile),
    documents: asArray(payload.documents).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      const actions = isRecord(row.actions) ? row.actions : {}
      const signed = bool(row.signed)
      return {
        id: text(row.id, `doc-${index}`), name: text(row.name ?? row.nome, 'Documento'), type: text(row.type ?? row.tipo, 'ALTRO'), rawType: text(row.rawType ?? row.raw_type ?? row.tipo, ''),
        size: text(row.size ?? row.dimensione, ''),
        uploadedAt: text(row.uploadedAt ?? row.data_caricamento), documentDate: text(row.documentDate ?? row.data_documento), notes: text(row.notes ?? row.note),
        tags: asArray(row.tags).map((tag) => text(tag)).filter(Boolean), signed,
        statusLabel: signed ? text(row.statusLabel ?? row.status_label, 'Firmato') : 'Da firmare',
        statusTone: signed ? text(row.statusTone ?? row.status_tone, 'success') as Tone : 'warning',
        source: text(row.source ?? row.fonte_documento),
        portalName: text(row.portalName ?? row.nome_portale), portalClass: text(row.portalClass ?? row.classificazione_portale), portalSender: text(row.portalSender ?? row.mittente_portale),
        portalDate: text(row.portalDate ?? row.data_deposito_portale), hash: text(row.hash ?? row.hash_sha256),
        catalogRole: text(row.catalogRole ?? row.catalog_role),
        catalogLabel: text(row.catalogLabel ?? row.catalog_label),
        catalogSection: text(row.catalogSection ?? row.catalog_section),
        catalogConfidence: number(row.catalogConfidence ?? row.catalog_confidence),
        catalogEvidence: text(row.catalogEvidence ?? row.catalog_evidence),
        depositRole: text(row.depositRole ?? row.deposit_role),
        depositCandidate: row.depositCandidate === undefined && row.deposit_candidate === undefined ? undefined : bool(row.depositCandidate ?? row.deposit_candidate),
        actions: {
          preview: text(actions.preview), download: text(actions.download), edit: text(actions.edit), sign: text(actions.sign), pdfa: text(actions.pdfa), attest: text(actions.attest), metadata: text(actions.metadata), rename: text(actions.rename), delete: text(actions.delete),
        },
      }
    }),
    activities: asArray(payload.activities).map(normalizeActivity),
    deadlines: asArray(payload.deadlines).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return { id: text(row.id, `scad-${index}`), title: text(row.title ?? row.titolo, 'Scadenza'), date: text(row.date ?? row.data, 'n.d.'), dateIso: text(row.dateIso ?? row.data_scadenza), type: text(row.type ?? row.tipo), priority: text(row.priority ?? row.priorita), status: text(row.status ?? row.stato), peremptory: bool(row.peremptory ?? row.perentorio), notes: text(row.notes ?? row.note), href: text(row.href, '/scadenziario'), tone: text(row.tone, 'warning') as Tone }
    }),
    appointments: asArray(payload.appointments).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return { id: text(row.id, `app-${index}`), title: text(row.title ?? row.titolo, 'Appuntamento'), date: text(row.date ?? row.data), time: text(row.time ?? row.ora), place: text(row.place ?? row.luogo), court: text(row.court ?? row.tribunale), type: text(row.type ?? row.tipo), href: text(row.href, '/agenda'), tone: text(row.tone, 'primary') as Tone }
    }),
    documentPresidio: normalizeDocumentPresidio(payload.documentPresidio ?? payload.document_presidio),
    operationalPresidio: normalizeOperationalPresidio(payload.operationalPresidio ?? payload.operational_presidio),
    deposits: asArray(payload.deposits).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return {
        id: text(row.id, `dep-${index}`),
        timestamp: text(row.timestamp),
        sentAt: text(row.sentAt ?? row.sent_at),
        acceptedAt: text(row.acceptedAt ?? row.accepted_at),
        acceptedBy: text(row.acceptedBy ?? row.accepted_by),
        registeredBy: text(row.registeredBy ?? row.registered_by),
        registeredAt: text(row.registeredAt ?? row.registered_at),
        roleNumber: text(row.roleNumber ?? row.role_number ?? row.numero_ruolo),
        receiptMessageId: text(row.receiptMessageId ?? row.receipt_message_id),
        sourceMessageId: text(row.sourceMessageId ?? row.source_message_id),
        status: text(row.status ?? row.stato),
        actType: text(row.actType ?? row.tipo_atto),
        pec: text(row.pec ?? row.pec_destinatario),
        message: text(row.message ?? row.messaggio),
        checks: text(row.checks ?? row.esito_controlli),
        source: text(row.source ?? row.fonte_portale),
        externalId: text(row.externalId ?? row.id_deposito_esterno),
        mainFile: text(row.mainFile ?? row.nome_atto_principale),
        documentsCount: number(row.documentsCount ?? row.documenti_count),
        portalDocuments: asArray(row.portalDocuments ?? row.documenti_portale).map((doc) => {
          const d = isRecord(doc) ? doc : {}
          return { name: text(d.name ?? d.nome, 'Documento'), type: text(d.type ?? d.tipo), date: text(d.date ?? d.data), sender: text(d.sender ?? d.mittente), imported: bool(d.imported ?? d.gia_importato), available: d.available === undefined ? true : bool(d.available ?? d.disponibile) }
        }),
        simulated: bool(row.simulated ?? row.simulazione),
        receiptSteps: asArray(row.receiptSteps ?? row.receipt_steps).map((step, stepIndex) => {
          const item = isRecord(step) ? step : {}
          return { id: text(item.id, `ricevuta-${stepIndex}`), label: text(item.label, 'Ricevuta'), done: bool(item.done), tone: text(item.tone, bool(item.done) ? 'success' : 'neutral') as Tone }
        }),
        checkReceiptsAction: text(row.checkReceiptsAction ?? row.check_receipts_action),
        nextSimulationAction: text(row.nextSimulationAction ?? row.next_simulation_action),
        tone: text(row.tone, 'primary') as Tone,
      }
    }),
    requests: asArray(payload.requests).map(normalizeActivity),
    parties: asArray(payload.parties).map((entry, index) => { const row = isRecord(entry) ? entry : {}; return { id: text(row.id, `party-${index}`), name: text(row.name ?? row.nome, 'Soggetto'), role: text(row.role ?? row.ruolo), taxCode: text(row.taxCode ?? row.codice_fiscale), email: text(row.email), pec: text(row.pec), phone: text(row.phone ?? row.telefono), href: text(row.href, '/soggetti') } }),
    history: asArray(payload.history).map((entry) => { const row = isRecord(entry) ? entry : {}; return { date: text(row.date ?? row.data), description: text(row.description ?? row.descrizione), from: text(row.from ?? row.stato_precedente), to: text(row.to ?? row.stato_nuovo), notes: text(row.notes ?? row.note), lawyer: text(row.lawyer ?? row.avvocato) } }),
    client: isRecord(payload.client) ? { id: text(payload.client.id), name: text(payload.client.name ?? payload.client.nome, 'Cliente'), taxCode: text(payload.client.taxCode ?? payload.client.codice_fiscale), vat: text(payload.client.vat ?? payload.client.partita_iva), email: text(payload.client.email), pec: text(payload.client.pec), phone: text(payload.client.phone ?? payload.client.telefono), address: text(payload.client.address ?? payload.client.indirizzo), href: text(payload.client.href, '/clienti') } : undefined,
    economics: asArray(payload.economics).map((entry, index) => { const row = isRecord(entry) ? entry : {}; return { id: text(row.id, `money-${index}`), label: text(row.label), value: text(row.value), note: text(row.note), href: text(row.href, '/fatturazione'), tone: text(row.tone, 'neutral') as Tone } }),
    sentenzeEconomiche: ((): FascicoloSentenzeEconomiche | null => {
      const se = isRecord(payload.sentenzeEconomiche) ? payload.sentenzeEconomiche : null
      if (!se) return null
      const t = isRecord(se.totals) ? se.totals : {}
      const kpi = isRecord(se.kpi) ? se.kpi : {}
      return {
        totals: {
          sentenze_lette: number(t.sentenze_lette),
          sentenze_verificate: number(t.sentenze_verificate),
          da_verificare: number(t.da_verificare),
          crediti_cliente: number(t.crediti_cliente),
          crediti_avvocato_antistatario: number(t.crediti_avvocato_antistatario),
          spese_liquidate_totale: number(t.spese_liquidate_totale),
          contributo_unificato_alert: number(t.contributo_unificato_alert),
        },
        worklist: asArray(se.worklist).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), hint: text(row.hint), value: text(row.value), tone: text(row.tone, 'neutral') as Tone } }),
        kpi: { label: text(kpi.label), value: text(kpi.value), tone: text(kpi.tone, 'neutral') as Tone },
      }
    })(),
    workflow: asArray(payload.workflow).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), value: text(row.value), note: text(row.note), tone: text(row.tone, 'neutral') as Tone, href: text(row.href) } }),
    regia: normalizeRegia(payload.regia),
    notificationRelata: normalizeNotificationRelata(payload.notificationRelata ?? payload.notification_relata),
    telematic: asArray(payload.telematic).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), value: text(row.value), note: text(row.note), tone: text(row.tone, 'neutral') as Tone, href: text(row.href) } }),
    quality: asArray(payload.quality).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), value: text(row.value), ok: bool(row.ok), tone: text(row.tone, 'neutral') as Tone } }),
    depositOffice: normalizeDepositOffice(payload.depositOffice ?? payload.deposit_office),
    depositCatalog: normalizeDepositCatalog(payload.depositCatalog ?? payload.deposit_catalog),
    depositReadiness: normalizeDepositReadiness(payload.depositReadiness ?? payload.deposit_readiness),
    depositPreparation: normalizeDepositPreparation(payload.depositPreparation ?? payload.deposit_preparation),
    signature: isRecord(payload.signature) ? {
      visibleSignatureMode: text(payload.signature.visibleSignatureMode ?? payload.signature.visible_signature_mode, 'laterale'),
      visibleSignaturePlace: text(payload.signature.visibleSignaturePlace ?? payload.signature.visible_signature_place),
      visibleSignatureDatetimeMode: text(payload.signature.visibleSignatureDatetimeMode ?? payload.signature.visible_signature_datetime_mode, 'data_ora'),
    } : emptyFascicoloDetail.signature,
    auditTrail: normalizeAuditTrail(payload.auditTrail ?? payload.audit_trail),
    actions: isRecord(payload.actions) ? {
      changeState: text(payload.actions.changeState), define: text(payload.actions.define), archive: text(payload.actions.archive), restore: text(payload.actions.restore), delete: text(payload.actions.delete), uploadDocument: text(payload.actions.uploadDocument), importPortal: text(payload.actions.importPortal), addActivity: text(payload.actions.addActivity), complianceOn: text(payload.actions.complianceOn), complianceOff: text(payload.actions.complianceOff), exportPdf: text(payload.actions.exportPdf), archiveZip: text(payload.actions.archiveZip), auditBundle: text(payload.actions.auditBundle), refreshLexIndex: text(payload.actions.refreshLexIndex), retryLexIndexErrors: text(payload.actions.retryLexIndexErrors),
    } : emptyFascicoloDetail.actions,
    options: { states: normalizeOptions(options.states), documentTypes: normalizeOptions(options.documentTypes), activityTypes: normalizeOptions(options.activityTypes), activityResults: normalizeOptions(options.activityResults) },
  }
}

function normalizeDepositReadiness(value: unknown): FascicoloDepositReadiness {
  const row = isRecord(value) ? value : {}
  const contribution = isRecord(row.contributoUnificato ?? row.contributo_unificato) ? (row.contributoUnificato ?? row.contributo_unificato) as Record<string, unknown> : {}
  const anagrafica = isRecord(row.anagraficaProcedimento ?? row.anagrafica_procedimento) ? (row.anagraficaProcedimento ?? row.anagrafica_procedimento) as Record<string, unknown> : {}
  const caseValue = isRecord(row.valoreCausa ?? row.valore_causa) ? (row.valoreCausa ?? row.valore_causa) as Record<string, unknown> : {}
  const mode = text(contribution.mode, 'da_definire') as FascicoloDepositReadiness['contributoUnificato']['mode']
  return {
    contributoUnificato: {
      ready: bool(contribution.ready),
      mode: ['esente', 'pagato', 'prenotato_a_debito'].includes(mode) ? mode : 'da_definire',
      label: text(contribution.label, emptyDepositReadiness.contributoUnificato.label),
      amount: contribution.amount === null || contribution.amount === undefined ? null : number(contribution.amount),
      amountLabel: text(contribution.amountLabel ?? contribution.amount_label),
      source: text(contribution.source),
      message: text(contribution.message, emptyDepositReadiness.contributoUnificato.message),
    },
    anagraficaProcedimento: {
      ready: bool(anagrafica.ready),
      label: text(anagrafica.label, emptyDepositReadiness.anagraficaProcedimento.label),
      missing: asArray(anagrafica.missing).map((item) => text(item)).filter(Boolean),
      message: text(anagrafica.message, emptyDepositReadiness.anagraficaProcedimento.message),
    },
    valoreCausa: {
      ready: bool(caseValue.ready),
      value: caseValue.value === null || caseValue.value === undefined ? null : number(caseValue.value),
      valueLabel: text(caseValue.valueLabel ?? caseValue.value_label),
      derivedFromExemption: bool(caseValue.derivedFromExemption ?? caseValue.derived_from_exemption),
      message: text(caseValue.message, emptyDepositReadiness.valoreCausa.message),
    },
  }
}

function normalizeDepositPreparation(value: unknown): FascicoloDepositPreparation {
  const row = isRecord(value) ? value : {}
  return {
    saved: bool(row.saved),
    typeKey: text(row.typeKey ?? row.type_key),
    typeLabel: text(row.typeLabel ?? row.type_label),
    policy: text(row.policy),
    updatedAt: text(row.updatedAt ?? row.updated_at),
    updatedBy: text(row.updatedBy ?? row.updated_by),
    datiattoExtra: isRecord(row.datiattoExtra ?? row.datiatto_extra)
      ? (row.datiattoExtra ?? row.datiatto_extra) as Record<string, unknown>
      : {},
    documents: asArray(row.documents).map((entry) => {
      const document = isRecord(entry) ? entry : {}
      return {
        documentId: text(document.documentId ?? document.document_id),
        selected: bool(document.selected),
        role: text(document.role, 'allegato'),
        alreadySigned: bool(document.alreadySigned ?? document.already_signed),
        requiresSignature: bool(document.requiresSignature ?? document.requires_signature),
      }
    }).filter((document) => document.documentId),
  }
}

function normalizeDepositCatalog(value: unknown): FascicoloDepositCatalog {
  const row = isRecord(value) ? value : {}
  const counts = isRecord(row.counts) ? row.counts : {}
  const entries = asArray(row.entries).map((entry, index): FascicoloDepositCatalogEntry => {
    const item = isRecord(entry) ? entry : {}
    const registry = isRecord(item.registry) ? item.registry : {}
    const quickOrganizer = isRecord(item.quickOrganizer ?? item.quick_organizer) ? (item.quickOrganizer ?? item.quick_organizer) as Record<string, unknown> : {}
    const payload = isRecord(item.payload) ? item.payload : {}
    const rules = isRecord(item.rules) ? item.rules : {}
    const schema = isRecord(item.schema) ? item.schema : {}
    const ui = isRecord(item.ui) ? item.ui : {}
    return {
      key: text(item.key, `deposito-${index}`),
      label: text(item.label ?? item.text, 'Tipo deposito'),
      macro: text(item.macro),
      category: text(item.category ?? item.categoria),
      path: text(item.path),
      prefix: text(item.prefix),
      channel: text(item.channel),
      registry: {
        code: text(registry.code ?? registry.codice),
        label: text(registry.label ?? registry.nome),
      },
      quickOrganizer: {
        rawKey: text(quickOrganizer.rawKey ?? quickOrganizer.raw_key),
        prefix: text(quickOrganizer.prefix),
        datiattoMethodsCount: number(quickOrganizer.datiattoMethodsCount ?? quickOrganizer.datiatto_methods_count),
        datiattoRootsCount: number(quickOrganizer.datiattoRootsCount ?? quickOrganizer.datiatto_roots_count),
      },
      payload: {
        tipo_atto: text(payload.tipo_atto),
        codice_registro: text(payload.codice_registro),
        tipo_deposito_telematico_key: text(payload.tipo_deposito_telematico_key),
        tipo_deposito_telematico_label: text(payload.tipo_deposito_telematico_label),
        tipo_deposito_telematico_channel: text(payload.tipo_deposito_telematico_channel),
        tipo_deposito_telematico_registry: text(payload.tipo_deposito_telematico_registry),
        tipo_deposito_telematico_policy: text(payload.tipo_deposito_telematico_policy),
        tipo_deposito_telematico_schema_status: text(payload.tipo_deposito_telematico_schema_status),
      },
      rules: {
        policy_code: text(rules.policy_code),
        channel_kind: text(rules.channel_kind),
        official_channel: text(rules.official_channel),
        registry_code: text(rules.registry_code),
        registry_label: text(rules.registry_label),
        transport_kind: text(rules.transport_kind),
        requires_datiatto: bool(rules.requires_datiatto),
        requires_indice_busta: bool(rules.requires_indice_busta),
        requires_atto_enc: bool(rules.requires_atto_enc),
        requires_pst_cer: bool(rules.requires_pst_cer),
        requires_local_signer: bool(rules.requires_local_signer),
        requires_local_pec: bool(rules.requires_local_pec),
        requires_relata: bool(rules.requires_relata),
        requires_receipts: bool(rules.requires_receipts),
        server_smtp_allowed: bool(rules.server_smtp_allowed),
        can_prepare_in_pct_panel: bool(rules.can_prepare_in_pct_panel),
        real_send_allowed_from_pct_panel: bool(rules.real_send_allowed_from_pct_panel),
        real_send_blocker: text(rules.real_send_blocker),
      },
      schema: {
        status: text(schema.status),
        label: text(schema.label),
        supported: bool(schema.supported),
        requiresSpecificGenerator: bool(schema.requiresSpecificGenerator ?? schema.requires_specific_generator),
        supportedMinisterialRoot: text(schema.supportedMinisterialRoot ?? schema.supported_ministerial_root),
        evidenceMethodsCount: number(schema.evidenceMethodsCount ?? schema.evidence_methods_count),
        evidenceRootsCount: number(schema.evidenceRootsCount ?? schema.evidence_roots_count),
        evidenceMethods: asArray(schema.evidenceMethods ?? schema.evidence_methods).map((item) => text(item)).filter(Boolean),
        evidenceRoots: asArray(schema.evidenceRoots ?? schema.evidence_roots).map((item) => text(item)).filter(Boolean),
        generatorClass: text(schema.generatorClass ?? schema.generator_class),
        ministerialRoot: text(schema.ministerialRoot ?? schema.ministerial_root),
        inputFields: asArray(schema.inputFields ?? schema.input_fields).map((field) => {
          const input = isRecord(field) ? field : {}
          return {
            id: text(input.id),
            label: text(input.label),
            type: text(input.type, 'text'),
            required: bool(input.required),
            group: text(input.group, 'Dati del deposito'),
            options: asArray(input.options).map((option) => {
              const item = isRecord(option) ? option : {}
              return { value: text(item.value), label: text(item.label) }
            }).filter((option) => option.value || option.label),
            note: text(input.note),
          }
        }).filter((field) => field.id && field.label),
      },
      ui: {
        service: text(ui.service),
        transport: text(ui.transport),
        behavior: text(ui.behavior),
        controls: asArray(ui.controls).map((item) => text(item)).filter(Boolean),
        documents: asArray(ui.documents).map((item) => text(item)).filter(Boolean),
      },
    }
  })
  const macroareas = asArray(row.macroareas).map((macro, index): FascicoloDepositCatalogMacroarea => {
    const item = isRecord(macro) ? macro : {}
    return {
      id: text(item.id, `macro-${index}`),
      label: text(item.label, 'Macroarea'),
      total: number(item.total),
      service: text(item.service),
      categories: asArray(item.categories).map((category, catIndex) => {
        const cat = isRecord(category) ? category : {}
        return {
          id: text(cat.id, `categoria-${index}-${catIndex}`),
          label: text(cat.label, 'Categoria'),
          total: number(cat.total),
          optionKeys: asArray(cat.optionKeys ?? cat.option_keys).map((item) => text(item)).filter(Boolean),
        }
      }),
    }
  })
  return {
    schemaVersion: number(row.schemaVersion ?? row.schema_version),
    source: text(row.source),
    sourceOfTruth: text(row.sourceOfTruth ?? row.source_of_truth),
    jsonAuthoritative: bool(row.jsonAuthoritative ?? row.json_authoritative),
    tenantScope: text(row.tenantScope ?? row.tenant_scope),
    generatedAt: text(row.generatedAt ?? row.generated_at),
    counts: {
      totalDepositTypes: number(counts.totalDepositTypes ?? counts.total_deposit_types),
      macroareas: isRecord(counts.macroareas) ? counts.macroareas as Record<string, number> : {},
      categories: isRecord(counts.categories) ? counts.categories as Record<string, number> : {},
    },
    officialSources: asArray(row.officialSources ?? row.official_sources).map((source) => {
      const item = isRecord(source) ? source : {}
      return { id: text(item.id), label: text(item.label ?? item.name), url: text(item.url), note: text(item.note) }
    }),
    referenceData: (() => {
      const referenceData = isRecord(row.referenceData ?? row.reference_data) ? (row.referenceData ?? row.reference_data) as Record<string, unknown> : {}
      const normalizeOptions = (value: unknown): FascicoloDepositInputOption[] => asArray(value).map((option) => {
        const item = isRecord(option) ? option : {}
        return { value: text(item.value), label: text(item.label) }
      }).filter((option) => option.value || option.label)
      return {
        titoliEsecutivi: normalizeOptions(referenceData.titoliEsecutivi ?? referenceData.titoli_esecutivi),
        ruoliProvvedimentoCassazione: normalizeOptions(referenceData.ruoliProvvedimentoCassazione ?? referenceData.ruoli_provvedimento_cassazione),
        materieCassazione: normalizeOptions(referenceData.materieCassazione ?? referenceData.materie_cassazione),
        classiImmobiliari: normalizeOptions(referenceData.classiImmobiliari ?? referenceData.classi_immobiliari),
      }
    })(),
    macroareas,
    entries,
  }
}

function normalizeDepositOffice(value: unknown): FascicoloDepositOffice {
  const row = isRecord(value) ? value : {}
  const name = text(row.name ?? row.nome)
  const pec = text(row.pec)
  const message = text(
    row.message ?? row.messaggio,
    pec
      ? 'PEC dell\'ufficio verificata dal catalogo uffici.'
      : 'PEC dell\'ufficio non disponibile: verificare prima dell\'invio reale.',
  )
  return {
    name,
    code: text(row.code ?? row.codice),
    ministerialCode: text(row.ministerialCode ?? row.codice_ministero ?? row.codiceMinistero),
    district: text(row.district ?? row.distretto),
    pec,
    kind: text(row.kind ?? row.tipo),
    verified: row.verified === undefined ? Boolean(name && pec) : bool(row.verified),
    message,
  }
}

function normalizeActivity(entry: unknown, index: number): FascicoloActivity {
  const row = isRecord(entry) ? entry : {}
  return {
    id: text(row.id, `att-${index}`),
    type: text(row.type ?? row.tipo),
    title: text(row.title ?? row.titolo, 'Attività'),
    date: text(row.date ?? row.data),
    description: text(row.description ?? row.descrizione),
    result: text(row.result ?? row.esito),
    place: text(row.place ?? row.luogo),
    notes: text(row.notes ?? row.note),
    lawyer: text(row.lawyer ?? row.avvocato),
    documentId: text(row.documentId ?? row.id_documento),
    depositId: text(row.depositId ?? row.id_deposito_pct),
    hearingTime: text(row.hearingTime ?? row.hearing_time),
    remoteHearingDetected: bool(row.remoteHearingDetected ?? row.remote_hearing_detected),
    remoteHearingMode: text(row.remoteHearingMode ?? row.remote_hearing_mode),
    remoteHearingUrl: text(row.remoteHearingUrl ?? row.remote_hearing_url),
    remoteHearingVerified: bool(row.remoteHearingVerified ?? row.remote_hearing_verified),
    remoteHearingPlatform: text(row.remoteHearingPlatform ?? row.remote_hearing_platform),
    remoteHearingMeetingId: text(row.remoteHearingMeetingId ?? row.remote_hearing_meeting_id),
    remoteHearingPasscode: text(row.remoteHearingPasscode ?? row.remote_hearing_passcode),
    remoteHearingAccessInfo: text(row.remoteHearingAccessInfo ?? row.remote_hearing_access_info),
    remoteHearingSource: text(row.remoteHearingSource ?? row.remote_hearing_source),
    updateAction: text(row.updateAction ?? row.update_action),
    deleteAction: text(row.deleteAction ?? row.delete_action),
    tone: text(row.tone, 'neutral') as Tone,
  }
}

function normalizeFormPayload(payload: unknown): FascicoloFormData {
  if (!isRecord(payload)) return emptyFascicoloForm
  const guardrails = isRecord(payload.guardrails) ? payload.guardrails : undefined
  const guardrailNextStepSource = guardrails ? guardrails.nextStep ?? guardrails.next_step : undefined
  const guardrailNextStep = isRecord(guardrailNextStepSource)
    ? { label: text(guardrailNextStepSource.label), href: text(guardrailNextStepSource.href) }
    : undefined
  return {
    source: text(payload.source, 'repository_reali'), generatedAt: text(payload.generatedAt ?? payload.generated_at), mode: text(payload.mode, 'new') === 'edit' ? 'edit' : 'new',
    action: text(payload.action, '/fascicoli/nuovo'), backHref: text(payload.backHref ?? payload.back_href, '/fascicoli'), detailHref: text(payload.detailHref ?? payload.detail_href, '/fascicoli'),
    query: isRecord(payload.query) ? Object.fromEntries(Object.entries(payload.query).map(([key, value]) => [key, text(value)])) : {},
    clients: asArray(payload.clients).map((entry) => {
      const row = isRecord(entry) ? entry : {}
      return {
        id: text(row.id),
        label: text(row.label ?? row.name),
        taxCode: text(row.taxCode ?? row.codice_fiscale),
        vat: text(row.vat ?? row.partita_iva),
        email: text(row.email),
        pec: text(row.pec),
        phone: text(row.phone ?? row.telefono ?? row.cellulare),
        type: text(row.type ?? row.tipo),
        href: text(row.href),
      }
    }).filter((row) => row.id),
    subjects: asArray(payload.subjects).map((entry) => {
      const row = isRecord(entry) ? entry : {}
      return {
        id: text(row.id),
        label: text(row.label ?? row.name ?? row.nome),
        taxCode: text(row.taxCode ?? row.codice_fiscale ?? row.identificativo),
        vat: text(row.vat ?? row.partita_iva),
        email: text(row.email),
        pec: text(row.pec),
        phone: text(row.phone ?? row.telefono ?? row.cellulare),
        type: text(row.type ?? row.tipo),
        qualification: text(row.qualification ?? row.qualifica),
        href: text(row.href),
      }
    }).filter((row) => row.id),
    judicialOffices: asArray(payload.judicialOffices ?? payload.judicial_offices ?? payload.offices).map((entry) => {
      const row = isRecord(entry) ? entry : {}
      return {
        value: text(row.value ?? row.nome),
        label: text(row.label ?? row.nome),
        code: text(row.code ?? row.codice),
        ministerialCode: text(row.ministerialCode ?? row.codice_ministero),
        district: text(row.district ?? row.distretto),
        pec: text(row.pec),
        kind: text(row.kind ?? row.tipo),
        services: asArray(row.services ?? row.servizi_ministero).map((item) => text(item)).filter(Boolean),
      }
    }).filter((row) => row.value),
    types: normalizeOptions(payload.types), states: normalizeOptions(payload.states),
    fascicolo: isRecord(payload.fascicolo) ? payload.fascicolo as FascicoloFormData['fascicolo'] : undefined,
    workflow: isRecord(payload.workflow) ? { title: text(payload.workflow.title), badges: asArray(payload.workflow.badges).map((badge) => text(badge)).filter(Boolean), summary: text(payload.workflow.summary), checklist: asArray(payload.workflow.checklist).map((item) => text(item)).filter(Boolean), values: normalizeKeyValues(payload.workflow.values) } : undefined,
    correction: isRecord(payload.correction) ? { active: bool(payload.correction.active), title: text(payload.correction.title), help: text(payload.correction.help), highlight: text(payload.correction.highlight) } : undefined,
    guardrails: guardrails ? {
      available: guardrails.available === undefined ? true : bool(guardrails.available),
      title: text(guardrails.title, 'Presidio apertura fascicolo'),
      portal: text(guardrails.portal, 'PCT'),
      channel: text(guardrails.channel, 'PCT_TELEMATICO'),
      channelLabel: text(guardrails.channelLabel ?? guardrails.channel_label, 'PCT / PST Civile'),
      mode: text(guardrails.mode, 'opening'),
      blocking: asArray(guardrails.blocking).map((entry) => { const row = isRecord(entry) ? entry : {}; return { code: text(row.code), message: text(row.message), field: text(row.field) } }).filter((issue) => issue.message),
      warnings: asArray(guardrails.warnings).map((entry) => { const row = isRecord(entry) ? entry : {}; return { code: text(row.code), message: text(row.message), field: text(row.field) } }).filter((issue) => issue.message),
      requiredOpeningFields: asArray(guardrails.requiredOpeningFields ?? guardrails.required_opening_fields).map((item) => text(item)).filter(Boolean),
      nextStep: guardrailNextStep,
    } : undefined,
  }
}

function normalizeExportPayload(payload: unknown): FascicoliExportData {
  if (!isRecord(payload)) return emptyFascicoliExport
  const recent = asArray(payload.recent).map(normalizeItem)
  return {
    source: text(payload.source, 'repository_reali'), generatedAt: text(payload.generatedAt ?? payload.generated_at), summary: normalizeSummary(payload.summary, recent),
    formats: asArray(payload.formats).map((entry) => { const row = isRecord(entry) ? entry : {}; return { id: text(row.id), label: text(row.label), description: text(row.description), href: text(row.href), tone: text(row.tone, 'primary') as Tone } }),
    fields: asArray(payload.fields).map((entry) => { const row = isRecord(entry) ? entry : {}; return { key: text(row.key), label: text(row.label), checked: row.checked === undefined ? true : bool(row.checked) } }),
    presets: asArray(payload.presets).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), description: text(row.description), href: text(row.href), tone: text(row.tone, 'primary') as Tone } }),
    recent,
    facets: normalizeFacets(payload.facets, recent),
  }
}

export function formatFascicoloType(value: FascicoloRow['type']): string {
  return typeLabels[value] || 'Altro'
}

export function formatFascicoloStatus(value: FascicoloRow['status']): string {
  return statusLabels[value] || 'Aperto'
}

const transientFetchStatuses = new Set([408, 423, 429, 500, 502, 503, 504])

function retryDelay(attempt: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, 300 * (attempt + 1)))
}

async function safeFetch<T>(url: string, normalizer: (payload: unknown) => T, fallback: T): Promise<T> {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
      if (response.ok) return normalizer(await response.json())
      if (response.status === 401 || response.status === 403 || response.status === 404) {
        const fallbackPayload = {
          notFound: true,
          errore: response.status === 401
            ? 'Autenticazione richiesta per caricare i dati del fascicolo.'
            : response.status === 403
              ? 'Permessi insufficienti per aprire il fascicolo.'
              : 'Fascicolo non disponibile nella fonte dati corrente.',
        }
        return normalizer(fallbackPayload)
      }
      if (!transientFetchStatuses.has(response.status) || attempt === 2) return fallback
    } catch {
      if (attempt === 2) return fallback
    }
    await retryDelay(attempt)
  }
  return fallback
}

function buildFascicoliQuery(params: FascicoliPageParams = {}): string {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.pageSize) query.set('page_size', String(params.pageSize))
  if (params.q?.trim()) query.set('q', params.q.trim())
  if (params.client?.trim()) query.set('client', params.client.trim())
  if (params.rg?.trim()) query.set('rg', params.rg.trim())
  if (params.type && params.type !== 'tutti') query.set('type', params.type)
  if (params.status && params.status !== 'tutti') query.set('status', params.status)
  if (params.court?.trim()) query.set('court', params.court.trim())
  if (params.sort) query.set('sort', params.sort)
  if (params.view?.trim()) query.set('view', params.view.trim())
  if (params.alertsOnly) query.set('alerts_only', '1')
  if (params.paymentsOnly) query.set('payments_only', '1')
  if (params.missingRgOnly) query.set('missing_rg_only', '1')
  if (params.duplicatesOnly) query.set('duplicates_only', '1')
  if (params.cu && params.cu !== 'tutti') query.set('cu', params.cu)
  if (params.fondoSpese && params.fondoSpese !== 'tutti') query.set('fondo_spese', params.fondoSpese)
  if (params.liquidazione && params.liquidazione !== 'tutti') query.set('liquidazione', params.liquidazione)
  if (params.parcella && params.parcella !== 'tutti') query.set('parcella', params.parcella)
  const suffix = query.toString()
  return suffix ? `?${suffix}` : ''
}

export function getFascicoliPage(params: FascicoliPageParams = {}): Promise<FascicoliPageData> {
  return safeFetch(`/api/v1/ui/fascicoli${buildFascicoliQuery(params)}`, normalizePagePayload, emptyFascicoliPage)
}

export type FascicoliEconomicPresidioResult = {
  ok: boolean
  message: string
  createdCount: number
  existingCount: number
  missingBasisCount: number
  processedDefined: number
  contributiCheckedCount: number
  contributiUpdatedCount: number
  contributiMissingCount: number
  documentAnalysisUpdatedCount: number
  statusDefinedUpdatedCount: number
}

export async function runFascicoliEconomicPresidio(limit = 500): Promise<FascicoliEconomicPresidioResult> {
  const token = csrfToken()
  const response = await fetch('/api/v1/ui/fascicoli/presidio-economico/proforme', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify({ limit }),
  })
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok || payload.ok === false) {
    throw new Error(text(payload.message ?? payload.errore ?? payload.error, 'Presidio economico non completato.'))
  }
  return {
    ok: true,
    message: text(payload.message, 'Presidio economico completato.'),
    createdCount: number(payload.createdCount ?? payload.created_count),
    existingCount: number(payload.existingCount ?? payload.existing_count),
    missingBasisCount: number(payload.missingBasisCount ?? payload.missing_basis_count),
    processedDefined: number(payload.processedDefined ?? payload.processed_defined),
    contributiCheckedCount: number(payload.contributiCheckedCount ?? payload.contributi_checked_count),
    contributiUpdatedCount: number(payload.contributiUpdatedCount ?? payload.contributi_updated_count),
    contributiMissingCount: number(payload.contributiMissingCount ?? payload.contributi_missing_count),
    documentAnalysisUpdatedCount: number(payload.documentAnalysisUpdatedCount ?? payload.document_analysis_updated_count),
    statusDefinedUpdatedCount: number(payload.statusDefinedUpdatedCount ?? payload.status_defined_updated_count),
  }
}

export function getFascicoliArchive(): Promise<FascicoliPageData> {
  return safeFetch('/api/v1/ui/fascicoli/archivio', normalizePagePayload, emptyFascicoliPage)
}

export function getFascicoloDetail(id: string, options: { include?: 'all' | FascicoloDetailSection[] } = {}): Promise<FascicoloDetailData> {
  const query = new URLSearchParams()
  if (options.include === 'all') query.set('include', 'all')
  else if (Array.isArray(options.include) && options.include.length) query.set('include', options.include.join(','))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return safeFetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}${suffix}`, normalizeDetailPayload, emptyFascicoloDetail)
}

export function getFascicoloDetailSection(id: string, section: FascicoloDetailSection): Promise<FascicoloDetailData> {
  if (section === 'regia') {
    return safeFetch(
      `/api/v1/ui/fascicoli/${encodeURIComponent(id)}/regia`,
      (payload) => ({ ...emptyFascicoloDetail, regia: normalizeRegia(payload) }),
      emptyFascicoloDetail,
    )
  }
  if (section === 'relata' || section === 'audit' || section === 'lex') {
    return safeFetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}/${section}`, normalizeDetailPayload, emptyFascicoloDetail)
  }
  return safeFetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}/${section}`, normalizeDetailPayload, emptyFascicoloDetail)
}

export function getFascicoloForm(id?: string, query = ''): Promise<FascicoloFormData> {
  const path = id ? `/api/v1/ui/fascicoli/${encodeURIComponent(id)}/modifica` : '/api/v1/ui/fascicoli/nuovo'
  return safeFetch(`${path}${query}`, normalizeFormPayload, emptyFascicoloForm)
}

export function getFascicoliExport(): Promise<FascicoliExportData> {
  return safeFetch('/api/v1/ui/fascicoli/export', normalizeExportPayload, emptyFascicoliExport)
}

export type FascicoloStatusUpdateResult = {
  ok: boolean
  message: string
  status: FascicoloStato
  tone: Tone
}

export async function updateFascicoloStatus(id: string, stato: FascicoloStato): Promise<FascicoloStatusUpdateResult> {
  const token = csrfToken()
  const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}/stato`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify({ stato }),
  })
  const contentType = response.headers.get('content-type') || ''
  const rawPayload = contentType.includes('application/json') ? await response.json().catch(() => ({})) : {}
  const raw = isRecord(rawPayload) ? rawPayload : {}
  const message = text(raw.message ?? raw.messaggio ?? raw.errore ?? raw.error, response.ok ? 'Stato fascicolo aggiornato.' : 'Non ho potuto aggiornare lo stato del fascicolo.')
  if (!response.ok || raw.ok === false) {
    throw new Error(message || 'Non ho potuto aggiornare lo stato del fascicolo.')
  }
  const fascicolo = isRecord(raw.fascicolo) ? raw.fascicolo : {}
  return {
    ok: true,
    message,
    status: text(fascicolo.status, stato) as FascicoloStato,
    tone: text(fascicolo.tone, 'primary') as Tone,
  }
}

export async function updateFascicoloPayment(id: string, kind: FascicoloPaymentKind, payload: FascicoloPaymentUpdatePayload): Promise<FascicoloPaymentUpdateResult> {
  const token = csrfToken()
  const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}/pagamenti/${kind}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify({
      status: payload.status,
      importo: payload.importo === '' ? null : payload.importo ?? null,
      dataPagamento: payload.dataPagamento || '',
      metodo: payload.metodo || '',
      note: payload.note || '',
    }),
  })
  const contentType = response.headers.get('content-type') || ''
  const rawPayload = contentType.includes('application/json') ? await response.json().catch(() => ({})) : {}
  const raw = isRecord(rawPayload) ? rawPayload : {}
  const message = text(raw.message ?? raw.messaggio ?? raw.errore ?? raw.error, response.ok ? 'Controllo economico aggiornato.' : 'Non ho potuto aggiornare il controllo economico.')
  if (!response.ok || raw.ok === false) {
    const errors = isRecord(raw.errors) ? Object.fromEntries(Object.entries(raw.errors).map(([key, value]) => [key, text(value)])) : {}
    throw new Error(message || Object.values(errors)[0] || 'Non ho potuto aggiornare il controllo economico.')
  }
  const paymentSummary = normalizePaymentSummary(raw.paymentSummary ?? raw.payment_summary, id)
  return {
    ok: true,
    message,
    payment: normalizePaymentItem(raw.payment, kind, id),
    paymentSummary,
    fascicolo: isRecord(raw.fascicolo) ? { id: text(raw.fascicolo.id, id) } : { id },
    errors: {},
  }
}

export async function generateFascicoloProforma(
  id: string,
  basis?: FascicoloProformaBasis,
): Promise<FascicoloProformaGenerationResult> {
  const token = csrfToken()
  const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}/proforma/genera`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify(basis ? { basis } : {}),
  })
  const contentType = response.headers.get('content-type') || ''
  const rawPayload = contentType.includes('application/json') ? await response.json().catch(() => ({})) : {}
  const raw = isRecord(rawPayload) ? rawPayload : {}
  const message = text(
    raw.message ?? raw.messaggio ?? raw.errore ?? raw.error,
    response.ok ? 'Proforma generata.' : 'Non ho potuto generare la proforma.',
  )
  if (!response.ok || raw.ok === false) {
    const errors = isRecord(raw.errors)
      ? Object.values(raw.errors).map((value) => text(value)).filter(Boolean)
      : []
    const details = Array.from(new Set(errors))
    throw new Error(details.length ? `${message} ${details.join(' ')}` : message)
  }
  const item = isRecord(raw.item) ? raw.item : {}
  return {
    ok: true,
    existing: Boolean(raw.existing),
    message,
    proformaId: text(raw.proformaId ?? raw.proforma_id ?? item.id),
    proformaNumber: text(raw.proformaNumber ?? raw.proforma_number ?? item.number),
    redirectHref: text(raw.redirectHref ?? raw.redirect_href),
    paymentSummary: normalizePaymentSummary(raw.paymentSummary ?? raw.payment_summary, id),
  }
}
