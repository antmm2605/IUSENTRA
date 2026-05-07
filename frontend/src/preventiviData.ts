import { apiJson, apiPostJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type PreventivoClientOption = {
  id: string
  value: string
  label: string
  description: string
}

export type PreventivoMatterOption = PreventivoClientOption & {
  idCliente: string
}

export type PreventivoMatterOptionAlias = PreventivoMatterOption

export type PreventivoVoiceInput = {
  descrizione: string
  tipo: string
  importo: number
}

export type PreventivoFiscalOptions = {
  applica_iva: boolean
  applica_cassa: boolean
  applica_ritenuta: boolean
}

export type CreatePreventivoPayload = {
  id_cliente: string
  id_fascicolo: string
  oggetto: string
  data_emissione: string
  data_scadenza: string
  tipo_compenso: string
  tipo_procedimento: string
  valore_controversia: number
  complessita: string
  voci: PreventivoVoiceInput[]
  opzioni_fiscali: PreventivoFiscalOptions
  note: string
  from_cliente?: string
  id_pratica?: string
  area_pratica?: string
  procedura_operativa_codice?: string
}

export type CreatePreventivoResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: PreventivoMutationItem | null
  redirect_href?: string
  status?: number
}

export type ConferimentoClientOption = PreventivoClientOption
export type ConferimentoMatterOption = PreventivoMatterOption

export type ConferimentoEstimateOption = PreventivoClientOption & {
  idCliente: string
  amountDisplay: string
  state: string
}

export type ConferimentoStudioDefaults = {
  avvocato_referente: string
  numero_iscrizione_albo: string
  ordine_avvocati: string
}

export type ConferimentoClauses = {
  informativa_art13_resa: boolean
  clausola_adr_resa: boolean
}

export type CreateConferimentoPayload = {
  id_cliente: string
  id_fascicolo: string
  id_preventivo: string
  oggetto: string
  avvocato_referente: string
  numero_iscrizione_albo: string
  ordine_avvocati: string
  data_incarico: string
  tipo_compenso: string
  tipo_procedimento: string
  compenso_pattuito: number
  informativa_art13_resa: boolean
  clausola_adr_resa: boolean
  apri_fascicolo_guidato: boolean
  note: string
  from_cliente?: string
  id_pratica?: string
  area_pratica?: string
  procedura_operativa_codice?: string
}

export type CreateConferimentoResult = CreatePreventivoResult

export type PreventiviRecordKind = 'preventivo' | 'conferimento'

export type PreventivoRow = {
  id: string
  kind: PreventiviRecordKind
  number: string
  subject: string
  customerName: string
  caseTitle: string
  amountDisplay: string
  issuedAt: string
  dueAt: string
  engagementAt: string
  state: string
  stateLabel: string
  stateTone: AdminTone
  detailHref: string
  wizardHref: string
  legacyHref: string
}

export type ConferimentoRow = PreventivoRow
export type PreventiviRecord = PreventivoRow

export type PreventivoStatus = {
  value: string
  label: string
  tone: AdminTone
}

export type PreventiviPermissions = {
  canCreate: boolean
  canUpdateStatus: boolean
  canArchive: boolean
  canCancel: boolean
  canDuplicate: boolean
  canCreateConferimento: boolean
  canOpenWizard: boolean
  canUseFiscalOptions: boolean
  canLinkMatter: boolean
  canLinkPreventivo: boolean
  canOpenMatterAfterSave: boolean
}

export type PreventivoDetail = PreventivoRow & {
  voci: Array<{
    descrizione: string
    tipo: string
    importoDisplay: string
  }>
}

export type UpdatePreventivoStatusPayload = {
  stato: string
  note?: string
}

export type PreventivoMutationItem = {
  id: string
  kind: string
  number: string
  subject: string
  amountDisplay: string
  state: string
  stateLabel: string
  stateTone: AdminTone
}

export type PreventivoMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  item: PreventivoMutationItem | null
  status?: number
}

export type PreventiviFormDefaults = {
  id_cliente: string
  id_fascicolo: string
  id_preventivo: string
  oggetto: string
  data_emissione: string
  data_scadenza: string
  data_incarico: string
  tipo_compenso: string
  tipo_procedimento: string
  valore_controversia: string
  complessita: string
  compenso_pattuito: string
  avvocato_referente: string
  numero_iscrizione_albo: string
  ordine_avvocati: string
  note: string
  voci: Array<{ descrizione: string; tipo: string; importo: string }>
  opzioni_fiscali: PreventivoFiscalOptions
  hidden: Record<string, string>
}

export type PreventiviFormDefinition = {
  id: string
  readHref: string
  saveHref: string
  enabled: boolean
  defaults: PreventiviFormDefaults
}

export type PreventiviPageData = {
  ok: boolean
  source: string
  generated_at: string
  contracts: AdminContract & {
    operational?: boolean
    canonical_calculation?: string
    dm55_calculation?: string
    document_generation?: string
    canonical_persistence?: string
  }
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: PreventivoRow[]
  estimates: ConferimentoEstimateOption[]
  assignments: ConferimentoRow[]
  statuses: PreventivoStatus[]
  clients: PreventivoClientOption[]
  matters: PreventivoMatterOption[]
  defaults: PreventiviFormDefaults
  form: PreventiviFormDefinition
  forms: PreventiviFormDefinition[]
  fiscal_options: Array<{ name: keyof PreventivoFiscalOptions; label: string; default: boolean; description: string }>
  compensation_options: Array<{ value: string; label: string; description: string }>
  studio: ConferimentoStudioDefaults
  clauses: ConferimentoClauses
  permissions: PreventiviPermissions
  actions: AdminAction[]
  warnings: AdminWarning[]
}

export type NuovoPreventivoPageData = PreventiviPageData
export type NuovoConferimentoPageData = PreventiviPageData

const emptyPermissions: PreventiviPermissions = {
  canCreate: false,
  canUpdateStatus: false,
  canArchive: false,
  canCancel: false,
  canDuplicate: false,
  canCreateConferimento: false,
  canOpenWizard: false,
  canUseFiscalOptions: false,
  canLinkMatter: false,
  canLinkPreventivo: false,
  canOpenMatterAfterSave: false,
}

const emptyDefaults: PreventiviFormDefaults = {
  id_cliente: '',
  id_fascicolo: '',
  id_preventivo: '',
  oggetto: '',
  data_emissione: '',
  data_scadenza: '',
  data_incarico: '',
  tipo_compenso: '',
  tipo_procedimento: '',
  valore_controversia: '',
  complessita: '',
  compenso_pattuito: '',
  avvocato_referente: '',
  numero_iscrizione_albo: '',
  ordine_avvocati: '',
  note: '',
  voci: [{ descrizione: '', tipo: 'ONORARIO', importo: '' }],
  opzioni_fiscali: { applica_iva: true, applica_cassa: true, applica_ritenuta: false },
  hidden: {},
}

const emptyForm: PreventiviFormDefinition = {
  id: 'nuovo_preventivo',
  readHref: '/api/v1/ui/preventivi/nuovo',
  saveHref: '/api/v1/ui/preventivi/nuovo',
  enabled: false,
  defaults: emptyDefaults,
}

export const emptyPreventiviPage: PreventiviPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: [],
  estimates: [],
  assignments: [],
  statuses: [],
  clients: [],
  matters: [],
  defaults: emptyDefaults,
  form: emptyForm,
  forms: [],
  fiscal_options: [],
  compensation_options: [],
  studio: { avvocato_referente: '', numero_iscrizione_albo: '', ordine_avvocati: '' },
  clauses: { informativa_art13_resa: true, clausola_adr_resa: true },
  permissions: emptyPermissions,
  actions: [],
  warnings: [],
}

const mutationFallback: PreventivoMutationResult = {
  ok: false,
  message: 'Operazione non completata.',
  errors: { server: 'Il backend non ha restituito una risposta valida.' },
  item: null,
}

const createFallback: CreatePreventivoResult = {
  ...mutationFallback,
  message: 'Salvataggio non completato.',
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

function bool(value: unknown, fallback = false): boolean {
  if (typeof value === 'boolean') return value
  return fallback
}

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
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
    label: text(item.label) || 'Metrica',
    value: scalar(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AdminSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'distribution',
    items: list(item.items).map((rawItem) => {
      const entry = asRecord(rawItem)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: text(entry.label) || 'Voce',
        value: scalar(entry.value),
        note: text(entry.note),
        tone: tone(entry.tone),
      }
    }),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: safeHref(item.href, '/preventivi'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): AdminWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso tecnico disponibile.',
  }
}

function normaliseOption(raw: unknown): PreventivoClientOption {
  const item = asRecord(raw)
  const id = text(item.id) || text(item.value)
  return {
    id,
    value: text(item.value) || id,
    label: text(item.label) || 'Voce non indicata',
    description: text(item.description),
  }
}

function normaliseMatter(raw: unknown): PreventivoMatterOption {
  const option = normaliseOption(raw)
  const item = asRecord(raw)
  return {
    ...option,
    idCliente: text(item.idCliente) || text(item.id_cliente),
  }
}

function normaliseEstimate(raw: unknown): ConferimentoEstimateOption {
  const option = normaliseOption(raw)
  const item = asRecord(raw)
  return {
    ...option,
    idCliente: text(item.idCliente) || text(item.id_cliente),
    amountDisplay: text(item.amountDisplay),
    state: text(item.state),
  }
}

function normaliseKind(value: unknown): PreventiviRecordKind {
  return text(value) === 'conferimento' ? 'conferimento' : 'preventivo'
}

function normaliseRecord(raw: unknown): PreventivoRow {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    kind: normaliseKind(item.kind),
    number: text(item.number),
    subject: text(item.subject) || 'Oggetto non indicato',
    customerName: text(item.customerName) || 'Cliente non indicato',
    caseTitle: text(item.caseTitle),
    amountDisplay: text(item.amountDisplay),
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    engagementAt: text(item.engagementAt),
    state: text(item.state),
    stateLabel: text(item.stateLabel) || text(item.state) || 'Stato non indicato',
    stateTone: tone(item.stateTone),
    detailHref: safeHref(item.detailHref),
    wizardHref: safeHref(item.wizardHref),
    legacyHref: safeHref(item.legacyHref),
  }
}

function normaliseStatus(raw: unknown): PreventivoStatus {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: text(item.label) || text(item.value),
    tone: tone(item.tone),
  }
}

function normaliseHidden(raw: unknown): Record<string, string> {
  return Object.fromEntries(
    Object.entries(asRecord(raw))
      .map(([key, rawValue]) => [key, text(rawValue)] as const)
      .filter(([, rawValue]) => rawValue),
  )
}

function normaliseFiscalOptions(raw: unknown): PreventivoFiscalOptions {
  const item = asRecord(raw)
  return {
    applica_iva: bool(item.applica_iva, true),
    applica_cassa: bool(item.applica_cassa, true),
    applica_ritenuta: bool(item.applica_ritenuta, false),
  }
}

function normaliseDefaults(raw: unknown): PreventiviFormDefaults {
  const item = asRecord(raw)
  const voices = list(item.voci).map((voice) => {
    const row = asRecord(voice)
    return {
      descrizione: text(row.descrizione),
      tipo: text(row.tipo) || 'ONORARIO',
      importo: text(row.importo),
    }
  })
  return {
    id_cliente: text(item.id_cliente),
    id_fascicolo: text(item.id_fascicolo),
    id_preventivo: text(item.id_preventivo),
    oggetto: text(item.oggetto),
    data_emissione: text(item.data_emissione),
    data_scadenza: text(item.data_scadenza),
    data_incarico: text(item.data_incarico),
    tipo_compenso: text(item.tipo_compenso),
    tipo_procedimento: text(item.tipo_procedimento),
    valore_controversia: text(item.valore_controversia),
    complessita: text(item.complessita),
    compenso_pattuito: text(item.compenso_pattuito),
    avvocato_referente: text(item.avvocato_referente),
    numero_iscrizione_albo: text(item.numero_iscrizione_albo),
    ordine_avvocati: text(item.ordine_avvocati),
    note: text(item.note),
    voci: voices.length ? voices : emptyDefaults.voci,
    opzioni_fiscali: normaliseFiscalOptions(item.opzioni_fiscali),
    hidden: normaliseHidden(item.hidden),
  }
}

function normaliseForm(raw: unknown, defaults: PreventiviFormDefaults): PreventiviFormDefinition {
  const item = asRecord(raw)
  return {
    id: text(item.id) || 'nuovo_preventivo',
    readHref: safeHref(item.readHref, '/api/v1/ui/preventivi/nuovo'),
    saveHref: safeHref(item.saveHref, '/api/v1/ui/preventivi/nuovo'),
    enabled: bool(item.enabled, false),
    defaults: normaliseDefaults(item.defaults || defaults),
  }
}

function normalisePermissions(rawActions: unknown): PreventiviPermissions {
  const item = asRecord(rawActions)
  return {
    canCreate: bool(item.canCreate),
    canUpdateStatus: bool(item.canUpdateStatus),
    canArchive: bool(item.canArchive),
    canCancel: bool(item.canCancel),
    canDuplicate: bool(item.canDuplicate),
    canCreateConferimento: bool(item.canCreateConferimento),
    canOpenWizard: bool(item.canOpenWizard),
    canUseFiscalOptions: bool(item.canUseFiscalOptions),
    canLinkMatter: bool(item.canLinkMatter),
    canLinkPreventivo: bool(item.canLinkPreventivo),
    canOpenMatterAfterSave: bool(item.canOpenMatterAfterSave),
  }
}

function normaliseMutationItem(raw: unknown): PreventivoMutationItem | null {
  if (!raw || typeof raw !== 'object') return null
  const item = asRecord(raw)
  return {
    id: text(item.id),
    kind: text(item.kind),
    number: text(item.number),
    subject: text(item.subject),
    amountDisplay: text(item.amountDisplay),
    state: text(item.state),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
  }
}

function normaliseMutationResult(raw: unknown): PreventivoMutationResult {
  const item = asRecord(raw)
  return {
    ok: item.ok === true,
    message: text(item.message) || (item.ok === true ? 'Operazione completata.' : 'Operazione non completata.'),
    errors: Object.fromEntries(Object.entries(asRecord(item.errors)).map(([key, rawValue]) => [key, text(rawValue)])),
    item: normaliseMutationItem(item.item),
    status: typeof item.status === 'number' ? item.status : undefined,
  }
}

function normaliseCreateResult(raw: unknown): CreatePreventivoResult {
  const result = normaliseMutationResult(raw)
  const item = asRecord(raw)
  return {
    ...result,
    redirect_href: safeHref(item.redirect_href),
  }
}

function normalisePage(raw: unknown): PreventiviPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const rawActions = page.actions
  const actionsRecord = asRecord(rawActions)
  const defaults = normaliseDefaults(page.defaults)
  const form = normaliseForm(page.form || list(page.forms)[0], defaults)
  const links = Array.isArray(rawActions) ? rawActions : list(actionsRecord.links)
  return {
    ok: page.ok === true,
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'json_api',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
      operational: bool(contracts.operational),
      canonical_calculation: text(contracts.canonical_calculation),
      dm55_calculation: text(contracts.dm55_calculation),
      document_generation: text(contracts.document_generation),
      canonical_persistence: text(contracts.canonical_persistence),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id || record.number),
    estimates: list(page.estimates).map(normaliseEstimate).filter((option) => option.value),
    assignments: list(page.assignments).map(normaliseRecord).filter((record) => record.id || record.number),
    statuses: list(page.statuses).map(normaliseStatus).filter((status) => status.value),
    clients: list(page.clients).map(normaliseOption).filter((option) => option.value),
    matters: list(page.matters).map(normaliseMatter).filter((option) => option.value),
    defaults,
    form,
    forms: list(page.forms).map((item) => normaliseForm(item, defaults)),
    fiscal_options: list(page.fiscal_options).map((rawOption) => {
      const option = asRecord(rawOption)
      return {
        name: text(option.name) as keyof PreventivoFiscalOptions,
        label: text(option.label) || text(option.name),
        default: bool(option.default),
        description: text(option.description),
      }
    }).filter((option) => ['applica_iva', 'applica_cassa', 'applica_ritenuta'].includes(option.name)),
    compensation_options: list(page.compensation_options).map((rawOption) => {
      const option = asRecord(rawOption)
      return {
        value: text(option.value),
        label: text(option.label) || text(option.value),
        description: text(option.description),
      }
    }).filter((option) => option.value),
    studio: {
      avvocato_referente: text(asRecord(page.studio).avvocato_referente),
      numero_iscrizione_albo: text(asRecord(page.studio).numero_iscrizione_albo),
      ordine_avvocati: text(asRecord(page.studio).ordine_avvocati),
    },
    clauses: {
      informativa_art13_resa: bool(asRecord(page.clauses).informativa_art13_resa, true),
      clausola_adr_resa: bool(asRecord(page.clauses).clausola_adr_resa, true),
    },
    permissions: normalisePermissions(rawActions),
    actions: links.map(normaliseAction).filter((action) => action.href),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getPreventiviPage(): Promise<PreventiviPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi', emptyPreventiviPage)
  return normalisePage(payload)
}

export async function getNuovoPreventivoPage(): Promise<NuovoPreventivoPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi/nuovo', emptyPreventiviPage)
  return normalisePage(payload)
}

export async function getNuovoConferimentoPage(): Promise<NuovoConferimentoPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi/conferimento/nuovo', emptyPreventiviPage)
  return normalisePage(payload)
}

export async function getPreventivoDetail(idPreventivo: string): Promise<{ ok: boolean; item: PreventivoDetail | null; message: string; errors: Record<string, string> }> {
  const payload = await apiJson<unknown>(`/api/v1/ui/preventivi/${encodeURIComponent(idPreventivo)}`, { ok: false, item: null })
  const page = asRecord(payload)
  const item = page.item ? {
    ...normaliseRecord(page.item),
    voci: list(asRecord(page.item).voci).map((voice) => {
      const row = asRecord(voice)
      return {
        descrizione: text(row.descrizione),
        tipo: text(row.tipo),
        importoDisplay: text(row.importoDisplay),
      }
    }),
  } : null
  return {
    ok: page.ok === true,
    item,
    message: text(page.message),
    errors: Object.fromEntries(Object.entries(asRecord(page.errors)).map(([key, rawValue]) => [key, text(rawValue)])),
  }
}

export async function createPreventivo(payload: CreatePreventivoPayload): Promise<CreatePreventivoResult> {
  const result = await apiPostJson<CreatePreventivoResult>('/api/v1/ui/preventivi/nuovo', payload, createFallback)
  return normaliseCreateResult(result)
}

export async function createConferimento(payload: CreateConferimentoPayload): Promise<CreateConferimentoResult> {
  const result = await apiPostJson<CreateConferimentoResult>('/api/v1/ui/preventivi/conferimento/nuovo', payload, createFallback)
  return normaliseCreateResult(result)
}

export async function updatePreventivoStatus(idPreventivo: string, payload: UpdatePreventivoStatusPayload): Promise<PreventivoMutationResult> {
  const result = await apiPostJson<PreventivoMutationResult>(`/api/v1/ui/preventivi/${encodeURIComponent(idPreventivo)}/stato`, payload, mutationFallback)
  return normaliseMutationResult(result)
}

export async function archivePreventivo(): Promise<PreventivoMutationResult> {
  return { ...mutationFallback, message: 'Archiviazione non supportata dal backend legacy.' }
}

export async function cancelPreventivo(): Promise<PreventivoMutationResult> {
  return { ...mutationFallback, message: 'Annullamento non supportato dal backend legacy.' }
}

export async function duplicatePreventivo(): Promise<PreventivoMutationResult> {
  return { ...mutationFallback, message: 'Duplicazione non supportata dal backend legacy.' }
}
