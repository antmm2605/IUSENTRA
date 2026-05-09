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
  type: 'text' | 'email' | 'password' | 'number' | 'date' | 'textarea' | 'select' | 'hidden' | 'checkbox' | 'file'
  required: boolean
  value: string
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
    note: display(item.note),
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
  const fieldType = ['text', 'email', 'password', 'number', 'date', 'textarea', 'select', 'hidden', 'checkbox', 'file'].includes(rawType)
    ? rawType as StudioRuntimeField['type']
    : 'text'
  return {
    name: text(item.name),
    label: display(item.label, 'Campo'),
    type: fieldType,
    required: item.required === true,
    value: text(item.value),
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
  return {
    id: text(item.id, 'operazione'),
    title: display(item.title, 'Operazione'),
    body: display(item.body),
    metrics: list(item.metrics).map(normaliseMetric),
    records: list(item.records).map(normaliseRecord),
    actions: list(item.actions).map(normaliseAction),
    form: normaliseForm(item.form),
    warnings: list(item.warnings).map((warning) => display(warning)).filter(Boolean),
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
