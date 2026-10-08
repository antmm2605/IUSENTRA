import { csrfHeader } from './api/csrf'

export type DocumentToolMode = 'merge' | 'zip' | 'multipage' | 'split' | 'word'

export type GeneratedDocument = {
  blob: Blob
  filename: string
  objectUrl: string
  pages: number
  files: number
  previewHref?: string
  downloadHref?: string
  expiresAt?: number
}

type ApiErrorPayload = {
  ok?: boolean
  documento_id?: string
  message?: string
  messaggio?: string
}

function filenameFromDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback
  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return encoded
    }
  }
  const plain = value.match(/filename="?([^";]+)"?/i)?.[1]
  return plain?.trim() || fallback
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = await response.json() as ApiErrorPayload
    return payload.message || payload.messaggio || 'Operazione non completata.'
  } catch {
    return 'Operazione non completata. Riprova tra pochi secondi.'
  }
}

export async function previewUploadedPdf(file: File, signal?: AbortSignal): Promise<{ href: string; expiresAt: number }> {
  const body = new FormData()
  body.append('files', file, file.name)
  const response = await fetch('/api/v1/ui/document-tools/preview', {
    method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', ...csrfHeader() }, body, signal,
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  const payload = await response.json() as { ok?: boolean; previewHref?: string; expiresAt?: number }
  if (!payload.ok || !payload.previewHref?.startsWith('/api/v1/ui/document-tools/results/') || payload.previewHref.includes('\\') || !Number.isFinite(payload.expiresAt)) {
    throw new Error('Anteprima non ricevuta. Verifica l’accesso a IUSENTRA e riprova.')
  }
  return { href: payload.previewHref, expiresAt: payload.expiresAt! }
}

export async function generateDocument(
  mode: DocumentToolMode,
  files: File[],
  outputName: string,
  logicalNames: string[],
  rotations: number[],
  pageFormat: '' | 'a4' = '',
  pages = '',
  review?: string,
): Promise<GeneratedDocument> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file, file.name))
  body.append('output_name', outputName)
  if (mode === 'word' && review) body.append('review', review)
  if (mode === 'split') body.append('pages', pages)
  if (pageFormat) body.append('page_format', pageFormat)
  logicalNames.forEach((name) => body.append('logical_names', name))
  rotations.forEach((rotation) => body.append('rotations', String(rotation)))

  const response = await fetch(`/api/v1/ui/document-tools/${mode}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/pdf, application/zip, application/vnd.openxmlformats-officedocument.wordprocessingml.document, application/json',
      ...csrfHeader(),
      'X-Iusentra-Result-Links': '1',
    },
    body,
  })
  if (!response.ok) throw new Error(await errorMessage(response))

  const expectedType = mode === 'word' ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' : mode === 'zip' ? 'application/zip' : 'application/pdf'
  if (!response.headers.get('content-type')?.toLowerCase().startsWith(expectedType)) throw new Error('Documento non ricevuto. Verifica l’accesso a IUSENTRA e riprova.')

  const downloadHref = response.headers.get('x-iusentra-download') || ''
  const previewHref = response.headers.get('x-iusentra-preview') || undefined
  const internalResult = (href: string) => href.startsWith('/api/v1/ui/document-tools/results/') && !href.includes('\\')
  if (!internalResult(downloadHref) || (previewHref && !internalResult(previewHref))) throw new Error('I collegamenti alla copia generata non sono disponibili. Riprova.')
  const blob = await response.blob()
  if (!blob.size) throw new Error('Il documento preparato è vuoto e non può essere salvato.')
  const fallback = mode === 'word' ? 'documento.docx' : mode === 'zip' ? 'documenti.zip' : 'documento.pdf'
  return {
    blob,
    filename: filenameFromDisposition(response.headers.get('content-disposition'), fallback),
    objectUrl: URL.createObjectURL(blob),
    expiresAt: Number(response.headers.get('x-iusentra-expires') || 0) * 1000 || undefined,
    downloadHref,
    previewHref,
    pages: Number(response.headers.get('x-iusentra-pages') || 0),
    files: Number(response.headers.get('x-iusentra-files') || files.length),
  }
}

export async function saveGeneratedDocument(fascicoloId: string, result: GeneratedDocument): Promise<string> {
  const body = new FormData()
  body.append('files', result.blob, result.filename)
  body.append('classificazione_modalita', 'automatica')
  const response = await fetch(`/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/carica`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...csrfHeader(),
    },
    body,
  })
  if (!response.ok) throw new Error(await errorMessage(response))
  const payload = await response.json() as ApiErrorPayload
  if (payload.ok !== true || !payload.documento_id) throw new Error(payload.message || payload.messaggio || 'Salvataggio non confermato. Controlla i documenti del fascicolo prima di riprovare.')
  return payload.message || payload.messaggio || 'Documento salvato nel fascicolo.'
}
