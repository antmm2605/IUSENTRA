import type { Tone } from './data'

export type PrivacyRiskFlag = {
  code: string
  label: string
  tone: Tone
  message: string
}

export type PrivacyTreatment = {
  id: string
  name: string
  purpose: string
  dataCategory: string
  legalBasis: string
  subjects: string
  recipients: string
  extraEuTransfer: boolean
  destinationCountry: string
  retention: string
  securityMeasures: string
  processor: string
  active: boolean
  notes: string
  createdAt: string
  createdLabel: string
  updatedAt: string
  updatedLabel: string
  riskFlags: PrivacyRiskFlag[]
  deleteAction: string
}

export type PrivacySummary = {
  total: number
  active: number
  inactive: number
  extraEu: number
  missingSecurity: number
  missingRetention: number
  warnings: number
}

export type PrivacyRegistroPageData = {
  source: string
  generatedAt: string
  page: {
    title: string
    subtitle: string
    path: string
    formOpenByDefault: boolean
  }
  summary: PrivacySummary
  treatments: PrivacyTreatment[]
  facets: {
    legalBasis: Array<{ value: string; label: string }>
    status: Array<{ value: string; label: string }>
  }
  actions: {
    create: string
    list: string
    audit: string
    exportAuditCsv: string
    clienti: string
    settings: string
    lex: string
  }
  contracts: {
    mock_fallback: boolean
    writes: string
    route_owner: string
    legacy_fallback: string
  }
}

const emptySummary: PrivacySummary = {
  total: 0,
  active: 0,
  inactive: 0,
  extraEu: 0,
  missingSecurity: 0,
  missingRetention: 0,
  warnings: 0,
}

export const emptyPrivacyRegistroPage: PrivacyRegistroPageData = {
  source: 'vuoto',
  generatedAt: '',
  page: {
    title: 'Registro dei trattamenti',
    subtitle: 'Caricamento del registro GDPR.',
    path: '/privacy/registro',
    formOpenByDefault: false,
  },
  summary: emptySummary,
  treatments: [],
  facets: {
    legalBasis: [],
    status: [
      { value: 'tutti', label: 'Tutti' },
      { value: 'attivi', label: 'Attivi' },
      { value: 'inattivi', label: 'Inattivi' },
      { value: 'extra_ue', label: 'Trasferimenti extra UE' },
      { value: 'da_completare', label: 'Da completare' },
    ],
  },
  actions: {
    create: '/privacy/registro/nuovo',
    list: '/privacy/registro',
    audit: '/audit',
    exportAuditCsv: '/audit/esporta.csv',
    clienti: '/clienti',
    settings: '/impostazioni',
    lex: '/lex?context=registro-gdpr',
  },
  contracts: {
    mock_fallback: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
    legacy_fallback: '_legacy=1 tecnico',
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim()
  return raw || fallback
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 1 || text(value).toLowerCase() === 'true' || text(value) === '1'
}

function tone(value: unknown): Tone {
  const raw = text(value, 'neutral').toLowerCase()
  if (['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw)) return raw as Tone
  return 'neutral'
}

function riskFlagFromPayload(value: unknown): PrivacyRiskFlag {
  const item = isRecord(value) ? value : {}
  return {
    code: text(item.code, 'warning'),
    label: text(item.label, 'Avviso'),
    tone: tone(item.tone),
    message: text(item.message),
  }
}

function treatmentFromPayload(value: unknown, index: number): PrivacyTreatment {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `trattamento-${index}`)
  return {
    id,
    name: text(item.name, 'Trattamento senza nome'),
    purpose: text(item.purpose),
    dataCategory: text(item.dataCategory),
    legalBasis: text(item.legalBasis),
    subjects: text(item.subjects),
    recipients: text(item.recipients),
    extraEuTransfer: bool(item.extraEuTransfer),
    destinationCountry: text(item.destinationCountry),
    retention: text(item.retention),
    securityMeasures: text(item.securityMeasures),
    processor: text(item.processor),
    active: item.active !== false,
    notes: text(item.notes),
    createdAt: text(item.createdAt),
    createdLabel: text(item.createdLabel, 'n.d.'),
    updatedAt: text(item.updatedAt),
    updatedLabel: text(item.updatedLabel, 'n.d.'),
    riskFlags: Array.isArray(item.riskFlags) ? item.riskFlags.map(riskFlagFromPayload) : [],
    deleteAction: text(item.deleteAction, `/privacy/registro/${encodeURIComponent(id)}/elimina`),
  }
}

function optionList(value: unknown): Array<{ value: string; label: string }> {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return { value: text(row.value), label: text(row.label, text(row.value)) }
  }).filter((item) => item.value || item.label)
}

function normalisePayload(payload: unknown): PrivacyRegistroPageData {
  if (!isRecord(payload)) return emptyPrivacyRegistroPage
  const page = isRecord(payload.page) ? payload.page : {}
  const summary = isRecord(payload.summary) ? payload.summary : {}
  const facets = isRecord(payload.facets) ? payload.facets : {}
  const actions = isRecord(payload.actions) ? payload.actions : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const treatments = Array.isArray(payload.treatments) ? payload.treatments.map(treatmentFromPayload) : []
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt),
    page: {
      title: text(page.title, 'Registro dei trattamenti'),
      subtitle: text(page.subtitle, emptyPrivacyRegistroPage.page.subtitle),
      path: text(page.path, '/privacy/registro'),
      formOpenByDefault: bool(page.formOpenByDefault),
    },
    summary: {
      total: number(summary.total ?? treatments.length),
      active: number(summary.active ?? treatments.filter((item) => item.active).length),
      inactive: number(summary.inactive ?? treatments.filter((item) => !item.active).length),
      extraEu: number(summary.extraEu ?? treatments.filter((item) => item.extraEuTransfer).length),
      missingSecurity: number(summary.missingSecurity ?? treatments.filter((item) => !item.securityMeasures).length),
      missingRetention: number(summary.missingRetention ?? treatments.filter((item) => !item.retention).length),
      warnings: number(summary.warnings ?? treatments.reduce((acc, item) => acc + item.riskFlags.length, 0)),
    },
    treatments,
    facets: {
      legalBasis: optionList(facets.legalBasis),
      status: optionList(facets.status).length ? optionList(facets.status) : emptyPrivacyRegistroPage.facets.status,
    },
    actions: {
      create: text(actions.create, emptyPrivacyRegistroPage.actions.create),
      list: text(actions.list, emptyPrivacyRegistroPage.actions.list),
      audit: text(actions.audit, emptyPrivacyRegistroPage.actions.audit),
      exportAuditCsv: text(actions.exportAuditCsv, emptyPrivacyRegistroPage.actions.exportAuditCsv),
      clienti: text(actions.clienti, emptyPrivacyRegistroPage.actions.clienti),
      settings: text(actions.settings, emptyPrivacyRegistroPage.actions.settings),
      lex: text(actions.lex, emptyPrivacyRegistroPage.actions.lex),
    },
    contracts: {
      mock_fallback: bool(contracts.mock_fallback),
      writes: text(contracts.writes, 'operational_routes'),
      route_owner: text(contracts.route_owner, 'react_shell'),
      legacy_fallback: text(contracts.legacy_fallback, '_legacy=1 tecnico'),
    },
  }
}

export async function getPrivacyRegistroPage(): Promise<PrivacyRegistroPageData> {
  const params = new URLSearchParams()
  params.set('path', window.location.pathname)
  params.set('_ts', String(Date.now()))
  const response = await fetch(`/api/v1/ui/privacy/registro?${params.toString()}`, {
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error('Registro GDPR non disponibile')
  return normalisePayload(await response.json())
}
