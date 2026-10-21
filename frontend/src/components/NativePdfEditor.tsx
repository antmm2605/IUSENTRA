import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { LoadingState } from '../ui/LoadingState'
import { csrfToken } from '../formSubmit'
import { PDF_EDITOR_ASSET_BASE } from '../pdfEditorRelease'
import './NativePdfEditor.css'

type Props = {
  endpoint: string
  filename: string
  expectedHash: string
  onDirty: (dirty: boolean) => void
  onSaving: (saving: boolean) => void
  onSaved: () => void
  onClose: () => void
}
type PcFont = { family: string; style: string; fullName: string; blob: () => Promise<Blob> }
type FontCheck = { family: string; style: string; ok: boolean; reason?: string }

export default function NativePdfEditor({ endpoint, filename, expectedHash, onDirty, onSaving, onSaved, onClose }: Props) {
  const section = useRef<HTMLElement>(null)
  const iframe = useRef<HTMLIFrameElement>(null)
  useLayoutEffect(() => {
    const container = section.current?.parentElement
    if (!container) return
    const previous = container.scrollTop
    container.scrollTop = 0
    return () => { container.scrollTop = previous }
  }, [])
  const token = useRef(crypto.randomUUID())
  const revision = useRef(expectedHash)
  const intent = useRef<{ hash: string; command: string } | null>(null)
  const dirty = useRef(false)
  const busy = useRef(false)
  const pcFonts = useRef(new Map<string, PcFont>())
  const handlers = useRef({ onDirty, onSaving, onSaved, onClose })
  handlers.current = { onDirty, onSaving, onSaved, onClose }
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [displayName, setDisplayName] = useState(filename)
  const [attempt, setAttempt] = useState(0)
  const [fontBusy, setFontBusy] = useState(false)
  const [fontCount, setFontCount] = useState(0)
  const [verifyingFonts, setVerifyingFonts] = useState(false)
  const [fontChecks, setFontChecks] = useState<FontCheck[] | null>(null)

  const loadPcFontCatalog = async () => {
    const query = (window as Window & { queryLocalFonts?: () => Promise<PcFont[]> }).queryLocalFonts
    if (!query) { setError('Questo browser non espone l’elenco dei caratteri installati. Apri IUSENTRA in Google Chrome o Microsoft Edge per caricarli tutti.'); return }
    setFontBusy(true)
    try {
      const fonts = await query.call(window)
      pcFonts.current.clear()
      const entries = fonts.map(font => {
        const id = crypto.randomUUID()
        pcFonts.current.set(id, font)
        return { id, family: font.family, style: font.style, fullName: font.fullName }
      })
      setFontCount(entries.length); setFontChecks(null)
      iframe.current?.contentWindow?.postMessage({ type: 'IUSENTRA_PDF_FONT_CATALOG', token: token.current, entries }, '*')
      setError('')
      setMessage(`${new Set(fonts.map(font => font.family)).size} famiglie di caratteri del PC disponibili nel menu Carattere.`)
    } catch {
      setError('Accesso ai caratteri del PC non consentito. Consenti l’accesso nel browser e riprova.')
    } finally { setFontBusy(false) }
  }

  const loadFonts = async (files: FileList | null) => {
    if (!files?.length) return
    setFontBusy(true)
    try {
      if (files.length > 10 || Array.from(files).reduce((sum, file) => sum + file.size, 0) > 40 * 1024 * 1024) {
        throw new Error('Scegli fino a 10 caratteri, entro 40 MiB complessivi.')
      }
      const fonts: { name: string; buffer: ArrayBuffer }[] = []
      for (const file of Array.from(files)) {
        if (!/\.(ttf|otf)$/i.test(file.name) || file.size > 40 * 1024 * 1024) {
          throw new Error('Scegli file TTF o OTF fino a 40 MiB ciascuno.')
        }
        fonts.push({ name: file.name, buffer: await file.arrayBuffer() })
      }
      iframe.current?.contentWindow?.postMessage({ type: 'IUSENTRA_PDF_FONTS', token: token.current, fonts }, '*', fonts.map(font => font.buffer))
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Caricamento caratteri non riuscito.')
    } finally { setFontBusy(false) }
  }
  const loadImage = async (file?: File) => {
    if (!file) return
    try {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 32 * 1024 * 1024) throw new Error('Scegli un’immagine PNG, JPEG o WebP entro 32 MiB.')
      const buffer = await file.arrayBuffer()
      iframe.current?.contentWindow?.postMessage({ type: 'IUSENTRA_PDF_IMAGE', token: token.current, buffer, name: file.name, mime: file.type }, '*', [buffer])
      setError('')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Immagine non caricata.') }
  }

  useEffect(() => {
    const controller = new AbortController()
    let requested = false
    const openingTimeout = window.setTimeout(() => {
      if (!requested) { setLoading(false); setError('L’editor PDF locale non ha risposto. Riprova l’apertura.'); }
    }, 30000)
    const send = (type: string, payload: object = {}, transfer: Transferable[] = []) =>
      iframe.current?.contentWindow?.postMessage({ type, token: token.current, ...payload }, '*', transfer)
    const close = () => {
      if (busy.current) { setError('Attendi la conferma del salvataggio prima di chiudere.'); return }
      if (!dirty.current || window.confirm('Chiudere senza salvare le modifiche al PDF?')) {
        handlers.current.onDirty(false); handlers.current.onClose()
      }
    }
    const receive = async (event: MessageEvent) => {
      if (event.source !== iframe.current?.contentWindow || event.data?.token !== token.current) return
      const data = event.data
      if (data.type === 'IUSENTRA_PDF_FONT_BYTES') {
        try {
          const font = pcFonts.current.get(String(data.fontId))
          if (!font || typeof data.id !== 'string') throw new Error('Carattere non autorizzato.')
          const blob = await font.blob()
          if (blob.size > 40 * 1024 * 1024) throw new Error('Il carattere supera 40 MiB.')
          const buffer = await blob.arrayBuffer()
          send('IUSENTRA_PDF_FONT_BYTES_RESULT', { id: data.id, ok: true, buffer }, [buffer])
        } catch {
          send('IUSENTRA_PDF_FONT_BYTES_RESULT', { id: data.id, ok: false })
        }
      } else if (data.type === 'IUSENTRA_PDF_READY' && !requested) {
        requested = true
        window.clearTimeout(openingTimeout)
        try {
          const response = await fetch(endpoint, {
            credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
          })
          if (!response.ok) {
            const result = await response.json()
            throw new Error(result.message || 'Il PDF non è disponibile.')
          }
          const currentRevision = response.headers.get('X-PDF-Revision') || ''
          if (!/^[0-9a-f]{64}$/.test(currentRevision)) throw new Error('Revisione del PDF non verificabile. Riprova apertura.')
          const buffer = await response.arrayBuffer()
          if (controller.signal.aborted) return
          revision.current = currentRevision
          intent.current = null
          const name = decodeURIComponent(response.headers.get('X-PDF-Name') || encodeURIComponent(filename))
          setDisplayName(name)
          send('IUSENTRA_PDF_LOAD', { name, buffer }, [buffer])
        } catch (failure) {
          if (!controller.signal.aborted) { setLoading(false); setError(failure instanceof Error ? failure.message : 'Apertura PDF non riuscita.') }
        }
      } else if (data.type === 'IUSENTRA_PDF_LOADED') {
        setLoading(false); setError('')
      } else if (data.type === 'IUSENTRA_PDF_ERROR') {
        setLoading(false); setError(String(data.message || 'Apertura PDF non riuscita.'))
      } else if (data.type === 'IUSENTRA_PDF_DIRTY') {
        dirty.current = Boolean(data.dirty); handlers.current.onDirty(dirty.current)
        if (dirty.current) setMessage('Modifiche da salvare')
      } else if (data.type === 'IUSENTRA_PDF_FONTS_RESULT') {
        if (data.imported > 0) { setError(''); setMessage(`${data.imported} caratteri caricati. Seleziona il testo e scegli il carattere dal menu Carattere.`) }
        else setError('Nessun carattere caricato. Scegli file TTF o OTF validi.')
      } else if (data.type === 'IUSENTRA_PDF_STATUS') {
        setMessage(String(data.message || ''))
      } else if (data.type === 'IUSENTRA_PDF_FONT_VERIFY_PROGRESS') {
        setMessage(`Verifica dei caratteri sul PC: ${data.tested} di ${data.total}.`)
      } else if (data.type === 'IUSENTRA_PDF_FONT_VERIFY_RESULT' && Array.isArray(data.results)) {
        setVerifyingFonts(false); setFontChecks(data.results)
        setMessage(data.cancelled ? `Verifica interrotta: ${data.results.length} di ${data.total} caratteri controllati.` : `Verifica terminata: ${data.results.length} caratteri controllati sul PC.`)
      } else if (data.type === 'IUSENTRA_PDF_EXIT') {
        close()
      } else if (data.type === 'IUSENTRA_PDF_SAVE') {
        if (busy.current || !(data.buffer instanceof ArrayBuffer) || typeof data.id !== 'string') return
        busy.current = true; handlers.current.onSaving(true); setError(''); setMessage('Salvataggio nel fascicolo…')
        try {
          if (data.buffer.byteLength > 64 * 1024 * 1024) throw new Error('Il PDF supera il limite di 64 MiB.')
          const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data.buffer)), value => value.toString(16).padStart(2, '0')).join('')
          if (!intent.current || intent.current.hash !== hash) intent.current = { hash, command: crypto.randomUUID() }
          const body = new FormData()
          body.set('file', new Blob([data.buffer], { type: 'application/pdf' }), filename)
          body.set('expectedHash', revision.current)
          body.set('commandId', intent.current.command)
          const response = await fetch(endpoint, { method: 'POST', credentials: 'same-origin', body,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken() }, signal: controller.signal })
          const result = await response.json()
          if (!response.ok || !result.ok) throw new Error(result.message || 'Salvataggio non confermato.')
          revision.current = result.hash
          intent.current = null; dirty.current = false
          handlers.current.onDirty(false); handlers.current.onSaved()
          setMessage(result.message)
          send('IUSENTRA_PDF_SAVE_RESULT', { id: data.id, ok: true })
        } catch (failure) {
          const text = failure instanceof Error ? failure.message : 'Salvataggio non confermato. Le modifiche restano aperte.'
          setError(text); setMessage('Modifiche da salvare')
          send('IUSENTRA_PDF_SAVE_RESULT', { id: data.id, ok: false, message: text })
        } finally {
          busy.current = false; handlers.current.onSaving(false)
        }
      }
    }
    const exit = () => close()
    window.addEventListener('message', receive)
    const frame = iframe.current
    frame?.addEventListener('iusentra-close-pdf', exit)
    return () => { window.clearTimeout(openingTimeout); controller.abort(); window.removeEventListener('message', receive); frame?.removeEventListener('iusentra-close-pdf', exit) }
  }, [endpoint, filename, attempt])

  return <section ref={section} className="iu-native-pdf" aria-label="Editor PDF">

    <header><strong>{displayName}</strong><button type="button" disabled={loading || fontBusy} onClick={() => { void loadPcFontCatalog() }}>{fontBusy ? 'Lettura caratteri…' : 'Tutti i caratteri del PC'}</button><label className="iu-native-pdf__fonts">Da file<input type="file" aria-label="Carica file caratteri dal PC" accept=".ttf,.otf" multiple disabled={loading || fontBusy} onChange={event => { void loadFonts(event.currentTarget.files); event.currentTarget.value = '' }} /></label><label className="iu-native-pdf__fonts">Immagine<input type="file" aria-label="Inserisci immagine dal PC" accept="image/png,image/jpeg,image/webp" disabled={loading} onChange={event => { void loadImage(event.currentTarget.files?.[0]); event.currentTarget.value = '' }} /></label><button type="button" onClick={() => iframe.current?.dispatchEvent(new Event('iusentra-close-pdf'))}>Torna al lettore</button><button className="iu-native-pdf__fullscreen" type="button" title="Apri o chiudi l’editor a tutto schermo" aria-label="Editor a tutto schermo" onClick={event => {
      const section=event.currentTarget.closest('section')
      const operation=document.fullscreenElement ? document.exitFullscreen() : section?.requestFullscreen()
      void operation?.catch(() => setError('Il browser non consente la visualizzazione a tutto schermo.'))
    }}>⛶</button></header>
    {error ? <p role="alert">{error}</p> : message ? <p role="status">{message}</p> : null}
    {fontCount > 0 ? <div className="iu-native-pdf__font-checks">
      <button type="button" disabled={verifyingFonts || loading} onClick={() => { setVerifyingFonts(true); setFontChecks(null); iframe.current?.contentWindow?.postMessage({ type: 'IUSENTRA_PDF_VERIFY_FONTS', token: token.current }, '*') }}>Verifica tutti i caratteri</button>
      {verifyingFonts ? <button type="button" onClick={() => iframe.current?.contentWindow?.postMessage({ type: 'IUSENTRA_PDF_CANCEL_FONT_VERIFY', token: token.current }, '*')}>Interrompi verifica</button> : null}
      {fontChecks ? <details><summary>{fontChecks.filter(font => font.ok).length} compatibili su {fontChecks.length} verificati — dettagli</summary>
        <p>Ogni variante viene letta dal PC, provata nel browser e nel motore PDF, salvata e riaperta in memoria. Il confronto riguarda un campione; non certifica tutti i simboli o tutti i documenti. Nessun documento del fascicolo viene modificato.</p>
        <ul>{fontChecks.map((font, index) => <li key={index}>{font.family} · {font.style}: {font.ok ? 'campione visualizzato e conservato dopo il salvataggio' : font.reason || 'non utilizzabile nel campione PDF'}</li>)}</ul>
      </details> : null}
    </div> : null}
    {error && !dirty.current && !busy.current ? <button type="button" onClick={() => { token.current = crypto.randomUUID(); setError(''); setLoading(true); setAttempt(value => value + 1) }}>Riprova apertura</button> : null}
    <div className="iu-native-pdf__canvas">
      {loading ? <LoadingState title="Apertura del PDF" message="Preparazione del documento modificabile" /> : null}
      <iframe key={attempt} ref={iframe} title={`Modifica PDF ${filename}`} sandbox="allow-scripts"
        src={`${PDF_EDITOR_ASSET_BASE}/index.html?lang=it#host_token=${encodeURIComponent(token.current)}`} />
    </div>
    <footer><details><summary>Informazioni editor PDF</summary><a href="/static/vendor/pdfcraft-direct/NOTICE.md" target="_blank" rel="noopener noreferrer">Licenza e sorgenti del componente PDF</a></details></footer>
  </section>
}
