import { useCallback, useEffect, useMemo, useRef, useState, type ClipboardEvent, type ReactNode } from 'react'
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  AlertTriangle,
  ArrowLeft,
  Bold,
  CheckCircle2,
  Download,
  Eye,
  FileDown,
  FileText,
  Heading1,
  Highlighter,
  Italic,
  Link,
  List,
  ListOrdered,
  LoaderCircle,
  Palette,
  Pilcrow,
  Redo2,
  Replace,
  Save,
  Search,
  ShieldCheck,
  Strikethrough,
  Table,
  Underline,
  Undo2,
  UploadCloud,
} from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyDocumentEditorPayload,
  getDocumentEditorPayload,
  type DocumentEditorPayload,
} from '../documentEditorData'
import './DocumentEditorPage.css'

type EditorRoute = { idFascicolo: string; idDocumento: string } | null
type EditorStatus = { tone: 'loading' | 'saving' | 'success' | 'warning' | 'danger' | 'neutral'; label: string }
type EditorStats = { words: number; chars: number; readingMinutes: number }
type InlineStylePatch = { fontFamily?: string; fontSize?: string; lineHeight?: string }

const defaultStats: EditorStats = { words: 0, chars: 0, readingMinutes: 1 }
const FONT_FAMILY_OPTIONS = [
  { label: 'Times New Roman', value: '"Times New Roman", Times, serif' },
  { label: 'Arial', value: 'Arial, Helvetica, sans-serif' },
  { label: 'Calibri', value: 'Calibri, "Segoe UI", sans-serif' },
  { label: 'Garamond', value: 'Garamond, "Times New Roman", serif' },
  { label: 'Georgia', value: 'Georgia, "Times New Roman", serif' },
  { label: 'Courier New', value: '"Courier New", Courier, monospace' },
] as const
const FONT_SIZE_OPTIONS = ['10pt', '11pt', '12pt', '13pt', '14pt', '16pt', '18pt', '20pt', '24pt'] as const
const LINE_HEIGHT_OPTIONS = [
  { label: '1,15', value: '1.15' },
  { label: '1,5', value: '1.5' },
  { label: '1,6', value: '1.6' },
  { label: 'Doppia', value: '2' },
] as const
const PAGE_PRESETS = [
  { id: 'a4', label: 'A4', width: '840px', minHeight: '1120px', paddingX: '82px', paddingY: '76px' },
  { id: 'a4-compact', label: 'A4 compatto', width: '840px', minHeight: '1120px', paddingX: '58px', paddingY: '54px' },
  { id: 'legal-wide', label: 'Uso studio', width: '900px', minHeight: '1120px', paddingX: '72px', paddingY: '66px' },
] as const

function parseEditorRoute(): EditorRoute {
  const rawPath = window.location.pathname.replace(/\/+$/, '') || '/'
  const path = rawPath.startsWith('/app-v2/fascicoli') ? rawPath.slice('/app-v2'.length) || '/fascicoli' : rawPath
  const match = /^\/fascicoli\/([^/]+)\/documenti\/([^/]+)\/editor$/i.exec(path)
  if (!match) return null
  return {
    idFascicolo: decodeURIComponent(match[1]),
    idDocumento: decodeURIComponent(match[2]),
  }
}

function escapeHtml(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function textToHtml(value: string): string {
  return value
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.trim() ? `<p>${escapeHtml(line)}</p>` : '<p><br></p>')
    .join('')
}

function markdownToHtml(value: string): string {
  return value
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => {
      if (!line.trim()) return '<p><br></p>'
      if (line.startsWith('#### ')) return `<h4>${escapeHtml(line.slice(5))}</h4>`
      if (line.startsWith('### ')) return `<h3>${escapeHtml(line.slice(4))}</h3>`
      if (line.startsWith('## ')) return `<h2>${escapeHtml(line.slice(3))}</h2>`
      if (line.startsWith('# ')) return `<h1>${escapeHtml(line.slice(2))}</h1>`
      return `<p>${escapeHtml(line)}</p>`
    })
    .join('')
}

function sanitizeHtml(html: string): string {
  const template = document.createElement('template')
  template.innerHTML = html || '<p><br></p>'
  template.content.querySelectorAll('script,style,iframe,object,embed,link,meta').forEach((node) => node.remove())
  template.content.querySelectorAll('*').forEach((node) => {
    Array.from(node.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase()
      const value = attribute.value.toLowerCase()
      if (name.startsWith('on') || value.includes('javascript:')) node.removeAttribute(attribute.name)
    })
  })
  return template.innerHTML || '<p><br></p>'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function boolLike(value: unknown): boolean {
  return value === true || value === 'true' || value === '1' || value === 1
}

function uniqueMessages(values: string[]): string[] {
  const seen = new Set<string>()
  return values.filter((value) => {
    const text = value.trim()
    if (!text || seen.has(text)) return false
    seen.add(text)
    return true
  })
}

function fileNameWithoutExtension(value: string): string {
  return value.replace(/\.[^.]+$/, '') || 'documento'
}

function isPdfLikeDocument(name: string, extension: string): boolean {
  const lowerName = name.toLowerCase()
  const lowerExtension = extension.toLowerCase()
  return lowerExtension === 'pdf' || lowerExtension === 'p7m' || lowerName.endsWith('.pdf.p7m')
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 750)
}

function ToolbarButton({ title, onClick, children, disabled = false }:{title:string; onClick:()=>void; children:ReactNode; disabled?:boolean}) {
  return (
    <button className="iu-de-tool" type="button" onClick={onClick} title={title} aria-label={title} disabled={disabled}>
      {children}
    </button>
  )
}

function EmptyEditorState({ title, body, actionHref, actionLabel }:{title:string; body:string; actionHref:string; actionLabel:string}) {
  return (
    <main className="iu-content iu-doc-editor-page">
      <section className="iu-de-empty" role="alert">
        <AlertTriangle size={28}/>
        <h1>{title}</h1>
        <p>{body}</p>
        <a href={actionHref}><ArrowLeft size={15}/>{actionLabel}</a>
      </section>
    </main>
  )
}

function DocumentFacts({ data }:{data: DocumentEditorPayload}) {
  const doc = data.document
  return (
    <aside className="iu-de-side" aria-label="Dati documento">
      <section>
        <header><FileText size={16}/><strong>Documento</strong></header>
        <dl>
          <div><dt>Tipo</dt><dd>{doc.type || 'n.d.'}</dd></div>
          <div><dt>Formato</dt><dd>{doc.extension ? `.${doc.extension}` : 'n.d.'}</dd></div>
          <div><dt>Dimensione</dt><dd>{doc.size || 'n.d.'}</dd></div>
          <div><dt>Data documento</dt><dd>{doc.documentDate || doc.uploadedAt || 'n.d.'}</dd></div>
        </dl>
        {doc.tags.length ? <div className="iu-de-tags">{doc.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
      </section>
      <section>
        <header><ShieldCheck size={16}/><strong>Contesto</strong></header>
        <dl>
          <div><dt>Fascicolo</dt><dd>{data.fascicolo.ref || data.fascicolo.id || 'n.d.'}</dd></div>
          <div><dt>Cliente</dt><dd>{data.fascicolo.client || 'n.d.'}</dd></div>
          <div><dt>Ufficio</dt><dd>{data.fascicolo.court || 'n.d.'}</dd></div>
          <div><dt>N. registro</dt><dd>{data.fascicolo.rg || 'n.d.'}</dd></div>
        </dl>
      </section>
      {doc.portal.name || doc.portal.class || doc.portal.sender ? (
        <section>
          <header><UploadCloud size={16}/><strong>Portale</strong></header>
          <dl>
            <div><dt>Nome portale</dt><dd>{doc.portal.name || 'n.d.'}</dd></div>
            <div><dt>Classificazione</dt><dd>{doc.portal.class || 'n.d.'}</dd></div>
            <div><dt>Mittente</dt><dd>{doc.portal.sender || 'n.d.'}</dd></div>
            <div><dt>Data deposito</dt><dd>{doc.portal.date || 'n.d.'}</dd></div>
          </dl>
        </section>
      ) : null}
    </aside>
  )
}

export function DocumentEditorPage() {
  const route = useMemo(parseEditorRoute, [])
  const editorRef = useRef<HTMLDivElement | null>(null)
  const replaceFileRef = useRef<HTMLInputElement | null>(null)
  const autosaveRef = useRef<number | null>(null)
  const [data, setData] = useState<DocumentEditorPayload>(emptyDocumentEditorPayload)
  const [payloadLoading, setPayloadLoading] = useState(true)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [status, setStatus] = useState<EditorStatus>({ tone: 'loading', label: 'Caricamento editor' })
  const [warnings, setWarnings] = useState<string[]>([])
  const [stats, setStats] = useState<EditorStats>(defaultStats)
  const [dirty, setDirty] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState('')
  const [conversionLocked, setConversionLocked] = useState(false)
  const [conversionLockedReason, setConversionLockedReason] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [replaceTerm, setReplaceTerm] = useState('')
  const [fontFamily, setFontFamily] = useState<string>(FONT_FAMILY_OPTIONS[0].value)
  const [fontSize, setFontSize] = useState('12pt')
  const [lineHeight, setLineHeight] = useState('1.6')
  const [pagePreset, setPagePreset] = useState<string>('a4')
  const [zoom, setZoom] = useState('100')

  const updateStats = useCallback(() => {
    const text = editorRef.current?.innerText.trim() || ''
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0
    setStats({ words, chars: text.length, readingMinutes: Math.max(1, Math.ceil(words / 200)) })
  }, [])

  const saveDocument = useCallback(async (auto = false) => {
    if (!data.endpoints.save || !editorRef.current || !data.document.editable || conversionLocked) return
    if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
    setStatus({ tone: 'saving', label: auto ? 'Salvataggio automatico' : 'Salvataggio in corso' })
    try {
      const response = await fetch(data.endpoints.save, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ html: editorRef.current.innerHTML, auto }),
      })
      const payload = await response.json().catch(() => ({} as Record<string, unknown>))
      if (!response.ok || payload.ok === false) throw new Error(String(payload.errore || payload.messaggio || 'Salvataggio non riuscito.'))
      setDirty(false)
      const now = new Date()
      setLastSavedAt(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`)
      setStatus({ tone: 'success', label: auto ? 'Salvato automaticamente' : 'Salvato' })
      window.setTimeout(() => setStatus({ tone: 'neutral', label: 'Pronto' }), 2400)
    } catch (error) {
      setStatus({ tone: 'danger', label: error instanceof Error ? error.message : 'Errore di salvataggio' })
    }
  }, [conversionLocked, data.document.editable, data.endpoints.save])

  const scheduleAutosave = useCallback(() => {
    if (!data.document.editable || conversionLocked) return
    setDirty(true)
    setStatus({ tone: 'warning', label: 'Modifiche non salvate' })
    if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
    autosaveRef.current = window.setTimeout(() => void saveDocument(true), Math.max(8, data.capabilities.autosaveSeconds) * 1000)
  }, [conversionLocked, data.capabilities.autosaveSeconds, data.document.editable, saveDocument])

  const markChanged = useCallback(() => {
    updateStats()
    scheduleAutosave()
  }, [scheduleAutosave, updateStats])

  const runCommand = useCallback((command: string, value?: string) => {
    if (conversionLocked) return
    editorRef.current?.focus()
    document.execCommand(command, false, value)
    markChanged()
  }, [conversionLocked, markChanged])

  const applyInlineStyle = useCallback((style: InlineStylePatch, label: string) => {
    if (conversionLocked || !editorRef.current) return
    const root = editorRef.current
    const applyStyle = (element: HTMLElement) => {
      if (style.fontFamily) element.style.fontFamily = style.fontFamily
      if (style.fontSize) element.style.fontSize = style.fontSize
      if (style.lineHeight) element.style.lineHeight = style.lineHeight
    }
    const selection = window.getSelection()
    const selectionInEditor = Boolean(
      selection
      && selection.rangeCount
      && selection.anchorNode
      && selection.focusNode
      && root.contains(selection.anchorNode)
      && root.contains(selection.focusNode),
    )
    if (!selection || !selectionInEditor || selection.isCollapsed) {
      const targets = root.children.length ? Array.from(root.children) : [root]
      targets.forEach((node) => applyStyle(node as HTMLElement))
      markChanged()
      setStatus({ tone: 'warning', label: `${label} applicato al documento` })
      return
    }
    const range = selection.getRangeAt(0)
    const span = document.createElement('span')
    applyStyle(span)
    try {
      range.surroundContents(span)
    } catch {
      const fragment = range.extractContents()
      span.appendChild(fragment)
      range.insertNode(span)
    }
    selection.removeAllRanges()
    const nextRange = document.createRange()
    nextRange.selectNodeContents(span)
    selection.addRange(nextRange)
    markChanged()
    setStatus({ tone: 'warning', label: `${label} da salvare` })
  }, [conversionLocked, markChanged])

  const changeFontFamily = useCallback((value: string) => {
    setFontFamily(value)
    applyInlineStyle({ fontFamily: value }, 'Font')
  }, [applyInlineStyle])

  const changeFontSize = useCallback((value: string) => {
    setFontSize(value)
    applyInlineStyle({ fontSize: value }, 'Dimensione testo')
  }, [applyInlineStyle])

  const changeLineHeight = useCallback((value: string) => {
    setLineHeight(value)
    applyInlineStyle({ lineHeight: value }, 'Interlinea')
  }, [applyInlineStyle])

  const loadDocument = useCallback(async (payload: DocumentEditorPayload) => {
    if (!payload.endpoints.loadHtml || !payload.document.editable) return
    setConversionLocked(false)
    setConversionLockedReason('')
    setDocumentLoading(true)
    setStatus({ tone: 'loading', label: 'Caricamento contenuto' })
    try {
      const response = await fetch(payload.endpoints.loadHtml, {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const body = await response.json().catch(() => ({} as Record<string, unknown>))
      const html = String(body.html || '<p><br></p>')
      const sanitizedHtml = sanitizeHtml(html)
      if (editorRef.current) editorRef.current.innerHTML = sanitizedHtml
      const rawAvvisi = Array.isArray(body.avvisi) ? body.avvisi : []
      const avvisi = rawAvvisi.map((item: unknown) => String(item || '').trim()).filter(Boolean)
      const meta = isRecord(body.meta) ? body.meta : {}
      const editorDisabled = boolLike(meta.editor_disabled) || sanitizedHtml.includes('data-editor-disabled="true"')
      if (editorDisabled) {
        const metaReason = String(meta.editor_disabled_reason || '').trim()
        const reason = metaReason === 'layout PDF complesso'
          ? 'Il PDF contiene impaginazione complessa: uso l\'anteprima originale e blocco il salvataggio per evitare una ricostruzione diversa dal documento.'
          : 'Il PDF non espone testo modificabile affidabile: uso l\'anteprima originale e blocco il salvataggio per evitare testo corrotto.'
        setConversionLocked(true)
        setConversionLockedReason(reason)
        setWarnings(uniqueMessages([...payload.warnings, ...avvisi, reason]))
        updateStats()
        setDirty(false)
        setStatus({ tone: 'warning', label: 'Anteprima consigliata' })
        return
      }
      setWarnings(uniqueMessages([...payload.warnings, ...avvisi]))
      updateStats()
      setDirty(false)
      setStatus({ tone: 'neutral', label: 'Pronto' })
    } catch (error) {
      setWarnings((current) => [...current, error instanceof Error ? error.message : 'Contenuto non leggibile.'])
      setStatus({ tone: 'danger', label: 'Errore caricamento documento' })
    } finally {
      setDocumentLoading(false)
    }
  }, [updateStats])

  useEffect(() => {
    if (!route) {
      setPayloadLoading(false)
      return
    }
    let active = true
    setPayloadLoading(true)
    getDocumentEditorPayload(route.idFascicolo, route.idDocumento)
      .then((payload) => {
        if (!active) return
        setConversionLocked(false)
        setConversionLockedReason('')
        setData(payload)
        setWarnings(payload.warnings)
        if (!payload.notFound && payload.document.editable) void loadDocument(payload)
        if (!payload.notFound && !payload.document.editable) setStatus({ tone: 'warning', label: 'Documento non modificabile' })
      })
      .catch((error) => {
        if (!active) return
        setStatus({ tone: 'danger', label: error instanceof Error ? error.message : 'Dati editor non disponibili' })
      })
      .finally(() => {
        if (active) setPayloadLoading(false)
      })
    return () => { active = false }
  }, [loadDocument, route])

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!dirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => {
      window.removeEventListener('beforeunload', handler)
      if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
    }
  }, [dirty])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        void saveDocument(false)
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
        event.preventDefault()
        setSearchOpen(true)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [saveDocument])

  const exportFile = async (endpoint: string, extension: 'pdf' | 'docx') => {
    if (!endpoint || !editorRef.current || conversionLocked) return
    setStatus({ tone: 'saving', label: extension === 'pdf' ? 'Genero PDF' : 'Genero DOCX' })
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: extension === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ html: editorRef.current.innerHTML }),
      })
      if (!response.ok) throw new Error(await response.text())
      downloadBlob(await response.blob(), `${fileNameWithoutExtension(data.document.name)}.${extension}`)
      setStatus({ tone: 'success', label: extension === 'pdf' ? 'PDF pronto' : 'DOCX pronto' })
    } catch {
      setStatus({ tone: 'danger', label: extension === 'pdf' ? 'Errore export PDF' : 'Errore export DOCX' })
    }
  }

  const importFile = async (file?: File) => {
    if (!file || !editorRef.current || conversionLocked) return
    if (!window.confirm(`Sostituire il contenuto editor con "${file.name}"? Il salvataggio resta manuale o automatico.`)) return
    const lower = file.name.toLowerCase()
    const content = await file.text()
    const html = lower.endsWith('.html') || lower.endsWith('.htm')
      ? sanitizeHtml(content)
      : lower.endsWith('.md')
        ? markdownToHtml(content)
        : textToHtml(content)
    editorRef.current.innerHTML = html
    markChanged()
    setStatus({ tone: 'warning', label: 'Contenuto importato, da salvare' })
  }

  const insertLink = () => {
    const href = window.prompt('Inserisci URL del collegamento')
    if (!href) return
    runCommand('createLink', href)
  }

  const insertTable = () => {
    runCommand('insertHTML', '<table><tbody><tr><th>Intestazione</th><th>Intestazione</th></tr><tr><td>Testo</td><td>Testo</td></tr></tbody></table><p><br></p>')
  }

  const findText = (backwards = false) => {
    if (!searchTerm.trim()) return
    editorRef.current?.focus()
    const browserFind = (window as Window & typeof globalThis & {
      find?: (
        text: string,
        caseSensitive?: boolean,
        backwards?: boolean,
        wrapAround?: boolean,
        wholeWord?: boolean,
        searchInFrames?: boolean,
        showDialog?: boolean
      ) => boolean
    }).find
    const found = browserFind ? browserFind(searchTerm, false, backwards, true, false, false, false) : false
    setStatus(found ? { tone: 'neutral', label: 'Occorrenza selezionata' } : { tone: 'warning', label: 'Testo non trovato' })
  }

  const replaceSelection = () => {
    const selection = window.getSelection()
    if (!selection || !selection.rangeCount || !editorRef.current?.contains(selection.anchorNode)) {
      setStatus({ tone: 'warning', label: "Seleziona un testo nell'editor" })
      return
    }
    const range = selection.getRangeAt(0)
    range.deleteContents()
    range.insertNode(document.createTextNode(replaceTerm))
    selection.removeAllRanges()
    range.collapse(false)
    selection.addRange(range)
    markChanged()
    setStatus({ tone: 'warning', label: 'Sostituzione da salvare' })
  }

  const handlePaste = (event: ClipboardEvent<HTMLDivElement>) => {
    if (conversionLocked) return
    const html = event.clipboardData.getData('text/html')
    const plain = event.clipboardData.getData('text/plain')
    if (!html && !plain) return
    event.preventDefault()
    document.execCommand('insertHTML', false, html ? sanitizeHtml(html) : textToHtml(plain))
    markChanged()
  }

  if (!route) {
    return <EmptyEditorState title="Route editor non valida" body="La pagina richiesta non corrisponde a un documento del fascicolo." actionHref="/fascicoli" actionLabel="Torna ai fascicoli"/>
  }
  if (payloadLoading && !data.document.id) {
    return (
      <main className="iu-content iu-doc-editor-page">
        <section className="iu-de-empty"><LoaderCircle className="iu-spin" size={28}/><h1>Caricamento editor</h1><p>Sto preparando i dati reali del documento.</p></section>
      </main>
    )
  }
  if (data.notFound) {
    return <EmptyEditorState title="Documento non trovato" body={data.message || 'Il documento non risulta disponibile nel fascicolo.'} actionHref={data.fascicolo.detailHref || '/fascicoli'} actionLabel="Torna al fascicolo"/>
  }

  const doc = data.document
  const pdfPreviewMode = isPdfLikeDocument(doc.name, doc.extension)
  const editorEnabled = doc.editable && !conversionLocked
  const lockedReason = conversionLocked
    ? conversionLockedReason || 'Il documento non espone testo affidabile per la modifica inline.'
    : doc.lockedReason
  const statusClass = `iu-de-status iu-de-status--${status.tone}`
  const selectedPage = PAGE_PRESETS.find((preset) => preset.id === pagePreset) || PAGE_PRESETS[0]
  const paperStyle = {
    '--iu-de-font-family': fontFamily,
    '--iu-de-font-size': fontSize,
    '--iu-de-line-height': lineHeight,
    '--iu-de-paper-width': selectedPage.width,
    '--iu-de-paper-min-height': selectedPage.minHeight,
    '--iu-de-paper-padding-x': selectedPage.paddingX,
    '--iu-de-paper-padding-y': selectedPage.paddingY,
    '--iu-de-zoom': `${Number(zoom || 100) / 100}`,
  } as React.CSSProperties

  return (
    <main className="iu-content iu-doc-editor-page">
      <section className="iu-de-hero">
        <div>
          <span className="iu-de-eyebrow"><FileText size={16}/> Editor professionale</span>
          <h1>{doc.name}</h1>
          <p>
            <Badge tone={editorEnabled ? 'success' : 'warning'}>{editorEnabled ? 'Modificabile' : pdfPreviewMode ? 'Anteprima nativa' : 'Bloccato'}</Badge>
            <span>{data.fascicolo.ref || data.fascicolo.id} - {data.fascicolo.client || data.fascicolo.title}</span>
          </p>
        </div>
        <nav aria-label="Azioni documento">
          <a href={data.fascicolo.detailHref}><ArrowLeft size={15}/> Fascicolo</a>
          {doc.actions.preview ? <a href={doc.actions.preview}><Eye size={15}/> Anteprima</a> : null}
          {doc.actions.sign ? <a href={doc.actions.sign}><ShieldCheck size={15}/> Firma</a> : null}
          {doc.actions.download ? <a href={doc.actions.download}><Download size={15}/> Scarica</a> : null}
          <button type="button" onClick={() => void saveDocument(false)} disabled={!editorEnabled}><Save size={15}/> Salva</button>
        </nav>
      </section>

      {warnings.length ? (
        <section className="iu-de-warnings" aria-label="Avvisi editor">
          {warnings.map((warning) => <span key={warning}><AlertTriangle size={15}/>{warning}</span>)}
        </section>
      ) : null}

      {!editorEnabled ? (
        <>
          <section className="iu-de-locked" role="alert">
            <ShieldCheck size={24}/>
            <div>
              <h2>{pdfPreviewMode ? 'Anteprima PDF fedele all\'originale' : 'Documento non modificabile in editor'}</h2>
              <p>{lockedReason || 'Apri il documento in anteprima o scaricalo per lavorarlo con un applicativo esterno.'}</p>
              <a href={doc.actions.preview || data.fascicolo.detailHref}><Eye size={15}/>{pdfPreviewMode ? 'Apri PDF originale' : 'Apri anteprima'}</a>
            </div>
          </section>
          {doc.actions.preview ? (
            <section className="iu-de-workbench iu-de-workbench--preview">
              <DocumentFacts data={data}/>
              <section className="iu-de-preview-shell">
                <div className="iu-de-paper-head">
                  <span>{pdfPreviewMode ? 'Anteprima originale del PDF' : 'Anteprima consultazione'}</span>
                  <Badge tone={doc.signed || doc.extension === 'p7m' ? 'warning' : 'neutral'}>{doc.signed || doc.extension === 'p7m' ? 'Documento firmato' : pdfPreviewMode ? 'PDF nativo' : 'Sola lettura'}</Badge>
                </div>
                <iframe
                  className="iu-de-preview-frame"
                  src={doc.actions.preview}
                  title={`Anteprima ${doc.name}`}
                />
              </section>
            </section>
          ) : null}
        </>
      ) : (
        <>
          <section className="iu-de-toolbar" aria-label="Barra strumenti editor">
            <label className="iu-de-field iu-de-field--style"><span>Stile</span>
              <select aria-label="Stile paragrafo" onChange={(event) => runCommand('formatBlock', event.target.value)} defaultValue="p">
                <option value="p">Normale</option>
                <option value="h1">Titolo 1</option>
                <option value="h2">Titolo 2</option>
                <option value="h3">Titolo 3</option>
                <option value="blockquote">Citazione</option>
              </select>
            </label>
            <label className="iu-de-field iu-de-field--font"><span>Font</span>
              <select aria-label="Font testo" value={fontFamily} onChange={(event) => changeFontFamily(event.target.value)}>
                {FONT_FAMILY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="iu-de-field iu-de-field--size"><span>Dimensione</span>
              <select aria-label="Dimensione testo" value={fontSize} onChange={(event) => changeFontSize(event.target.value)}>
                {FONT_SIZE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="iu-de-field iu-de-field--line"><span>Interlinea</span>
              <select aria-label="Interlinea" value={lineHeight} onChange={(event) => changeLineHeight(event.target.value)}>
                {LINE_HEIGHT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <ToolbarButton title="Grassetto" onClick={() => runCommand('bold')}><Bold size={16}/></ToolbarButton>
            <ToolbarButton title="Corsivo" onClick={() => runCommand('italic')}><Italic size={16}/></ToolbarButton>
            <ToolbarButton title="Sottolineato" onClick={() => runCommand('underline')}><Underline size={16}/></ToolbarButton>
            <ToolbarButton title="Barrato" onClick={() => runCommand('strikeThrough')}><Strikethrough size={16}/></ToolbarButton>
            <span className="iu-de-separator"/>
            <ToolbarButton title="Allinea a sinistra" onClick={() => runCommand('justifyLeft')}><AlignLeft size={16}/></ToolbarButton>
            <ToolbarButton title="Centra" onClick={() => runCommand('justifyCenter')}><AlignCenter size={16}/></ToolbarButton>
            <ToolbarButton title="Allinea a destra" onClick={() => runCommand('justifyRight')}><AlignRight size={16}/></ToolbarButton>
            <ToolbarButton title="Giustifica" onClick={() => runCommand('justifyFull')}><AlignJustify size={16}/></ToolbarButton>
            <span className="iu-de-separator"/>
            <ToolbarButton title="Elenco puntato" onClick={() => runCommand('insertUnorderedList')}><List size={16}/></ToolbarButton>
            <ToolbarButton title="Elenco numerato" onClick={() => runCommand('insertOrderedList')}><ListOrdered size={16}/></ToolbarButton>
            <ToolbarButton title="Tabella" onClick={insertTable}><Table size={16}/></ToolbarButton>
            <ToolbarButton title="Collegamento" onClick={insertLink}><Link size={16}/></ToolbarButton>
            <span className="iu-de-separator"/>
            <label className="iu-de-color" title="Colore testo"><Palette size={15}/><input type="color" onChange={(event) => runCommand('foreColor', event.target.value)} defaultValue="#111827"/></label>
            <label className="iu-de-color" title="Evidenziatore"><Highlighter size={15}/><input type="color" onChange={(event) => runCommand('hiliteColor', event.target.value)} defaultValue="#fef3c7"/></label>
            <span className="iu-de-separator"/>
            <ToolbarButton title="Annulla" onClick={() => runCommand('undo')}><Undo2 size={16}/></ToolbarButton>
            <ToolbarButton title="Ripeti" onClick={() => runCommand('redo')}><Redo2 size={16}/></ToolbarButton>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => setSearchOpen((value) => !value)}><Search size={15}/> Cerca</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => replaceFileRef.current?.click()}><UploadCloud size={15}/> Importa</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => void exportFile(data.endpoints.exportPdf, 'pdf')}><FileDown size={15}/> PDF</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => void exportFile(data.endpoints.exportDocx, 'docx')}><FileDown size={15}/> DOCX</button>
          </section>

          <section className="iu-de-meta-row" aria-label="Stato editor">
            <span className={statusClass}>{status.tone === 'success' ? <CheckCircle2 size={15}/> : status.tone === 'loading' || status.tone === 'saving' ? <LoaderCircle className="iu-spin" size={15}/> : <Pilcrow size={15}/>} {status.label}</span>
            <span>{stats.words} parole - {stats.chars} caratteri - {stats.readingMinutes} min</span>
            <label><Heading1 size={14}/> <select value={pagePreset} onChange={(event) => setPagePreset(event.target.value)}>{PAGE_PRESETS.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}</select></label>
            <label><Eye size={14}/> <select value={zoom} onChange={(event) => setZoom(event.target.value)}><option value="90">90%</option><option value="100">100%</option><option value="110">110%</option><option value="125">125%</option></select></label>
            <span>{lastSavedAt ? `Ultimo salvataggio ${lastSavedAt}` : dirty ? 'Salvataggio pendente' : 'Nessuna modifica pendente'}</span>
          </section>

          {searchOpen ? (
            <section className="iu-de-search-panel" aria-label="Cerca e sostituisci">
              <label><span>Cerca</span><input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') findText(false) }}/></label>
              <label><span>Sostituisci con</span><input value={replaceTerm} onChange={(event) => setReplaceTerm(event.target.value)}/></label>
              <button type="button" onClick={() => findText(false)}><Search size={15}/> Successivo</button>
              <button type="button" onClick={replaceSelection}><Replace size={15}/> Sostituisci</button>
            </section>
          ) : null}

          <section className="iu-de-workbench">
            <DocumentFacts data={data}/>
            <section className="iu-de-paper-shell" style={paperStyle}>
              <div className="iu-de-paper-head">
                <span>{doc.name}</span>
                <Badge tone={data.contracts.mock_fallback ? 'danger' : 'success'}>{data.contracts.mock_fallback ? 'Dati non reali' : 'Dati reali'}</Badge>
              </div>
              <div className="iu-de-paper">
                {documentLoading ? <div className="iu-de-loader"><LoaderCircle className="iu-spin" size={24}/><span>Caricamento contenuto...</span></div> : null}
                <div
                  ref={editorRef}
                  className="iu-de-editable"
                  contentEditable={editorEnabled}
                  suppressContentEditableWarning
                  role="textbox"
                  aria-multiline="true"
                  aria-label={`Contenuto modificabile ${doc.name}`}
                  onInput={markChanged}
                  onPaste={handlePaste}
                />
              </div>
            </section>
          </section>

          <input
            ref={replaceFileRef}
            type="file"
            hidden
            accept=".txt,.html,.htm,.md"
            onChange={(event) => {
              void importFile(event.target.files?.[0])
              event.target.value = ''
            }}
          />
        </>
      )}

      <FloatingLex
        context="editor-documento"
        title="Lex AI editor"
        body="Posso aiutarti a controllare coerenza dell atto, punti mancanti, stile professionale e collegamenti con il fascicolo aperto."
        primaryHref={data.fascicolo.detailHref}
        primaryLabel="Fascicolo"
        secondaryHref={`/global-search?q=${encodeURIComponent(doc.name || data.fascicolo.ref)}`}
        secondaryLabel="Cerca collegati"
      />
    </main>
  )
}
