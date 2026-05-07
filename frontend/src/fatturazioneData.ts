import { apiJson, apiPostJson } from './lib/apiClient'
import type { AdminAction, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

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

export type FatturazioneFormDefaults = {
  id_cliente: string
  id_fascicolo: string
  data_emissione: string
  data_scadenza: string
  note: string
  voci: FatturazioneVoiceDefault[]
  opzioni_fiscali: FatturazioneFiscalDefaults
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
  defaults: FatturazioneFormDefaults
  fiscal_options: FatturazioneFiscalOption[]
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: FatturazioneRecord[]
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

const emptyDefaults: FatturazioneFormDefaults = {
  id_cliente: '',
  id_fascicolo: '',
  data_emissione: '',
  data_scadenza: '',
  note: '',
  voci: [emptyVoice],
  opzioni_fiscali: emptyFiscalDefaults,
  hidden: {},
}

const emptyForm: FatturazioneFormDefinition = {
  id: 'nuova_parcella',
  title: 'Nuova parcella',
  description: '',
  readHref: '/api/v1/ui/fatturazione/nuova',
  saveHref: '/api/v1/ui/fatturazione/nuova',
  submitLabel: 'Crea parcella',
  enabled: false,
  defaults: emptyDefaults,
  hidden: {},
}

const archiveWritesContract = 'legacy_' + 'routes'

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
  defaults: emptyDefaults,
  fiscal_options: [],
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
}

const createFallback: CreateFatturaResult = {
  ok: false,
  message: 'Salvataggio non completato.',
  errors: { server: 'Il backend non ha restituito una risposta valida.' },
  item: null,
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

function value(value: unknown): string | number {
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
    value: value(item.value),
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
        value: value(entry.value),
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
    href: safeHref(item.href, '/fatturazione'),
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

function normaliseRecord(raw: unknown): FatturazioneRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    number: text(item.number),
    customerName: text(item.customerName) || 'Cliente non indicato',
    caseTitle: text(item.caseTitle),
    amountDisplay: text(item.amountDisplay),
    issuedAt: text(item.issuedAt),
    dueAt: text(item.dueAt),
    paidAt: text(item.paidAt),
    state: text(item.state),
    stateLabel: text(item.stateLabel) || text(item.state) || 'Stato non indicato',
    stateTone: tone(item.stateTone),
    paymentMethod: text(item.paymentMethod),
    detailHref: safeHref(item.detailHref),
    pdfHref: safeHref(item.pdfHref),
    xmlHref: safeHref(item.xmlHref),
  }
}

function normaliseOption(raw: unknown): FatturazioneOption {
  const item = asRecord(raw)
  const id = text(item.id) || text(item.value)
  return {
    id,
    value: text(item.value) || id,
    label: text(item.label) || 'Voce non indicata',
    description: text(item.description),
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
    descrizione: text(item.descrizione),
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
    hidden: normaliseHidden(item.hidden),
  }
}

function normaliseForm(raw: unknown): FatturazioneFormDefinition {
  const item = asRecord(raw)
  const defaults = normaliseDefaults(item.defaults)
  return {
    id: text(item.id) || 'nuova_parcella',
    title: text(item.title) || 'Nuova parcella',
    description: text(item.description),
    readHref: safeHref(item.readHref, '/api/v1/ui/fatturazione/nuova'),
    saveHref: safeHref(item.saveHref, '/api/v1/ui/fatturazione/nuova'),
    submitLabel: text(item.submitLabel) || 'Crea parcella',
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
    label: text(item.label) || name,
    default: bool(item.default),
    description: text(item.description),
  }
}

function normalisePage(raw: unknown): FatturazionePageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const form = normaliseForm(page.form || list(page.forms)[0])
  const defaults = normaliseDefaults(page.defaults || form.defaults)
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
    defaults,
    fiscal_options: list(page.fiscal_options)
      .map(normaliseFiscalOption)
      .filter((option): option is FatturazioneFiscalOption => Boolean(option)),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id || record.number),
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
    message: text(item.message) || (item.ok === true ? 'Parcella creata.' : 'Salvataggio non completato.'),
    errors: Object.fromEntries(
      Object.entries(asRecord(item.errors)).map(([key, rawValue]) => [key, text(rawValue)]),
    ),
    item: item.item && typeof item.item === 'object' ? {
      id: text(created.id),
      number: text(created.number),
      amountDisplay: text(created.amountDisplay),
      issuedAt: text(created.issuedAt),
      dueAt: text(created.dueAt),
      state: text(created.state),
      stateLabel: text(created.stateLabel),
      stateTone: tone(created.stateTone),
    } : null,
    redirect_href: safeHref(item.redirect_href),
    status: typeof item.status === 'number' ? item.status : undefined,
  }
}

export async function getFatturazionePage(): Promise<FatturazionePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/fatturazione', emptyFatturazionePage)
  return normalisePage(payload)
}

export async function getNuovaFatturaPage(): Promise<FatturazionePageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/fatturazione/nuova', emptyFatturazionePage)
  return normalisePage(payload)
}

export async function createFattura(payload: CreateFatturaPayload): Promise<CreateFatturaResult> {
  const result = await apiPostJson<CreateFatturaResult>('/api/v1/ui/fatturazione/nuova', payload, createFallback)
  return normaliseCreateResult(result)
}

export async function createParcella(payload: CreateFatturaPayload): Promise<CreateFatturaResult> {
  return createFattura(payload)
}
