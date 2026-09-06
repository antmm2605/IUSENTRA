import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Camera, Check, FileCheck2, RotateCw, ScanLine, Trash2, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { acquireFromLocalScanner } from '../../services/localScanner'
import { generateDocument, saveGeneratedDocument, type GeneratedDocument } from '../../documentToolsData'
import { CaptureCamera } from './CaptureCamera'
import { MAX_CAPTURE_BYTES, MAX_CAPTURE_FILES, prepareCaptureImage, type CapturePage } from './captureImages'
import './documentCapture.css'

export default function DocumentCapture({ fascicoloId, reference, onSaved }: { fascicoloId: string; reference: string; onSaved: (message?: string) => void }) {
  const [open, setOpen] = useState(false)
  const [camera, setCamera] = useState(false)
  const [pages, setPages] = useState<CapturePage[]>([])
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [name, setName] = useState('Acquisizione documenti')
  const [result, setResult] = useState<GeneratedDocument | null>(null)
  const [reviewed, setReviewed] = useState(false)
  const [discard, setDiscard] = useState(false)
  const photo = useRef<HTMLInputElement>(null)
  const state = useRef({ pages, result })
  const active = useRef(true)
  const working = useRef(false)
  state.current = { pages, result }
  const stopCamera = useCallback(() => setCamera(false), [])
  useEffect(() => {
    active.current = true
    return () => { active.current = false; state.current.pages.forEach((page) => URL.revokeObjectURL(page.url)); if (state.current.result) URL.revokeObjectURL(state.current.result.objectUrl) }
  }, [])
  useEffect(() => {
    const protect = (event: BeforeUnloadEvent) => { if (pages.length || busy) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [pages.length, busy])
  const invalidate = () => { if (state.current.result) URL.revokeObjectURL(state.current.result.objectUrl); setResult(null); setReviewed(false); setNotice('') }
  const perform = async (label: string, action: () => Promise<void>) => {
    if (working.current) return
    working.current = true; setBusy(label); setError('')
    try { await action() } catch (cause) { if (active.current) setError(cause instanceof Error ? cause.message : 'Acquisizione non completata.') }
    finally { working.current = false; if (active.current) setBusy('') }
  }
  const append = async (file: File) => {
    const current = state.current.pages
    if (current.length >= MAX_CAPTURE_FILES) throw new Error('Puoi acquisire fino a 80 pagine per documento.')
    const page = await prepareCaptureImage(file)
    if (!active.current) { URL.revokeObjectURL(page.url); return }
    if (current.reduce((bytes, item) => bytes + item.file.size, page.file.size) > MAX_CAPTURE_BYTES) { URL.revokeObjectURL(page.url); throw new Error('Le pagine superano 180 MB. Salva questo documento prima di acquisirne altre.') }
    invalidate(); setPages([...current, page]); setSelected(page.id)
    setNotice('Pagina acquisita, non ancora salvata. Controlla l’anteprima.')
  }
  const reset = () => {
    pages.forEach((page) => URL.revokeObjectURL(page.url)); invalidate(); setPages([]); setSelected(''); setError(''); setDiscard(false); setCamera(false)
  }
  const close = () => { stopCamera(); if (pages.length) setDiscard(true); else setOpen(false) }
  const editPages = (next: CapturePage[]) => { invalidate(); setPages(next) }
  const move = (index: number, delta: number) => { const next = [...pages]; [next[index], next[index + delta]] = [next[index + delta], next[index]]; editPages(next) }
  const prepare = () => perform('Preparazione dell’anteprima PDF…', async () => {
    stopCamera()
    const generated = await generateDocument('multipage', pages.map((page) => page.file), name, pages.map((page) => page.file.name), pages.map((page) => page.rotation))
    if (!active.current) { URL.revokeObjectURL(generated.objectUrl); return }
    invalidate(); setResult(generated)
  })
  const save = () => perform('Salvataggio nel fascicolo…', async () => {
    if (!result || !reviewed) return
    const message = await saveGeneratedDocument(fascicoloId, result)
    reset(); setNotice(`${result.filename}: ${message}`); onSaved(message)
  })
  const preview = pages.find((page) => page.id === selected) || pages[0]
  return <section className="iu-document-capture" aria-label="Acquisizione documenti da scanner, webcam e fotocamera">
    {!open ? <div className="iu-document-capture__closed">
      <div>
        <strong>Acquisizione da dispositivo</strong>
        <span>Scanner Windows, webcam o fotocamera del telefono: anteprima e salvataggio nel fascicolo.</span>
      </div>
      <Button type="button" tone="neutral" className="iu-document-capture__opener" onClick={() => setOpen(true)}><ScanLine size={17}/>Scanner / webcam / fotocamera</Button>
    </div> : <>
      <header><div><h3>Acquisisci documenti</h3><p>Destinazione: {reference}. Le pagine entrano in Documenti e atti solo dopo la conferma.</p></div><Button type="button" tone="neutral" disabled={Boolean(busy)} onClick={close}><X size={16}/>Chiudi</Button></header>
      <div className="iu-capture-actions">
        <Button type="button" tone="neutral" disabled={Boolean(busy) || camera} onClick={() => perform('Acquisizione dallo scanner: completa la finestra sul PC…', async () => append(await acquireFromLocalScanner()))}><ScanLine size={16}/>Scanner Windows</Button>
        <Button type="button" tone="neutral" disabled={Boolean(busy) || camera} onClick={() => { setError(''); setCamera(true) }}><Camera size={16}/>Webcam / fotocamera</Button>
        <Button type="button" tone="neutral" disabled={Boolean(busy) || camera} onClick={() => photo.current?.click()}><Camera size={16}/>Scatta dal telefono</Button>
        <input ref={photo} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void perform('Preparazione della foto…', () => append(file)) }}/>
      </div>
      <p className="iu-capture-help">Scanner: collegamento al PC tramite IUSENTRA Local Signer e driver Windows. Telefono: apri questo fascicolo dal dispositivo e usa la sua fotocamera.</p>
      {camera ? <CaptureCamera onCapture={(file) => perform('Acquisizione della foto…', () => append(file))} onClose={stopCamera}/> : null}
      {busy ? <p role="status" aria-live="polite">{busy}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      {discard ? <div role="alert"><p>Vuoi scartare le pagine non salvate? Il fascicolo non verrà modificato.</p><Button type="button" tone="danger" onClick={() => { reset(); setOpen(false) }}>Scarta e chiudi</Button> <Button type="button" tone="neutral" onClick={() => setDiscard(false)}>Continua la verifica</Button></div> : null}
      {pages.length ? <>
        <div className="iu-capture-review">
          <ol aria-label="Pagine acquisite, nell’ordine del PDF">{pages.map((page, index) => <li key={page.id}>
            <Button type="button" tone="neutral" aria-pressed={preview?.id === page.id} onClick={() => setSelected(page.id)}>Pagina {index + 1}</Button>
            <div className="iu-capture-actions">
              <Button type="button" tone="neutral" aria-label={`Ruota pagina ${index + 1}`} disabled={Boolean(busy)} onClick={() => editPages(pages.map((item) => item.id === page.id ? { ...item, rotation: (item.rotation + 90) % 360 } : item))}><RotateCw size={16}/></Button>
              <Button type="button" tone="neutral" aria-label={`Sposta pagina ${index + 1} prima`} disabled={Boolean(busy) || index === 0} onClick={() => move(index, -1)}><ArrowUp size={16}/></Button>
              <Button type="button" tone="neutral" aria-label={`Sposta pagina ${index + 1} dopo`} disabled={Boolean(busy) || index === pages.length - 1} onClick={() => move(index, 1)}><ArrowDown size={16}/></Button>
              <Button type="button" tone="neutral" aria-label={`Rimuovi pagina ${index + 1} dall’acquisizione`} disabled={Boolean(busy)} onClick={() => { URL.revokeObjectURL(page.url); editPages(pages.filter((item) => item.id !== page.id)) }}><Trash2 size={16}/></Button>
            </div>
          </li>)}</ol>
          {preview ? <figure><div className="iu-capture-image"><img src={preview.url} alt={`Anteprima della pagina ${pages.indexOf(preview) + 1}, rotazione ${preview.rotation} gradi`} style={{ transform: `rotate(${preview.rotation}deg)` }}/></div><figcaption>Pagina {pages.indexOf(preview) + 1} di {pages.length}. Controlla leggibilità, bordi e orientamento.</figcaption></figure> : null}
        </div>
        <label className="iu-capture-name">Nome del PDF<input value={name} maxLength={120} disabled={Boolean(busy)} onChange={(event) => { setName(event.target.value); invalidate() }}/></label>
        <Button type="button" disabled={Boolean(busy) || !name.trim()} onClick={prepare}><FileCheck2 size={16}/>Prepara PDF da verificare</Button>
      </> : !camera ? <p>Nessuna pagina acquisita. Puoi aggiungere più pagine allo stesso PDF.</p> : null}
      {result ? <section className="iu-capture-result" aria-label="Verifica prima del salvataggio">
        <h4>{result.filename}, {result.pages} {result.pages === 1 ? 'pagina' : 'pagine'}</h4>
        <iframe src={result.objectUrl} title="Anteprima del PDF da salvare nel fascicolo"/>
        <label><input type="checkbox" checked={reviewed} disabled={Boolean(busy)} onChange={(event) => setReviewed(event.target.checked)}/>Ho controllato tutte le pagine e confermo il salvataggio in questo fascicolo.</label>
        <Button type="button" disabled={!reviewed || Boolean(busy)} onClick={save}><Check size={16}/>Conferma e salva nel fascicolo</Button>
        <p>Il PDF non viene firmato né inviato. Le foto vengono preparate senza metadati di posizione.</p>
      </section> : null}
    </>}
  </section>
}
