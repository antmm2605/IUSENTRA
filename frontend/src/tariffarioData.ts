import { apiJson, apiPostJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type TariffarioFormField = {
  name: string
  label: string
  type: 'text' | 'select' | 'hidden' | 'checkbox'
  required?: boolean
  value?: string
  options?: TariffarioOption[]
}

export type TariffarioOption = {
  value: string
  label: string
  description: string
  enabled: boolean
}

export type TariffarioPhaseOption = {
  key: string
  label: string
  value: string
}

export type TariffarioRuleRow = {
  rule_code: string
  label: string
  rule_label: string
  table_label: string
  table_code?: string
  matter: string
  materia_label?: string
  suggested_practice_id: string
  grado_input_value: string
  calc_mode?: string
  exact_snapshot?: boolean
  compliance_status?: string
  compliance_note?: string
  reference_codes?: string[]
}

export type TariffarioPracticeRow = {
  id: string
  label: string
  area: string
  summary: string
  when_to_use: string
  accessori_calcolo: TariffarioAccessory[]
  esborsi_tipici: TariffarioExpenseOption[]
  variation_policy: Record<string, unknown>
}

export type TariffarioAccessory = {
  id: string
  label: string
  description: string
  tipo_pratica_id: string
  default_checked?: boolean
  row_label?: string
}

export type TariffarioExpenseOption = {
  key: string
  descrizione: string
  importo: number
  importo_label: string
  source: string
}

export type TariffarioCatalog = {
  materiaOptions: TariffarioOption[]
  gradeCatalog: Record<string, string[]>
  phaseCatalog: Record<string, TariffarioPhaseOption[]>
  ruleCatalog: Record<string, TariffarioRuleRow[]>
  complexityOptions: TariffarioOption[]
  ruleOptions: TariffarioOption[]
  areaOptions: TariffarioOption[]
  tableOptions: TariffarioOption[]
  calcModeOptions: TariffarioOption[]
  gradeOptions: TariffarioOption[]
  practices: Record<string, TariffarioPracticeRow>
}

export type TariffarioManualLine = {
  id: string
  descrizione: string
  tipo: string
  importo: string
  fiscale: string
  inclusa: boolean
}

export type TariffarioState = {
  [key: string]: unknown
  materia: string
  regola_tariffaria: string
  grado: string
  valore: string
  complessita: string
  fasi: string[]
  compenso_unico: boolean
  spese_generali: boolean
  bonus_telematico: boolean
  perc_spese_generali: string
  accessori: string[]
  esborsi: string[]
  adr_accordo: boolean
  mediazione_odm_attiva: boolean
  mediazione_odm_regime: string
  mediazione_odm_esito: string
  mediazione_odm_art31_maggiorazione_20: boolean
  manual_lines: TariffarioManualLine[]
}

export type TariffarioProfile = {
  title: string
  description: string
  when: string
  badges: string[]
  metadata: Array<{ label: string; value: string }>
  practiceId: string
  profileCode: string
}

export type TariffarioDynamic = {
  phaseOptions: TariffarioPhaseOption[]
  accessori: TariffarioAccessory[]
  expenseOptions: TariffarioExpenseOption[]
  variationPolicy: Record<string, unknown>
  mediazioneEnabled: boolean
  mediazioneTargets: string[]
  mediazioneEligible?: boolean
  mediazioneEligibleTargets?: string[]
  manualTypes: string[]
  fiscalTypes: string[]
}

export type TariffarioResultRow = {
  id: string
  label: string
  kind: string
  values: Record<string, string>
}

export type TariffarioResult = {
  title: string
  engineLabel: string
  engineText: string
  metadata: Array<{ label: string; value: string }>
  badges: string[]
  table: {
    columns: Array<{ id: string; label: string }>
    rows: TariffarioResultRow[]
    selected: string
  }
  note: string
  warnings: string[]
  audit: Record<string, unknown>
  references: Array<Record<string, unknown> | string>
  referenceCodes: string[]
  tableCode: string
  tableLabel: string
  ruleCode: string
  ruleLabel: string
  exactSnapshot: boolean
  complianceStatus: string
  complianceNote: string
  sourceSnapshot: string
  highRange: boolean
  indeterminate: boolean
  included: Array<{ id: string; descrizione: string; tipo: string; importo: number; importo_label: string; fiscale?: string }>
  economic: {
    rows: Array<{ id: string; label: string; value: string; tone?: string }>
    total: string
    base: string
  }
  actions: {
    preventivo: string
    parcella: string
  }
  selectedLevel: string
  selectedTotal: string
  rangeTotals: Record<string, string>
}

export type TariffarioSupport = {
  auditSummary: Record<string, number>
  auditRows: Array<Record<string, string | number | boolean | null>>
  auditCards: Array<{ value: number; label: string }>
  tables: Array<Record<string, string | number | boolean | null>>
  options: Array<Record<string, string | number | boolean | null>>
  references: Array<Record<string, string | number | boolean | null>>
  channels: Array<Record<string, string | number | boolean | null>>
}

export type TariffarioStats = {
  profiles: number
  rules: number
  tables: number
  options: number
  auditOpen: number
  auditAligned: number
  auditTotal: number
}

export type TariffarioRecord = {
  id: string
  title: string
  subtitle: string
  meta: string
  stateLabel: string
  stateTone: AdminTone
  href: string
}

export type TariffarioFormDefinition = {
  id: string
  title: string
  description: string
  action: string
  method: 'POST'
  submitLabel: string
  enabled: boolean
  fields: TariffarioFormField[]
}

export type TariffarioDetail = {
  id: string
  title: string
  metadata: Record<string, string>
}

export type TariffarioPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  stats: TariffarioStats
  catalog: TariffarioCatalog
  state: TariffarioState
  profile: TariffarioProfile
  dynamic: TariffarioDynamic
  result: TariffarioResult | null
  support: TariffarioSupport
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: TariffarioRecord[]
  actions: AdminAction[]
  forms: TariffarioFormDefinition[]
  warnings: AdminWarning[]
}

export type TariffarioRunResponse = {
  ok: boolean
  state: TariffarioState
  profile: TariffarioProfile
  dynamic: TariffarioDynamic
  result: TariffarioResult | null
  warnings: AdminWarning[]
}

const emptyCatalog: TariffarioCatalog = {
  materiaOptions: [],
  gradeCatalog: {},
  phaseCatalog: {},
  ruleCatalog: {},
  complexityOptions: [],
  ruleOptions: [],
  areaOptions: [],
  tableOptions: [],
  calcModeOptions: [],
  gradeOptions: [],
  practices: {},
}

export const emptyTariffarioState: TariffarioState = {
  materia: '',
  regola_tariffaria: '',
  grado: '',
  valore: '0',
  complessita: 'media',
  fasi: [],
  compenso_unico: true,
  spese_generali: true,
  bonus_telematico: false,
  perc_spese_generali: '15',
  accessori: [],
  esborsi: [],
  adr_accordo: false,
  mediazione_odm_attiva: false,
  mediazione_odm_regime: 'volontaria',
  mediazione_odm_esito: 'primo_incontro_senza_accordo',
  mediazione_odm_art31_maggiorazione_20: false,
  manual_lines: [],
}

const emptyProfile: TariffarioProfile = {
  title: '',
  description: '',
  when: '',
  badges: [],
  metadata: [],
  practiceId: '',
  profileCode: '',
}

const emptyDynamic: TariffarioDynamic = {
  phaseOptions: [],
  accessori: [],
  expenseOptions: [],
  variationPolicy: {},
  mediazioneEnabled: false,
  mediazioneTargets: [],
  mediazioneEligible: false,
  mediazioneEligibleTargets: [],
  manualTypes: [],
  fiscalTypes: [],
}

const emptySupport: TariffarioSupport = {
  auditSummary: {},
  auditRows: [],
  auditCards: [],
  tables: [],
  options: [],
  references: [],
  channels: [],
}

export const emptyTariffarioPage: TariffarioPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
  },
  stats: {
    profiles: 0,
    rules: 0,
    tables: 0,
    options: 0,
    auditOpen: 0,
    auditAligned: 0,
    auditTotal: 0,
  },
  catalog: emptyCatalog,
  state: emptyTariffarioState,
  profile: emptyProfile,
  dynamic: emptyDynamic,
  result: null,
  support: emptySupport,
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
}

const emptyRunResponse: TariffarioRunResponse = {
  ok: false,
  state: emptyTariffarioState,
  profile: emptyProfile,
  dynamic: emptyDynamic,
  result: null,
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

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
  return ''
}

function numberValue(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function bool(value: unknown): boolean {
  return value === true
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

function normaliseOption(raw: unknown): TariffarioOption {
  const item = asRecord(raw)
  return {
    value: text(item.value),
    label: text(item.label) || text(item.value),
    description: text(item.description),
    enabled: item.enabled !== false,
  }
}

function normalisePhase(raw: unknown): TariffarioPhaseOption {
  const item = asRecord(raw)
  return {
    key: text(item.key) || text(item.value),
    label: text(item.label) || text(item.value),
    value: text(item.value) || text(item.label),
  }
}

function normaliseRule(raw: unknown): TariffarioRuleRow {
  const item = asRecord(raw)
  return {
    rule_code: text(item.rule_code),
    label: text(item.label) || text(item.rule_label),
    rule_label: text(item.rule_label),
    table_label: text(item.table_label),
    table_code: text(item.table_code),
    matter: text(item.matter),
    materia_label: text(item.materia_label),
    suggested_practice_id: text(item.suggested_practice_id),
    grado_input_value: text(item.grado_input_value),
    calc_mode: text(item.calc_mode),
    exact_snapshot: bool(item.exact_snapshot),
    compliance_status: text(item.compliance_status),
    compliance_note: text(item.compliance_note),
    reference_codes: normaliseStringList(item.reference_codes),
  }
}

function normaliseExpense(raw: unknown): TariffarioExpenseOption {
  const item = asRecord(raw)
  return {
    key: text(item.key),
    descrizione: text(item.descrizione),
    importo: numberValue(item.importo),
    importo_label: text(item.importo_label),
    source: text(item.source),
  }
}

function normaliseAccessory(raw: unknown): TariffarioAccessory {
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

function normalisePractice(raw: unknown): TariffarioPracticeRow {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    label: text(item.label),
    area: text(item.area),
    summary: text(item.summary),
    when_to_use: text(item.when_to_use),
    accessori_calcolo: list(item.accessori_calcolo).map(normaliseAccessory),
    esborsi_tipici: list(item.esborsi_tipici).map(normaliseExpense),
    variation_policy: asRecord(item.variation_policy),
  }
}

function normaliseStringList(raw: unknown): string[] {
  return list(raw).map((item) => text(item)).filter(Boolean)
}

function normaliseManualLine(raw: unknown): TariffarioManualLine {
  const item = asRecord(raw)
  return {
    id: text(item.id) || `manuale-${String(Date.now())}`,
    descrizione: text(item.descrizione),
    tipo: text(item.tipo) || 'Onorario',
    importo: String(item.importo ?? ''),
    fiscale: text(item.fiscale) || 'imponibile',
    inclusa: item.inclusa !== false,
  }
}

function normaliseState(raw: unknown): TariffarioState {
  const item = asRecord(raw)
  const extraVariationState = Object.fromEntries(
    Object.entries(item).filter(([key]) => key.startsWith('var_')).map(([key, value]) => [key, text(value)]),
  )
  return {
    ...emptyTariffarioState,
    ...extraVariationState,
    materia: text(item.materia),
    regola_tariffaria: text(item.regola_tariffaria),
    grado: text(item.grado),
    valore: text(item.valore) || '0',
    complessita: text(item.complessita) || 'media',
    fasi: normaliseStringList(item.fasi),
    compenso_unico: item.compenso_unico !== false,
    spese_generali: item.spese_generali !== false,
    bonus_telematico: bool(item.bonus_telematico),
    perc_spese_generali: text(item.perc_spese_generali) || '15',
    accessori: normaliseStringList(item.accessori),
    esborsi: normaliseStringList(item.esborsi),
    adr_accordo: bool(item.adr_accordo),
    mediazione_odm_attiva: bool(item.mediazione_odm_attiva),
    mediazione_odm_regime: text(item.mediazione_odm_regime) || 'volontaria',
    mediazione_odm_esito: text(item.mediazione_odm_esito) || 'primo_incontro_senza_accordo',
    mediazione_odm_art31_maggiorazione_20: bool(item.mediazione_odm_art31_maggiorazione_20),
    manual_lines: list(item.manual_lines).map(normaliseManualLine),
  }
}

function normaliseCatalog(raw: unknown): TariffarioCatalog {
  const item = asRecord(raw)
  const gradeCatalogRaw = asRecord(item.gradeCatalog)
  const phaseCatalogRaw = asRecord(item.phaseCatalog)
  const ruleCatalogRaw = asRecord(item.ruleCatalog)
  const practicesRaw = asRecord(item.practices)
  return {
    materiaOptions: list(item.materiaOptions).map(normaliseOption),
    gradeCatalog: Object.fromEntries(
      Object.entries(gradeCatalogRaw).map(([key, value]) => [key, normaliseStringList(value)]),
    ),
    phaseCatalog: Object.fromEntries(
      Object.entries(phaseCatalogRaw).map(([key, value]) => [key, list(value).map(normalisePhase)]),
    ),
    ruleCatalog: Object.fromEntries(
      Object.entries(ruleCatalogRaw).map(([key, value]) => [key, list(value).map(normaliseRule)]),
    ),
    complexityOptions: list(item.complexityOptions).map(normaliseOption),
    ruleOptions: list(item.ruleOptions).map(normaliseOption),
    areaOptions: list(item.areaOptions).map(normaliseOption),
    tableOptions: list(item.tableOptions).map(normaliseOption),
    calcModeOptions: list(item.calcModeOptions).map(normaliseOption),
    gradeOptions: list(item.gradeOptions).map(normaliseOption),
    practices: Object.fromEntries(
      Object.entries(practicesRaw).map(([key, value]) => [key, normalisePractice(value)]),
    ),
  }
}

function normaliseProfile(raw: unknown): TariffarioProfile {
  const item = asRecord(raw)
  return {
    title: text(item.title),
    description: text(item.description),
    when: text(item.when),
    badges: normaliseStringList(item.badges),
    metadata: list(item.metadata).map((rawItem) => {
      const entry = asRecord(rawItem)
      return { label: text(entry.label), value: text(entry.value) }
    }).filter((entry) => entry.label || entry.value),
    practiceId: text(item.practiceId),
    profileCode: text(item.profileCode),
  }
}

function normaliseDynamic(raw: unknown): TariffarioDynamic {
  const item = asRecord(raw)
  return {
    phaseOptions: list(item.phaseOptions).map(normalisePhase),
    accessori: list(item.accessori).map(normaliseAccessory),
    expenseOptions: list(item.expenseOptions).map(normaliseExpense),
    variationPolicy: asRecord(item.variationPolicy),
    mediazioneEnabled: bool(item.mediazioneEnabled),
    mediazioneTargets: normaliseStringList(item.mediazioneTargets),
    mediazioneEligible: bool(item.mediazioneEligible),
    mediazioneEligibleTargets: normaliseStringList(item.mediazioneEligibleTargets),
    manualTypes: normaliseStringList(item.manualTypes),
    fiscalTypes: normaliseStringList(item.fiscalTypes),
  }
}

function normaliseResult(raw: unknown): TariffarioResult | null {
  const item = asRecord(raw)
  if (!Object.keys(item).length) return null
  const table = asRecord(item.table)
  return {
    title: text(item.title) || 'Risultato del calcolo',
    engineLabel: text(item.engineLabel),
    engineText: text(item.engineText),
    metadata: list(item.metadata).map((rawItem) => {
      const entry = asRecord(rawItem)
      return { label: text(entry.label), value: text(entry.value) }
    }).filter((entry) => entry.label || entry.value),
    badges: normaliseStringList(item.badges),
    table: {
      columns: list(table.columns).map((rawColumn) => {
        const column = asRecord(rawColumn)
        return { id: text(column.id), label: text(column.label) }
      }),
      rows: list(table.rows).map((rawRow) => {
        const row = asRecord(rawRow)
        return {
          id: text(row.id),
          label: text(row.label),
          kind: text(row.kind),
          values: Object.fromEntries(
            Object.entries(asRecord(row.values)).map(([key, value]) => [key, text(value)]),
          ),
        }
      }),
      selected: text(table.selected),
    },
    note: text(item.note),
    warnings: normaliseStringList(item.warnings),
    audit: asRecord(item.audit),
    references: list(item.references).map((entry) => {
      const rawRef = asRecord(entry)
      return Object.keys(rawRef).length ? rawRef : text(entry)
    }),
    referenceCodes: normaliseStringList(item.referenceCodes),
    tableCode: text(item.tableCode),
    tableLabel: text(item.tableLabel),
    ruleCode: text(item.ruleCode),
    ruleLabel: text(item.ruleLabel),
    exactSnapshot: bool(item.exactSnapshot),
    complianceStatus: text(item.complianceStatus),
    complianceNote: text(item.complianceNote),
    sourceSnapshot: text(item.sourceSnapshot),
    highRange: bool(item.highRange),
    indeterminate: bool(item.indeterminate),
    included: list(item.included).map((rawLine) => {
      const line = asRecord(rawLine)
      return {
        id: text(line.id),
        descrizione: text(line.descrizione),
        tipo: text(line.tipo),
        importo: numberValue(line.importo),
        importo_label: text(line.importo_label),
        fiscale: text(line.fiscale),
      }
    }),
    economic: {
      rows: list(asRecord(item.economic).rows).map((rawRow) => {
        const row = asRecord(rawRow)
        return { id: text(row.id), label: text(row.label), value: text(row.value), tone: text(row.tone) }
      }),
      total: text(asRecord(item.economic).total),
      base: text(asRecord(item.economic).base),
    },
    actions: {
      preventivo: safeHref(asRecord(item.actions).preventivo),
      parcella: safeHref(asRecord(item.actions).parcella),
    },
    selectedLevel: text(item.selectedLevel),
    selectedTotal: text(item.selectedTotal),
    rangeTotals: Object.fromEntries(
      Object.entries(asRecord(item.rangeTotals)).map(([key, value]) => [key, text(value)]),
    ),
  }
}

function normaliseSupport(raw: unknown): TariffarioSupport {
  const item = asRecord(raw)
  return {
    auditSummary: Object.fromEntries(
      Object.entries(asRecord(item.auditSummary)).map(([key, value]) => [key, numberValue(value)]),
    ),
    auditRows: list(item.auditRows).map((rawRow) => asRecord(rawRow) as Record<string, string | number | boolean | null>),
    auditCards: list(item.auditCards).map((rawCard) => {
      const card = asRecord(rawCard)
      return { value: numberValue(card.value), label: text(card.label) }
    }),
    tables: list(item.tables).map((rawRow) => asRecord(rawRow) as Record<string, string | number | boolean | null>),
    options: list(item.options).map((rawRow) => asRecord(rawRow) as Record<string, string | number | boolean | null>),
    references: list(item.references).map((rawRow) => asRecord(rawRow) as Record<string, string | number | boolean | null>),
    channels: list(item.channels).map((rawRow) => asRecord(rawRow) as Record<string, string | number | boolean | null>),
  }
}

function normaliseStats(raw: unknown): TariffarioStats {
  const item = asRecord(raw)
  return {
    profiles: numberValue(item.profiles),
    rules: numberValue(item.rules),
    tables: numberValue(item.tables),
    options: numberValue(item.options),
    auditOpen: numberValue(item.auditOpen),
    auditAligned: numberValue(item.auditAligned),
    auditTotal: numberValue(item.auditTotal),
  }
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
    href: safeHref(item.href, '/tariffario'),
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

function normaliseRecord(raw: unknown): TariffarioRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'record',
    title: text(item.title) || 'Voce tariffaria',
    subtitle: text(item.subtitle),
    meta: text(item.meta),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    href: safeHref(item.href, '/tariffario'),
  }
}

function normaliseField(raw: unknown): TariffarioFormField | null {
  const item = asRecord(raw)
  const name = text(item.name)
  const allowedNames = new Set([
    'materia',
    'regola_tariffaria',
    'grado',
    'valore',
    'complessita',
    'spese_generali',
    'perc_spese_generali',
    'bonus_telematico',
  ])
  if (!allowedNames.has(name)) return null
  const rawType = text(item.type)
  const fieldType: TariffarioFormField['type'] =
    rawType === 'select' || rawType === 'hidden' || rawType === 'checkbox' ? rawType : 'text'
  return {
    name,
    label: text(item.label) || name,
    type: fieldType,
    required: bool(item.required),
    value: text(item.value),
    options: list(item.options).map(normaliseOption),
  }
}

function normaliseForm(raw: unknown): TariffarioFormDefinition {
  const item = asRecord(raw)
  return {
    id: text(item.id) || 'tariffario_form',
    title: text(item.title) || 'Form tariffario',
    description: text(item.description),
    action: safeHref(item.action, '/tariffario'),
    method: 'POST',
    submitLabel: text(item.submitLabel) || 'Invia',
    enabled: item.enabled !== false,
    fields: list(item.fields).map(normaliseField).filter((field): field is TariffarioFormField => Boolean(field)),
  }
}

function normalisePage(raw: unknown): TariffarioPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'json_api',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    stats: normaliseStats(page.stats),
    catalog: normaliseCatalog(page.catalog),
    state: normaliseState(page.state),
    profile: normaliseProfile(page.profile),
    dynamic: normaliseDynamic(page.dynamic),
    result: normaliseResult(page.result),
    support: normaliseSupport(page.support),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: list(page.forms).map(normaliseForm).filter((form) => form.action),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseRun(raw: unknown): TariffarioRunResponse {
  const page = asRecord(raw)
  return {
    ok: page.ok === true,
    state: normaliseState(page.state),
    profile: normaliseProfile(page.profile),
    dynamic: normaliseDynamic(page.dynamic),
    result: normaliseResult(page.result),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getTariffarioPage(): Promise<TariffarioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/tariffario', emptyTariffarioPage)
  return normalisePage(payload)
}

export async function calculateTariffario(payload: TariffarioState): Promise<TariffarioRunResponse> {
  const response = await apiPostJson<unknown>('/api/v1/ui/tariffario/calcola', payload, emptyRunResponse)
  return normaliseRun(response)
}

export async function runTariffario(payload: TariffarioState): Promise<TariffarioRunResponse> {
  return calculateTariffario(payload)
}

export async function getTariffarioDetail(idVoce: string): Promise<TariffarioDetail | null> {
  const response = await apiJson<unknown>(`/api/v1/ui/tariffario/${encodeURIComponent(idVoce)}`, { ok: false, item: null })
  const item = asRecord(asRecord(response).item)
  if (!Object.keys(item).length) return null
  return {
    id: text(item.id),
    title: text(item.title),
    metadata: Object.fromEntries(Object.entries(asRecord(item.metadata)).map(([key, value]) => [key, text(value)])),
  }
}

export async function linkTariffarioToCompensi() {
  return { ok: false, message: 'Collegamento gestito tramite /compensi-forensi.', errors: { unsupported: 'Azione non supportata.' }, item: null }
}

export async function createPreventivoFromTariffario() {
  return { ok: false, message: 'Creazione preventivo diretta non disponibile da questa API.', errors: { unsupported: 'Usa /preventivi/nuovo.' }, item: null }
}
