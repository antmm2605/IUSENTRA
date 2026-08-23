import { apiJson } from './lib/apiClient'
import { sanitizeDisplayText } from './displayText'
import { sanitizePayload, tone, type RouteAction, type WarningItem } from './studioData'
import type { AdminTone } from './utentiData'

export type CapabilityTruthEvidence = {
  kind: string
  status: string
  label: string
  reference: string
  lastVerified: string
  note: string
}

export type ProductReadinessCapability = {
  id: string
  module: string
  owner: string
  route: string
  api: string
  backend: string
  operations: string[]
  permissions: string[]
  storage: string
  featureFlag: string
  status: string
  statusLabel: string
  statusTone: AdminTone
  statusNote: string
  version: string
  tests: string[]
  lastSmoke: { status: string; label: string; verifiedAt: string }
  environment: { local: string; production: string }
  evidence: CapabilityTruthEvidence[]
  dependencies: string[]
  limitations: string
  rollback: string
  incidents: { status: string; label: string }
  nextAction: string
}

export type ProductReadinessPageData = {
  ok: boolean
  generatedAt: string
  registryVersion: string
  applicationVersion: string
  scope: string
  contracts: {
    writes: string
    sourceOfTruth: string
    tenantScope: string
    providerCalls: boolean
    runtimeScans: boolean
    secretsExposed: boolean
  }
  summary: { total: number; verified: number; partial: number; pending: number; blocked: number }
  capabilities: ProductReadinessCapability[]
  navigation: RouteAction
  warnings: WarningItem[]
}

export const emptyProductReadinessPage: ProductReadinessPageData = {
  ok: false,
  generatedAt: '',
  registryVersion: '',
  applicationVersion: '',
  scope: '',
  contracts: { writes: 'none', sourceOfTruth: '', tenantScope: '', providerCalls: false, runtimeScans: false, secretsExposed: false },
  summary: { total: 0, verified: 0, partial: 0, pending: 0, blocked: 0 },
  capabilities: [],
  navigation: { id: 'product-readiness', label: 'Apri prontezza prodotto', href: '/amministrazione?tab=prontezza-prodotto', method: 'GET', tone: 'primary' },
  warnings: [],
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function list(value: unknown): unknown[] { return Array.isArray(value) ? value : [] }
function text(value: unknown, fallback = ''): string { return typeof value === 'string' ? value.trim() : fallback }
function display(value: unknown, fallback = ''): string { return sanitizeDisplayText(text(value, fallback).replace(/[_-]+/g, ' ')) }
function bool(value: unknown): boolean { return value === true }
function number(value: unknown): number { return typeof value === 'number' && Number.isFinite(value) ? value : 0 }
function stringList(value: unknown): string[] { return list(value).map((item) => text(item)).filter(Boolean) }

function normaliseAction(raw: unknown): RouteAction {
  const item = asRecord(raw)
  return { id: text(item.id) || text(item.label) || 'azione', label: display(item.label) || 'Apri', href: text(item.href), method: 'GET', tone: tone(item.tone), protected: bool(item.protected) }
}

function normaliseWarning(raw: unknown): WarningItem {
  const item = asRecord(raw)
  return { code: display(item.code) || 'avviso', message: display(item.message) || 'Avviso operativo disponibile.' }
}

function normaliseEvidence(raw: unknown): CapabilityTruthEvidence {
  const item = asRecord(raw)
  return {
    kind: display(item.kind) || 'prova', status: display(item.status) || 'non indicato', label: display(item.label) || 'Prova non disponibile',
    reference: text(item.reference), lastVerified: text(item.lastVerified), note: display(item.note),
  }
}

function normaliseCapability(raw: unknown): ProductReadinessCapability {
  const item = asRecord(raw)
  const lastSmoke = asRecord(item.lastSmoke)
  const environment = asRecord(item.environment)
  const incidents = asRecord(item.incidents)
  return {
    id: text(item.id) || 'capability', module: display(item.module) || 'Capability P0', owner: display(item.owner) || 'Owner non indicato', route: text(item.route), api: text(item.api), backend: display(item.backend),
    operations: stringList(item.operations).map((entry) => display(entry)), permissions: stringList(item.permissions), storage: display(item.storage), featureFlag: display(item.featureFlag), status: display(item.status) || 'non indicato', statusLabel: display(item.statusLabel) || 'Stato non indicato', statusTone: tone(item.statusTone), statusNote: display(item.statusNote), version: text(item.version), tests: stringList(item.tests),
    lastSmoke: { status: display(lastSmoke.status) || 'non eseguito', label: display(lastSmoke.label) || 'Non ancora verificato', verifiedAt: text(lastSmoke.verifiedAt) },
    environment: { local: display(environment.local) || 'Non ancora verificato', production: display(environment.production) || 'Non ancora verificato' },
    evidence: list(item.evidence).map(normaliseEvidence), dependencies: stringList(item.dependencies).map((entry) => display(entry)), limitations: display(item.limitations), rollback: display(item.rollback),
    incidents: { status: display(incidents.status) || 'non integrato', label: display(incidents.label) || 'Non disponibile' }, nextAction: display(item.nextAction),
  }
}

function normaliseProductReadiness(raw: unknown): ProductReadinessPageData {
  const page = asRecord(sanitizePayload(raw))
  const contracts = asRecord(page.contracts)
  const summary = asRecord(page.summary)
  return {
    ok: bool(page.ok), generatedAt: text(page.generatedAt), registryVersion: text(page.registryVersion), applicationVersion: text(page.applicationVersion), scope: display(page.scope),
    contracts: { writes: display(contracts.writes) || 'none', sourceOfTruth: display(contracts.sourceOfTruth), tenantScope: display(contracts.tenantScope), providerCalls: bool(contracts.providerCalls), runtimeScans: bool(contracts.runtimeScans), secretsExposed: bool(contracts.secretsExposed) },
    summary: { total: number(summary.total), verified: number(summary.verified), partial: number(summary.partial), pending: number(summary.pending), blocked: number(summary.blocked) },
    capabilities: list(page.capabilities).map(normaliseCapability), navigation: normaliseAction(page.navigation), warnings: list(page.warnings).map(normaliseWarning),
  }
}

export async function getProductReadinessPage(): Promise<ProductReadinessPageData> {
  const payload = await apiJson<unknown>('/api/v1/ui/amministrazione/prontezza-prodotto', emptyProductReadinessPage)
  return normaliseProductReadiness(payload)
}
