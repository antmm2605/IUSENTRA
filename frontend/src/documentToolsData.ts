import { csrfHeader } from './api/csrf'

export type DocumentToolMode = 'merge' | 'zip' | 'multipage'

export type GeneratedDocument = {
  blob: Blob
  filename: string
  objectUrl: string
  pages: number
  files: number
}

type ApiErrorPayload = {
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

export async function generateDocument(
  mode: DocumentToolMode,
  files: File[],
  outputName: string,
  logicalNames: string[],
  rotations: number[],
): Promise<GeneratedDocument> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file, file.name))
  body.append('output_name', outputName)
  logicalNames.forEach((name) => body.append('logical_names', name))
  rotations.forEach((rotation) => body.append('rotations', String(rotation)))

  const response = await fetch(`/api/v1/ui/document-tools/${mode}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/pdf, application/zip, application/json',
      ...csrfHeader(),
    },
    body,
  })
  if (!response.ok) throw new Error(await errorMessage(response))

  const blob = await response.blob()
  const fallback = mode === 'zip' ? 'documenti.zip' : 'documento.pdf'
  return {
    blob,
    filename: filenameFromDisposition(response.headers.get('content-disposition'), fallback),
    objectUrl: URL.createObjectURL(blob),
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
  return payload.message || payload.messaggio || 'Documento salvato nel fascicolo.'
}

