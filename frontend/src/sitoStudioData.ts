import { apiJson } from './lib/apiClient'
import type { AdminAction, AdminContract, AdminMetric, AdminSection, AdminTone, AdminWarning, LegacyFormDefinition } from './utentiData'

export type SitoStudioSite = {
  id: number
  tenantSlug: string
  studioName: string
  siteName: string
  publicSlug: string
  title: string
  description: string
  claim: string
  contactEmail: string
  contactPhone: string
  address: string
  city: string
  province: string
  zipCode: string
  published: boolean
  active: boolean
  updatedAt: string
  publicUrl: string
  showLegalTools: boolean
  showApplications: boolean
  showLegalNews: boolean
}

export type SitoStudioMeta = {
  label: string
  value: string
}

export type SitoStudioRecord = {
  id: string
  kind: 'page' | 'article' | 'service' | 'professional' | 'office' | 'contact' | 'booking' | 'unknown'
  title: string
  subtitle: string
  status: string
  statusTone: AdminTone
  href: string
  meta: SitoStudioMeta[]
  forms: LegacyFormDefinition[]
}

export type SitoStudioPageData = {
  source: string
  generated_at: string
  contracts: AdminContract
  site: SitoStudioSite
  metrics: AdminMetric[]
  sections: AdminSection[]
  records: SitoStudioRecord[]
  actions: AdminAction[]
  forms: LegacyFormDefinition[]
  warnings: AdminWarning[]
}

export const emptySitoStudioPage: SitoStudioPageData = {
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'legacy_routes',
    route_owner: 'react_shell',
  },
  site: {
    id: 0,
    tenantSlug: '',
    studioName: '',
    siteName: '',
    publicSlug: '',
    title: '',
    description: '',
    claim: '',
    contactEmail: '',
    contactPhone: '',
    address: '',
    city: '',
    province: '',
    zipCode: '',
    published: false,
    active: false,
    updatedAt: '',
    publicUrl: '',
    showLegalTools: false,
    showApplications: false,
    showLegalNews: false,
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

function kind(value: unknown): SitoStudioRecord['kind'] {
  return ['page', 'article', 'service', 'professional', 'office', 'contact', 'booking'].includes(String(value))
    ? String(value) as SitoStudioRecord['kind']
    : 'unknown'
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
    kind: text(item.kind) || 'summary',
    items: list(item.items).map(normaliseSectionItem),
    emptyMessage: text(item.emptyMessage) || 'Nessun dato disponibile.',
  }
}

function normaliseMeta(raw: unknown): SitoStudioMeta {
  const item = asRecord(raw)
  return {
    label: text(item.label),
    value: text(item.value),
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
    fields: [],
  }
}

function normaliseRecord(raw: unknown): SitoStudioRecord {
  const item = asRecord(raw)
  return {
    id: text(item.id),
    kind: kind(item.kind),
    title: text(item.title) || 'Elemento sito',
    subtitle: text(item.subtitle),
    status: text(item.status),
    statusTone: tone(item.statusTone),
    href: text(item.href),
    meta: list(item.meta).map(normaliseMeta).filter((entry) => entry.label || entry.value),
    forms: list(item.forms).map(normaliseForm).filter((form) => form.action),
  }
}

function normaliseAction(raw: unknown): AdminAction {
  const item = asRecord(raw)
  return {
    id: text(item.id) || text(item.label) || 'azione',
    label: text(item.label) || 'Apri',
    href: text(item.href),
    method: 'GET',
    tone: tone(item.tone),
  }
}

function normaliseWarning(raw: unknown): AdminWarning {
  const item = asRecord(raw)
  return {
    code: text(item.code) || 'warning',
    message: text(item.message) || 'Avviso operativo disponibile.',
  }
}

function normaliseSite(raw: unknown): SitoStudioSite {
  const item = asRecord(raw)
  return {
    id: number(item.id),
    tenantSlug: text(item.tenantSlug),
    studioName: text(item.studioName),
    siteName: text(item.siteName),
    publicSlug: text(item.publicSlug),
    title: text(item.title),
    description: text(item.description),
    claim: text(item.claim),
    contactEmail: text(item.contactEmail),
    contactPhone: text(item.contactPhone),
    address: text(item.address),
    city: text(item.city),
    province: text(item.province),
    zipCode: text(item.zipCode),
    published: bool(item.published),
    active: bool(item.active),
    updatedAt: text(item.updatedAt),
    publicUrl: text(item.publicUrl),
    showLegalTools: bool(item.showLegalTools),
    showApplications: bool(item.showApplications),
    showLegalNews: bool(item.showLegalNews),
  }
}

function normalisePage(raw: unknown): SitoStudioPageData {
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
    site: normaliseSite(page.site),
    metrics: list(page.metrics).map(normaliseMetric),
    sections: list(page.sections).map(normaliseSection),
    records: list(page.records).map(normaliseRecord),
    actions: list(page.actions).map(normaliseAction).filter((action) => action.href && action.method === 'GET'),
    forms: list(page.forms).map(normaliseForm).filter((form) => form.action),
    warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getSitoStudioPage(): Promise<SitoStudioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/sito-studio', emptySitoStudioPage)
  return normalisePage(payload)
}

export async function getSitoStudioContattiPage(): Promise<SitoStudioPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/sito-studio/contatti', emptySitoStudioPage)
  return normalisePage(payload)
}
