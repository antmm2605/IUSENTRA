import { apiJson, apiPostJson } from './lib/apiClient'
import { csrfHeader } from './api/csrf'

export type ImportTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export type StudioTelematicoStep = {
  id: string
  label: string
  description: string
}

export type StudioTelematicoImportPage = {
  ok: boolean
  generatedAt: string
  page: {
    title: string
    subtitle: string
    path: string
  }
  permissions: {
    canImport: boolean
    message: string
  }
  steps: StudioTelematicoStep[]
  acceptedFiles: string
  localPathEnabled?: boolean
  actions: {
    refresh: string
    preview: string
    run: string
    helper: string
    fascicoli: string
    clienti: string
  }
  notes: string[]
  contracts: {
    mock_fallback: boolean
    writes: string
    route_owner: string
  }
}

export type StudioTelematicoAnalysis = {
  ok: boolean
  sourceKind: string
  generatedAt: string
  summary: {
    matters: number
    activeMatters: number
    archivedMatters: number
    people: number
    partyLinks: number
    documents: number
    documentFilesFound: number
    documentFilesMissing: number
    emails: number
    emailFilesFound: number
    emailFilesMissing: number
    appointments: number
    availableFiles: number
  }
  samples: {
    missingDocuments: string[]
    missingEmails: string[]
    matters: Array<{
      id: string
      title: string
      object: string
      status: string
    }>
  }
  warnings: Array<{ code: string; message: string }>
  canImportComplete: boolean
}

export type StudioTelematicoPreview = {
  ok: boolean
  importId: string
  sourceName: string
  sourceSha256: string
  createdAt: string
  analysis: StudioTelematicoAnalysis
  errore?: string
}

export type StudioTelematicoImportResult = {
  ok: boolean
  importId: string
  sourceName: string
  generatedAt: string
  summary: {
    clientsCreated: number
    subjectsCreated: number
    partyLinksCreated: number
    mattersCreated: number
    mattersUpdated: number
    documentsImported: number
    documentsMissing: number
    emailsImported: number
    emailsMissing: number
    activitiesImported: number
    duplicatesSkipped: number
  }
  errors: string[]
  warnings: Array<{ code: string; message: string }>
  matters: Array<{ id: string; title: string; href: string }>
  errore?: string
}

export const emptyStudioTelematicoPage: StudioTelematicoImportPage = {
  ok: false,
  generatedAt: '',
  page: {
    title: 'Importa pratiche da Studio Telematico',
    subtitle: 'Acquisizione guidata delle pratiche dal precedente gestionale dello studio.',
    path: '/importa-pratiche-studio-telematico',
  },
  permissions: {
    canImport: false,
    message: '',
  },
  steps: [],
  acceptedFiles: '.zip,.json,.mdb',
  localPathEnabled: false,
  actions: {
    refresh: '/api/v1/ui/import/quickorganizer',
    preview: '/api/v1/ui/import/quickorganizer/anteprima',
    run: '/api/v1/ui/import/quickorganizer/esegui',
    helper: '/static/tools/PreparaPacchettoStudioTelematico.exe',
    fascicoli: '/fascicoli',
    clienti: '/clienti',
  },
  notes: [],
  contracts: {
    mock_fallback: false,
    writes: 'operational_routes',
    route_owner: 'react_shell',
  },
}

export const emptyStudioTelematicoAnalysis: StudioTelematicoAnalysis = {
  ok: false,
  sourceKind: '',
  generatedAt: '',
  summary: {
    matters: 0,
    activeMatters: 0,
    archivedMatters: 0,
    people: 0,
    partyLinks: 0,
    documents: 0,
    documentFilesFound: 0,
    documentFilesMissing: 0,
    emails: 0,
    emailFilesFound: 0,
    emailFilesMissing: 0,
    appointments: 0,
    availableFiles: 0,
  },
  samples: {
    missingDocuments: [],
    missingEmails: [],
    matters: [],
  },
  warnings: [],
  canImportComplete: false,
}

const emptyPreview: StudioTelematicoPreview = {
  ok: false,
  importId: '',
  sourceName: '',
  sourceSha256: '',
  createdAt: '',
  analysis: emptyStudioTelematicoAnalysis,
}

export const emptyStudioTelematicoResult: StudioTelematicoImportResult = {
  ok: false,
  importId: '',
  sourceName: '',
  generatedAt: '',
  summary: {
    clientsCreated: 0,
    subjectsCreated: 0,
    partyLinksCreated: 0,
    mattersCreated: 0,
    mattersUpdated: 0,
    documentsImported: 0,
    documentsMissing: 0,
    emailsImported: 0,
    emailsMissing: 0,
    activitiesImported: 0,
    duplicatesSkipped: 0,
  },
  errors: [],
  warnings: [],
  matters: [],
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function stringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function numberValue(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function boolValue(value: unknown): boolean {
  return value === true
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => stringValue(item)).filter(Boolean) : []
}

function normaliseAnalysis(value: unknown): StudioTelematicoAnalysis {
  const record = isRecord(value) ? value : {}
  const summary = isRecord(record.summary) ? record.summary : {}
  const samples = isRecord(record.samples) ? record.samples : {}
  const matterSamples = Array.isArray(samples.matters) ? samples.matters : []
  return {
    ok: boolValue(record.ok),
    sourceKind: stringValue(record.sourceKind),
    generatedAt: stringValue(record.generatedAt),
    summary: {
      matters: numberValue(summary.matters),
      activeMatters: numberValue(summary.activeMatters),
      archivedMatters: numberValue(summary.archivedMatters),
      people: numberValue(summary.people),
      partyLinks: numberValue(summary.partyLinks),
      documents: numberValue(summary.documents),
      documentFilesFound: numberValue(summary.documentFilesFound),
      documentFilesMissing: numberValue(summary.documentFilesMissing),
      emails: numberValue(summary.emails),
      emailFilesFound: numberValue(summary.emailFilesFound),
      emailFilesMissing: numberValue(summary.emailFilesMissing),
      appointments: numberValue(summary.appointments),
      availableFiles: numberValue(summary.availableFiles),
    },
    samples: {
      missingDocuments: stringArray(samples.missingDocuments),
      missingEmails: stringArray(samples.missingEmails),
      matters: matterSamples.filter(isRecord).map((item) => ({
        id: stringValue(item.id),
        title: stringValue(item.title, 'Pratica senza titolo'),
        object: stringValue(item.object),
        status: stringValue(item.status, 'Da verificare'),
      })),
    },
    warnings: Array.isArray(record.warnings)
      ? record.warnings.filter(isRecord).map((warning) => ({
        code: stringValue(warning.code),
        message: stringValue(warning.message),
      }))
      : [],
    canImportComplete: boolValue(record.canImportComplete),
  }
}

export function formatImportNumber(value: number): string {
  return new Intl.NumberFormat('it-IT').format(value)
}

export function getStudioTelematicoImportPage(signal?: AbortSignal): Promise<StudioTelematicoImportPage> {
  return apiJson<StudioTelematicoImportPage>('/api/v1/ui/import/quickorganizer', emptyStudioTelematicoPage, { signal })
}

export async function previewStudioTelematicoPackage(
  endpoint: string,
  options: { file?: File | null; sourcePath?: string },
): Promise<StudioTelematicoPreview> {
  const file = options.file || null
  const sourcePath = stringValue(options.sourcePath).trim()
  try {
    const isUpload = Boolean(file)
    const body = isUpload ? new FormData() : JSON.stringify({ sourcePath })
    if (file && body instanceof FormData) {
      body.append('pacchetto', file)
    }
    const response = await fetch(endpoint || emptyStudioTelematicoPage.actions.preview, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(isUpload ? {} : { 'Content-Type': 'application/json' }),
        ...csrfHeader(),
      },
      body,
    })
    const raw = await response.json().catch(() => ({}))
    const record = isRecord(raw) ? raw : {}
    return {
      ok: response.ok && boolValue(record.ok),
      importId: stringValue(record.importId),
      sourceName: stringValue(record.sourceName),
      sourceSha256: stringValue(record.sourceSha256),
      createdAt: stringValue(record.createdAt),
      analysis: normaliseAnalysis(record.analysis),
      errore: stringValue(record.errore || record.message),
    }
  } catch {
    return { ...emptyPreview, errore: 'Il pacchetto non è stato caricato.' }
  }
}

export async function runStudioTelematicoImport(
  endpoint: string,
  importId: string,
  allowPartial: boolean,
): Promise<StudioTelematicoImportResult> {
  const raw = await apiPostJson<unknown>(
    endpoint || emptyStudioTelematicoPage.actions.run,
    { importId, allowPartial },
    emptyStudioTelematicoResult,
  )
  const record = isRecord(raw) ? raw : {}
  const summary = isRecord(record.summary) ? record.summary : {}
  const matters = Array.isArray(record.matters) ? record.matters : []
  const warnings = Array.isArray(record.warnings) ? record.warnings : []
  return {
    ok: boolValue(record.ok),
    importId: stringValue(record.importId),
    sourceName: stringValue(record.sourceName),
    generatedAt: stringValue(record.generatedAt),
    summary: {
      clientsCreated: numberValue(summary.clientsCreated),
      subjectsCreated: numberValue(summary.subjectsCreated),
      partyLinksCreated: numberValue(summary.partyLinksCreated),
      mattersCreated: numberValue(summary.mattersCreated),
      mattersUpdated: numberValue(summary.mattersUpdated),
      documentsImported: numberValue(summary.documentsImported),
      documentsMissing: numberValue(summary.documentsMissing),
      emailsImported: numberValue(summary.emailsImported),
      emailsMissing: numberValue(summary.emailsMissing),
      activitiesImported: numberValue(summary.activitiesImported),
      duplicatesSkipped: numberValue(summary.duplicatesSkipped),
    },
    errors: stringArray(record.errors),
    warnings: warnings.filter(isRecord).map((warning) => ({
      code: stringValue(warning.code),
      message: stringValue(warning.message),
    })),
    matters: matters.filter(isRecord).map((matter) => ({
      id: stringValue(matter.id),
      title: stringValue(matter.title, 'Fascicolo importato'),
      href: stringValue(matter.href, '/fascicoli'),
    })),
    errore: stringValue(record.errore || record.message),
  }
}
