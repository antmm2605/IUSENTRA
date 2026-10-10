import { useCallback, useEffect, useMemo, useRef, useState, type ClipboardEvent, type FormEvent, type ReactNode } from 'react'
import { editTable, type TableAction } from '../editorTableGrid'
import { EditorHistory, editorCaret, restoreEditorCaret } from '../editorHistory'
import { clearSpellingMarks, showSpellingMarks, documentLanguageSource, grammarRanges, type SpellingMark } from '../editorSpelling'
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  AlertTriangle,
  ArrowLeft,
  Bold,
  Check,
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileDown,
  FileText,
  Heading1,
  Highlighter,
  ImagePlus,
  Italic,
  Link,
  List,
  ListChecks,
  ListOrdered,
  LoaderCircle,
  Maximize2,
  Mic,
  Minimize2,
  Palette,
  Pilcrow,
  Printer,
  Redo2,
  Replace,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Strikethrough,
  Table,
  Underline,
  X,
  Undo2,
  UploadCloud,
  Wand2,
  XCircle,
} from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import {
  emptyDocumentEditorPayload,
  getDocumentEditorPayload,
  type DocumentEditorPayload,
} from '../documentEditorData'
import './DocumentEditorPage.css'
import { GRUPPI_CARATTERI } from './documentCapture/ocrBarraVoci'

type EditorRoute = { idFascicolo: string; idDocumento: string } | null
type EditorStatus = { tone: 'loading' | 'saving' | 'success' | 'warning' | 'danger' | 'neutral'; label: string }
type EditorStats = { words: number; chars: number; readingMinutes: number }
type InlineStylePatch = { fontFamily?: string; fontSize?: string; lineHeight?: string }
type PageLayout = { width: number; height: number; top: number; bottom: number; left: number; right: number }
const DEFAULT_PAGE_LAYOUT: PageLayout = { width: 210, height: 297, top: 25, bottom: 25, left: 25, right: 25 }

function nativePageLayout(page: Element | null): PageLayout {
  const read = (attribute: string, fallback: number) => {
    const raw = page?.getAttribute(`data-${attribute}`)
    const value = raw === null || raw === undefined ? fallback : Number(raw) * 25.4 / 72
    return Number.isFinite(value) ? value : fallback
  }
  return { width: read('larghezza', 210), height: read('altezza', 297), top: read('margine-alto', 25), bottom: read('margine-basso', 25), left: read('margine-sinistro', 25), right: read('margine-destro', 25) }
}
type EditorAITemplate = { id: string; titolo: string; area: string; canale_telematico: string }
type EditorAIDocument = { document_id: string; filename: string; status: string; page_count: number | null; sha256: string }
type EditorAISource = { id: string; source_type: string; source_id: string; document_id: string; page_number: number | null; quote: string; sha256: string; reason: string }
type EditorAIProposal = {
  id: string
  status: string
  operation_type: string
  find_text: string
  replace_text: string
  insert_text: string
  reason: string
}
type EditorAIBootstrap = {
  templates: EditorAITemplate[]
  documents: EditorAIDocument[]
  missing_fields: string[]
}
type EditorAIDetail = {
  sources: EditorAISource[]
  edit_proposals: EditorAIProposal[]
  versions: Array<{ id: string; version_number: number; source: string; created_at: string }>
}
type PdfEditorTool = 'text' | 'highlight' | 'cover'

//: Sotto questa frazione della pagina il trascinamento non e' un
//: trascinamento: e' un clic, e vale il riquadro di sempre.
const MISURA_MINIMA_RIQUADRO = 0.004

//: Il riquadro di chi clicca e basta, in frazione di pagina.
const RIQUADRO_PREDEFINITO = { width: 0.22, height: 0.045 }
type PdfAnnotation = {
  id: string
  type: PdfEditorTool
  page: number
  x: number
  y: number
  width?: number
  height?: number
  text?: string
  fontSizePt?: number
  color?: string
  fillColor?: string
}
type PdfMeta = {
  pageCount: number
  pages: Array<{ number: number; width: number; height: number }>
}
type IusentraVoiceInputService = {
  startForTarget?: (target: HTMLElement, options?: {
    context?: string
    lang?: string
    silenceMs?: number
    onStart?: () => void
    onInserted?: (text: string) => void
  }) => Promise<string>
}

declare global {
  interface Window {
    IusentraVoiceInput?: IusentraVoiceInputService
  }
}

const defaultStats: EditorStats = { words: 0, chars: 0, readingMinutes: 1 }
const FONT_FAMILY_OPTIONS = [
  { label: 'Times New Roman', value: '"Times New Roman", Times, serif' },
  { label: 'Arial', value: 'Arial, Helvetica, sans-serif' },
  { label: 'Calibri', value: 'Calibri, "Segoe UI", sans-serif' },
  { label: 'Garamond', value: 'Garamond, "Times New Roman", serif' },
  { label: 'Georgia', value: 'Georgia, "Times New Roman", serif' },
  { label: 'Courier New', value: '"Courier New", Courier, monospace' },
].concat(GRUPPI_CARATTERI.flatMap((gruppo) => gruppo.caratteri
  .filter((nome) => !['Times New Roman', 'Arial', 'Calibri', 'Garamond', 'Georgia', 'Courier New'].includes(nome))
  .map((nome) => ({ label: nome, value: `"${nome}", ${gruppo.gruppo === 'A spaziatura fissa' ? 'monospace' : gruppo.gruppo === 'Senza grazie' ? 'sans-serif' : 'serif'}` }))))
const FONT_SIZE_OPTIONS = Array.from({ length: 70 }, (_, index) => `${index + 3}pt`)
const ZOOM_OPTIONS = Array.from({ length: 36 }, (_, index) => String(25 + index * 5))
const LINE_HEIGHT_OPTIONS = [
  { label: 'Singola', value: '1' },
  { label: '1,15', value: '1.15' },
  { label: '1,25', value: '1.25' },
  { label: '1,5', value: '1.5' },
  { label: '1,6', value: '1.6' },
  { label: '1,75', value: '1.75' },
  { label: 'Doppia', value: '2' },
  { label: '2,5', value: '2.5' },
  { label: 'Tripla', value: '3' },
  { label: '3,5', value: '3.5' },
  { label: 'Quadrupla', value: '4' },
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

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function boolLike(value: unknown): boolean {
  return value === true || value === 'true' || value === '1' || value === 1
}

function numberOrNull(value: unknown): number | null {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function shortHash(value: string): string {
  const clean = value.trim()
  return clean.length > 12 ? clean.slice(0, 12) : clean
}

function jsonHeaders(): HeadersInit {
  return {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  }
}

async function fetchEditorAIJson(endpoint: string, init?: RequestInit): Promise<Record<string, unknown>> {
  const extraHeaders = init?.headers instanceof Headers
    ? Object.fromEntries(init.headers.entries())
    : Array.isArray(init?.headers)
      ? Object.fromEntries(init.headers)
      : (init?.headers || {})
  const response = await fetch(endpoint, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...init,
    headers: { ...jsonHeaders(), ...extraHeaders },
  })
  const body = await response.json().catch(() => ({} as Record<string, unknown>))
  if (!response.ok) throw new Error(text(body.detail || body.errore || body.message, `Operazione non riuscita: HTTP ${response.status}`))
  return isRecord(body) ? body : {}
}

function normalizeEditorAIBootstrap(payload: Record<string, unknown>): EditorAIBootstrap {
  const templates = Array.isArray(payload.templates) ? payload.templates : []
  const documents = Array.isArray(payload.documents) ? payload.documents : []
  const missingFields = Array.isArray(payload.missing_fields) ? payload.missing_fields : []
  return {
    templates: templates
      .filter(isRecord)
      .map((item) => ({
        id: text(item.id),
        titolo: text(item.titolo, text(item.id, 'Template atto')),
        area: text(item.area),
        canale_telematico: text(item.canale_telematico),
      }))
      .filter((item) => item.id),
    documents: documents
      .filter(isRecord)
      .map((item) => ({
        document_id: text(item.document_id),
        filename: text(item.filename, 'Documento fascicolo'),
        status: text(item.status),
        page_count: numberOrNull(item.page_count),
        sha256: text(item.sha256),
      }))
      .filter((item) => item.document_id),
    missing_fields: missingFields.map((item) => text(item)).filter(Boolean),
  }
}

function normalizeEditorAIDetail(payload: Record<string, unknown>): EditorAIDetail {
  const sources = Array.isArray(payload.sources) ? payload.sources : []
  const proposals = Array.isArray(payload.edit_proposals) ? payload.edit_proposals : Array.isArray(payload.proposals) ? payload.proposals : []
  const versions = Array.isArray(payload.versions) ? payload.versions : []
  return {
    sources: sources.filter(isRecord).map((item) => ({
      id: text(item.id),
      source_type: text(item.source_type),
      source_id: text(item.source_id),
      document_id: text(item.document_id),
      page_number: numberOrNull(item.page_number),
      quote: text(item.quote),
      sha256: text(item.sha256),
      reason: text(item.reason),
    })),
    edit_proposals: proposals.filter(isRecord).map((item) => ({
      id: text(item.id),
      status: text(item.status),
      operation_type: text(item.operation_type),
      find_text: text(item.find_text),
      replace_text: text(item.replace_text),
      insert_text: text(item.insert_text),
      reason: text(item.reason),
    })).filter((item) => item.id),
    versions: versions.filter(isRecord).map((item) => ({
      id: text(item.id),
      version_number: Number(item.version_number || 0),
      source: text(item.source),
      created_at: text(item.created_at),
    })),
  }
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

function isEmlDocument(name: string, extension: string): boolean {
  return extension.toLowerCase() === 'eml' || name.toLowerCase().endsWith('.eml')
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

function normalizePdfMeta(payload: unknown): PdfMeta {
  const row = isRecord(payload) ? payload : {}
  const pages = Array.isArray(row.pages) ? row.pages : []
  const normalizedPages = pages
    .filter(isRecord)
    .map((item) => ({
      number: Number(item.number || 0),
      width: Number(item.width || 0),
      height: Number(item.height || 0),
    }))
    .filter((item) => item.number > 0 && item.width > 0 && item.height > 0)
  return {
    pageCount: Number(row.pageCount || normalizedPages.length || 0),
    pages: normalizedPages,
  }
}

function newPdfAnnotationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `pdf-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function ToolbarButton({ title, onClick, children, disabled = false }:{title:string; onClick:()=>void; children:ReactNode; disabled?:boolean}) {
  return (
    <button className="iu-de-tool" type="button" onMouseDown={(event) => event.preventDefault()} onClick={onClick} title={title} aria-label={title} disabled={disabled}>
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
  const saveInFlightRef = useRef(false)
  const editRevisionRef = useRef(0)
  const tableRangeRef = useRef<Range | null>(null)
  const editorRangeRef = useRef<Range | null>(null)
  const editorHistoryRef = useRef(new EditorHistory())
  const linkRangeRef = useRef<Range | null>(null)
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkExisting, setLinkExisting] = useState(false)
  const [linkUrl, setLinkUrl] = useState('')
  const [linkText, setLinkText] = useState('')
  const imageFileRef = useRef<HTMLInputElement | null>(null)
  const imageRangeRef = useRef<Range | null>(null)
  const languageTimerRef = useRef<number | null>(null)
  const languageRequestRef = useRef<AbortController | null>(null)
  const phraseRequestRef = useRef<AbortController | null>(null)
  const [spellingEnabled, setSpellingEnabled] = useState(true)
  const [spellingResults, setSpellingResults] = useState<Array<{ parola: string; suggerimenti: string[] }>>([])
  const [languageError, setLanguageError] = useState('')
  const [phraseSuggestion, setPhraseSuggestion] = useState('')
  const [phraseLoading, setPhraseLoading] = useState(false)
  const [phraseCopied, setPhraseCopied] = useState(false)
  const spellingMarksRef = useRef<SpellingMark[]>([])
  const [grammarLoading, setGrammarLoading] = useState(false)
  const [grammarNotice, setGrammarNotice] = useState('')
  const [grammarMarks, setGrammarMarks] = useState<SpellingMark[]>([])
  const grammarRequestRef = useRef<AbortController | null>(null)
  const [spellingChoice, setSpellingChoice] = useState<{ mark: SpellingMark; x: number; y: number } | null>(null)
  const lineHeightRangeRef = useRef<Range | null>(null)
  const [tablePickerOpen, setTablePickerOpen] = useState(false)
  const [tableContext, setTableContext] = useState<{ table: HTMLTableElement; cell: HTMLTableCellElement } | null>(null)
  const [tableRows, setTableRows] = useState('3')
  const [tableColumns, setTableColumns] = useState('2')
  const [tableHeader, setTableHeader] = useState(true)
  const [data, setData] = useState<DocumentEditorPayload>(emptyDocumentEditorPayload)
  const [payloadLoading, setPayloadLoading] = useState(true)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [pendingImportFile, setPendingImportFile] = useState<File | null>(null)
  const [status, setStatus] = useState<EditorStatus>({ tone: 'loading', label: 'Caricamento editor' })
  const [warnings, setWarnings] = useState<string[]>([])
  const [stats, setStats] = useState<EditorStats>(defaultStats)
  const [dirty, setDirty] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState('')
  const [conversionLocked, setConversionLocked] = useState(false)
  const [conversionLockedReason, setConversionLockedReason] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [documentFactsOpen, setDocumentFactsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [replaceTerm, setReplaceTerm] = useState('')
  const [fontFamily, setFontFamily] = useState<string>(FONT_FAMILY_OPTIONS[0].value)
  const [fontSize, setFontSize] = useState('12pt')
  const [lineHeight, setLineHeight] = useState('1.6')
  const [customLineHeight, setCustomLineHeight] = useState('1,6')
  const [customLineHeightOpen, setCustomLineHeightOpen] = useState(false)
  const [pagePreset, setPagePreset] = useState<string>('a4')
  const [pageLayout, setPageLayout] = useState<PageLayout>(DEFAULT_PAGE_LAYOUT)
  const originalSectionLayoutsRef = useRef(new Map<HTMLElement, PageLayout>())
  const pageLayoutRef = useRef({ layout: DEFAULT_PAGE_LAYOUT, changed: false })
  const originalLayoutRef = useRef<PageLayout>(DEFAULT_PAGE_LAYOUT)
  const [layoutOpen, setLayoutOpen] = useState(false)
  const [layoutDraft, setLayoutDraft] = useState<PageLayout>(DEFAULT_PAGE_LAYOUT)
  const [printPreviewUrl, setPrintPreviewUrl] = useState('')
  const printRequestRef = useRef<AbortController | null>(null)
  const printFrameRef = useRef<HTMLIFrameElement | null>(null)
  const [printLoading, setPrintLoading] = useState(false)
  const [printError, setPrintError] = useState('')
  const [printPages, setPrintPages] = useState(0)
  const [printPage, setPrintPage] = useState('1')
  const [printZoom, setPrintZoom] = useState('fit')
  const printWhenReadyRef = useRef(false)
  const [zoom, setZoom] = useState('100')
  const [editorAiOpen, setEditorAiOpen] = useState(false)
  // Tutto schermo: la pagina dell'editor occupa lo schermo (API Fullscreen; dove manca, ad esempio
  // su iPhone, la pagina copre comunque la finestra e si chiude con Esc o con lo stesso pulsante).
  const paginaRef = useRef<HTMLElement | null>(null)
  const [tuttoSchermo, setTuttoSchermo] = useState(false)
  useEffect(() => {
    const allinea = () => setTuttoSchermo(Boolean(document.fullscreenElement) || paginaRef.current?.classList.contains('is-tutto-schermo') === true)
    const esci = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && paginaRef.current?.classList.contains('is-tutto-schermo')) {
        paginaRef.current.classList.remove('is-tutto-schermo')
        setTuttoSchermo(false)
      }
    }
    document.addEventListener('fullscreenchange', allinea)
    document.addEventListener('keydown', esci)
    return () => { document.removeEventListener('fullscreenchange', allinea); document.removeEventListener('keydown', esci) }
  }, [])
  const cambiaTuttoSchermo = async () => {
    const pagina = paginaRef.current
    if (!pagina) return
    if (document.fullscreenElement) { await document.exitFullscreen().catch(() => undefined); return }
    if (pagina.classList.contains('is-tutto-schermo')) { pagina.classList.remove('is-tutto-schermo'); setTuttoSchermo(false); return }
    if (pagina.requestFullscreen) {
      try { await pagina.requestFullscreen(); return } catch { /* ripiego sotto */ }
    }
    pagina.classList.add('is-tutto-schermo')
    setTuttoSchermo(true)
  }
  const [editorAiBootstrapped, setEditorAiBootstrapped] = useState(false)
  const [editorAiLoading, setEditorAiLoading] = useState(false)
  const [editorAiError, setEditorAiError] = useState('')
  const [editorAiBootstrap, setEditorAiBootstrap] = useState<EditorAIBootstrap>({ templates: [], documents: [], missing_fields: [] })
  const [editorAiDetail, setEditorAiDetail] = useState<EditorAIDetail>({ sources: [], edit_proposals: [], versions: [] })
  const [editorAiTemplateId, setEditorAiTemplateId] = useState('')
  const [editorAiTipoAtto, setEditorAiTipoAtto] = useState('')
  const [editorAiInstructions, setEditorAiInstructions] = useState('')
  const [editorAiDocumentIds, setEditorAiDocumentIds] = useState<string[]>([])
  const [editorAiEditInstructions, setEditorAiEditInstructions] = useState('')
  const [voiceDictating, setVoiceDictating] = useState(false)
  const [pdfEditorOpen, setPdfEditorOpen] = useState(false)
  const [pdfMeta, setPdfMeta] = useState<PdfMeta>({ pageCount: 0, pages: [] })
  const [pdfPage, setPdfPage] = useState(1)
  const [pdfTool, setPdfTool] = useState<PdfEditorTool>('text')
  const [pdfText, setPdfText] = useState('')
  const [pdfFontSize, setPdfFontSize] = useState(12)
  const [pdfTextColor, setPdfTextColor] = useState('#111827')
  const [pdfFillColor, setPdfFillColor] = useState('#fef3c7')
  const [pdfAnnotations, setPdfAnnotations] = useState<PdfAnnotation[]>([])
  const [pdfBozza, setPdfBozza] = useState<{ x: number; y: number; x1: number; y1: number } | null>(null)
  const pdfTrascinaRef = useRef<{ x: number; y: number } | null>(null)
  const [pdfSaving, setPdfSaving] = useState(false)
  const [pdfStatus, setPdfStatus] = useState('')
  const [pdfRevision, setPdfRevision] = useState(Date.now())

  const updateStats = useCallback(() => {
    const root = editorRef.current
    let text = root?.innerText.trim() || ''
    if (root?.querySelector('[data-iu-word-region]')) {
      const body = root.cloneNode(true) as HTMLElement
      body.querySelectorAll('[data-iu-word-region],[data-iu-word-variants]').forEach((node) => node.remove())
      body.querySelectorAll('p,h1,h2,h3,li,td,section').forEach((node) => node.appendChild(document.createTextNode('\n')))
      text = (body.textContent || '').trim()
    }
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0
    setStats({ words, chars: text.length, readingMinutes: Math.max(1, Math.ceil(words / 200)) })
  }, [])

  const serializeEditorHtml = useCallback(() => {
    const root = editorRef.current?.cloneNode(true) as HTMLElement | undefined
    if (!root) return ''
    let pages = Array.from(root.querySelectorAll<HTMLElement>('section.iu-doc-pagina'))
    if (!pages.length) {
      const page = document.createElement('section')
      page.className = 'iu-doc-pagina'
      page.setAttribute('data-pagina', '1')
      page.style.fontFamily = 'Times New Roman'
      page.style.fontSize = '12pt'
      page.style.lineHeight = '1.6'
      while (root.firstChild) page.appendChild(root.firstChild)
      root.appendChild(page)
      pages = [page]
    }
    const config = pageLayoutRef.current
    for (const page of pages) {
      if (!config.changed && page.hasAttribute('data-larghezza')) continue
      for (const [key, attribute] of [['width', 'larghezza'], ['height', 'altezza'], ['top', 'margine-alto'], ['bottom', 'margine-basso'], ['left', 'margine-sinistro'], ['right', 'margine-destro']] as const) {
        page.setAttribute(`data-${attribute}`, String(config.layout[key] * 72 / 25.4))
      }
    }
    return root.innerHTML
  }, [])

  const saveDocument = useCallback(async (auto = false) => {
    if (!data.endpoints.save || !editorRef.current || !data.document.editable || conversionLocked) return
    if (saveInFlightRef.current) {
      if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
      autosaveRef.current = window.setTimeout(() => void saveDocument(auto), 500)
      return
    }
    if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
    const submittedRevision = editRevisionRef.current
    saveInFlightRef.current = true
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
        body: JSON.stringify({ html: serializeEditorHtml(), auto }),
      })
      const payload = await response.json().catch(() => ({} as Record<string, unknown>))
      if (!response.ok || payload.ok === false) throw new Error(String(payload.errore || payload.messaggio || 'Salvataggio non riuscito.'))
      if (text(payload.nome)) setData((current) => ({ ...current, document: { ...current.document, name: text(payload.nome), extension: 'docx' } }))
      const hasNewEdits = editRevisionRef.current !== submittedRevision
      setDirty(hasNewEdits)
      const now = new Date()
      setLastSavedAt(`${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`)
      setStatus(hasNewEdits
        ? { tone: 'warning', label: 'Nuove modifiche da salvare' }
        : { tone: 'success', label: auto ? 'Salvato automaticamente' : 'Salvato' })
      if (!hasNewEdits) window.setTimeout(() => {
        if (editRevisionRef.current === submittedRevision && !saveInFlightRef.current) {
          setStatus({ tone: 'neutral', label: 'Pronto' })
        }
      }, 2400)
    } catch (error) {
      setStatus({ tone: 'danger', label: error instanceof Error ? error.message : 'Errore di salvataggio' })
    } finally {
      saveInFlightRef.current = false
    }
  }, [conversionLocked, data.document.editable, data.endpoints.save, serializeEditorHtml])

  const scheduleAutosave = useCallback(() => {
    if (!data.document.editable || conversionLocked) return
    editRevisionRef.current += 1
    setDirty(true)
    setStatus({ tone: 'warning', label: 'Modifiche non salvate' })
    if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
    autosaveRef.current = window.setTimeout(() => void saveDocument(true), Math.max(8, data.capabilities.autosaveSeconds) * 1000)
  }, [conversionLocked, data.capabilities.autosaveSeconds, data.document.editable, saveDocument])

  const markChanged = useCallback((group = '') => {
    setGrammarNotice('')
    grammarRequestRef.current?.abort()
    setGrammarLoading(false)
    setGrammarMarks([])
    setSpellingChoice(null)
    spellingMarksRef.current = spellingMarksRef.current.filter((mark) => mark.range.startContainer.isConnected && mark.range.toString() === mark.word)
    showSpellingMarks(spellingMarksRef.current)
    const root = editorRef.current
    const node = window.getSelection()?.anchorNode
    const element = node instanceof Element ? node : node?.parentElement
    const region = element?.closest<HTMLElement>('[data-iu-word-region][data-iu-word-key]')
    if (root && region && root.contains(region)) {
      const key = region.getAttribute('data-iu-word-key')
      root.querySelectorAll<HTMLElement>('[data-iu-word-region][data-iu-word-key]').forEach((copy) => {
        if (copy !== region && copy.getAttribute('data-iu-word-key') === key) copy.innerHTML = region.innerHTML
      })
    }
    if (root) editorHistoryRef.current.record(root.innerHTML, editorCaret(root), group)
    updateStats()
    scheduleAutosave()
  }, [scheduleAutosave, updateStats])

  useEffect(() => {
    const rememberSelection = () => {
      const selection = window.getSelection()
      if (selection?.rangeCount && editorRef.current?.contains(selection.anchorNode)) {
        editorRangeRef.current = selection.getRangeAt(0).cloneRange()
        const node = selection.anchorNode
        const element = node instanceof Element ? node : node?.parentElement
        if (!element) return
        const computed = window.getComputedStyle(element)
        const family = computed.fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase()
        const option = FONT_FAMILY_OPTIONS.find((item) => item.label.toLowerCase() === family)
        if (option) setFontFamily(option.value)
        const points = Number.parseFloat(computed.fontSize) * 0.75
        if (Number.isFinite(points)) setFontSize(`${Number(points.toFixed(2))}pt`)
        const paragraph = element.closest('p,li,h1,h2,h3,h4,h5,h6,blockquote') || element
        const paragraphStyle = window.getComputedStyle(paragraph)
        const height = Number.parseFloat(paragraphStyle.lineHeight)
        const size = Number.parseFloat(paragraphStyle.fontSize)
        if (Number.isFinite(height) && size > 0) setLineHeight(String(Number((height / size).toFixed(3))))
      }
    }
    document.addEventListener('selectionchange', rememberSelection)
    return () => document.removeEventListener('selectionchange', rememberSelection)
  }, [])

  const applyPageLayout = (layout: PageLayout, preset = 'custom') => {
    if (Object.values(layout).some((value) => !Number.isFinite(value) || value < 0)
      || layout.width < 100 || layout.height < 100 || layout.width > 700 || layout.height > 700
      || layout.left + layout.right >= layout.width - 20 || layout.top + layout.bottom >= layout.height - 20
      || [layout.top, layout.bottom, layout.left, layout.right].some((value) => value > 100)) {
      setStatus({ tone: 'danger', label: 'Controlla i margini: deve restare spazio per il documento.' })
      return false
    }
    pageLayoutRef.current = { layout, changed: preset !== 'original' }
    for (const [page, original] of originalSectionLayoutsRef.current) {
      if (!editorRef.current?.contains(page)) continue
      const selected = preset === 'original' ? original : layout
      page.style.width = `${selected.width}mm`
      page.style.minHeight = `${selected.height}mm`
      page.style.padding = `${selected.top}mm ${selected.right}mm ${selected.bottom}mm ${selected.left}mm`
      page.querySelectorAll<HTMLElement>('.iu-doc-regione-word').forEach((region) => {
        region.style.left = `${selected.left}mm`
        region.style.right = `${selected.right}mm`
      })
      for (const [key, attribute] of [['width', 'larghezza'], ['height', 'altezza'], ['top', 'margine-alto'], ['bottom', 'margine-basso'], ['left', 'margine-sinistro'], ['right', 'margine-destro']] as const) {
        page.setAttribute(`data-${attribute}`, String(selected[key] * 72 / 25.4))
      }
    }
    setPageLayout(layout)
    setPagePreset(preset)
    setLayoutOpen(false)
    markChanged()
    return true
  }

  const currentParagraphText = () => {
    const root = editorRef.current
    const selection = window.getSelection()
    if (!root || !selection?.anchorNode || !root.contains(selection.anchorNode)) return ''
    if (!selection.isCollapsed) return selection.toString().slice(0, 2000)
    const node = selection.anchorNode
    const element = node instanceof Element ? node : node.parentElement
    return (element?.closest('p,h1,h2,h3,li,td,blockquote')?.textContent || '').slice(0, 2000)
  }

  const handleEditorInput = (event: FormEvent<HTMLDivElement>) => {
    setLanguageError('')
    grammarRequestRef.current?.abort()
    setGrammarLoading(false)
    setGrammarMarks([])
    const kind = (event.nativeEvent as InputEvent).inputType
    markChanged(kind === 'insertText' || kind === 'deleteContentBackward' || kind === 'deleteContentForward' ? kind : '')
    setPhraseSuggestion('')
    setPhraseCopied(false)
    setSpellingChoice(null)
    phraseRequestRef.current?.abort()
    phraseRequestRef.current = null
    setPhraseLoading(false)
    if (languageTimerRef.current) window.clearTimeout(languageTimerRef.current)
    languageRequestRef.current?.abort()
    if (!spellingEnabled || !data.endpoints.language) return
    const anchor = window.getSelection()?.anchorNode
    const element = anchor instanceof Element ? anchor : anchor?.parentElement
    const paragraph = element?.closest('p,h1,h2,h3,li,td,blockquote')
    const testo = paragraph?.textContent || ''
    spellingMarksRef.current = spellingMarksRef.current.filter((mark) => mark.paragraph !== paragraph && mark.range.startContainer.isConnected && mark.range.toString() === mark.word)
    showSpellingMarks(spellingMarksRef.current)
    if (!testo.trim()) { setSpellingResults([]); return }
    languageTimerRef.current = window.setTimeout(async () => {
      const controller = new AbortController()
      languageRequestRef.current = controller
      try {
        const response = await fetch(data.endpoints.language, {
          method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ azione: 'documento', testo }),
        })
        const payload = await response.json()
        if (controller.signal.aborted || languageRequestRef.current !== controller || !paragraph?.isConnected || paragraph.textContent !== testo) return
        if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Vocabolario locale non disponibile.')
        setSpellingResults([])
        spellingMarksRef.current.push(...grammarRanges({ text: testo, parts: [{ paragraph, start: 0, text: testo }] }, payload.rilievi || []))
        setGrammarMarks([...spellingMarksRef.current])
        showSpellingMarks(spellingMarksRef.current)
        setLanguageError('')
      } catch (error) {
        if (!controller.signal.aborted) setLanguageError(error instanceof Error ? error.message : 'Controllo linguistico non disponibile.')
      }
    }, 800)
  }

  const suggestPhrase = async () => {
    const testo = currentParagraphText()
    if (!testo.trim()) { setLanguageError('Posiziona il cursore nella frase o seleziona il testo da migliorare.'); return }
    setPhraseLoading(true)
    setPhraseSuggestion('')
    setPhraseCopied(false)
    setLanguageError('')
    phraseRequestRef.current?.abort()
    const controller = new AbortController()
    phraseRequestRef.current = controller
    try {
      const response = await fetch(data.endpoints.language, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ azione: 'frase', testo }),
      })
      const payload = await response.json()
      if (controller.signal.aborted || phraseRequestRef.current !== controller) return
      if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Suggerimento locale non disponibile.')
      setPhraseSuggestion(String(payload.proposta || ''))
    } catch (error) {
      if (!controller.signal.aborted) setLanguageError(error instanceof Error ? error.message : 'Suggerimento non disponibile.')
    } finally { if (phraseRequestRef.current === controller) setPhraseLoading(false) }
  }

  const checkDocumentLanguage = async () => {
    const root = editorRef.current
    if (!root) return
    const source = documentLanguageSource(root)
    const revision = editRevisionRef.current
    grammarRequestRef.current?.abort()
    const controller = new AbortController()
    grammarRequestRef.current = controller
    setGrammarLoading(true)
    setGrammarNotice('')
    setLanguageError('')
    try {
      const response = await fetch(data.endpoints.language, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ azione: 'documento', testo: source.text }),
      })
      const payload = await response.json()
      if (controller.signal.aborted || revision !== editRevisionRef.current) return
      if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Revisione italiana non disponibile.')
      const marks = grammarRanges(source, payload.rilievi || [])
      setGrammarMarks(marks)
      spellingMarksRef.current = marks
      showSpellingMarks(marks)
      setGrammarNotice(marks.length ? '' : 'Controllo terminato: nessun rilievo linguistico trovato.')
    } catch (error) {
      if (!controller.signal.aborted) setLanguageError(error instanceof Error ? error.message : 'Revisione italiana non disponibile.')
    } finally { if (grammarRequestRef.current === controller) setGrammarLoading(false) }
  }

  useEffect(() => {
    if (payloadLoading || documentLoading || !spellingEnabled || !data.endpoints.language || !editorRef.current || !data.document.editable) return
    const timer = window.setTimeout(() => void checkDocumentLanguage(), 300)
    return () => { window.clearTimeout(timer); grammarRequestRef.current?.abort() }
  }, [payloadLoading, documentLoading, spellingEnabled, data.endpoints.language, data.document.id])

  useEffect(() => () => {
    if (languageTimerRef.current) window.clearTimeout(languageTimerRef.current)
    languageRequestRef.current?.abort()
    phraseRequestRef.current?.abort()
    grammarRequestRef.current?.abort()
    clearSpellingMarks()
  }, [])

  useEffect(() => {
    const close = () => setSpellingChoice(null)
    document.addEventListener('wheel', close, true)
    document.addEventListener('touchmove', close, true)
    return () => { document.removeEventListener('wheel', close, true); document.removeEventListener('touchmove', close, true) }
  }, [])

  const correctSpelling = (mark: SpellingMark, correction: string) => {
    const root = editorRef.current
    if (!root || !root.contains(mark.range.startContainer) || mark.range.toString() !== mark.word) {
      setSpellingChoice(null)
      return
    }
    editorHistoryRef.current.rememberCaret(editorCaret(root))
    root.focus()
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(mark.range)
    const revision = editRevisionRef.current
    if (!document.execCommand('insertText', false, correction)) {
      setLanguageError('Correzione non applicata. Il testo è rimasto invariato.')
      return
    }
    if (revision === editRevisionRef.current) markChanged()
    spellingMarksRef.current = spellingMarksRef.current.filter((entry) => entry.paragraph !== mark.paragraph)
    showSpellingMarks(spellingMarksRef.current)
    setSpellingResults((results) => results.filter((result) => result.parola !== mark.word))
    setSpellingChoice(null)
  }

  const runCommand = useCallback((command: string, value?: string) => {
    if (conversionLocked) return
    const root = editorRef.current
    if (root && (command === 'undo' || command === 'redo')) {
      const target = editorHistoryRef.current.move(command, root.innerHTML)
      if (!target) return
      root.innerHTML = target.html
      restoreEditorCaret(root, target.caret)
      editorRangeRef.current = null
      setTableContext(null)
      setTablePickerOpen(false)
      markChanged()
      return
    }
    const range = editorRangeRef.current?.cloneRange()
    const selection = window.getSelection()
    if (range && selection && editorRef.current?.contains(range.startContainer)) {
      selection.removeAllRanges()
      selection.addRange(range)
    } else {
      editorRef.current?.focus()
    }
    document.execCommand(command, false, value)
    if (selection?.rangeCount && editorRef.current?.contains(selection.anchorNode)) editorRangeRef.current = selection.getRangeAt(0).cloneRange()
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
    const rememberedRange = editorRangeRef.current
    if (selection && rememberedRange && root.contains(rememberedRange.startContainer) && root.contains(rememberedRange.endContainer)) {
      root.focus()
      selection.removeAllRanges()
      selection.addRange(rememberedRange)
    }
    const selectionInEditor = Boolean(
      selection
      && selection.rangeCount
      && selection.anchorNode
      && selection.focusNode
      && root.contains(selection.anchorNode)
      && root.contains(selection.focusNode),
    )
    if (!selection || !selectionInEditor) {
      setStatus({ tone: 'warning', label: 'Posiziona il cursore o seleziona il testo da formattare' })
      return
    }
    if (selection.isCollapsed) {
      const node = selection.anchorNode
      const element = node instanceof HTMLElement ? node : node?.parentElement
      const target = element?.closest<HTMLElement>('span,strong,em,u,s,a,p,li,h1,h2,h3,h4,h5,h6')
      if (!target || !root.contains(target)) {
        setStatus({ tone: 'warning', label: 'Seleziona il testo da formattare' })
        return
      }
      applyStyle(target)
      markChanged()
      setStatus({ tone: 'warning', label: `${label} da salvare` })
      return
    }
    const range = selection.getRangeAt(0)
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    const pieces: Array<{ node: Text; start: number; end: number }> = []
    while (walker.nextNode()) {
      const node = walker.currentNode as Text
      if (!range.intersectsNode(node)) continue
      const start = node === range.startContainer ? range.startOffset : 0
      const end = node === range.endContainer ? range.endOffset : node.length
      if (end > start) pieces.push({ node, start, end })
    }
    if (!pieces.length) return
    const spans: HTMLElement[] = []
    // Formattare i tratti singolarmente conserva paragrafi, liste e celle:
    // un unico span intorno a blocchi diversi ne altera la struttura.
    for (const { node, start, end } of pieces.reverse()) {
      const piece = document.createRange()
      piece.setStart(node, start)
      piece.setEnd(node, end)
      const span = document.createElement('span')
      applyStyle(span)
      piece.surroundContents(span)
      spans.unshift(span)
    }
    const nextRange = document.createRange()
    nextRange.setStartBefore(spans[0])
    nextRange.setEndAfter(spans[spans.length - 1])
    selection.removeAllRanges()
    selection.addRange(nextRange)
    editorRangeRef.current = nextRange.cloneRange()
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
    const multiplier = Number(value.replace(',', '.'))
    if (!Number.isFinite(multiplier) || multiplier < 0.8 || multiplier > 4) {
      setStatus({ tone: 'danger', label: 'Inserisci un’interlinea tra 0,8 e 4.' })
      return
    }
    if (conversionLocked || !editorRef.current) return
    const root = editorRef.current
    const selection = window.getSelection()
    const currentRange = selection?.rangeCount && selection.anchorNode && root.contains(selection.anchorNode)
      ? selection.getRangeAt(0) : null
    const savedRange = lineHeightRangeRef.current || editorRangeRef.current
    const range = currentRange || (savedRange && root.contains(savedRange.startContainer) ? savedRange : null)
    const paragraphs = Array.from(root.querySelectorAll<HTMLElement>('p,h1,h2,h3,h4,h5,h6,li,blockquote'))
    if (!range) {
      setStatus({ tone: 'warning', label: 'Posiziona il cursore nel paragrafo da formattare' })
      return
    }
    const targets = paragraphs.filter((paragraph) => range.intersectsNode(paragraph))
    targets.forEach((paragraph) => {
      paragraph.style.lineHeight = String(multiplier)
    })
    setLineHeight(String(multiplier))
    setCustomLineHeight(String(multiplier).replace('.', ','))
    lineHeightRangeRef.current = null
    markChanged()
    setStatus({ tone: 'warning', label: 'Interlinea da salvare' })
  }, [conversionLocked, markChanged])

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
      if (editorRef.current) {
        editorRef.current.innerHTML = sanitizedHtml
        editorHistoryRef.current.reset(editorRef.current.innerHTML)
      }
      const page = editorRef.current?.querySelector('section.iu-doc-pagina')
      originalSectionLayoutsRef.current = new Map(Array.from(
        editorRef.current?.querySelectorAll<HTMLElement>('section.iu-doc-pagina[data-layout-sezione="true"]') ?? [],
        (nativePage) => [nativePage, nativePageLayout(nativePage)],
      ))
      const layout = nativePageLayout(page ?? null)
      originalLayoutRef.current = layout
      pageLayoutRef.current = { layout, changed: false }
      setPageLayout(layout)
      setPagePreset('original')
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

  const loadEditorAIDetail = useCallback(async () => {
    const endpoint = data.editorAI.current?.detail
    if (!endpoint) {
      setEditorAiDetail({ sources: [], edit_proposals: [], versions: [] })
      return
    }
    const detail = normalizeEditorAIDetail(await fetchEditorAIJson(endpoint))
    setEditorAiDetail(detail)
  }, [data.editorAI.current?.detail])

  const loadEditorAIBootstrap = useCallback(async () => {
    if (!data.editorAI.bootstrap) return
    setEditorAiLoading(true)
    setEditorAiError('')
    try {
      const bootstrap = normalizeEditorAIBootstrap(await fetchEditorAIJson(data.editorAI.bootstrap))
      setEditorAiBootstrap(bootstrap)
      setEditorAiTemplateId((current) => current || bootstrap.templates[0]?.id || '')
      setEditorAiTipoAtto((current) => current || bootstrap.templates[0]?.titolo || 'Atto')
      setEditorAiDocumentIds((current) => current.length ? current : bootstrap.documents.filter((item) => item.status === 'ready').map((item) => item.document_id))
      await loadEditorAIDetail()
    } catch (error) {
      setEditorAiError(error instanceof Error ? error.message : 'Lex non disponibile per la generazione atti.')
    } finally {
      setEditorAiBootstrapped(true)
      setEditorAiLoading(false)
    }
  }, [data.editorAI.bootstrap, loadEditorAIDetail])

  useEffect(() => {
    if (editorAiOpen && data.editorAI.enabled && data.editorAI.bootstrap && !editorAiBootstrapped && !editorAiLoading) {
      void loadEditorAIBootstrap()
    }
  }, [data.editorAI.bootstrap, data.editorAI.enabled, editorAiBootstrapped, editorAiLoading, editorAiOpen, loadEditorAIBootstrap])

  const toggleEditorAIDocument = (documentId: string) => {
    setEditorAiDocumentIds((current) => (
      current.includes(documentId)
        ? current.filter((item) => item !== documentId)
        : [...current, documentId]
    ))
  }

  const generateAttoWithLex = async () => {
    const selectedTemplate = editorAiBootstrap.templates.find((item) => item.id === editorAiTemplateId)
    const tipoAtto = editorAiTipoAtto || selectedTemplate?.titolo || 'Atto'
    if (!data.editorAI.generate || !editorAiTemplateId) {
      setEditorAiError('Seleziona un template atto prima di generare la bozza.')
      return
    }
    setEditorAiLoading(true)
    setEditorAiError('')
    try {
      const payload = await fetchEditorAIJson(data.editorAI.generate, {
        method: 'POST',
        body: JSON.stringify({
          template_id: editorAiTemplateId,
          tipo_atto: tipoAtto,
          istruzioni_utente: editorAiInstructions,
          document_ids: editorAiDocumentIds,
          use_fascicolo_context: true,
          language: 'it',
        }),
      })
      const missing = Array.isArray(payload.missing_fields) ? payload.missing_fields.map((item) => text(item)).filter(Boolean) : []
      setEditorAiBootstrap((current) => ({ ...current, missing_fields: missing }))
      const openUrl = text(payload.open_url)
      if (openUrl) window.location.assign(openUrl)
    } catch (error) {
      setEditorAiError(error instanceof Error ? error.message : 'Generazione atto non riuscita.')
    } finally {
      setEditorAiLoading(false)
    }
  }

  const proposeEditorAIEdit = async () => {
    const endpoint = data.editorAI.current?.proposeEdits
    if (!endpoint || !editorAiEditInstructions.trim()) {
      setEditorAiError("Scrivi le modifiche da proporre sull'atto aperto.")
      return
    }
    setEditorAiLoading(true)
    setEditorAiError('')
    try {
      const payload = await fetchEditorAIJson(endpoint, {
        method: 'POST',
        body: JSON.stringify({ istruzioni: editorAiEditInstructions }),
      })
      const detail = normalizeEditorAIDetail({ ...payload, versions: editorAiDetail.versions, sources: editorAiDetail.sources })
      setEditorAiDetail((current) => ({ ...current, edit_proposals: detail.edit_proposals }))
      setEditorAiEditInstructions('')
    } catch (error) {
      setEditorAiError(error instanceof Error ? error.message : 'Proposte modifica non create.')
    } finally {
      setEditorAiLoading(false)
    }
  }

  const resolveEditorAIProposal = async (proposalId: string, action: 'accetta' | 'rifiuta') => {
    const base = data.editorAI.current?.proposeEdits
    if (!base) return
    const endpoint = base.replace(/\/proponi$/, `/${encodeURIComponent(proposalId)}/${action}`)
    setEditorAiLoading(true)
    setEditorAiError('')
    try {
      await fetchEditorAIJson(endpoint, { method: 'POST', body: JSON.stringify({}) })
      await loadEditorAIDetail()
      if (action === 'accetta') void loadDocument(data)
    } catch (error) {
      setEditorAiError(error instanceof Error ? error.message : 'Aggiornamento proposta non riuscito.')
    } finally {
      setEditorAiLoading(false)
    }
  }

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
        setEditorAiBootstrapped(false)
        setEditorAiDetail({ sources: [], edit_proposals: [], versions: [] })
        setPdfAnnotations([])
        setPdfStatus('')
        setPdfMeta({ pageCount: 0, pages: [] })
        setPdfPage(1)
        setPdfRevision(Date.now())
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
    }
  }, [dirty])

  useEffect(() => () => {
    if (autosaveRef.current) window.clearTimeout(autosaveRef.current)
  }, [])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const undo = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !event.shiftKey
      const redo = (event.ctrlKey || event.metaKey) && (event.key.toLowerCase() === 'y' || (event.key.toLowerCase() === 'z' && event.shiftKey))
      if ((undo || redo) && editorRef.current?.contains(event.target as Node)) {
        event.preventDefault()
        runCommand(undo ? 'undo' : 'redo')
        return
      }
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
  }, [saveDocument, runCommand])

  const exportFile = async (endpoint: string, extension: 'pdf' | 'docx' | 'rtf') => {
    if (!endpoint || !editorRef.current || conversionLocked) return
    setStatus({ tone: 'saving', label: `Genero ${extension.toUpperCase()}` })
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: extension === 'pdf' ? 'application/pdf' : extension === 'rtf' ? 'application/rtf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ html: serializeEditorHtml() }),
      })
      if (!response.ok) throw new Error(await response.text())
      downloadBlob(await response.blob(), `${fileNameWithoutExtension(data.document.name)}.${extension}`)
      setStatus({ tone: 'success', label: `${extension.toUpperCase()} pronto` })
    } catch {
      setStatus({ tone: 'danger', label: `Esportazione ${extension.toUpperCase()} non riuscita. Riprova.` })
    }
  }

  const previewPrint = async (print = false) => {
    if (!data.endpoints.printPreview || !editorRef.current || conversionLocked) return
    printRequestRef.current?.abort()
    const controller = new AbortController()
    printRequestRef.current = controller
    setPrintLoading(true)
    setPrintError('')
    try {
      const response = await fetch(data.endpoints.printPreview, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ html: serializeEditorHtml() }),
      })
      if (!response.ok) throw new Error('Anteprima di stampa non generata.')
      const file = await response.blob()
      if (controller.signal.aborted || printRequestRef.current !== controller) return
      if (!file.type.includes('text/html')) throw new Error('Anteprima di stampa non valida.')
      printWhenReadyRef.current = print
      setLayoutDraft(pageLayoutRef.current.layout)
      setPrintPreviewUrl(URL.createObjectURL(file))
    } catch (error) {
      if (controller.signal.aborted || printRequestRef.current !== controller) return
      setStatus({ tone: 'danger', label: 'Anteprima di stampa non disponibile. Riprova tra poco.' })
      setPrintError('Anteprima non aggiornata. Riprova prima di stampare.')
    } finally { if (printRequestRef.current === controller) setPrintLoading(false) }
  }

  const closePrintPreview = () => {
    printRequestRef.current?.abort()
    printRequestRef.current = null
    setPrintLoading(false)
    setPrintPreviewUrl('')
  }

  useEffect(() => () => { printRequestRef.current?.abort() }, [])

  useEffect(() => () => { if (printPreviewUrl) URL.revokeObjectURL(printPreviewUrl) }, [printPreviewUrl])

  const updatePrintZoom = (value: string) => {
    setPrintZoom(value)
    const frame = printFrameRef.current?.contentDocument
    frame?.querySelectorAll<HTMLElement>('.pagina').forEach((page) => {
      const width = Number(page.dataset.widthMm)
      page.style.width = value === 'fit' ? `${width}mm` : `${width * 96 / 25.4 * Number(value) / 100}px`
      page.style.maxWidth = value === 'fit' ? '100%' : 'none'
    })
  }

  const importFile = async (file?: File) => {
    if (!file) return
    const lower = file.name.toLowerCase()
    const serverImport = lower.endsWith('.pdf') || lower.endsWith('.docx') || lower.endsWith('.doc')
      || (!data.document.editable || conversionLocked)
    if (serverImport) {
      if (!data.endpoints.importFile) {
        setStatus({ tone: 'danger', label: 'Import non disponibile per questo documento' })
        return
      }
      setStatus({ tone: 'saving', label: 'Importazione documento' })
      try {
        const formData = new FormData()
        formData.append('documento', file)
        const response = await fetch(data.endpoints.importFile, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: formData,
        })
        const payload = await response.json().catch(() => ({} as Record<string, unknown>))
        if (!response.ok || payload.ok === false) throw new Error(text(payload.messaggio || payload.message, 'Documento non importato.'))
        setStatus({ tone: 'success', label: text(payload.message || payload.messaggio, 'Documento importato') })
        window.setTimeout(() => window.location.reload(), 450)
      } catch (error) {
        setStatus({ tone: 'danger', label: error instanceof Error ? error.message : 'Import non riuscito' })
      }
      return
    }
    if (!editorRef.current) return
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

  const loadPdfMeta = useCallback(async () => {
    if (!data.endpoints.pdfMeta) return
    setPdfStatus('Carico pagine PDF...')
    try {
      const response = await fetch(data.endpoints.pdfMeta, {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await response.json().catch(() => ({} as Record<string, unknown>))
      if (!response.ok || payload.ok === false) throw new Error(text(payload.errore || payload.message, 'Metadati PDF non disponibili.'))
      const meta = normalizePdfMeta(payload)
      setPdfMeta(meta)
      setPdfPage((current) => Math.min(Math.max(1, current), Math.max(1, meta.pageCount || 1)))
      setPdfStatus(meta.pageCount ? 'PDF pronto per modifiche sicure a overlay.' : 'PDF senza pagine renderizzabili.')
    } catch (error) {
      setPdfStatus(error instanceof Error ? error.message : 'Metadati PDF non disponibili.')
    }
  }, [data.endpoints.pdfMeta])

  const addPdfAnnotationAt = (x: number, y: number) => {
    const safeX = Math.min(0.98, Math.max(0, x))
    const safeY = Math.min(0.98, Math.max(0, y))
    if (pdfTool === 'text') {
      const value = pdfText.trim()
      if (!value) {
        setPdfStatus('Scrivi il testo da inserire prima di cliccare sulla pagina.')
        return
      }
      setPdfAnnotations((current) => [...current, {
        id: newPdfAnnotationId(),
        type: 'text',
        page: pdfPage,
        x: safeX,
        y: safeY,
        text: value,
        fontSizePt: pdfFontSize,
        color: pdfTextColor,
      }])
      setPdfStatus('Testo aggiunto alla bozza PDF. Salva per creare la nuova versione.')
      return
    }
    addPdfRiquadro(safeX, safeY, safeX + RIQUADRO_PREDEFINITO.width, safeY + RIQUADRO_PREDEFINITO.height)
  }

  // Il riquadro si disegna: si preme dove comincia, si trascina fin dove
  // finisce, si rilascia. Prima era di misura fissa, ancorata al punto del
  // clic: per coprire una riga di venticinque lettere ne servivano due
  // sovrapposti, e chi mirava male copriva la parola accanto. Su un atto,
  // un omissis che non copre e' una cosa seria.
  const addPdfRiquadro = (x0: number, y0: number, x1: number, y1: number) => {
    const sinistra = Math.min(0.999, Math.max(0, Math.min(x0, x1)))
    const alto = Math.min(0.999, Math.max(0, Math.min(y0, y1)))
    let larghezza = Math.abs(x1 - x0)
    let altezza = Math.abs(y1 - y0)
    // un clic secco, senza trascinare, vale come prima: chi clicca e basta
    // non deve restare senza niente
    if (larghezza < MISURA_MINIMA_RIQUADRO) larghezza = RIQUADRO_PREDEFINITO.width
    if (altezza < MISURA_MINIMA_RIQUADRO) altezza = RIQUADRO_PREDEFINITO.height
    larghezza = Math.min(larghezza, 1 - sinistra)
    altezza = Math.min(altezza, 1 - alto)
    setPdfAnnotations((current) => [...current, {
      id: newPdfAnnotationId(),
      type: pdfTool,
      page: pdfPage,
      x: sinistra,
      y: alto,
      width: larghezza,
      height: altezza,
      fillColor: pdfTool === 'cover' ? '#ffffff' : pdfFillColor,
    }])
    setPdfStatus(pdfTool === 'cover' ? 'Riquadro coprente aggiunto alla bozza PDF.' : 'Evidenziazione aggiunta alla bozza PDF.')
  }

  const pdfPuntoDa = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    return {
      x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
    }
  }

  const handlePdfPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (pdfTool === 'text') return
    const punto = pdfPuntoDa(event)
    if (!punto) return
    event.preventDefault()
    try { event.currentTarget.setPointerCapture(event.pointerId) } catch { /* il browser non lo sostiene */ }
    pdfTrascinaRef.current = punto
    setPdfBozza({ x: punto.x, y: punto.y, x1: punto.x, y1: punto.y })
  }

  const handlePdfPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const inizio = pdfTrascinaRef.current
    if (!inizio) return
    const punto = pdfPuntoDa(event)
    if (!punto) return
    setPdfBozza({ x: inizio.x, y: inizio.y, x1: punto.x, y1: punto.y })
  }

  const handlePdfPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    const inizio = pdfTrascinaRef.current
    const punto = pdfPuntoDa(event)
    pdfTrascinaRef.current = null
    setPdfBozza(null)
    if (!punto) return
    if (pdfTool === 'text' || !inizio) {
      addPdfAnnotationAt(punto.x, punto.y)
      return
    }
    addPdfRiquadro(inizio.x, inizio.y, punto.x, punto.y)
  }

  // Dove finisce il risultato. Sovrascrivere va bene finche' si aggiunge un
  // timbro; per una copia da mandare a qualcuno, o per una versione con gli
  // omissis, l'originale deve restare dov'e' — e a volte quella copia non
  // deve nemmeno entrare nel fascicolo, serve solo sul computer.
  const savePdfOverlay = async (destinazione: 'versione' | 'copia' | 'scarica' = 'versione') => {
    if (!data.endpoints.pdfOverlay || !pdfAnnotations.length || pdfSaving) return
    setPdfSaving(true)
    setPdfStatus(
      destinazione === 'copia' ? 'Creo una copia nel fascicolo...'
        : destinazione === 'scarica' ? 'Preparo la copia da scaricare...'
        : 'Salvo il PDF come nuova versione...',
    )
    try {
      const response = await fetch(data.endpoints.pdfOverlay, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: destinazione === 'scarica' ? 'application/pdf' : 'application/json',
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ annotations: pdfAnnotations, destinazione }),
      })
      if (destinazione === 'scarica') {
        if (!response.ok) {
          const errore = await response.json().catch(() => ({} as Record<string, unknown>))
          throw new Error(text(errore.errore || errore.message, 'Copia non scaricata.'))
        }
        const blob = await response.blob()
        const intestazione = response.headers.get('content-disposition') || ''
        const trovato = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(intestazione)
        const nome = trovato ? decodeURIComponent(trovato[1]) : `${data.document.name.replace(/\.pdf$/i, '')} (copia).pdf`
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = nome
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(url)
        setPdfAnnotations([])
        setPdfStatus(`Copia scaricata: ${nome}. L'originale nel fascicolo non e' stato toccato.`)
        setStatus({ tone: 'success', label: 'Copia scaricata' })
        return
      }
      const payload = await response.json().catch(() => ({} as Record<string, unknown>))
      if (!response.ok || payload.ok === false) throw new Error(text(payload.errore || payload.message, 'PDF non salvato.'))
      setPdfAnnotations([])
      setPdfRevision(Date.now())
      setPdfStatus(text(payload.message, 'PDF salvato come nuova versione.'))
      setStatus({ tone: 'success', label: destinazione === 'copia' ? 'Copia creata' : 'PDF salvato' })
      if (destinazione !== 'copia') await loadPdfMeta()
    } catch (error) {
      setPdfStatus(error instanceof Error ? error.message : 'PDF non salvato.')
      setStatus({ tone: 'danger', label: 'Modifica PDF non salvata' })
    } finally {
      setPdfSaving(false)
    }
  }

  // «Modifica» su un documento che non si edita come testo apre subito l'editor PDF.
  useEffect(() => {
    if (!data.document.editable && data.document.pdfOverlayAllowed) setPdfEditorOpen(true)
  }, [data.document.id, data.document.editable, data.document.pdfOverlayAllowed])
  useEffect(() => {
    if (pdfEditorOpen && data.document.pdfOverlayAllowed && data.endpoints.pdfMeta && !pdfMeta.pageCount) {
      void loadPdfMeta()
    }
  }, [data.document.pdfOverlayAllowed, data.endpoints.pdfMeta, loadPdfMeta, pdfEditorOpen, pdfMeta.pageCount])

  const openLink = () => {
    linkRangeRef.current = editorRangeRef.current?.cloneRange() || null
    const node = linkRangeRef.current?.commonAncestorContainer
    const anchor = (node instanceof Element ? node : node?.parentElement)?.closest('a')
    if (anchor && editorRef.current?.contains(anchor)) {
      const range = document.createRange()
      range.selectNodeContents(anchor)
      linkRangeRef.current = range
    }
    setLinkText(linkRangeRef.current?.toString() || '')
    setLinkUrl(anchor?.getAttribute('href') || '')
    setLinkExisting(Boolean(anchor && editorRef.current?.contains(anchor)))
    setLinkOpen(true)
  }

  const insertLink = () => {
    const raw = linkUrl.trim()
    const href = /^(https?:|mailto:|tel:|\/[^/])/i.test(raw) ? raw : /^[\w.-]+\.[a-z]{2,}(?:\/|$)/i.test(raw) ? `https://${raw}` : ''
    if (!href || /[\u0000-\u0020<>]/.test(href)) {
      setStatus({ tone: 'danger', label: 'Inserisci un indirizzo HTTP, HTTPS, email o collegamento interno valido.' })
      return
    }
    editorRangeRef.current = linkRangeRef.current
    if (linkRangeRef.current && !linkRangeRef.current.collapsed && linkText === linkRangeRef.current.toString()) runCommand('createLink', href)
    else {
      const link = document.createElement('a')
      link.href = href
      link.textContent = linkText.trim() || href
      runCommand('insertHTML', link.outerHTML)
    }
    setLinkOpen(false)
  }

  const openTablePicker = () => {
    const selection = window.getSelection()
    tableRangeRef.current = selection?.rangeCount && editorRef.current?.contains(selection.anchorNode)
      ? selection.getRangeAt(0).cloneRange() : null
    const node = selection?.anchorNode
    const element = node instanceof Element ? node : node?.parentElement
    const cell = element?.closest<HTMLTableCellElement>('td,th')
    const table = cell?.closest<HTMLTableElement>('table')
    setTableContext(cell && table && editorRef.current?.contains(table) ? { cell, table } : null)
    setTablePickerOpen((open) => !open)
  }

  const changeTable = (action: TableAction | 'delete') => {
    const context = tableContext
    if (conversionLocked || !context || !editorRef.current?.contains(context.table)) return
    try {
      const replacement = action === 'delete' ? null : editTable(context.table, context.cell, action)
      const inserted = replacement
      if (replacement) context.table.replaceWith(replacement)
      else context.table.remove()
      if (inserted?.rows[0]?.cells[0]) {
        const cell = inserted.rows[0].cells[0]
        const caret = document.createRange()
        caret.selectNodeContents(cell)
        caret.collapse(true)
        const selection = window.getSelection()
        selection?.removeAllRanges()
        selection?.addRange(caret)
        editorRangeRef.current = caret.cloneRange()
        setTableContext({ table: inserted, cell })
      } else {
        setTableContext(null)
        setTablePickerOpen(false)
      }
      markChanged()
    } catch (error) {
      setStatus({ tone: 'danger', label: error instanceof Error ? error.message : 'Modifica della tabella non riuscita.' })
    }
  }

  const insertTable = () => {
    const rows = Number(tableRows)
    const columns = Number(tableColumns)
    if (!Number.isInteger(rows) || !Number.isInteger(columns) || rows < 1 || rows > 50 || columns < 1 || columns > 20) {
      setStatus({ tone: 'danger', label: 'Scegli da 1 a 50 righe e da 1 a 20 colonne.' })
      return
    }
    editorRef.current?.focus()
    const selection = window.getSelection()
    if (selection && tableRangeRef.current && editorRef.current?.contains(tableRangeRef.current.startContainer)) {
      selection.removeAllRanges()
      selection.addRange(tableRangeRef.current)
      editorRangeRef.current = tableRangeRef.current.cloneRange()
    }
    const html = Array.from({ length: rows }, (_, row) => {
      const tag = tableHeader && row === 0 ? 'th' : 'td'
      return `<tr>${Array.from({ length: columns }, () => `<${tag}><br></${tag}>`).join('')}</tr>`
    }).join('')
    runCommand('insertHTML', `<table style="width:100%;table-layout:fixed"><tbody>${html}</tbody></table><p><br></p>`)
    tableRangeRef.current = null
    setTablePickerOpen(false)
  }

  const insertTextBox = () => {
    runCommand('insertHTML', '<table data-iu-text-box="true" style="width:360px;max-width:100%;table-layout:fixed"><tbody><tr><td><p>Scrivi qui…</p></td></tr></tbody></table><p><br></p>')
  }

  const chooseImage = () => {
    const selection = window.getSelection()
    imageRangeRef.current = selection?.rangeCount && editorRef.current?.contains(selection.anchorNode)
      ? selection.getRangeAt(0).cloneRange() : null
    imageFileRef.current?.click()
  }

  const insertImage = async (file?: File) => {
    if (!file) return
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      setStatus({ tone: 'danger', label: 'Scegli un’immagine PNG, JPEG o WebP fino a 5 MB.' })
      return
    }
    try {
      const source = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = () => reject(new Error('Immagine non caricata.'))
        reader.readAsDataURL(file)
      })
      const picture = new Image()
      picture.src = source
      await picture.decode()
      const root = editorRef.current
      if (!root || conversionLocked) return
      root.focus()
      const selection = window.getSelection()
      const range = imageRangeRef.current
      if (selection && range && root.contains(range.startContainer)) {
        selection.removeAllRanges()
        selection.addRange(range)
      }
      const node = range?.startContainer
      const element = node instanceof Element ? node : node?.parentElement
      const box = element?.closest('table[data-iu-text-box]')
      const cell = box && element?.closest('td,th')
      const inBox = Boolean(box && cell)
      const cellStyle = cell ? window.getComputedStyle(cell) : null
      const contentWidth = cell && cellStyle
        ? cell.clientWidth - parseFloat(cellStyle.paddingLeft || '0') - parseFloat(cellStyle.paddingRight || '0')
        : 0
      // Registra la misura realmente visibile, così l'export non interpreta
      // 100% rispetto al foglio o alla risoluzione nativa della fotografia.
      const width = inBox && contentWidth > 0 ? `${contentWidth}px` : `${Math.min(picture.naturalWidth, 640)}px`
      runCommand('insertHTML', `<img src="${source}" alt="Immagine inserita" style="width:${width};max-width:100%;height:auto;object-fit:contain">`)
      imageRangeRef.current = null
      setStatus({ tone: 'warning', label: inBox ? 'Immagine adattata alla casella, da salvare' : 'Immagine inserita, da salvare' })
    } catch {
      setStatus({ tone: 'danger', label: 'Immagine non leggibile. Prova un file PNG o JPEG valido.' })
    }
  }

  const startEditorDictation = () => {
    if (conversionLocked || !editorRef.current) return
    const service = window.IusentraVoiceInput
    if (!service?.startForTarget) {
      setStatus({ tone: 'danger', label: 'Dettatura non disponibile in questa sessione' })
      return
    }
    setVoiceDictating(true)
    setStatus({ tone: 'loading', label: 'Controllo microfono editor' })
    void service.startForTarget(editorRef.current, {
      context: 'editor-professionale',
      lang: 'it-IT',
      silenceMs: 3200,
      onStart: () => setStatus({ tone: 'loading', label: 'Dettatura attiva nell’editor' }),
    }).then((insertedText) => {
      setStatus({ tone: insertedText ? 'warning' : 'neutral', label: insertedText ? 'Dettatura inserita, da salvare' : 'Nessun testo vocale rilevato' })
      if (insertedText) markChanged()
    }).catch((error) => {
      setStatus({ tone: 'danger', label: error instanceof Error ? error.message : 'Dettatura non disponibile' })
    }).finally(() => {
      setVoiceDictating(false)
    })
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
    if (html) document.execCommand('insertHTML', false, sanitizeHtml(html))
    else document.execCommand('insertText', false, plain)
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
  const emlPreviewMode = isEmlDocument(doc.name, doc.extension)
  const editorEnabled = doc.editable && !conversionLocked
  const exportDisabled = !editorEnabled || payloadLoading || documentLoading || status.tone === 'saving'
  const lockedReason = conversionLocked
    ? conversionLockedReason || 'Il documento non espone testo affidabile per la modifica inline.'
    : doc.lockedReason
  const statusClass = `iu-de-status iu-de-status--${status.tone}`
  const currentAttoAI = data.editorAI.current
  const editorAiReadyDocuments = editorAiBootstrap.documents.filter((item) => item.status === 'ready')
  const editorAiPendingProposals = editorAiDetail.edit_proposals.filter((item) => item.status === 'pending')
  const pdfCurrentPageAnnotations = pdfAnnotations.filter((annotation) => annotation.page === pdfPage)
  const pdfPageImageUrl = data.endpoints.pdfPageImage
    ? `${data.endpoints.pdfPageImage}/${pdfPage}.png?v=${pdfRevision}`
    : ''
  const pdfMarkStyle = (annotation: PdfAnnotation) => ({
    left: `${annotation.x * 100}%`,
    top: `${annotation.y * 100}%`,
    width: annotation.type === 'text' ? 'auto' : `${(annotation.width || 0.22) * 100}%`,
    height: annotation.type === 'text' ? 'auto' : `${(annotation.height || 0.045) * 100}%`,
    color: annotation.color || '#111827',
    backgroundColor: annotation.type === 'highlight' ? annotation.fillColor || '#fef3c7' : annotation.type === 'cover' ? '#fff' : 'rgba(255,255,255,.86)',
    fontSize: `${annotation.fontSizePt || 12}px`,
  }) as React.CSSProperties
  const pdfBozzaStyle = (bozza: { x: number; y: number; x1: number; y1: number }) => ({
    left: `${Math.min(bozza.x, bozza.x1) * 100}%`,
    top: `${Math.min(bozza.y, bozza.y1) * 100}%`,
    width: `${Math.abs(bozza.x1 - bozza.x) * 100}%`,
    height: `${Math.abs(bozza.y1 - bozza.y) * 100}%`,
  }) as React.CSSProperties
  const paperStyle = {
    // La selezione aggiorna i controlli, senza cambiare il formato dei blocchi non selezionati.
    '--iu-de-font-family': FONT_FAMILY_OPTIONS[0].value,
    '--iu-de-font-size': '12pt',
    '--iu-de-line-height': '1.6',
    '--iu-de-paper-width': `${pageLayout.width}mm`,
    '--iu-de-paper-min-height': `${pageLayout.height}mm`,
    '--iu-de-paper-padding-top': `${pageLayout.top}mm`,
    '--iu-de-paper-padding-bottom': `${pageLayout.bottom}mm`,
    '--iu-de-paper-padding-left': `${pageLayout.left}mm`,
    '--iu-de-paper-padding-right': `${pageLayout.right}mm`,
    '--iu-de-zoom': `${Number(zoom || 100) / 100}`,
  } as React.CSSProperties

  return (
    <main className={`iu-content iu-doc-editor-page${editorEnabled && !editorAiOpen ? ' iu-doc-editor-page--focused' : ''}`} ref={paginaRef}>
      <section className="iu-de-hero">
        <div>
          <span className="iu-de-eyebrow"><FileText size={16}/> Editor professionale</span>
          <h1>{doc.name}</h1>
          <p>
            <Badge tone={editorEnabled ? 'success' : 'warning'}>{editorEnabled ? 'Modificabile' : pdfPreviewMode ? 'Anteprima nativa' : emlPreviewMode ? 'EML originale' : 'Bloccato'}</Badge>
            <span>{data.fascicolo.ref || data.fascicolo.id} - {data.fascicolo.client || data.fascicolo.title}</span>
          </p>
        </div>
        <nav aria-label="Azioni documento">
          <a href={data.fascicolo.detailHref}><ArrowLeft size={15}/> Fascicolo</a>
          <button type="button" onClick={() => void cambiaTuttoSchermo()} aria-pressed={tuttoSchermo} title={tuttoSchermo ? 'Esci da tutto schermo (Esc)' : 'Apri l’editor a tutto schermo'}>
            {tuttoSchermo ? <Minimize2 size={15}/> : <Maximize2 size={15}/>} {tuttoSchermo ? 'Esci da tutto schermo' : 'Tutto schermo'}
          </button>
          {doc.actions.preview ? <a href={doc.actions.preview}><Eye size={15}/> Anteprima</a> : null}
          {doc.actions.sign ? <a href={doc.actions.sign}><ShieldCheck size={15}/> Firma</a> : null}
          {doc.actions.download ? <a href={doc.actions.download} download={doc.name}><Download size={15}/> Scarica</a> : null}
          <button type="button" onClick={() => setEditorAiOpen((value) => !value)} disabled={!data.editorAI.enabled}><Sparkles size={15}/> Nuovo atto con Lex</button>
          <button type="button" onClick={() => void saveDocument(false)} disabled={!editorEnabled}><Save size={15}/> Salva DOCX</button>
        </nav>
        {editorEnabled ? (
          <section className="iu-de-meta-row" aria-label="Stato editor">
            <span className={statusClass}>{status.tone === 'success' ? <CheckCircle2 size={15}/> : status.tone === 'loading' || status.tone === 'saving' ? <LoaderCircle className="iu-spin" size={15}/> : <Pilcrow size={15}/>} {status.label}</span>
            <span>{stats.words} parole - {stats.chars} caratteri - {stats.readingMinutes} min</span>
            <label><Heading1 size={14}/> <select aria-label="Formato pagina" value={pagePreset} onChange={(event) => {
              const preset = event.target.value
              if (preset === 'original') applyPageLayout(originalLayoutRef.current, preset)
              else if (preset !== 'custom') applyPageLayout({ ...DEFAULT_PAGE_LAYOUT, ...(preset === 'a4-compact' ? { top: 15, bottom: 15, left: 15, right: 15 } : preset === 'legal-wide' ? { top: 30, left: 40 } : {}) }, preset)
            }}><option value="original">Formato originale</option>{PAGE_PRESETS.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}{pagePreset === 'custom' && <option value="custom">Personalizzato</option>}</select></label>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => { setLayoutDraft(pageLayout); setLayoutOpen((open) => !open) }}>Layout pagina</button>
            <label><Eye size={14}/> <select aria-label="Zoom documento" value={zoom} onChange={(event) => setZoom(event.target.value)}>{ZOOM_OPTIONS.map((value) => <option key={value} value={value}>{value}%</option>)}</select></label>
            <span>{dirty
              ? lastSavedAt ? `Modifiche da salvare · ultimo salvataggio ${lastSavedAt}` : 'Salvataggio pendente'
              : lastSavedAt ? `Ultimo salvataggio ${lastSavedAt}` : 'Nessuna modifica pendente'}</span>
            <button className="iu-de-facts-toggle" type="button" aria-expanded={documentFactsOpen} aria-controls="iu-de-document-facts" onClick={() => setDocumentFactsOpen((value) => !value)}><FileText size={15}/> {documentFactsOpen ? 'Nascondi dati documento' : 'Dati documento'}</button>
            <Badge tone={data.contracts.mock_fallback ? 'danger' : 'success'}>{data.contracts.mock_fallback ? 'Dati non reali' : 'Dati reali'}</Badge>
          </section>
        ) : null}
      </section>

      {warnings.length ? (
        <section className="iu-de-warnings" aria-label="Avvisi editor">
          {warnings.map((warning) => <span key={warning}><AlertTriangle size={15}/>{warning}</span>)}
        </section>
      ) : null}

      {editorAiOpen && data.editorAI.enabled ? (
        <section className="iu-de-ai-panel" aria-label="Generazione atti con Lex">
          <div className="iu-de-ai-head">
            <div>
              <span className="iu-de-eyebrow"><Sparkles size={15}/> Lex nell'editor</span>
              <h2>Nuovo atto con Lex</h2>
              <p>La bozza viene creata come documento reale dell'editor, collegato al fascicolo e versionato.</p>
            </div>
            <div className="iu-de-ai-actions">
              <button type="button" onClick={() => void loadEditorAIBootstrap()} disabled={editorAiLoading}><ListChecks size={15}/> Aggiorna dati</button>
              <button type="button" onClick={() => setEditorAiOpen(false)}><XCircle size={15}/> Chiudi</button>
            </div>
          </div>
          {editorAiError ? <p className="iu-de-ai-error"><AlertTriangle size={15}/>{editorAiError}</p> : null}
          {data.editorAI.warning ? <p className="iu-de-ai-warning"><AlertTriangle size={15}/>{data.editorAI.warning}</p> : null}
          <div className="iu-de-ai-grid">
            <form className="iu-de-ai-form" onSubmit={(event) => { event.preventDefault(); void generateAttoWithLex() }}>
              <label>
                <span>Template atto</span>
                <select value={editorAiTemplateId} onChange={(event) => {
                  const next = event.target.value
                  const template = editorAiBootstrap.templates.find((item) => item.id === next)
                  setEditorAiTemplateId(next)
                  if (template?.titolo) setEditorAiTipoAtto(template.titolo)
                }}>
                  <option value="">Seleziona template</option>
                  {editorAiBootstrap.templates.map((template) => (
                    <option key={template.id} value={template.id}>{template.titolo}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Tipo atto</span>
                <input value={editorAiTipoAtto} onChange={(event) => setEditorAiTipoAtto(event.target.value)} placeholder="Es. memoria difensiva"/>
              </label>
              <label className="iu-de-ai-span">
                <span>Istruzioni per Lex</span>
                <textarea
                  value={editorAiInstructions}
                  onChange={(event) => setEditorAiInstructions(event.target.value)}
                  rows={4}
                  placeholder="Indica obiettivo, tono, questioni da trattare e dati da verificare nei documenti del fascicolo."
                />
              </label>
              <fieldset className="iu-de-ai-span">
                <legend>Documenti indicizzati del fascicolo</legend>
                {editorAiReadyDocuments.length ? (
                  <div className="iu-de-ai-docs">
                    {editorAiReadyDocuments.map((documentItem) => (
                      <label key={documentItem.document_id}>
                        <input
                          type="checkbox"
                          checked={editorAiDocumentIds.includes(documentItem.document_id)}
                          onChange={() => toggleEditorAIDocument(documentItem.document_id)}
                        />
                        <span>{documentItem.filename}</span>
                        <small>{documentItem.page_count ? `${documentItem.page_count} pag.` : 'pagine n.d.'} - SHA {shortHash(documentItem.sha256) || 'n.d.'}</small>
                      </label>
                    ))}
                  </div>
                ) : <p>Nessun documento indicizzato pronto. Lex userà solo i dati strutturati del fascicolo disponibili.</p>}
              </fieldset>
              <button className="iu-de-ai-primary" type="submit" disabled={editorAiLoading || !editorAiTemplateId}>
                {editorAiLoading ? <LoaderCircle className="iu-spin" size={15}/> : <Wand2 size={15}/>} Genera bozza
              </button>
            </form>
            <aside className="iu-de-ai-summary" aria-label="Stato atto AI">
              <section>
                <h3>Dati da completare</h3>
                {editorAiBootstrap.missing_fields.length ? (
                  <ul>{editorAiBootstrap.missing_fields.map((field) => <li key={field}>{field}</li>)}</ul>
                ) : <p>Nessun campo obbligatorio mancante rilevato nel bootstrap.</p>}
              </section>
              <section>
                <h3>Fonti usate</h3>
                {editorAiDetail.sources.length ? (
                  <ul>{editorAiDetail.sources.map((source) => <li key={source.id}>{source.document_id || source.source_id}{source.page_number ? `, pag. ${source.page_number}` : ''}{source.quote ? ` - ${source.quote}` : ''}</li>)}</ul>
                ) : <p>Le fonti saranno registrate dopo la generazione o la rilettura dell'atto.</p>}
              </section>
              {currentAttoAI ? (
                <section>
                  <h3>Modifiche proposte da Lex</h3>
                  <label>
                    <span>Istruzioni modifica</span>
                    <textarea
                      value={editorAiEditInstructions}
                      onChange={(event) => setEditorAiEditInstructions(event.target.value)}
                      rows={3}
                      placeholder="Descrivi la modifica puntuale da proporre sull'atto aperto."
                    />
                  </label>
                  <button type="button" onClick={() => void proposeEditorAIEdit()} disabled={editorAiLoading || !editorAiEditInstructions.trim()}><Sparkles size={15}/> Proponi modifiche</button>
                  {editorAiPendingProposals.length ? (
                    <div className="iu-de-ai-proposals">
                      {editorAiPendingProposals.map((proposal) => (
                        <article key={proposal.id}>
                          <strong>{proposal.operation_type || 'Modifica puntuale'}</strong>
                          <p>{proposal.reason || proposal.replace_text || proposal.insert_text || 'Proposta da verificare.'}</p>
                          <div>
                            <button type="button" onClick={() => void resolveEditorAIProposal(proposal.id, 'accetta')}><Check size={14}/> Accetta</button>
                            <button type="button" onClick={() => void resolveEditorAIProposal(proposal.id, 'rifiuta')}><XCircle size={14}/> Rifiuta</button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : <p>Nessuna proposta pendente.</p>}
                </section>
              ) : null}
              <section>
                <h3>Export</h3>
                <p>DOCX e PDF vengono generati dal documento reale aperto nell'editor.</p>
                <div className="iu-de-ai-export">
                  <button type="button" onClick={() => void exportFile(data.endpoints.exportDocx, 'docx')} disabled={!editorEnabled}><FileDown size={15}/> DOCX</button>
                  <button type="button" onClick={() => void exportFile(data.endpoints.exportPdf, 'pdf')} disabled={!editorEnabled}><FileDown size={15}/> PDF</button>
                </div>
              </section>
            </aside>
          </div>
        </section>
      ) : null}

      {!editorEnabled ? (
        <>
          <section className={`iu-de-locked${pdfPreviewMode ? ' iu-de-locked--compact' : ''}`} aria-label="Comandi documento">
            {!pdfPreviewMode ? <ShieldCheck size={24}/> : null}
            <div>
              {!pdfPreviewMode ? <><h2>{emlPreviewMode ? 'Messaggio EML consultabile' : 'Documento non modificabile in editor'}</h2>
              <p>{lockedReason || 'Apri il documento in anteprima o scaricalo per lavorarlo con un applicativo esterno.'}</p>
              <a href={doc.actions.preview || data.fascicolo.detailHref}><Eye size={15}/>{emlPreviewMode ? 'Apri email originale' : 'Apri anteprima'}</a></> : null}
              {doc.pdfOverlayAllowed && data.endpoints.pdfOverlay ? (
                <button type="button" onClick={() => setPdfEditorOpen((value) => !value)}><FileText size={15}/>{pdfEditorOpen ? 'Chiudi modifica PDF' : 'Modifica PDF sicura'}</button>
              ) : null}
              <button type="button" onClick={() => replaceFileRef.current?.click()}><UploadCloud size={15}/> Importa PDF/Word</button>
            </div>
          </section>
          {doc.pdfOverlayAllowed && pdfEditorOpen ? (
            <section className="iu-de-pdf-editor" aria-label="Editor PDF sicuro">
              <div className="iu-de-pdf-editor__head">
                <div>
                  <h2>Modifica PDF sicura</h2>
                  {doc.pdfSoloCopia ? <p><strong>Documento di prova: l’originale resta intatto.</strong> Il risultato va in una copia PDF del fascicolo o si scarica.</p> : null}
                  <p>Gli interventi vengono applicati come overlay sul PDF originale. Per coprire o evidenziare tieni premuto dove comincia e trascina fin dove finisce: il riquadro e' quello che disegni. Poi scegli dove va il risultato — una nuova versione di questo documento, una copia nel fascicolo che lascia intatto l'originale, o una copia scaricata sul computer.</p>
                </div>
                <div className="iu-de-pdf-editor__actions">
                  <button type="button" onClick={() => setPdfAnnotations((current) => current.slice(0, -1))} disabled={!pdfAnnotations.length || pdfSaving}><Undo2 size={15}/> Annulla ultimo</button>
                  <button type="button" onClick={() => setPdfAnnotations([])} disabled={!pdfAnnotations.length || pdfSaving}><XCircle size={15}/> Svuota</button>
                  <button type="button" onClick={() => void savePdfOverlay('copia')} disabled={!pdfAnnotations.length || pdfSaving} title="Crea un documento nuovo nel fascicolo e lascia intatto l'originale"><Copy size={15}/> Copia nel fascicolo</button>
                  <button type="button" onClick={() => void savePdfOverlay('scarica')} disabled={!pdfAnnotations.length || pdfSaving} title="Scarica la copia sul computer senza toccare il fascicolo"><Download size={15}/> Scarica copia</button>
                  {doc.pdfSoloCopia ? null : <button type="button" onClick={() => void savePdfOverlay('versione')} disabled={!pdfAnnotations.length || pdfSaving}><Save size={15}/>{pdfSaving ? 'Salvo...' : 'Salva versione PDF'}</button>}
                </div>
              </div>
              <div className="iu-de-pdf-editor__toolbar">
                <label><span>Pagina</span>
                  <select value={pdfPage} onChange={(event) => setPdfPage(Number(event.target.value) || 1)}>
                    {Array.from({ length: Math.max(1, pdfMeta.pageCount || 1) }, (_, index) => index + 1).map((page) => (
                      <option key={page} value={page}>Pagina {page}</option>
                    ))}
                  </select>
                </label>
                <label><span>Strumento</span>
                  <select value={pdfTool} onChange={(event) => setPdfTool(event.target.value as PdfEditorTool)}>
                    <option value="text">Testo</option>
                    <option value="highlight">Evidenzia</option>
                    <option value="cover">Copri</option>
                  </select>
                </label>
                <label className="iu-de-pdf-editor__text"><span>Testo da inserire</span>
                  <input value={pdfText} onChange={(event) => setPdfText(event.target.value)} placeholder="Scrivi il testo e clicca sulla pagina" disabled={pdfTool !== 'text'}/>
                </label>
                <label><span>Dimensione</span>
                  <input type="number" min={6} max={48} value={pdfFontSize} onChange={(event) => setPdfFontSize(Number(event.target.value) || 12)} disabled={pdfTool !== 'text'}/>
                </label>
                <label><span>Colore</span>
                  <input type="color" value={pdfTool === 'text' ? pdfTextColor : pdfFillColor} onChange={(event) => pdfTool === 'text' ? setPdfTextColor(event.target.value) : setPdfFillColor(event.target.value)}/>
                </label>
              </div>
              {pdfStatus ? <p className="iu-de-pdf-editor__status">{pdfStatus}</p> : null}
              <div className="iu-de-pdf-editor__body">
                <div className="iu-de-pdf-page">
                  <div
                    className={`iu-de-pdf-page__canvas${pdfTool === 'text' ? '' : ' iu-de-pdf-page__canvas--disegna'}`}
                    role="button"
                    tabIndex={0}
                    onPointerDown={handlePdfPointerDown}
                    onPointerMove={handlePdfPointerMove}
                    onPointerUp={handlePdfPointerUp}
                    onPointerCancel={() => { pdfTrascinaRef.current = null; setPdfBozza(null) }}
                    onKeyDown={(event) => { if (event.key === 'Enter') addPdfAnnotationAt(0.12, 0.12) }}
                  >
                    {pdfPageImageUrl ? <img src={pdfPageImageUrl} alt={`Pagina ${pdfPage} del PDF ${doc.name}`}/> : <div className="iu-de-loader"><LoaderCircle className="iu-spin" size={24}/><span>Pagina PDF in caricamento...</span></div>}
                    {pdfBozza ? (
                      <span className="iu-de-pdf-mark iu-de-pdf-mark--bozza" style={pdfBozzaStyle(pdfBozza)} />
                    ) : null}
                    {pdfCurrentPageAnnotations.map((annotation) => (
                      <span
                        key={annotation.id}
                        className={`iu-de-pdf-mark iu-de-pdf-mark--${annotation.type}`}
                        style={pdfMarkStyle(annotation)}
                      >
                        {annotation.type === 'text' ? annotation.text : annotation.type === 'cover' ? 'Copertura' : 'Evidenziato'}
                      </span>
                    ))}
                  </div>
                </div>
                <aside className="iu-de-pdf-editor__list">
                  <strong>Interventi da salvare</strong>
                  {pdfAnnotations.length ? (
                    <ol>
                      {pdfAnnotations.map((annotation) => (
                        <li key={annotation.id}>
                          <span>Pag. {annotation.page} · {annotation.type === 'text' ? `Testo: ${annotation.text}` : annotation.type === 'cover' ? 'Copertura' : 'Evidenziazione'}</span>
                          <button type="button" onClick={() => setPdfAnnotations((current) => current.filter((item) => item.id !== annotation.id))}>Rimuovi</button>
                        </li>
                      ))}
                    </ol>
                  ) : <p>Nessun intervento inserito. Seleziona uno strumento e clicca sulla pagina renderizzata.</p>}
                </aside>
              </div>
            </section>
          ) : null}
          {doc.actions.preview ? (
            <section className="iu-de-workbench iu-de-workbench--preview">
              <DocumentFacts data={data}/>
              <section className="iu-de-preview-shell">
                <div className="iu-de-paper-head">
                  <span>{pdfPreviewMode ? 'Anteprima originale del PDF' : emlPreviewMode ? 'Email originale' : 'Anteprima consultazione'}</span>
                  <Badge tone={doc.signed || doc.extension === 'p7m' ? 'warning' : 'neutral'}>{doc.signed || doc.extension === 'p7m' ? 'Documento firmato' : pdfPreviewMode ? 'PDF nativo' : emlPreviewMode ? 'EML originale' : 'Sola lettura'}</Badge>
                </div>
                <iframe
                  className="iu-de-preview-frame"
                  src={`${doc.actions.preview}${doc.actions.preview.includes('?') ? '&' : '?'}v=${pdfRevision}`}
                  title={`Anteprima ${doc.name}`}
                />
              </section>
            </section>
          ) : null}
        </>
      ) : (
        <>
          <section className="iu-de-editor-stage">
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
                {!FONT_SIZE_OPTIONS.includes(fontSize) && <option value={fontSize}>{fontSize}</option>}
                {FONT_SIZE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            </label>
            <label className="iu-de-field iu-de-field--line"><span>Interlinea</span>
              <select aria-label="Interlinea" value={customLineHeightOpen ? 'custom' : lineHeight} onChange={(event) => {
                const custom = event.target.value === 'custom'
                if (custom) {
                  const selection = window.getSelection()
                  lineHeightRangeRef.current = selection?.rangeCount && editorRef.current?.contains(selection.anchorNode)
                    ? selection.getRangeAt(0).cloneRange() : null
                }
                setCustomLineHeightOpen(custom)
                if (!custom) changeLineHeight(event.target.value)
              }}>
                {LINE_HEIGHT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                {!LINE_HEIGHT_OPTIONS.some((option) => option.value === lineHeight) && <option value={lineHeight}>{lineHeight.replace('.', ',')}</option>}
                <option value="custom">Personalizzata…</option>
              </select>
            </label>
            {customLineHeightOpen && <div className="iu-de-custom-line">
              <label><span>Interlinea personalizzata</span><input aria-label="Interlinea personalizzata" inputMode="decimal" value={customLineHeight} onChange={(event) => setCustomLineHeight(event.target.value)} onKeyDown={(event) => {
                if (event.key === 'Enter') { event.preventDefault(); changeLineHeight(customLineHeight) }
              }}/></label>
              <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeLineHeight(customLineHeight)}>Applica</button>
            </div>}
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
            <ToolbarButton title="Tabella" onClick={openTablePicker}><Table size={16}/></ToolbarButton>
            <ToolbarButton title="Casella di testo" onClick={insertTextBox}><FileText size={16}/></ToolbarButton>
            <ToolbarButton title="Inserisci immagine" onClick={chooseImage}><ImagePlus size={16}/></ToolbarButton>
            <ToolbarButton title="Collegamento" onClick={openLink}><Link size={16}/></ToolbarButton>
            <ToolbarButton title="Aumenta rientro" onClick={() => runCommand('indent')}><ListOrdered size={16}/></ToolbarButton>
            <ToolbarButton title="Riduci rientro" onClick={() => runCommand('outdent')}><List size={16}/></ToolbarButton>
            <ToolbarButton title={voiceDictating ? 'Dettatura in corso' : 'Detta nel documento'} onClick={startEditorDictation} disabled={!editorEnabled || voiceDictating}><Mic size={16}/></ToolbarButton>
            <span className="iu-de-separator"/>
            <label className="iu-de-color" title="Colore testo"><Palette size={15}/><input type="color" onChange={(event) => runCommand('foreColor', event.target.value)} defaultValue="#111827"/></label>
            <label className="iu-de-color" title="Evidenziatore"><Highlighter size={15}/><input type="color" onChange={(event) => runCommand('hiliteColor', event.target.value)} defaultValue="#fef3c7"/></label>
            <span className="iu-de-separator"/>
            <ToolbarButton title="Annulla" onClick={() => runCommand('undo')}><Undo2 size={16}/></ToolbarButton>
            <ToolbarButton title="Ripeti" onClick={() => runCommand('redo')}><Redo2 size={16}/></ToolbarButton>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => setSearchOpen((value) => !value)}><Search size={15}/> Cerca</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => replaceFileRef.current?.click()}><UploadCloud size={15}/> Importa</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={exportDisabled} onClick={() => void exportFile(data.endpoints.exportPdf, 'pdf')}><FileDown size={15}/> PDF</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={exportDisabled} onClick={() => void exportFile(data.endpoints.exportDocx, 'docx')}><FileDown size={15}/> DOCX</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={exportDisabled} onClick={() => void exportFile(data.endpoints.exportRtf, 'rtf')}><FileDown size={15}/> RTF</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={printLoading || exportDisabled} onClick={() => void previewPrint()}><Eye size={15}/> Anteprima stampa</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={printLoading || exportDisabled} onClick={() => void previewPrint(true)}><Printer size={15}/> Stampa</button>
            <label className="iu-de-spelling-toggle"><input type="checkbox" checked={spellingEnabled} onChange={(event) => { setSpellingEnabled(event.target.checked); if (!event.target.checked) { languageRequestRef.current?.abort(); if (languageTimerRef.current) window.clearTimeout(languageTimerRef.current); setSpellingResults([]); setGrammarMarks([]); setGrammarNotice(''); grammarRequestRef.current?.abort(); setGrammarLoading(false); spellingMarksRef.current = []; clearSpellingMarks(); setSpellingChoice(null) } }}/> Italiano</label>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={grammarLoading || !data.endpoints.language} onClick={() => void checkDocumentLanguage()}>{grammarLoading ? <LoaderCircle className="iu-spin" size={15}/> : <Check size={15}/>} Controlla documento</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" disabled={phraseLoading || !data.endpoints.language} onClick={() => void suggestPhrase()}>{phraseLoading ? <LoaderCircle className="iu-spin" size={15}/> : <Wand2 size={15}/>} Suggerisci frase</button>
            </section>

            <div className="iu-de-editor-main">
          {layoutOpen && <section className="iu-de-table-picker" aria-label="Layout pagina">
            <label>Orientamento<select aria-label="Orientamento pagina" value={layoutDraft.width > layoutDraft.height ? 'landscape' : 'portrait'} onChange={(event) => {
              const short = Math.min(layoutDraft.width, layoutDraft.height), long = Math.max(layoutDraft.width, layoutDraft.height)
              setLayoutDraft({ ...layoutDraft, width: event.target.value === 'landscape' ? long : short, height: event.target.value === 'landscape' ? short : long })
            }}><option value="portrait">Verticale</option><option value="landscape">Orizzontale</option></select></label>
            {([['top', 'Superiore'], ['bottom', 'Inferiore'], ['left', 'Sinistro'], ['right', 'Destro']] as const).map(([key, label]) => <label key={key}>{label} (mm)<input aria-label={`Margine ${label.toLowerCase()}`} type="number" min="0" max="100" step="0.5" value={Number.isFinite(layoutDraft[key]) ? Number(layoutDraft[key].toFixed(2)) : ''} onChange={(event) => setLayoutDraft({ ...layoutDraft, [key]: event.target.value === '' ? NaN : Number(event.target.value) })}/></label>)}
            <button className="iu-de-tool" type="button" onClick={() => applyPageLayout(layoutDraft)}>Applica layout</button>
            <button className="iu-de-tool" type="button" onClick={() => setLayoutOpen(false)}>Annulla</button>
          </section>}
          {linkOpen && <section className="iu-de-table-picker iu-de-link-picker" aria-label="Inserisci collegamento">
            <label>Testo<input aria-label="Testo del collegamento" value={linkText} onChange={(event) => setLinkText(event.target.value)}/></label>
            <label>Indirizzo<input aria-label="Indirizzo del collegamento" type="url" value={linkUrl} onChange={(event) => setLinkUrl(event.target.value)} placeholder="https://…" onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); insertLink() } }}/></label>
            <button className="iu-de-tool" type="button" onClick={insertLink}>Inserisci collegamento</button>
            {linkExisting && <button className="iu-de-tool" type="button" onClick={() => { editorRangeRef.current = linkRangeRef.current; runCommand('unlink'); setLinkOpen(false) }}>Rimuovi collegamento</button>}
            <button className="iu-de-tool" type="button" onClick={() => setLinkOpen(false)}>Annulla</button>
          </section>}
          {(grammarNotice || grammarMarks.length > 0 || spellingResults.length > 0 || languageError || phraseSuggestion) && <section className={`iu-de-language-panel${grammarNotice && !grammarMarks.length && !spellingResults.length && !languageError && !phraseSuggestion ? ' iu-de-language-panel--notice' : ''}`} aria-label="Suggerimenti italiani" aria-live="polite">
            {grammarNotice && <p role="status">{grammarNotice}</p>}
            {grammarMarks.length > 0 && <div className="iu-de-language-words"><strong>Revisione del documento · {grammarMarks.length} {grammarMarks.length === 1 ? 'rilievo' : 'rilievi'}</strong><ul>{grammarMarks.map((mark, index) => <li key={index}><button type="button" className="iu-de-tool iu-de-tool--wide" onClick={() => { mark.paragraph.scrollIntoView({ block: 'center', behavior: 'instant' }); const rect = mark.range.getBoundingClientRect(); setSpellingChoice({ mark, x: Math.max(8, Math.min(rect.left, window.innerWidth - 288)), y: Math.max(8, Math.min(rect.bottom + 8, window.innerHeight - 260)) }) }}>{mark.word || 'Inserimento'}</button><span>{mark.message}</span></li>)}</ul></div>}
            {languageError && <p className="iu-de-language-error" role="alert">{languageError}</p>}
            {spellingResults.length > 0 && <div className="iu-de-language-words"><strong>Parole da controllare</strong><ul>{spellingResults.map((result) => <li key={result.parola}><b>{result.parola}</b><span>{result.suggerimenti.length ? result.suggerimenti.map((suggestion) => <button key={suggestion} type="button" className="iu-de-tool iu-de-tool--wide" onMouseDown={(event) => event.preventDefault()} onClick={() => { const mark = spellingMarksRef.current.find((entry) => entry.word === result.parola && entry.range.startContainer.isConnected && entry.range.toString() === entry.word); if (mark) correctSpelling(mark, suggestion); else setLanguageError('Il testo è cambiato: ripeti il controllo prima di correggere.') }}>{suggestion}</button>) : 'Non presente nel vocabolario'}</span></li>)}</ul></div>}
            {phraseSuggestion && <div className="iu-de-language-phrase"><strong>Proposta di frase</strong><p>{phraseSuggestion}</p></div>}
            <div className="iu-de-language-actions">
              {phraseSuggestion && <button type="button" className="iu-de-tool iu-de-tool--wide" onClick={() => { void navigator.clipboard.writeText(phraseSuggestion).then(() => setPhraseCopied(true)).catch(() => setLanguageError('Copia non riuscita. Seleziona la proposta e copiala con la tastiera.')) }}>{phraseCopied ? <Check size={15}/> : <Copy size={15}/>} {phraseCopied ? 'Proposta copiata' : 'Copia proposta'}</button>}
              <button type="button" className="iu-de-tool iu-de-tool--wide" onClick={() => { phraseRequestRef.current?.abort(); phraseRequestRef.current = null; setPhraseLoading(false); setSpellingResults([]); setGrammarMarks([]); setGrammarNotice(''); grammarRequestRef.current?.abort(); languageRequestRef.current?.abort(); if (languageTimerRef.current) window.clearTimeout(languageTimerRef.current); setLanguageError(''); setPhraseSuggestion('') }}><X size={15}/> Chiudi suggerimenti</button>
            </div>
          </section>}
          {tablePickerOpen && tableContext && <section className="iu-de-table-picker" aria-label="Modifica tabella">
            <strong>Tabella selezionata</strong>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('rowBefore')}>Riga sopra</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('rowAfter')}>Riga sotto</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('rowDelete')}>Elimina riga</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('columnBefore')}>Colonna a sinistra</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('columnAfter')}>Colonna a destra</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('columnDelete')}>Elimina colonna</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => changeTable('delete')}>Elimina tabella</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => setTablePickerOpen(false)}>Chiudi</button>
          </section>}
          {tablePickerOpen && !tableContext && <section className="iu-de-table-picker" aria-label="Inserisci tabella">
            <strong>Inserisci tabella</strong>
            <label>Colonne<input aria-label="Colonne tabella" type="number" min="1" max="20" step="1" value={tableColumns} onChange={(event) => setTableColumns(event.target.value)}/></label>
            <label>Righe<input aria-label="Righe tabella" type="number" min="1" max="50" step="1" value={tableRows} onChange={(event) => setTableRows(event.target.value)}/></label>
            <label className="iu-de-table-header"><input type="checkbox" checked={tableHeader} onChange={(event) => setTableHeader(event.target.checked)}/> Prima riga di intestazione</label>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={insertTable}>Inserisci</button>
            <button className="iu-de-tool iu-de-tool--wide" type="button" onClick={() => setTablePickerOpen(false)}>Annulla</button>
          </section>}


          {searchOpen ? (
            <section className="iu-de-search-panel" aria-label="Cerca e sostituisci">
              <label><span>Cerca</span><input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') findText(false) }}/></label>
              <label><span>Sostituisci con</span><input value={replaceTerm} onChange={(event) => setReplaceTerm(event.target.value)}/></label>
              <button type="button" onClick={() => findText(false)}><Search size={15}/> Successivo</button>
              <button type="button" onClick={replaceSelection}><Replace size={15}/> Sostituisci</button>
            </section>
          ) : null}

          {spellingChoice && <section className="iu-de-spelling-choice" role="region" aria-label={`Correggi ${spellingChoice.mark.word}`} style={{ left: spellingChoice.x, top: spellingChoice.y }}>
            <header><strong>{spellingChoice.mark.word}</strong><button type="button" className="iu-de-tool" aria-label="Chiudi correzioni" onClick={() => setSpellingChoice(null)}><X size={15}/></button></header>
            {spellingChoice.mark.message && <p>{spellingChoice.mark.message}</p>}
            <div>{spellingChoice.mark.suggestions.length ? spellingChoice.mark.suggestions.map((suggestion) => <button key={suggestion} type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => correctSpelling(spellingChoice.mark, suggestion)}>{suggestion}</button>) : <p>Nessuna alternativa nel vocabolario italiano.</p>}</div>
          </section>}
          <section className="iu-de-workbench">
            {documentFactsOpen ? <div id="iu-de-document-facts" className="iu-de-facts-panel"><DocumentFacts data={data}/></div> : null}
            <section className="iu-de-paper-shell" style={paperStyle}>
              <div className="iu-de-paper">
                {documentLoading ? <div className="iu-de-loader"><LoaderCircle className="iu-spin" size={24}/><span>Caricamento contenuto...</span></div> : null}
                <div
                  ref={editorRef}
                  className="iu-de-editable"
                  contentEditable={editorEnabled}
                  suppressContentEditableWarning
                  role="textbox"
                  aria-multiline="true"
                  lang="it-IT"
                  aria-label={`Contenuto modificabile ${doc.name}`}
                  spellCheck={false}
                  onInput={handleEditorInput}
                  onClick={(event) => {
                    const mark = spellingMarksRef.current.find((entry) => entry.range.toString() === entry.word && Array.from(entry.range.getClientRects()).some((rect) => event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom))
                    if (!mark) { setSpellingChoice(null); return }
                    const rect = mark.range.getBoundingClientRect()
                    setSpellingChoice({ mark, x: Math.max(8, Math.min(rect.left, window.innerWidth - 292)), y: Math.max(8, Math.min(rect.bottom + 8, window.innerHeight - 240)) })
                  }}
                  onKeyDown={(event) => { if (event.key === 'Escape') setSpellingChoice(null) }}
                  onBeforeInput={() => { if (editorRef.current) editorHistoryRef.current.rememberCaret(editorCaret(editorRef.current)) }}
                  onPaste={handlePaste}
                />
              </div>
            </section>
          </section>
            </div>
          </section>

        </>
      )}

      <input
        ref={imageFileRef}
        type="file"
        hidden
        accept="image/png,image/jpeg,image/webp"
        onChange={(event) => { void insertImage(event.target.files?.[0]); event.target.value = '' }}
      />
      {printPreviewUrl && <div className="iu-de-print-preview" role="dialog" aria-modal="true" aria-label="Anteprima di stampa">
        <header><strong>Anteprima di stampa</strong><button className="iu-de-tool" type="button" disabled={printLoading || Boolean(printError)} onClick={() => printFrameRef.current?.contentWindow?.print()}><Printer size={15}/> Stampa</button><button className="iu-de-tool" type="button" aria-label="Chiudi anteprima" onClick={closePrintPreview}>Chiudi anteprima</button></header>
        <div className="iu-de-print-workspace">
        <aside className="iu-de-print-settings" aria-label="Impostazioni anteprima di stampa">
          <strong title={doc.name}>{doc.name}</strong>
          <label>Pagina<select aria-label="Pagina anteprima" value={printPage} disabled={!printPages} onChange={(event) => {
            setPrintPage(event.target.value)
            printFrameRef.current?.contentDocument?.querySelectorAll('.pagina')[Number(event.target.value) - 1]?.scrollIntoView({ block: 'start' })
          }}>{Array.from({ length: printPages }, (_, i) => <option key={i} value={String(i + 1)}>{i + 1} di {printPages}</option>)}</select></label>
          <label>Zoom<select aria-label="Zoom anteprima" value={printZoom} onChange={(event) => updatePrintZoom(event.target.value)}><option value="fit">Adatta alla larghezza</option>{[25,50,75,100,125,150,175,200].map((value) => <option key={value} value={String(value)}>{value}%</option>)}</select></label>
          <fieldset><legend>Impaginazione</legend>
            <label>Orientamento<select aria-label="Orientamento anteprima" value={layoutDraft.width > layoutDraft.height ? 'landscape' : 'portrait'} onChange={(event) => setLayoutDraft((layout) => ({ ...layout, width: event.target.value === 'landscape' ? Math.max(layout.width, layout.height) : Math.min(layout.width, layout.height), height: event.target.value === 'landscape' ? Math.min(layout.width, layout.height) : Math.max(layout.width, layout.height) }))}><option value="portrait">Verticale</option><option value="landscape">Orizzontale</option></select></label>
            <span>Margini in millimetri, tutte le sezioni</span>
            <div className="iu-de-print-margins">{([['top','Superiore'],['bottom','Inferiore'],['left','Sinistro'],['right','Destro']] as const).map(([key,label]) => <label key={key}>{label}<input aria-label={`Margine ${label.toLowerCase()} anteprima`} type="number" min="0" max="100" step="0.5" value={Number.isFinite(layoutDraft[key]) ? Number(layoutDraft[key].toFixed(2)) : ''} onChange={(event) => setLayoutDraft((layout) => ({ ...layout, [key]: event.target.value === '' ? NaN : Number(event.target.value) }))}/></label>)}</div>
            <button className="iu-de-tool" type="button" disabled={printLoading} onClick={() => {
              if (applyPageLayout(layoutDraft)) void previewPrint()
              else setPrintError('Margini non validi: lascia spazio per il documento.')
            }}>{printLoading ? 'Aggiornamento…' : 'Applica e aggiorna'}</button>
          </fieldset>
          {printError && <p className="iu-de-print-error" role="alert">{printError}<button className="iu-de-tool" type="button" disabled={printLoading} onClick={() => void previewPrint()}>Riprova anteprima</button></p>}
          <button className="iu-de-tool" type="button" onClick={() => {
            closePrintPreview()
            editorRef.current?.focus()
          }}>Modifica testo</button>
          <small>Le modifiche di impaginazione aggiornano il documento. Salva DOCX per conservarle nel fascicolo.</small>
        </aside>
        <iframe ref={printFrameRef} title="Documento pronto per la stampa" src={printPreviewUrl} onLoad={() => {
          const pages = printFrameRef.current?.contentDocument?.querySelectorAll<HTMLElement>('.pagina')
          pages?.forEach((page) => { page.dataset.widthMm = String(Number.parseFloat(page.style.width || getComputedStyle(page).width) * (page.style.width.endsWith('mm') ? 1 : 25.4 / 96)) })
          setPrintPages(pages?.length || 0)
          setPrintPage('1')
          updatePrintZoom(printZoom)
          if (printWhenReadyRef.current) { printWhenReadyRef.current = false; printFrameRef.current?.contentWindow?.print() }
        }}/>
        </div>
      </div>}
      <input
        ref={replaceFileRef}
        type="file"
        hidden
        accept=".pdf,.doc,.docx,.txt,.html,.htm,.md"
        onChange={(event) => {
          setPendingImportFile(event.target.files?.[0] ?? null)
          event.target.value = ''
        }}
      />
      <ConfirmDialog
        title="Importa documento"
        open={pendingImportFile !== null}
        message={`Importare "${pendingImportFile?.name ?? ''}" nell'anteprima? Il documento del fascicolo verrà versionato.${dirty ? ' La bozza corrente sarà sostituita dal documento importato.' : ''}`}
        onCancel={() => setPendingImportFile(null)}
        onConfirm={() => {
          const file = pendingImportFile
          setPendingImportFile(null)
          if (file) void importFile(file)
        }}
      />

      <FloatingLex
        context="editor-documento"
        title="Lex AI editor"
        body="Posso aiutarti a controllare coerenza dell'atto, punti mancanti, stile professionale e collegamenti con il fascicolo aperto."
        primaryHref={data.fascicolo.detailHref || '/fascicoli'}
        primaryLabel="Apri Lex editor"
        secondaryHref={data.fascicolo.detailHref}
        secondaryLabel="Fascicolo"
      />
    </main>
  )
}
