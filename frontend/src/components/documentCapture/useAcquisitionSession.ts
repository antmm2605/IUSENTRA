import { useCallback, useEffect, useRef, useState } from 'react'
import { generateDocument, saveGeneratedDocument, type GeneratedDocument } from '../../documentToolsData'
import { recognizeDocument } from '../../services/documentOcr'
import { MAX_CAPTURE_BYTES, MAX_CAPTURE_FILES, type CapturePage } from './captureImages'

export type OcrState = { paragraphs: string[]; characters: number; emptyPages: number }

/**
 * Stato di una sessione di acquisizione: pagine in memoria, PDF da verificare,
 * OCR facoltativo e salvataggio confermato nel fascicolo. Gli URL temporanei
 * vengono sempre rilasciati.
 */
export function useAcquisitionSession() {
  const [pages, setPages] = useState<CapturePage[]>([])
  const [result, setResult] = useState<GeneratedDocument | null>(null)
  const [ocr, setOcr] = useState<OcrState | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const state = useRef({ pages, result })
  const working = useRef(false)
  const alive = useRef(true)
  const abort = useRef<AbortController | null>(null)
  state.current = { pages, result }

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      abort.current?.abort()
      state.current.pages.forEach((page) => URL.revokeObjectURL(page.url))
      if (state.current.result) URL.revokeObjectURL(state.current.result.objectUrl)
    }
  }, [])

  const clearResult = useCallback(() => {
    if (state.current.result) URL.revokeObjectURL(state.current.result.objectUrl)
    setResult(null)
    setOcr(null)
  }, [])

  const perform = useCallback(async (label: string, action: () => Promise<void>) => {
    if (working.current) return
    working.current = true
    setBusy(label)
    setError('')
    try { await action() } catch (cause) {
      if (alive.current) setError(cause instanceof Error ? cause.message : 'Operazione non completata.')
    } finally {
      working.current = false
      if (alive.current) setBusy('')
    }
  }, [])

  const addPage = useCallback((page: CapturePage) => {
    const current = state.current.pages
    if (current.length >= MAX_CAPTURE_FILES) { URL.revokeObjectURL(page.url); setError('Puoi acquisire fino a 80 pagine per documento.'); return }
    if (current.reduce((bytes, item) => bytes + item.file.size, page.file.size) > MAX_CAPTURE_BYTES) {
      URL.revokeObjectURL(page.url)
      setError('Le pagine superano 180 MB. Crea il PDF prima di acquisirne altre.')
      return
    }
    clearResult()
    setPages([...current, page])
    setNotice(`Pagina ${current.length + 1} aggiunta. Non è ancora salvata.`)
  }, [clearResult])

  const editPages = useCallback((next: CapturePage[]) => { clearResult(); setPages(next) }, [clearResult])
  const rotate = (id: string) => editPages(pages.map((page) => (page.id === id ? { ...page, rotation: (page.rotation + 90) % 360 } : page)))
  const remove = (id: string) => {
    const page = pages.find((item) => item.id === id)
    if (page) URL.revokeObjectURL(page.url)
    editPages(pages.filter((item) => item.id !== id))
  }
  const move = (index: number, delta: number) => {
    const target = index + delta
    if (target < 0 || target >= pages.length) return
    const next = [...pages]
    ;[next[index], next[target]] = [next[target], next[index]]
    editPages(next)
  }
  const reset = useCallback(() => {
    abort.current?.abort()
    state.current.pages.forEach((page) => URL.revokeObjectURL(page.url))
    clearResult()
    setPages([])
    setError('')
    setNotice('')
  }, [clearResult])

  const buildPdf = (name: string) => perform('Creazione del PDF…', async () => {
    const current = state.current.pages
    const generated = await generateDocument('multipage', current.map((page) => page.file), name, current.map((page) => page.file.name), current.map((page) => page.rotation), 'a4')
    if (!alive.current) { URL.revokeObjectURL(generated.objectUrl); return }
    clearResult()
    setResult(generated)
    setNotice('PDF pronto: controlla l’anteprima. Puoi anche riconoscere il testo prima di salvarlo.')
  })

  const runOcr = (name: string) => perform('Riconoscimento del testo…', async () => {
    const controller = new AbortController()
    abort.current = controller
    const current = state.current.pages
    const outcome = await recognizeDocument(current, name, (done, total) => { if (alive.current) setBusy(`Riconoscimento del testo: pagina ${Math.min(done + 1, total)} di ${total}…`) }, controller.signal)
    if (!alive.current) { URL.revokeObjectURL(outcome.document.objectUrl); return }
    clearResult()
    setResult(outcome.document)
    setOcr({ paragraphs: outcome.paragraphs, characters: outcome.characters, emptyPages: outcome.emptyPages })
    setNotice(outcome.characters
      ? 'Testo riconosciuto: il PDF ora è ricercabile. Verifica il testo prima di usarlo.'
      : 'Nessun testo riconosciuto: controlla nitidezza e luce delle pagine.')
  })

  const save = (fascicoloId: string, onSaved: (message: string) => void) => perform('Salvataggio nel fascicolo…', async () => {
    const current = state.current.result
    if (!current || !fascicoloId) return
    const message = await saveGeneratedDocument(fascicoloId, current)
    if (!alive.current) return
    reset()
    setNotice(`${current.filename}: ${message}`)
    onSaved(message)
  })

  return { pages, result, ocr, busy, error, notice, setError, addPage, rotate, remove, move, reset, buildPdf, runOcr, save }
}
