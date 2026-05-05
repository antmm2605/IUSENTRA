import type { Tone } from './data'

export type EditorContracts = {
  mock_fallback: boolean
  read_only: boolean
  writes: 'operational_routes' | 'api'
}

export type EditorFascicolo = {
  id: string
  ref: string
  title: string
  client: string
  court: string
  rg: string
  detailHref: string
  quadroHref: string
}

export type EditorDocument = {
  id: string
  name: string
  extension: string
  type: string
  size: string
  uploadedAt: string
  documentDate: string
  notes: string
  tags: string[]
  signed: boolean
  hash: string
  source: string
  editable: boolean
  lockedReason: string
  portal: {
    name: string
    class: string
    sender: string
    date: string
  }
  actions: {
    preview: string
    download: string
    sign: string
    detail: string
  }
}

export type EditorAICurrent = {
  atto_ai_id: string
  status: string
  title: string
  detail: string
  proposeEdits: string
  export: string
}

export type EditorAIEndpointPayload = {
  enabled: boolean
  bootstrap: string
  generate: string
  current: EditorAICurrent | null
  warning: string
}

export type DocumentEditorPayload = {
  source: string
  generatedAt: string
  contracts: EditorContracts
  notFound: boolean
  message: string
  fascicolo: EditorFascicolo
  document: EditorDocument
  endpoints: {
    loadHtml: string
    save: string
    exportPdf: string
    exportDocx: string
  }
  capabilities: {
    formats: string[]
    autosaveSeconds: number
    localBundle: boolean
  }
  editorAI: EditorAIEndpointPayload
  warnings: string[]
}

export type EditorStatusTone = Tone | 'saving' | 'loading'

const emptyContracts: EditorContracts = { mock_fallback: false, read_only: false, writes: 'operational_routes' }
const emptyEditorAI: EditorAIEndpointPayload = {
  enabled: false,
  bootstrap: '',
  generate: '',
  current: null,
  warning: '',
}

export const emptyDocumentEditorPayload: DocumentEditorPayload = {
  source: 'vuoto',
  generatedAt: '',
  contracts: emptyContracts,
  notFound: false,
  message: '',
  fascicolo: {
    id: '',
    ref: '',
    title: '',
    client: '',
    court: '',
    rg: '',
    detailHref: '/fascicoli',
    quadroHref: '/fascicoli',
  },
  document: {
    id: '',
    name: '',
    extension: '',
    type: '',
    size: '',
    uploadedAt: '',
    documentDate: '',
    notes: '',
    tags: [],
    signed: false,
    hash: '',
    source: '',
    editable: true,
    lockedReason: '',
    portal: { name: '', class: '', sender: '', date: '' },
    actions: { preview: '', download: '', sign: '', detail: '/fascicoli' },
  },
  endpoints: { loadHtml: '', save: '', exportPdf: '', exportDocx: '' },
  capabilities: { formats: [], autosaveSeconds: 30, localBundle: true },
  editorAI: emptyEditorAI,
  warnings: [],
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === '1' || value === 1
}

function normalizeContracts(value: unknown): EditorContracts {
  if (!isRecord(value)) return emptyContracts
  return {
    mock_fallback: bool(value.mock_fallback),
    read_only: bool(value.read_only),
    writes: text(value.writes, 'operational_routes') as EditorContracts['writes'],
  }
}

function normalizeFascicolo(value: unknown): EditorFascicolo {
  const row = isRecord(value) ? value : {}
  return {
    id: text(row.id),
    ref: text(row.ref),
    title: text(row.title, 'Fascicolo'),
    client: text(row.client),
    court: text(row.court),
    rg: text(row.rg),
    detailHref: text(row.detailHref, '/fascicoli'),
    quadroHref: text(row.quadroHref, text(row.detailHref, '/fascicoli')),
  }
}

function normalizeDocument(value: unknown): EditorDocument {
  const row = isRecord(value) ? value : {}
  const portal = isRecord(row.portal) ? row.portal : {}
  const actions = isRecord(row.actions) ? row.actions : {}
  return {
    id: text(row.id),
    name: text(row.name, 'Documento'),
    extension: text(row.extension),
    type: text(row.type, 'Documento'),
    size: text(row.size),
    uploadedAt: text(row.uploadedAt),
    documentDate: text(row.documentDate),
    notes: text(row.notes),
    tags: asArray(row.tags).map((item) => text(item)).filter(Boolean),
    signed: bool(row.signed),
    hash: text(row.hash),
    source: text(row.source),
    editable: row.editable !== false,
    lockedReason: text(row.lockedReason),
    portal: {
      name: text(portal.name),
      class: text(portal.class),
      sender: text(portal.sender),
      date: text(portal.date),
    },
    actions: {
      preview: text(actions.preview),
      download: text(actions.download),
      sign: text(actions.sign),
      detail: text(actions.detail, '/fascicoli'),
    },
  }
}

function normalizeEndpoints(value: unknown): DocumentEditorPayload['endpoints'] {
  const row = isRecord(value) ? value : {}
  return {
    loadHtml: text(row.loadHtml),
    save: text(row.save),
    exportPdf: text(row.exportPdf),
    exportDocx: text(row.exportDocx),
  }
}

function normalizeCapabilities(value: unknown): DocumentEditorPayload['capabilities'] {
  const row = isRecord(value) ? value : {}
  return {
    formats: asArray(row.formats).map((item) => text(item)).filter(Boolean),
    autosaveSeconds: Number(row.autosaveSeconds || 30) || 30,
    localBundle: row.localBundle !== false,
  }
}

function normalizeEditorAI(value: unknown): EditorAIEndpointPayload {
  if (!isRecord(value)) return emptyEditorAI
  const current = isRecord(value.current) ? value.current : null
  return {
    enabled: value.enabled !== false,
    bootstrap: text(value.bootstrap),
    generate: text(value.generate),
    current: current
      ? {
        atto_ai_id: text(current.atto_ai_id),
        status: text(current.status),
        title: text(current.title),
        detail: text(current.detail),
        proposeEdits: text(current.proposeEdits),
        export: text(current.export),
      }
      : null,
    warning: text(value.warning),
  }
}

export function normalizeDocumentEditorPayload(payload: unknown): DocumentEditorPayload {
  if (!isRecord(payload)) return emptyDocumentEditorPayload
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt),
    contracts: normalizeContracts(payload.contracts),
    notFound: bool(payload.notFound),
    message: text(payload.message),
    fascicolo: normalizeFascicolo(payload.fascicolo),
    document: normalizeDocument(payload.document),
    endpoints: normalizeEndpoints(payload.endpoints),
    capabilities: normalizeCapabilities(payload.capabilities),
    editorAI: normalizeEditorAI(payload.editorAI),
    warnings: asArray(payload.warnings).map((item) => text(item)).filter(Boolean),
  }
}

export async function getDocumentEditorPayload(idFascicolo: string, idDocumento: string): Promise<DocumentEditorPayload> {
  const query = new URLSearchParams()
  query.set('_ts', String(Date.now()))
  const response = await fetch(
    `/api/v1/ui/fascicoli/${encodeURIComponent(idFascicolo)}/documenti/${encodeURIComponent(idDocumento)}/editor?${query.toString()}`,
    {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    },
  )
  if (!response.ok) return { ...emptyDocumentEditorPayload, notFound: true, message: `Editor non disponibile: HTTP ${response.status}` }
  return normalizeDocumentEditorPayload(await response.json())
}
