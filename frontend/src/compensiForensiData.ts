import { apiJson, apiPostJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type CompensiForensiRecord = {
  id: string
  title: string
  subtitle: string
  meta: string
  stateLabel: string
  stateTone: AdminTone
  href: string
}

export type CompensiForensiParameters = {
  areas: Array<{ value: string; label: string }>
  proceedings: Array<{ value: string; label: string; area: string; grade: string }>
  complexities: Array<{ value: string; label: string }>
  fiscal_options: {
    applica_iva: boolean
    applica_cassa: boolean
    applica_ritenuta: boolean
  }
}

export type CompensiForensiCalculationPayload = {
  area: string
  procedimento: string
  fase: string
  valore_controversia: number
  complessita: string
  aumenti: string[]
  riduzioni: string[]
  opzioni_fiscali: {
    applica_iva: boolean
    applica_cassa: boolean
    applica_ritenuta: boolean
  }
}

export type CompensiForensiCalculationResult = {
  title: string
  engineLabel: string
  engineText: string
  metadata: Array<{ label: string; value: string }>
  badges: string[]
  table?: {
    columns: Array<{ id: string; label: string }>
    rows: Array<{ id: string; label: string; values: Record<string, string> }>
    selected: string
  }
  note: string
  warnings: string[]
  economic?: {
    rows: Array<{ id: string; label: string; value: string; tone?: string }>
    total: string
    base: string
  }
  selectedTotal?: string
}

export type CompensiForensiPermissions = {
  canCalculate: boolean
  canSaveLog: boolean
  canCreatePreventivo: boolean
  canOpenTariffario: boolean
  links: AdminAction[]
}

export type CompensiForensiMutationResult = {
  ok: boolean
  message: string
  errors: Record<string, string>
  result: CompensiForensiCalculationResult | null
  warnings: AdminWarning[]
}

export type CompensiForensiPageData = {
  ok?: boolean
  source: string
  generated_at: string
  contracts: AdminContract
  parameters: CompensiForensiParameters
  areas: Array<{ value: string; label: string }>
  phases: Array<{ value: string; label: string }>
  options: Record<string, unknown>
  last_results: CompensiForensiCalculationResult[]
  actions: CompensiForensiPermissions
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: CompensiForensiRecord[]
  warnings: AdminWarning[]
}

const emptyParameters: CompensiForensiParameters = {
  areas: [],
  proceedings: [],
  complexities: [],
  fiscal_options: {
    applica_iva: true,
    applica_cassa: true,
    applica_ritenuta: false,
  },
}

const emptyActions: CompensiForensiPermissions = {
  canCalculate: false,
  canSaveLog: false,
  canCreatePreventivo: false,
  canOpenTariffario: false,
  links: [],
}

export const emptyCompensiForensiPage: CompensiForensiPageData = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'azioni_auditate',
    route_owner: 'react_shell',
  },
  parameters: emptyParameters,
  areas: [],
  phases: [],
  options: {},
  last_results: [],
  actions: emptyActions,
  metrics: [],
  sections: [],
  records: [],
  warnings: [],
}

const emptyMutation: CompensiForensiMutationResult = {
  ok: false,
  message: 'Calcolo non completato.',
  errors: {},
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

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function scalar(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return value.trim()
  return ''
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

function normaliseMetric(raw: unknown): AdminMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: scalar(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): AdminSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'Sezione operativa',
    items: list(item.items).map((rawItem) => {
      const entry = asRecord(rawItem)
      return {
        id: text(entry.id) || text(entry.label) || 'voce',
        label: display(entry.label) || 'Voce',
        value: scalar(entry.value),
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
    href: safeHref(item.href, '/compensi-forensi'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): AdminWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseRecord(raw: unknown): CompensiForensiRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'record',
    title: display(item.title) || 'Voce operativa',
    subtitle: display(item.subtitle),
    meta: display(item.meta),
    stateLabel: display(item.stateLabel),
    stateTone: tone(item.stateTone),
    href: safeHref(item.href, '/tariffario'),
  }
}

function normaliseParameters(raw: unknown): CompensiForensiParameters {
  const item = asRecord(raw)
  return {
    areas: list(item.areas).map((entry) => {
      const row = asRecord(entry)
      return { value: text(row.value), label: display(row.label) || display(row.value) }
    }).filter((row) => row.value || row.label),
    proceedings: list(item.proceedings).map((entry) => {
      const row = asRecord(entry)
      return {
        value: text(row.value),
        label: display(row.label) || display(row.value),
        area: display(row.area),
        grade: display(row.grade),
      }
    }).filter((row) => row.value || row.label),
    complexities: list(item.complexities).map((entry) => {
      const row = asRecord(entry)
      return { value: text(row.value), label: display(row.label) || display(row.value) }
    }).filter((row) => row.value || row.label),
    fiscal_options: {
      applica_iva: asRecord(item.fiscal_options).applica_iva !== false,
      applica_cassa: asRecord(item.fiscal_options).applica_cassa !== false,
      applica_ritenuta: bool(asRecord(item.fiscal_options).applica_ritenuta),
    },
  }
}

function normaliseActions(raw: unknown): CompensiForensiPermissions {
  const item = asRecord(raw)
  return {
    canCalculate: bool(item.canCalculate),
    canSaveLog: bool(item.canSaveLog),
    canCreatePreventivo: bool(item.canCreatePreventivo),
    canOpenTariffario: bool(item.canOpenTariffario),
    links: list(item.links).map(normaliseAction).filter((action) => action.href),
  }
}

function normaliseResult(raw: unknown): CompensiForensiCalculationResult | null {
  const item = asRecord(raw)
  if (!Object.keys(item).length) return null
  const table = asRecord(item.table)
  const economic = asRecord(item.economic)
  return {
    title: display(item.title) || 'Risultato calcolo',
    engineLabel: display(item.engineLabel),
    engineText: display(item.engineText),
    metadata: list(item.metadata).map((entry) => {
      const row = asRecord(entry)
      return { label: display(row.label), value: display(row.value) }
    }).filter((row) => row.label || row.value),
    badges: list(item.badges).map((entry) => display(entry)).filter(Boolean),
    table: Object.keys(table).length ? {
      columns: list(table.columns).map((entry) => {
        const row = asRecord(entry)
        return { id: text(row.id), label: display(row.label) }
      }),
      rows: list(table.rows).map((entry) => {
        const row = asRecord(entry)
        return {
          id: text(row.id),
          label: display(row.label),
          values: Object.fromEntries(Object.entries(asRecord(row.values)).map(([key, val]) => [key, display(val)])),
        }
      }),
      selected: display(table.selected),
    } : undefined,
    note: display(item.note),
    warnings: list(item.warnings).map((entry) => display(entry)).filter(Boolean),
    economic: Object.keys(economic).length ? {
      rows: list(economic.rows).map((entry) => {
        const row = asRecord(entry)
        return { id: text(row.id), label: display(row.label), value: display(row.value), tone: text(row.tone) }
      }),
      total: display(economic.total),
      base: display(economic.base),
    } : undefined,
    selectedTotal: display(item.selectedTotal),
  }
}

function normalisePage(raw: unknown): CompensiForensiPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const parameters = normaliseParameters(page.parameters)
  return {
    ok: page.ok === true,
    source: display(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: display(contracts.writes) || 'azioni_auditate',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    parameters,
    areas: list(page.areas).map((entry) => {
      const row = asRecord(entry)
      return { value: text(row.value), label: display(row.label) || display(row.value) }
    }).filter((row) => row.value || row.label),
    phases: list(page.phases).map((entry) => {
      const row = asRecord(entry)
      return { value: text(row.value), label: display(row.label) || display(row.value) }
    }).filter((row) => row.value || row.label),
    options: asRecord(page.options),
    last_results: list(page.last_results).map(normaliseResult).filter((item): item is CompensiForensiCalculationResult => Boolean(item)),
    actions: normaliseActions(page.actions),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

function normaliseMutation(raw: unknown): CompensiForensiMutationResult {
  const item = asRecord(raw)
  return {
    ok: item.ok === true,
    message: display(item.message) || (item.ok === true ? 'Calcolo completato.' : 'Calcolo non completato.'),
    errors: asRecord(item.errors) as Record<string, string>,
    result: normaliseResult(item.result),
    warnings: list(item.warnings).map(normaliseWarning),
  }
}

export async function getCompensiForensiPage(): Promise<CompensiForensiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/compensi-forensi', emptyCompensiForensiPage)
  return normalisePage(payload)
}

export async function calculateCompensiForensi(payload: CompensiForensiCalculationPayload): Promise<CompensiForensiMutationResult> {
  return normaliseMutation(await apiPostJson<unknown>('/api/v1/ui/compensi-forensi/calcola', payload, emptyMutation))
}

export async function saveCompensiForensiLog(): Promise<CompensiForensiMutationResult> {
  return {
    ...emptyMutation,
    message: 'Salvataggio log non disponibile da questa vista.',
    errors: { unsupported: 'Azione non disponibile da questa vista.' },
  }
}

export async function createPreventivoFromCompensi(): Promise<CompensiForensiMutationResult> {
  return {
    ...emptyMutation,
    message: 'Creazione preventivo diretta non disponibile da questa vista.',
    errors: { unsupported: 'Usa il flusso nuovo preventivo.' },
  }
}
