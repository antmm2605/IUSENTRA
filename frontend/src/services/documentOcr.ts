/**
 * Riconoscimento del testo (OCR) delle pagine acquisite, una richiesta per pagina:
 * ogni pagina diventa un PDF con testo ricercabile e le pagine vengono poi unite.
 * Nessun salvataggio: il PDF resta nel browser finché l'avvocato non conferma.
 */
import { csrfHeader } from '../api/csrf'
import { generateDocument, type GeneratedDocument } from '../documentToolsData'

export type OcrSourcePage = { file: File; rotation: number }
export type OcrPage = { pdf: Blob; paragraphs: string[]; characters: number }
export type OcrOutcome = { document: GeneratedDocument; paragraphs: string[]; characters: number; emptyPages: number }

type OcrPayload = { ok?: boolean; pdf_base64?: string; paragraphs?: unknown; characters?: number; message?: string }

export function pdfBlobFromBase64(encoded: string): Blob {
  let binary = ''
  try { binary = atob(String(encoded || '')) } catch { throw new Error('Il documento riconosciuto non è leggibile. Riprova.') }
  if (!binary.startsWith('%PDF-')) throw new Error('Il documento riconosciuto non è un PDF valido. Riprova.')
  return new Blob([Uint8Array.from(binary, (character) => character.charCodeAt(0))], { type: 'application/pdf' })
}

export async function recognizePage(page: OcrSourcePage, signal?: AbortSignal): Promise<OcrPage> {
  const body = new FormData()
  body.append('file', page.file, page.file.name)
  body.append('rotation', String(page.rotation % 360))
  const response = await fetch('/api/v1/ui/document-tools/ocr-page', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...csrfHeader() },
    body,
    signal,
  })
  const payload = await response.json().catch(() => null) as OcrPayload | null
  if (!response.ok || !payload?.ok || !payload.pdf_base64) {
    throw new Error(payload?.message || 'Riconoscimento del testo non completato. Riprova tra qualche istante.')
  }
  const paragraphs = Array.isArray(payload.paragraphs) ? payload.paragraphs.map((item) => String(item || '').trim()).filter(Boolean) : []
  return { pdf: pdfBlobFromBase64(payload.pdf_base64), paragraphs, characters: Number(payload.characters || 0) }
}

function safePdfName(name: string) {
  const stem = String(name || '').replace(/\.[^.]+$/, '').replace(/[\\/:*?"<>|\x00-\x1f]+/g, ' ').replace(/\s+/g, ' ').trim()
  return `${(stem || 'acquisizione').slice(0, 120)}.pdf`
}

/** Pagine riconosciute in ordine; `onProgress` riceve il numero di pagine completate. */
export async function recognizeDocument(pages: OcrSourcePage[], outputName: string, onProgress: (done: number, total: number) => void, signal?: AbortSignal): Promise<OcrOutcome> {
  if (!pages.length) throw new Error('Nessuna pagina da riconoscere.')
  const results: OcrPage[] = []
  onProgress(0, pages.length)
  for (const page of pages) {
    if (signal?.aborted) throw new Error('Riconoscimento del testo annullato.')
    results.push(await recognizePage(page, signal))
    onProgress(results.length, pages.length)
  }
  const filename = safePdfName(outputName)
  let document: GeneratedDocument
  if (results.length === 1) {
    const blob = results[0].pdf
    document = { blob, filename, objectUrl: URL.createObjectURL(blob), pages: 1, files: 1 }
  } else {
    const files = results.map((result, index) => new File([result.pdf], `pagina-${index + 1}.pdf`, { type: 'application/pdf' }))
    document = await generateDocument('merge', files, filename, [], [])
  }
  return {
    document,
    paragraphs: results.flatMap((result) => result.paragraphs),
    characters: results.reduce((sum, result) => sum + result.characters, 0),
    emptyPages: results.filter((result) => !result.characters).length,
  }
}
