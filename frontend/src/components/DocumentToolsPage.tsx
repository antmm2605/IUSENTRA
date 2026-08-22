import {
  Archive,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Camera,
  CheckCircle2,
  Download,
  Eye,
  FilePlus2,
  Files,
  FolderCheck,
  GripVertical,
  LoaderCircle,
  RotateCcw,
  RotateCw,
  ScanLine,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import {
  generateDocument,
  saveGeneratedDocument,
  type DocumentToolMode,
  type GeneratedDocument,
} from '../documentToolsData'
import './DocumentToolsPage.css'

type SelectedDocument = {
  id: string
  file: File
  logicalName: string
  rotation: number
  previewUrl: string
}

const MODES: Array<{
  id: DocumentToolMode
  label: string
  title: string
  description: string
  icon: typeof Files
  accept: string
}> = [
  {
    id: 'merge',
    label: 'Unisci PDF',
    title: 'Unisci documenti PDF',
    description: 'Scegli almeno due PDF e disponili nell’ordine del documento finale.',
    icon: Files,
    accept: 'application/pdf,.pdf',
  },
  {
    id: 'zip',
    label: 'Crea ZIP',
    title: 'Crea un archivio ZIP',
    description: 'Raccogli documenti diversi in un unico archivio, conservando i nomi scelti.',
    icon: Archive,
    accept: '*/*',
  },
  {
    id: 'multipage',
    label: 'Acquisisci pagine',
    title: 'Crea un PDF multipagina',
    description: 'Aggiungi immagini o PDF, ruota le pagine e definisci l’ordine finale.',
    icon: ScanLine,
    accept: 'application/pdf,image/jpeg,image/png,image/tiff,image/webp,.pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp',
  },
]

function makeSelected(file: File): SelectedDocument {
  return {
    id: `${crypto.randomUUID?.() || Date.now()}-${file.name}-${file.lastModified}`,
    file,
    logicalName: file.name,
    rotation: 0,
    previewUrl: URL.createObjectURL(file),
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toLocaleString('it-IT', { maximumFractionDigits: 1 })} KB`
  return `${(bytes / (1024 * 1024)).toLocaleString('it-IT', { maximumFractionDigits: 1 })} MB`
}

function initialMode(): DocumentToolMode {
  const value = new URLSearchParams(window.location.search).get('modo')
  return value === 'zip' || value === 'multipage' ? value : 'merge'
}


type LocalScannerPayload = {
  ok?: boolean
  filename?: string
  mime_type?: string
  content_base64?: string
  errore?: string
}

const LOCAL_SCANNER_ENDPOINTS = [
  'http://127.0.0.1:27272/scanner/acquire',
  'http://localhost:27272/scanner/acquire',
]

function scannerFileFromPayload(payload: LocalScannerPayload): File {
  const encoded = String(payload.content_base64 || '').trim()
  if (!encoded) throw new Error('Lo scanner non ha restituito alcuna pagina.')
  let binary = ''
  try {
    binary = window.atob(encoded)
  } catch {
    throw new Error('La pagina acquisita non è leggibile.')
  }
  if (!binary.length || binary.length > 60 * 1024 * 1024) {
    throw new Error('La pagina acquisita è vuota o supera 60 MB.')
  }
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  const filename = String(payload.filename || 'scansione.jpg').replace(/[\\/:*?"<>|]/g, ' ').trim() || 'scansione.jpg'
  return new File([bytes], filename, { type: payload.mime_type || 'image/jpeg' })
}

export async function acquireFromLocalScanner(): Promise<File> {
  let lastError = ''
  for (const endpoint of LOCAL_SCANNER_ENDPOINTS) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 130_000)
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timeout: 120 }),
        signal: controller.signal,
      })
      const payload = await response.json().catch(() => null) as LocalScannerPayload | null
      if (response.ok && payload?.ok) return scannerFileFromPayload(payload)
      lastError = response.status === 404
        ? 'Aggiorna il Local Signer e ripeti l’acquisizione.'
        : String(payload?.errore || `Acquisizione non completata (HTTP ${response.status}).`)
    } catch (caught) {
      lastError = caught instanceof DOMException && caught.name === 'AbortError'
        ? 'Tempo scaduto durante l’acquisizione dallo scanner.'
        : caught instanceof Error ? caught.message : 'Local Signer non raggiungibile.'
    } finally {
      window.clearTimeout(timeout)
    }
  }
  throw new Error(lastError || 'Local Signer non raggiungibile sul PC in uso.')
}

export function DocumentToolsPage() {
  const [mode, setMode] = useState<DocumentToolMode>(initialMode)
  const [documents, setDocuments] = useState<SelectedDocument[]>([])
  const [outputName, setOutputName] = useState('')
  const [previewId, setPreviewId] = useState<string>('')
  const [draggedId, setDraggedId] = useState<string>('')
  const [scanning, setScanning] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [result, setResult] = useState<GeneratedDocument | null>(null)
  const documentsRef = useRef<SelectedDocument[]>([])
  const resultRef = useRef<GeneratedDocument | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)
  const fascicoloId = new URLSearchParams(window.location.search).get('id_fascicolo')?.trim() || ''
  const activeMode = MODES.find((item) => item.id === mode) || MODES[0]
  const previewDocument = documents.find((item) => item.id === previewId) || null
  const canGenerate = mode === 'merge' ? documents.length >= 2 : documents.length >= 1

  const clearResult = useCallback(() => {
    setResult((current) => {
      if (current) URL.revokeObjectURL(current.objectUrl)
      return null
    })
  }, [])


  useEffect(() => {
    documentsRef.current = documents
  }, [documents])

  useEffect(() => {
    resultRef.current = result
  }, [result])

  useEffect(() => () => {
    documentsRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl))
    if (resultRef.current) URL.revokeObjectURL(resultRef.current.objectUrl)
  }, [])

  useEffect(() => {
    setOutputName(mode === 'zip' ? 'documenti' : mode === 'merge' ? 'documenti-uniti' : 'acquisizione-multipagina')
    setError('')
    setNotice('')
    clearResult()
  }, [mode, clearResult])

  const totalSize = useMemo(
    () => documents.reduce((total, document) => total + document.file.size, 0),
    [documents],
  )

  const addFiles = (files: File[]) => {
    if (!files.length) return
    const next = files.map(makeSelected)
    setDocuments((current) => [...current, ...next])
    setPreviewId((current) => current || next[0]?.id || '')
    setError('')
    setNotice('')
    clearResult()
  }

  const acquireScannerPage = async () => {
    setScanning(true)
    setError('')
    setNotice('')
    try {
      const scannedFile = await acquireFromLocalScanner()
      addFiles([scannedFile])
      setNotice('Pagina acquisita dallo scanner locale e aggiunta all’elenco.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Acquisizione dallo scanner non completata.')
    } finally {
      setScanning(false)
    }
  }


  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files || []))
    event.target.value = ''
  }

  const removeDocument = (id: string) => {
    setDocuments((current) => {
      const target = current.find((item) => item.id === id)
      if (target) URL.revokeObjectURL(target.previewUrl)
      return current.filter((item) => item.id !== id)
    })
    if (previewId === id) setPreviewId('')
    clearResult()
  }

  const moveDocument = (id: string, direction: -1 | 1) => {
    setDocuments((current) => {
      const from = current.findIndex((item) => item.id === id)
      const to = from + direction
      if (from < 0 || to < 0 || to >= current.length) return current
      const next = [...current]
      const [item] = next.splice(from, 1)
      next.splice(to, 0, item)
      return next
    })
    clearResult()
  }

  const dropOnDocument = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return
    setDocuments((current) => {
      const from = current.findIndex((item) => item.id === draggedId)
      const to = current.findIndex((item) => item.id === targetId)
      if (from < 0 || to < 0) return current
      const next = [...current]
      const [item] = next.splice(from, 1)
      next.splice(to, 0, item)
      return next
    })
    setDraggedId('')
    clearResult()
  }

  const updateDocument = (id: string, values: Partial<Pick<SelectedDocument, 'logicalName' | 'rotation'>>) => {
    setDocuments((current) => current.map((item) => item.id === id ? { ...item, ...values } : item))
    clearResult()
  }

  const createResult = async () => {
    if (!canGenerate) return
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const generated = await generateDocument(
        mode,
        documents.map((item) => item.file),
        outputName,
        documents.map((item) => item.logicalName),
        documents.map((item) => item.rotation),
      )
      setResult((current) => {
        if (current) URL.revokeObjectURL(current.objectUrl)
        return generated
      })
      setPreviewId('')
      setNotice('Documento creato. Controllalo prima di scaricarlo o salvarlo nel fascicolo.')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Operazione non completata.')
    } finally {
      setLoading(false)
    }
  }

  const saveToFile = async () => {
    if (!result || !fascicoloId) return
    setSaving(true)
    setError('')
    try {
      setNotice(await saveGeneratedDocument(fascicoloId, result))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Documento non salvato nel fascicolo.')
    } finally {
      setSaving(false)
    }
  }

  const onDropFiles = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setDragActive(false)
    addFiles(Array.from(event.dataTransfer.files || []))
  }

  return (
    <main className="iu-content iu-document-tools">
      <header className="iu-document-tools__header">
        <div>
          <span className="iu-document-tools__eyebrow"><FilePlus2 size={16} /> Strumenti documenti</span>
          <h1>Prepara i documenti</h1>
          <p>Unisci, ordina e raccogli i file senza modificare gli originali.</p>
        </div>
        <a className="iu-document-tools__back" href={fascicoloId ? `/fascicoli/${encodeURIComponent(fascicoloId)}` : '/strumenti-operativi'}>
          <ArrowLeft size={18} /> {fascicoloId ? 'Torna al fascicolo' : 'Torna agli strumenti'}
        </a>
      </header>

      <nav className="iu-document-tools__tabs" aria-label="Operazione documentale">
        {MODES.map((item) => {
          const Icon = item.icon
          return (
            <button
              type="button"
              className={mode === item.id ? 'is-active' : ''}
              aria-pressed={mode === item.id}
              onClick={() => setMode(item.id)}
              key={item.id}
            >
              <Icon size={18} /> {item.label}
            </button>
          )
        })}
      </nav>

      <section className="iu-document-tools__workspace" aria-labelledby="document-tool-title">
        <div className="iu-document-tools__intro">
          <div>
            <h2 id="document-tool-title">{activeMode.title}</h2>
            <p>{activeMode.description}</p>
          </div>
          <div className="iu-document-tools__count" aria-label={`${documents.length} file selezionati`}>
            <strong>{documents.length}</strong>
            <span>{documents.length === 1 ? 'file' : 'file'}</span>
            <small>{formatBytes(totalSize)}</small>
          </div>
        </div>

        <div
          className={`iu-document-tools__dropzone ${dragActive ? 'is-dragging' : ''}`}
          onDragEnter={(event) => { event.preventDefault(); setDragActive(true) }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => { if (event.currentTarget === event.target) setDragActive(false) }}
          onDrop={onDropFiles}
        >
          <Upload size={26} aria-hidden="true" />
          <div>
            <strong>Trascina qui i documenti</strong>
            <span>oppure selezionali dal computer</span>
          </div>
          <button type="button" className="iu-document-tools__secondary" onClick={() => fileInput.current?.click()}>
            <FilePlus2 size={18} /> Seleziona file
          </button>
          {mode === 'multipage' ? (
            <>
            <button
              type="button"
              className="iu-document-tools__icon-command"
              title="Acquisisci una pagina dallo scanner"
              aria-label="Acquisisci una pagina dallo scanner"
              disabled={scanning}
              onClick={acquireScannerPage}
            >
              {scanning ? <LoaderCircle className="is-spinning" size={20} /> : <ScanLine size={20} />}
            </button>
            <button type="button" className="iu-document-tools__icon-command" title="Acquisisci una pagina con la fotocamera" aria-label="Acquisisci una pagina con la fotocamera" onClick={() => cameraInput.current?.click()}>
              <Camera size={20} />
            </button>
            </>
          ) : null}
          <input ref={fileInput} type="file" multiple accept={activeMode.accept} hidden onChange={onFileChange} />
          <input ref={cameraInput} type="file" multiple accept="image/*" capture="environment" hidden onChange={onFileChange} />
        </div>

        {documents.length ? (
          <div className="iu-document-tools__body">
            <div className="iu-document-tools__list" role="list" aria-label="Documenti selezionati">
              {documents.map((document, index) => (
                <article
                  className="iu-document-tools__row"
                  role="listitem"
                  draggable
                  onDragStart={() => setDraggedId(document.id)}
                  onDragEnd={() => setDraggedId('')}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => dropOnDocument(document.id)}
                  key={document.id}
                >
                  <GripVertical className="iu-document-tools__grip" size={18} aria-hidden="true" />
                  <span className="iu-document-tools__index">{index + 1}</span>
                  <div className="iu-document-tools__file">
                    <strong title={document.file.name}>{document.file.name}</strong>
                    <span>{formatBytes(document.file.size)}</span>
                    {mode === 'zip' ? (
                      <label>
                        <span>Nome nell’archivio</span>
                        <input value={document.logicalName} onChange={(event) => updateDocument(document.id, { logicalName: event.target.value })} />
                      </label>
                    ) : null}
                    {mode === 'multipage' && document.rotation ? <small>Rotazione: {document.rotation}°</small> : null}
                  </div>
                  <div className="iu-document-tools__row-actions">
                    <button type="button" title="Sposta su" aria-label={`Sposta ${document.file.name} su`} disabled={index === 0} onClick={() => moveDocument(document.id, -1)}><ArrowUp size={17} /></button>
                    <button type="button" title="Sposta giù" aria-label={`Sposta ${document.file.name} giù`} disabled={index === documents.length - 1} onClick={() => moveDocument(document.id, 1)}><ArrowDown size={17} /></button>
                    {mode === 'multipage' ? (
                      <>
                        <button type="button" title="Ruota a sinistra" aria-label={`Ruota ${document.file.name} a sinistra`} onClick={() => updateDocument(document.id, { rotation: (document.rotation + 270) % 360 })}><RotateCcw size={17} /></button>
                        <button type="button" title="Ruota a destra" aria-label={`Ruota ${document.file.name} a destra`} onClick={() => updateDocument(document.id, { rotation: (document.rotation + 90) % 360 })}><RotateCw size={17} /></button>
                      </>
                    ) : null}
                    <button type="button" title="Visualizza" aria-label={`Visualizza ${document.file.name}`} onClick={() => setPreviewId(previewId === document.id ? '' : document.id)}><Eye size={17} /></button>
                    <button type="button" className="is-danger" title="Rimuovi" aria-label={`Rimuovi ${document.file.name}`} onClick={() => removeDocument(document.id)}><Trash2 size={17} /></button>
                  </div>
                </article>
              ))}
            </div>

            {previewDocument ? (
              <aside className="iu-document-tools__preview" aria-label={`Anteprima ${previewDocument.file.name}`}>
                <header>
                  <strong>{previewDocument.file.name}</strong>
                  <button type="button" title="Chiudi anteprima" aria-label="Chiudi anteprima" onClick={() => setPreviewId('')}><X size={18} /></button>
                </header>
                {previewDocument.file.type.startsWith('image/') ? (
                  <img src={previewDocument.previewUrl} alt={`Anteprima ${previewDocument.file.name}`} />
                ) : previewDocument.file.type === 'application/pdf' || previewDocument.file.name.toLowerCase().endsWith('.pdf') ? (
                  <iframe src={previewDocument.previewUrl} title={`Anteprima ${previewDocument.file.name}`} />
                ) : (
                  <div className="iu-document-tools__preview-empty"><Archive size={32} /><span>Anteprima non disponibile per questo formato.</span></div>
                )}
              </aside>
            ) : null}
          </div>
        ) : (
          <div className="iu-document-tools__empty">
            <Files size={30} />
            <strong>Nessun documento selezionato</strong>
            <span>L’ordine mostrato qui sarà lo stesso del risultato finale.</span>
          </div>
        )}

        <footer className="iu-document-tools__footer">
          <label>
            <span>Nome del documento</span>
            <div className="iu-document-tools__filename">
              <input value={outputName} onChange={(event) => setOutputName(event.target.value)} />
              <span>.{mode === 'zip' ? 'zip' : 'pdf'}</span>
            </div>
          </label>
          <button type="button" className="iu-document-tools__primary" disabled={!canGenerate || loading} onClick={createResult}>
            {loading ? <LoaderCircle className="is-spinning" size={18} /> : <CheckCircle2 size={18} />}
            {loading ? 'Preparazione…' : mode === 'zip' ? 'Crea archivio' : 'Crea documento'}
          </button>
        </footer>

        {error ? <div className="iu-document-tools__message is-error" role="alert">{error}</div> : null}
        {notice ? <div className="iu-document-tools__message is-success" role="status">{notice}</div> : null}

        {result ? (
          <section className="iu-document-tools__result" aria-label="Documento creato">
            <div>
              <CheckCircle2 size={22} />
              <span>
                <strong>{result.filename}</strong>
                <small>{result.pages ? `${result.pages} ${result.pages === 1 ? 'pagina' : 'pagine'} · ` : ''}{formatBytes(result.blob.size)}</small>
              </span>
            </div>
            <div className="iu-document-tools__result-actions">
              {result.blob.type === 'application/pdf' ? <a href={result.objectUrl} target="_blank" rel="noreferrer"><Eye size={18} /> Visualizza</a> : null}
              <a href={result.objectUrl} download={result.filename}><Download size={18} /> Scarica</a>
              {fascicoloId ? (
                <button type="button" disabled={saving} onClick={saveToFile}>
                  {saving ? <LoaderCircle className="is-spinning" size={18} /> : <FolderCheck size={18} />}
                  {saving ? 'Salvataggio…' : 'Salva nel fascicolo'}
                </button>
              ) : null}
            </div>
          </section>
        ) : null}
      </section>
    </main>
  )
}

export default DocumentToolsPage

