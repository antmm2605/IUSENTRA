import { apiJson, apiPostJson } from './lib/apiClient'

export type WizardMode = 'guidato' | 'avanzato'

export type WizardOption = {
  value: string
  label: string
  description: string
  enabled: boolean
}

export type WizardClient = {
  id: string
  label: string
  type: string
  state: string
  email: string
  phone: string
  fiscalId: string
  minimumProfile: boolean
  engagementReady: boolean
  missingEngagementFields: string[]
}

export type WizardCase = {
  id: string
  label: string
  customerId: string
  area: string
  court: string
}

export type WizardPractice = {
  id: string
  label: string
  area: string
  materia: string
  grado_default: string
  fasi_default: string[]
  fasi_default_keys: string[]
  base_normativa: string
  tipo_compenso_default: string
  valore_suggerito: number
  esborsi_tipici: WizardExpense[]
  motore_label: string
  redattore_label: string
  summary: string
  when_to_use: string
  oggetto_template: string
  note_template: string
  checklist_iniziale: string[]
  normative_references: WizardReference[]
  accessori_calcolo: WizardAccessory[]
  variation_policy: Record<string, unknown>
  area_tassonomica: string
  area_tassonomica_code: string
  macro_area_tassonomica: string
  macro_area_tassonomica_code: string
  sottobranca_tassonomica: string
  sottobranca_tassonomica_code: string
  tassonomia_codice: string
  tassonomia_descrizione: string
  tassonomia_sources: Array<Record<string, string>>
  procedura_operativa_codice: string
  procedura_operativa_nome: string
  subbranch_operativa_codice: string
  workflow_operativo_codice: string
  copertura_operativa: string
  canale_operativo: string
  registro_operativo: string
  regola_tariffaria_default: string
  regole_tariffarie: Array<Record<string, unknown>>
}

export type WizardExpense = {
  key: string
  descrizione: string
  importo: number
  source?: string
}

export type WizardAccessory = {
  id: string
  label: string
  description: string
  tipo_pratica_id: string
  default_checked?: boolean
  row_label?: string
}

export type WizardReference = {
  title: string
  article: string
  description: string
  url: string
}

export type WizardTaxonomyRow = Record<string, string | number | boolean | null>

export type WizardClauseModel = {
  id: string
  label: string
  source: string
  default_text: string
}

export type WizardDraftRow = {
  id: string
  descrizione: string
  tipo: string
  importo: number
  importo_label: string
  fiscale: string
  source: string
  locked?: boolean
}

export type WizardEconomicSummary = {
  imponibile_voci: number
  cpa: number
  base_iva: number
  iva: number
  anticipazioni_art15: number
  totale: number
  imponibile_label: string
  cpa_label: string
  iva_label: string
  anticipazioni_label: string
  totale_label: string
}

export type WizardWarning = {
  code: string
  message: string
}

export type PreventivoWizardPageData = {
  source: string
  generated_at: string
  contracts: {
    mock_fallback: boolean
    writes: string
    route_owner: string
    legacy_contract?: string
  }
  defaults: {
    issuedAt: string
    issuedAtLabel: string
    dueAt: string
    dueAtLabel: string
    mode: WizardMode
    applicaCpa: boolean
    applicaIva: boolean
    speseGenerali: boolean
    percSpeseGenerali: string
    informativaArt13: boolean
  }
  prefill: Record<string, unknown>
  clients: WizardClient[]
  cases: WizardCase[]
  catalog: {
    areas: Array<{ id: string; label: string; value: string; count: number }>
    grouped: Record<string, WizardPractice[]>
    practices: Record<string, WizardPractice>
    procedures: WizardOption[]
    workflows: WizardOption[]
    channels: WizardOption[]
    taxonomyRows: WizardTaxonomyRow[]
    taxonomySummary: {
      areas: string[]
      macroAreas: string[]
      subBranches: string[]
      missing: string[]
    }
    taxonomySources: Array<Record<string, string>>
  }
  options: {
    complexity: WizardOption[]
    voiceTypes: WizardOption[]
    manualFiscalTypes: WizardOption[]
    quickClientTypes: WizardOption[]
    clauseModels: WizardClauseModel[]
    defaultClause: {
      id: string
      label: string
      source: string
      defaultText: string
    }
  }
  support: {
    references: Array<Record<string, string | number | boolean | null>>
    audit: {
      aligned: number
      total: number
      open: number
    }
  }
  actions: {
    back: string
    legacy: string
    calculate: string
    create: string
  }
  warnings: WizardWarning[]
}

export type WizardCalculationResponse = {
  ok: boolean
  state: Record<string, unknown>
  profile: WizardPractice | null
  rows: WizardDraftRow[]
  economic: WizardEconomicSummary | null
  fasi: Record<string, { min: number; base: number; max: number }>
  scaglione: string
  livello_compenso: string
  compenso_base: number
  bonus_telematico: number
  spese_generali: number
  note: string
  mediazione_odm: Record<string, unknown> | null
  warnings: WizardWarning[]
  audit: Record<string, unknown>
  transfer: Record<string, unknown>
}

export type WizardCreateResponse = {
  ok: boolean
  id_preventivo: string
  id_conferimento: string
  id_fascicolo: string
  detail_url: string
  redirect_url: string
  messages: Array<{ tone: string; message: string }>
  warnings: WizardWarning[]
}

const emptyDefaults: PreventivoWizardPageData['defaults'] = {
  issuedAt: '',
  issuedAtLabel: '',
  dueAt: '',
  dueAtLabel: '',
  mode: 'guidato',
  applicaCpa: true,
  applicaIva: true,
  speseGenerali: true,
  percSpeseGenerali: '15',
  informativaArt13: true,
}

export const emptyPreventivoWizardPage: PreventivoWizardPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
  },
  defaults: emptyDefaults,
  prefill: {},
  clients: [],
  cases: [],
  catalog: {
    areas: [],
    grouped: {},
    practices: {},
    procedures: [],
    workflows: [],
    channels: [],
    taxonomyRows: [],
    taxonomySummary: { areas: [], macroAreas: [], subBranches: [], missing: [] },
    taxonomySources: [],
  },
  options: {
    complexity: [],
    voiceTypes: [],
    manualFiscalTypes: [],
    quickClientTypes: [],
    clauseModels: [],
    defaultClause: { id: '', label: '', source: '', defaultText: '' },
  },
  support: {
    references: [],
    audit: { aligned: 0, total: 0, open: 0 },
  },
  actions: {
    back: '/preventivi',
    legacy: '/preventivi/wizard?_legacy=1',
    calculate: '/api/v1/ui/preventivi/wizard/calculate',
    create: '/api/v1/ui/preventivi/wizard/create',
  },
  warnings: [],
}

const emptyCalculation: WizardCalculationResponse = {
  ok: false,
  state: {},
  profile: null,
  rows: [],
  economic: null,
  fasi: {},
  scaglione: '',
  livello_compenso: '',
  compenso_base: 0,
  bonus_telematico: 0,
  spese_generali: 0,
  note: '',
  mediazione_odm: null,
  warnings: [],
  audit: {},
  transfer: {},
}

const emptyCreate: WizardCreateResponse = {
  ok: false,
  id_preventivo: '',
  id_conferimento: '',
  id_fascicolo: '',
  detail_url: '',
  redirect_url: '',
  messages: [],
  warnings: [],
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

function numberValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function bool(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function stringList(value: unknown): string[] {
  return list(value).map((item) => text(item)).filter(Boolean)
}

function option(raw: unknown): WizardOption {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: text(item.label) || text(item.value),
    description: text(item.description),
    enabled: item.enabled !== false,
  }
}

function warning(raw: unknown): WizardWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso operativo disponibile.',
  }
}

function expense(raw: unknown): WizardExpense {
  const item = asRecord(raw)
  return {
    key: text(item.key),
    descrizione: text(item.descrizione),
    importo: numberValue(item.importo),
    source: text(item.source),
  }
}

function reference(raw: unknown): WizardReference {
  const item = asRecord(raw)
  return {
    title: text(item.title),
    article: text(item.article),
    description: text(item.description),
    url: text(item.url),
  }
}

function accessory(raw: unknown): WizardAccessory {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    label: text(item.label),
    description: text(item.description),
    tipo_pratica_id: text(item.tipo_pratica_id),
    default_checked: bool(item.default_checked),
    row_label: text(item.row_label),
  }
}

function practice(raw: unknown): WizardPractice {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    label: text(item.label),
    area: text(item.area),
    materia: text(item.materia),
    grado_default: text(item.grado_default),
    fasi_default: stringList(item.fasi_default),
    fasi_default_keys: stringList(item.fasi_default_keys),
    base_normativa: text(item.base_normativa),
    tipo_compenso_default: text(item.tipo_compenso_default),
    valore_suggerito: numberValue(item.valore_suggerito),
    esborsi_tipici: list(item.esborsi_tipici).map(expense),
    motore_label: text(item.motore_label),
    redattore_label: text(item.redattore_label),
    summary: text(item.summary),
    when_to_use: text(item.when_to_use),
    oggetto_template: text(item.oggetto_template),
    note_template: text(item.note_template),
    checklist_iniziale: stringList(item.checklist_iniziale),
    normative_references: list(item.normative_references).map(reference),
    accessori_calcolo: list(item.accessori_calcolo).map(accessory),
    variation_policy: asRecord(item.variation_policy),
    area_tassonomica: text(item.area_tassonomica),
    area_tassonomica_code: text(item.area_tassonomica_code),
    macro_area_tassonomica: text(item.macro_area_tassonomica),
    macro_area_tassonomica_code: text(item.macro_area_tassonomica_code),
    sottobranca_tassonomica: text(item.sottobranca_tassonomica),
    sottobranca_tassonomica_code: text(item.sottobranca_tassonomica_code),
    tassonomia_codice: text(item.tassonomia_codice),
    tassonomia_descrizione: text(item.tassonomia_descrizione),
    tassonomia_sources: list(item.tassonomia_sources).map((entry) => asRecord(entry) as Record<string, string>),
    procedura_operativa_codice: text(item.procedura_operativa_codice),
    procedura_operativa_nome: text(item.procedura_operativa_nome),
    subbranch_operativa_codice: text(item.subbranch_operativa_codice),
    workflow_operativo_codice: text(item.workflow_operativo_codice),
    copertura_operativa: text(item.copertura_operativa),
    canale_operativo: text(item.canale_operativo),
    registro_operativo: text(item.registro_operativo),
    regola_tariffaria_default: text(item.regola_tariffaria_default),
    regole_tariffarie: list(item.regole_tariffarie).map((entry) => asRecord(entry)),
  }
}

function client(raw: unknown): WizardClient {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    label: text(item.label),
    type: text(item.type),
    state: text(item.state),
    email: text(item.email),
    phone: text(item.phone),
    fiscalId: text(item.fiscalId),
    minimumProfile: bool(item.minimumProfile),
    engagementReady: bool(item.engagementReady),
    missingEngagementFields: stringList(item.missingEngagementFields),
  }
}

function matter(raw: unknown): WizardCase {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    label: text(item.label),
    customerId: text(item.customerId),
    area: text(item.area),
    court: text(item.court),
  }
}

function draftRow(raw: unknown): WizardDraftRow {
  const item = asRecord(raw)
  return {
    id: text(item.id) || `voce-${Date.now()}`,
    descrizione: text(item.descrizione),
    tipo: text(item.tipo) || 'Onorario',
    importo: numberValue(item.importo),
    importo_label: text(item.importo_label),
    fiscale: text(item.fiscale) || 'imponibile',
    source: text(item.source),
    locked: bool(item.locked),
  }
}

function economic(raw: unknown): WizardEconomicSummary | null {
  const item = asRecord(raw)
  if (!Object.keys(item).length) return null
  return {
    imponibile_voci: numberValue(item.imponibile_voci),
    cpa: numberValue(item.cpa),
    base_iva: numberValue(item.base_iva),
    iva: numberValue(item.iva),
    anticipazioni_art15: numberValue(item.anticipazioni_art15),
    totale: numberValue(item.totale),
    imponibile_label: text(item.imponibile_label),
    cpa_label: text(item.cpa_label),
    iva_label: text(item.iva_label),
    anticipazioni_label: text(item.anticipazioni_label),
    totale_label: text(item.totale_label),
  }
}

function normalisePage(raw: unknown): PreventivoWizardPageData {
  const page = asRecord(raw)
  const catalog = asRecord(page.catalog)
  const options = asRecord(page.options)
  const support = asRecord(page.support)
  const actions = asRecord(page.actions)
  const groupedRaw = asRecord(catalog.grouped)
  const practicesRaw = asRecord(catalog.practices)
  const defaults = asRecord(page.defaults)
  const defaultClause = asRecord(options.defaultClause)
  const contracts = asRecord(page.contracts)
  return {
    ...emptyPreventivoWizardPage,
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true,
      writes: text(contracts.writes) || 'operational_routes',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    defaults: {
      ...emptyDefaults,
      issuedAt: text(defaults.issuedAt),
      issuedAtLabel: text(defaults.issuedAtLabel),
      dueAt: text(defaults.dueAt),
      dueAtLabel: text(defaults.dueAtLabel),
      mode: text(defaults.mode) === 'avanzato' ? 'avanzato' : 'guidato',
      applicaCpa: defaults.applicaCpa === false ? false : true,
      applicaIva: defaults.applicaIva === false ? false : true,
      speseGenerali: defaults.speseGenerali === false ? false : true,
      percSpeseGenerali: text(defaults.percSpeseGenerali) || '15',
      informativaArt13: defaults.informativaArt13 === false ? false : true,
    },
    prefill: asRecord(page.prefill),
    clients: list(page.clients).map(client),
    cases: list(page.cases).map(matter),
    catalog: {
      areas: list(catalog.areas).map((rawArea) => {
        const area = asRecord(rawArea)
        return { id: text(area.id), label: text(area.label), value: text(area.value), count: numberValue(area.count) }
      }),
      grouped: Object.fromEntries(Object.entries(groupedRaw).map(([key, value]) => [key, list(value).map(practice)])),
      practices: Object.fromEntries(Object.entries(practicesRaw).map(([key, value]) => [key, practice(value)])),
      procedures: list(catalog.procedures).map(option),
      workflows: list(catalog.workflows).map(option),
      channels: list(catalog.channels).map(option),
      taxonomyRows: list(catalog.taxonomyRows).map((row) => asRecord(row) as WizardTaxonomyRow),
      taxonomySummary: {
        areas: stringList(asRecord(catalog.taxonomySummary).areas),
        macroAreas: stringList(asRecord(catalog.taxonomySummary).macroAreas),
        subBranches: stringList(asRecord(catalog.taxonomySummary).subBranches),
        missing: stringList(asRecord(catalog.taxonomySummary).missing),
      },
      taxonomySources: list(catalog.taxonomySources).map((row) => asRecord(row) as Record<string, string>),
    },
    options: {
      complexity: list(options.complexity).map(option),
      voiceTypes: list(options.voiceTypes).map(option),
      manualFiscalTypes: list(options.manualFiscalTypes).map(option),
      quickClientTypes: list(options.quickClientTypes).map(option),
      clauseModels: list(options.clauseModels).map((rawModel) => {
        const model = asRecord(rawModel)
        return {
          id: text(model.id),
          label: text(model.label),
          source: text(model.source),
          default_text: text(model.default_text),
        }
      }),
      defaultClause: {
        id: text(defaultClause.id),
        label: text(defaultClause.label),
        source: text(defaultClause.source),
        defaultText: text(defaultClause.defaultText),
      },
    },
    support: {
      references: list(support.references).map((row) => asRecord(row) as Record<string, string | number | boolean | null>),
      audit: {
        aligned: numberValue(asRecord(support.audit).aligned),
        total: numberValue(asRecord(support.audit).total),
        open: numberValue(asRecord(support.audit).open),
      },
    },
    actions: {
      back: text(actions.back) || '/preventivi',
      legacy: text(actions.legacy) || '/preventivi/wizard?_legacy=1',
      calculate: text(actions.calculate) || '/api/v1/ui/preventivi/wizard/calculate',
      create: text(actions.create) || '/api/v1/ui/preventivi/wizard/create',
    },
    warnings: list(page.warnings).map(warning),
  }
}

function normaliseCalculation(raw: unknown): WizardCalculationResponse {
  const payload = asRecord(raw)
  return {
    ...emptyCalculation,
    ok: payload.ok === true,
    state: asRecord(payload.state),
    profile: payload.profile ? practice(payload.profile) : null,
    rows: list(payload.rows).map(draftRow),
    economic: economic(payload.economic),
    fasi: Object.fromEntries(
      Object.entries(asRecord(payload.fasi)).map(([key, value]) => {
        const row = asRecord(value)
        return [key, { min: numberValue(row.min), base: numberValue(row.base), max: numberValue(row.max) }]
      }),
    ),
    scaglione: text(payload.scaglione),
    livello_compenso: text(payload.livello_compenso),
    compenso_base: numberValue(payload.compenso_base),
    bonus_telematico: numberValue(payload.bonus_telematico),
    spese_generali: numberValue(payload.spese_generali),
    note: text(payload.note),
    mediazione_odm: payload.mediazione_odm ? asRecord(payload.mediazione_odm) : null,
    warnings: list(payload.warnings).map(warning),
    audit: asRecord(payload.audit),
    transfer: asRecord(payload.transfer),
  }
}

function normaliseCreate(raw: unknown): WizardCreateResponse {
  const payload = asRecord(raw)
  return {
    ...emptyCreate,
    ok: payload.ok === true,
    id_preventivo: text(payload.id_preventivo),
    id_conferimento: text(payload.id_conferimento),
    id_fascicolo: text(payload.id_fascicolo),
    detail_url: text(payload.detail_url),
    redirect_url: text(payload.redirect_url),
    messages: list(payload.messages).map((rawMessage) => {
      const item = asRecord(rawMessage)
      return { tone: text(item.tone), message: text(item.message) }
    }),
    warnings: list(payload.warnings).map(warning),
  }
}

export async function getPreventivoWizardPage(): Promise<PreventivoWizardPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/preventivi/wizard', emptyPreventivoWizardPage)
  return normalisePage(payload)
}

export async function runPreventivoWizardCalculation(payload: Record<string, unknown>): Promise<WizardCalculationResponse> {
  const response = await apiPostJson<unknown>('/api/v1/ui/preventivi/wizard/calculate', payload, emptyCalculation)
  return normaliseCalculation(response)
}

export async function createPreventivoWizard(payload: Record<string, unknown>): Promise<WizardCreateResponse> {
  const response = await apiPostJson<unknown>('/api/v1/ui/preventivi/wizard/create', payload, emptyCreate)
  return normaliseCreate(response)
}
