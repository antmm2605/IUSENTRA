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
  FilePenLine,
  Files,
  FolderCheck,
  GripVertical,
  LoaderCircle,
  RotateCcw,
  RotateCw,
  ScanLine,
  Scissors,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import {
  generateDocument,
  previewUploadedPdf,
  saveGeneratedDocument,
  type DocumentToolMode,
  type GeneratedDocument,
} from '../documentToolsData'
import './DocumentToolsPage.css'
import { formatDateTimeIt } from '../formatting'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import { acquireFromLocalScanner } from '../services/localScanner'
export { acquireFromLocalScanner } from '../services/localScanner'

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
    id: 'split', label: 'Dividi PDF', icon: Scissors, title: 'Estrai le pagine utili',
    description: 'Scegli un PDF e indica le pagine da estrarre. L’originale resta intatto.',
    accept: '.pdf,application/pdf',
  },
  {
    id: 'word', label: 'PDF in Word', icon: FilePenLine, title: 'Converti un PDF in Word',
    description: 'Crea una copia modificabile con testo, caratteri, tabelle e immagini. Seleziona un PDF da 1 a 100 pagine.',
    accept: '.pdf,application/pdf',
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
  return value === 'zip' || value === 'multipage' || value === 'split' || value === 'word' ? value : 'merge'
}


export function DocumentToolsPage() {
  const [mode, setMode] = useState<DocumentToolMode>(initialMode)
  const [documents, setDocuments] = useState<SelectedDocument[]>([])
  const [outputName, setOutputName] = useState('')
  const [previewId, setPreviewId] = useState<string>('')
  const [pageSelection, setPageSelection] = useState('')
  const [draggedId, setDraggedId] = useState<string>('')
  const [scanning, setScanning] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [result, setResult] = useState<GeneratedDocument | null>(null)
  const [resultExpired, setResultExpired] = useState(false)
  const [generatedPreview, setGeneratedPreview] = useState<SourceDocument | null>(null)
  const [previewLoading, setPreviewLoading] = useState('')
  const previewRequests = useRef<AbortController | null>(null)
  const previewCache = useRef(new Map<string, { href: string; expiresAt: number }>())
  const documentsRef = useRef<SelectedDocument[]>([])
  const resultRef = useRef<GeneratedDocument | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)
  const fascicoloId = new URLSearchParams(window.location.search).get('id_fascicolo')?.trim() || ''
  const activeMode = MODES.find((item) => item.id === mode) || MODES[0]
  const previewDocument = documents.find((item) => item.id === previewId) || null
  const canGenerate = mode === 'word' ? documents.length === 1 : mode === 'split' ? documents.length === 1 && Boolean(pageSelection.trim()) : mode === 'merge' ? documents.length >= 2 : documents.length >= 1

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
    previewRequests.current?.abort()
    documentsRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl))
    if (resultRef.current) URL.revokeObjectURL(resultRef.current.objectUrl)
  }, [])

  useEffect(() => {
    setOutputName(mode === 'word' ? 'documento-convertito' : mode === 'zip' ? 'documenti' : mode === 'merge' ? 'documenti-uniti' : mode === 'split' ? 'pagine-estratte' : 'acquisizione-multipagina')
    setError('')
    setNotice('')
    clearResult()
  }, [mode, clearResult])

  useEffect(() => {
    setResultExpired(false)
    if (!result?.expiresAt) return
    const timer = window.setTimeout(() => setResultExpired(true), Math.max(0, result.expiresAt - Date.now()))
    return () => window.clearTimeout(timer)
  }, [result])

  const totalSize = useMemo(
    () => documents.reduce((total, document) => total + document.file.size, 0),
    [documents],
  )

  const addFiles = (files: File[]) => {
    if (loading) return
    if (!files.length) return
    if ((mode === 'split' || mode === 'word') && files.length !== 1) { setError('Seleziona un solo documento PDF per questa operazione.'); return }
    const next = files.map(makeSelected)
    setDocuments((current) => {
      if (mode === 'split' || mode === 'word') current.forEach(item => URL.revokeObjectURL(item.previewUrl))
      return mode === 'split' || mode === 'word' ? next : [...current, ...next]
    })
    setPreviewId((current) => mode === 'split' || mode === 'word' ? next[0]?.id || '' : current || next[0]?.id || '')
    setError('')
    setNotice('')
    clearResult()
  }

  const openPreview = async (document: SelectedDocument) => {
    if (document.file.type !== 'application/pdf' && !document.file.name.toLowerCase().endsWith('.pdf')) {
      setPreviewId(current => current === document.id ? '' : document.id)
      return
    }
    previewRequests.current?.abort()
    const controller = new AbortController()
    previewRequests.current = controller
    setPreviewLoading(document.id)
    setError('')
    try {
      let preview = previewCache.current.get(document.id)
      if (!preview || preview.expiresAt <= Date.now()) {
        preview = await previewUploadedPdf(document.file, controller.signal)
        previewCache.current.set(document.id, preview)
      }
      if (controller.signal.aborted || !documentsRef.current.some(item => item.id === document.id)) return
      setPreviewId('')
      setGeneratedPreview({ href: preview.href, label: document.file.name, context: 'Documento selezionato. L’originale resta intatto.' })
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Anteprima non disponibile. Riprova.')
    } finally {
      if (previewRequests.current === controller) setPreviewLoading('')
    }
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
    if (loading) return
    previewCache.current.delete(id)
    if (previewLoading === id) previewRequests.current?.abort()
    setDocuments((current) => {
      const target = current.find((item) => item.id === id)
      if (target) URL.revokeObjectURL(target.previewUrl)
      return current.filter((item) => item.id !== id)
    })
    if (previewId === id) setPreviewId('')
    clearResult()
  }

  const moveDocument = (id: string, direction: -1 | 1) => {
    if (loading) return
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
    if (loading) return
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
    if (loading) return
    setDocuments((current) => current.map((item) => item.id === id ? { ...item, ...values } : item))
    clearResult()
  }

  const createResult = async () => {
    if (!canGenerate || loading) return
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
        '',
        pageSelection,
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
              disabled={loading}
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
          <div className="iu-document-tools__count" aria-label={`${documents.length} ${documents.length === 1 ? 'file selezionato' : 'file selezionati'}`}>
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
          <button type="button" className="iu-document-tools__secondary" disabled={loading} onClick={() => fileInput.current?.click()}>
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
          <input ref={fileInput} type="file" multiple={mode !== 'split' && mode !== 'word'} accept={activeMode.accept} hidden onChange={onFileChange} />
          <input ref={cameraInput} type="file" multiple accept="image/*" capture="environment" hidden onChange={onFileChange} />
        </div>

        {documents.length ? (
          <div className="iu-document-tools__body">
            <div className="iu-document-tools__list" role="list" aria-label="Documenti selezionati">
              {documents.map((document, index) => (
                <article
                  className={`iu-document-tools__row${mode === 'word' || mode === 'split' ? ' is-single' : ''}`}
                  role="listitem"
                  draggable={!loading && mode !== 'word' && mode !== 'split'}
                  onDragStart={() => setDraggedId(document.id)}
                  onDragEnd={() => setDraggedId('')}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => dropOnDocument(document.id)}
                  key={document.id}
                >
                  {mode !== 'word' && mode !== 'split' ? <GripVertical className="iu-document-tools__grip" size={18} aria-hidden="true" /> : null}
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
                    {mode !== 'word' && mode !== 'split' ? <>
                    <button type="button" title="Sposta su" aria-label={`Sposta ${document.file.name} su`} disabled={loading || index === 0} onClick={() => moveDocument(document.id, -1)}><ArrowUp size={17} /></button>
                    <button type="button" title="Sposta giù" aria-label={`Sposta ${document.file.name} giù`} disabled={loading || index === documents.length - 1} onClick={() => moveDocument(document.id, 1)}><ArrowDown size={17} /></button>
                    </> : null}
                    {mode === 'multipage' ? (
                      <>
                        <button type="button" title="Ruota a sinistra" aria-label={`Ruota ${document.file.name} a sinistra`} onClick={() => updateDocument(document.id, { rotation: (document.rotation + 270) % 360 })}><RotateCcw size={17} /></button>
                        <button type="button" title="Ruota a destra" aria-label={`Ruota ${document.file.name} a destra`} onClick={() => updateDocument(document.id, { rotation: (document.rotation + 90) % 360 })}><RotateCw size={17} /></button>
                      </>
                    ) : null}
                    <button type="button" title="Visualizza" aria-label={`Visualizza ${document.file.name}`} aria-busy={previewLoading === document.id} disabled={previewLoading === document.id} onClick={() => void openPreview(document)}>{previewLoading === document.id ? <LoaderCircle size={17} className="iu-spin" /> : <Eye size={17} />}</button>
                    <button type="button" className="is-danger" title="Rimuovi" aria-label={`Rimuovi ${document.file.name}`} disabled={loading} onClick={() => removeDocument(document.id)}><Trash2 size={17} /></button>
                  </div>
                </article>
              ))}
            </div>

            {previewDocument ? (
              <aside className={`iu-document-tools__preview${previewDocument.file.type === 'application/pdf' || previewDocument.file.name.toLowerCase().endsWith('.pdf') ? ' iu-document-tools__preview--link' : ''}`} aria-label={`Anteprima ${previewDocument.file.name}`}>
                <header>
                  <strong>{previewDocument.file.name}</strong>
                  <button type="button" title="Chiudi anteprima" aria-label="Chiudi anteprima" onClick={() => setPreviewId('')}><X size={18} /></button>
                </header>
                {previewDocument.file.type.startsWith('image/') ? (
                  <img src={previewDocument.previewUrl} alt={`Anteprima ${previewDocument.file.name}`} />
                ) : previewDocument.file.type === 'application/pdf' || previewDocument.file.name.toLowerCase().endsWith('.pdf') ? (
                  <button type="button" className="iu-document-tools__secondary" disabled={previewLoading === previewDocument.id} onClick={() => void openPreview(previewDocument)}><Eye size={17} />{previewLoading === previewDocument.id ? 'Apertura…' : 'Apri nel lettore'}</button>
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
            <span>{mode === 'word' ? 'Seleziona il PDF da convertire in un documento modificabile.' : 'L’ordine mostrato qui sarà lo stesso del risultato finale.'}</span>
          </div>
        )}

        {mode === 'split' ? <label className="iu-document-tools__page-selection">
          <span>Pagine da estrarre</span>
          <input aria-label="Pagine da estrarre" aria-describedby="split-pages-help" value={pageSelection} disabled={loading} placeholder="Per esempio: 1-3, 5" onChange={event => { setPageSelection(event.target.value); clearResult(); setError(''); setNotice('') }} />
          <small id="split-pages-help">Numeri e intervalli separati da virgole. L’ordine indicato sarà quello del nuovo PDF.</small>
          {documents.length > 1 ? <span role="alert">Per questa operazione mantieni un solo PDF nella selezione.</span> : null}
        </label> : null}
        <footer className="iu-document-tools__footer">
          <label>
            <span>Nome del documento</span>
            <div className="iu-document-tools__filename">
              <input value={outputName} disabled={loading} onChange={(event) => setOutputName(event.target.value)} />
              <span>.{mode === 'word' ? 'docx' : mode === 'zip' ? 'zip' : 'pdf'}</span>
            </div>
          </label>
          <button type="button" className="iu-document-tools__primary" disabled={!canGenerate || loading} onClick={createResult}>
            {loading ? <LoaderCircle className="is-spinning" size={18} /> : <CheckCircle2 size={18} />}
            {loading ? 'Preparazione…' : mode === 'word' ? 'Converti in Word' : mode === 'zip' ? 'Crea archivio' : mode === 'split' ? 'Estrai pagine' : 'Crea documento'}
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
                <small>{result.pages ? `${result.pages} ${result.pages === 1 ? 'pagina' : 'pagine'} · ` : ''}{formatBytes(result.blob.size)}{result.expiresAt ? ` · Copia temporanea fino al ${formatDateTimeIt(new Date(result.expiresAt))}` : ''}</small>
                {resultExpired ? <small role="alert">Copia temporanea scaduta. Usa il comando di creazione per generarla di nuovo.</small> : null}
              </span>
            </div>
            <div className="iu-document-tools__result-actions">
              {result.previewHref ? <button type="button" disabled={resultExpired} className="iu-document-tools__secondary" onClick={() => setGeneratedPreview({href: result.previewHref!,label: result.filename,context: 'Copia generata. L’originale resta intatto.'})}><Eye size={18} /> Visualizza</button> : null}
              {resultExpired ? <button type="button" disabled><Download size={18} /> Scarica</button> : <a href={result.downloadHref} download={result.filename}><Download size={18} /> Scarica</a>}
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
      <SourceDocumentModal source={generatedPreview} onClose={() => setGeneratedPreview(null)} />
    </main>
  )
}

export default DocumentToolsPage
