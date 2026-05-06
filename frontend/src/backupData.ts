import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning, LegacyFormDefinition } from './utentiData'
import type { LegacyPostField } from './ui/LegacyPostForm'

export type BackupRecord = {
  id: string
  timestamp: string
  type: string
  status: string
  statusTone: AdminTone
  fileName: string
  sizeMb: number
  filesCount: number
  components: string[]
  encrypted: boolean
  note: string
  error: string
  downloadHref: string
  verifyAction: string
  restoreHref: string
  deleteAction: string
}

export type BackupPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: BackupRecord[]
  actions: AdminAction[]
  forms: LegacyFormDefinition[]
  warnings: AdminWarning[]
}

export const emptyBackupPage: BackupPageData = {
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

function number(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
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

function normaliseSectionItem(raw: unknown) {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'voce',
    label: text(item.label) || 'Voce',
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
    items: list(item.items).map(normaliseSectionItem),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseRecord(raw: unknown): BackupRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    timestamp: text(item.timestamp),
    type: text(item.type),
    status: text(item.status),
    statusTone: tone(item.statusTone),
    fileName: text(item.fileName),
    sizeMb: number(item.sizeMb),
    filesCount: number(item.filesCount),
    components: list(item.components).map((entry) => text(entry)).filter(Boolean),
    encrypted: bool(item.encrypted),
    note: text(item.note),
    error: text(item.error),
    downloadHref: text(item.downloadHref),
    verifyAction: text(item.verifyAction),
    restoreHref: text(item.restoreHref),
    deleteAction: text(item.deleteAction),
  }
}

function normaliseField(raw: unknown): LegacyPostField {
  const item = asRecord(raw)
  const fieldType = ['text', 'email', 'select', 'checkbox', 'hidden'].includes(String(item.type))
    ? String(item.type) as LegacyPostField['type']
    : 'text'
  return {
    name: text(item.name),
    label: text(item.label),
    type: fieldType,
    required: bool(item.required),
    value: text(item.value),
    options: list(item.options).map((option) => {
      const record = asRecord(option)
      return {
        value: text(record.value) || text(record.id),
        label: text(record.label),
        enabled: record.enabled === false ? false : true,
      }
    }),
  }
}

function normaliseForm(raw: unknown): LegacyFormDefinition {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.title) || 'form',
    title: text(item.title),
    description: text(item.description),
    action: text(item.action),
    method: 'POST',
    csrfField: text(item.csrfField),
    submitLabel: text(item.submitLabel) || 'Invia',
    enabled: item.enabled === false ? false : true,
    fields: list(item.fields).map(normaliseField).filter((field) => field.name),
  }
}

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: text(item.href) || '/backup?_legacy=1',
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

function normalisePage(raw: unknown): BackupPageData {
  const page = asRecord(raw)
  const contracts = asRecord(page.contracts)
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
    records: list(page.records).map(normaliseRecord),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.method === 'GET' && action.href),
    forms: list(page.forms).map(normaliseForm).filter((form) => form.action),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getBackupPage(): Promise<BackupPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/backup', emptyBackupPage)
  return normalisePage(payload)
}
