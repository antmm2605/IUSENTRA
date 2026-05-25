import { sanitizeDisplayText } from './displayText'

export type StudioRuntimeMetric = {
  label: string
  value: string
  note: string
}

export type StudioRuntimeRecord = {
  id: string
  title: string
  subtitle: string
  badge: string
  href: string
  meta: string
}

export type StudioRuntimeAction = {
  label: string
  href: string
  method: 'GET' | 'POST'
  tone: string
}

export type StudioRuntimeField = {
  name: string
  label: string
  type: 'text' | 'email' | 'password' | 'number' | 'date' | 'textarea' | 'select' | 'hidden' | 'checkbox' | 'file' | 'multiselect'
  required: boolean
  value: string | string[]
  step: string
  min: string
  max: string
  options: Array<{ value: string; label: string }>
}

export type StudioRuntimeForm = {
  action: string
  method: 'GET' | 'POST'
  enctype: string
  submitLabel: string
  fields: StudioRuntimeField[]
}

export type StudioRuntimeOperation = {
  id: string
  title: string
  body: string
  metrics: StudioRuntimeMetric[]
  records: StudioRuntimeRecord[]
  actions: StudioRuntimeAction[]
  form: StudioRuntimeForm | null
  warnings: string[]
  tool: {
    toolId: string
    appId: string
  } | null
}

export type StudioRuntimeResultTable = {
  title: string
  headers: string[]
  rows: string[][]
}

export type StudioRuntimeResultSource = {
  title: string
  url: string
}

export type StudioRuntimeOffice = {
  id: string
  name: string
  kind: string
  typeLabel: string
  primary: boolean
  address: string
  city: string
  cap: string
  phone: string
  fax: string
  email: string
  pec: string
  site: string
  fiscalCode: string
  patrono: string
  notes: string
  assistenzaPct: Record<string, string>
  casellario: Record<string, string>
  actions: StudioRuntimeAction[]
}

export type StudioRuntimeResult = {
  ok: boolean
  message: string
  toolId: string
  title: string
  metrics: StudioRuntimeMetric[]
  tables: StudioRuntimeResultTable[]
  previewText: string
  notes: string[]
  warnings: string[]
  sources: StudioRuntimeResultSource[]
  offices: StudioRuntimeOffice[]
}

export type StudioModuleRuntime = {
  source: string
  moduleId: string
  generatedAt: string
  contracts: {
    mock_fallback: boolean
    writes: string
    route_owner: string
  }
  metrics: StudioRuntimeMetric[]
  operations: StudioRuntimeOperation[]
}

export const emptyStudioModuleRuntime: StudioModuleRuntime = {
  source: 'vuoto',
  moduleId: '',
  generatedAt: '',
  contracts: {
    mock_fallback: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
  },
  metrics: [],
  operations: [],
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim()
  return raw || fallback
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function method(value: unknown): 'GET' | 'POST' {
  return text(value).toUpperCase() === 'POST' ? 'POST' : 'GET'
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function normaliseMetric(value: unknown): StudioRuntimeMetric {
  const item = isRecord(value) ? value : {}
  return {
    label: display(item.label, 'Indicatore'),
    value: display(item.value, '0'),
    note: display(item.note || item.subtext),
  }
}

function normaliseRecord(value: unknown): StudioRuntimeRecord {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, 'record'),
    title: display(item.title, 'Elemento'),
    subtitle: display(item.subtitle),
    badge: display(item.badge),
    href: text(item.href, '#'),
    meta: display(item.meta),
  }
}

function normaliseAction(value: unknown): StudioRuntimeAction {
  const item = isRecord(value) ? value : {}
  return {
    label: display(item.label, 'Apri'),
    href: text(item.href, '#'),
    method: method(item.method),
    tone: text(item.tone, 'primary'),
  }
}

function normaliseField(value: unknown): StudioRuntimeField {
  const item = isRecord(value) ? value : {}
  const rawType = text(item.type, 'text')
  const fieldType = ['text', 'email', 'password', 'number', 'date', 'textarea', 'select', 'hidden', 'checkbox', 'file', 'multiselect'].includes(rawType)
    ? rawType as StudioRuntimeField['type']
    : 'text'
  return {
    name: text(item.name),
    label: display(item.label, 'Campo'),
    type: fieldType,
    required: item.required === true,
    value: Array.isArray(item.value) ? item.value.map((row) => text(row)).filter(Boolean) : text(item.value),
    step: text(item.step),
    min: text(item.min),
    max: text(item.max),
    options: list(item.options).map((option) => {
      const row = isRecord(option) ? option : {}
      return { value: text(row.value), label: display(row.label, text(row.value)) }
    }),
  }
}

function normaliseForm(value: unknown): StudioRuntimeForm | null {
  if (!isRecord(value)) return null
  return {
    action: text(value.action, '#'),
    method: method(value.method),
    enctype: text(value.enctype),
    submitLabel: display(value.submitLabel, 'Salva'),
    fields: list(value.fields).map(normaliseField).filter((field) => field.name),
  }
}

function normaliseOperation(value: unknown): StudioRuntimeOperation {
  const item = isRecord(value) ? value : {}
  const tool = isRecord(item.tool) ? item.tool : null
  return {
    id: text(item.id, 'operazione'),
    title: display(item.title, 'Operazione'),
    body: display(item.body),
    metrics: list(item.metrics).map(normaliseMetric),
    records: list(item.records).map(normaliseRecord),
    actions: list(item.actions).map(normaliseAction),
    form: normaliseForm(item.form),
    warnings: list(item.warnings).map((warning) => display(warning)).filter(Boolean),
    tool: tool ? { toolId: text(tool.toolId), appId: text(tool.appId) } : null,
  }
}

function normaliseResultTable(value: unknown): StudioRuntimeResultTable {
  const item = isRecord(value) ? value : {}
  return {
    title: display(item.title, 'Dettaglio'),
    headers: list(item.headers).map((header) => display(header)).filter(Boolean),
    rows: list(item.rows).map((row) => list(row).map((cell) => display(cell))),
  }
}

function normaliseResultSource(value: unknown): StudioRuntimeResultSource {
  const item = isRecord(value) ? value : {}
  return {
    title: display(item.title || item.label || item.name, 'Fonte'),
    url: text(item.url || item.href),
  }
}

function normaliseTextMap(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {}
  const entries: Array<[string, string]> = []
  Object.entries(value).forEach(([key, mapValue]) => {
    const entryKey = text(key)
    const entryValue = display(mapValue)
    if (entryKey && entryValue) entries.push([entryKey, entryValue])
  })
  return Object.fromEntries(entries)
}

function normaliseOffice(value: unknown): StudioRuntimeOffice {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, 'ufficio'),
    name: display(item.name, 'Ufficio giudiziario'),
    kind: text(item.kind),
    typeLabel: display(item.typeLabel || item.type_label, 'Ufficio'),
    primary: item.primary === true,
    address: display(item.address),
    city: display(item.city),
    cap: display(item.cap),
    phone: display(item.phone),
    fax: display(item.fax),
    email: display(item.email),
    pec: display(item.pec),
    site: text(item.site),
    fiscalCode: display(item.fiscalCode || item.fiscal_code),
    patrono: display(item.patrono),
    notes: display(item.notes),
    assistenzaPct: normaliseTextMap(item.assistenzaPct || item.assistenza_pct),
    casellario: normaliseTextMap(item.casellario),
    actions: list(item.actions).map(normaliseAction),
  }
}

export function normaliseStudioRuntimeResult(value: unknown): StudioRuntimeResult {
  const item = isRecord(value) ? value : {}
  return {
    ok: item.ok === true,
    message: display(item.message, item.ok === true ? 'Calcolo completato.' : 'Verifica non riuscita.'),
    toolId: text(item.toolId),
    title: display(item.title, 'Risultato'),
    metrics: list(item.metrics).map(normaliseMetric),
    tables: list(item.tables).map(normaliseResultTable),
    previewText: display(item.previewText || item.preview_text),
    notes: list(item.notes).map((note) => display(note)).filter(Boolean),
    warnings: list(item.warnings).map((warning) => display(warning)).filter(Boolean),
    sources: list(item.sources).map(normaliseResultSource).filter((source) => source.title || source.url),
    offices: list(item.offices).map(normaliseOffice).filter((office) => office.name),
  }
}

export function operationIdFromTitle(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function normaliseRuntime(payload: unknown): StudioModuleRuntime {
  if (!isRecord(payload)) return emptyStudioModuleRuntime
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  return {
    source: text(payload.source, 'repository_reali'),
    moduleId: text(payload.moduleId),
    generatedAt: text(payload.generatedAt),
    contracts: {
      mock_fallback: contracts.mock_fallback === true,
      writes: text(contracts.writes, 'operational_routes'),
      route_owner: text(contracts.route_owner, 'react_shell'),
    },
    metrics: list(payload.metrics).map(normaliseMetric),
    operations: list(payload.operations).map(normaliseOperation),
  }
}

export async function getStudioModuleRuntime(moduleId: string): Promise<StudioModuleRuntime> {
  try {
    const params = new URLSearchParams()
    if (typeof window !== 'undefined') {
      params.set('path', window.location.pathname)
      const current = new URLSearchParams(window.location.search)
      current.forEach((value, key) => params.append(key, value))
    }
    const query = params.toString()
    const response = await fetch(`/api/v1/ui/studio-modules/${encodeURIComponent(moduleId)}${query ? `?${query}` : ''}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyStudioModuleRuntime
    return normaliseRuntime(await response.json())
  } catch {
    return emptyStudioModuleRuntime
  }
}
