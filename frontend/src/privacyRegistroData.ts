import { sanitizeDisplayText } from './displayText'
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
  transferSafeguards: string
  retention: string
  securityMeasures: string
  processor: string
  processorRegister: string
  sourceReference: string
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
  missingLegalBasis: number
  missingRecipients: number
  missingSubjects: number
  missingCategories: number
  missingTransferSafeguards: number
  warnings: number
}

export type PrivacyOfficialSource = {
  id: string
  authority: string
  label: string
  url: string
  localPath: string
}

export type PrivacyChecklistItem = {
  id: string
  label: string
  message: string
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
  officialSources: PrivacyOfficialSource[]
  registerChecklist: PrivacyChecklistItem[]
  governance: {
    title: string
    message: string
  }
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
  missingLegalBasis: 0,
  missingRecipients: 0,
  missingSubjects: 0,
  missingCategories: 0,
  missingTransferSafeguards: 0,
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
  officialSources: [],
  registerChecklist: [],
  governance: {
    title: 'Presidio GDPR',
    message: '',
  },
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
    lex: '#lex',
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

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
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
    code: display(item.code, 'warning'),
    label: display(item.label, 'Avviso'),
    tone: tone(item.tone),
    message: display(item.message),
  }
}

function treatmentFromPayload(value: unknown, index: number): PrivacyTreatment {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `trattamento-${index}`)
  return {
    id,
    name: display(item.name, 'Trattamento senza nome'),
    purpose: display(item.purpose),
    dataCategory: display(item.dataCategory),
    legalBasis: display(item.legalBasis),
    subjects: display(item.subjects),
    recipients: display(item.recipients),
    extraEuTransfer: bool(item.extraEuTransfer),
    destinationCountry: display(item.destinationCountry),
    transferSafeguards: display(item.transferSafeguards),
    retention: display(item.retention),
    securityMeasures: display(item.securityMeasures),
    processor: display(item.processor),
    processorRegister: display(item.processorRegister),
    sourceReference: display(item.sourceReference),
    active: item.active !== false,
    notes: display(item.notes),
    createdAt: text(item.createdAt),
    createdLabel: display(item.createdLabel, 'n.d.'),
    updatedAt: text(item.updatedAt),
    updatedLabel: display(item.updatedLabel, 'n.d.'),
    riskFlags: Array.isArray(item.riskFlags) ? item.riskFlags.map(riskFlagFromPayload) : [],
    deleteAction: text(item.deleteAction, `/privacy/registro/${encodeURIComponent(id)}/elimina`),
  }
}

function officialSourceFromPayload(value: unknown): PrivacyOfficialSource {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, 'fonte'),
    authority: display(item.authority),
    label: display(item.label, 'Fonte ufficiale'),
    url: text(item.url),
    localPath: text(item.localPath),
  }
}

function checklistFromPayload(value: unknown): PrivacyChecklistItem {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, 'presidio'),
    label: display(item.label, 'Presidio'),
    message: display(item.message),
  }
}

function optionList(value: unknown): Array<{ value: string; label: string }> {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    const row = isRecord(item) ? item : {}
    return { value: text(row.value), label: display(row.label, text(row.value)) }
  }).filter((item) => item.value || item.label)
}

function normalisePayload(payload: unknown): PrivacyRegistroPageData {
  if (!isRecord(payload)) return emptyPrivacyRegistroPage
  const page = isRecord(payload.page) ? payload.page : {}
  const summary = isRecord(payload.summary) ? payload.summary : {}
  const facets = isRecord(payload.facets) ? payload.facets : {}
  const actions = isRecord(payload.actions) ? payload.actions : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const governance = isRecord(payload.governance) ? payload.governance : {}
  const treatments = Array.isArray(payload.treatments) ? payload.treatments.map(treatmentFromPayload) : []
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt),
    page: {
      title: display(page.title, 'Registro dei trattamenti'),
      subtitle: display(page.subtitle, emptyPrivacyRegistroPage.page.subtitle),
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
      missingLegalBasis: number(summary.missingLegalBasis ?? treatments.filter((item) => !item.legalBasis).length),
      missingRecipients: number(summary.missingRecipients ?? treatments.filter((item) => !item.recipients).length),
      missingSubjects: number(summary.missingSubjects ?? treatments.filter((item) => !item.subjects).length),
      missingCategories: number(summary.missingCategories ?? treatments.filter((item) => !item.dataCategory).length),
      missingTransferSafeguards: number(summary.missingTransferSafeguards ?? treatments.filter((item) => item.extraEuTransfer && !item.transferSafeguards).length),
      warnings: number(summary.warnings ?? treatments.reduce((acc, item) => acc + item.riskFlags.length, 0)),
    },
    treatments,
    officialSources: Array.isArray(payload.officialSources) ? payload.officialSources.map(officialSourceFromPayload) : [],
    registerChecklist: Array.isArray(payload.registerChecklist) ? payload.registerChecklist.map(checklistFromPayload) : [],
    governance: {
      title: display(governance.title, emptyPrivacyRegistroPage.governance.title),
      message: display(governance.message),
    },
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
