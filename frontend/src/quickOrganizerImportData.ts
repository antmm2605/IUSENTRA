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
    uploadStart: string
    uploadChunk: string
    uploadComplete: string
    prepareStart?: string
    run: string
    helper: string
    fascicoli: string
    clienti: string
  }
  upload: {
    directLimitBytes: number
    chunkSizeBytes: number
    maxUploadBytes: number
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

export type StudioTelematicoPrepareStatus = {
  ok: boolean
  sessionId: string
  status: string
  progress: number
  detail: string
  downloadUrl: string
  statusUrl: string
  expiresAt: string
  canAutoUpload: boolean
  preview: StudioTelematicoPreview | null
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
    uploadStart: '/api/v1/ui/import/quickorganizer/upload-session',
    uploadChunk: '/api/v1/ui/import/quickorganizer/upload-session/{uploadId}/chunk',
    uploadComplete: '/api/v1/ui/import/quickorganizer/upload-session/{uploadId}/completa',
    prepareStart: '/api/v1/ui/import/quickorganizer/preparazione',
    run: '/api/v1/ui/import/quickorganizer/esegui',
    helper: '/static/tools/PreparaPacchettoStudioTelematico.exe',
    fascicoli: '/fascicoli',
    clienti: '/clienti',
  },
  upload: {
    directLimitBytes: 150 * 1024 * 1024,
    chunkSizeBytes: 64 * 1024 * 1024,
    maxUploadBytes: 30 * 1024 * 1024 * 1024,
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

type ChunkedUploadOptions = {
  startEndpoint: string
  chunkEndpoint: string
  completeEndpoint: string
  chunkSizeBytes: number
  onProgress?: (progress: { value: number; detail: string }) => void
}

function uploadUrl(template: string, uploadId: string): string {
  return template.replace('{uploadId}', encodeURIComponent(uploadId))
}

async function jsonFromResponse(response: Response): Promise<Record<string, unknown>> {
  const raw = await response.json().catch(() => ({}))
  return isRecord(raw) ? raw : {}
}

function normalisePreviewRecord(record: Record<string, unknown>, responseOk: boolean): StudioTelematicoPreview {
  return {
    ok: responseOk && boolValue(record.ok),
    importId: stringValue(record.importId),
    sourceName: stringValue(record.sourceName),
    sourceSha256: stringValue(record.sourceSha256),
    createdAt: stringValue(record.createdAt),
    analysis: normaliseAnalysis(record.analysis),
    errore: stringValue(record.errore || record.message),
  }
}

function normalisePreviewResponse(response: Response, record: Record<string, unknown>): StudioTelematicoPreview {
  return normalisePreviewRecord(record, response.ok)
}

function normalisePrepareStatus(record: Record<string, unknown>): StudioTelematicoPrepareStatus {
  const previewRecord = isRecord(record.preview) ? record.preview : isRecord(record.stage) ? record.stage : null
  return {
    ok: boolValue(record.ok),
    sessionId: stringValue(record.sessionId),
    status: stringValue(record.status, 'pending'),
    progress: Math.max(0, Math.min(100, numberValue(record.progress))),
    detail: stringValue(record.detail),
    downloadUrl: stringValue(record.downloadUrl),
    statusUrl: stringValue(record.statusUrl),
    expiresAt: stringValue(record.expiresAt),
    canAutoUpload: boolValue(record.canAutoUpload),
    preview: previewRecord ? normalisePreviewRecord(previewRecord, true) : null,
    errore: stringValue(record.errore || record.message),
  }
}

export async function startStudioTelematicoAutoPrepare(endpoint: string): Promise<StudioTelematicoPrepareStatus> {
  const response = await fetch(endpoint || emptyStudioTelematicoPage.actions.prepareStart || '', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...csrfHeader(),
    },
    body: JSON.stringify({}),
  })
  const raw = await jsonFromResponse(response)
  const status = normalisePrepareStatus(raw)
  return {
    ...status,
    ok: response.ok && status.ok,
    errore: response.ok ? status.errore : status.errore || 'Preparazione pacchetto non avviata.',
  }
}

export async function getStudioTelematicoAutoPrepareStatus(
  statusUrl: string,
  signal?: AbortSignal,
): Promise<StudioTelematicoPrepareStatus> {
  const response = await fetch(statusUrl, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })
  const raw = await jsonFromResponse(response)
  const status = normalisePrepareStatus(raw)
  return {
    ...status,
    ok: response.ok && status.ok,
    errore: response.ok ? status.errore : status.errore || 'Stato preparazione non disponibile.',
  }
}

async function previewChunkedPackage(file: File, options: ChunkedUploadOptions): Promise<StudioTelematicoPreview> {
  const startResponse = await fetch(options.startEndpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...csrfHeader(),
    },
    body: JSON.stringify({ filename: file.name, totalSize: file.size }),
  })
  const startRaw = await jsonFromResponse(startResponse)
  if (!startResponse.ok || !boolValue(startRaw.ok)) {
    return { ...emptyPreview, errore: stringValue(startRaw.errore || startRaw.message, 'Caricamento a blocchi non avviato.') }
  }
  const uploadId = stringValue(startRaw.uploadId)
  const chunkSize = Math.max(1, numberValue(startRaw.chunkSizeBytes) || options.chunkSizeBytes)
  const totalChunks = Math.max(1, numberValue(startRaw.totalChunks) || Math.ceil(file.size / chunkSize))
  for (let index = 0; index < totalChunks; index += 1) {
    const start = index * chunkSize
    const end = Math.min(file.size, start + chunkSize)
    const body = new FormData()
    body.append('chunk', file.slice(start, end), file.name)
    body.append('index', String(index))
    body.append('totalChunks', String(totalChunks))
    const chunkResponse = await fetch(uploadUrl(options.chunkEndpoint, uploadId), {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...csrfHeader(),
      },
      body,
    })
    const chunkRaw = await jsonFromResponse(chunkResponse)
    if (!chunkResponse.ok || !boolValue(chunkRaw.ok)) {
      return { ...emptyPreview, errore: stringValue(chunkRaw.errore || chunkRaw.message, 'Caricamento del pacchetto interrotto.') }
    }
    options.onProgress?.({
      value: Math.min(90, 10 + Math.round(((index + 1) / totalChunks) * 75)),
      detail: `Caricati ${index + 1} blocchi su ${totalChunks}`,
    })
  }
  options.onProgress?.({ value: 92, detail: 'Ricomposizione e controllo del pacchetto nello studio' })
  const completeResponse = await fetch(uploadUrl(options.completeEndpoint, uploadId), {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...csrfHeader(),
    },
    body: JSON.stringify({ totalChunks }),
  })
  const completeRaw = await jsonFromResponse(completeResponse)
  return normalisePreviewResponse(completeResponse, completeRaw)
}

export async function previewStudioTelematicoPackage(
  endpoint: string,
  options: { file?: File | null; sourcePath?: string; chunked?: ChunkedUploadOptions },
): Promise<StudioTelematicoPreview> {
  const file = options.file || null
  const sourcePath = stringValue(options.sourcePath).trim()
  try {
    if (file && options.chunked) {
      return previewChunkedPackage(file, options.chunked)
    }
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
    return normalisePreviewResponse(response, await jsonFromResponse(response))
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
