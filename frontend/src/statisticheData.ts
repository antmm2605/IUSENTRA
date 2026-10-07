import { ensureJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'

export type StatisticheTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type StatisticheContract = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  legacy_contract?: string
}

export type StatisticheMetric = {
  id: string
  label: string
  value: string | number
  note: string
  tone: StatisticheTone
}

export type StatisticheItem = {
  id: string
  label: string
  value: string | number
  secondaryValue?: string | number
  secondaryLabel?: string
  note: string
  tone: StatisticheTone
}

export type StatisticheSection = {
  id: string
  title: string
  kind: string
  items: StatisticheItem[]
  emptyMessage: string
}

export type StatisticheRecord = {
  id: string
  label: string
  value: string | number
  note: string
  href: string
}

export type StatisticheAction = {
  id: string
  label: string
  href: string
  method: 'GET'
  tone: StatisticheTone
}

export type StatisticheWarning = {
  code: string
  message: string
}

export type StatistichePageData = {
  source: string
  generated_at: string
  contracts: StatisticheContract
  metrics: StatisticheMetric[]
  metricSections: Record<string, StatisticheSection[]>
  sections: StatisticheSection[]
  records: StatisticheRecord[]
  actions: StatisticheAction[]
  warnings: StatisticheWarning[]
}

export const emptyStatistichePage: StatistichePageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
  },
  metrics: [],
  metricSections: {},
  sections: [],
  records: [],
  actions: [],
  warnings: [],
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value.trim() : fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function value(value: unknown): string | number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') return sanitizeDisplayText(value.trim())
  return ''
}

function tone(value: unknown): StatisticheTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as StatisticheTone
    : 'neutral'
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function normaliseMetric(raw: unknown): StatisticheMetric {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: display(item.label) || 'Metrica',
    value: value(item.value),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function displayCategory(raw: unknown): string {
  const labels: Record<string, string> = {
    IN_CORSO: 'In corso', DEFINITO: 'Definito', ARCHIVIATO: 'Archiviato', CHIUSO: 'Chiuso',
    APERTO: 'Aperto', COMPLETATO: 'Completato', ANNULLATO: 'Annullato', SCADUTO: 'Scaduto',
    CRITICA: 'Critica', ALTA: 'Alta', MEDIA: 'Media', BASSA: 'Bassa',
    LAVORO: 'Lavoro', CIVILE: 'Civile', AMMINISTRATIVO: 'Amministrativo', PENALE: 'Penale',
    UDIENZA: 'Udienza', SCADENZA: 'Scadenza', ALTRO: 'Altro', RIUNIONE: 'Riunione',
    CONVERTITO: 'Convertito', BOZZA: 'Bozza', EMESSA: 'Emessa', PAGATA: 'Pagata', EMAIL: 'Email',
  }
  const label = display(raw)
  return labels[label] || label
}

function normaliseItem(raw: unknown): StatisticheItem {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: displayCategory(item.label) || 'Voce',
    value: value(item.value),
    secondaryValue: item.secondaryValue === undefined || item.secondaryValue === null ? undefined : value(item.secondaryValue),
    secondaryLabel: display(item.secondaryLabel),
    note: display(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(raw: unknown): StatisticheSection {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: display(item.title) || 'Sezione',
    kind: display(item.kind) || 'Distribuzione',
    items: list(item.items).map((rawItem) => {
      const row = normaliseItem(rawItem)
      return text(item.id) === 'comunicazioni' && row.label === 'Email'
        ? { ...row, label: 'Messaggi clienti (email)' }
        : row
    }),
    emptyMessage: display(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseRecord(raw: unknown): StatisticheRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'record',
    label: display(item.label) || 'Record',
    value: value(item.value),
    note: display(item.note),
    href: text(item.href) || '/statistiche',
  }
}

function normaliseAction(raw: unknown): StatisticheAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: display(item.label) || 'Apri',
    href: text(item.href) || '/statistiche',
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): StatisticheWarning {
  const item = asRecord(raw)
  return {
    code: display(item.code) || 'warning',
    message: display(item.message) || 'Avviso operativo disponibile.',
  }
}

function normalisePage(raw: unknown): StatistichePageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'none',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    metricSections: Object.fromEntries(Object.entries(asRecord(page.metricSections)).map(([id, sections]) => [id, list(sections).map(normaliseSection)])),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.method === 'GET' && action.href),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getStatistichePage(): Promise<StatistichePageData> {
  const payload = await ensureJson<unknown>('/api/v1/ui/statistiche')
  const page = asRecord(payload)
  if (page.ok === false || page.source === 'errore_controllato' || !text(page.source) ||
      !Array.isArray(page.metrics) || !Array.isArray(page.sections) || !Array.isArray(page.records)) {
    throw new Error('Statistiche non disponibili: risposta incompleta o negativa.')
  }
  return normalisePage(payload)
}
