export type DocumentAIStatus =
  | 'uploaded'
  | 'processing'
  | 'ready'
  | 'error'
  | 'archived'

export type DocumentAIFileType = 'pdf' | 'docx' | 'doc' | 'txt' | 'eml'

export type DocumentAIRecord = {
  id: string
  original_filename: string
  safe_filename: string
  file_type: DocumentAIFileType
  mime_type: string | null
  size_bytes: number
  sha256: string
  status: DocumentAIStatus
  current_version_id: string | null
  page_count: number | null
  created_by: string
  created_at: string
  updated_at: string
}

export type DocumentAIVersion = {
  id: string
  version_number: number
  source: string
  sha256: string
  created_at: string
}

export type DocumentAIListPayload = {
  mock_fallback: false
  fascicolo_id: string
  documents: DocumentAIRecord[]
  capabilities: {
    upload: boolean
    read: boolean
    search: boolean
    lex_tools: boolean
    generate_docx: boolean
    propose_edits: boolean
    compare: boolean
  }
}

export type DocumentAIDetailPayload = {
  mock_fallback: false
  document: DocumentAIRecord
  versions: DocumentAIVersion[]
  audit_summary: {
    last_event: string | null
    last_event_at: string | null
  }
}

export type DocumentAIUploadPayload = {
  mock_fallback: false
  document: DocumentAIRecord
  version: DocumentAIVersion | null
  extraction: {
    status: 'completed' | 'failed'
    engine: string
    page_count: number | null
    warnings: string[]
  }
}

export type DocumentAITextPayload = {
  mock_fallback: false
  document_id: string
  version_id: string
  status: 'ready'
  extraction_engine: string
  page_count: number | null
  text: string
  pages: Array<{
    page_number: number
    text: string
  }>
  warnings: string[]
}

export type DocumentAISearchPayload = {
  mock_fallback: false
  document_id: string
  query: string
  results: Array<{
    page_number: number | null
    snippet: string
    start_offset: number | null
    end_offset: number | null
  }>
}

export type LegalDocumentRecord = {
  id: string
  tenant_id: string
  fascicolo_id: string | null
  parent_document_id: string | null
  root_document_id: string
  source_type: string
  source_message_id: string | null
  original_filename: string
  normalized_filename: string
  mime_type: string
  extension: string
  sha256: string
  file_size: number
  status: string
  security_status: string
  processing_status: string
  created_at: string
  updated_at: string
}

export type LegalDocumentEvidence = {
  document: LegalDocumentRecord | null
  files: Array<Record<string, unknown>>
  classification: Record<string, unknown> | null
  entities: Array<Record<string, unknown>>
  validation: Record<string, unknown> | null
  case_match: Record<string, unknown> | null
  events: Array<Record<string, unknown>>
  lex_index: Record<string, unknown> | null
  audit: Array<Record<string, unknown>>
  hash_chain: Array<Record<string, unknown>>
}

export type LegalDocumentTree = {
  document: LegalDocumentRecord | null
  children: Array<{
    link: Record<string, unknown>
    document: LegalDocumentRecord | null
    children: LegalDocumentTree['children']
  }>
}

export type LegalDocumentListPayload = {
  ok: boolean
  data: LegalDocumentRecord[]
  count: number
}

export type LegalDocumentEvidencePayload = {
  ok: boolean
  data: LegalDocumentEvidence
}

export type LegalDocumentTreePayload = {
  ok: boolean
  data: LegalDocumentTree
}

export type LegalOcrReview = {
  run_id: string
  document_id: string
  metrics: Record<string, unknown>
  qc: Record<string, unknown>
  engine_version: Record<string, unknown>
  mandatory_fields: Array<Record<string, unknown>>
  low_tokens: Array<{
    token: string
    confidence: number
    bbox: unknown
    page: number
    line_id: string
  }>
  suggested_fixes: Array<Record<string, string>>
  correction_history: Array<Record<string, unknown>>
  lex_export: Record<string, unknown>
}

export type LegalOcrReviewPayload = {
  ok: boolean
  data: LegalOcrReview | Record<string, never>
}

export type LegalDocumentUploadPayload = {
  ok: boolean
  data: Array<{
    document: LegalDocumentRecord | null
    children: Array<Record<string, unknown>>
    blocked: Array<Record<string, unknown>>
    processed: Array<Record<string, unknown>>
  }>
  count: number
}

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function readApiError(response: Response): Promise<string> {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const payload = await response.json().catch(() => ({}))
    return String(payload.detail || payload.errore || payload.error || 'Operazione non completata.')
  }
  return response.text().catch(() => 'Operazione non completata.')
}

async function jsonRequest<T>(url: string, init: RequestInit = {}): Promise<T> {
  const method = String(init.method || 'GET').toUpperCase()
  const response = await fetch(url, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...init,
    headers: {
      Accept: 'application/json',
      ...(method === 'GET' ? {} : { 'X-CSRF-Token': csrfToken() }),
      ...(init.headers || {}),
    },
  })
  if (!response.ok) throw new Error(await readApiError(response))
  return response.json() as Promise<T>
}

export function fetchDocumentAIList(fascicoloId: string): Promise<DocumentAIListPayload> {
  return jsonRequest<DocumentAIListPayload>(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai`)
}

export function fetchDocumentAIDetail(fascicoloId: string, documentId: string): Promise<DocumentAIDetailPayload> {
  return jsonRequest<DocumentAIDetailPayload>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai/${encodeURIComponent(documentId)}`,
  )
}

export function fetchDocumentAIText(fascicoloId: string, documentId: string): Promise<DocumentAITextPayload> {
  return jsonRequest<DocumentAITextPayload>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai/${encodeURIComponent(documentId)}/testo`,
  )
}

export function searchDocumentAI(
  fascicoloId: string,
  documentId: string,
  query: string,
  maxResults = 20,
): Promise<DocumentAISearchPayload> {
  return jsonRequest<DocumentAISearchPayload>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai/${encodeURIComponent(documentId)}/cerca`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, max_results: maxResults }),
    },
  )
}

export function uploadDocumentAI(fascicoloId: string, file: File): Promise<DocumentAIUploadPayload> {
  const form = new FormData()
  form.append('file', file)
  return jsonRequest<DocumentAIUploadPayload>(
    `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai/upload`,
    {
      method: 'POST',
      body: form,
    },
  )
}

export function fetchLegalDocuments(fascicoloId: string): Promise<LegalDocumentListPayload> {
  const params = new URLSearchParams()
  if (fascicoloId) params.set('fascicolo_id', fascicoloId)
  return jsonRequest<LegalDocumentListPayload>(`/api/documents?${params.toString()}`)
}

export function fetchLegalDocumentEvidence(documentId: string): Promise<LegalDocumentEvidencePayload> {
  return jsonRequest<LegalDocumentEvidencePayload>(`/api/documents/${encodeURIComponent(documentId)}/evidence`)
}

export function fetchLegalDocumentTree(documentId: string): Promise<LegalDocumentTreePayload> {
  return jsonRequest<LegalDocumentTreePayload>(`/api/documents/${encodeURIComponent(documentId)}/archive-tree`)
}

export function fetchLegalOcrReview(documentId: string): Promise<LegalOcrReviewPayload> {
  return jsonRequest<LegalOcrReviewPayload>(`/api/documents/${encodeURIComponent(documentId)}/ocr-legal-review`)
}

export function uploadLegalDocument(fascicoloId: string, file: File): Promise<LegalDocumentUploadPayload> {
  const form = new FormData()
  form.append('file', file)
  if (fascicoloId) form.append('fascicolo_id', fascicoloId)
  return jsonRequest<LegalDocumentUploadPayload>('/api/documents/upload', {
    method: 'POST',
    body: form,
  })
}

export function approveLegalDocument(documentId: string): Promise<{ok: boolean; data: Record<string, unknown>}> {
  return jsonRequest<{ok: boolean; data: Record<string, unknown>}>(`/api/documents/${encodeURIComponent(documentId)}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'validated', motivo: 'Revisione umana completata' }),
  })
}

export function requestLegalDocumentLexIndex(documentId: string): Promise<{ok: boolean; data: Record<string, unknown>}> {
  return jsonRequest<{ok: boolean; data: Record<string, unknown>}>(`/api/documents/${encodeURIComponent(documentId)}/lex-index`, {
    method: 'POST',
  })
}

export function requestFascicoloLexIndex(fascicoloId: string): Promise<{ok: boolean; data: Record<string, unknown>}> {
  return jsonRequest<{ok: boolean; data: Record<string, unknown>}>(`/api/documents/fascicoli/${encodeURIComponent(fascicoloId)}/lex-index`, {
    method: 'POST',
  })
}

export function applyLegalOcrFix(
  documentId: string,
  fix: Record<string, string>,
): Promise<{ok: boolean; data: {review: LegalOcrReview}}> {
  return jsonRequest<{ok: boolean; data: {review: LegalOcrReview}}>(`/api/documents/${encodeURIComponent(documentId)}/ocr-legal-review/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fix }),
  })
}

export function createLegalDocumentProofBundle(documentId: string): Promise<{ok: boolean; data: Record<string, unknown>}> {
  return jsonRequest<{ok: boolean; data: Record<string, unknown>}>(`/api/documents/${encodeURIComponent(documentId)}/proof-bundle`, {
    method: 'POST',
  })
}

export function formatDocumentAISize(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = sizeBytes
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: index ? 1 : 0 }).format(value)} ${units[index]}`
}

export function formatDocumentAIDate(value: string): string {
  if (!value) return 'n.d.'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(parsed)
}

export function shortSha(value: string): string {
  return value ? value.slice(0, 12) : 'n.d.'
}
