import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type LegalTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type LegalUiContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  external_fetch: boolean
  ai_generation: boolean
  canonical_source: string
  legacy_contract?: string
}

export type LegalMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: LegalTone
}

export type LegalSectionItem = {
  id: string
  label: string
  value: string | number
  note: string
  tone: LegalTone
}

export type LegalSection = {
  id: string
  title: string
  kind: string
  items: LegalSectionItem[]
  emptyMessage: string
}

export type LegalAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: LegalTone
}

export type LegalWarning = {
  code: string
  message: string
}

export type GiurisprudenzaSource = {
  id: string
  label: string
  kind: string
  coverage: string
  accessMode: string
  sourceHref: string
  legacyHref: string
  lastRunAt: string
  stateLabel: string
  stateTone: LegalTone
  resolutionNote: string
  count: number
  evidenceType: string
}

export type PracticeLink = {
  id: string
  label: string
  href: string
}

export type GiurisprudenzaRecord = {
  id: string
  title: string
  subtitle: string
  sourceId: string
  sourceLabel: string
  sourceKind: string
  authority: string
  office: string
  date: string
  area: string
  branch: string
  subbranch: string
  grade: string
  jurisdiction: string
  caseNumber: string
  ecli: string
  orientation: string
  orientationKind: string
  verificationLabel: string
  verificationTone: LegalTone
  citationLabel: string
  tags: string[]
  legacyHref: string
  practiceLinks: PracticeLink[]
  evidenceType: string
  sourceHref: string
  summary: string
  principle: string
  abstract: string
  practicalUse: string
  reliabilityNote: string
  officialSource: boolean
  fullTextAvailable: boolean
}

export type GiurisprudenzaPageData = {
  source: string
  generated_at: string
  contracts: LegalUiContract
  metrics: LegalMetric[]
  sections: LegalSection[]
  records: GiurisprudenzaRecord[]
  actions: LegalAction[]
  forms: []
  warnings: LegalWarning[]
  sources: GiurisprudenzaSource[]
  filters: Record<string, string>
}

export type GiurisprudenzaCreateOption = {
  value: string
  label: string
}

export type GiurisprudenzaCreateDefaults = {
  titolo: string
  source_system: string
  giurisdizione: string
  ufficio: string
  organo_giudicante: string
  grado: string
  sezione: string
  numero_provvedimento: string
  data_decisione: string
  data_deposito: string
  tipo_provvedimento: string
  area: string
  branca: string
  sottobranca: string
  microtema: string
  rito: string
  materia: string
  norme_citate: string
  parole_chiave: string
  massima: string
  principio_diritto: string
  abstract: string
  esito: string
  orientamento: string
  rilevanza_pratica: string
  uso_nel_software: string
  ecli: string
  url_origine: string
  url_pagina_ufficiale: string
  url_pdf_ufficiale: string
  text_original: string
  note_redazionali: string
}

export type GiurisprudenzaCreatePageData = {
  source: string
  generated_at: string
  contracts: LegalUiContract
  defaults: GiurisprudenzaCreateDefaults
  options: Record<string, GiurisprudenzaCreateOption[]>
  sources: GiurisprudenzaSource[]
  actions: LegalAction[]
  forms: { id: string; method: string; endpoint: string }[]
  warnings: LegalWarning[]
}

export type GiurisprudenzaCreateResponse = {
  ok: boolean
  message: string
  errors: Record<string, string>
  warnings: LegalWarning[]
  record: GiurisprudenzaRecord | null
  redirectHref: string
  status?: number
}

export const emptyGiurisprudenzaPage: GiurisprudenzaPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
    external_fetch: false,
    ai_generation: false,
    canonical_source: 'backend_storico',
  },
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
  sources: [],
  filters: {},
}

export const emptyGiurisprudenzaCreateDefaults: GiurisprudenzaCreateDefaults = {
  titolo: '',
  source_system: 'manuale_interno',
  giurisdizione: '',
  ufficio: '',
  organo_giudicante: '',
  grado: '',
  sezione: '',
  numero_provvedimento: '',
  data_decisione: '',
  data_deposito: '',
  tipo_provvedimento: '',
  area: '',
  branca: '',
  sottobranca: '',
  microtema: '',
  rito: '',
  materia: '',
  norme_citate: '',
  parole_chiave: '',
  massima: '',
  principio_diritto: '',
  abstract: '',
  esito: '',
  orientamento: '',
  rilevanza_pratica: '',
  uso_nel_software: '',
  ecli: '',
  url_origine: '',
  url_pagina_ufficiale: '',
  url_pdf_ufficiale: '',
  text_original: '',
  note_redazionali: '',
}

export const emptyGiurisprudenzaCreatePage: GiurisprudenzaCreatePageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
    external_fetch: false,
    ai_generation: false,
    canonical_source: 'backend_storico',
  },
  defaults: emptyGiurisprudenzaCreateDefaults,
  options: {},
  sources: [],
  actions: [],
  forms: [],
  warnings: [],
}

export const emptyGiurisprudenzaCreateResponse: GiurisprudenzaCreateResponse = {
  ok: false,
  message: 'Salvataggio non riuscito. Riprova tra qualche istante.',
  errors: {},
  warnings: [],
  record: null,
  redirectHref: '',
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function integer(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.trunc(value)
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number.parseInt(value, 10)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function tone(value: unknown): LegalTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as LegalTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  if (href.startsWith('/') && href !== '#') return href
  if (href.startsWith('https://') || href.startsWith('http://')) return href
  return fallback
}

function normaliseMetric(input: unknown): LegalMetric {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSectionItem(input: unknown): LegalSectionItem {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: display(item.label) || 'Voce',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): LegalSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'informazioni',
    items: list(item.items).map(normaliseSectionItem),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(input: unknown): LegalAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: safeHref(item.href, '/giurisprudenza'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): LegalWarning {
  const item = asRecord(input)
  return {
    code: display(item.code) || 'warning',
    message: display(item.message) || 'Avviso disponibile.',
  }
}

function normalisePracticeLink(input: unknown): PracticeLink {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'collegamento',
    label: display(item.label) || 'Fascicolo collegato',
    href: safeHref(item.href),
  }
}

function normaliseSource(input: unknown): GiurisprudenzaSource {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'fonte',
    label: display(item.label) || 'Fonte',
    kind: display(item.kind),
    coverage: display(item.coverage),
    accessMode: display(item.accessMode),
    sourceHref: safeHref(item.sourceHref),
    legacyHref: safeHref(item.legacyHref),
    lastRunAt: display(item.lastRunAt),
    stateLabel: display(item.stateLabel),
    stateTone: tone(item.stateTone),
    resolutionNote: display(item.resolutionNote),
    count: integer(item.count),
    evidenceType: display(item.evidenceType) || 'fonte',
  }
}

function normaliseRecord(input: unknown): GiurisprudenzaRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'provvedimento',
    title: display(item.title) || 'Provvedimento',
    subtitle: display(item.subtitle),
    sourceId: text(item.sourceId),
    sourceLabel: display(item.sourceLabel) || 'Fonte',
    sourceKind: display(item.sourceKind),
    authority: display(item.authority),
    office: display(item.office),
    date: display(item.date),
    area: display(item.area),
    branch: display(item.branch),
    subbranch: display(item.subbranch),
    grade: display(item.grade),
    jurisdiction: display(item.jurisdiction),
    caseNumber: display(item.caseNumber),
    ecli: display(item.ecli),
    orientation: display(item.orientation),
    orientationKind: display(item.orientationKind),
    verificationLabel: display(item.verificationLabel),
    verificationTone: tone(item.verificationTone),
    citationLabel: display(item.citationLabel),
    tags: list(item.tags).map((tag) => display(tag)).filter(Boolean),
    legacyHref: safeHref(item.legacyHref, '/giurisprudenza'),
    practiceLinks: list(item.practiceLinks).map(normalisePracticeLink).filter((link) => link.href || link.label),
    evidenceType: display(item.evidenceType) || 'informazione',
    sourceHref: safeHref(item.sourceHref),
    summary: display(item.summary),
    principle: display(item.principle),
    abstract: display(item.abstract),
    practicalUse: display(item.practicalUse),
    reliabilityNote: display(item.reliabilityNote),
    officialSource: item.officialSource === true,
    fullTextAvailable: item.fullTextAvailable === true,
  }
}

function normaliseContracts(input: unknown, writes = 'none'): LegalUiContract {
  const contracts = asRecord(input)
  return {
    mock_fallback: contracts.mock_fallback === true,
    writes: text(contracts.writes) || writes,
    route_owner: text(contracts.route_owner) || 'react_shell',
    external_fetch: contracts.external_fetch === true,
    ai_generation: contracts.ai_generation === true,
    canonical_source: text(contracts.canonical_source) || 'backend_storico',
    legacy_contract: text(contracts.legacy_contract),
  }
}

function normalisePage(input: unknown): GiurisprudenzaPageData {
  const page = asRecord(input)
  const filtersPayload = asRecord(page.filters)
  const filters: Record<string, string> = {}
  for (const [key, value] of Object.entries(filtersPayload)) {
    const cleaned = text(value)
    if (cleaned) filters[key] = cleaned
  }
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContracts(page.contracts),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
    sources: list(page.sources).map(normaliseSource).filter((source) => source.id),
    filters,
  }
}

function normaliseCreateOption(input: unknown): GiurisprudenzaCreateOption {
  const item = asRecord(input)
  return {
    value: text(item.value) || text(item.label),
    label: display(item.label) || display(item.value),
  }
}

function normaliseCreateDefaults(input: unknown): GiurisprudenzaCreateDefaults {
  const item = asRecord(input)
  return {
    titolo: display(item.titolo),
    source_system: text(item.source_system) || 'manuale_interno',
    giurisdizione: display(item.giurisdizione),
    ufficio: display(item.ufficio),
    organo_giudicante: display(item.organo_giudicante),
    grado: display(item.grado),
    sezione: display(item.sezione),
    numero_provvedimento: display(item.numero_provvedimento),
    data_decisione: display(item.data_decisione),
    data_deposito: display(item.data_deposito),
    tipo_provvedimento: display(item.tipo_provvedimento),
    area: display(item.area),
    branca: display(item.branca),
    sottobranca: display(item.sottobranca),
    microtema: display(item.microtema),
    rito: display(item.rito),
    materia: display(item.materia),
    norme_citate: display(item.norme_citate),
    parole_chiave: display(item.parole_chiave),
    massima: display(item.massima),
    principio_diritto: display(item.principio_diritto),
    abstract: display(item.abstract),
    esito: display(item.esito),
    orientamento: display(item.orientamento),
    rilevanza_pratica: display(item.rilevanza_pratica),
    uso_nel_software: display(item.uso_nel_software),
    ecli: display(item.ecli),
    url_origine: safeHref(item.url_origine),
    url_pagina_ufficiale: safeHref(item.url_pagina_ufficiale),
    url_pdf_ufficiale: safeHref(item.url_pdf_ufficiale),
    text_original: display(item.text_original),
    note_redazionali: display(item.note_redazionali),
  }
}

function normaliseOptions(input: unknown): Record<string, GiurisprudenzaCreateOption[]> {
  const options = asRecord(input)
  return Object.fromEntries(
    Object.entries(options).map(([key, value]) => [
      key,
      list(value)
        .map(normaliseCreateOption)
        .filter((option) => option.value && option.label),
    ]),
  )
}

function normaliseCreatePage(input: unknown): GiurisprudenzaCreatePageData {
  const page = asRecord(input)
  const forms = list(page.forms).map((form) => {
    const item = asRecord(form)
    return {
      id: text(item.id) || 'giurisprudenza_nuova',
      method: text(item.method) || 'POST',
      endpoint: safeHref(item.endpoint, '/api/v1/ui/giurisprudenza/nuova'),
    }
  })
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: normaliseContracts(page.contracts, 'json_api'),
    defaults: normaliseCreateDefaults(page.defaults),
    options: normaliseOptions(page.options),
    sources: list(page.sources).map(normaliseSource).filter((source) => source.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms,
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseCreateResponse(input: unknown): GiurisprudenzaCreateResponse {
  const payload = asRecord(input)
  const errorsPayload = asRecord(payload.errors)
  const errors: Record<string, string> = {}
  for (const [key, value] of Object.entries(errorsPayload)) {
    const cleaned = display(value)
    if (cleaned) errors[key] = cleaned
  }
  return {
    ok: payload.ok === true,
    message: display(payload.message) || (payload.ok === true ? 'Scheda salvata.' : emptyGiurisprudenzaCreateResponse.message),
    errors,
    warnings: list(payload.warnings).map(normaliseWarning),
    record: payload.record ? normaliseRecord(payload.record) : null,
    redirectHref: safeHref(payload.redirectHref, ''),
    status: typeof payload.status === 'number' ? payload.status : undefined,
  }
}

export async function getGiurisprudenzaPage(): Promise<GiurisprudenzaPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/giurisprudenza', emptyGiurisprudenzaPage)
  return normalisePage(payload)
}

export async function getGiurisprudenzaCreatePage(): Promise<GiurisprudenzaCreatePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/giurisprudenza/nuova', emptyGiurisprudenzaCreatePage)
  return normaliseCreatePage(payload)
}

export async function createGiurisprudenzaRecord(
  form: GiurisprudenzaCreateDefaults,
): Promise<GiurisprudenzaCreateResponse> {
  const payload = await apiPostJson<unknown>(
    '/api/v1/ui/giurisprudenza/nuova',
    form,
    emptyGiurisprudenzaCreateResponse,
  )
  return normaliseCreateResponse(payload)
}
