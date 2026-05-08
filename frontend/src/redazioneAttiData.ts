import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning } from './utentiData'

export type RedazioneAttiRecord = {
  id: string
  title: string
  subtitle: string
  meta: string
  stateLabel: string
  stateTone: AdminTone
  href: string
}

export type RedazioneAttiPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: RedazioneAttiRecord[]
  actions: AdminAction[]
  forms: []
  warnings: AdminWarning[]
  summary: string
}

export const emptyRedazioneAttiPage: RedazioneAttiPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'none',
    route_owner: 'react_shell',
  },
  metrics: [],
  sections: [],
  records: [],
  actions: [],
  forms: [],
  warnings: [],
  summary: '',
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

function tone(value: unknown): AdminTone {
  return ['primary', 'neutral', 'danger', 'success', 'warning', 'info'].includes(String(value))
    ? String(value) as AdminTone
    : 'neutral'
}

function safeHref(value: unknown, fallback = ''): string {
  const href = text(value)
  return href.startsWith('/') && href !== '#' ? href : fallback
}

function normaliseMetric(input: unknown): AdminMetric {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'metrica',
    label: text(item.label) || 'Metrica',
    value: scalar(item.value),
    note: text(item.note),
    tone: tone(item.tone),
  }
}

function normaliseSection(input: unknown): AdminSection {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'sezione',
    title: text(item.title) || 'Sezione',
    kind: text(item.kind) || 'distribution',
    items: list(item.items).map((entryInput) => {
      const entry = asRecord(entryInput)
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

function normaliseAction(input: unknown): AdminAction {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: safeHref(item.href, '/redazione-atti'),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(input: unknown): AdminWarning {
  const item = asRecord(input)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso tecnico disponibile.',
  }
}

function normaliseRecord(input: unknown): RedazioneAttiRecord {
  const item = asRecord(input)
  return {
    id: text(item.id) || text(item.title) || 'record',
    title: text(item.title) || 'Voce operativa',
    subtitle: text(item.subtitle),
    meta: text(item.meta),
    stateLabel: text(item.stateLabel),
    stateTone: tone(item.stateTone),
    href: safeHref(item.href, '/redazione-atti'),
  }
}

function normalisePage(input: unknown): RedazioneAttiPageData {
  const page = asRecord(input)
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
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord).filter((record) => record.id),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href),
    forms: [],
    warnings: list(page.warnings).map(normaliseWarning),
    summary: text(page.summary),
  }
}

export async function getRedazioneAttiPage(): Promise<RedazioneAttiPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/redazione-atti', emptyRedazioneAttiPage)
  return normalisePage(payload)
}
