import type { Tone } from './data'
import { sanitizeDisplayText } from './displayText'

export type FascicoloTipo = 'tutti' | 'civile' | 'penale' | 'amministrativo' | 'tributario' | 'stragiudiziale' | 'consulenza' | 'lavoro' | 'famiglia' | 'successioni' | 'altro'
export type FascicoloStato = 'tutti' | 'aperto' | 'in_corso' | 'definito' | 'da_archiviare' | 'archiviato' | 'sospeso'

export type Facet<T extends string> = { value: T; label: string; count: number }
export type SelectOption = { value: string; label: string }
export type ActionLink = { label: string; href: string; tone?: Tone; method?: 'get' | 'post'; confirm?: string }
export type KeyValue = { label: string; value: string; mono?: boolean; href?: string; tone?: Tone }

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
}

export type FascicoliPagination = {
  page: number
  pageSize: number
  total: number
  pages: number
}

export type FascicoliPageParams = {
  page?: number
  pageSize?: number
  q?: string
  type?: FascicoloTipo
  status?: FascicoloStato
  court?: string
  sort?: string
  alertsOnly?: boolean
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
  actions: {
    preview: string
    download: string
    edit: string
    sign: string
    pdfa: string
    attest: string
    metadata: string
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

export type FascicoloDeposit = {
  id: string
  timestamp: string
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
  tone: Tone
}

export type FascicoloParty = { id: string; name: string; role: string; taxCode: string; email: string; pec: string; phone: string; href: string }
export type FascicoloHistory = { date: string; description: string; from: string; to: string; notes: string; lawyer: string }
export type FascicoloMoney = { id: string; label: string; value: string; note: string; href: string; tone: Tone }
export type FascicoloPerson = { id: string; name: string; taxCode: string; vat: string; email: string; pec: string; phone: string; address: string; href: string }

export type FascicoloFull = FascicoloRow & {
  object: string
  counterparty: string
  counterpartyTaxCode: string
  judge: string
  section: string
  leadLawyer: string
  dominus: string
  value: string
  quotedValue: string
  agreedFee: string
  procedureType: string
  practiceId: string
  practiceArea: string
  proceduraOperativaCodice: string
  codiceOggettoPst: string
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
  last_indexed_at: string | null
  status: 'ready' | 'partial' | 'working' | 'error' | 'stale'
}

export type FascicoloDetailData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes: 'operational_routes' | 'api' }
  notFound?: boolean
  fascicolo: FascicoloFull
  quickCounts: Record<string, number>
  lexIndexing: LexIndexingSummary
  profile: KeyValue[]
  documents: FascicoloDocument[]
  activities: FascicoloActivity[]
  deadlines: FascicoloDeadline[]
  appointments: FascicoloAppointment[]
  deposits: FascicoloDeposit[]
  requests: FascicoloActivity[]
  parties: FascicoloParty[]
  history: FascicoloHistory[]
  client?: FascicoloPerson
  economics: FascicoloMoney[]
  workflow: Array<{ label: string; value: string; note: string; tone: Tone; href: string }>
  regia: RegiaOperativaData
  telematic: Array<{ label: string; value: string; note: string; href: string; tone: Tone }>
  quality: Array<{ label: string; value: string; ok: boolean; tone: Tone }>
  signature: { visibleSignatureMode: string; visibleSignaturePlace: string; visibleSignatureDatetimeMode: string }
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

export type FascicoloDetailSection = 'documenti' | 'attivita' | 'scadenze' | 'depositi' | 'regia'

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
}

export const emptyFascicoliPage: FascicoliPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes' },
  summary: emptySummary,
  items: [],
  pagination: { page: 1, pageSize: 25, total: 0, pages: 0 },
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

export const emptyFascicoloDetail: FascicoloDetailData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes' },
  fascicolo: {
    id: '', ref: 'n.d.', internalRef: 'n.d.', title: 'Fascicolo non trovato', subtitle: '', type: 'altro', client: 'n.d.', court: 'n.d.', rg: 'n.d.',
    nextDeadline: 'n.d.', nextDeadlineIso: '', status: 'aperto', documents: 0, unreadCommunications: 0, alerts: 0, openedAt: '', closedAt: '', updatedAt: '',
    href: '/fascicoli', operationalHref: '/fascicoli', editHref: '/fascicoli', operationalEditHref: '/fascicoli', exportPdfHref: '', deleteHref: '', archiveZipHref: '', restoreAction: '', tone: 'neutral',
    object: '', counterparty: '', counterpartyTaxCode: '', judge: '', section: '', leadLawyer: '', dominus: '', value: '', quotedValue: '', agreedFee: '',
    procedureType: '', practiceId: '', practiceArea: '', proceduraOperativaCodice: '', codiceOggettoPst: '', fonteCodiceOggetto: '', fileFonteCodiceOggetto: '',
    riferimentoCartaceo: '', attorePrincipale: '', istruttorePmGip: '', cancelliere: '', ctu: '', ctp: '',
    statoPraticaOperativa: '', personalizzabile: false, fascicoloVeloce: false, documentiInizialiCount: 0, emailInizialiCount: 0, dataAperturaIso: '', dataChiusuraIso: '',
    firstHearing: '', citationNotification: '', nextHearing: '', notes: '', reservedNotes: '',
    source: '', sourceExternalId: '', lastSyncAt: '', syncStatus: '', importLogId: '', hasConflicts: false, documentSyncEnabled: false,
    eventsSyncEnabled: false, complianceControlsEnabled: true, archiveReady: false,
  },
  quickCounts: {}, lexIndexing: { total_documents: 0, ready: 0, queued: 0, indexing: 0, errors: 0, stale: 0, last_indexed_at: null, status: 'ready' }, profile: [], documents: [], activities: [], deadlines: [], appointments: [], deposits: [], requests: [], parties: [], history: [],
  economics: [], workflow: [], telematic: [], quality: [],
  regia: emptyRegiaOperativa,
  signature: { visibleSignatureMode: 'laterale', visibleSignaturePlace: '', visibleSignatureDatetimeMode: 'data_ora' },
  actions: { changeState: '', define: '', archive: '', restore: '', delete: '', uploadDocument: '', importPortal: '', addActivity: '', complianceOn: '', complianceOff: '', exportPdf: '', archiveZip: '', refreshLexIndex: '', retryLexIndexErrors: '' },
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
    }
  }
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
    const pageSize = Math.max(1, number(value.pageSize ?? value.page_size) || 25)
    const total = Math.max(0, number(value.total ?? summary.total ?? items.length))
    const pages = Math.max(0, number(value.pages) || (total ? Math.ceil(total / pageSize) : 0))
    const page = Math.min(Math.max(1, number(value.page) || 1), Math.max(1, pages || 1))
    return { page, pageSize, total, pages }
  }
  const total = Math.max(0, summary.total || items.length)
  const pageSize = items.length || 25
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

function normalizeDetailPayload(payload: unknown): FascicoloDetailData {
  if (!isRecord(payload)) return emptyFascicoloDetail
  const base = normalizeItem(payload.fascicolo ?? {}, 0)
  const fullPayload = isRecord(payload.fascicolo) ? payload.fascicolo : {}
  const full: FascicoloFull = {
    ...emptyFascicoloDetail.fascicolo,
    ...base,
    object: text(fullPayload.object ?? fullPayload.oggetto),
    counterparty: text(fullPayload.counterparty ?? fullPayload.controparte),
    counterpartyTaxCode: text(fullPayload.counterpartyTaxCode ?? fullPayload.cf_controparte),
    judge: text(fullPayload.judge ?? fullPayload.giudice),
    section: text(fullPayload.section ?? fullPayload.sezione),
    leadLawyer: text(fullPayload.leadLawyer ?? fullPayload.avvocato_referente),
    dominus: text(fullPayload.dominus ?? fullPayload.avvocato_dominus),
    value: text(fullPayload.value ?? fullPayload.valore_causa),
    quotedValue: text(fullPayload.quotedValue ?? fullPayload.valore_preventivato),
    agreedFee: text(fullPayload.agreedFee ?? fullPayload.compenso_pattuito),
    procedureType: text(fullPayload.procedureType ?? fullPayload.tipo_procedimento),
    practiceId: text(fullPayload.practiceId ?? fullPayload.id_pratica),
    practiceArea: text(fullPayload.practiceArea ?? fullPayload.area_pratica),
    proceduraOperativaCodice: text(fullPayload.proceduraOperativaCodice ?? fullPayload.procedura_operativa_codice),
    codiceOggettoPst: text(fullPayload.codiceOggettoPst ?? fullPayload.codice_oggetto_pst),
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
    fascicolo: full,
    quickCounts: isRecord(payload.quickCounts ?? payload.quick_counts) ? payload.quickCounts as Record<string, number> : {},
    lexIndexing: {
      total_documents: number(lexIndexingSource.total_documents ?? lexIndexingSource.totalDocuments),
      ready: number(lexIndexingSource.ready),
      queued: number(lexIndexingSource.queued),
      indexing: number(lexIndexingSource.indexing),
      errors: number(lexIndexingSource.errors),
      stale: number(lexIndexingSource.stale),
      last_indexed_at: text(lexIndexingSource.last_indexed_at ?? lexIndexingSource.lastIndexedAt) || null,
      status: text(lexIndexingSource.status, 'ready') as LexIndexingSummary['status'],
    },
    profile: normalizeKeyValues(payload.profile),
    documents: asArray(payload.documents).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      const actions = isRecord(row.actions) ? row.actions : {}
      return {
        id: text(row.id, `doc-${index}`), name: text(row.name ?? row.nome, 'Documento'), type: text(row.type ?? row.tipo, 'ALTRO'), size: text(row.size ?? row.dimensione, ''),
        uploadedAt: text(row.uploadedAt ?? row.data_caricamento), documentDate: text(row.documentDate ?? row.data_documento), notes: text(row.notes ?? row.note),
        tags: asArray(row.tags).map((tag) => text(tag)).filter(Boolean), signed: bool(row.signed ?? row.firmato),
        statusLabel: text(row.statusLabel ?? row.status_label, bool(row.signed ?? row.firmato) ? 'Firmato' : 'Da firmare'),
        statusTone: text(row.statusTone ?? row.status_tone, bool(row.signed ?? row.firmato) ? 'success' : 'warning') as Tone,
        source: text(row.source ?? row.fonte_documento),
        portalName: text(row.portalName ?? row.nome_portale), portalClass: text(row.portalClass ?? row.classificazione_portale), portalSender: text(row.portalSender ?? row.mittente_portale),
        portalDate: text(row.portalDate ?? row.data_deposito_portale), hash: text(row.hash ?? row.hash_sha256),
        actions: {
          preview: text(actions.preview), download: text(actions.download), edit: text(actions.edit), sign: text(actions.sign), pdfa: text(actions.pdfa), attest: text(actions.attest), metadata: text(actions.metadata), delete: text(actions.delete),
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
    deposits: asArray(payload.deposits).map((entry, index) => {
      const row = isRecord(entry) ? entry : {}
      return { id: text(row.id, `dep-${index}`), timestamp: text(row.timestamp), status: text(row.status ?? row.stato), actType: text(row.actType ?? row.tipo_atto), pec: text(row.pec ?? row.pec_destinatario), message: text(row.message ?? row.messaggio), checks: text(row.checks ?? row.esito_controlli), source: text(row.source ?? row.fonte_portale), externalId: text(row.externalId ?? row.id_deposito_esterno), mainFile: text(row.mainFile ?? row.nome_atto_principale), documentsCount: number(row.documentsCount ?? row.documenti_count), portalDocuments: asArray(row.portalDocuments ?? row.documenti_portale).map((doc) => { const d = isRecord(doc) ? doc : {}; return { name: text(d.name ?? d.nome, 'Documento'), type: text(d.type ?? d.tipo), date: text(d.date ?? d.data), sender: text(d.sender ?? d.mittente), imported: bool(d.imported ?? d.gia_importato), available: d.available === undefined ? true : bool(d.available ?? d.disponibile) } }), tone: text(row.tone, 'primary') as Tone }
    }),
    requests: asArray(payload.requests).map(normalizeActivity),
    parties: asArray(payload.parties).map((entry, index) => { const row = isRecord(entry) ? entry : {}; return { id: text(row.id, `party-${index}`), name: text(row.name ?? row.nome, 'Soggetto'), role: text(row.role ?? row.ruolo), taxCode: text(row.taxCode ?? row.codice_fiscale), email: text(row.email), pec: text(row.pec), phone: text(row.phone ?? row.telefono), href: text(row.href, '/soggetti') } }),
    history: asArray(payload.history).map((entry) => { const row = isRecord(entry) ? entry : {}; return { date: text(row.date ?? row.data), description: text(row.description ?? row.descrizione), from: text(row.from ?? row.stato_precedente), to: text(row.to ?? row.stato_nuovo), notes: text(row.notes ?? row.note), lawyer: text(row.lawyer ?? row.avvocato) } }),
    client: isRecord(payload.client) ? { id: text(payload.client.id), name: text(payload.client.name ?? payload.client.nome, 'Cliente'), taxCode: text(payload.client.taxCode ?? payload.client.codice_fiscale), vat: text(payload.client.vat ?? payload.client.partita_iva), email: text(payload.client.email), pec: text(payload.client.pec), phone: text(payload.client.phone ?? payload.client.telefono), address: text(payload.client.address ?? payload.client.indirizzo), href: text(payload.client.href, '/clienti') } : undefined,
    economics: asArray(payload.economics).map((entry, index) => { const row = isRecord(entry) ? entry : {}; return { id: text(row.id, `money-${index}`), label: text(row.label), value: text(row.value), note: text(row.note), href: text(row.href, '/fatturazione'), tone: text(row.tone, 'neutral') as Tone } }),
    workflow: asArray(payload.workflow).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), value: text(row.value), note: text(row.note), tone: text(row.tone, 'neutral') as Tone, href: text(row.href) } }),
    regia: normalizeRegia(payload.regia),
    telematic: asArray(payload.telematic).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), value: text(row.value), note: text(row.note), tone: text(row.tone, 'neutral') as Tone, href: text(row.href) } }),
    quality: asArray(payload.quality).map((entry) => { const row = isRecord(entry) ? entry : {}; return { label: text(row.label), value: text(row.value), ok: bool(row.ok), tone: text(row.tone, 'neutral') as Tone } }),
    signature: isRecord(payload.signature) ? {
      visibleSignatureMode: text(payload.signature.visibleSignatureMode ?? payload.signature.visible_signature_mode, 'laterale'),
      visibleSignaturePlace: text(payload.signature.visibleSignaturePlace ?? payload.signature.visible_signature_place),
      visibleSignatureDatetimeMode: text(payload.signature.visibleSignatureDatetimeMode ?? payload.signature.visible_signature_datetime_mode, 'data_ora'),
    } : emptyFascicoloDetail.signature,
    actions: isRecord(payload.actions) ? {
      changeState: text(payload.actions.changeState), define: text(payload.actions.define), archive: text(payload.actions.archive), restore: text(payload.actions.restore), delete: text(payload.actions.delete), uploadDocument: text(payload.actions.uploadDocument), importPortal: text(payload.actions.importPortal), addActivity: text(payload.actions.addActivity), complianceOn: text(payload.actions.complianceOn), complianceOff: text(payload.actions.complianceOff), exportPdf: text(payload.actions.exportPdf), archiveZip: text(payload.actions.archiveZip), refreshLexIndex: text(payload.actions.refreshLexIndex), retryLexIndexErrors: text(payload.actions.retryLexIndexErrors),
    } : emptyFascicoloDetail.actions,
    options: { states: normalizeOptions(options.states), documentTypes: normalizeOptions(options.documentTypes), activityTypes: normalizeOptions(options.activityTypes), activityResults: normalizeOptions(options.activityResults) },
  }
}

function normalizeActivity(entry: unknown, index: number): FascicoloActivity {
  const row = isRecord(entry) ? entry : {}
  return { id: text(row.id, `att-${index}`), type: text(row.type ?? row.tipo), title: text(row.title ?? row.titolo, 'Attivit?'), date: text(row.date ?? row.data), description: text(row.description ?? row.descrizione), result: text(row.result ?? row.esito), place: text(row.place ?? row.luogo), notes: text(row.notes ?? row.note), lawyer: text(row.lawyer ?? row.avvocato), documentId: text(row.documentId ?? row.id_documento), depositId: text(row.depositId ?? row.id_deposito_pct), updateAction: text(row.updateAction ?? row.update_action), deleteAction: text(row.deleteAction ?? row.delete_action), tone: text(row.tone, 'neutral') as Tone }
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
      title: text(guardrails.title, 'Presidio deposito assistito'),
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

async function safeFetch<T>(url: string, normalizer: (payload: unknown) => T, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return fallback
    return normalizer(await response.json())
  } catch {
    return fallback
  }
}

function buildFascicoliQuery(params: FascicoliPageParams = {}): string {
  const query = new URLSearchParams()
  if (params.page) query.set('page', String(params.page))
  if (params.pageSize) query.set('page_size', String(params.pageSize))
  if (params.q?.trim()) query.set('q', params.q.trim())
  if (params.type && params.type !== 'tutti') query.set('type', params.type)
  if (params.status && params.status !== 'tutti') query.set('status', params.status)
  if (params.court?.trim()) query.set('court', params.court.trim())
  if (params.sort) query.set('sort', params.sort)
  if (params.alertsOnly) query.set('alerts_only', '1')
  const suffix = query.toString()
  return suffix ? `?${suffix}` : ''
}

export function getFascicoliPage(params: FascicoliPageParams = {}): Promise<FascicoliPageData> {
  return safeFetch(`/api/v1/ui/fascicoli${buildFascicoliQuery(params)}`, normalizePagePayload, emptyFascicoliPage)
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
  return safeFetch(`/api/v1/ui/fascicoli/${encodeURIComponent(id)}/${section}`, normalizeDetailPayload, emptyFascicoloDetail)
}

export function getFascicoloForm(id?: string, query = ''): Promise<FascicoloFormData> {
  const path = id ? `/api/v1/ui/fascicoli/${encodeURIComponent(id)}/modifica` : '/api/v1/ui/fascicoli/nuovo'
  return safeFetch(`${path}${query}`, normalizeFormPayload, emptyFascicoloForm)
}

export function getFascicoliExport(): Promise<FascicoliExportData> {
  return safeFetch('/api/v1/ui/fascicoli/export', normalizeExportPayload, emptyFascicoliExport)
}
