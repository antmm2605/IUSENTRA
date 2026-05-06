import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type StudioRecord = {
  id: string
  label: string
  href: string
  status: string
  tone: AdminTone
  note: string
}

export type StudioProfile = {
  id: string
  username: string
  label: string
  role: string
  active: boolean
}

export type StudioPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: StudioRecord[]
  actions: AdminAction[]
  forms: []
  warnings: AdminWarning[]
  studio: {
    name: string
    profile: StudioProfile
  }
}

export const emptyStudioPage: StudioPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'legacy_routes',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
  studio: {
    name: '',
    profile: {
      id: '',
      username: '',
      label: '',
      role: '',
      active: false,
    },
  },
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

function bool(value: unknown): boolean {
  return value === true
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
    href: text(item.href) || '/studio',
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

function normaliseRecord(raw: unknown): StudioRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'modulo',
    label: text(item.label) || 'Modulo',
    href: text(item.href) || '/studio',
    status: text(item.status) || 'Stato non indicato',
    tone: tone(item.tone),
    note: text(item.note),
  }
}

function normaliseProfile(raw: unknown): StudioProfile {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    username: text(item.username),
    label: text(item.label) || text(item.username),
    role: text(item.role),
    active: bool(item.active),
  }
}

function normalisePage(raw: unknown): StudioPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
  const studio = asRecord(page.studio)
  return {
    source: text(page.source),
    generated_at: text(page.generated_at),
    contracts: {
      mock_fallback: contracts.mock_fallback === true ? true : false,
      writes: text(contracts.writes) || 'legacy_routes',
      route_owner: text(contracts.route_owner) || 'react_shell',
      legacy_contract: text(contracts.legacy_contract),
    },
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.href),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
    studio: {
      name: text(studio.name) || 'Studio',
      profile: normaliseProfile(studio.profile),
    },
  }
}

export async function getStudioPage(): Promise<StudioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/studio', emptyStudioPage)
  return normalisePage(payload)
}
