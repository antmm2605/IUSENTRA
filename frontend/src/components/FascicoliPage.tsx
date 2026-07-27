import { Fragment, Suspense, lazy, useCallback, useEffect, useId, useMemo, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from 'react'
import {
  Archive,
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Bell,
  BrainCircuit,
  BriefcaseBusiness,
  Building2,
  Calculator,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ClipboardCheck,
  Clock3,
  Copy,
  Download,
  Edit3,
  Euro,
  Eye,
  FileArchive,
  FileCheck2,
  FileDown,
  FileSignature,
  FileText,
  Fingerprint,
  Filter,
  FolderSearch2,
  FolderOpen,
  FolderPlus,
  Gauge,
  Gavel,
  Landmark,
  ListChecks,
  Mail,
  MapPin,
  Maximize2,
  Minimize2,
  PackageCheck,
  PencilLine,
  Phone,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Save,
  Trash2,
  UploadCloud,
  UserRound,
  UsersRound,
  Video,
  WalletCards,
  X,
  type LucideIcon,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { SyncedTopScrollbar } from './SyncedTopScrollbar'
import {
  IusentraContextFilters,
  IusentraDataSurface,
  IusentraFiltersBar,
  IusentraMainArea,
  IusentraMainSurface,
  IusentraPageShell,
  IusentraPanelCard,
  IusentraSupportRail,
} from './iusentra'
import {
  emptyFascicoliPage,
  emptyFascicoloDetail,
  emptyFascicoloForm,
  emptyFascicoliExport,
  formatFascicoloStatus,
  formatFascicoloType,
  getFascicoliArchive,
  getFascicoliExport,
  getFascicoliPage,
  getFascicoliFilterPreferences,
  getFascicoloDetail,
  getFascicoloDetailSection,
  getFascicoloForm,
  generateFascicoloProforma,
  runFascicoliEconomicPresidio,
  saveFascicoliFilterPreferences,
  updateFascicoloPayment,
  updateFascicoloStatus,
  defaultFascicoliFilterPreferences,
  fascicoloPaymentKinds,
  type FascicoliFilterPreferences,
  type FascicoliPageData,
  type FascicoliPageParams,
  type FascicoloPaymentFilter,
  type FascicoliExportData,
  type FascicoloActivity,
  type FascicoloAuditTrail,
  type FascicoloDeadline,
  type FascicoloDetailData,
  type FascicoloDeposit,
  type FascicoloDepositCatalog,
  type FascicoloDepositCatalogEntry,
  type FascicoloDocument,
  type FascicoloDetailSection,
  type FascicoloFull,
  type LexIndexingSummary,
  type FascicoloFormData,
  type FascicoloRow,
  type FascicoloSentenzeEconomiche,
  type FascicoloPaymentKind,
  type FascicoloPaymentItem,
  type FascicoloProformaBasis,
  type FascicoloPaymentUpdatePayload,
  type FascicoloPaymentSummary,
  type FascicoloPaymentStatus,
  type FascicoloStato,
  type FascicoloTipo,
  type KeyValue,
  type SelectOption,
  type FascicoliPagination,
} from '../fascicoliData'
import {
  NUOVO_FASCICOLO_LABELS,
  STATI_PRATICA,
  codiceOggettoPstSource,
  findPraticaCollegata,
} from '../data/praticheCollegateCatalog'
import { csrfToken, redirectAfterSuccess, submitFormJson } from '../formSubmit'
import { formatDateIt, formatDateTimeIt, formatEuroIt } from '../formatting'
import { normaliseStudioRuntimeResult, type StudioRuntimeOffice, type StudioRuntimeResult } from '../studioModuleRuntime'
import { CodiceOggettoPstSearch } from './CodiceOggettoPstSearch'
import { GuidaPraticaSidebar } from './GuidaPraticaSidebar'
import './FascicoliPage.css'

const FascicoloDepositoPage = lazy(() => import('./FascicoloDepositoPage').then((module) => ({ default: module.FascicoloDepositoPage })))
const OfficeDocumentsPanel = lazy(() => import('./OfficeDocumentsPanel').then((module) => ({ default: module.OfficeDocumentsPanel })))

const PAGOPA_PST_URL = 'https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp'
const PAGOPA_PST_NEW_PAYMENT_URL = 'https://servizipst.giustizia.it/PST/it/pagopa_nuovarich.wp'
const PAGOPA_PROXY_URL = '/api/v1/ui/pst/pagopa-proxy/it/pagopa_altripag.wp'
const PAGOPA_PROXY_NEW_PAYMENT_URL = '/api/v1/ui/pst/pagopa-proxy/it/pagopa_nuovarich.wp'
const PAGOPA_LOGO_URL = '/static/react/pagopa-removebg-preview.png'

type SortKey = 'recenti' | 'rg' | 'cliente' | 'scadenza' | 'documenti'
type Route =
  | { kind: 'list' }
  | { kind: 'archive' }
  | { kind: 'new' }
  | { kind: 'export' }
  | { kind: 'detail'; id: string }
  | { kind: 'quadro'; id: string }
  | { kind: 'depositPrepare'; id: string }
  | { kind: 'signature'; id: string; documentId: string }
  | { kind: 'edit'; id: string }

type ComuneOption = {
  codiceIstat: string
  nome: string
  label: string
  cap: string[]
  siglaProvincia: string
  provincia: string
}

const FASCICOLO_OFFICE_KIND_FILTERS = [
  { value: '', label: 'Tutti' },
  { value: 'giudice_pace', label: 'GDP' },
  { value: 'tribunale', label: 'Tribunale' },
  { value: 'unep', label: 'UNEP' },
  { value: 'procura', label: 'Procura' },
  { value: 'corte_appello', label: 'Corte appello' },
  { value: 'tribunale_minorenni', label: 'Minorenni' },
]

function comuneOptionFromPayload(value: unknown): ComuneOption | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const row = value as Record<string, unknown>
  const cap = Array.isArray(row.cap) ? row.cap.map((item) => String(item || '').trim()).filter(Boolean) : []
  const option = {
    codiceIstat: recordText(row, 'codiceIstat'),
    nome: recordText(row, 'nome'),
    label: recordText(row, 'label'),
    cap,
    siglaProvincia: recordText(row, 'siglaProvincia'),
    provincia: recordText(row, 'provincia'),
  }
  return option.codiceIstat && option.nome ? option : null
}

function comuneOptionMatches(option: ComuneOption | null, value: string): boolean {
  if (!option) return false
  const query = normaliseText(value.trim())
  return Boolean(query) && [option.nome, option.label].some((item) => normaliseText(item) === query)
}

function officeDepositoCode(office: StudioRuntimeOffice): string {
  return office.codice
}

function officeCodeMeta(office: StudioRuntimeOffice): string {
  return compactMeta([
    office.codice || office.codiceMinistero ? 'deposito telematico verificato' : '',
    office.codiceGiustiziaLocale ? 'collegamento ufficiale verificato' : '',
    office.istatCode ? 'sede verificata' : '',
  ])
}

const sortLabels: Record<SortKey, string> = {
  recenti: 'Aggiornati di recente',
  rg: 'Anno e numero RG',
  cliente: 'Cliente',
  scadenza: 'Prossima scadenza',
  documenti: 'Documenti',
}

const paymentFullLabels: Record<FascicoloPaymentKind, string> = {
  contributo_unificato: 'Contributo unificato',
  spese_esborsi: 'Spese/esborsi',
  fondo_spese: 'Fondo spese',
  liquidazione_giudice: 'Liquidazione giudice',
  parcella: 'Parcella',
}

const paymentColumnLabels: Record<FascicoloPaymentKind, string> = {
  contributo_unificato: 'Contributo',
  spese_esborsi: 'Spese/esborsi',
  fondo_spese: 'Fondo spese',
  liquidazione_giudice: 'Liquidazione',
  parcella: 'Parcella',
}

const economicPaymentKinds: FascicoloPaymentKind[] = fascicoloPaymentKinds.filter((kind) => kind !== 'fondo_spese')

const paymentStatusOptions: Array<{ value: FascicoloPaymentStatus; label: string }> = [
  { value: 'da_registrare', label: 'Da registrare' },
  { value: 'pagato', label: 'Pagato' },
  { value: 'parziale', label: 'Parziale' },
  { value: 'non_previsto', label: 'Non previsto' },
  { value: 'da_emettere', label: 'Da emettere' },
]

// Elenco unico con due viste: operativa (default) ed economica.
// La vista è persistita nell'URL (?vista=economica) per bookmark e deep link.
type ListView = 'operativa' | 'economica'

const paymentFilterOptions: Array<{ value: FascicoloPaymentFilter; label: string }> = [
  { value: 'tutti', label: 'Tutti' },
  ...paymentStatusOptions,
]

// Stati impostabili inline dall'elenco. "da_archiviare" è derivato
// (DEFINITO + archivio pronto) e non è un target selezionabile.
const fascicoloStatusEditOptions: Array<{ value: Exclude<FascicoloStato, 'tutti'>; label: string }> = [
  { value: 'aperto', label: 'Aperto' },
  { value: 'in_corso', label: 'In corso' },
  { value: 'sospeso', label: 'Sospeso' },
  { value: 'definito', label: 'Definito' },
  { value: 'archiviato', label: 'Archiviato' },
]

function initialListView(): ListView {
  const params = new URLSearchParams(window.location.search)
  return (params.get('vista') || params.get('view')) === 'economica' ? 'economica' : 'operativa'
}

function syncListViewInUrl(view: ListView) {
  const url = new URL(window.location.href)
  if (view === 'economica') url.searchParams.set('vista', 'economica')
  else url.searchParams.delete('vista')
  window.history.replaceState({}, '', url.toString())
}

type ListContextTarget = {
  view?: ListView
  status?: FascicoloStato
  sort?: SortKey
  alertsOnly?: boolean
  paymentsOnly?: boolean
  missingRgOnly?: boolean
  duplicatesOnly?: boolean
  cu?: FascicoloPaymentFilter
  liquidazione?: FascicoloPaymentFilter
  parcella?: FascicoloPaymentFilter
  hash?: string
}

function syncListContextInUrl(target: ListContextTarget) {
  const url = new URL('/fascicoli', window.location.origin)
  if (target.view === 'economica') url.searchParams.set('vista', 'economica')
  if (target.status && target.status !== 'tutti') url.searchParams.set('status', target.status)
  if (target.sort && target.sort !== 'rg') url.searchParams.set('sort', target.sort)
  if (target.alertsOnly) url.searchParams.set('alerts_only', '1')
  if (target.paymentsOnly) url.searchParams.set('payments_only', '1')
  if (target.missingRgOnly) url.searchParams.set('missing_rg_only', '1')
  if (target.duplicatesOnly) url.searchParams.set('duplicates_only', '1')
  if (target.cu && target.cu !== 'tutti') url.searchParams.set('cu', target.cu)
  if (target.liquidazione && target.liquidazione !== 'tutti') url.searchParams.set('liquidazione', target.liquidazione)
  if (target.parcella && target.parcella !== 'tutti') url.searchParams.set('parcella', target.parcella)
  window.history.replaceState({}, '', `${url.pathname}${url.search}${target.hash || ''}`)
}

function initialUrlParam(name: string, fallback = ''): string {
  return new URLSearchParams(window.location.search).get(name) || fallback
}

function initialUrlBool(...names: string[]): boolean {
  const params = new URLSearchParams(window.location.search)
  return names.some((name) => ['1', 'true', 'si', 'sì'].includes((params.get(name) || '').toLowerCase()))
}

function hasExplicitListPreferenceParams(): boolean {
  const params = new URLSearchParams(window.location.search)
  return [
    'q',
    'client',
    'rg',
    'type',
    'status',
    'court',
    'sort',
    'view',
    'vista',
    'alerts_only',
    'alertsOnly',
    'payments_only',
    'paymentsOnly',
    'missing_rg_only',
    'missingRgOnly',
    'duplicates_only',
    'duplicatesOnly',
    'cu',
    'contributo_unificato',
    'fondo_spese',
    'fondoSpese',
    'liquidazione',
    'liquidazione_giudice',
    'parcella',
    'page_size',
    'pageSize',
  ].some((name) => params.has(name))
}

function initialStatusFilter(): FascicoloStato {
  const raw = initialUrlParam('status').toLowerCase()
  return ['aperto', 'in_corso', 'definito', 'da_archiviare', 'archiviato', 'sospeso'].includes(raw) ? raw as FascicoloStato : 'tutti'
}

function initialSortFilter(): SortKey {
  const raw = initialUrlParam('sort', 'rg').toLowerCase()
  return ['recenti', 'rg', 'cliente', 'scadenza', 'documenti'].includes(raw) ? raw as SortKey : 'rg'
}

function initialPaymentFilter(name: string): FascicoloPaymentFilter {
  const raw = initialUrlParam(name).toLowerCase()
  return ['non_previsto', 'da_registrare', 'pagato', 'parziale', 'da_emettere'].includes(raw) ? raw as FascicoloPaymentFilter : 'tutti'
}

function toSavedSortKey(value: string): SortKey {
  return ['recenti', 'rg', 'cliente', 'scadenza', 'documenti'].includes(value) ? value as SortKey : defaultFascicoliFilterPreferences.sort as SortKey
}

function toSavedListView(value: string): ListView {
  return value === 'economica' ? 'economica' : 'operativa'
}

function toSavedPaymentFilter(value: string): FascicoloPaymentFilter {
  return ['non_previsto', 'da_registrare', 'pagato', 'parziale', 'da_emettere'].includes(value) ? value as FascicoloPaymentFilter : 'tutti'
}

function filterPreferencesSignature(preferences: FascicoliFilterPreferences): string {
  return JSON.stringify({
    type: preferences.type,
    status: preferences.status,
    sort: preferences.sort,
    view: preferences.view,
    court: preferences.court.trim(),
    alertsOnly: preferences.alertsOnly,
    paymentsOnly: preferences.paymentsOnly,
    missingRgOnly: preferences.missingRgOnly,
    duplicatesOnly: preferences.duplicatesOnly,
    cu: preferences.cu,
    liquidazione: preferences.liquidazione,
    parcella: preferences.parcella,
    pageSize: preferences.pageSize,
  })
}

function fascicoliListCacheKey(params: FascicoliPageParams): string {
  const normalized = [
    params.page || 1,
    params.pageSize || 25,
    (params.q || '').trim(),
    params.type || 'tutti',
    params.status || 'tutti',
    (params.court || '').trim(),
    params.sort || 'rg',
    params.view || 'operativa',
    params.alertsOnly ? '1' : '0',
    params.paymentsOnly ? '1' : '0',
    params.missingRgOnly ? '1' : '0',
    params.duplicatesOnly ? '1' : '0',
    params.cu || 'tutti',
    params.fondoSpese || 'tutti',
    params.liquidazione || 'tutti',
    params.parcella || 'tutti',
  ]
  return normalized.map((value) => encodeURIComponent(String(value))).join('|')
}

function formatCurrency(value: number): string {
  return formatEuroIt(value)
}

function parseRoute(): Route {
  const rawPath = window.location.pathname.replace(/\/+$/, '') || '/'
  const path = rawPath.startsWith('/app-v2/fascicoli') ? rawPath.slice('/app-v2'.length) || '/fascicoli' : rawPath
  const prefix = '/fascicoli'
  const rest = path.startsWith(prefix) ? path.slice(prefix.length).replace(/^\//, '') : ''
  if (!rest) return { kind: 'list' }
  if (rest === 'archivio') return { kind: 'archive' }
  if (rest === 'nuovo') return { kind: 'new' }
  if (rest === 'esporta' || rest === 'export') return { kind: 'export' }
  const parts = rest.split('/').filter(Boolean)
  if (parts.length >= 4 && parts[1] === 'documenti' && parts[3] === 'firma') {
    return { kind: 'signature', id: decodeURIComponent(parts[0]), documentId: decodeURIComponent(parts[2]) }
  }
  if (parts.length >= 3 && parts[1] === 'deposito' && parts[2] === 'prepara') return { kind: 'depositPrepare', id: decodeURIComponent(parts[0]) }
  if (parts.length >= 2 && parts[1] === 'quadro') return { kind: 'quadro', id: decodeURIComponent(parts[0]) }
  if (parts.length >= 2 && parts[1] === 'modifica') return { kind: 'edit', id: decodeURIComponent(parts[0]) }
  return { kind: 'detail', id: decodeURIComponent(parts[0] || '') }
}

function normaliseText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function isInsideQuery(item: FascicoloRow, query: string): boolean {
  const needle = normaliseText(query.trim())
  if (!needle) return true
  const haystack = normaliseText([
    item.ref,
    item.internalRef,
    item.title,
    item.subtitle,
    item.client,
    item.court,
    item.rg,
    formatFascicoloType(item.type),
    formatFascicoloStatus(item.status),
  ].join(' '))
  return haystack.includes(needle)
}

function openDetailSectionById(id: string) {
  const element = document.getElementById(id)
  if (element instanceof HTMLDetailsElement && !element.open) element.open = true
  if (element) window.requestAnimationFrame(() => element.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  if (window.location.hash !== `#${id}`) window.history.replaceState(null, '', `#${id}`)
}

function relataListHref(item: FascicoloRow): string {
  return item.relataHref || `${item.href}#relata-notifica`
}

const statCardContextHref: Record<string, string> = {
  Attivi: '/fascicoli',
  'In corso': '?status=in_corso',
  'Da archiviare': '?status=da_archiviare',
  Economico: '?vista=economica&payments_only=1',
  Registrato: '?vista=economica',
  Parcelle: '?vista=economica&parcella=da_emettere',
  'Scadenze urgenti': '#scadenze-urgenti',
  Doppioni: '?duplicates_only=1',
  'RG da acquisire': '?missing_rg_only=1',
  Documenti: '?sort=documenti',
  Comunicazioni: '?alerts_only=1',
}

function countIt(value: number, singular: string, plural: string): string {
  return `${value} ${value === 1 ? singular : plural}`
}

function deadlineUrgencyCopy(summary: FascicoliPageData['summary']) {
  const overdue = Number(summary.overdueDeadlines || 0)
  const upcoming7 = Number(summary.deadlines7 || 0)
  const urgent = Number(summary.urgentDeadlines || 0) || overdue + upcoming7
  const note = `${countIt(overdue, 'scaduta', 'scadute')}, ${countIt(upcoming7, 'entro 7 giorni', 'entro 7 giorni')}`
  const title = overdue && upcoming7
    ? 'Scadenze scadute e prossimi 7 giorni'
    : overdue
      ? 'Scadenze scadute'
      : 'Scadenze entro 7 giorni'
  const tone: FascicoloRow['tone'] = overdue ? 'danger' : urgent ? 'warning' : 'success'
  return { overdue, upcoming7, urgent, note, title, tone }
}

function StatCard({ icon, label, value, note, tone = 'primary', href, onClick }:{icon:ReactNode; label:string; value:number|string; note:string; tone?:FascicoloRow['tone']; href?:string; onClick?:(event:MouseEvent<HTMLAnchorElement>)=>void}) {
  const isFascicoliListRoute = window.location.pathname.replace(/\/+$/, '') === '/fascicoli'
  const contextHref = href || (isFascicoliListRoute ? statCardContextHref[label] : '') || ''
  const body = (
    <>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </>
  )
  return contextHref ? <a className={`iu-fas-stat iu-fas-stat--${tone}`} href={contextHref} onClick={onClick} title={`Visualizza contesto: ${label}`} aria-label={`Visualizza contesto: ${label}`}>{body}</a> : <article className={`iu-fas-stat iu-fas-stat--${tone}`}>{body}</article>
}

function EmptyState({ icon, title, children, action }:{icon:ReactNode; title:string; children:ReactNode; action?:ReactNode}) {
  return (
    <section className="iu-fas-empty">
      <div>{icon}</div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </section>
  )
}

type ActionPayload = {
  ok?: boolean
  messaggio?: string
  message?: string
  errore?: string
  error?: string
  redirect_url?: string
  requires_guided_completion?: boolean
  requires_local_signature?: boolean
  requires_local_pec?: boolean
  package_ready?: boolean
  id_deposito?: string
  pec_dest?: string
  oggetto_pec?: string
  corpo_pec?: string
  documenti_busta?: string[]
  next_actions?: string[]
  busta_audit?: Record<string, unknown>
  pec_sender_ready?: boolean
  local_pec?: Record<string, unknown>
  local_signature?: Record<string, unknown>
  compatibility_report?: Record<string, unknown>
}

function PostAction({ action, children, tone = 'secondary', confirm, confirmTitle = 'Conferma operazione', onDone, onError, redirectTo, title, ariaLabel }:{action:string; children:ReactNode; tone?:'primary'|'secondary'|'danger'|'ghost'; confirm?:string; confirmTitle?:string; onDone?:(message?:string)=>void; onError?:(message:string)=>void; redirectTo?:string; title?:string; ariaLabel?:string}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (!action) return null
  const run = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const contentType = response.headers.get('content-type') || ''
      const payload = contentType.includes('application/json') ? await response.json().catch(() => ({} as ActionPayload)) : {} as ActionPayload
      if (!response.ok || payload.ok === false) throw new Error(String(payload.messaggio || payload.errore || payload.error || `Operazione non riuscita: HTTP ${response.status}`))
      const message = String(payload.messaggio || payload.message || '')
      setConfirming(false)
      if (onDone) {
        onDone(message)
        return
      }
      const target = String(payload.redirect_url || redirectTo || response.url || '')
      if (target) window.location.href = target
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Operazione non riuscita.'
      setError(message)
      onError?.(message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <button className={`iu-fas-post iu-fas-post--${tone}`} type="button" onClick={() => confirm ? setConfirming(true) : void run()} disabled={busy} title={title} aria-label={ariaLabel}>
        {busy ? <span className="iu-fas-post__busy"><RefreshCw size={15}/> Operazione...</span> : children}
      </button>
      {!confirming && error ? <span className="iu-fas-inline-error" role="alert">{error}</span> : null}
      {confirming ? (
        <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label={confirmTitle}>
          <div className="iu-fas-confirm-modal__box">
            <strong>{confirmTitle}</strong>
            <p>{confirm}</p>
            {error ? <span className="iu-fas-inline-error">{error}</span> : null}
            <footer>
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}>Annulla</button>
              <button className="is-danger" type="button" onClick={run} disabled={busy}>{busy ? 'Operazione...' : 'Conferma'}</button>
            </footer>
          </div>
        </div>
      ) : null}
    </>
  )
}

type DepositActionPayload = Record<string, string | string[]>
type BatchSignatureResult = { pinSessionId?: string; pinSessionTtlSeconds?: number }
type BatchSignatureAction = () => Promise<BatchSignatureResult | void>
type LocalSignatureCompletion = { payload: ActionPayload; submittedPayload: DepositActionPayload }
type DepositDocumentRole = 'atto_principale' | 'procura' | 'allegato_prova' | 'allegato' | 'prova_notifica' | 'fuori_busta'

type DepositPackagePreview = {
  idDeposito: string
  pecDest: string
  oggettoPec: string
  corpoPec: string
  documenti: string[]
  nextActions: string[]
  packageReady: boolean
  requiresGuidedCompletion: boolean
  requiresLocalPec: boolean
  localPec: Record<string, unknown>
  bustaAudit: Record<string, unknown>
  compatibilityReport: Record<string, unknown>
  pecSenderReady: boolean
  message: string
}

type LocalPecPasswordRequest = {
  from: string
  username: string
  to: string
  subject: string
  attachments: string[]
  resolve: (password: string) => void
  reject: (error: Error) => void
}

const SIGNATURE_INPUT_REQUIRED_PREFIX = 'SIGNATURE_INPUT_REQUIRED:'

function signatureInputRequired(message: string): Error {
  return new Error(`${SIGNATURE_INPUT_REQUIRED_PREFIX}${message}`)
}

function signatureInputRequiredMessage(message: string): string {
  return message.startsWith(SIGNATURE_INPUT_REQUIRED_PREFIX)
    ? message.slice(SIGNATURE_INPUT_REQUIRED_PREFIX.length).trim()
    : ''
}

type DepositDocumentClassification = {
  selected: boolean
  role: DepositDocumentRole
  alreadySigned: boolean
  requiresSignature?: boolean
}

type DepositCatalogPreviewOption = FascicoloDepositCatalogEntry

type DepositCatalogPreviewCategory = {
  id: string
  label: string
  total: number
  options: DepositCatalogPreviewOption[]
}

type DepositCatalogPreviewMacro = {
  id: string
  label: string
  total: number
  service: string
  categories: DepositCatalogPreviewCategory[]
}

const DEPOSIT_DOCUMENT_ROLE_OPTIONS: Array<{ value: DepositDocumentRole; label: string }> = [
  { value: 'atto_principale', label: 'Atto principale' },
  { value: 'procura', label: 'Procura alle liti' },
  { value: 'allegato', label: 'Allegato' },
  { value: 'prova_notifica', label: 'Prova notifica' },
  { value: 'fuori_busta', label: 'Fuori busta' },
]

type DepositCatalogPreviewState = {
  total: number
  macroareas: DepositCatalogPreviewMacro[]
}

const EMPTY_DEPOSIT_CATALOG_PREVIEW: DepositCatalogPreviewState = { total: 0, macroareas: [] }

function buildDepositCatalogPreviewState(catalog: FascicoloDepositCatalog | undefined): DepositCatalogPreviewState {
  const entries = (catalog?.entries || []).filter((entry) => Boolean(entry.key))
  const entryByKey = new Map(entries.map((entry) => [entry.key, entry]))
  const macroareas = (catalog?.macroareas || [])
    .map((macro) => ({
      id: macro.id,
      label: macro.label,
      total: macro.total,
      service: macro.service,
      categories: macro.categories.map((category) => ({
        id: category.id,
        label: category.label,
        total: category.total,
        options: category.optionKeys.map((key) => entryByKey.get(key)).filter(Boolean) as DepositCatalogPreviewOption[],
      })).filter((category) => category.options.length > 0),
    }))
    .filter((macro) => macro.categories.length > 0)
  return {
    total: catalog?.counts.totalDepositTypes || entries.length,
    macroareas: macroareas.length ? macroareas : buildDepositCatalogPreviewMacroareasFromEntries(entries),
  }
}

function buildDepositCatalogPreviewMacroareasFromEntries(entries: FascicoloDepositCatalogEntry[]): DepositCatalogPreviewMacro[] {
  const orderedMacroNames = entries.map((entry) => entry.macro).filter(Boolean).filter((macro, index, all) => all.indexOf(macro) === index)
  return orderedMacroNames.map((macroName) => {
    const macroEntries = entries.filter((entry) => entry.macro === macroName)
    const categoryNames = macroEntries.map((entry) => entry.category).filter(Boolean).filter((category, index, all) => all.indexOf(category) === index)
    return {
      id: depositCatalogSlug(macroName),
      label: macroName,
      total: macroEntries.length,
      service: macroEntries[0]?.ui.service || macroEntries[0]?.registry.label || '',
      categories: categoryNames.map((categoryName) => {
        const categoryEntries = macroEntries.filter((entry) => entry.category === categoryName)
        return {
          id: `${depositCatalogSlug(macroName)}-${depositCatalogSlug(categoryName)}`,
          label: categoryName,
          total: categoryEntries.length,
          options: categoryEntries,
        }
      }).filter((category) => category.options.length > 0),
    }
  }).filter((macro) => macro.categories.length > 0)
}

function depositCatalogSlug(value: string) {
  const normalized = value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  return normalized.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'catalogo'
}

const DEPOSIT_PROGRESS_USER_STEPS = [
  'Controllo dati deposito',
  'Firma controlli',
  'Indice documenti',
  'Preparazione pacchetto',
  'Verifica finale',
]

function depositUserControlLabel(value: string): string {
  const text = normaliseText(value)
  if (/datiatto|metadat/.test(text)) return 'Dati deposito'
  if (/indicebusta/.test(text)) return 'Indice del pacchetto'
  if (/indicedocumenti|indice document/.test(text)) return 'Indice documenti'
  if (/atto\.enc|aes|certificato|\.cer|pst/.test(text)) return 'Pacchetto protetto'
  if (/pec locale/.test(text)) return 'Invio PEC dal PC in uso'
  if (/codice deposito|codice oggetto/.test(text)) return 'Codice deposito'
  if (/ufficio/.test(text)) return 'Ufficio giudiziario'
  if (/registro/.test(text)) return 'Registro e ruolo'
  return value
}

function uniqueDepositUserList(values: string[]): string[] {
  const result: string[] = []
  for (const item of values.map(depositUserControlLabel).filter(Boolean)) {
    if (!result.includes(item)) result.push(item)
  }
  return result
}

function depositUserTransportLabel(entry: FascicoloDepositCatalogEntry): string {
  const transport = normaliseText(`${entry.ui.transport} ${entry.channel}`)
  if (/unep|notific/.test(transport)) return 'Flusso notifiche separato'
  if (/portale|upload/.test(transport)) return 'Caricamento sul portale ufficiale'
  if (/pec|atto|busta|datiatto|indice/.test(transport)) return 'Preparazione busta e invio PEC dal PC in uso'
  return entry.ui.transport || 'Preparazione deposito'
}

function depositAttachmentDisplayName(value: string): string {
  const text = value.trim()
  if (!text) return ''
  const lowered = text.toLowerCase()
  if (lowered === 'atto.enc' || /datiatto|indicebusta|cms|pkcs|\.cer|aes256/.test(lowered)) return 'Pacchetto deposito'
  if (lowered === 'indicedocumentidepositati.pdf') return 'Indice documenti'
  return text
}

function depositUserFacingMessage(value: string): string {
  const raw = value.trim()
  if (!raw) return ''
  let result = raw
  result = result.replace(/Studio Telematico|QuickOrganizer/gi, 'IUSENTRA')
  result = result.replace(/DatiAtto\.xml(?:\.p7m)?/gi, 'dati del deposito')
  result = result.replace(/IndiceBusta\.xml/gi, 'indice del pacchetto')
  result = result.replace(/IndiceDocumentiDepositati\.PDF/gi, 'indice documenti')
  result = result.replace(/Atto\.msg/gi, 'messaggio di deposito')
  result = result.replace(/Atto\.enc/gi, 'pacchetto deposito')
  result = result.replace(/AES256|CMS EnvelopedData|PKCS#?7/gi, 'formato protetto')
  result = result.replace(/\.cer/gi, "certificato dell'ufficio")
  result = result.replace(/\.cer\s*PST|PST\s*\.cer|certificato PST/gi, "certificato dell'ufficio")
  result = result.replace(/Catalogo ministeriale|CatalogoServizi\.getCertificato/gi, 'servizio ufficiale')
  result = result.replace(/\bPCT\b/gi, 'deposito telematico')
  result = result.replace(/\bPST\b/gi, 'servizio ufficiale')
  result = result.replace(/token\s+PKCS#?11|PKCS#?11|token/gi, 'dispositivo di firma')
  result = result.replace(/\bhash\b/gi, 'impronta')
  result = result.replace(/\bslot documentali\b|\bslot\b/gi, 'documenti richiesti')
  result = result.replace(/ministeriale|ministeriali/gi, 'ufficiale')
  result = result.replace(/blocco tecnico/gi, 'requisito mancante')
  result = result.replace(/metadato ministeriale/gi, 'dati del deposito')
  result = result.replace(/artefatti ministeriali/gi, 'documenti prodotti')
  result = result.replace(/schema ministeriale|schema/gi, 'controllo')
  result = result.replace(/Deposito\s+deposito telematico/gi, 'Deposito telematico')
  return result
}

function depositUserFacingLabel(value: string): string {
  const registerCodes = '(SICID|SIECIC|SIGP|SIL|SIVG|SIMIN|MIN|RGN|LAV|VG|CASSCI|CASSPE)'
  let result = depositUserFacingMessage(value)
  result = result.replace(new RegExp(`\\s*\\(${registerCodes}\\)`, 'gi'), '')
  result = result.replace(new RegExp(`\\s*/\\s*${registerCodes}\\b`, 'gi'), '')
  result = result.replace(new RegExp(`\\b${registerCodes}\\b`, 'gi'), '')
  result = result.replace(/\s{2,}/g, ' ').replace(/\s+[-/]\s*$/g, '').trim()
  return result || value
}

function DepositRolePicker({
  documentName,
  value,
  onChange,
}: {
  documentName: string
  value: DepositDocumentRole
  onChange: (role: DepositDocumentRole) => void
}) {
  const [open, setOpen] = useState(false)
  const labelId = useId()
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const currentValue = normaliseDepositRoleForUi(value)
  const current = DEPOSIT_DOCUMENT_ROLE_OPTIONS.find((option) => option.value === currentValue) || DEPOSIT_DOCUMENT_ROLE_OPTIONS[2]

  return (
    <div className="iu-fas-deposit-role-picker" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
    }} onKeyDown={(event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setOpen(false)
        buttonRef.current?.focus()
      }
    }}>
      <span id={labelId}>Ruolo</span>
      <div className="iu-fas-deposit-role-picker__box">
        <button
          ref={buttonRef}
          type="button"
          className="iu-fas-deposit-role-picker__button"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-labelledby={labelId}
          aria-label={`Ruolo deposito per ${documentName}`}
          onClick={() => setOpen((currentOpen) => !currentOpen)}
        >
          <strong>{current.label}</strong>
          <ChevronDown size={14} aria-hidden="true" />
        </button>
        {open ? (
          <div className="iu-fas-deposit-role-picker__menu" role="listbox" aria-label={`Seleziona ruolo deposito per ${documentName}`}>
            {DEPOSIT_DOCUMENT_ROLE_OPTIONS.map((option) => {
              const selected = option.value === currentValue
              return (
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={selected ? 'is-selected' : ''}
                  key={`${documentName}-${option.value}`}
                  onClick={() => {
                    onChange(option.value)
                    setOpen(false)
                  }}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function normaliseDepositRoleForUi(role: DepositDocumentRole | undefined): DepositDocumentRole {
  if (role === 'allegato_prova') return 'allegato'
  return role || 'allegato'
}

function DepositTypePreviewPanel({
  catalog,
  selectedKey,
  onSelect,
  currentProfile,
}: {
  catalog: FascicoloDepositCatalog
  selectedKey: string
  onSelect: (key: string) => void
  currentProfile: string
}) {
  const catalogPreview = useMemo(() => buildDepositCatalogPreviewState(catalog), [catalog])
  const [macroId, setMacroId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [schemaOpen, setSchemaOpen] = useState(true)
  const [treeOpen, setTreeOpen] = useState(false)
  const macroareas = catalogPreview.macroareas

  const selectedByKey = useMemo(() => {
    for (const macro of macroareas) {
      for (const category of macro.categories) {
        const type = category.options.find((option) => option.key === selectedKey)
        if (type) return { macro, category, type }
      }
    }
    return null
  }, [macroareas, selectedKey])

  const selectedMacro = selectedByKey?.macro || macroareas.find((macro) => macro.id === macroId) || macroareas[0]
  const selectedCategory = selectedByKey?.category || selectedMacro?.categories.find((category) => category.id === categoryId) || selectedMacro?.categories[0]
  const selectedType = selectedByKey?.type || selectedCategory?.options[0]

  useEffect(() => {
    if (!selectedMacro || !selectedCategory || !selectedType) return
    if (macroId !== selectedMacro.id) setMacroId(selectedMacro.id)
    if (categoryId !== selectedCategory.id) setCategoryId(selectedCategory.id)
    if (selectedKey !== selectedType.key) onSelect(selectedType.key)
  }, [categoryId, macroId, onSelect, selectedCategory, selectedKey, selectedMacro, selectedType])

  const selectMacro = (nextMacroId: string) => {
    const nextMacro = macroareas.find((macro) => macro.id === nextMacroId) || macroareas[0]
    const nextCategory = nextMacro?.categories[0]
    const nextType = nextCategory?.options[0]
    if (!nextMacro || !nextCategory || !nextType) return
    setMacroId(nextMacro.id)
    setCategoryId(nextCategory.id)
    onSelect(nextType.key)
  }

  const selectCategory = (nextCategoryId: string) => {
    if (!selectedMacro) return
    const nextCategory = selectedMacro.categories.find((category) => category.id === nextCategoryId) || selectedMacro.categories[0]
    const nextType = nextCategory?.options[0]
    if (!nextCategory || !nextType) return
    setCategoryId(nextCategory.id)
    onSelect(nextType.key)
  }

  if (!selectedMacro || !selectedCategory || !selectedType) {
    return (
      <section className="iu-fas-deposit-type-panel" aria-label="Tipo deposito telematico">
        <header>
          <div>
            <strong>Tipo deposito</strong>
            <span>Elenco depositi non disponibile.</span>
          </div>
          <Badge tone="warning">Da caricare</Badge>
        </header>
      </section>
    )
  }

  const sendReady = selectedType.rules.real_send_allowed_from_pct_panel
  const userControls = uniqueDepositUserList(selectedType.ui.controls)
  const transportLabel = depositUserTransportLabel(selectedType)

  return (
    <section className="iu-fas-deposit-type-panel" aria-label="Tipo deposito telematico">
      <header>
        <div>
          <strong>Tipo deposito</strong>
          <span>{catalogPreview.total} tipi disponibili in {macroareas.length} aree. La scelta governa controlli, documenti richiesti e preparazione della busta.</span>
        </div>
        <Badge tone={sendReady ? 'success' : 'warning'}>{sendReady ? 'Operativo' : 'Da completare'}</Badge>
      </header>
      <div className="iu-fas-deposit-type-panel__controls">
        <label>
          <span>Macroarea</span>
          <select value={selectedMacro.id} onChange={(event) => selectMacro(event.currentTarget.value)}>
            {macroareas.map((macro) => (
              <option value={macro.id} key={macro.id}>{depositUserFacingLabel(macro.label)} ({macro.total})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Categoria</span>
          <select value={selectedCategory.id} onChange={(event) => selectCategory(event.currentTarget.value)}>
            {selectedMacro.categories.map((category) => (
              <option value={category.id} key={category.id}>{depositUserFacingLabel(category.label)} ({category.total})</option>
            ))}
          </select>
        </label>
        <label>
          <span>Deposito</span>
          <select value={selectedType.key} onChange={(event) => onSelect(event.currentTarget.value)}>
            {selectedCategory.options.map((option) => (
              <option value={option.key} key={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="iu-fas-deposit-type-panel__summary">
        <article>
          <span>Area</span>
          <strong>{depositUserFacingLabel(selectedMacro.label)}</strong>
          <small>{depositUserFacingLabel(selectedCategory.label)}</small>
        </article>
        <article>
          <span>Preparazione</span>
          <strong>{sendReady ? 'Pronta per i controlli' : 'Da completare'}</strong>
          <small>{selectedType.label}</small>
        </article>
        <article>
          <span>Invio</span>
          <strong>{transportLabel}</strong>
          <small>{sendReady ? 'Controllabile nel flusso deposito' : 'Richiede flusso dedicato'}</small>
        </article>
      </div>
      <div className="iu-fas-deposit-type-panel__behavior">
        <ShieldCheck size={16} aria-hidden="true" />
        <div>
          <strong>Comportamento previsto</strong>
          <span>{depositUserFacingMessage(selectedType.ui.behavior)}</span>
        </div>
      </div>
      {!sendReady && selectedType.rules.real_send_blocker ? (
        <div className="iu-fas-deposit-type-panel__blocker" role="status">
          <ShieldAlert size={16} aria-hidden="true" />
          <span>{depositUserFacingMessage(selectedType.rules.real_send_blocker)}</span>
        </div>
      ) : null}
      <div className="iu-fas-deposit-type-panel__actions">
        <button type="button" onClick={() => setSchemaOpen((open) => !open)} aria-expanded={schemaOpen}>
          {schemaOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />} Dettagli
        </button>
        <button type="button" onClick={() => setTreeOpen((open) => !open)} aria-expanded={treeOpen}>
          {treeOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />} {treeOpen ? 'Compatta' : 'Esplodi tutto'}
        </button>
      </div>
      {schemaOpen ? (
        <div className="iu-fas-deposit-type-panel__schema">
          <section>
            <strong>Scelta attuale</strong>
            <ul>
              <li>Area: {depositUserFacingLabel(selectedMacro.label)}</li>
              <li>Categoria: {depositUserFacingLabel(selectedCategory.label)}</li>
              <li>Tipo: {selectedType.label}</li>
              <li>{sendReady ? 'Controlli disponibili in questo flusso' : 'Serve un percorso dedicato prima dell’invio'}</li>
            </ul>
          </section>
          <section>
            <strong>Controlli automatici</strong>
            <ul>
              {userControls.map((item) => <li key={`${selectedType.key}-control-${item}`}>{item}</li>)}
            </ul>
          </section>
          <section>
            <strong>Documenti attesi</strong>
            <ul>
              {selectedType.ui.documents.map((item, index) => <li key={`${selectedType.key}-document-${item}-${index}`}>{depositUserFacingMessage(depositAttachmentDisplayName(item) || item)}</li>)}
            </ul>
          </section>
        </div>
      ) : null}
      {treeOpen ? (
        <div className="iu-fas-deposit-type-panel__tree" aria-label="Elenco tipi deposito">
          {macroareas.map((macro) => (
            <section key={`macro-${macro.id}`}>
              <h4>{depositUserFacingLabel(macro.label)} <span>{macro.total}</span></h4>
              {macro.categories.map((category) => (
                <div key={`category-${category.id}`}>
                  <strong>{depositUserFacingLabel(category.label)} <span>{category.total}</span></strong>
                  <ul>
                    {category.options.map((option) => (
                      <li key={`tree-${option.key}`} className={option.key === selectedType.key ? 'is-selected' : ''}>
                        <button
                          type="button"
                          onClick={() => {
                            setMacroId(macro.id)
                            setCategoryId(category.id)
                            onSelect(option.key)
                          }}
                        >
                          {option.label}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          ))}
        </div>
      ) : null}
      <p className="iu-fas-deposit-type-panel__current">
        <Gavel size={14} aria-hidden="true" />
        <span>{depositUserFacingLabel(currentProfile) || 'Profilo pratica da confermare'}</span>
      </p>
    </section>
  )
}

const DEPOSIT_PHASE_IDS = [
  'verifica-deposito',
  'proposta-busta',
  'firma-busta',
  'generazione-busta',
  'inventario-fascicolo',
] as const

type DepositPhaseId = typeof DEPOSIT_PHASE_IDS[number]
const DEPOSIT_DETAIL_INCLUDE = ['documenti', 'depositi', 'regia', 'relata', 'audit'] as const

function isDepositPhaseId(value: string): value is DepositPhaseId {
  return DEPOSIT_PHASE_IDS.includes(value as DepositPhaseId)
}

function initialDepositPhaseFromHash(): DepositPhaseId {
  if (typeof window === 'undefined') return 'verifica-deposito'
  const value = decodeURIComponent(window.location.hash.replace(/^#/, ''))
  return isDepositPhaseId(value) ? value : 'verifica-deposito'
}

async function submitJsonPayload(endpoint: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  const token = csrfToken()
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
      ...(token ? { 'X-CSRFToken': token } : {}),
    },
    body: JSON.stringify(payload),
  })
  const data = await response.json().catch(() => ({})) as Record<string, unknown>
  if (!response.ok || data.ok === false) {
    throw new Error(String(data.message || data.errore || data.error || 'Non ho potuto salvare la classificazione deposito.'))
  }
  return data
}

function DepositActionButton({
  action,
  payload,
  children,
  tone = 'primary',
  disabled,
  confirm,
  confirmTitle = 'Conferma deposito',
  disabledReason,
  beforeSubmit,
  onDone,
  onError,
  onPackageReady,
  completeLocalSignature,
  completeLocalPec,
  progressItems = [],
  progressLabel = 'Preparazione deposito in corso',
}: {
  action: string
  payload: DepositActionPayload
  children: ReactNode
  tone?: 'primary' | 'secondary'
  disabled?: boolean
  confirm?: string
  confirmTitle?: string
  disabledReason?: string
  beforeSubmit?: () => Promise<void>
  onDone?: (message?: string) => void
  onError?: (message: string) => void
  onPackageReady?: (payload: ActionPayload) => void
  completeLocalSignature?: (payload: ActionPayload, submittedPayload: DepositActionPayload) => Promise<LocalSignatureCompletion>
  completeLocalPec?: (payload: ActionPayload, submittedPayload: DepositActionPayload) => Promise<string | void>
  progressItems?: string[]
  progressLabel?: string
}) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [progressIndex, setProgressIndex] = useState(0)
  const progressQueue = progressItems.length ? progressItems : DEPOSIT_PROGRESS_USER_STEPS
  const currentProgressItem = depositUserFacingMessage(progressQueue[progressIndex % progressQueue.length] || 'Pacchetto deposito')
  useEffect(() => {
    if (!busy) {
      setProgressIndex(0)
      return undefined
    }
    const timer = window.setInterval(() => {
      setProgressIndex((current) => (current + 1) % progressQueue.length)
    }, 1100)
    return () => window.clearInterval(timer)
  }, [busy, progressQueue.length])
  if (!action) return null
  const handleJsonResult = async (result: ActionPayload, submittedPayload: DepositActionPayload, responseOk = true) => {
    if (result.requires_local_signature && completeLocalSignature) {
      setConfirming(false)
      const completion = await completeLocalSignature(result, submittedPayload)
      return handleJsonResult(completion.payload, completion.submittedPayload, true)
    }
    if (result.requires_local_pec && completeLocalPec) {
      setConfirming(false)
      const message = await completeLocalPec(result, submittedPayload)
      onDone?.(message || String(result.messaggio || result.message || 'Invio PEC locale confermato.'))
      return undefined
    }
    if (result.package_ready || result.requires_guided_completion || result.requires_local_pec) {
      setConfirming(false)
      onPackageReady?.(result)
      if (!onPackageReady) onDone?.(String(result.messaggio || result.message || 'Pacchetto deposito preparato.'))
      return undefined
    }
    if (!responseOk || result.ok === false) {
      const nextActions = Array.isArray(result.next_actions)
        ? result.next_actions.map((item) => String(item || '').trim()).filter(Boolean)
        : []
      const baseMessage = String(result.message || result.messaggio || result.errore || result.error || 'Deposito non completato.')
      throw new Error(nextActions.length ? `${baseMessage} Prossimi passi: ${nextActions.join(' ')}` : baseMessage)
    }
    setConfirming(false)
    onDone?.(String(result.messaggio || result.message || 'Operazione deposito completata.'))
    return undefined
  }
  const run = async () => {
    setBusy(true)
    setError('')
    try {
      if (beforeSubmit) await beforeSubmit()
      const form = new FormData()
      Object.entries(payload).forEach(([key, value]) => {
        if (Array.isArray(value)) value.forEach((item: string) => form.append(key, item))
        else form.append(key, value)
      })
      const response = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json, application/octet-stream', 'X-Requested-With': 'XMLHttpRequest' },
        body: form,
      })
      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const result = (await response.json().catch(() => ({}))) as ActionPayload
        await handleJsonResult(result, payload, response.ok)
        return
      }
      if (!response.ok) throw new Error(`Operazione non riuscita: HTTP ${response.status}`)
      const blob = await response.blob()
      const header = response.headers.get('content-disposition') || ''
      const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header)
      const filename = decodeURIComponent((match?.[1] || 'busta-deposito.enc').replace(/"/g, ''))
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      setConfirming(false)
      onDone?.('Busta generata e scaricata.')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Deposito non completato.'
      const signatureMessage = signatureInputRequiredMessage(message)
      const visibleMessage = depositUserFacingMessage(signatureMessage || message)
      if (signatureMessage) {
        setConfirming(false)
        setError(visibleMessage)
      } else {
        setError(visibleMessage)
        onError?.(visibleMessage)
      }
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <button
        className={`iu-fas-post iu-fas-post--${tone}`}
        type="button"
        onClick={() => confirm ? setConfirming(true) : void run()}
        disabled={busy || disabled}
        title={disabled && disabledReason ? depositUserFacingMessage(disabledReason) : undefined}
        aria-disabled={disabled ? true : undefined}
      >
        {children}
      </button>
      {busy ? (
        <div className="iu-fas-package-progress" role="status" aria-live="polite">
          <div className="iu-fas-package-progress__head">
            <span>{progressLabel}</span>
            <strong title={currentProgressItem}>{currentProgressItem}</strong>
          </div>
          <div className="iu-fas-package-progress__bar" aria-hidden="true"><span/></div>
          <div className="iu-fas-package-progress__ticker" aria-hidden="true">
            <span>{progressQueue.map(depositUserFacingMessage).join(' - ')}</span>
          </div>
        </div>
      ) : null}
      {confirming ? (
        <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label={confirmTitle}>
          <div className="iu-fas-confirm-modal__box">
            <strong>{confirmTitle}</strong>
            <p>{confirm}</p>
            {error ? <span className="iu-fas-inline-error">{depositUserFacingMessage(error)}</span> : null}
            <footer>
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}>Annulla</button>
              <button className="is-danger" type="button" onClick={run} disabled={busy || disabled}>{busy ? 'Operazione...' : 'Conferma'}</button>
            </footer>
          </div>
        </div>
      ) : null}
    </>
  )
}

function DepositPdfPreviewButton({
  action,
  payload,
  onPreview,
  onError,
  disabled = false,
  disabledReason = '',
}: {
  action: string
  payload: DepositActionPayload
  onPreview: (preview: PreviewDocument) => void
  onError?: (message: string) => void
  disabled?: boolean
  disabledReason?: string
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const openPreview = async () => {
    if (!action || busy || disabled) return
    setBusy(true)
    setError('')
    try {
      const params = new URLSearchParams()
      Object.entries(payload).forEach(([key, value]) => {
        if (Array.isArray(value)) value.forEach((item) => params.append(key, item))
        else params.append(key, value)
      })
      const previewUrl = `${action}?${params.toString()}`
      const response = await fetch(previewUrl, {
        method: 'GET',
        credentials: 'same-origin',
        headers: { Accept: 'application/pdf', 'X-Requested-With': 'XMLHttpRequest' },
      })
      if (!response.ok) {
        const contentType = response.headers.get('content-type') || ''
        const jsonBody = contentType.includes('application/json') ? await response.json().catch(() => null) : null
        const textBody = jsonBody ? '' : await response.text().catch(() => '')
        const message = String(jsonBody?.errore || jsonBody?.message || textBody || '').trim()
        throw new Error(message || `Indice non disponibile: HTTP ${response.status}`)
      }
      onPreview({
        name: 'IndiceDocumentiDepositati.PDF',
        url: previewUrl,
        downloadUrl: previewUrl,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Indice documenti non disponibile.'
      setError(message)
      onError?.(message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <span className="iu-fas-package-preview-button">
      <button
        type="button"
        onClick={openPreview}
        disabled={busy || disabled}
        title={disabled ? disabledReason || 'Indice non ancora disponibile' : 'Visualizza indice documenti'}
        aria-label="Visualizza IndiceDocumentiDepositati.PDF"
      >
        {busy ? <RefreshCw size={16} aria-hidden="true"/> : <Eye size={16} aria-hidden="true"/>}
      </button>
      {error ? <small role="alert">{error}</small> : disabled && disabledReason ? <small>{disabledReason}</small> : null}
    </span>
  )
}

function JsonPostForm({
  action,
  className,
  children,
  redirectTo,
  encType,
  onDone,
  onError,
}: {
  action: string
  className?: string
  children: ReactNode
  redirectTo?: string
  encType?: string
  onDone?: (message?: string) => void
  onError?: (message: string) => void
}) {
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  if (!action) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setMessage('Salvataggio in corso...')
    try {
      const result = await submitFormJson(action, new FormData(event.currentTarget))
      const nextMessage = result.message || 'Operazione completata.'
      setMessage(nextMessage)
      if (onDone) {
        onDone(nextMessage)
      } else {
        redirectAfterSuccess(result, redirectTo || window.location.href)
      }
    } catch (error) {
      const nextMessage = error instanceof Error ? error.message : 'Operazione non riuscita.'
      setMessage(nextMessage)
      onError?.(nextMessage)
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className={className} onSubmit={submit} encType={encType} data-busy={busy ? 'true' : undefined}>
      {children}
      {message ? <span className="iu-fas-inline-error" role="status">{message}</span> : null}
    </form>
  )
}

function CollapsibleFormPanel({
  title,
  subtitle,
  icon,
  children,
  defaultOpen = true,
  className = '',
}: {
  title: string
  subtitle?: string
  icon?: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  className?: string
}) {
  return (
    <details className={`iu-fas-form-panel ${className}`.trim()} {...(defaultOpen ? { open: true } : {})}>
      <summary className="iu-fas-form-panel__summary">
        <span className="iu-fas-form-panel__icon">{icon}</span>
        <span className="iu-fas-form-panel__copy">
          <strong>{title}</strong>
          {subtitle ? <small>{subtitle}</small> : null}
        </span>
        <ChevronDown className="iu-fas-form-panel__chevron" size={17}/>
      </summary>
      <div className="iu-fas-form-panel__body">{children}</div>
    </details>
  )
}

function LexIndexingPanel({ summary, refreshAction, retryAction, onDone, onError }:{summary:LexIndexingSummary; refreshAction:string; retryAction:string; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const working = summary.queued + summary.indexing
  const warnings = summary.warnings.slice(0, 4)
  const rawStatus = String(summary.status || '').toLowerCase()
  const effectiveStatus: LexIndexingSummary['status'] = rawStatus === 'ready'
    ? 'ready'
    : rawStatus === 'error'
      ? 'error'
      : rawStatus === 'stale' || rawStatus === 'not_indexed'
        ? (summary.ready > 0 ? 'partial' : 'stale')
        : rawStatus === 'working'
          ? 'working'
          : 'partial'
  const tone = effectiveStatus === 'ready' ? 'success' : effectiveStatus === 'error' ? 'danger' : effectiveStatus === 'stale' ? 'warning' : 'info'
  const statusLabel: Record<LexIndexingSummary['status'], string> = { ready: 'Pronto', partial: 'Parziale', working: 'In corso', error: 'Errore', stale: 'Da aggiornare' }
  const message = summary.errors > 0
    ? 'Alcuni documenti non sono stati indicizzati. Qui sotto trovi quali file richiedono attenzione.'
    : working > 0
      ? 'Alcuni documenti sono in indicizzazione. Lex li userà appena pronti.'
      : summary.stale > 0
        ? 'Alcuni documenti sono cambiati: aggiorna l’indice prima di usarli con Lex.'
        : 'Lex può leggere i documenti del fascicolo.'
  return (
    <section className="iu-fas-lex-indexing" aria-label="Indicizzazione Lex">
      <header>
        <div>
          <span><BrainCircuit size={16}/> Indicizzazione Lex</span>
          <strong>{message}</strong>
        </div>
        <Badge tone={tone}>{statusLabel[effectiveStatus]}</Badge>
      </header>
      <dl>
        <div><dt>Totali</dt><dd>{summary.total_documents}</dd></div>
        <div><dt>Pronti</dt><dd>{summary.ready}</dd></div>
        <div><dt>In coda</dt><dd>{summary.queued}</dd></div>
        <div><dt>In corso</dt><dd>{summary.indexing}</dd></div>
        <div><dt>Errori</dt><dd>{summary.errors}</dd></div>
        <div><dt>Da aggiornare</dt><dd>{summary.stale}</dd></div>
      </dl>
      {warnings.length ? (
        <div className="iu-fas-lex-indexing__warnings" aria-label="Documenti da verificare per Lex">
          <strong>Documenti da verificare</strong>
          <ul>
            {warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      ) : null}
      <footer>
        <span>Ultimo indice: {summary.last_indexed_at ? formatDateTimeIt(summary.last_indexed_at, 'mai') : 'mai'}</span>
        <div>
          {refreshAction ? <PostAction action={refreshAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={15}/> Aggiorna indice</PostAction> : null}
          {retryAction && summary.errors > 0 ? <PostAction action={retryAction} tone="secondary" onDone={onDone} onError={onError}><RotateCcw size={15}/> Riprova errori</PostAction> : null}
        </div>
      </footer>
    </section>
  )
}

function RowActions({ item, archive = false, onDeleted, onError, className = '' }:{item:FascicoloRow; archive?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; className?:string}) {
  const deleteHref = item.deleteHref || `/fascicoli/${encodeURIComponent(item.id)}/elimina`
  return (
    <div className={`iu-fas-actions ${className}`.trim()} aria-label={`Azioni fascicolo ${item.ref}`}>
      <a href={item.href} aria-label="Apri fascicolo" title="Apri"><Eye size={15}/></a>
      {item.relataStatusLabel ? <a href={relataListHref(item)} aria-label={`Apri Relata notifica ${item.ref}`} title="Relata notifica"><FileSignature size={15}/></a> : null}
      {!archive ? <a href={item.editHref} aria-label="Modifica fascicolo" title="Modifica"><PencilLine size={15}/></a> : null}
      <a href={item.exportPdfHref} aria-label="Esporta PDF fascicolo" title="PDF"><FileDown size={15}/></a>
      {archive && item.archive?.zipAvailable ? <a href={item.archiveZipHref} aria-label="Scarica ZIP archivio" title="ZIP"><FileArchive size={15}/></a> : null}
      <PostAction action={deleteHref} tone="danger" confirm={`Eliminare definitivamente il fascicolo ${item.ref}?`} confirmTitle="Elimina fascicolo" onDone={(message) => onDeleted?.(item.id, message)} onError={onError} title="Elimina fascicolo" ariaLabel={`Elimina fascicolo ${item.ref}`}><Trash2 size={15}/></PostAction>
    </div>
  )
}

function StatusEditCell({ item, onSaved, onError }:{item:FascicoloRow; onSaved:(id:string, status:FascicoloRow['status'], tone:FascicoloRow['tone'], message?:string)=>void; onError:(message:string)=>void}) {
  const [saving, setSaving] = useState(false)
  // "da_archiviare" è uno stato derivato: nel select lo mostriamo come "Definito"
  // perché è il valore di dominio sottostante.
  const selectValue = item.status === 'da_archiviare' ? 'definito' : item.status
  const handleChange = async (next: Exclude<FascicoloStato, 'tutti'>) => {
    if (next === selectValue || saving) return
    setSaving(true)
    try {
      const result = await updateFascicoloStatus(item.id, next)
      onSaved(item.id, result.status as FascicoloRow['status'], result.tone as FascicoloRow['tone'], result.message)
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Cambio stato non riuscito.')
    } finally {
      setSaving(false)
    }
  }
  return (
    <select
      className={`iu-fas-status-select iu-fas-status-select--${item.tone}`}
      value={selectValue}
      disabled={saving}
      onChange={(event) => { void handleChange(event.target.value as Exclude<FascicoloStato, 'tutti'>) }}
      aria-label={`Stato fascicolo ${item.ref}`}
      title="Cambia stato del fascicolo"
    >
      {fascicoloStatusEditOptions.map((option) => (
        <option value={option.value} key={option.value}>{option.label}</option>
      ))}
    </select>
  )
}

function paymentAmountDraft(item: FascicoloPaymentItem): string {
  return item.importo === null || item.importo === undefined ? '' : String(item.importo).replace('.', ',')
}

function compactPaymentLabel(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '')
}

function visibleDocumentSource(value?: string): string {
  const source = (value || '').trim().replace(/\s+/g, ' ')
  if (!source) return ''
  const normalised = source.toLowerCase()
  if (normalised.startsWith('sentenza_key:') || (normalised.includes('|') && normalised.includes('sentenza'))) {
    const dateMatch = source.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/)
    if (dateMatch) return `Sentenza del ${dateMatch[3]}/${dateMatch[2]}/${dateMatch[1]}`
    return 'Sentenza indicizzata nel fascicolo'
  }
  const fileName = source.split(/[\\/]/).pop() || source
  const fileStem = fileName.replace(/\.[a-z0-9]{2,5}$/i, '').toLowerCase()
  if (/^\d{10,}$/.test(normalised) || /^\d{10,}$/.test(fileStem)) {
    return 'Documento indicizzato del fascicolo'
  }
  if (normalised.includes('autocertificazione') && (normalised.includes(' esenzione ') || normalised.includes(' cu ') || normalised.includes('contributo'))) {
    return 'Autocertificazione esenzione contributo unificato'
  }
  if (normalised.includes('esenzione') && (normalised.includes(' cu ') || normalised.includes('contributo unificato'))) {
    return 'Documento di esenzione contributo unificato'
  }
  if (normalised.includes('pagopa') || normalised.includes('pago pa')) {
    return 'Ricevuta pagoPA'
  }
  if (normalised.includes('ricevuta telematica') && normalised.includes('pagamento')) {
    return 'Ricevuta telematica pagoPA'
  }
  if (normalised.includes('sentenza')) {
    return 'Sentenza del fascicolo'
  }
  if (
    normalised.startsWith('document_id:')
    || normalised.startsWith('documento_id:')
    || normalised.startsWith('pst:')
    || /^docai[-_]/.test(normalised)
    || /^doc[-_][a-z0-9]/.test(normalised)
  ) {
    return 'Documento indicizzato del fascicolo'
  }
  if (normalised.includes('document ai') && normalised.includes('sentenza')) {
    return 'Sentenza letta automaticamente'
  }
  if (normalised.includes('document ai')) {
    return 'Documento letto automaticamente'
  }
  const readable = fileName
    .replace(/\.[a-z0-9]{2,5}$/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\bcu\b/gi, 'contributo unificato')
    .replace(/\s+/g, ' ')
    .trim()
  if (!readable) return 'Documento del fascicolo'
  return readable.length > 72 ? `${readable.slice(0, 69)}...` : readable
}

function economicEvidenceLabel(kind: FascicoloPaymentKind, payment: FascicoloPaymentItem): string {
  const amount = payment.importoLabel
  if (kind === 'contributo_unificato') {
    if (payment.status === 'non_previsto') return 'Contributo non dovuto o esente'
    if (payment.status === 'pagato') return amount ? `Contributo pagato: ${amount}` : 'Contributo pagato'
    if (payment.status === 'parziale') return amount ? `Contributo parziale: ${amount}` : 'Contributo parziale'
    return amount ? `Contributo da registrare: ${amount}` : 'Contributo da verificare'
  }
  if (kind === 'liquidazione_giudice') {
    if (payment.status === 'pagato') return amount ? `Liquidazione trovata: ${amount}` : 'Liquidazione trovata'
    return amount ? `Liquidazione da controllare: ${amount}` : 'Liquidazione da controllare'
  }
  if (kind === 'parcella') {
    if (payment.status === 'da_emettere') return amount ? `Parcella da emettere: ${amount}` : 'Parcella da emettere'
    if (payment.status === 'pagato') return amount ? `Parcella pagata: ${amount}` : 'Parcella pagata'
    return amount ? `Parcella proposta: ${amount}` : 'Parcella da verificare'
  }
  if (kind === 'spese_esborsi') {
    if (payment.status === 'non_previsto') return 'Spese non risultano dai documenti'
    return amount ? `Spese/esborsi trovati: ${amount}` : 'Spese/esborsi da verificare'
  }
  return amount ? `${payment.statusLabel}: ${amount}` : payment.statusLabel
}

function economicAnalysisLabel(analysis: FascicoloPaymentSummary['analysis']): string {
  if (analysis.status === 'da_rianalizzare') return 'Nuovi documenti'
  if (analysis.status === 'da_analizzare') return 'Da controllare'
  if (analysis.status === 'aggiornato_con_rilievi') return 'Documenti controllati'
  if (analysis.status === 'aggiornato_provvisorio') return 'Documenti letti'
  return analysis.statusLabel || 'Controllo documenti'
}

function economicAnalysisMessage(analysis: FascicoloPaymentSummary['analysis']): string {
  if (analysis.status === 'da_rianalizzare') {
    return 'Sono entrati nuovi documenti: aggiorna il controllo prima di usare questi importi.'
  }
  if (analysis.status === 'da_analizzare') {
    return 'Avvia il controllo del fascicolo per contributo, sentenze, spese e parcella.'
  }
  if (analysis.status === 'aggiornato_provvisorio') {
    return 'Il sistema ha letto i documenti disponibili e segnala solo le informazioni utili.'
  }
  if (analysis.status === 'aggiornato_con_rilievi') {
    return analysis.reason || 'Presidio eseguito: alcuni dati non risultano dai documenti del fascicolo o dai documenti indicizzati in archivio centrale.'
  }
  if (analysis.relatedDuplicateFascicoli) {
    const suffix = analysis.relatedDuplicateFascicoli === 1 ? 'pratica collegata' : 'pratiche collegate'
    return `${analysis.relatedDuplicateFascicoli} ${suffix} da riconciliare.`
  }
  return ''
}

function EconomicPaymentSummary({ payment, kind }:{payment:FascicoloPaymentItem; kind:FascicoloPaymentKind}) {
  const label = paymentColumnLabels[kind] || payment.displayLabel || payment.label
  const amount = payment.importoLabel || (payment.status === 'non_previsto' ? 'n.d.' : payment.status === 'da_emettere' ? 'Da calcolare' : 'Da verificare')
  const detail = payment.dataPagamento || visibleDocumentSource(payment.documentoFonte) || payment.updatedAtLabel || payment.metodo || payment.note || ''
  const title = [label, amount, payment.statusLabel, detail].filter(Boolean).join(' - ')
  return (
    <div className={`iu-fas-economic-summary iu-fas-economic-summary--${payment.tone}`} title={title} aria-label={title}>
      <div>
        <span>{label}</span>
        <strong>{amount}</strong>
      </div>
      <Badge tone={payment.tone}>{payment.statusLabel}</Badge>
      {detail ? <small>{detail}</small> : null}
    </div>
  )
}

function DuplicatePracticeBadge({ item }:{item:FascicoloRow}) {
  if (!item.duplicateCount || item.duplicateCount < 2) return null
  const href = item.duplicateHref || `/fascicoli?rg=${encodeURIComponent(item.rg)}`
  const label = item.duplicateLabel || `${item.client} - ${item.rg}`
  return (
    <a className="iu-fas-duplicate-badge" href={href} title={`Verificare possibili doppioni: ${label}`}>
      <Copy size={13}/>
      <span>{item.duplicateCount} pratiche stesso cliente/RG</span>
    </a>
  )
}

function MissingRgBadge({ item, compact = false }:{item:FascicoloRow; compact?:boolean}) {
  if (!item.rgMissing) return null
  const label = item.rgStatusLabel || 'Acquisire il numero di ruolo dal portale o da un provvedimento del fascicolo.'
  const source = item.rgSourceLabel || 'Dato processuale da completare'
  return (
    <a className="iu-fas-rg-missing-badge" href={item.editHref} title={label}>
      <Landmark size={13}/>
      <span>RG da acquisire</span>
      {compact ? null : <strong>{source}</strong>}
    </a>
  )
}

function EconomicEvidenceStrip({ row }:{row:FascicoloRow}) {
  const analysis = row.paymentSummary.analysis
  const proforma = row.paymentSummary.proformaPresidio
  const evidences = economicPaymentKinds
    .map((kind) => {
      const payment = row.paymentSummary.items[kind]
      if (!payment.documentoFonte && !payment.origine) return null
      const source = visibleDocumentSource(payment.documentoFonte || payment.origine)
      if (!source) return null
      return { kind, label: economicEvidenceLabel(kind, payment), source, tone: payment.tone }
    })
    .filter(Boolean) as Array<{ kind:FascicoloPaymentKind; label:string; source:string; tone:FascicoloRow['tone'] }>
  const analysisVisible = Boolean(
    analysis.status
    && analysis.status !== 'aggiornato'
    && !(analysis.status === 'aggiornato_provvisorio' && evidences.length)
  )
  const proformaVisible = Boolean(proforma.message && proforma.status !== 'non_applicabile')
  const analysisMessage = economicAnalysisMessage(analysis)
  if (!evidences.length && !analysisVisible && !proformaVisible) return null
  return (
    <div className="iu-fas-economic-evidence" aria-label={`Fonti economiche lette dai documenti per ${row.ref}`}>
      <span><FileCheck2 size={14}/> Controllo documenti</span>
      {proformaVisible ? (
        <small className="iu-fas-economic-evidence__proforma">
          <Badge tone={proforma.tone}>{proforma.statusLabel}</Badge>
          <a className="iu-fas-economic-evidence__source" href={proforma.href}>{proforma.message}</a>
        </small>
      ) : null}
      {analysisVisible ? (
        <small>
          <Badge tone={analysis.tone}>{economicAnalysisLabel(analysis)}</Badge>
          {analysisMessage ? <span className="iu-fas-economic-evidence__source">{analysisMessage}</span> : null}
        </small>
      ) : null}
      {evidences.slice(0, 4).map((item) => (
        <small key={item.kind}>
          <Badge tone={item.tone}>{item.label}</Badge>
          <span className="iu-fas-economic-evidence__source">{item.source}</span>
        </small>
      ))}
    </div>
  )
}

function EconomicPaymentCell({ row, kind, onSaved, onError, onDraftChange, forceLabel = false }:{row:FascicoloRow; kind:FascicoloPaymentKind; onSaved:(id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string)=>void; onError:(message:string)=>void; onDraftChange?:(kind:FascicoloPaymentKind, draft:FascicoloPaymentUpdatePayload | null)=>void; forceLabel?:boolean}) {
  const payment = row.paymentSummary.items[kind]
  const paymentLabel = payment.displayLabel || payment.label || paymentFullLabels[kind]
  const paymentNatureLabel = payment.natura ? payment.natura.replace(/_/g, ' ') : ''
  const showPaymentNature = Boolean(paymentNatureLabel && compactPaymentLabel(paymentNatureLabel) !== compactPaymentLabel(paymentLabel))
  const showSpecificLabel = Boolean(showPaymentNature || paymentLabel !== paymentFullLabels[kind])
  const [status, setStatus] = useState<FascicoloPaymentStatus>(payment.status)
  const [amount, setAmount] = useState(paymentAmountDraft(payment))
  const [date, setDate] = useState(payment.dataPagamentoIso || '')
  const [method, setMethod] = useState(payment.metodo || '')
  const [note, setNote] = useState(payment.note || '')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setStatus(payment.status)
    setAmount(paymentAmountDraft(payment))
    setDate(payment.dataPagamentoIso || '')
    setMethod(payment.metodo || '')
    setNote(payment.note || '')
  }, [payment.dataPagamentoIso, payment.importo, payment.metodo, payment.note, payment.status])

  const availableStatuses = kind === 'parcella'
    ? paymentStatusOptions
    : paymentStatusOptions.filter((option) => option.value !== 'da_emettere')
  const dirty = status !== payment.status
    || amount.trim() !== paymentAmountDraft(payment)
    || date !== (payment.dataPagamentoIso || '')
    || method.trim() !== (payment.metodo || '')
    || note.trim() !== (payment.note || '')

  useEffect(() => {
    onDraftChange?.(kind, dirty ? {
      status,
      importo: amount.trim() === '' ? null : amount.trim(),
      dataPagamento: date,
      metodo: method.trim(),
      note: note.trim(),
    } : null)
  }, [amount, date, dirty, kind, method, note, onDraftChange, status])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    try {
      const result = await updateFascicoloPayment(row.id, kind, {
        status,
        importo: amount.trim() === '' ? null : amount.trim(),
        dataPagamento: date,
        metodo: method.trim(),
        note: note.trim(),
      })
      onDraftChange?.(kind, null)
      onSaved(row.id, result.paymentSummary, result.message)
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Aggiornamento economico non riuscito.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={`iu-fas-economic-cell iu-fas-economic-cell--${payment.tone}`} onSubmit={(event) => { void submit(event) }}>
      {forceLabel || showSpecificLabel ? (
        <div className="iu-fas-economic-cell__kind">
          <Badge tone={payment.tone}>{paymentLabel}</Badge>
          {showPaymentNature ? <small>{paymentNatureLabel}</small> : null}
        </div>
      ) : null}
      <label>
        <span>Stato</span>
        <select value={status} onChange={(event) => setStatus(event.target.value as FascicoloPaymentStatus)} aria-label={`${paymentLabel} - stato`}>
          {availableStatuses.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
        </select>
      </label>
      <label>
        <span>Importo</span>
        <input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" placeholder="vuoto" aria-label={`${paymentLabel} - importo`}/>
      </label>
      <label>
        <span>Data</span>
        <input value={date} onChange={(event) => setDate(event.target.value)} type="date" aria-label={`${paymentLabel} - data`}/>
      </label>
      <button type="submit" disabled={saving || !dirty} title="Salva aggiornamento economico" aria-label={`Salva ${paymentLabel} per ${row.ref}`}>
        {saving ? <RefreshCw size={14}/> : <Save size={14}/>}
      </button>
      <details className="iu-fas-economic-cell__details">
        <summary>
          <span>Dettagli</span>
          <small>{payment.metodo || payment.note || payment.updatedAtLabel || 'Metodo e note'}</small>
        </summary>
        <div>
          <label>
            <span>Metodo</span>
            <input value={method} onChange={(event) => setMethod(event.target.value)} placeholder="F24, bonifico..." aria-label={`${paymentLabel} - metodo`}/>
          </label>
          <label>
            <span>Note</span>
            <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="nota interna" aria-label={`${paymentLabel} - note`}/>
          </label>
        </div>
      </details>
    </form>
  )
}

type EconomicPaymentDrafts = Partial<Record<FascicoloPaymentKind, FascicoloPaymentUpdatePayload>>

function economicProformaBasis(summary: FascicoloPaymentSummary): FascicoloProformaBasis | undefined {
  for (const sourceKind of ['parcella', 'liquidazione_giudice'] as const) {
    const payment = summary.items[sourceKind]
    if (payment.importo === null || payment.importo <= 0) continue
    return {
      sourceKind,
      status: payment.status,
      importo: payment.importo,
      dataPagamento: payment.dataPagamentoIso,
      metodo: payment.metodo,
      note: payment.note,
    }
  }
  return undefined
}

function EconomicEditorPanel({ row, onSaved, onError }:{row:FascicoloRow; onSaved:(id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string)=>void; onError:(message:string)=>void}) {
  const [drafts, setDrafts] = useState<EconomicPaymentDrafts>({})
  const [generating, setGenerating] = useState(false)
  const [operationMessage, setOperationMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const registerDraft = useCallback((kind: FascicoloPaymentKind, draft: FascicoloPaymentUpdatePayload | null) => {
    setDrafts((current) => {
      const next = { ...current }
      if (draft) next[kind] = draft
      else delete next[kind]
      return next
    })
  }, [])
  useEffect(() => {
    setDrafts({})
    setOperationMessage(null)
  }, [row.id])

  const dirtyCount = Object.keys(drafts).length
  const hasProforma = row.paymentSummary.proformaPresidio.status === 'presente'
  const generate = async () => {
    setGenerating(true)
    setOperationMessage(null)
    try {
      let latestSummary: FascicoloRow['paymentSummary'] | null = null
      for (const kind of economicPaymentKinds) {
        const draft = drafts[kind]
        if (!draft) continue
        const saved = await updateFascicoloPayment(row.id, kind, draft)
        latestSummary = saved.paymentSummary
      }
      if (latestSummary) onSaved(row.id, latestSummary, 'Dati economici salvati.')
      const generated = await generateFascicoloProforma(
        row.id,
        economicProformaBasis(latestSummary ?? row.paymentSummary),
      )
      setDrafts({})
      onSaved(row.id, generated.paymentSummary, generated.message)
      const destination = generated.redirectHref || (generated.proformaId
        ? `/fatturazione?id_documento=${encodeURIComponent(generated.proformaId)}`
        : '')
      setOperationMessage({ tone: 'success', text: generated.message || 'Proforma pronta.' })
      if (destination) window.location.assign(destination)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Generazione della proforma non riuscita.'
      setOperationMessage({ tone: 'error', text: message })
      onError(message)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <>
      <EconomicEvidenceStrip row={row}/>
      <div className="iu-fas-economic-edit-grid">
        {economicPaymentKinds.map((kind) => (
          <EconomicPaymentCell row={row} kind={kind} onSaved={onSaved} onError={onError} onDraftChange={registerDraft} forceLabel key={kind}/>
        ))}
      </div>
      <div className="iu-fas-economic-editor__actions" aria-live="polite">
        <span>{dirtyCount ? `${dirtyCount} ${dirtyCount === 1 ? 'modifica da salvare' : 'modifiche da salvare'}` : hasProforma ? 'Proforma già collegata' : 'Proforma da generare'}</span>
        <button type="button" className="iu-fas-economic-generate" onClick={() => { void generate() }} disabled={generating}>
          {generating ? <RefreshCw size={15} className="iu-spin"/> : <FileText size={15}/>}
          <span>{generating ? 'Generazione…' : hasProforma ? 'Apri proforma' : 'Genera proforma'}</span>
        </button>
      </div>
      {operationMessage ? (
        <div className={`iu-fas-economic-editor__message iu-fas-economic-editor__message--${operationMessage.tone}`} role={operationMessage.tone === 'error' ? 'alert' : 'status'}>
          {operationMessage.tone === 'error' ? <AlertTriangle size={15}/> : <CheckCircle2 size={15}/>}
          <span>{operationMessage.text}</span>
        </div>
      ) : null}
    </>
  )
}

function DossierMobileCard({ item, checked, onToggle, archive = false, economic = false, onDeleted, onError, onPaymentSaved }:{item:FascicoloRow; checked:boolean; onToggle:()=>void; archive?:boolean; economic?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; onPaymentSaved?:(id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string)=>void}) {
  return (
    <article className="iu-fas-mobile-card">
      <header>
        <label>
          <input type="checkbox" checked={checked} onChange={onToggle}/>
          <span>{item.ref}</span>
        </label>
        <Badge tone={item.tone}>{formatFascicoloStatus(item.status)}</Badge>
      </header>
      <a href={item.href} className="iu-fas-mobile-card__title">{item.title}</a>
      <p>{item.subtitle || item.court}</p>
      <DuplicatePracticeBadge item={item}/>
      <MissingRgBadge item={item}/>
      {item.relataStatusLabel ? (
        <a className={`iu-fas-relata-list-link iu-fas-relata-list-link--${item.relataTone}`} href={relataListHref(item)}>
          <FileSignature size={15}/>
          <span>Relata notifica</span>
          <strong>{item.relataStatusLabel}</strong>
        </a>
      ) : null}
      <dl>
        <div><dt>Cliente</dt><dd>{item.client}</dd></div>
        <div><dt>Tipo</dt><dd>{formatFascicoloType(item.type)}</dd></div>
        <div><dt>N. causa</dt><dd>{item.rgMissing ? 'Da acquisire' : item.rg}</dd></div>
        <div><dt>{archive ? 'Archiviazione' : 'Prossima scad.'}</dt><dd>{archive ? item.archive?.archivedAt || 'n.d.' : item.nextDeadline || 'n.d.'}</dd></div>
      </dl>
      {economic ? (
        <div className="iu-fas-mobile-card__economic">
          <ul>
            {economicPaymentKinds.map((kind) => {
              const payment = item.paymentSummary.items[kind]
              const label = payment.displayLabel || payment.label || paymentFullLabels[kind]
              return (
                <li key={kind}>
                  <span>{label}</span>
                  <strong>{payment.importoLabel || 'vuoto'}</strong>
                  <Badge tone={payment.tone}>{payment.statusLabel}</Badge>
                </li>
              )
            })}
          </ul>
          <details className="iu-fas-mobile-economic-editor">
            <summary><Edit3 size={14}/> Modifica controllo economico</summary>
            <div>
              <EconomicEditorPanel row={item} onSaved={onPaymentSaved || (() => {})} onError={onError || (() => {})}/>
            </div>
          </details>
        </div>
      ) : null}
      <footer>
        <span><FileText size={14}/> {item.documents}</span>
        {item.unreadCommunications ? <span><Bell size={14}/> {item.unreadCommunications}</span> : null}
        {item.alerts ? <span><ShieldCheck size={14}/> {item.alerts}</span> : null}
        <RowActions item={item} archive={archive} onDeleted={onDeleted} onError={onError}/>
      </footer>
    </article>
  )
}

function FascicoliTable({ items, selected, onToggle, onToggleAll, archive = false, filtered = false, onDeleted, onError, pagination, pageSize, onPageSizeChange, onPageChange, onPagePrefetch, pendingPage = null, view = 'operativa', viewToggle, onPaymentSaved, onStatusSaved }:{items:FascicoloRow[]; selected:Set<string>; onToggle:(id:string)=>void; onToggleAll:()=>void; archive?:boolean; filtered?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; pagination?:FascicoliPagination; pageSize?:number; onPageSizeChange?:(value:number)=>void; onPageChange?:(value:number)=>void; onPagePrefetch?:(value:number)=>void; pendingPage?:number | null; view?:ListView; viewToggle?:ReactNode; onPaymentSaved?:(id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string)=>void; onStatusSaved?:(id:string, status:FascicoloRow['status'], tone:FascicoloRow['tone'], message?:string)=>void}) {
  const economic = view === 'economica' && !archive
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  const total = pagination?.total ?? items.length
  const totalLabel = filtered ? 'fascicoli filtrati' : 'fascicoli'
  const handleError = onError || (() => {})
  const [expandedEconomicId, setExpandedEconomicId] = useState<string | null>(null)
  const statusCell = (item: FascicoloRow) => (
    !archive && onStatusSaved
      ? <StatusEditCell item={item} onSaved={onStatusSaved} onError={handleError}/>
      : <Badge tone={item.tone}>{formatFascicoloStatus(item.status)}</Badge>
  )
  const currentPage = pagination?.page ?? 1
  const totalPages = pagination?.pages ?? (items.length ? 1 : 0)
  const pageBusy = Boolean(pendingPage && pendingPage !== currentPage)
  const pageNumbers = (() => {
    const last = Math.max(1, totalPages)
    const values = new Set<number>([1, currentPage - 1, currentPage, currentPage + 1, last])
    return Array.from(values).filter((value) => value >= 1 && value <= last).sort((a, b) => a - b)
  })()
  const pageSizeControl = onPageSizeChange ? (
    <label className="iu-fas-page-size">
      <span>Per pagina</span>
      <select value={pageSize || pagination?.pageSize || 5} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
        <option value={5}>5</option>
        <option value={10}>10</option>
        <option value={25}>25</option>
        <option value={50}>50</option>
      </select>
    </label>
  ) : null
  const paginationControls = onPageChange && pagination ? (
    <>
      <button type="button" onClick={() => onPageChange(1)} onMouseEnter={() => onPagePrefetch?.(1)} onFocus={() => onPagePrefetch?.(1)} disabled={currentPage <= 1 || pageBusy}>Prima</button>
      <button type="button" onClick={() => onPageChange(currentPage - 1)} onMouseEnter={() => onPagePrefetch?.(currentPage - 1)} onFocus={() => onPagePrefetch?.(currentPage - 1)} disabled={currentPage <= 1 || pageBusy}>Precedente</button>
      <span>Pagina {currentPage} di {Math.max(1, totalPages)} - {total} {totalLabel}</span>
      {pageBusy ? <span className="iu-fas-page-loading" role="status">Caricamento pagina {pendingPage}...</span> : null}
      <div className="iu-fas-page-jump" aria-label="Vai a pagina">
        {pageNumbers.map((value, index) => (
          <button
            type="button"
            className={value === currentPage ? 'is-current' : ''}
            onClick={() => onPageChange(value)}
            onMouseEnter={() => onPagePrefetch?.(value)}
            onFocus={() => onPagePrefetch?.(value)}
            disabled={value === currentPage || pageBusy}
            aria-current={value === currentPage ? 'page' : undefined}
            key={value}
          >
            {index > 0 && value - pageNumbers[index - 1] > 1 ? `... ${value}` : value}
          </button>
        ))}
      </div>
      <button type="button" onClick={() => onPageChange(currentPage + 1)} onMouseEnter={() => onPagePrefetch?.(currentPage + 1)} onFocus={() => onPagePrefetch?.(currentPage + 1)} disabled={totalPages === 0 || currentPage >= totalPages || pageBusy}>Successiva</button>
      <button type="button" onClick={() => onPageChange(Math.max(1, totalPages))} onMouseEnter={() => onPagePrefetch?.(Math.max(1, totalPages))} onFocus={() => onPagePrefetch?.(Math.max(1, totalPages))} disabled={totalPages === 0 || currentPage >= totalPages || pageBusy}>Ultima</button>
    </>
  ) : null
  return (
    <IusentraDataSurface
      title={`${total} ${totalLabel}`}
      subtitle={archive
        ? 'Archivio pratiche chiuse'
        : economic
          ? 'Elenco unico dello studio — vista economica (contributo, spese/esborsi, liquidazione, parcella)'
          : 'Elenco unico dello studio — vista operativa'}
      toolbar={viewToggle || pageSizeControl ? (
        <div className="iu-fas-table-toolbar">
          {viewToggle}
          {pageSizeControl}
        </div>
      ) : null}
      footer={paginationControls}
      fill
      className="iu-fas-table-card"
      ariaLabel={archive ? 'Archivio fascicoli' : 'Elenco fascicoli'}
      empty={!items.length ? <p className="iu-empty">Nessun fascicolo corrisponde ai filtri impostati.</p> : null}
    >
      <SyncedTopScrollbar className="iu-fas-table-wrap iusentra-data-surface__scroll">
        <table className={economic ? 'iu-fas-table iu-fas-table--economic' : 'iu-fas-table'}>
          <thead>
            <tr>
              <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutti i fascicoli visibili"/></th>
              <th>Rif.</th>
              {economic ? null : <th>Titolo / oggetto</th>}
              {economic ? null : <th>Tipo</th>}
              <th>Cliente</th>
              {economic ? null : <th>N. causa</th>}
              <th>{archive ? 'Esito / archiviazione' : 'Prossima scad.'}</th>
              <th>Stato</th>
              {economic ? <th>Controllo economico</th> : <th>Documenti</th>}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const economicEditorOpen = economic && expandedEconomicId === item.id
              const economicEditorId = `economic-editor-${item.id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
              return (
                <Fragment key={item.id}>
                  <tr className={[economicEditorOpen ? 'is-economic-open' : '', item.duplicateCount > 1 ? 'iu-fas-row--duplicate' : ''].filter(Boolean).join(' ') || undefined}>
                    <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.ref}`}/></td>
                    <td>
                      {economic
                        ? <span className="iu-fas-economic-ref"><a href={item.href}><strong>{item.ref}</strong></a><span>{item.title}</span><MissingRgBadge item={item} compact/></span>
                        : <><strong>{item.ref}</strong><span>{item.internalRef}</span></>}
                    </td>
                    {economic ? null : (
                      <td className="iu-fas-title-cell">
                        <div className="iu-fas-title-line">
                          <a href={item.href}>{item.title}</a>
                        </div>
                        <span>{item.subtitle || item.court}</span>
                        <RowActions item={item} archive={archive} onDeleted={onDeleted} onError={onError} className="iu-fas-title-actions"/>
                        <DuplicatePracticeBadge item={item}/>
                        <MissingRgBadge item={item}/>
                        {item.relataStatusLabel ? (
                          <a className={`iu-fas-relata-list-link iu-fas-relata-list-link--${item.relataTone}`} href={relataListHref(item)}>
                            <FileSignature size={14}/>
                            <span>Relata notifica</span>
                            <strong>{item.relataStatusLabel}</strong>
                          </a>
                        ) : null}
                      </td>
                    )}
                    {economic ? null : <td><Badge tone="neutral">{formatFascicoloType(item.type)}</Badge></td>}
                    <td className={economic ? 'iu-fas-economic-client-cell' : undefined}>
                      {economic ? (
                        <span className="iu-fas-economic-client">
                          <strong>{item.client}</strong>
                          <DuplicatePracticeBadge item={item}/>
                          <button
                            type="button"
                            className="iu-fas-economic-edit-toggle"
                            aria-expanded={economicEditorOpen}
                            aria-controls={economicEditorId}
                            onClick={() => setExpandedEconomicId(economicEditorOpen ? null : item.id)}
                          >
                            <Edit3 size={14}/>
                            <span>{economicEditorOpen ? 'Chiudi modifica' : 'Modifica controllo economico'}</span>
                          </button>
                        </span>
                      ) : item.client}
                    </td>
                    {economic ? null : <td>{item.rgMissing ? <MissingRgBadge item={item} compact/> : item.rg}</td>}
                    <td>{archive ? <span>{item.archive?.outcome || 'n.d.'}<small>{item.archive?.archivedAt || ''}</small></span> : item.nextDeadline || 'n.d.'}</td>
                    <td>{statusCell(item)}</td>
                    {economic ? (
                      <td className="iu-fas-economic-matrix">
                        <div className="iu-fas-economic-summary-grid" aria-label={`Sintesi economica ${item.ref}`}>
                          {economicPaymentKinds.map((kind) => (
                            <EconomicPaymentSummary payment={item.paymentSummary.items[kind]} kind={kind} key={kind}/>
                          ))}
                        </div>
                        <EconomicEvidenceStrip row={item}/>
                      </td>
                    ) : <td><span className="iu-fas-doc-count">{item.documents}</span></td>}
                  </tr>
                  {economicEditorOpen ? (
                    <tr className="iu-fas-economic-editor-row">
                      <td colSpan={6}>
                        <section className="iu-fas-economic-editor" id={economicEditorId} aria-label={`Modifica controllo economico ${item.ref}`}>
                          <header>
                            <div>
                              <strong>Modifica controllo economico</strong>
                              <span>{item.ref} - {item.client}</span>
                            </div>
                            <button type="button" onClick={() => setExpandedEconomicId(null)} aria-label={`Chiudi modifica economica ${item.ref}`}>
                              <ChevronUp size={15}/>
                              <span>Chiudi</span>
                            </button>
                          </header>
                          <EconomicEditorPanel row={item} onSaved={onPaymentSaved || (() => {})} onError={handleError}/>
                        </section>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </SyncedTopScrollbar>
      <div className="iu-fas-mobile-list">
        {items.map((item) => <DossierMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} archive={archive} economic={economic} onDeleted={onDeleted} onError={onError} onPaymentSaved={onPaymentSaved} key={item.id}/>) }
      </div>
    </IusentraDataSurface>
  )
}

function ListFilters({ data, query, setQuery, type, setType, status, setStatus, sort, setSort, advancedOpen, setAdvancedOpen, refresh, onSavePreferences, preferencesState, preferencesUpdatedAt }:{data:FascicoliPageData; query:string; setQuery:(value:string)=>void; type:FascicoloTipo; setType:(value:FascicoloTipo)=>void; status:FascicoloStato; setStatus:(value:FascicoloStato)=>void; sort:SortKey; setSort:(value:SortKey)=>void; advancedOpen:boolean; setAdvancedOpen:(value:boolean)=>void; refresh:()=>void; onSavePreferences:()=>void; preferencesState:'idle'|'dirty'|'saving'|'saved'|'error'; preferencesUpdatedAt:string}) {
  const saveLabel = preferencesState === 'saving' ? 'Salvataggio...' : preferencesState === 'saved' ? 'Vista salvata' : 'Salva vista'
  const saveTitle = preferencesUpdatedAt ? `Vista salvata per questo studio: ${formatDateTimeIt(preferencesUpdatedAt)}` : 'Salva questi filtri come vista predefinita dello studio'
  return (
    <IusentraFiltersBar className="iu-fas-toolbar">
      <label className="iu-fas-search">
        <Search size={17}/>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca numero, anno, RG, cliente, titolo..."/>
      </label>
      <label className="iu-fas-filter-field iu-fas-filter-field--type">
        <span>Tipo</span>
        <select value={type} onChange={(event) => setType(event.target.value as FascicoloTipo)}>
          {data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
        </select>
      </label>
      <label className="iu-fas-filter-field iu-fas-filter-field--status">
        <span>Stato</span>
        <select value={status} onChange={(event) => setStatus(event.target.value as FascicoloStato)}>
          {data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
        </select>
      </label>
      <label className="iu-fas-filter-field iu-fas-filter-field--sort">
        <span>Ordine</span>
        <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select>
      </label>
      <button className="iu-fas-filter-btn" type="button" onClick={() => setAdvancedOpen(!advancedOpen)} aria-expanded={advancedOpen}><Filter size={16}/> Filtri</button>
      <button className={`iu-fas-filter-save iu-fas-filter-save--${preferencesState}`} type="button" onClick={onSavePreferences} disabled={preferencesState === 'saving'} title={saveTitle}>
        {preferencesState === 'saving' ? <RefreshCw size={16}/> : <Save size={16}/>}
        {saveLabel}
      </button>
      <button className="iu-fas-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna fascicoli"><RefreshCw size={17}/></button>
    </IusentraFiltersBar>
  )
}

function InsightPanel({ data, visible }:{data:FascicoliPageData; visible:FascicoloRow[]}) {
  const urgent = visible.filter((item) => item.alerts > 0 || item.unreadCommunications > 0).slice(0, 4)
  const withoutDeadline = visible.filter((item) => item.status !== 'archiviato' && !item.nextDeadlineIso && item.nextDeadline === 'n.d.').length
  const deadlineCopy = deadlineUrgencyCopy(data.summary)
  return (
    <IusentraSupportRail className="iu-fas-insights">
      <IusentraPanelCard title="Cabina fascicoli" subtitle="Controlli che conviene avere subito" icon={Gauge}>
        <div className="iu-fas-briefing">
          <article>
            <span>Da governare ora</span>
            <strong>{deadlineCopy.overdue ? countIt(deadlineCopy.overdue, 'scadenza scaduta', 'scadenze scadute') : countIt(data.summary.deadlines30, 'scadenza nei prossimi 30 giorni', 'scadenze nei prossimi 30 giorni')}</strong>
            <small>{deadlineCopy.urgent ? `${countIt(deadlineCopy.urgent, 'scadenza urgente', 'scadenze urgenti')}: ${deadlineCopy.note}.` : 'Nessuna scadenza urgente aperta.'}</small>
          </article>
          <article>
            <span>Qualità archivio</span>
            <strong>{data.summary.toArchive} fascicoli da chiudere o archiviare</strong>
            <small>{data.summary.archived} fascicoli già archiviati. {withoutDeadline} pratiche attive senza prossima scadenza visibile.</small>
          </article>
          {data.summary.duplicatePractices ? (
            <article>
              <span>Doppioni da verificare</span>
              <strong>{data.summary.duplicatePractices} gruppi stesso cliente/RG</strong>
              <small>Controlla prima di usare importi, scadenze o documenti come fonte operativa.</small>
            </article>
          ) : null}
          {data.summary.missingRg ? (
            <article>
              <span>Ruoli da completare</span>
              <strong>{data.summary.missingRg} fascicoli senza RG</strong>
              <small>Acquisire il numero di ruolo dal portale o dai provvedimenti prima di deposito e notifiche.</small>
            </article>
          ) : null}
        </div>
      </IusentraPanelCard>
      <IusentraPanelCard title="Alert operativi" icon={Bell} badge={urgent.length} tone="warning">
        {urgent.length ? (
          <div className="iu-fas-alerts">
            {urgent.map((item) => (
              <a href={item.href} key={item.id}>
                <Badge tone={item.alerts ? 'warning' : 'primary'}>{item.alerts ? 'Controllo' : 'Comunicazione'}</Badge>
                <strong>{item.ref} - {item.client}</strong>
                <span>{item.alerts ? `${item.alerts} elementi da verificare` : `${item.unreadCommunications} comunicazioni non lette`}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun alert sui fascicoli visibili.</p>}
      </IusentraPanelCard>
      <IusentraPanelCard title="Azioni rapide" icon={Sparkles} tone="gold">
        <div className="iu-fas-quick-actions">
          <a href="/fascicoli/nuovo"><FolderPlus size={15}/> Nuovo fascicolo</a>
          <a href="/scadenziario/nuova"><CalendarDays size={15}/> Nuova scadenza</a>
          <a href="/redazione-atti"><FileCheck2 size={15}/> Redazione atti</a>
          <a href="/fascicoli/archivio"><Archive size={15}/> Archivio</a>
        </div>
      </IusentraPanelCard>
    </IusentraSupportRail>
  )
}

function FascicoliListPage() {
  const [data, setData] = useState<FascicoliPageData>(emptyFascicoliPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [type, setType] = useState<FascicoloTipo>('tutti')
  const [status, setStatus] = useState<FascicoloStato>(initialStatusFilter)
  const [sort, setSort] = useState<SortKey>(initialSortFilter)
  const [court, setCourt] = useState('')
  const [debouncedCourt, setDebouncedCourt] = useState('')
  const [alertsOnly, setAlertsOnly] = useState(() => initialUrlBool('alerts_only', 'alertsOnly'))
  const [paymentsOnly, setPaymentsOnly] = useState(() => initialUrlBool('payments_only', 'paymentsOnly'))
  const [missingRgOnly, setMissingRgOnly] = useState(() => initialUrlBool('missing_rg_only', 'missingRgOnly'))
  const [duplicatesOnly, setDuplicatesOnly] = useState(() => initialUrlBool('duplicates_only', 'duplicatesOnly'))
  const [view, setView] = useState<ListView>(initialListView)
  const [cuFilter, setCuFilter] = useState<FascicoloPaymentFilter>(() => initialPaymentFilter('cu'))
  const [liquidazioneFilter, setLiquidazioneFilter] = useState<FascicoloPaymentFilter>(() => initialPaymentFilter('liquidazione'))
  const [parcellaFilter, setParcellaFilter] = useState<FascicoloPaymentFilter>(() => initialPaymentFilter('parcella'))
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ tone: 'success' | 'warning' | 'danger'; message: string } | null>(null)
  const [bulkConfirmMessage, setBulkConfirmMessage] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [pendingPage, setPendingPage] = useState<number | null>(null)
  const pageCacheRef = useRef<Map<string, FascicoliPageData>>(new Map())
  const pageRequestsRef = useRef<Map<string, Promise<FascicoliPageData>>>(new Map())
  const economicPresidioRunRef = useRef('')
  const explicitListPreferenceParamsRef = useRef(hasExplicitListPreferenceParams())
  const savedFilterPreferencesSignatureRef = useRef('')
  const [preferencesReady, setPreferencesReady] = useState(() => explicitListPreferenceParamsRef.current)
  const [filterPreferencesState, setFilterPreferencesState] = useState<'idle'|'dirty'|'saving'|'saved'|'error'>('idle')
  const [filterPreferencesUpdatedAt, setFilterPreferencesUpdatedAt] = useState('')

  const listParams = (overrides: Partial<FascicoliPageParams> = {}): FascicoliPageParams => ({
    page,
    pageSize,
    q: debouncedQuery,
    type,
    status,
    court: debouncedCourt,
    sort,
    view,
    alertsOnly,
    paymentsOnly,
    missingRgOnly,
    duplicatesOnly,
    cu: cuFilter,
    liquidazione: liquidazioneFilter,
    parcella: parcellaFilter,
    ...overrides,
  })

  const currentFilterPreferences = useMemo<FascicoliFilterPreferences>(() => ({
    type,
    status,
    sort,
    view,
    court: court.trim(),
    alertsOnly,
    paymentsOnly,
    missingRgOnly,
    duplicatesOnly,
    cu: cuFilter,
    liquidazione: liquidazioneFilter,
    parcella: parcellaFilter,
    pageSize,
  }), [alertsOnly, court, cuFilter, duplicatesOnly, liquidazioneFilter, missingRgOnly, pageSize, parcellaFilter, paymentsOnly, sort, status, type, view])

  const currentFilterPreferencesSignature = useMemo(
    () => filterPreferencesSignature(currentFilterPreferences),
    [currentFilterPreferences],
  )

  const requestFascicoliPage = (params: FascicoliPageParams, options: { force?: boolean } = {}) => {
    const key = fascicoliListCacheKey(params)
    if (!options.force) {
      const cached = pageCacheRef.current.get(key)
      if (cached) return Promise.resolve(cached)
      const running = pageRequestsRef.current.get(key)
      if (running) return running
    }
    const request = getFascicoliPage(params).then((payload) => {
      pageCacheRef.current.set(key, payload)
      return payload
    }).finally(() => {
      if (pageRequestsRef.current.get(key) === request) pageRequestsRef.current.delete(key)
    })
    pageRequestsRef.current.set(key, request)
    return request
  }

  const invalidateListCache = () => {
    pageCacheRef.current.clear()
    pageRequestsRef.current.clear()
  }

  const refresh = () => {
    invalidateListCache()
    const params = listParams()
    setPendingPage(params.page || page)
    setLoading(true)
    requestFascicoliPage(params, { force: true })
      .then((payload) => {
        setData(payload)
        setPendingPage(null)
      })
      .finally(() => setLoading(false))
  }

  const warmEconomicFirstPages = (params: FascicoliPageParams) => {
    if (params.view !== 'economica' || params.page !== 1) return
    const hasScopedFilters = Boolean(
      params.q?.trim()
      || params.client?.trim()
      || params.rg?.trim()
      || params.court?.trim()
      || (params.type && params.type !== 'tutti')
      || (params.status && params.status !== 'tutti')
      || params.alertsOnly
      || params.paymentsOnly
      || params.missingRgOnly
      || params.duplicatesOnly
      || (params.cu && params.cu !== 'tutti')
      || (params.fondoSpese && params.fondoSpese !== 'tutti')
      || (params.liquidazione && params.liquidazione !== 'tutti')
      || (params.parcella && params.parcella !== 'tutti')
    )
    if (hasScopedFilters) return
    ;[2, 3].forEach((target) => {
      void requestFascicoliPage({ ...params, page: target }).catch(() => undefined)
    })
  }

  useEffect(() => {
    if (explicitListPreferenceParamsRef.current) return
    let active = true
    getFascicoliFilterPreferences()
      .then((result) => {
        if (!active) return
        const preferences = result.preferences
        if (result.configured) {
          setPage(1)
          setType(preferences.type)
          setStatus(preferences.status)
          setSort(toSavedSortKey(String(preferences.sort)))
          setView(toSavedListView(String(preferences.view)))
          setCourt(preferences.court)
          setDebouncedCourt(preferences.court.trim())
          setAlertsOnly(preferences.alertsOnly)
          setPaymentsOnly(preferences.paymentsOnly)
          setMissingRgOnly(preferences.missingRgOnly)
          setDuplicatesOnly(preferences.duplicatesOnly)
          setCuFilter(toSavedPaymentFilter(String(preferences.cu)))
          setLiquidazioneFilter(toSavedPaymentFilter(String(preferences.liquidazione)))
          setParcellaFilter(toSavedPaymentFilter(String(preferences.parcella)))
          setPageSize(preferences.pageSize)
          setAdvancedOpen(Boolean(
            preferences.court.trim()
            || preferences.alertsOnly
            || preferences.paymentsOnly
            || preferences.missingRgOnly
            || preferences.duplicatesOnly
            || preferences.cu !== 'tutti'
            || preferences.liquidazione !== 'tutti'
            || preferences.parcella !== 'tutti',
          ))
          savedFilterPreferencesSignatureRef.current = filterPreferencesSignature(preferences)
          setFilterPreferencesState('saved')
          setFilterPreferencesUpdatedAt(result.updatedAt)
        }
      })
      .catch(() => {
        if (active) setFilterPreferencesState('error')
      })
      .finally(() => {
        if (active) setPreferencesReady(true)
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1)
      setDebouncedQuery(query.trim())
      setDebouncedCourt(court.trim())
    }, 350)
    return () => window.clearTimeout(timer)
  }, [court, query])

  useEffect(() => {
    if (!preferencesReady) return
    let active = true
    const params = listParams()
    const hasCachedPage = pageCacheRef.current.has(fascicoliListCacheKey(params))
    setPendingPage(hasCachedPage ? null : params.page || page)
    setLoading(!hasCachedPage)
    const request = requestFascicoliPage(params)
    request
      .then((payload) => {
        if (!active) return
        setData(payload)
        setPendingPage(null)
        if (!hasCachedPage) window.setTimeout(() => warmEconomicFirstPages(params), 250)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
    // listParams legge solo gli stati elencati sotto: la dipendenza esplicita evita refetch spurii.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alertsOnly, cuFilter, debouncedCourt, debouncedQuery, duplicatesOnly, liquidazioneFilter, missingRgOnly, page, pageSize, parcellaFilter, paymentsOnly, preferencesReady, sort, status, type, view])

  useEffect(() => {
    if (!preferencesReady) return
    if (filterPreferencesState === 'saving') return
    if (!savedFilterPreferencesSignatureRef.current) return
    setFilterPreferencesState(
      savedFilterPreferencesSignatureRef.current === currentFilterPreferencesSignature ? 'saved' : 'dirty',
    )
  }, [currentFilterPreferencesSignature, filterPreferencesState, preferencesReady])

  useEffect(() => {
    if (!preferencesReady) return
    if (loading || pendingPage) return
    const current = data.pagination.page || page
    const totalPages = data.pagination.pages || 0
    if (totalPages < 2) return
    ;[current + 1, current + 2].forEach((target) => {
      if (target < 1 || target > totalPages) return
      void requestFascicoliPage(listParams({ page: target })).catch(() => undefined)
    })
    // listParams legge solo gli stati elencati sotto: la dipendenza esplicita evita prefetch su filtri vecchi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alertsOnly, cuFilter, data.pagination.page, data.pagination.pages, debouncedCourt, debouncedQuery, duplicatesOnly, liquidazioneFilter, loading, missingRgOnly, page, pageSize, parcellaFilter, paymentsOnly, pendingPage, preferencesReady, sort, status, type, view])

  useEffect(() => {
    const presidioDue = Number(data.summary.economicAnalysisDue || 0)
    const presidioKey = `${view}:${data.summary.total || 0}:${data.summary.economicAnalysisDue || 0}`
    if (view !== 'economica' || loading || economicPresidioRunRef.current === presidioKey || presidioDue < 1) return
    economicPresidioRunRef.current = presidioKey
    runFascicoliEconomicPresidio(1000)
      .then((result) => {
        const changed = result.createdCount + result.contributiUpdatedCount + result.documentAnalysisUpdatedCount + result.statusDefinedUpdatedCount
        if (changed > 0) {
          const parts = [
            result.contributiUpdatedCount ? `${result.contributiUpdatedCount} contributi unificati salvati` : '',
            result.documentAnalysisUpdatedCount ? `${result.documentAnalysisUpdatedCount} controlli documentali aggiornati` : '',
            result.statusDefinedUpdatedCount ? `${result.statusDefinedUpdatedCount} fascicoli definiti` : '',
            result.createdCount ? `${result.createdCount} bozze proforma create` : '',
          ].filter(Boolean)
          setToast({ tone: 'success', message: `${parts.join(', ')}. I dati sono stati consolidati nel fascicolo.` })
          refresh()
        }
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message.trim() : ''
        if (message && message !== 'Presidio economico non completato.') {
          setToast({ tone: 'warning', message: `Presidio automatico proforma da ricontrollare: ${message}` })
        }
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.summary.economicAnalysisDue, data.summary.total, loading, view])

  const visible = data.items
  const economicFiltersActive = cuFilter !== 'tutti' || liquidazioneFilter !== 'tutti' || parcellaFilter !== 'tutti'
  const filtersActive = Boolean(query.trim() || type !== 'tutti' || status !== 'tutti' || court.trim() || alertsOnly || paymentsOnly || missingRgOnly || duplicatesOnly || economicFiltersActive)
  const updateType = (value: FascicoloTipo) => { setPage(1); setType(value) }
  const updateStatus = (value: FascicoloStato) => { setPage(1); setStatus(value) }
  const updateSort = (value: SortKey) => { setPage(1); setSort(value) }
  const updateAlertsOnly = (value: boolean) => { setPage(1); setAlertsOnly(value) }
  const updatePaymentsOnly = (value: boolean) => { setPage(1); setPaymentsOnly(value) }
  const updateCuFilter = (value: FascicoloPaymentFilter) => { setPage(1); setCuFilter(value) }
  const updateLiquidazioneFilter = (value: FascicoloPaymentFilter) => { setPage(1); setLiquidazioneFilter(value) }
  const updateParcellaFilter = (value: FascicoloPaymentFilter) => { setPage(1); setParcellaFilter(value) }
  const updateView = (value: ListView) => { setView(value); syncListViewInUrl(value) }
  const updatePageSize = (value: number) => { setPage(1); setPageSize(value) }
  const saveCurrentFilterPreferences = () => {
    setFilterPreferencesState('saving')
    saveFascicoliFilterPreferences(currentFilterPreferences)
      .then((result) => {
        savedFilterPreferencesSignatureRef.current = filterPreferencesSignature(result.preferences)
        setFilterPreferencesUpdatedAt(result.updatedAt)
        setFilterPreferencesState('saved')
        setToast({ tone: 'success', message: result.message || 'Vista fascicoli salvata per questo studio.' })
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message.trim() : ''
        setFilterPreferencesState('error')
        setToast({ tone: 'danger', message: message || 'Preferenze filtri non salvate.' })
      })
  }
  const prefetchPage = (value: number) => {
    const maxPage = Math.max(1, data.pagination.pages || 1)
    const target = Math.max(1, Math.min(maxPage, value))
    if (target === data.pagination.page) return
    void requestFascicoliPage(listParams({ page: target })).catch(() => undefined)
  }
  const updatePage = (value: number) => {
    const maxPage = Math.max(1, data.pagination.pages || 1)
    const target = Math.max(1, Math.min(maxPage, value))
    if (target === page && target === data.pagination.page) return
    const cached = pageCacheRef.current.get(fascicoliListCacheKey(listParams({ page: target })))
    setPendingPage(target)
    setPage(target)
    if (cached) {
      setData(cached)
      setLoading(false)
      setPendingPage(null)
    }
  }
  const applyStatContext = (target: ListContextTarget) => (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    const next: Required<Omit<ListContextTarget, 'hash'>> & { hash?: string } = {
      view: target.view || 'operativa',
      status: target.status || 'tutti',
      sort: target.sort || 'rg',
      alertsOnly: Boolean(target.alertsOnly),
      paymentsOnly: Boolean(target.paymentsOnly),
      missingRgOnly: Boolean(target.missingRgOnly),
      duplicatesOnly: Boolean(target.duplicatesOnly),
      cu: target.cu || 'tutti',
      liquidazione: target.liquidazione || 'tutti',
      parcella: target.parcella || 'tutti',
      hash: target.hash,
    }
    setPage(1)
    setQuery('')
    setDebouncedQuery('')
    setType('tutti')
    setStatus(next.status)
    setSort(next.sort)
    setCourt('')
    setDebouncedCourt('')
    setAlertsOnly(next.alertsOnly)
    setPaymentsOnly(next.paymentsOnly)
    setMissingRgOnly(next.missingRgOnly)
    setDuplicatesOnly(next.duplicatesOnly)
    setView(next.view)
    setCuFilter(next.cu)
    setLiquidazioneFilter(next.liquidazione)
    setParcellaFilter(next.parcella)
    setSelected(new Set())
    syncListContextInUrl(next)
    if (next.hash) {
      window.setTimeout(() => document.querySelector(next.hash || '')?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 50)
    }
  }

  const selectedVisible = visible.filter((item) => selected.has(item.id)).length
  const selectedItems = visible.filter((item) => selected.has(item.id))
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const toggleAll = () => setSelected((current) => {
    const allSelected = visible.length > 0 && visible.every((item) => current.has(item.id))
    if (allSelected) return new Set([...current].filter((id) => !visible.some((item) => item.id === id)))
    return new Set([...current, ...visible.map((item) => item.id)])
  })
  const requestBulkDelete = () => {
    if (!selectedItems.length) return
    const refs = selectedItems.map((item) => item.ref).join(', ')
    const message = selectedItems.length === 1
      ? `Eliminare definitivamente il fascicolo ${selectedItems[0].ref}?`
      : `Eliminare definitivamente ${selectedItems.length} fascicoli selezionati? ${refs}`
    setBulkConfirmMessage(message)
  }

  const handleBulkDelete = async () => {
    if (!selectedItems.length) return
    setBulkConfirmMessage('')
    setLoading(true)
    try {
      const deleted: string[] = []
      for (const item of selectedItems) {
        const response = await fetch(item.deleteHref || `/fascicoli/${encodeURIComponent(item.id)}/elimina`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        })
        const contentType = response.headers.get('content-type') || ''
        const payload = contentType.includes('application/json') ? await response.json().catch(() => ({} as ActionPayload)) : {} as ActionPayload
        if (!response.ok || payload.ok === false) throw new Error(String(payload.messaggio || payload.errore || payload.error || `Eliminazione non riuscita: HTTP ${response.status}`))
        deleted.push(item.id)
      }
      setSelected((current) => new Set([...current].filter((id) => !deleted.includes(id))))
      setToast({ tone: 'success', message: deleted.length === 1 ? 'Fascicolo eliminato.' : `${deleted.length} fascicoli eliminati.` })
      refresh()
    } catch (err) {
      setLoading(false)
      setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Eliminazione selezione non riuscita.' })
    }
  }
  const handleFascicoloDeleted = (id: string, message?: string) => {
    setSelected((current) => { const next = new Set(current); next.delete(id); return next })
    setToast({ tone: 'success', message: message || 'Fascicolo eliminato.' })
    refresh()
  }
  const handleListError = (message: string) => setToast({ tone: 'danger', message })
  const handlePaymentSaved = (id: string, paymentSummary: FascicoloRow['paymentSummary'], message?: string) => {
    invalidateListCache()
    setData((current) => ({
      ...current,
      items: current.items.map((item) => item.id === id ? { ...item, paymentSummary } : item),
    }))
    setToast({ tone: 'success', message: message || 'Controllo economico aggiornato.' })
  }
  const handleStatusSaved = (id: string, statusValue: FascicoloRow['status'], tone: FascicoloRow['tone'], message?: string) => {
    invalidateListCache()
    setData((current) => ({
      ...current,
      items: current.items.map((item) => item.id === id ? { ...item, status: statusValue, tone } : item),
    }))
    setToast({ tone: 'success', message: message || 'Stato fascicolo aggiornato.' })
    // Con un filtro stato attivo la riga potrebbe non corrispondere più: riallinea conteggi e pagina.
    if (status !== 'tutti') refresh()
  }

  const viewToggle = (
    <div className="iu-fas-viewtoggle" role="tablist" aria-label="Vista elenco fascicoli">
      <button type="button" role="tab" aria-selected={view === 'operativa'} className={view === 'operativa' ? 'is-active' : ''} onClick={() => updateView('operativa')}>
        <FolderOpen size={14}/> Operativa
      </button>
      <button type="button" role="tab" aria-selected={view === 'economica'} className={view === 'economica' ? 'is-active' : ''} onClick={() => updateView('economica')}>
        <Euro size={14}/> Economica
      </button>
    </div>
  )
  const deadlineCopy = deadlineUrgencyCopy(data.summary)

  return (
    <main className="iu-content iu-fascicoli-page">
      <IusentraPageShell className="iu-fas-preset-shell">
        <section className="iu-fas-hero">
          <div>
            <span className="iu-fas-eyebrow"><FolderOpen size={16}/> Fascicoli</span>
            <h1>Fascicoli</h1>
            <p>Procedimenti civili, penali, amministrativi e tributari con scadenze, documenti, clienti e prossime azioni.</p>
          </div>
          <div className="iu-fas-hero__actions">
            <Button href="/fascicoli/esporta"><Download size={15}/> Esporta</Button>
            <Button href="/fascicoli/archivio"><Archive size={15}/> Archivio</Button>
            <Button variant="primary" href="/fascicoli/nuovo"><FolderPlus size={16}/> Nuovo fascicolo</Button>
          </div>
        </section>

        <section className="iu-fas-stats" aria-label="Indicatori fascicoli">
          <StatCard icon={<FolderOpen size={19}/>} label="Attivi" value={data.summary.active} note="non archiviati" tone="primary" onClick={applyStatContext({})}/>
          <StatCard icon={<CheckCircle2 size={19}/>} label="In corso" value={data.summary.inProgress} note="da lavorare" tone="success" onClick={applyStatContext({ status: 'in_corso' })}/>
          <StatCard icon={<Archive size={19}/>} label="Da archiviare" value={data.summary.toArchive} note={`${data.summary.toArchive} definiti, ${data.summary.archived} già archiviati`} tone="warning" onClick={applyStatContext({ status: 'da_archiviare' })}/>
          <StatCard icon={<Euro size={19}/>} label="Economico" value={data.summary.economicToReview} note="controlli da completare" tone="warning" href="?vista=economica&payments_only=1" onClick={applyStatContext({ view: 'economica', paymentsOnly: true })}/>
          <StatCard icon={<WalletCards size={19}/>} label="Registrato" value={formatCurrency(data.summary.registeredAmount)} note="sui fascicoli visibili" tone="success" onClick={applyStatContext({ view: 'economica' })}/>
          <StatCard icon={<FileCheck2 size={19}/>} label="Parcelle" value={data.summary.invoiceWorkTotal || data.summary.invoicesToIssue} note={`${data.summary.invoicesToIssue} da emettere, ${data.summary.invoiceDraftsToReview} bozze da visionare`} tone="purple" onClick={applyStatContext({ view: 'economica', parcella: 'da_emettere' })}/>
          <StatCard icon={<CalendarDays size={19}/>} label="Scadenze urgenti" value={deadlineCopy.urgent} note={deadlineCopy.note} tone={deadlineCopy.tone} onClick={applyStatContext({ hash: '#scadenze-urgenti' })}/>
          <StatCard icon={<Copy size={19}/>} label="Doppioni" value={data.summary.duplicatePractices} note={data.summary.duplicatePractices ? 'stesso cliente e RG' : 'nessun gruppo rilevato'} tone={data.summary.duplicatePractices ? 'warning' : 'success'} onClick={applyStatContext({ duplicatesOnly: true })}/>
          <StatCard icon={<Landmark size={19}/>} label="RG da acquisire" value={data.summary.missingRg} note={data.summary.missingRg ? 'completare da portale o provvedimento' : 'ruoli completi'} tone={data.summary.missingRg ? 'warning' : 'success'} onClick={applyStatContext({ missingRgOnly: true })}/>
          <StatCard icon={<FileText size={19}/>} label="Documenti" value={data.summary.documents} note="nel perimetro visibile" tone="purple" onClick={applyStatContext({ sort: 'documenti' })}/>
          <StatCard icon={<Bell size={19}/>} label="Comunicazioni" value={data.summary.unreadCommunications} note="non lette o da associare" tone="info" onClick={applyStatContext({ alertsOnly: true })}/>
        </section>

        {data.deadlines.length ? (
          <section className="iu-fas-deadline-alert" id="scadenze-urgenti">
            <AlertIcon />
            <div>
              <strong>{deadlineCopy.title}</strong>
              <div>{data.deadlines.slice(0, 4).map((item) => <a href={item.href} key={item.id}>{item.matterRef} - {item.title} <span>{item.date}</span></a>)}</div>
            </div>
          </section>
        ) : null}

      <IusentraMainArea className="iu-fas-layout">
        <IusentraMainSurface className="iu-fas-main-list">
          <ListFilters data={data} query={query} setQuery={setQuery} type={type} setType={updateType} status={status} setStatus={updateStatus} sort={sort} setSort={updateSort} advancedOpen={advancedOpen} setAdvancedOpen={setAdvancedOpen} refresh={refresh} onSavePreferences={saveCurrentFilterPreferences} preferencesState={filterPreferencesState} preferencesUpdatedAt={filterPreferencesUpdatedAt}/>

      {advancedOpen ? (
      <IusentraContextFilters className="iu-fas-advanced is-open">
        <div className="iu-fas-context-summary">
          <strong>{sortLabels[sort]}</strong>
          <small>{court ? `Ufficio: ${court}` : 'Tutti gli uffici'}{alertsOnly ? ' · solo alert' : ''}</small>
        </div>
        {advancedOpen ? (
          <>
            <label><span>Ufficio giudiziario</span><input value={court} onChange={(event) => setCourt(event.target.value)} placeholder="Tribunale, TAR, GDP..."/></label>
            <label><span>Ordinamento</span><select value={sort} onChange={(event) => updateSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
            <label className="iu-fas-check"><input type="checkbox" checked={alertsOnly} onChange={(event) => updateAlertsOnly(event.target.checked)}/><span>Solo fascicoli con alert o comunicazioni</span></label>
            <label className="iu-fas-check"><input type="checkbox" checked={paymentsOnly} onChange={(event) => updatePaymentsOnly(event.target.checked)}/><span>Solo controllo economico da completare</span></label>
            <div className="iu-fas-economic-filters" role="group" aria-label="Filtri per voce economica">
              <label><span>Contributo</span><select value={cuFilter} onChange={(event) => updateCuFilter(event.target.value as FascicoloPaymentFilter)}>{paymentFilterOptions.filter((option) => option.value !== 'da_emettere').map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
              <label><span>Liquidazione</span><select value={liquidazioneFilter} onChange={(event) => updateLiquidazioneFilter(event.target.value as FascicoloPaymentFilter)}>{paymentFilterOptions.filter((option) => option.value !== 'da_emettere').map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
              <label><span>Parcella</span><select value={parcellaFilter} onChange={(event) => updateParcellaFilter(event.target.value as FascicoloPaymentFilter)}>{paymentFilterOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
            </div>
          </>
        ) : null}
      </IusentraContextFilters>
      ) : null}

      <section className="iu-fas-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione fascicoli...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> Vista operativa aggiornata con salvataggi tracciati e controlli di studio già governati.</small>
        {selectedVisible ? <small className="iu-fas-selected">{selectedVisible} selezionati</small> : null}
      </section>

      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}

          {selectedVisible ? (
            <div className="iu-fas-bulkbar">
              <strong>{selectedVisible} fascicoli selezionati</strong>
              <a href="/fascicoli/esporta"><Download size={14}/> Esporta selezione</a>
              <button className="is-danger" type="button" onClick={requestBulkDelete}><Trash2 size={14}/> Elimina selezionati</button>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          {bulkConfirmMessage ? (
            <div className="iu-fas-confirm-modal" role="dialog" aria-modal="true" aria-label="Elimina fascicoli selezionati">
              <div className="iu-fas-confirm-modal__box">
                <strong>Elimina fascicoli selezionati</strong>
                <p>{bulkConfirmMessage}</p>
                <div>
                  <button type="button" onClick={() => setBulkConfirmMessage('')} disabled={loading}>Annulla</button>
                  <button type="button" className="is-danger" onClick={() => { void handleBulkDelete() }} disabled={loading}>Elimina</button>
                </div>
              </div>
            </div>
          ) : null}
          <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll} onDeleted={handleFascicoloDeleted} onError={handleListError} filtered={filtersActive} pagination={data.pagination} pageSize={pageSize} onPageSizeChange={updatePageSize} onPageChange={updatePage} onPagePrefetch={prefetchPage} pendingPage={pendingPage} view={view} viewToggle={viewToggle} onPaymentSaved={handlePaymentSaved} onStatusSaved={handleStatusSaved}/>
        </IusentraMainSurface>
        <InsightPanel data={data} visible={visible}/>
      </IusentraMainArea>

        <section className="iu-fas-lower-grid">
          <Panel title="Controllo qualità fascicoli" subtitle="Cose da non lasciare implicite" icon={<BriefcaseBusiness size={17}/>}>
            <div className="iu-fas-checklist">
              <span><Landmark size={16}/> Ufficio, RG e tipo procedimento sempre visibili</span>
              <span><CalendarDays size={16}/> Prossima scadenza in evidenza per ogni pratica attiva</span>
              <span><FileText size={16}/> Documenti locali, portale e stato firma separati</span>
            </div>
          </Panel>
          <Panel title="Integrazioni pronte" subtitle="Agganci alla gestione telematica" icon={<Sparkles size={17}/>}>
            <div className="iu-fas-integrations">
              <a href="/polisWeb">PolisWeb / PST</a>
              <a href="/pdp">PDP Penale</a>
              <a href="/pat">PAT Amministrativo</a>
              <a href="/sigit">PTT Tributario</a>
            </div>
          </Panel>
        </section>
      </IusentraPageShell>

      <FloatingLex context="fascicoli" title="Lex AI fascicoli" body="Posso sintetizzare un fascicolo, evidenziare scadenze senza prossima azione, preparare una lista documenti e suggerire il percorso prima di deposito, udienza o archiviazione." primaryHref="#lex" primaryLabel="Apri Lex fascicoli" secondaryHref="/global-search?tipo=fascicoli" secondaryLabel="Cerca fascicoli" />
    </main>
  )
}

function AlertIcon() {
  return <ShieldCheck size={20}/>
}

function ArchivePage() {
  const [data, setData] = useState<FascicoliPageData>(emptyFascicoliPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  useEffect(() => { let active = true; getFascicoliArchive().then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [])
  const visible = useMemo(() => data.items.filter((item) => isInsideQuery(item, query)), [data.items, query])
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const toggleAll = () => setSelected((current) => visible.every((item) => current.has(item.id)) ? new Set<string>() : new Set(visible.map((item) => item.id)))
  const refreshArchive = () => {
    setLoading(true)
    getFascicoliArchive().then(setData).finally(() => setLoading(false))
  }
  const handleArchiveDeleted = (id: string, message?: string) => {
    setSelected((current) => { const next = new Set(current); next.delete(id); return next })
    setToast({ tone: 'success', message: message || 'Fascicolo eliminato.' })
    refreshArchive()
  }
  const handleArchiveError = (message: string) => setToast({ tone: 'danger', message })
  return (
    <main className="iu-content iu-fascicoli-page">
      <section className="iu-fas-hero iu-fas-hero--archive">
        <div><span className="iu-fas-eyebrow"><Archive size={16}/> Archivio</span><h1>Archivio Fascicoli</h1><p>Procedimenti definiti, archiviati, ZIP e possibilità di ripristino.</p></div>
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><FolderOpen size={15}/> Fascicoli attivi</Button><Button href="/fascicoli/esporta"><Download size={15}/> Esporta</Button></div>
      </section>
      <section className="iu-fas-stats"><StatCard icon={<Archive size={19}/>} label="Archiviati" value={data.summary.archived || data.items.length} note="in archivio" tone="neutral"/><StatCard icon={<FileArchive size={19}/>} label="ZIP" value={data.items.filter((item) => item.archive?.zipAvailable).length} note="archivi scaricabili" tone="primary"/><StatCard icon={<BadgeCheck size={19}/>} label="Esiti" value={data.items.filter((item) => item.archive?.outcome).length} note="con esito finale" tone="success"/></section>
      <section className="iu-fas-toolbar"><label className="iu-fas-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca per numero, titolo, cliente..."/></label></section>
      <section className="iu-fas-status-line"><span className={loading ? '' : 'is-ok'}>{loading ? 'Caricamento archivio...' : `Archivio aggiornato - ${data.source}`}</span><small><RotateCcw size={14}/> Il ripristino usa il servizio operativo con audit.</small></section>
      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}
      <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll} archive onDeleted={handleArchiveDeleted} onError={handleArchiveError}/>
      <FloatingLex context="archivio-fascicoli" title="Lex AI archivio" body="Posso aiutarti a controllare fascicoli archiviati, ZIP mancanti, esiti finali e criteri di conservazione." primaryHref="#lex" primaryLabel="Apri Lex archivio" secondaryHref="/fascicoli/archivio" secondaryLabel="Archivio fascicoli" />
    </main>
  )
}

function dateInputValue(value: string | number | boolean | undefined): string {
  const raw = String(value ?? '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw
  const italian = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (italian) return `${italian[3]}-${italian[2]}-${italian[1]}`
  return ''
}

type LocalSignaturePinRequest = {
  filename: string
  outputFilename: string
  resolve: (pin: string) => void
  reject: (error: Error) => void
}

function Field({ label, name, defaultValue = '', type = 'text', required = false, readOnly = false, placeholder = '', step, min, inputMode, children }:{label:string; name:string; defaultValue?:string|number|boolean; type?:string; required?:boolean; readOnly?:boolean; placeholder?:string; step?:string|number; min?:string|number; inputMode?:'decimal'|'numeric'; children?:ReactNode}) {
  const value = type === 'date' ? dateInputValue(defaultValue) : String(defaultValue ?? '')
  return (
    <label className="iu-fas-field">
      <span>{label}{required ? <b>*</b> : null}</span>
      {children || <input type={type} name={name} defaultValue={value} required={required} readOnly={readOnly} placeholder={placeholder} step={step} min={min} inputMode={inputMode}/>}
    </label>
  )
}

function SelectField({ label, name, options, defaultValue = '', required = false }:{label:string; name:string; options:SelectOption[]; defaultValue?:string; required?:boolean}) {
  return <Field label={label} name={name} required={required}><select name={name} defaultValue={defaultValue} required={required}>{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></Field>
}

function TextAreaField({ label, name, defaultValue = '', rows = 3, placeholder = '', required = false }:{label:string; name:string; defaultValue?:string; rows?:number; placeholder?:string; required?:boolean}) {
  return <label className="iu-fas-field iu-fas-field--wide"><span>{label}{required ? <b>*</b> : null}</span><textarea name={name} rows={rows} defaultValue={defaultValue} placeholder={placeholder} required={required}/></label>
}

function getValue(data: FascicoloFormData, key: string): string {
  const value = data.fascicolo?.[key]
  return value === undefined || value === null ? '' : String(value)
}

function getBoolValue(data: FascicoloFormData, key: string): boolean {
  const value = data.fascicolo?.[key]
  return value === true || value === 'true' || value === '1' || value === 1
}

function StatoPraticaField({ data }:{data:FascicoloFormData}) {
  const current = getValue(data, 'statoPraticaOperativa') || (getValue(data, 'statusRaw') === 'ARCHIVIATO' ? 'archiviata' : 'aperta')
  return (
    <SelectField
      label={NUOVO_FASCICOLO_LABELS.fields.statoPratica}
      name="stato_pratica_operativa"
      options={STATI_PRATICA.map((stato) => ({ value: stato.value, label: stato.label }))}
      defaultValue={current}
    />
  )
}

function compactMeta(parts: Array<string | undefined>): string {
  return parts.map((part) => String(part || '').trim()).filter(Boolean).join(' - ')
}

function ClientChoiceField({ data }:{data:FascicoloFormData}) {
  const initialClientId = getValue(data, 'clientId') || data.query.id_cliente || ''
  const [clientId, setClientId] = useState(initialClientId)
  useEffect(() => setClientId(initialClientId), [initialClientId])
  const selected = data.clients.find((client) => client.id === clientId)
  return (
    <div className="iu-fas-field iu-fas-field--wide iu-fas-choice-field">
      <label>
        <span>Cliente</span>
        <select name="id_cliente" value={clientId} onChange={(event) => setClientId(event.currentTarget.value)}>
          <option value="">Seleziona cliente</option>
          {data.clients.map((client) => (
            <option value={client.id} key={client.id}>
              {compactMeta([client.label, client.taxCode || client.vat, client.pec || client.email])}
            </option>
          ))}
        </select>
      </label>
      {selected ? (
        <div className="iu-fas-choice-card">
          <Building2 size={17}/>
          <div>
            <strong>{selected.label}</strong>
            <span>{compactMeta([selected.taxCode || selected.vat, selected.pec || selected.email, selected.phone]) || 'Scheda cliente collegata.'}</span>
          </div>
          {selected.href ? <a href={selected.href}>Apri scheda</a> : null}
        </div>
      ) : (
        <div className="iu-fas-choice-card iu-fas-choice-card--empty">
          <UserRound size={17}/>
          <div>
            <strong>Nessun cliente selezionato</strong>
            <span>Puoi collegarlo ora o creare la scheda in un secondo momento.</span>
          </div>
          <a href="/clienti/nuovo" target="_blank" rel="noreferrer">Nuovo cliente</a>
        </div>
      )}
    </div>
  )
}

function CounterpartyFields({ data, required }:{data:FascicoloFormData; required:boolean}) {
  const initialName = getValue(data, 'counterparty')
  const initialCode = getValue(data, 'counterpartyTaxCode') || getValue(data, 'cf_controparte')
  const [selectedId, setSelectedId] = useState('')
  const [counterpartyName, setCounterpartyName] = useState(initialName)
  const [counterpartyCode, setCounterpartyCode] = useState(initialCode)
  const [createSubject, setCreateSubject] = useState(false)
  const [subjectType, setSubjectType] = useState('PERSONA_GIURIDICA')
  useEffect(() => {
    setCounterpartyName(initialName)
    setCounterpartyCode(initialCode)
  }, [initialName, initialCode])
  const selected = data.subjects.find((subject) => subject.id === selectedId)
  const handleSubjectChange = (value: string) => {
    setSelectedId(value)
    const subject = data.subjects.find((item) => item.id === value)
    if (subject) {
      setCounterpartyName(subject.label)
      setCounterpartyCode(subject.taxCode || subject.vat)
    }
  }
  return (
    <>
      <div className="iu-fas-field iu-fas-field--wide iu-fas-choice-field">
        <label>
          <span>Soggetto controparte già censito</span>
          <select name="id_soggetto_controparte" value={selectedId} onChange={(event) => handleSubjectChange(event.currentTarget.value)}>
            <option value="">Cerca tra i soggetti</option>
            {data.subjects.map((subject) => (
              <option value={subject.id} key={subject.id}>
                {compactMeta([subject.label, subject.taxCode || subject.vat, subject.pec || subject.email])}
              </option>
            ))}
          </select>
        </label>
        {selected ? (
          <div className="iu-fas-choice-card">
            <UsersRound size={17}/>
            <div>
              <strong>{selected.label}</strong>
              <span>{compactMeta([selected.taxCode || selected.vat, selected.qualification, selected.pec || selected.email])}</span>
            </div>
            {selected.href ? <a href={selected.href}>Apri soggetto</a> : null}
          </div>
        ) : <small className="iu-fas-field-help">Se il soggetto esiste già, selezionalo: nome e identificativo vengono riportati nel fascicolo.</small>}
      </div>
      <Field label="Controparte" name="controparte" required={required}>
        <input name="controparte" value={counterpartyName} onChange={(event) => setCounterpartyName(event.currentTarget.value)} required={required} placeholder="Nome o ragione sociale della controparte"/>
      </Field>
      <Field label="Codice fiscale / P. IVA controparte" name="cf_controparte" required={required}>
        <input name="cf_controparte" value={counterpartyCode} onChange={(event) => setCounterpartyCode(event.currentTarget.value)} required={required} placeholder="Dato necessario per la scheda soggetto"/>
      </Field>
      <Field label={NUOVO_FASCICOLO_LABELS.fields.attorePrincipale} name="attore_principale" defaultValue={getValue(data, 'attorePrincipale')}/>
      <label className="iu-fas-check-field iu-fas-check-field--wide">
        <input type="checkbox" name="crea_soggetto_controparte" value="1" checked={createSubject} onChange={(event) => setCreateSubject(event.currentTarget.checked)}/>
        <span>Crea anche la scheda soggetto della controparte</span>
        <small>Utile quando la controparte non è ancora in anagrafica. Nome e identificativo restano obbligatori.</small>
      </label>
      {createSubject ? (
        <div className="iu-fas-inline-subject iu-fas-field--wide">
          <Field label="Tipo soggetto" name="nuovo_soggetto_tipo" required>
            <select name="nuovo_soggetto_tipo" value={subjectType} onChange={(event) => setSubjectType(event.currentTarget.value)} required>
              <option value="PERSONA_FISICA">Persona fisica</option>
              <option value="PERSONA_GIURIDICA">Persona giuridica</option>
              <option value="ENTE">Ente</option>
              <option value="PUBBLICA_AMMINISTRAZIONE">Pubblica amministrazione</option>
              <option value="CONDOMINIO">Condominio</option>
            </select>
          </Field>
          <Field label="Nome completo / ragione sociale" name="nuovo_soggetto_nome_completo" required placeholder="Dato obbligatorio"/>
          <Field label="Codice fiscale / P. IVA" name="nuovo_soggetto_identificativo" required placeholder="Dato obbligatorio"/>
          <Field label="Email" name="nuovo_soggetto_email" type="email"/>
          <Field label="PEC" name="nuovo_soggetto_pec" type="email"/>
          <Field label="Telefono" name="nuovo_soggetto_telefono"/>
        </div>
      ) : null}
    </>
  )
}

function JudicialOfficeField({ data, required }:{data:FascicoloFormData; required:boolean}) {
  const initial = getValue(data, 'court') || getValue(data, 'tribunale') || data.query.ufficio_competente || ''
  const initialComune = data.query.comune_competenza || ''
  const [officeName, setOfficeName] = useState(initial)
  const [competenceComune, setCompetenceComune] = useState(initialComune)
  const [selectedComune, setSelectedComune] = useState<ComuneOption | null>(null)
  const [comuneOptions, setComuneOptions] = useState<ComuneOption[]>([])
  const [comuneLoading, setComuneLoading] = useState(false)
  const [officeKind, setOfficeKind] = useState('')
  const [includeSpeciali, setIncludeSpeciali] = useState(false)
  const [lookupLoading, setLookupLoading] = useState(false)
  const [lookupError, setLookupError] = useState('')
  const [lookupResult, setLookupResult] = useState<StudioRuntimeResult | null>(null)
  const [selectedOfficialOffice, setSelectedOfficialOffice] = useState<StudioRuntimeOffice | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  useEffect(() => setOfficeName(initial), [initial])
  useEffect(() => setCompetenceComune(initialComune), [initialComune])
  useEffect(() => {
    const query = competenceComune.trim()
    if (query.length < 2 || comuneOptionMatches(selectedComune, query)) {
      setComuneOptions([])
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setComuneLoading(true)
      fetch(`/api/v1/ui/territorio/comuni?q=${encodeURIComponent(query)}&limit=8`, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      })
        .then((response) => response.ok ? response.json() : { items: [] })
        .then((payload) => {
          if (!active) return
          const items = Array.isArray(payload.items) ? payload.items : []
          setComuneOptions(items.map(comuneOptionFromPayload).filter((item: ComuneOption | null): item is ComuneOption => Boolean(item)))
        })
        .catch(() => {
          if (active) setComuneOptions([])
        })
        .finally(() => {
          if (active) setComuneLoading(false)
        })
    }, 220)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [competenceComune, selectedComune])
  useEffect(() => {
    const query = competenceComune.trim()
    if (query.length < 2) {
      setLookupResult(null)
      setLookupError('')
      setLookupLoading(false)
      return
    }
    let active = true
    const timer = window.setTimeout(() => {
      setLookupLoading(true)
      setLookupError('')
      const body = new FormData()
      body.set('comune', query)
      if (comuneOptionMatches(selectedComune, query) && selectedComune?.codiceIstat) {
        body.set('comune_istat', selectedComune.codiceIstat)
      }
      if (includeSpeciali) body.set('includi_speciali', '1')
      if (officeKind) body.append('tipo_ufficio', officeKind)
      const token = csrfToken()
      fetch('/api/v1/ui/strumenti-legali/uffici_competenti', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body,
      })
        .then(async (response) => {
          const result = normaliseStudioRuntimeResult(await response.json().catch(() => ({})))
          if (!response.ok || !result.ok) {
            throw new Error(result.message || 'Ricerca uffici non riuscita.')
          }
          return result
        })
        .then((result) => {
          if (!active) return
          setLookupResult(result)
          setLookupError(result.offices.length ? '' : 'Nessun ufficio trovato con il filtro selezionato.')
        })
        .catch((requestError) => {
          if (!active) return
          setLookupResult(null)
          setLookupError(requestError instanceof Error ? requestError.message : 'Ricerca uffici non riuscita.')
        })
        .finally(() => {
          if (active) setLookupLoading(false)
        })
    }, 360)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [competenceComune, selectedComune, officeKind, includeSpeciali, refreshTick])
  const selected = data.judicialOffices.find((office) => office.value.toLocaleLowerCase() === officeName.toLocaleLowerCase())
  const selectedOfficeCode = selectedOfficialOffice ? officeDepositoCode(selectedOfficialOffice) : selected?.code || ''
  const selectedPstCode = selectedOfficialOffice ? selectedOfficialOffice.codiceMinistero : selected?.ministerialCode || ''
  const selectedRequiresTelematicCheck = Boolean(
    selectedOfficialOffice && !selectedOfficialOffice.codice && !selectedOfficialOffice.codiceMinistero,
  )
  const selectedHeaderMeta = selectedOfficialOffice
    ? officeCodeMeta(selectedOfficialOffice)
    : compactMeta([
        selectedOfficeCode || selectedPstCode ? 'deposito telematico verificato' : '',
      ])
  const applyOffice = (office: StudioRuntimeOffice) => {
    setOfficeName(office.name)
    setSelectedOfficialOffice(office)
  }
  const chooseComune = (option: ComuneOption) => {
    setSelectedComune(option)
    setCompetenceComune(option.label || option.nome)
    setComuneOptions([])
  }
  return (
    <div className="iu-fas-field iu-fas-field--wide iu-fas-office-field">
      <label>
        <span>{NUOVO_FASCICOLO_LABELS.fields.autoritaGiudiziaria}{required ? <b>*</b> : null}</span>
        <input
          list="fascicolo-uffici-giudiziari"
          name="tribunale"
          value={officeName}
          onChange={(event) => {
            setOfficeName(event.currentTarget.value)
            setSelectedOfficialOffice(null)
          }}
          required={required}
          placeholder="Cerca tribunale, corte, giudice di pace, TAR..."
        />
      </label>
      <input type="hidden" name="codice_ufficio_autorita" value={selectedOfficeCode}/>
      <input type="hidden" name="codice_ministero_autorita" value={selectedPstCode}/>
      <input type="hidden" name="codice_gl_autorita" value={selectedOfficialOffice?.codiceGiustiziaLocale || ''}/>
      <input type="hidden" name="codice_istat_sede_autorita" value={selectedOfficialOffice?.istatCode || ''}/>
      <input type="hidden" name="comune_competenza" value={competenceComune}/>
      <input type="hidden" name="tipo_ufficio_autorita" value={selectedOfficialOffice?.kind || ''}/>
      <input type="hidden" name="pec_ufficio_autorita" value={selectedOfficialOffice?.pec || selected?.pec || ''}/>
      <datalist id="fascicolo-uffici-giudiziari">
        {data.judicialOffices.map((office) => <option value={office.value} label={office.label} key={`${office.code}-${office.value}`}/>)}
      </datalist>
      {selectedOfficialOffice ? (
        <div className="iu-fas-choice-card">
          <Landmark size={17}/>
          <div>
            <strong>{selectedOfficialOffice.name}</strong>
            <span>{compactMeta([selectedOfficialOffice.typeLabel, selectedOfficialOffice.city, selectedOfficialOffice.pec, officeCodeMeta(selectedOfficialOffice)]) || 'Ufficio applicato dalla competenza territoriale.'}</span>
            {selectedRequiresTelematicCheck ? (
              <em>Fonte territoriale verificata; prima del deposito conferma il canale sul portale ufficiale.</em>
            ) : null}
          </div>
        </div>
      ) : selected ? (
        <div className="iu-fas-choice-card">
          <Landmark size={17}/>
          <div>
            <strong>{selected.value}</strong>
            <span>{compactMeta([selected.kind, selected.district, selected.pec]) || 'Ufficio presente nel registro.'}</span>
          </div>
        </div>
      ) : <small className="iu-fas-field-help">Gli uffici arrivano dal registro giudiziario IUSENTRA. Per il fascicolo veloce scegli una voce dell'elenco.</small>}
      <section className="iu-fas-office-competence" aria-label="Uffici giudiziari per Comune">
        <header>
          <div>
            <span><MapPin size={15}/> Competenza territoriale</span>
            <strong>Uffici giudiziari per Comune</strong>
          </div>
          {selectedHeaderMeta ? <em>{selectedHeaderMeta}</em> : null}
        </header>
        <div className="iu-fas-office-competence__controls">
          <label className="iu-fas-office-comune-field">
            <span>Comune</span>
            <input
              value={competenceComune}
              onChange={(event) => {
                setCompetenceComune(event.currentTarget.value)
                if (!comuneOptionMatches(selectedComune, event.currentTarget.value)) setSelectedComune(null)
              }}
              placeholder="Esempio: Taurianova"
              autoComplete="off"
            />
            {comuneLoading ? <small>Ricerca Comune...</small> : null}
            {comuneOptions.length ? (
              <div className="iu-fas-comune-suggestions" role="listbox" aria-label="Comuni trovati">
                {comuneOptions.map((option) => (
                  <button type="button" onClick={() => chooseComune(option)} key={option.codiceIstat}>
                    <strong>{option.label}</strong>
                    <span>{compactMeta([option.provincia, option.cap.slice(0, 2).join(', ')])}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </label>
          <div className="iu-fas-office-kind-filter" role="group" aria-label="Filtra per tipo ufficio">
            {FASCICOLO_OFFICE_KIND_FILTERS.map((option) => (
              <button
                type="button"
                className={officeKind === option.value ? 'is-active' : ''}
                onClick={() => setOfficeKind(option.value)}
                key={option.value || 'tutti'}
              >
                {option.label}
              </button>
            ))}
          </div>
          <label className="iu-fas-office-check">
            <input type="checkbox" checked={includeSpeciali} onChange={(event) => setIncludeSpeciali(event.currentTarget.checked)}/>
            <span>Anche uffici distrettuali e speciali</span>
          </label>
          <button className="iu-fas-office-refresh" type="button" onClick={() => setRefreshTick((value) => value + 1)} disabled={competenceComune.trim().length < 2 || lookupLoading}>
            <Search size={15}/>{lookupLoading ? 'Verifica...' : 'Aggiorna'}
          </button>
        </div>
        {lookupError ? <p className="iu-fas-office-error">{lookupError}</p> : null}
        {lookupResult ? (
          <div className="iu-fas-office-picker-results" aria-live="polite">
            <div className="iu-fas-office-picker-results__summary">
              <strong>{lookupResult.metrics.find((metric) => metric.label === 'Comune')?.value || competenceComune}</strong>
              <span>{lookupResult.offices.length} uffici visualizzati</span>
            </div>
            {lookupResult.offices.map((office) => {
              const isCurrent = office.name.toLocaleLowerCase() === officeName.toLocaleLowerCase()
              return (
                <article className={`iu-fas-office-pick-card ${isCurrent ? 'is-selected' : ''}`} key={office.id}>
                  <div>
                    <span><Landmark size={14}/>{office.typeLabel}</span>
                    <strong>{office.name}</strong>
                    <small>{compactMeta([office.city, office.pec, officeCodeMeta(office)]) || 'Ufficio presente nella fonte territoriale.'}</small>
                  </div>
                  <button type="button" onClick={() => applyOffice(office)}>
                    <CheckCircle2 size={15}/>{isCurrent ? 'Applicato' : 'Usa nel fascicolo'}
                  </button>
                </article>
              )
            })}
            {lookupResult.warnings.length ? <p className="iu-fas-office-warning">{lookupResult.warnings[0]}</p> : null}
          </div>
        ) : competenceComune.trim().length >= 2 && lookupLoading ? (
          <p className="iu-fas-field-help">Verifica degli uffici competenti in corso...</p>
        ) : (
          <small className="iu-fas-field-help">Scrivi il Comune per ricevere gli uffici territorialmente competenti e applicare quello corretto al fascicolo.</small>
        )}
      </section>
    </div>
  )
}

function PraticheCollegateField({ data }:{data:FascicoloFormData}) {
  const initialCode = getValue(data, 'codiceOggettoPst')
  const [selectedCode, setSelectedCode] = useState(initialCode)
  useEffect(() => setSelectedCode(initialCode), [initialCode])
  const selected = findPraticaCollegata(selectedCode)
  const currentProcedure = selected?.label || getValue(data, 'procedureType')
  const currentArea = selected?.area || getValue(data, 'practiceArea')
  const source = codiceOggettoPstSource(selectedCode)
  return (
    <div className="iu-fas-field iu-fas-field--wide iu-fas-catalog-field">
      <CodiceOggettoPstSearch
        name="codice_oggetto_pst"
        id="pratiche-collegate"
        label={NUOVO_FASCICOLO_LABELS.fields.praticheCollegate}
        value={selectedCode}
        help="Scegli dall’elenco ufficiale. La scelta resta modificabile finché non viene generata o inviata la busta."
        onChange={(codice) => setSelectedCode(codice)}
      />
      <input type="hidden" name="tipo_procedimento" value={currentProcedure}/>
      <input type="hidden" name="area_pratica" value={currentArea}/>
      <input type="hidden" name="fonte_codice_oggetto" value={selectedCode ? source.fonteCodiceOggetto : ''}/>
      <input type="hidden" name="file_fonte_codice_oggetto" value={selectedCode ? source.fileFonteCodiceOggetto : ''}/>
      <small id="pratiche-collegate-help" className="iu-fas-field-help">
        La scelta viene conservata nel fascicolo e sarà usata nei passaggi di deposito quando il flusso lo richiede.
      </small>
    </div>
  )
}

function FascicoloGuardrailsPanel({ guardrails }: { guardrails?: FascicoloFormData['guardrails'] }) {
  if (!guardrails?.available) return null
  const modeLabel = guardrails.mode === 'opening' ? 'apertura fascicolo' : 'controllo pratica'
  const panelTitle = guardrails.title?.toLowerCase().includes('guardrail')
    ? 'Presidio apertura fascicolo'
    : guardrails.title || 'Presidio apertura fascicolo'
  return (
    <CollapsibleFormPanel title={panelTitle} subtitle={`${guardrails.channelLabel} - ${modeLabel}`} icon={<ShieldCheck size={17}/>}>
      <div className="iu-fas-checklist iu-fas-guardrails">
        <span><CheckCircle2 size={16}/> Il fascicolo resta il centro operativo. La Guida Pratica legge questi dati solo se decidi di usarla.</span>
        <span><Landmark size={16}/> Codice pratica: <strong>{guardrails.channelLabel}</strong></span>
        {guardrails.requiredOpeningFields.length ? <span><ClipboardCheck size={16}/> Campi minimi apertura: {guardrails.requiredOpeningFields.join(', ')}</span> : null}
        {guardrails.blocking.map((issue) => <span key={issue.code || issue.message} className="iu-fas-issue iu-fas-issue--block"><ShieldCheck size={16}/> {issue.message}</span>)}
        {guardrails.warnings.map((issue) => <span key={issue.code || issue.message} className="iu-fas-issue iu-fas-issue--warning"><Bell size={16}/> {issue.message}</span>)}
        {guardrails.nextStep?.href ? <a className="iu-fas-inline-link" href={guardrails.nextStep.href}>{guardrails.nextStep.label || 'Apri fascicolo'}</a> : null}
      </div>
    </CollapsibleFormPanel>
  )
}

function FascicoloVeloceUploadSections({ enabled }:{enabled:boolean}) {
  if (!enabled) return null
  return (
    <>
      <CollapsibleFormPanel title="Documenti iniziali" subtitle="Multicaricamento degli atti e degli allegati da inserire subito nel fascicolo" icon={<UploadCloud size={17}/>} className="iu-fas-form-panel--quick">
        <div className="iu-fas-upload-zone">
          <label htmlFor="documenti-fascicolo-veloce">
            <span><FileText size={16}/> Documenti del fascicolo</span>
            <input
              id="documenti-fascicolo-veloce"
              type="file"
              name="documenti_fascicolo"
              multiple
              accept=".pdf,.pdfa,.p7m,.doc,.docx,.odt,.rtf,.txt,.jpg,.jpeg,.png,.tif,.tiff,.xml,.zip,.rar,.7z"
            />
          </label>
          <small>Alla creazione saranno archiviati nella sezione documenti del fascicolo con origine apertura rapida.</small>
        </div>
      </CollapsibleFormPanel>
      <CollapsibleFormPanel title="Email da conservare" subtitle="Multicaricamento dei messaggi EML da collegare al fascicolo" icon={<Mail size={17}/>} className="iu-fas-form-panel--quick">
        <div className="iu-fas-upload-zone">
          <label htmlFor="email-fascicolo-veloce">
            <span><Mail size={16}/> Email in formato EML</span>
            <input
              id="email-fascicolo-veloce"
              type="file"
              name="email_fascicolo"
              multiple
              accept=".eml,message/rfc822"
            />
          </label>
          <small>Sono accettati solo file EML, utili per PEC, ricevute e comunicazioni da conservare nel fascicolo.</small>
        </div>
      </CollapsibleFormPanel>
    </>
  )
}

function FascicoloFormPage({ mode, id }:{mode:'new'|'edit'; id?:string}) {
  const [data, setData] = useState<FascicoloFormData>(emptyFascicoloForm)
  const [loading, setLoading] = useState(true)
  const [fascicoloVeloce, setFascicoloVeloce] = useState(false)
  useEffect(() => { let active = true; getFascicoloForm(mode === 'edit' ? id : undefined, window.location.search).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [id, mode])
  const labels = NUOVO_FASCICOLO_LABELS
  return (
    <main className="iu-content iu-fascicoli-page iu-fascicolo-form-page">
      <section className="iu-fas-hero">
        <div><span className="iu-fas-eyebrow">{mode === 'edit' ? <Edit3 size={16}/> : <FolderPlus size={16}/>} {mode === 'edit' ? 'Modifica fascicolo' : labels.title}</span><h1>{mode === 'edit' ? getValue(data, 'title') || 'Modifica fascicolo' : labels.title}</h1><p>{mode === 'edit' ? 'Aggiorna dati principali, procedimento e annotazioni operative.' : labels.subtitle}</p></div>
        <div className="iu-fas-hero__actions"><Button href={data.detailHref || data.backHref}><ArrowLeft size={15}/> {mode === 'edit' ? 'Fascicolo' : 'Fascicoli'}</Button></div>
      </section>
      {loading ? <p className="iu-empty">Caricamento dati fascicolo...</p> : null}
      {data.correction?.active ? <section className="iu-fas-correction"><Badge tone="primary">Correzione</Badge><div><strong>{data.correction.title}</strong><span>{data.correction.help}</span></div></section> : null}
      {!loading ? <section className="iu-fas-form-layout">
        <JsonPostForm key={`${mode}-${id || 'new'}-${data.generatedAt || getValue(data, 'id') || 'ready'}`} className="iu-fas-form" action={data.action || (mode === 'edit' && id ? `/fascicoli/${encodeURIComponent(id)}/modifica` : '/fascicoli/nuovo')} redirectTo={data.detailHref || data.backHref} encType="multipart/form-data">
          {mode === 'new' ? <><input type="hidden" name="source_preventivo" value={data.query.source_preventivo || ''}/><input type="hidden" name="source_conferimento" value={data.query.source_conferimento || ''}/><input type="hidden" name="from_page" value={data.query.from_page || ''}/></> : null}
          <CollapsibleFormPanel title={labels.sections.datiGenerali} subtitle="Pratica, oggetto, stato e date principali" icon={<FolderOpen size={17}/>}>
            <div className="iu-fas-form-grid">
              <Field label={labels.fields.pratica} name="titolo" defaultValue={getValue(data, 'title')} required placeholder="es. Rossi c/ Bianchi - Inadempimento contrattuale"/>
              <Field label={labels.fields.rifCartaceo} name="riferimento_cartaceo" defaultValue={getValue(data, 'riferimentoCartaceo')}/>
              <SelectField label="Tipo fascicolo" name="tipo" options={data.types} defaultValue={getValue(data, 'typeRaw') || getValue(data, 'type').toUpperCase()} required/>
              <StatoPraticaField data={data}/>
              <Field label={labels.fields.dataApertura} name="data_apertura" type="date" defaultValue={getValue(data, 'dataAperturaIso') || new Date().toISOString().slice(0, 10)}/>
              <Field label={labels.fields.dataArchiviazione} name="data_chiusura" type="date" defaultValue={getValue(data, 'dataChiusuraIso')}/>
              <TextAreaField label={labels.fields.oggettoPratica} name="oggetto" defaultValue={getValue(data, 'object') || getValue(data, 'subtitle')} rows={2} required={fascicoloVeloce}/>
              <label className="iu-fas-check-field"><input type="checkbox" name="personalizzabile" value="1" defaultChecked={getBoolValue(data, 'personalizzabile')}/><span>{labels.fields.personalizzabile}</span></label>
              <PraticheCollegateField data={data}/>
              {mode === 'new' ? (
                <label className="iu-fas-check-field iu-fas-check-field--wide" htmlFor="fascicolo-veloce">
                  <input id="fascicolo-veloce" type="checkbox" name="fascicolo_veloce" value="1" checked={fascicoloVeloce} onChange={(event) => setFascicoloVeloce(event.currentTarget.checked)} aria-controls="documenti-fascicolo-veloce email-fascicolo-veloce"/>
                  <span>Fascicolo Veloce</span>
                  <small>Attiva caricamento iniziale di documenti ed email e, se serve, apre il controllo deposito assistito separato dalla Guida Pratica.</small>
                </label>
              ) : null}
            </div>
          </CollapsibleFormPanel>
          <CollapsibleFormPanel title="Parti" subtitle="Cliente, controparte e attore principale" icon={<UsersRound size={17}/>}>
            <div className="iu-fas-form-grid">
              <ClientChoiceField data={data}/>
              <CounterpartyFields data={data} required={fascicoloVeloce}/>
              <a className="iu-fas-inline-link" href="/soggetti/nuovo" target="_blank" rel="noreferrer"><Plus size={14}/> Nuovo soggetto</a>
            </div>
          </CollapsibleFormPanel>
          <CollapsibleFormPanel title={labels.sections.identificazioneGiudiziale} subtitle="Autorità, numero di ruolo e riferimenti dell'ufficio" icon={<Landmark size={17}/>}>
            <div className="iu-fas-form-grid">
              <JudicialOfficeField data={data} required={fascicoloVeloce}/>
              <Field label={labels.fields.numeroRuolo} name="numero_rg" defaultValue={getValue(data, 'numeroRg')}/>
              <Field label="Anno iscrizione" name="anno_rg" type="number" defaultValue={getValue(data, 'annoRg') || new Date().getFullYear()}/>
              <Field label="Sezione" name="sezione" defaultValue={getValue(data, 'section')}/>
              <Field label={labels.fields.istruttorePmGip} name="istruttore_pm_gip" defaultValue={getValue(data, 'istruttorePmGip') || getValue(data, 'judge')}/>
              <Field label={labels.fields.cancelliere} name="cancelliere" defaultValue={getValue(data, 'cancelliere')}/>
              <Field label={labels.fields.ctu} name="ctu" defaultValue={getValue(data, 'ctu')}/>
              <Field label={labels.fields.ctp} name="ctp" defaultValue={getValue(data, 'ctp')}/>
              <Field label="Valore causa (€)" name="valore_causa" type="number" defaultValue={getValue(data, 'valueRaw') || getValue(data, 'value')} placeholder="0,00" step="0.01" min="0" inputMode="decimal"/>
              <Field label="Compenso pattuito (€)" name="compenso_pattuito" type="number" defaultValue={getValue(data, 'agreedFeeRaw') || getValue(data, 'agreedFee')} readOnly={Boolean(getValue(data, 'agreedFee'))} step="0.01" min="0" inputMode="decimal"/>
              <Field label="Valore preventivato (€)" name="valore_preventivato" type="number" defaultValue={getValue(data, 'quotedValueRaw') || getValue(data, 'quotedValue')} readOnly={Boolean(getValue(data, 'quotedValue'))} step="0.01" min="0" inputMode="decimal"/>
              <input type="hidden" name="id_pratica" value={getValue(data, 'practiceId')}/>
              <input type="hidden" name="procedura_operativa_codice" value={getValue(data, 'proceduraOperativaCodice')}/>
              <Field label="Data prima udienza / comparizione" name="data_prima_udienza" type="date" defaultValue={getValue(data, 'firstHearingIso') || getValue(data, 'firstHearing')}/>
              <Field label="Data notificazione citazione" name="data_notifica_citazione" type="date" defaultValue={getValue(data, 'citationNotificationIso') || getValue(data, 'citationNotification')}/>
            </div>
          </CollapsibleFormPanel>
          <CollapsibleFormPanel title={labels.sections.annotazioni} subtitle="Referente, dominus e note operative" icon={<BriefcaseBusiness size={17}/>}>
            <div className="iu-fas-form-grid"><Field label="Avvocato referente" name="avvocato_referente" defaultValue={getValue(data, 'leadLawyer')}/><Field label="Avvocato dominus" name="avvocato_dominus" defaultValue={getValue(data, 'dominus')}/><TextAreaField label={labels.fields.annotazioni} name="note" defaultValue={getValue(data, 'notes')} rows={4}/></div>
          </CollapsibleFormPanel>
          {mode === 'new' ? <FascicoloVeloceUploadSections enabled={fascicoloVeloce}/> : null}
          <div className="iu-fas-form-actions"><button className="iu-fas-submit" type="submit"><CheckCircle2 size={16}/> {mode === 'edit' ? 'Salva modifiche' : 'Crea fascicolo'}</button><a href={data.detailHref || data.backHref}>Annulla</a></div>
        </JsonPostForm>
        <aside className="iu-fas-form-side">
          <FascicoloGuardrailsPanel guardrails={data.guardrails} />
          {data.workflow ? <CollapsibleFormPanel title="Apertura pratica guidata" icon={<Sparkles size={17}/>}><div className="iu-fas-workflow-box"><div>{data.workflow.badges.map((badge) => <Badge tone="primary" key={badge}>{badge}</Badge>)}</div><p>{data.workflow.summary}</p>{data.workflow.values.map((item) => <span key={item.label}><strong>{item.label}</strong>{item.value}</span>)}<ul>{data.workflow.checklist.map((item) => <li key={item}>{item}</li>)}</ul></div></CollapsibleFormPanel> : null}
          <CollapsibleFormPanel title="Contesto fascicolo" icon={<BadgeCheck size={17}/>}><div className="iu-fas-help"><p><strong>RG</strong>: numero assegnato dall'ufficio quando la pratica è iscritta.</p><p><strong>Sezione</strong>: sezione competente, utile per filtri, udienze e notifiche.</p><p><strong>Valore causa</strong>: alimenta compensi, quadro economico e controllo incassi.</p></div></CollapsibleFormPanel>
          <CollapsibleFormPanel title="Guida Pratica facoltativa" icon={<ListChecks size={17}/>}><div className="iu-fas-help"><p>Dopo il salvataggio rientri nel fascicolo. Da lì puoi aprire Guida Pratica, documenti o deposito solo quando ti serve.</p></div></CollapsibleFormPanel>
        </aside>
      </section> : null}
      <FloatingLex context="fascicolo-form" title="Lex AI fascicolo" body="Posso aiutarti a completare oggetto, tipo procedimento, checklist iniziale, scadenze e dati mancanti prima della creazione o modifica." primaryHref="#lex" primaryLabel="Apri Lex fascicolo" secondaryHref="/fascicoli" secondaryLabel="Torna ai fascicoli" />
    </main>
  )
}

function KvGrid({ items }:{items:KeyValue[]}) {
  return <div className="iu-fas-kv-grid">{items.map((item) => {
    const value = String(item.value || '')
    const sizeClass = value.length > 34 ? 'iu-fas-kv-grid__item--full' : value.length > 18 ? 'iu-fas-kv-grid__item--wide' : ''
    return <div key={`${item.label}-${item.value}`} className={sizeClass || undefined}><span>{item.label}</span>{item.href ? <a href={item.href} className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</a> : <strong className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</strong>}</div>
  })}</div>
}

function SourceSnapshotPanel({ fascicolo }:{fascicolo:FascicoloFull}) {
  const snapshot = fascicolo.sourceSnapshot
  const counts = snapshot.counts || {}
  const hasSnapshot = Boolean(snapshot.portale || snapshot.externalId || Object.values(counts).some((value) => Number(value || 0) > 0))
  if (!hasSnapshot) return null
  const items: KeyValue[] = [
    { label: 'Portale', value: snapshot.portale || fascicolo.source || 'n.d.' },
    { label: 'Riferimento', value: snapshot.externalId || fascicolo.sourceExternalId || 'n.d.', mono: true },
    { label: 'Ufficio', value: [snapshot.ufficioNome, snapshot.ufficioCodice].filter(Boolean).join(' - ') || fascicolo.court || 'n.d.' },
    { label: 'Procedimento', value: snapshot.procedimento || fascicolo.procedureType || 'n.d.' },
    { label: 'Stato portale', value: snapshot.stato || fascicolo.syncStatus || 'n.d.' },
    { label: 'Data iscrizione', value: snapshot.dataIscrizione || 'n.d.' },
    { label: 'Data udienza', value: snapshot.dataUdienza || 'n.d.' },
    { label: 'Dati letti', value: `${Number(counts.parti || 0)} parti, ${Number(counts.documenti || 0)} documenti, ${Number(counts.depositi || 0)} depositi, ${Number(counts.eventi || 0)} eventi` },
  ]
  const names = [...snapshot.parti, ...snapshot.controparti]
  return (
    <div className="iu-fas-source-panel">
      <header><Landmark size={16}/><strong>Fonte telematica acquisita</strong><span>{snapshot.acquisitoIl || fascicolo.lastSyncAt || 'ultimo allineamento registrato'}</span></header>
      <KvGrid items={items}/>
      {snapshot.oggetto ? <p>{snapshot.oggetto}</p> : null}
      {names.length ? <div className="iu-fas-source-parties">{names.map((name) => <span key={name}>{name}</span>)}</div> : null}
    </div>
  )
}

function DetailSection({
  id,
  title,
  icon,
  count,
  defaultOpen = false,
  open,
  onOpen,
  onToggle,
  children,
}:{
  id:string
  title:string
  icon:ReactNode
  count?:number
  defaultOpen?:boolean
  open?:boolean
  onOpen?:()=>void
  onToggle?:(open:boolean)=>void
  children:ReactNode
}) {
  const isControlled = typeof open === 'boolean'
  const detailsRef = useRef<HTMLDetailsElement | null>(null)
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const actualOpen = isControlled ? Boolean(open) : internalOpen
  useEffect(() => {
    if (!isControlled && defaultOpen) setInternalOpen(true)
  }, [defaultOpen, isControlled])
  useEffect(() => {
    if (detailsRef.current && detailsRef.current.open !== actualOpen) {
      detailsRef.current.open = actualOpen
    }
  }, [actualOpen])
  return (
    <details ref={detailsRef} id={id} open={actualOpen} className="iu-fas-detail-section" onToggle={(event) => {
      const nextOpen = event.currentTarget.open
      if (!isControlled) {
        setInternalOpen(nextOpen)
      } else if (nextOpen !== actualOpen && detailsRef.current) {
        window.setTimeout(() => {
          if (detailsRef.current) detailsRef.current.open = actualOpen
        }, 0)
      }
      if (nextOpen) onOpen?.()
      onToggle?.(nextOpen)
    }}>
      <summary className="iu-fas-detail-section__summary">
        <span className="iu-fas-detail-section__icon">{icon}</span>
        <span className="iu-fas-detail-section__title">{title}</span>
        {typeof count === 'number' ? <span className="iu-fas-detail-section__count">{count}</span> : null}
        <ChevronDown className="iu-fas-detail-section__chevron" size={17}/>
      </summary>
      <div className="iu-fas-detail-section__body">{children}</div>
    </details>
  )
}

type FascicoloOfficeSearchRow = {
  comune: string
  result?: StudioRuntimeResult
  error?: string
}

function splitOfficeComuneQuery(value: string): string[] {
  const seen = new Set<string>()
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => {
      const key = item.toLowerCase()
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .slice(0, 8)
}

function officeLookupDetailLabel(key: string): string {
  const labels: Record<string, string> = {
    avviso: 'Avviso',
    email: 'Email',
    fax: 'Fax',
    note: 'Note',
    orari: 'Orari',
    pec: 'PEC',
    ricevimento: 'Ricevimento',
    telefono: 'Telefono',
  }
  return labels[key] || key.replace(/_/g, ' ')
}

function FascicoloOfficeContact({ icon: Icon, label, value, onCopy }:{icon:LucideIcon; label:string; value:string; onCopy:(value:string,label:string)=>void}) {
  if (!value) return null
  return (
    <div className="iu-fas-office-contact">
      <Icon size={15}/>
      <strong>{label}</strong>
      <span>{value}</span>
      <button type="button" onClick={() => onCopy(value, label)} title={`Copia ${label}`}>
        <Copy size={14}/>
      </button>
    </div>
  )
}

function FascicoloOfficeDetailBlock({ title, details }:{title:string; details:Record<string, string>}) {
  const entries = Object.entries(details).filter(([, value]) => value)
  if (!entries.length) return null
  return (
    <section className="iu-fas-office-detail">
      <strong>{title}</strong>
      {entries.slice(0, 4).map(([key, value]) => (
        <p key={`${title}-${key}`}>
          <span>{officeLookupDetailLabel(key)}</span>
          <em>{value}</em>
        </p>
      ))}
    </section>
  )
}

function FascicoloOfficeCard({ office, onCopy }:{office:StudioRuntimeOffice; onCopy:(value:string,label:string)=>void}) {
  return (
    <article className={`iu-fas-office-card ${office.primary ? 'is-primary' : ''}`}>
      <header>
        <span><Landmark size={15}/>{office.typeLabel}</span>
        <strong>{office.name}</strong>
        <p><MapPin size={15}/>{[office.address, office.cap, office.city].filter(Boolean).join(' - ') || 'Sede non indicata'}</p>
      </header>
      <div className="iu-fas-office-card__contacts">
        <FascicoloOfficeContact icon={Phone} label="Telefono" value={office.phone} onCopy={onCopy}/>
        <FascicoloOfficeContact icon={Mail} label="Email" value={office.email} onCopy={onCopy}/>
        <FascicoloOfficeContact icon={ShieldAlert} label="PEC" value={office.pec} onCopy={onCopy}/>
        <FascicoloOfficeContact icon={Landmark} label="Sito" value={office.site} onCopy={onCopy}/>
      </div>
      <FascicoloOfficeDetailBlock title="Assistenza depositi telematici" details={office.assistenzaPct}/>
      <FascicoloOfficeDetailBlock title="Casellario" details={office.casellario}/>
      {office.notes ? <p className="iu-fas-office-note">{office.notes}</p> : null}
    </article>
  )
}

function FascicoloOfficeResultsWindow({ rows, loading }:{rows:FascicoloOfficeSearchRow[]; loading:boolean}) {
  const [copied, setCopied] = useState('')
  const copyValue = (value: string, label: string) => {
    if (!value) return
    if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(value)
    setCopied(`${label} copiato`)
    window.setTimeout(() => setCopied(''), 1600)
  }
  if (loading && !rows.length) {
    return <section className="iu-fas-office-window" aria-live="polite"><p className="iu-empty">Ricerca uffici in corso...</p></section>
  }
  if (!rows.length) {
    return <section className="iu-fas-office-window is-empty"><p className="iu-empty">Inserisci uno o più Comuni per visualizzare qui gli uffici competenti.</p></section>
  }
  return (
    <section className="iu-fas-office-window" aria-live="polite">
      <header>
        <div>
          <span><Landmark size={15}/> Risultato ricerca</span>
          <strong>{rows.length === 1 ? rows[0].comune : `${rows.length} Comuni cercati`}</strong>
        </div>
        {copied ? <em>{copied}</em> : null}
      </header>
      <div className="iu-fas-office-result-list">
        {rows.map((row) => (
          <section className="iu-fas-office-result-group" key={row.comune}>
            <div className="iu-fas-office-result-group__head">
              <strong>{row.comune}</strong>
              {row.result ? <span>{row.result.offices.length} uffici visualizzati</span> : null}
            </div>
            {row.error ? <p className="iu-fas-office-error">{row.error}</p> : null}
            {row.result?.metrics.length ? (
              <div className="iu-fas-office-metrics">
                {row.result.metrics.slice(0, 4).map((metric) => (
                  <article key={`${row.comune}-${metric.label}`}>
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                    {metric.note ? <small>{metric.note}</small> : null}
                  </article>
                ))}
              </div>
            ) : null}
            <div className="iu-fas-office-cards">
              {row.result?.offices.map((office) => <FascicoloOfficeCard office={office} onCopy={copyValue} key={`${row.comune}-${office.id}`}/>)}
            </div>
            {row.result && !row.result.offices.length ? <p className="iu-empty">Nessun ufficio trovato per il Comune indicato.</p> : null}
            {row.result?.warnings.length || row.result?.notes.length ? (
              <div className="iu-fas-office-notes">
                {[...row.result.warnings, ...row.result.notes].slice(0, 4).map((note) => <span key={`${row.comune}-${note}`}>{note}</span>)}
              </div>
            ) : null}
          </section>
        ))}
      </div>
    </section>
  )
}

function FascicoloUfficiCompetentiPanel({ fascicolo }:{fascicolo:FascicoloFull}) {
  const [query, setQuery] = useState('')
  const [includeSpeciali, setIncludeSpeciali] = useState(false)
  const [rows, setRows] = useState<FascicoloOfficeSearchRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const currentOffice = fascicolo.court
  const search = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const comuni = splitOfficeComuneQuery(query)
    if (!comuni.length) {
      setError('Inserisci almeno un Comune.')
      setRows([])
      return
    }
    setLoading(true)
    setError('')
    setRows(comuni.map((comune) => ({ comune })))
    const token = csrfToken()
    const nextRows = await Promise.all(comuni.map(async (comune): Promise<FascicoloOfficeSearchRow> => {
      const body = new FormData()
      body.set('comune', comune)
      if (includeSpeciali) body.set('includi_speciali', '1')
      try {
        const response = await fetch('/api/v1/ui/strumenti-legali/uffici_competenti', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            ...(token ? { 'X-CSRFToken': token } : {}),
          },
          body,
        })
        const result = normaliseStudioRuntimeResult(await response.json().catch(() => ({})))
        if (!response.ok || !result.ok) {
          return { comune, error: result.message || 'Ricerca non riuscita.' }
        }
        return { comune, result }
      } catch (requestError) {
        return { comune, error: requestError instanceof Error ? requestError.message : 'Ricerca non riuscita.' }
      }
    }))
    setRows(nextRows)
    setLoading(false)
  }
  return (
    <div className="iu-fas-office-lookup">
      <header>
        <div>
          <span><MapPin size={15}/> Competenza territoriale</span>
          <strong>Uffici giudiziari per Comune</strong>
          <p>La ricerca resta dentro il fascicolo e avvia la verifica solo quando la richiedi.</p>
        </div>
        <Badge tone="success">Nel fascicolo</Badge>
      </header>
      <form className="iu-fas-office-form" onSubmit={search}>
        <label>
          <span>Comuni da cercare</span>
          <textarea value={query} onChange={(event) => setQuery(event.currentTarget.value)} rows={2} placeholder="Esempio: Taurianova, Palmi"/>
        </label>
        <label className="iu-fas-office-check">
          <input type="checkbox" checked={includeSpeciali} onChange={(event) => setIncludeSpeciali(event.currentTarget.checked)}/>
          <span>Mostra anche uffici distrettuali e speciali</span>
        </label>
        <button type="submit" disabled={loading}><Search size={15}/>{loading ? 'Ricerca...' : 'Cerca uffici'}</button>
      </form>
      {currentOffice ? <p className="iu-fas-office-current"><strong>Ufficio nel fascicolo</strong><span>{currentOffice}</span></p> : null}
      {error ? <p className="iu-fas-office-error">{error}</p> : null}
      <FascicoloOfficeResultsWindow rows={rows} loading={loading}/>
    </div>
  )
}

type PreviewDocument = { name: string; url: string; downloadUrl: string; objectUrl?: string; mobileUrl?: string }
type LazySectionStatus = 'idle' | 'loading' | 'loaded' | 'error'
type EmbeddedRecordKind = 'cliente' | 'soggetti' | 'pagopa'
type EmbeddedRecordState = { kind: EmbeddedRecordKind; title: string; href: string; externalHref?: string }
type FascicoloContextMenuState = { x: number; y: number }
type ContributoUnificatoFormState = {
  cu_categoria: string
  cu_grado: string
  cu_valore_tipo: string
  cu_valore: string
  cu_anticipazione_forfettaria: string
  cu_numero_parti_ricorrenti: string
  cu_sezione_specializzata_impresa: string
  cu_dati_obbligatori_mancanti: string
}
type ContributoUnificatoResult = {
  categoria?: string
  categoria_label?: string
  grado?: string
  grado_label?: string
  valore_tipo?: string
  valore_tipo_label?: string
  valore?: number | string | null
  numero_parti_ricorrenti?: number
  base?: number | string | null
  anticipazione_forfettaria?: number | string | null
  totale?: number | string | null
  sezione_specializzata_impresa?: boolean
  dati_obbligatori_mancanti?: boolean
  regole_applicate?: Array<Record<string, unknown>>
  notes?: string[]
  warnings?: string[]
  sources?: Array<Record<string, unknown>>
}
type ContributoUnificatoMemory = {
  fascicoloId: string
  title: string
  reference: string
  objectLabel: string
  clientName: string
  totalLabel: string
  totalValue: number | null
  createdAt: string
  copyText: string
  result: ContributoUnificatoResult
}

type PagoPaPrefillOutcome = {
  status: 'idle' | 'waiting' | 'filled' | 'partial' | 'blocked'
  message: string
}

const CONTRIBUTION_MEMORY_STORAGE_PREFIX = 'iusentra.fascicolo.contributoUnificato.'
const CONTRIBUTION_CATEGORIES = [
  { value: 'civile_ordinario', label: 'Civile ordinario' },
  { value: 'decreto_ingiuntivo', label: 'Ricorso per decreto ingiuntivo' },
  { value: 'lavoro', label: 'Lavoro / pubblico impiego' },
  { value: 'processo_speciale_libro_iv', label: 'Procedimento speciale civile' },
  { value: 'volontaria_giurisdizione', label: 'Volontaria giurisdizione' },
  { value: 'separazione_consensuale', label: 'Separazione / divorzio congiunto' },
  { value: 'ricerca_beni_492bis', label: 'Ricerca beni ex art. 492-bis c.p.c.' },
  { value: 'cittadinanza_italiana', label: 'Accertamento cittadinanza italiana' },
  { value: 'esecuzione_immobiliare', label: 'Esecuzione immobiliare' },
  { value: 'altri_processi_esecutivi', label: 'Altra esecuzione' },
  { value: 'esecuzione_mobiliare_sotto_2500', label: 'Esecuzione mobiliare sotto € 2.500,00' },
  { value: 'opposizione_atti_esecutivi', label: 'Opposizione agli atti esecutivi' },
  { value: 'procedura_fallimentare', label: 'Procedura fallimentare' },
  { value: 'tributario', label: 'Ricorso tributario' },
  { value: 'amministrativo_accesso_soggiorno_cittadinanza', label: 'Accesso, soggiorno, cittadinanza e ottemperanza' },
  { value: 'amministrativo_ordinario', label: 'Ricorso amministrativo ordinario' },
  { value: 'amministrativo_rito_abbreviato', label: 'Rito abbreviato amministrativo' },
  { value: 'amministrativo_appalti', label: 'Appalti pubblici (art. 119 c.p.a.)' },
  { value: 'amministrativo_ottemperanza', label: 'Ottemperanza con contestuale risarcitoria' },
]
const CONTRIBUTION_DEGREES = [
  { value: 'primo_grado', label: 'Primo grado' },
  { value: 'appello', label: 'Appello' },
  { value: 'cassazione', label: 'Cassazione' },
]
const CONTRIBUTION_VALUE_MODES = [
  { value: 'determinato', label: 'Valore determinato' },
  { value: 'indeterminabile', label: 'Valore indeterminabile' },
  { value: 'non_indicato', label: 'Valore non indicato' },
]

function shouldUseNativeContextMenu(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false
  return Boolean(target.closest('input, textarea, select, [contenteditable="true"], .iu-fas-preview-modal, .iu-fas-document-flow-modal, .iu-fas-context-menu, .iu-fas-contributo-modal, .iu-fas-economic-control-modal'))
}

function clampFascicoloContextMenuPosition(x: number, y: number): FascicoloContextMenuState {
  if (typeof window === 'undefined') return { x, y }
  const menuWidth = 348
  const menuHeight = Math.min(620, window.innerHeight * 0.86)
  const margin = 12
  return {
    x: Math.max(margin, Math.min(x, window.innerWidth - menuWidth - margin)),
    y: Math.max(margin, Math.min(y, window.innerHeight - Math.min(menuHeight, window.innerHeight - margin * 2) - margin)),
  }
}

const emptyLazySections: Record<FascicoloDetailSection, LazySectionStatus> = {
  documenti: 'idle',
  attivita: 'idle',
  scadenze: 'idle',
  depositi: 'idle',
  regia: 'idle',
  relata: 'idle',
  audit: 'idle',
  lex: 'idle',
}

function initialDetailIncludesFromHash(): FascicoloDetailSection[] {
  if (typeof window === 'undefined') return []
  const section = lazySectionForDetailHash(currentDetailHashSectionId())
  return section ? [section] : []
}

function currentDetailHashSectionId(): string {
  if (typeof window === 'undefined') return ''
  return decodeURIComponent(window.location.hash.replace(/^#/, ''))
}

function lazySectionForDetailHash(sectionId: string): FascicoloDetailSection | undefined {
  switch (sectionId) {
    case 'documenti':
      return 'documenti'
    case 'attivita':
      return 'attivita'
    case 'udienze':
      return 'scadenze'
    case 'cancelleria':
      return 'depositi'
    case 'regia-operativa':
      return 'regia'
    case 'relata-notifica':
      return 'relata'
    case 'audit':
      return 'audit'
    default:
      return undefined
  }
}

function mobilePreviewUrl(url: string): string {
  if (!url || !url.includes('/documenti/') || !url.includes('/visualizza')) return ''
  try {
    const parsed = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost')
    parsed.searchParams.set('viewer', 'mobile')
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    const separator = url.includes('?') ? '&' : '?'
    return `${url}${separator}viewer=mobile`
  }
}

function PdfPreviewModal({ preview, onClose }:{preview:PreviewDocument | null; onClose:()=>void}) {
  useEffect(() => {
    const objectUrl = preview?.objectUrl
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [preview?.objectUrl])

  if (!preview) return null
  const mobileUrl = preview.mobileUrl || mobilePreviewUrl(preview.url)
  const viewerUrl = mobileUrl || preview.url
  return (
    <div className="iu-fas-preview-modal" role="dialog" aria-modal="true" aria-label={`Anteprima ${preview.name}`}>
      <div className="iu-fas-preview-modal__box">
        <header>
          <div className="iu-fas-preview-modal__title">
            <span><Eye size={14}/> Lettore documento</span>
            <strong>{preview.name}</strong>
          </div>
          <nav>
            <a href={preview.downloadUrl}><Download size={15}/> Scarica</a>
            <button type="button" onClick={onClose} aria-label="Chiudi anteprima">Chiudi</button>
          </nav>
        </header>
        <iframe src={viewerUrl} title={`Anteprima documento ${preview.name}`}/>
      </div>
    </div>
  )
}

function PagoPaActionButton({ onClick, variant = 'hero' }:{onClick:()=>void; variant?: 'hero' | 'side'}) {
  const className = variant === 'side'
    ? 'iu-fas-side-link iu-fas-pagopa-button iu-fas-pagopa-button--side'
    : 'iu-button iu-button--secondary iu-fas-pagopa-button'
  return (
    <button type="button" className={className} onClick={onClick} aria-label="Apri PagoPA PST nel fascicolo" title="PagoPA PST">
      <img src={PAGOPA_LOGO_URL} alt="" aria-hidden="true"/>
      <span>PagoPA</span>
    </button>
  )
}

function RecordOverlayButton({ onClick, icon, label, title }:{onClick:()=>void; icon:ReactNode; label:string; title:string}) {
  return (
    <button type="button" className="iu-button iu-button--secondary iu-fas-record-link" onClick={onClick} aria-label={title} title={title}>
      {icon}
      {label}
    </button>
  )
}

function contributionStorageKey(fascicoloId: string): string {
  return `${CONTRIBUTION_MEMORY_STORAGE_PREFIX}${fascicoloId || 'corrente'}`
}

function readContributionMemory(fascicoloId: string): ContributoUnificatoMemory | null {
  if (typeof window === 'undefined' || !fascicoloId) return null
  try {
    const raw = window.sessionStorage.getItem(contributionStorageKey(fascicoloId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as ContributoUnificatoMemory
    return parsed && parsed.fascicoloId === fascicoloId && parsed.copyText ? parsed : null
  } catch {
    return null
  }
}

function saveContributionMemory(memory: ContributoUnificatoMemory): void {
  if (typeof window === 'undefined' || !memory.fascicoloId) return
  try {
    window.sessionStorage.setItem(contributionStorageKey(memory.fascicoloId), JSON.stringify(memory))
  } catch {
    // La memoria PagoPA resta disponibile nello stato React anche se il browser blocca sessionStorage.
  }
}

function cleanDisplayText(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function contributoAmountNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const raw = String(value ?? '').trim()
  if (!raw) return null
  let normalized = raw.replace(/€/g, '').replace(/EUR/gi, '').replace(/\s+/g, '')
  if (normalized.includes(',')) normalized = normalized.replace(/\./g, '').replace(',', '.')
  normalized = normalized.replace(/[^0-9.-]/g, '')
  const parsed = Number.parseFloat(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

function fascicoloOggettoRicorso(fascicolo: FascicoloFull): string {
  const snapshot = fascicolo.sourceSnapshot
  const candidates = [
    fascicolo.object,
    snapshot?.oggetto,
    fascicolo.subtitle,
    fascicolo.procedureType,
    fascicolo.title,
  ]
  return candidates.map(cleanDisplayText).find(Boolean) || ''
}

function pagoPaAmountInput(memory: ContributoUnificatoMemory): string {
  const amount = memory.totalValue ?? contributoAmountNumber(memory.result?.totale) ?? contributoAmountNumber(memory.totalLabel)
  return amount === null ? '' : formatEuroIt(amount).replace(/^€\s*/, '')
}

function normalizePagoPaText(value: unknown): string {
  return cleanDisplayText(value)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

function controlIdentity(control: HTMLInputElement | HTMLTextAreaElement, doc: Document): string {
  const direct = [
    control.name,
    control.id,
    control.getAttribute('placeholder'),
    control.getAttribute('aria-label'),
    control.getAttribute('title'),
  ]
  const labels: string[] = []
  if (control.id) {
    try {
      doc.querySelectorAll<HTMLLabelElement>(`label[for="${control.id.replace(/"/g, '\\"')}"]`).forEach((label) => labels.push(label.textContent || ''))
    } catch {
      // Alcuni portali usano id non validi per i selettori CSS: in quel caso bastano name e placeholder.
    }
  }
  const wrapperText = control.closest('label')?.textContent || control.closest('tr')?.textContent || ''
  return normalizePagoPaText([...direct, ...labels, wrapperText].filter(Boolean).join(' '))
}

function setPagoPaControlValue(control: HTMLInputElement | HTMLTextAreaElement, value: string): boolean {
  if (!value || control.disabled || control.readOnly) return false
  const type = control instanceof HTMLInputElement ? normalizePagoPaText(control.type) : 'textarea'
  if (['button', 'checkbox', 'file', 'hidden', 'image', 'radio', 'reset', 'submit'].includes(type)) return false
  const current = cleanDisplayText(control.value)
  if (current && current !== '0' && current !== '0,00') return false
  control.focus({ preventScroll: true })
  control.value = value
  control.dispatchEvent(new Event('input', { bubbles: true }))
  control.dispatchEvent(new Event('change', { bubbles: true }))
  return true
}

function tryPrefillPagoPaFrame(iframe: HTMLIFrameElement | null, memory: ContributoUnificatoMemory | null): PagoPaPrefillOutcome {
  if (!memory) {
    return { status: 'waiting', message: 'Esegui o copia un calcolo del contributo per preparare i dati PagoPA.' }
  }
  const amount = pagoPaAmountInput(memory)
  const subject = cleanDisplayText(memory.objectLabel || memory.title)
  const reference = cleanDisplayText(memory.reference || memory.fascicoloId)
  const client = cleanDisplayText(memory.clientName)
  if (!amount && !subject && !reference && !client) {
    return { status: 'waiting', message: 'Calcolo disponibile, ma mancano dati compilabili per il portale PagoPA.' }
  }
  try {
    const doc = iframe?.contentDocument || iframe?.contentWindow?.document || null
    if (!doc) return { status: 'waiting', message: 'PagoPA è in caricamento: i dati restano in memoria.' }
    const controls = Array.from(doc.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea'))
    const filled: string[] = []
    const fill = (label: string, patterns: RegExp[], value: string) => {
      if (!value || filled.includes(label)) return
      const target = controls.find((control) => patterns.some((pattern) => pattern.test(controlIdentity(control, doc))))
      if (target && setPagoPaControlValue(target, value)) filled.push(label)
    }
    fill('importo', [/\b(importo|totale|ammontare|somma|euro)\b/], amount)
    fill('oggetto', [/\b(oggetto|causale|descrizione|note|annotazioni)\b/], subject)
    fill('riferimento', [/\b(riferimento|rg|r\.g\.|ruolo|procedimento|fascicolo)\b/], reference)
    fill('cliente', [/\b(cliente|debitore|versante|contribuente|soggetto|nominativo|nome)\b/], client)
    if (filled.length >= 2) {
      return { status: 'filled', message: `Dati inseriti nei campi PagoPA visibili: ${filled.join(', ')}.` }
    }
    if (filled.length === 1) {
      return { status: 'partial', message: `Inserito ${filled[0]}; gli altri dati restano copiabili dal riepilogo.` }
    }
    return { status: 'waiting', message: 'Nuovo pagamento aperto. Il riepilogo resta pronto se il portale non espone campi compilabili in questa schermata.' }
  } catch {
    return { status: 'blocked', message: 'PagoPA ha isolato la pagina: il calcolo resta disponibile per copia manuale.' }
  }
}

async function copyTextForUser(value: string): Promise<void> {
  if (!value) return
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }
  if (typeof document === 'undefined') return
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.setAttribute('readonly', 'true')
  textarea.className = 'iu-fas-clipboard-buffer'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  textarea.remove()
}

function defaultContributoUnificatoForm(fascicolo: FascicoloFull, prefill?: Record<string, unknown>): ContributoUnificatoFormState {
  const value = String(prefill?.valore_causa ?? fascicolo.valueRaw ?? fascicolo.value ?? '').trim()
  return {
    cu_categoria: 'civile_ordinario',
    cu_grado: 'primo_grado',
    cu_valore_tipo: value ? 'determinato' : 'indeterminabile',
    cu_valore: value,
    cu_anticipazione_forfettaria: '1',
    cu_numero_parti_ricorrenti: '1',
    cu_sezione_specializzata_impresa: '0',
    cu_dati_obbligatori_mancanti: '0',
  }
}

function buildContributoUnificatoCopyText({
  fascicolo,
  clientName,
  result,
}:{
  fascicolo: FascicoloFull
  clientName: string
  result: ContributoUnificatoResult
}): string {
  const notes = Array.isArray(result.notes) ? result.notes.filter(Boolean) : []
  const warnings = Array.isArray(result.warnings) ? result.warnings.filter(Boolean) : []
  const objectLabel = fascicoloOggettoRicorso(fascicolo)
  const lines = [
    'Calcolo contributo unificato',
    `Fascicolo: ${fascicolo.title || fascicolo.ref || fascicolo.id}`,
    fascicolo.ref ? `Riferimento: ${fascicolo.ref}` : '',
    clientName ? `Cliente: ${clientName}` : '',
    objectLabel ? `Oggetto del ricorso: ${objectLabel}` : '',
    `Tipologia: ${result.categoria_label || result.categoria || 'Non indicata'}`,
    `Grado: ${result.grado_label || result.grado || 'Primo grado'}`,
    `Tipo valore: ${result.valore_tipo_label || result.valore_tipo || 'Non indicato'}`,
    result.valore ? `Valore causa: ${formatEuroIt(result.valore)}` : '',
    `Contributo base: ${formatEuroIt(result.base)}`,
    `Anticipazione forfettaria: ${formatEuroIt(result.anticipazione_forfettaria)}`,
    `Totale da usare per PagoPA: ${formatEuroIt(result.totale)}`,
    notes.length ? `Note: ${notes.join(' ')}` : '',
    warnings.length ? `Avvisi: ${warnings.join(' ')}` : '',
  ].filter(Boolean)
  return lines.join('\n')
}

function buildContributoUnificatoMemory({
  fascicolo,
  clientName,
  result,
}:{
  fascicolo: FascicoloFull
  clientName: string
  result: ContributoUnificatoResult
}): ContributoUnificatoMemory {
  const copyText = buildContributoUnificatoCopyText({ fascicolo, clientName, result })
  const totalValue = contributoAmountNumber(result.totale)
  return {
    fascicoloId: fascicolo.id,
    title: fascicolo.title,
    reference: fascicolo.ref,
    objectLabel: fascicoloOggettoRicorso(fascicolo),
    clientName,
    totalLabel: formatEuroIt(result.totale),
    totalValue,
    createdAt: new Date().toISOString(),
    copyText,
    result,
  }
}

function FascicoloContextMenuItem({
  icon,
  label,
  note,
  href,
  primary = false,
  disabled = false,
  onSelect,
}:{
  icon: ReactNode
  label: string
  note: string
  href?: string
  primary?: boolean
  disabled?: boolean
  onSelect?: () => void
}) {
  const className = `iu-fas-context-menu__item${primary ? ' is-primary' : ''}`
  const content = (
    <>
      <span className="iu-fas-context-menu__icon">{icon}</span>
      <span>
        <strong>{label}</strong>
        <small>{note}</small>
      </span>
    </>
  )
  if (href && !disabled) {
    return <a className={className} href={href} role="menuitem" onClick={onSelect}>{content}</a>
  }
  return (
    <button className={className} type="button" role="menuitem" disabled={disabled} onClick={onSelect}>
      {content}
    </button>
  )
}

function FascicoloContextMenu({
  position,
  title,
  reference,
  fascicoloId,
  clientName,
  editHref,
  compilerHref,
  exportPdfHref,
  archiveZipHref,
  auditBundleHref,
  onClose,
  onDeposit,
  onClient,
  onParties,
  onOfficePortal,
  onNotification,
  onContributoUnificato,
  onPagoPa,
  onEconomicControl,
  onSection,
}:{
  position: FascicoloContextMenuState | null
  title: string
  reference: string
  fascicoloId: string
  clientName: string
  editHref: string
  compilerHref: string
  exportPdfHref: string
  archiveZipHref: string
  auditBundleHref: string
  onClose: () => void
  onDeposit: () => void
  onClient: () => void
  onParties: () => void
  onOfficePortal: () => void
  onNotification: () => void
  onContributoUnificato: () => void
  onPagoPa: () => void
  onEconomicControl: () => void
  onSection: (sectionId: string, lazySection?: FascicoloDetailSection) => void
}) {
  const menuRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!position) return undefined
    const frame = window.requestAnimationFrame(() => {
      const firstItem = menuRef.current?.querySelector<HTMLElement>('button.iu-fas-context-menu__item:not(:disabled), a.iu-fas-context-menu__item[href]')
      firstItem?.focus({ preventScroll: true })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [position])

  if (!position) return null
  return (
    <aside
      ref={menuRef}
      className="iu-fas-context-menu"
      style={{ left: position.x, top: position.y }}
      role="menu"
      aria-label="Azioni rapide del fascicolo"
      onContextMenu={(event) => event.preventDefault()}
    >
      <header>
        <span><FolderOpen size={15}/> Azioni fascicolo</span>
        <button type="button" onClick={onClose} aria-label="Chiudi menu azioni"><X size={15}/></button>
      </header>
      <div className="iu-fas-context-menu__summary">
        <strong>{title}</strong>
        <span>{[reference, clientName].filter(Boolean).join(' · ')}</span>
      </div>

      <div className="iu-fas-context-menu__group">
        <FascicoloContextMenuItem primary icon={<Send size={16}/>} label="Deposito telematico" note="Scegli documenti, firma e prepara la busta" onSelect={onDeposit}/>
        <FascicoloContextMenuItem icon={<Bell size={16}/>} label="Notifica" note="Prepara relata, allegati e prova" onSelect={onNotification}/>
        <FascicoloContextMenuItem icon={<FolderSearch2 size={16}/>} label="Apri Portale Servizi" note="Fascicolo d’ufficio con sessione assistita" onSelect={onOfficePortal}/>
      </div>

      <div className="iu-fas-context-menu__group" aria-label="Anagrafiche">
        <span className="iu-fas-context-menu__group-title">Anagrafiche</span>
        <FascicoloContextMenuItem icon={<UserRound size={16}/>} label="Modifica anagrafica cliente" note="Apri la scheda cliente collegata" onSelect={onClient}/>
        <FascicoloContextMenuItem icon={<UsersRound size={16}/>} label="Soggetti" note="Assistiti, controparti e parti del fascicolo" onSelect={onParties}/>
        <FascicoloContextMenuItem icon={<Edit3 size={16}/>} label="Modifica" note="Dati principali e profilo del fascicolo" href={editHref} onSelect={onClose}/>
      </div>

      <div className="iu-fas-context-menu__group" aria-label="Economia e calendario">
        <span className="iu-fas-context-menu__group-title">Economia e calendario</span>
        <FascicoloContextMenuItem icon={<Calculator size={16}/>} label="Calcola contributo unificato" note="Calcolo rapido e memoria per PagoPA" onSelect={onContributoUnificato}/>
        <FascicoloContextMenuItem icon={<Euro size={16}/>} label="PagoPA" note="Contributo, ricevute e pagamenti PST" onSelect={onPagoPa}/>
        <FascicoloContextMenuItem icon={<WalletCards size={16}/>} label="Controllo economico" note="Contributo, ricevute, liquidazioni e parcella" onSelect={onEconomicControl}/>
        <FascicoloContextMenuItem icon={<CalendarDays size={16}/>} label="Nuova scadenza" note="Aggiungi un termine collegato al fascicolo" href={`/scadenziario/nuova?id_fascicolo=${encodeURIComponent(fascicoloId)}`} onSelect={onClose}/>
        <FascicoloContextMenuItem icon={<Clock3 size={16}/>} label="Nuovo appuntamento" note="Crea udienza o attività in Agenda" href={`/agenda/nuovo?id_fascicolo=${encodeURIComponent(fascicoloId)}`} onSelect={onClose}/>
      </div>

      <div className="iu-fas-context-menu__group" aria-label="Documenti e verifiche">
        <span className="iu-fas-context-menu__group-title">Documenti e verifiche</span>
        <FascicoloContextMenuItem icon={<FileText size={16}/>} label="Documenti e atti" note="Carica, visualizza, classifica e firma" onSelect={() => onSection('documenti', 'documenti')}/>
        <FascicoloContextMenuItem icon={<ClipboardCheck size={16}/>} label="Compilatore atti" note="Modelli e bozze dal fascicolo" href={compilerHref} onSelect={onClose}/>
        <FascicoloContextMenuItem icon={<FileDown size={16}/>} label="PDF fascicolo" note={exportPdfHref ? "Scarica il fascicolo in PDF" : "PDF non disponibile"} href={exportPdfHref} disabled={!exportPdfHref} onSelect={onClose}/>
        <FascicoloContextMenuItem icon={<FileArchive size={16}/>} label="Scarica ZIP" note={archiveZipHref ? "Archivio documenti del fascicolo" : "ZIP non ancora disponibile"} href={archiveZipHref} disabled={!archiveZipHref} onSelect={onClose}/>
        <FascicoloContextMenuItem icon={<Fingerprint size={16}/>} label="Audit" note={auditBundleHref ? 'Scarica bundle eventi e prove' : 'Apri eventi e prove del fascicolo'} href={auditBundleHref} onSelect={auditBundleHref ? onClose : () => onSection('audit', 'audit')}/>
      </div>
    </aside>
  )
}

function embeddedRecordIcon(kind: EmbeddedRecordKind) {
  if (kind === 'cliente') return <UserRound size={18}/>
  if (kind === 'soggetti') return <UsersRound size={18}/>
  return <img src={PAGOPA_LOGO_URL} alt="" aria-hidden="true"/>
}

function ContributoUnificatoModal({
  open,
  fascicolo,
  clientName,
  onClose,
  onMemory,
  onOpenPagoPa,
}:{
  open: boolean
  fascicolo: FascicoloFull
  clientName: string
  onClose: () => void
  onMemory: (memory: ContributoUnificatoMemory, message?: string) => void
  onOpenPagoPa: () => void
}) {
  const [form, setForm] = useState<ContributoUnificatoFormState>(() => defaultContributoUnificatoForm(fascicolo))
  const [result, setResult] = useState<ContributoUnificatoResult | null>(null)
  const [loadingPrefill, setLoadingPrefill] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return undefined
    let active = true
    setResult(null)
    setError('')
    setCopyState('idle')
    setForm(defaultContributoUnificatoForm(fascicolo))
    setLoadingPrefill(true)
    fetch(`/strumenti-legali/api/prefill/${encodeURIComponent(fascicolo.id)}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
      .then((response) => response.json())
      .then((payload) => {
        if (!active) return
        if (payload?.ok && payload.prefill && typeof payload.prefill === 'object') {
          setForm(defaultContributoUnificatoForm(fascicolo, payload.prefill as Record<string, unknown>))
        }
      })
      .catch(() => {
        if (active) setError('Precompilazione non disponibile: puoi completare i campi manualmente.')
      })
      .finally(() => {
        if (active) setLoadingPrefill(false)
      })
    return () => { active = false }
  }, [open, fascicolo.id])

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  const updateField = (field: keyof ContributoUnificatoFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setCopyState('idle')
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setCopyState('idle')
    try {
      const response = await fetch('/strumenti-legali/api/contributo-unificato', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify(form),
      })
      const payload = await response.json()
      if (!payload?.ok) throw new Error(String(payload?.errore || 'Calcolo non riuscito.'))
      const nextResult = payload.result as ContributoUnificatoResult
      setResult(nextResult)
      const memory = buildContributoUnificatoMemory({ fascicolo, clientName, result: nextResult })
      saveContributionMemory(memory)
      onMemory(memory, 'Calcolo contributo unificato salvato in memoria per PagoPA.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calcolo non riuscito.')
    } finally {
      setSubmitting(false)
    }
  }
  const copyCurrentResult = async (openPagoPa = false) => {
    if (!result) return
    const memory = buildContributoUnificatoMemory({ fascicolo, clientName, result })
    try {
      await copyTextForUser(memory.copyText)
      saveContributionMemory(memory)
      onMemory(memory, 'Calcolo copiato e pronto per PagoPA.')
      setCopyState('copied')
      if (openPagoPa) {
        onClose()
        onOpenPagoPa()
      }
    } catch {
      saveContributionMemory(memory)
      onMemory(memory, 'Calcolo salvato in memoria per PagoPA, ma la copia negli appunti è stata bloccata dal browser.')
      setCopyState('error')
      if (openPagoPa) {
        onClose()
        onOpenPagoPa()
      }
    }
  }
  const notes = Array.isArray(result?.notes) ? result?.notes || [] : []
  const warnings = Array.isArray(result?.warnings) ? result?.warnings || [] : []
  const rules = Array.isArray(result?.regole_applicate) ? result?.regole_applicate || [] : []
  return (
    <div className="iu-fas-contributo-modal" role="dialog" aria-modal="true" aria-label="Calcola contributo unificato">
      <div className="iu-fas-contributo-modal__box">
        <header>
          <div>
            <span><Calculator size={15}/> Calcolo contributo unificato</span>
            <strong>{fascicolo.title || fascicolo.ref}</strong>
          </div>
          <nav>
            <button type="button" onClick={onClose} aria-label="Chiudi calcolo contributo unificato">Chiudi</button>
          </nav>
        </header>
        <form onSubmit={submit} className="iu-fas-contributo-form">
          <label>
            <span>Tipologia</span>
            <select value={form.cu_categoria} onChange={(event) => updateField('cu_categoria', event.target.value)}>
              {CONTRIBUTION_CATEGORIES.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Grado</span>
            <select value={form.cu_grado} onChange={(event) => updateField('cu_grado', event.target.value)}>
              {CONTRIBUTION_DEGREES.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Tipo valore</span>
            <select value={form.cu_valore_tipo} onChange={(event) => updateField('cu_valore_tipo', event.target.value)}>
              {CONTRIBUTION_VALUE_MODES.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Valore causa</span>
            <input type="number" min="0" step="0.01" value={form.cu_valore} onChange={(event) => updateField('cu_valore', event.target.value)} placeholder="0,00"/>
          </label>
          <label>
            <span>Anticipazione forfettaria</span>
            <select value={form.cu_anticipazione_forfettaria} onChange={(event) => updateField('cu_anticipazione_forfettaria', event.target.value)}>
              <option value="1">Sì</option>
              <option value="0">No</option>
            </select>
          </label>
          <label>
            <span>Parti ricorrenti</span>
            <input type="number" min="1" step="1" value={form.cu_numero_parti_ricorrenti} onChange={(event) => updateField('cu_numero_parti_ricorrenti', event.target.value)}/>
          </label>
          <label>
            <span>Sezione impresa</span>
            <select value={form.cu_sezione_specializzata_impresa} onChange={(event) => updateField('cu_sezione_specializzata_impresa', event.target.value)}>
              <option value="0">No</option>
              <option value="1">Sì</option>
            </select>
          </label>
          <label>
            <span>Dati obbligatori mancanti</span>
            <select value={form.cu_dati_obbligatori_mancanti} onChange={(event) => updateField('cu_dati_obbligatori_mancanti', event.target.value)}>
              <option value="0">No</option>
              <option value="1">Sì</option>
            </select>
          </label>
          <footer>
            {loadingPrefill ? <span>Precompilazione dal fascicolo in corso...</span> : <span>Il calcolo usa il servizio interno già presente negli strumenti forensi.</span>}
            <button type="submit" disabled={submitting}>{submitting ? 'Calcolo...' : 'Calcola contributo'}</button>
          </footer>
        </form>
        {error ? <p className="iu-fas-contributo-alert is-danger"><AlertTriangle size={15}/> {error}</p> : null}
        {result ? (
          <section className="iu-fas-contributo-result" aria-label="Risultato contributo unificato">
            <div className="iu-fas-contributo-result__metrics">
              <span><small>Contributo base</small><strong>{formatEuroIt(result.base)}</strong></span>
              <span><small>Anticipazione</small><strong>{formatEuroIt(result.anticipazione_forfettaria)}</strong></span>
              <span className="is-total"><small>Totale PagoPA</small><strong>{formatEuroIt(result.totale)}</strong></span>
            </div>
            {rules.length ? (
              <div className="iu-fas-contributo-result__rules">
                {rules.map((rule, index) => <span key={`${String(rule.code || rule.label || 'regola')}-${index}`}>{String(rule.label || rule.code || 'Regola applicata')}</span>)}
              </div>
            ) : null}
            {[...notes, ...warnings].length ? (
              <ul>
                {notes.map((note, index) => <li key={`note-${index}`}>{note}</li>)}
                {warnings.map((warning, index) => <li className="is-warning" key={`warning-${index}`}>{warning}</li>)}
              </ul>
            ) : null}
            <div className="iu-fas-contributo-result__actions">
              <button type="button" onClick={() => copyCurrentResult(false)}><Copy size={15}/> Copia calcolo</button>
              <button type="button" className="is-primary" onClick={() => copyCurrentResult(true)}><Euro size={15}/> Copia e apri PagoPA</button>
              {copyState === 'copied' ? <span>Calcolo copiato negli appunti e salvato in memoria.</span> : null}
              {copyState === 'error' ? <span>Memoria salvata; gli appunti sono stati bloccati dal browser.</span> : null}
            </div>
          </section>
        ) : (
          <section className="iu-fas-contributo-empty">
            <strong>Calcolo non ancora eseguito</strong>
            <p>Inserisci valore e categoria, poi salva il risultato in memoria per usarlo durante la compilazione PagoPA.</p>
          </section>
        )}
      </div>
    </div>
  )
}

function EmbeddedRecordModal({
  record,
  contributoMemory,
  onCopyContributoMemory,
  onClose,
}:{
  record:EmbeddedRecordState | null
  contributoMemory: ContributoUnificatoMemory | null
  onCopyContributoMemory: (memory: ContributoUnificatoMemory) => void
  onClose:()=>void
}) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const [fullScreen, setFullScreen] = useState(false)
  const [prefillOutcome, setPrefillOutcome] = useState<PagoPaPrefillOutcome>({ status: 'idle', message: '' })
  const isPagoPa = record?.kind === 'pagopa'

  useEffect(() => {
    if (!record) return undefined
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [record, onClose])

  useEffect(() => {
    setFullScreen(false)
    setPrefillOutcome({ status: 'idle', message: '' })
  }, [record?.href])

  const runPagoPaPrefill = useCallback(() => {
    if (!isPagoPa) return
    setPrefillOutcome(tryPrefillPagoPaFrame(iframeRef.current, contributoMemory))
  }, [isPagoPa, contributoMemory])

  useEffect(() => {
    if (!isPagoPa || !contributoMemory) return undefined
    const timer = window.setTimeout(runPagoPaPrefill, 250)
    return () => window.clearTimeout(timer)
  }, [isPagoPa, contributoMemory, runPagoPaPrefill])

  if (!record) return null
  return (
    <div className={`iu-fas-preview-modal iu-fas-embedded-modal${isPagoPa ? ' iu-fas-embedded-modal--pagopa' : ''}${isPagoPa && contributoMemory ? ' iu-fas-embedded-modal--pagopa-memory' : ''}${isPagoPa && prefillOutcome.message ? ' iu-fas-embedded-modal--pagopa-prefill' : ''}${fullScreen ? ' iu-fas-embedded-modal--fullscreen' : ''}`} role="dialog" aria-modal="true" aria-label={record.title}>
      <div className="iu-fas-preview-modal__box">
        <header>
          <div>{embeddedRecordIcon(record.kind)}<strong>{record.title}</strong></div>
          <nav>
            {isPagoPa ? (
              <button type="button" onClick={() => setFullScreen((current) => !current)} aria-pressed={fullScreen}>
                {fullScreen ? <Minimize2 size={15}/> : <Maximize2 size={15}/>}
                {fullScreen ? 'Riduci' : 'Tutto schermo'}
              </button>
            ) : null}
            <a href={record.externalHref || record.href} target="_blank" rel="noopener noreferrer">Apri fuori</a>
            <button type="button" onClick={onClose} aria-label={`Chiudi ${record.title}`}>Chiudi</button>
          </nav>
        </header>
        <div className="iu-fas-embedded-modal__body">
          {isPagoPa ? <p className="iu-fas-pagopa-proxy-note">Nuovo pagamento PagoPA PST: importo, RG, oggetto del ricorso e cliente restano pronti qui. IUSENTRA prova a compilare i campi visibili, senza inviare nulla.</p> : null}
          {isPagoPa && contributoMemory ? (
            <section className="iu-fas-pagopa-memory" aria-label="Calcolo contributo unificato in memoria">
              <div>
                <span>Calcolo contributo in memoria</span>
                <strong>{contributoMemory.totalLabel}</strong>
                <small>{[contributoMemory.reference, contributoMemory.clientName, contributoMemory.objectLabel].filter(Boolean).join(' · ')}</small>
              </div>
              <button type="button" onClick={() => onCopyContributoMemory(contributoMemory)}><Copy size={15}/> Copia calcolo</button>
            </section>
          ) : null}
          {isPagoPa && prefillOutcome.message ? (
            <p className={`iu-fas-pagopa-prefill iu-fas-pagopa-prefill--${prefillOutcome.status}`} aria-live="polite">
              {prefillOutcome.message}
            </p>
          ) : null}
          <iframe
            ref={iframeRef}
            src={record.href}
            title={record.title}
            onLoad={isPagoPa ? runPagoPaPrefill : undefined}
            sandbox={isPagoPa ? 'allow-same-origin allow-forms allow-scripts allow-popups allow-popups-to-escape-sandbox allow-downloads allow-top-navigation-by-user-activation' : undefined}
            referrerPolicy={isPagoPa ? 'same-origin' : undefined}
          />
        </div>
      </div>
    </div>
  )
}

function italianDateOrRaw(value: string): string {
  const raw = cleanDisplayText(value)
  if (!raw) return ''
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) return raw
  return formatDateIt(raw, raw)
}

function paymentValueLabel(item: FascicoloPaymentItem, fallback = 'n.d.'): string {
  return cleanDisplayText(item.importoLabel) || fallback
}

function paymentNote(item: FascicoloPaymentItem): string {
  return [item.metodo, item.documentoFonte, item.note, item.updatedAtLabel].map(cleanDisplayText).filter(Boolean).join(' · ')
}

function economicControlPaymentRow(item: FascicoloPaymentItem, label = item.displayLabel, fallback = 'n.d.') {
  return {
    key: item.kind,
    label,
    value: paymentValueLabel(item, fallback),
    status: item.statusLabel,
    tone: item.tone,
    note: paymentNote(item) || (item.previsto ? 'Importo da confermare nel fascicolo.' : 'Non previsto per il fascicolo.'),
  }
}

function EconomicControlModal({
  open,
  data,
  contributoMemory,
  onClose,
  onPaymentSaved,
  onError,
  onOpenPagoPa,
}:{
  open: boolean
  data: FascicoloDetailData
  contributoMemory: ContributoUnificatoMemory | null
  onClose: () => void
  onPaymentSaved: (id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string) => void
  onError: (message:string) => void
  onOpenPagoPa: () => void
}) {
  const [editing, setEditing] = useState(false)
  useEffect(() => {
    if (!open) setEditing(false)
  }, [open])
  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null
  const f = data.fascicolo
  const summary = f.paymentSummary
  const items = summary.items
  const contribution = items.contributo_unificato
  const expenses = items.spese_esborsi.importo !== null || items.spese_esborsi.status !== 'non_previsto'
    ? items.spese_esborsi
    : items.fondo_spese
  const proformaNeedsConfirmation = summary.proformaPresidio.status === 'importi_da_confermare' || (f.status === 'definito' && !summary.proformaPresidio.total)
  const proformaStatus = proformaNeedsConfirmation ? 'Importi da confermare' : summary.proformaPresidio.statusLabel
  const proformaMessage = summary.proformaPresidio.message
    || (f.status === 'definito'
      ? 'Fascicolo definito: documento economico letto, ma importo da confermare prima della proforma.'
      : 'Controlla documenti economici, ricevute e importi prima di emettere la proforma.')
  const proformaEditorStatus = proformaNeedsConfirmation
    ? 'Proforma da preparare'
    : summary.proformaPresidio.status === 'presente'
      ? 'Proforma già collegata'
      : summary.proformaPresidio.statusLabel || 'Proforma da generare'
  const proformaEditorMessage = proformaNeedsConfirmation
    ? 'Importo o fonte economica letta dal fascicolo: verifica se emettere la proforma.'
    : proformaMessage
  const contributionStatusLabel = contribution.status === 'non_previsto'
    ? 'Contributo non dovuto o esente'
    : contribution.statusLabel
  const receiptStatus = contribution.status === 'pagato'
    ? 'Ricevuta presente'
    : contribution.status === 'non_previsto'
      ? 'Non prevista'
      : 'Da allegare'
  const rows = [
    { ...economicControlPaymentRow(contribution, 'Contributo'), status: contributionStatusLabel },
    {
      key: 'ricevuta_pagopa',
      label: 'Ricevuta pagoPA',
      value: cleanDisplayText(contribution.documentoFonte) || 'n.d.',
      status: receiptStatus,
      tone: contribution.status === 'pagato' ? 'success' : contribution.status === 'non_previsto' ? 'neutral' : 'warning',
      note: contribution.origine || contribution.note || 'Collega ricevuta PagoPA, F23/F24 o documento di esenzione quando disponibile.',
    },
    economicControlPaymentRow(expenses, 'Spese/esborsi'),
    economicControlPaymentRow(items.liquidazione_giudice, 'Liquidazione'),
    economicControlPaymentRow(items.parcella, 'Parcella', items.parcella.status === 'da_emettere' ? 'Da calcolare' : 'n.d.'),
    {
      key: 'controllo_documenti',
      label: 'Controllo documenti',
      value: proformaStatus,
      status: summary.analysis.statusLabel || summary.statoLabel,
      tone: summary.proformaPresidio.tone || summary.analysis.tone || summary.tone,
      note: proformaMessage,
    },
  ]
  const importHref = `/importa-pratiche-studio-telematico?fascicolo=${encodeURIComponent(f.id)}`
  const caseDate = italianDateOrRaw(f.sourceSnapshot.dataIscrizione || f.openedAt || f.dataAperturaIso)
  const objectLabel = fascicoloOggettoRicorso(f)
  const chips = [
    { label: contributionStatusLabel, tone: contribution.status === 'non_previsto' ? 'neutral' : contribution.tone },
    { label: 'Ricevuta pagoPA', tone: contribution.status === 'pagato' ? 'success' : contribution.status === 'non_previsto' ? 'neutral' : 'warning' },
    { label: items.parcella.status === 'da_emettere' || summary.parcelleDaEmettere ? 'Parcella da emettere' : items.parcella.statusLabel, tone: items.parcella.tone },
    { label: proformaStatus, tone: proformaNeedsConfirmation ? 'warning' : summary.proformaPresidio.tone },
  ]
  return (
    <div className="iu-fas-economic-control-modal" role="dialog" aria-modal="true" aria-label="Controllo economico fascicolo">
      <div className="iu-fas-economic-control-modal__box">
        <header>
          <div>
            <span><WalletCards size={15}/> Controllo economico fascicolo</span>
            <strong>{f.ref || f.rg || f.id}</strong>
            <small>{[f.title, data.client?.name || f.client].filter(Boolean).join(' · ')}</small>
          </div>
          <nav>
            <button type="button" onClick={() => setEditing((current) => !current)} aria-pressed={editing}>
              {editing ? <ListChecks size={15}/> : <PencilLine size={15}/>}
              {editing ? 'Riepilogo controllo' : 'Modifica controllo economico'}
            </button>
            <button type="button" onClick={onClose} aria-label="Chiudi controllo economico">Chiudi</button>
          </nav>
        </header>
        <section className="iu-fas-economic-control-modal__summary" aria-label="Riepilogo pratica">
          <span><strong>RG</strong>{f.ref || f.rg || 'n.d.'}</span>
          <span><strong>Cliente</strong>{data.client?.name || f.client || 'n.d.'}</span>
          <span><strong>Data</strong>{caseDate || 'n.d.'}</span>
          <span><strong>Stato</strong>{formatFascicoloStatus(f.status)}</span>
          <span className="is-wide"><strong>Oggetto del ricorso</strong>{objectLabel || 'Oggetto non indicato'}</span>
        </section>
        {editing ? (
          <section className="iu-fas-economic-control-modal__editor" aria-label="Modifica controllo economico">
            <div className="iu-fas-economic-control-modal__editor-head">
              <Badge tone={summary.tone}>{summary.statoLabel}</Badge>
              <strong>Modifica controllo economico</strong>
              <span>{proformaEditorStatus}</span>
              <p>{proformaEditorMessage}</p>
            </div>
            <EconomicEditorPanel row={f} onSaved={onPaymentSaved} onError={onError}/>
          </section>
        ) : (
          <>
            <section className="iu-fas-economic-control-modal__rows" aria-label="Voci economiche">
              {rows.map((row) => (
                <article key={row.key}>
                  <div>
                    <span>{row.label}</span>
                    <strong>{row.value}</strong>
                    <small>{row.note}</small>
                  </div>
                  <Badge tone={row.tone as FascicoloRow['tone']}>{row.status}</Badge>
                </article>
              ))}
            </section>
            <aside className="iu-fas-economic-control-modal__presidio" aria-label="Presidio economico">
              <Badge tone={summary.tone}>{summary.statoLabel}</Badge>
              <strong>{proformaStatus}</strong>
              <p>{proformaMessage}</p>
              <div>
                {chips.map((chip, index) => <Badge tone={chip.tone as FascicoloRow['tone']} key={`${chip.label}-${index}`}>{chip.label}</Badge>)}
              </div>
              {contributoMemory ? <small>Calcolo CU in memoria per PagoPA: {contributoMemory.totalLabel}</small> : null}
            </aside>
          </>
        )}
        <footer>
          <button type="button" onClick={onOpenPagoPa}><Euro size={15}/> PagoPA nuovo pagamento</button>
          <a href={importHref}><UploadCloud size={15}/> Import pratiche</a>
        </footer>
      </div>
    </div>
  )
}

function recordText(row: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = row?.[key]
  return String(value ?? fallback).trim()
}

async function parseLocalSignerResponse(response: Response): Promise<Record<string, unknown>> {
  const rawText = await response.text().catch(() => '')
  const text = rawText.trim()
  if (!text) return {}
  try {
    const payload = JSON.parse(text)
    return payload && typeof payload === 'object' && !Array.isArray(payload)
      ? payload as Record<string, unknown>
      : { errore: text }
  } catch {
    return { errore: text }
  }
}

function recordBool(row: Record<string, unknown> | undefined, key: string) {
  const value = row?.[key]
  return value === true || value === 'true' || value === '1' || value === 1
}

function recordNumber(row: Record<string, unknown> | undefined, key: string, fallback = 0) {
  const value = Number(row?.[key] ?? fallback)
  return Number.isFinite(value) ? value : fallback
}

function recordHref(row: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = recordText(row, key, fallback)
  return value.startsWith('/') || value.startsWith('#') ? value : fallback
}

function RegiaActionCard({ label, value, note, href, tone = 'neutral' }:{label:string; value:string; note:string; href:string; tone?:FascicoloRow['tone']}) {
  return (
    <a className={`iu-fas-regia-action iu-fas-regia-action--${tone}`} href={href}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
      <ChevronRight size={16} aria-hidden="true"/>
    </a>
  )
}

function RegiaOperativaSection({ data, onDone, onError, onOpen, loading = false }:{data:FascicoloDetailData; onDone:(message?:string)=>void; onError:(message:string)=>void; onOpen?:()=>void; loading?:boolean}) {
  const regia = data.regia
  const h = regia.header
  const economics = regia.economics
  const deposit = regia.deposit
  const evidence = regia.evidencePack
  const blocked = recordBool(deposit, 'blocked')
  const ready = recordBool(deposit, 'ready')
  const sendAction = recordText(deposit, 'sendAction')
  const prepareAction = recordText(deposit, 'prepareAction')
  const predepositAction = recordText(regia.actions, 'predepositCheck')
  const recalculateAction = recordText(regia.actions, 'recalculate')
  const evidenceHref = recordText(evidence, 'href')
  const preventivoHref = recordHref(economics, 'preventivoHref', `/preventivi/nuovo?id_fascicolo=${encodeURIComponent(data.fascicolo.id)}`)
  const conferimentoHref = recordHref(economics, 'conferimentoHref', `/preventivi/conferimento/nuovo?id_fascicolo=${encodeURIComponent(data.fascicolo.id)}`)
  const proformaHref = recordHref(economics, 'proformaHref', `/fatturazione/nuova?id_fascicolo=${encodeURIComponent(data.fascicolo.id)}`)
  const paymentHref = recordHref(economics, 'paymentHref', proformaHref)
  const blockReasons = Array.isArray(deposit.blockReasons) ? deposit.blockReasons.map((item) => String(item || '').trim()).filter(Boolean) : []
  const metaItems = [
    ['Area', h.area],
    ['Canale', h.channel],
    ['Registro', h.registry],
    ['Percorso', h.workflow],
  ].filter(([, value]) => String(value || '').trim())
  const validationHasRun = Boolean(regia.validation.lastCheck || regia.validation.results.length || regia.validation.blockers.length || regia.validation.warnings.length)
  const validationMessage = regia.validation.blockers[0]
    ? recordText(regia.validation.blockers[0], 'message')
    : regia.validation.warnings[0]
      ? recordText(regia.validation.warnings[0], 'message')
      : validationHasRun
        ? 'Verifica completata: nessun blocco critico rilevato.'
        : 'Avvia una verifica per controllare dati, documenti e deposito.'
  const statusTone: FascicoloRow['tone'] = regia.validation.ready ? 'success' : regia.validation.blockers.length ? 'danger' : 'warning'
  return (
    <DetailSection id="regia-operativa" title="Regia Operativa" icon={<ClipboardCheck size={17}/>} count={regia.checklist.length + regia.documentSlots.length} onOpen={onOpen}>
      {loading ? <p className="iu-empty">Caricamento Regia Operativa...</p> : null}
      <div className="iu-fas-regia">
        <header className="iu-fas-regia__header">
          <div>
            <Badge tone={statusTone}>{h.operationalState || 'Da verificare'}</Badge>
            <h3>{h.practiceType || fLabel(data.fascicolo.title)}</h3>
            <p>{h.nextAction || 'Completa i controlli operativi del fascicolo.'}</p>
          </div>
          <div className="iu-fas-regia__progress" aria-label="Completamento Regia Operativa">
            <strong>{h.completion}%</strong>
            <span>completamento</span>
          </div>
        </header>
        {metaItems.length ? (
          <div className="iu-fas-regia__meta">
            {metaItems.map(([label, value]) => <span key={label}><strong>{label}</strong>{value}</span>)}
          </div>
        ) : null}
        <div className="iu-fas-regia__grid">
          <article>
            <h4>Contesto economico e incarico</h4>
            <div className="iu-fas-regia-action-list">
              <RegiaActionCard label="Preventivo accettato" value={recordBool(economics, 'preventivoAccepted') ? 'Si' : 'No'} note={recordBool(economics, 'preventivoAccepted') ? 'Apri preventivo' : 'Apri per accettare o creare'} href={preventivoHref} tone={recordBool(economics, 'preventivoAccepted') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Conferimento firmato" value={recordBool(economics, 'conferimentoSigned') ? 'Si' : 'No'} note={recordBool(economics, 'conferimentoSigned') ? 'Apri conferimento' : 'Apri il conferimento'} href={conferimentoHref} tone={recordBool(economics, 'conferimentoSigned') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Avviso / parcella" value={recordBool(economics, 'proformaIssued') ? 'Emesso' : 'Non emesso'} note={recordBool(economics, 'proformaIssued') ? 'Apri documento economico' : 'Crea la parcella'} href={proformaHref} tone={recordBool(economics, 'proformaIssued') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Pagamento" value={recordBool(economics, 'paymentRegistered') ? 'Registrato' : 'Da registrare'} note={recordBool(economics, 'paymentRegistered') ? 'Apri incassi' : 'Registra incasso'} href={paymentHref} tone={recordBool(economics, 'paymentRegistered') ? 'success' : 'warning'}/>
            </div>
            <ul className="iu-fas-regia__facts">
              <li><span>Compenso pattuito</span><strong>{recordText(economics, 'agreedFee', '€ 0,00')}</strong></li>
              <li><span>Spese vive / anticipazioni</span><strong>{recordText(economics, 'expenses', '€ 0,00')}</strong></li>
            </ul>
            {Array.isArray(economics.overrides) && economics.overrides.length ? <p className="iu-fas-regia__warn">Variazione economica presente e registrata.</p> : null}
          </article>
          <article>
            <h4>Validazione</h4>
            <Badge tone={statusTone}>{regia.validation.status || 'Da verificare'}</Badge>
            <p>{validationMessage}</p>
            <div className="iu-fas-regia__actions">
              {predepositAction ? <PostAction action={predepositAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={15}/> Verifica operativa</PostAction> : null}
              {prepareAction ? <PostAction action={prepareAction} tone="secondary" onDone={onDone} onError={onError}><ClipboardCheck size={15}/> Prepara deposito</PostAction> : null}
            </div>
          </article>
        </div>
        <div className="iu-fas-regia__columns">
          <section>
            <h4>Checklist dinamica</h4>
            <div className="iu-fas-regia-list">
              {regia.checklist.map((item) => <article key={recordText(item, 'id') || recordText(item, 'key')}><Badge tone={recordText(item, 'status') === 'BLOCCATO' ? 'danger' : recordText(item, 'status') === 'COMPLETATO' ? 'success' : 'warning'}>{recordText(item, 'status', 'Da completare')}</Badge><strong>{recordText(item, 'label')}</strong><span>{recordText(item, 'message')}</span><small>{recordText(item, 'suggestedAction')}</small></article>)}
              {!regia.checklist.length ? <div className="iu-fas-regia-empty-card"><strong>Checklist da creare</strong><span>La Regia genera i controlli dopo il profilo operativo del fascicolo.</span>{recalculateAction ? <PostAction action={recalculateAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={15}/> Aggiorna Regia</PostAction> : null}</div> : null}
            </div>
          </section>
          <section>
            <h4>Documenti richiesti</h4>
            <div className="iu-fas-regia-list">
              {regia.documentSlots.map((slot) => {
                const slotStatus = slotStatusDisplay(recordText(slot, 'status'), Boolean(recordText(slot, 'documentId')))
                return (
                  <article key={recordText(slot, 'slotKey')}>
                    <Badge tone={slotStatus.tone}>{slotStatus.label}</Badge>
                    <strong>{recordText(slot, 'label')}</strong>
                    <span>{recordText(slot, 'documentId') ? 'Documento collegato' : depositUserFacingMessage(recordText(slot, 'message', 'Documento non collegato'))}</span>
                    <small>{depositUserFacingMessage(recordText(slot, 'suggestedAction'))}</small>
                  </article>
                )
              })}
              {!regia.documentSlots.length ? <div className="iu-fas-regia-empty-card"><strong>Documenti da impostare</strong><span>Carica o classifica i documenti, poi aggiorna la Regia per creare le scelte richieste.</span><a href="#documenti"><FileText size={15}/> Vai ai documenti</a></div> : null}
            </div>
          </section>
        </div>
        <div className="iu-fas-regia__deposit">
          <div>
              <Badge tone={recordText(deposit, 'status') === 'ACQUISITO' ? 'success' : blocked ? 'danger' : ready ? 'success' : 'warning'}>{depositStatusLabel(recordText(deposit, 'status', 'Da preparare'))}</Badge>
            <strong>{recordText(deposit, 'label', 'Deposito')}</strong>
            <p>{recordText(deposit, 'message') || blockReasons[0] || 'Stato deposito non avviato.'}</p>
            {blockReasons.length ? <ul>{blockReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}
          </div>
          <div className="iu-fas-regia__actions">
            {ready && sendAction ? <PostAction action={sendAction} tone="primary" onDone={onDone} onError={onError} confirm="Inviare il deposito con il canale configurato?" confirmTitle="Invia deposito"><Send size={15}/> Invia deposito</PostAction> : prepareAction ? <PostAction action={prepareAction} tone="secondary" onDone={onDone} onError={onError}><ClipboardCheck size={15}/> Prepara deposito</PostAction> : <a href="#documenti"><FileText size={15}/> Controlla documenti</a>}
            {evidenceHref ? <a className="iu-fas-side-link" href={evidenceHref}><FileArchive size={15}/> Evidence pack</a> : null}
          </div>
        </div>
        {regia.timeline.length ? (
          <section>
            <h4>Timeline ricevute</h4>
            <div className="iu-fas-timeline">
              {regia.timeline.map((event) => <article key={recordText(event, 'id')}><time>{recordText(event, 'createdAt')}</time><strong>{recordText(event, 'status')}</strong><p>{recordText(event, 'message')}</p></article>)}
            </div>
          </section>
        ) : null}
      </div>
    </DetailSection>
  )
}

function relataStatusDisplayLabel(value: string): string {
  const key = normaliseText(value)
  if (key === 'superato') return 'completato'
  if (key === 'da acquisire') return 'da acquisire'
  if (key === 'da completare') return 'da completare'
  if (key === 'da preparare') return 'da preparare'
  if (key === 'da firmare') return 'da firmare'
  if (key === 'in attesa') return 'in attesa'
  if (key === 'monitorato') return 'monitorato'
  if (key === 'prova depositata') return 'prova depositata'
  if (key === 'storico gestito') return 'storico gestito'
  return value.replace(/_/g, ' ')
}

function NotificationRelataMonitor({ data }:{data:FascicoloDetailData}) {
  const monitor = data.notificationRelata
  const proofDeposited = monitor.proofDeposited || monitor.status === 'prova_depositata'
  const legacyHandled = monitor.legacyAssumedHandled || monitor.status === 'storico_gestito'
  const alreadySent = proofDeposited || legacyHandled || monitor.notificationAlreadySent || ['ricevute_da_completare', 'prova_raccolta'].includes(monitor.status)
  const canPrepareNotification = !alreadySent && ['monitoraggio', 'da_preparare', 'da_firmare', 'pronta_invio'].includes(monitor.status)
  const actions = [
    { label: monitor.primaryLabel || 'Apri presidio', href: monitor.primaryHref, icon: monitor.status === 'da_acquisire' ? <FileDown size={15}/> : <FileSignature size={15}/>, show: true },
    { label: 'Acquisisci dal portale', href: monitor.acquisitionHref, icon: <FileDown size={15}/>, show: monitor.releaseDetected },
    { label: 'Prepara relata', href: monitor.prepareHref, icon: <FileSignature size={15}/>, show: canPrepareNotification },
    { label: alreadySent ? 'Deposita prova' : 'Prepara deposito prova', href: monitor.depositHref, icon: <Send size={15}/>, show: !proofDeposited && !legacyHandled && (alreadySent || monitor.proofDocuments > 0 || monitor.proofComplete) },
  ].filter((item, index, rows) => item.href && rows.findIndex((row) => row.href === item.href) === index)
    .filter((item) => item.show)
  const total = Math.max(monitor.pendingPortalDocuments, monitor.relataDocuments, monitor.signedRelataDocuments, monitor.proofDocuments, monitor.documents.length)
  return (
    <div className={`iu-fas-relata-monitor iu-fas-relata-monitor--${monitor.tone}`}>
      <header>
        <div>
          <Badge tone={monitor.tone}>{monitor.statusLabel}</Badge>
          <h3>Presidio notifica e prova</h3>
          <p>{monitor.systemNotification || 'Il fascicolo resta monitorato per documenti d\'ufficio, relata, firma, invio e prova.'}</p>
        </div>
        <strong>{total}</strong>
      </header>
      <div className="iu-fas-relata-actions">
        {actions.map((action) => <a href={action.href} key={`${action.label}-${action.href}`}>{action.icon}{action.label}</a>)}
      </div>
      <div className="iu-fas-relata-flow">
        {monitor.steps.map((step, index) => (
          <article key={step.id || `${step.label}-${index}`} className={`iu-fas-relata-flow__step is-${step.status}`}>
            <span>{index + 1}</span>
            <div>
              <strong>{step.label}</strong>
              <small>{step.detail}</small>
            </div>
            <em>{relataStatusDisplayLabel(step.status)}</em>
          </article>
        ))}
      </div>
      {monitor.releasedDocuments.length ? (
        <section className="iu-fas-relata-list">
          <h4>Documenti rilasciati da acquisire</h4>
          {monitor.releasedDocuments.map((doc, index) => (
            <article key={doc.documentoId || doc.riferimentoPortale || `${doc.nome}-${index}`}>
              <FileDown size={16}/>
              <div>
                <strong>{doc.nome || doc.tipo || 'Documento d\'ufficio'}</strong>
                <span>{[doc.fontePortale || 'Portale Servizi', doc.ufficio, doc.numeroRg && doc.annoRg ? `R.G. ${doc.numeroRg}/${doc.annoRg}` : '', doc.dataDeposito ? formatDateIt(doc.dataDeposito, doc.dataDeposito) : ''].filter(Boolean).join(' · ')}</span>
              </div>
              {doc.notificaRichiesta ? <Badge tone="warning">Relata richiesta</Badge> : null}
            </article>
          ))}
        </section>
      ) : null}
      {monitor.documents.length ? (
        <section className="iu-fas-relata-list">
          <h4>Documenti monitorati</h4>
          {monitor.documents.map((doc, index) => (
            <article key={doc.id || `${doc.name}-${index}`}>
              <FileText size={16}/>
              <div>
                <strong>{doc.href ? <a href={doc.href}>{doc.name}</a> : doc.name}</strong>
                <span>{[doc.kindLabel || doc.kind.replace(/_/g, ' '), doc.statusLabel || relataStatusDisplayLabel(doc.status)].filter(Boolean).join(' · ')}</span>
              </div>
            </article>
          ))}
        </section>
      ) : null}
      {!monitor.releasedDocuments.length && !monitor.documents.length ? (
        <p className="iu-empty">Nessun documento d'ufficio da acquisire. Il collegamento al Portale Servizi resta pronto con dati del fascicolo.</p>
      ) : null}
    </div>
  )
}

function fLabel(value: string) {
  return value || 'Fascicolo'
}

type DocumentAutoSection = {
  id: string
  title: string
  note: string
  tone: FascicoloRow['tone']
  documents: FascicoloDocument[]
}

type PortalCatalogRow = {
  id: string
  name: string
  type: string
  role: string
  date: string
  sender: string
  source: string
  imported: boolean
  available: boolean
  tone: FascicoloRow['tone']
}

const documentAutoSectionOrder: Array<Omit<DocumentAutoSection, 'documents'>> = [
  { id: 'atti', title: 'Atti e memorie', note: 'Atto principale, difese e bozze redazionali.', tone: 'primary' },
  { id: 'provvedimenti', title: 'Provvedimenti', note: 'Sentenze, ordinanze, decreti e verbali.', tone: 'purple' },
  { id: 'comunicazioni', title: 'Comunicazioni', note: 'PEC, cancelleria, notifiche e messaggi collegati.', tone: 'info' },
  { id: 'pagamenti', title: 'Pagamenti e contributi', note: 'Contributo unificato, PagoPA, bolli, parcelle e note spese.', tone: 'success' },
  { id: 'allegati', title: 'Allegati e supporti', note: 'Procure, contratti, parcelle e allegati di fascicolo.', tone: 'neutral' },
  { id: 'da-verificare', title: 'Da verificare', note: 'Documenti senza sezione certa da controllare.', tone: 'warning' },
]

function documentSearchText(doc: FascicoloDocument): string {
  return normaliseText([doc.type, doc.rawType, doc.name, doc.source, doc.portalClass, doc.portalName, doc.portalSender, doc.statusLabel, doc.catalogRole, doc.catalogLabel, doc.catalogSection, doc.catalogEvidence, doc.depositRole, ...doc.tags].join(' '))
}

function uniqueFascicoloDocuments(documents: FascicoloDocument[]): FascicoloDocument[] {
  const seen = new Set<string>()
  return documents.filter((doc) => {
    if (!doc.id || seen.has(doc.id)) return false
    seen.add(doc.id)
    return true
  })
}

function visibleDocumentTags(doc: FascicoloDocument): string[] {
  const seen = new Set<string>()
  return doc.tags
    .map((tag) => tag.trim())
    .filter((tag) => {
      const key = normaliseText(tag)
      if (!key || /(quickorganizer|import_esterno|backend|frontend|payload|runtime|legacy)/.test(key)) return false
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

function isPortalAcquiredDocument(doc: FascicoloDocument): boolean {
  const text = documentSearchText(doc)
  return Boolean(doc.portalClass || doc.portalName || doc.portalDate || doc.portalSender || /portale|polisweb|pst|pdp|pat|ptt|sigit|telematico/.test(text))
}

function isCommunicationDocument(doc: FascicoloDocument): boolean {
  if (doc.catalogRole === 'comunicazione') return true
  if (doc.catalogSection === 'comunicazioni' && !['prova_notifica', 'relata'].includes(doc.catalogRole)) return true
  return /(pec|cancelleria|comunicazion|notifica|relata|busta|rdac|rac|esito|ricevut|accettazion|consegna)/.test(documentSearchText(doc))
}

type NotificationProofKind = 'atto_notificato' | 'relata' | 'pec' | 'rac' | 'rdac' | 'attestazione' | ''

function notificationProofKind(doc: FascicoloDocument): NotificationProofKind {
  const text = documentSearchText(doc)
  const notificationContext = /(notifica|notificaz|originale notificato|legge n\.?\s*53|l\.?\s*53|notifica[_\s-]*id)/.test(text)
  if (notificationContext && /relata/.test(text)) return 'relata'
  if (/originale notificato/.test(text) && /(ricorso|citazione|comparsa|memoria|istanza|atto|decreto)/.test(text)) return 'atto_notificato'
  if (notificationContext && /(accettazione|rac)/.test(text)) return 'rac'
  if (notificationContext && /(consegna|rdac|avvenuta consegna)/.test(text)) return 'rdac'
  if (notificationContext && /(pec inviata|postacert|messaggio pec|\.eml)/.test(text)) return 'pec'
  if (notificationContext && /attestazione di conform/.test(text)) return 'attestazione'
  return ''
}

function isNotificationProofDocument(doc: FascicoloDocument): boolean {
  return Boolean(notificationProofKind(doc))
}

function isNotificationCommunicationDocument(doc: FascicoloDocument): boolean {
  return ['atto_notificato', 'pec', 'rac', 'rdac', 'attestazione'].includes(notificationProofKind(doc))
}

function notificationProofLabel(doc: FascicoloDocument): string {
  const kind = notificationProofKind(doc)
  if (kind === 'atto_notificato') return 'Atto notificato'
  if (kind === 'relata') return 'Relata'
  if (kind === 'pec') return 'PEC inviata'
  if (kind === 'rac') return 'RAC'
  if (kind === 'rdac') return 'RdAC'
  if (kind === 'attestazione') return 'Attestazione'
  return 'Prova notifica'
}

function notificationCommunicationDetail(doc: FascicoloDocument): string {
  const kind = notificationProofKind(doc)
  if (kind === 'atto_notificato') return 'Documento originale notificato: deve provenire dal Portale Servizi, non dall’allegato PEC d’ufficio.'
  if (kind === 'rac') return 'Ricevuta di accettazione della notifica PEC conservata nel fascicolo.'
  if (kind === 'rdac') return 'Ricevuta di avvenuta consegna della notifica PEC conservata nel fascicolo.'
  if (kind === 'pec') return 'Messaggio PEC di invio notifica collegato al documento notificato.'
  if (kind === 'attestazione') return 'Attestazione di conformità collegata alla notifica.'
  return 'Prova di notifica conservata nel fascicolo.'
}

function depositIssueLabel(row: { label?: string; message?: string; note?: string }): string {
  const text = normaliseText(`${row.label || ''} ${row.message || ''}`)
  if (/atto principale/.test(text)) return 'Atto principale'
  if (/codice oggetto|catalogo/.test(text)) return 'Codice deposito'
  if (/ufficio|registro|rg/.test(text)) return 'Dati fascicolo'
  if (/pdf\/?a/.test(text)) return 'Formato atto'
  if (/file|slot|documento non collegato|documento vuoto/.test(text)) return 'Documento busta'
  if (/hash|datiatto|xml|schema|busta|indice/.test(text)) return 'Pacchetto'
  if (/firm|firma|pin|token/.test(text)) return 'Firma'
  if (/preventivo|conferimento|pagamento|acconto|fattura/.test(text)) return 'Informazione studio'
  return row.label || 'Controllo'
}

function depositIssueMessage(row: { message?: string; note?: string; label?: string }): string {
  const text = normaliseText(`${row.message || ''} ${row.note || ''} ${row.label || ''}`)
  if (/hash documento assente|calcolare l'?hash|calcol.*hash/.test(text)) return 'Ricalcola l’impronta del documento prima della generazione.'
  if (/file non collegato|documento non collegato|collega il documento/.test(text)) return 'Collega il documento richiesto alla busta.'
  if (/file non apribile|ricarica il documento|correggi il collegamento/.test(text)) return 'Ricarica il documento oppure correggi il collegamento.'
  if (/documento vuoto|file valido/.test(text)) return 'Ricarica un file valido.'
  return depositUserFacingMessage(row.message || row.note || row.label || 'Controllo registrato')
}

function isDecisiveDepositIssue(row: { tone?: string; label?: string; message?: string; note?: string }): boolean {
  if (row.tone !== 'danger') return false
  const text = normaliseText(`${row.label || ''} ${row.message || ''} ${row.note || ''}`)
  if (/firm|firma|pin|token|certificat/.test(text)) return false
  if (/preventivo|conferimento|pagamento|acconto|fattura|onorari|cliente|avvocato referente|recapito|email|controparte/.test(text)) return false
  return /(atto principale|codice oggetto|catalogo ufficiale|ufficio|registro|rg|documento selezionato|file|percorso|hash|datiatto|xml|schema|busta|indice|pdf\/?a|dimensione|slot|obbligator)/.test(text)
}

function requiresPackageSignature(doc: FascicoloDocument): boolean {
  const proofKind = notificationProofKind(doc)
  if (proofKind && proofKind !== 'relata') return false
  return !doc.signed
}

function documentHasSignedContainerExtension(doc: FascicoloDocument | undefined): boolean {
  return Boolean(doc?.name && /\.(p7m|sig|pkcs7)$/i.test(doc.name.trim()))
}

function documentExplicitlyRequiresSignature(doc: FascicoloDocument | undefined): boolean {
  if (!doc) return false
  const text = normaliseText(`${doc.name} ${doc.type} ${doc.tags.join(' ')}`)
  if (documentHasSignedContainerExtension(doc)) return false
  return /(firma richiesta|firma obbligatoria|firmare obbligatoriamente|sottoscrizione obbligatoria|da sottoscrivere)/.test(text)
}

function packageDocumentSignatureLabel(doc: FascicoloDocument): string {
  if (doc.signed) return 'Firmato'
  if (documentExplicitlyRequiresSignature(doc)) return 'Da firmare'
  return 'Firma non necessaria'
}

function defaultSignatureRequiredForDepositRole(doc: FascicoloDocument | undefined, role: DepositDocumentRole): boolean {
  if (!doc || doc.signed || !requiresPackageSignature(doc)) return false
  return role === 'atto_principale' || role === 'procura' || documentExplicitlyRequiresSignature(doc)
}

function buildDepositPecBody(documenti: string[]): string {
  const files = documenti.map((item) => item.trim()).filter(Boolean)
  const elenco = files.length
    ? `\n\nIl pacchetto contiene i seguenti documenti:\n${files.map((name) => `- ${name}`).join('\n')}`
    : ''
  return [
    'Egregio sig. Cancelliere,',
    '',
    `Allego alla presente il pacchetto di deposito telematico.${elenco}`,
    '',
    '',
  ].join('\n')
}

function portalCatalogRole(value: string): { label: string; tone: FascicoloRow['tone']; depositCandidate: boolean } {
  const text = normaliseText(value)
  if (/(sentenza|ordinanza|decreto|provvediment|verbale)/.test(text)) return { label: 'Provvedimento', tone: 'purple', depositCandidate: false }
  if (/(ricevut|accettazion|consegna|rdac|rac|esito|cancelleria|pec|comunicazion)/.test(text)) return { label: 'Ricevuta / cancelleria', tone: 'info', depositCandidate: false }
  if (/(atto principale|\batto\b|\bricorso\b|\bcitazione\b|\bcomparsa\b|\bmemoria\b|\bistanza\b|deduzion|conclusionale)/.test(text)) return { label: 'Atto', tone: 'primary', depositCandidate: true }
  if (/(allegato|procura|documento|contratto|quietanza)/.test(text)) return { label: 'Allegato', tone: 'neutral', depositCandidate: true }
  return { label: 'Da classificare', tone: 'warning', depositCandidate: false }
}

function isDepositCandidateDocument(doc: FascicoloDocument): boolean {
  if (['atto_principale', 'atto_difensivo', 'procura', 'prova_notifica', 'relata', 'contributo_unificato', 'nota_iscrizione_ruolo', 'provvedimento', 'allegato'].includes(doc.catalogRole)) {
    return doc.depositCandidate !== false
  }
  if (doc.depositCandidate !== undefined) return doc.depositCandidate
  if (isCommunicationDocument(doc)) return false
  if (!isPortalAcquiredDocument(doc)) return true
  return portalCatalogRole(`${doc.portalClass} ${doc.type} ${doc.name}`).depositCandidate
}

function isDepositManualSelectableDocument(doc: FascicoloDocument): boolean {
  if (doc.catalogRole === 'comunicazione' || doc.depositRole === 'fuori_busta') return false
  if (isCommunicationDocument(doc)) return false
  return true
}

function isMainActCandidateDocument(doc: FascicoloDocument): boolean {
  if (doc.catalogRole === 'atto_principale') return true
  if (doc.catalogRole === 'atto_difensivo' && doc.catalogConfidence >= 80) return true
  if (doc.catalogConfidence >= 70 && ['allegato', 'classificato_storico', 'comunicazione', 'contributo_unificato', 'economia_fascicolo', 'nota_iscrizione_ruolo', 'procura', 'prova_notifica', 'provvedimento', 'relata'].includes(doc.catalogRole)) return false
  const text = documentSearchText(doc)
  if (/(procura|contratto|contributo|pagopa|marca|nota iscrizione|nir|ricevut|accettazion|consegna|rdac|rac|relata|pec|notifica_id|perizia|ctu|ctp|perital|verbale|sentenza|ordinanza|decreto|provvediment|liquidazione)/.test(text)) return false
  return /(\batto\b|\bricorso\b|\bcitazione\b|\bcomparsa\b|\bmemoria\b|\bistanza\b|\bappello\b|\breclamo\b|\bopposizione\b|deduzion)/.test(text)
}

function isMainActSlot(slot: Record<string, unknown>): boolean {
  const slotKey = recordText(slot, 'slotKey').toUpperCase()
  const type = recordText(slot, 'type').toUpperCase()
  return slotKey === 'ATTO_PRINCIPALE' || type === 'ATTO_PRINCIPALE'
}

function mainActCandidateScore(doc: FascicoloDocument): number {
  if (!isMainActCandidateDocument(doc)) return 0
  const text = documentSearchText(doc)
  let score = 10
  if (doc.catalogRole === 'atto_principale') score += 80
  if (doc.catalogRole === 'atto_difensivo') score += 55
  if (doc.signed) score += 30
  if (/(^|[^a-z])atto([^a-z]|$)|attoacq|atto acquisito|atto giudiziario/.test(text)) score += 25
  if (/\bricorso\b|\bcitazione\b|\bcomparsa\b|\bappello\b|\breclamo\b|\bopposizione\b/.test(text)) score += 20
  if (/\bmemoria\b|\bistanza\b|deduzion|conclusion/.test(text)) score += 12
  return score
}

function preferredMainActCandidateDocument(documents: FascicoloDocument[]): FascicoloDocument | undefined {
  return documents
    .map((doc, index) => ({ doc, index, score: mainActCandidateScore(doc) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)[0]?.doc
}

function documentOperationalRole(doc: FascicoloDocument): { label: string; detail: string; tone: FascicoloRow['tone'] } {
  if (isNotificationProofDocument(doc)) {
    return { label: notificationProofLabel(doc), detail: 'Prova di notifica già presente nel fascicolo: si usa per il deposito prova, senza nuovo invio.', tone: 'info' }
  }
  if (doc.catalogLabel && doc.catalogConfidence >= 70) {
    const tone: FascicoloRow['tone'] =
      doc.catalogSection === 'atti' ? 'primary'
        : doc.catalogSection === 'provvedimenti' ? 'purple'
          : doc.catalogSection === 'comunicazioni' ? 'info'
            : doc.catalogSection === 'pagamenti' ? 'success'
              : doc.catalogSection === 'allegati' ? 'neutral'
                : 'warning'
    const detail = doc.catalogEvidence
      ? `Catalogato da OCR e dati del fascicolo: ${doc.catalogEvidence}.`
      : 'Catalogato da OCR e dati del fascicolo.'
    return { label: doc.catalogLabel, detail, tone }
  }
  if (isCommunicationDocument(doc)) {
    return { label: 'Ricevuta / comunicazione', detail: 'Fuori dalla busta: presidio cancelleria e ricevute.', tone: 'info' }
  }
  if (isPortalAcquiredDocument(doc)) {
    const role = portalCatalogRole(`${doc.portalClass} ${doc.type} ${doc.name}`)
    return {
      label: role.label,
      detail: role.depositCandidate ? 'Documento portale candidato come allegato/atto.' : 'Documento portale tenuto come contesto ufficiale.',
      tone: role.tone,
    }
  }
  if (isDepositCandidateDocument(doc)) {
    return { label: 'Candidato busta', detail: 'Letto dall’intero fascicolo per atto o allegato.', tone: doc.signed ? 'success' : 'warning' }
  }
  return { label: 'Da classificare', detail: 'Presente nel fascicolo, da verificare prima del deposito.', tone: 'warning' }
}

function defaultDepositRoleForDocument(doc: FascicoloDocument | undefined, linkedSlotKey = '', isProposedMainAct = false): DepositDocumentRole {
  if (!doc) return 'allegato'
  const slot = normaliseText(linkedSlotKey)
  const text = documentSearchText(doc)
  if (isProposedMainAct || /atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slot)) return 'atto_principale'
  if (doc.depositRole === 'atto_principale') return 'atto_principale'
  if (doc.depositRole === 'procura') return 'procura'
  if (doc.depositRole === 'prova_notifica') return 'prova_notifica'
  if (doc.depositRole === 'fuori_busta') return 'fuori_busta'
  if (doc.depositRole === 'contributo_unificato' || doc.catalogRole === 'contributo_unificato') return 'allegato'
  if (doc.depositRole === 'allegato' || doc.catalogRole === 'provvedimento' || doc.catalogRole === 'allegato') return 'allegato'
  if (/procura/.test(slot) || /procura/.test(text)) return 'procura'
  if (/prova|notifica|ricevuta/.test(slot) || notificationProofKind(doc)) return 'prova_notifica'
  if (isCommunicationDocument(doc)) return 'fuori_busta'
  if (/contratto|quietanza|busta paga|cedolin|documento|allegat/.test(text)) return 'allegato'
  return 'allegato'
}

function depositRoleLabel(role: DepositDocumentRole): { label: string; tone: FascicoloRow['tone'] } {
  if (role === 'atto_principale') return { label: 'Atto principale', tone: 'primary' }
  if (role === 'procura') return { label: 'Procura alle liti', tone: 'purple' }
  if (role === 'allegato_prova') return { label: 'Allegato', tone: 'success' }
  if (role === 'prova_notifica') return { label: 'Prova notifica', tone: 'info' }
  if (role === 'fuori_busta') return { label: 'Fuori busta', tone: 'neutral' }
  return { label: 'Allegato', tone: 'neutral' }
}

function depositRoleDisplayLabelForDocument(doc: FascicoloDocument, role: DepositDocumentRole): string {
  const technicalLabel = depositRoleLabel(role).label
  if (role !== 'allegato' || !doc.catalogLabel || doc.catalogConfidence < 70) return technicalLabel
  if (['atto_difensivo', 'contributo_unificato', 'nota_iscrizione_ruolo', 'provvedimento', 'relata', 'prova_notifica', 'procura'].includes(doc.catalogRole)) {
    return `${doc.catalogLabel} (allegato busta)`
  }
  if (doc.catalogSection === 'pagamenti') return `${doc.catalogLabel} (allegato busta)`
  return technicalLabel
}

function normaliseDepositClassificationMainAct(
  classificationById: Record<string, DepositDocumentClassification>,
  preferredMainActId = '',
  validMainActIds?: ReadonlySet<string>,
): Record<string, DepositDocumentClassification> {
  const entries = Object.entries(classificationById)
  const preferredSelected = preferredMainActId ? entries.find(([id, row]) => id === preferredMainActId && row.selected) : undefined
  const validSelectedMain = entries.find(([id, row]) => row.selected && row.role === 'atto_principale' && (!validMainActIds || validMainActIds.has(id)))
  const selectedMain = validSelectedMain
    || preferredSelected
    || entries.find(([id, row]) => row.selected && row.role === 'atto_principale' && id === preferredMainActId)
    || entries.find(([, row]) => row.selected && row.role === 'atto_principale')
  const selectedMainId = selectedMain?.[0] || ''
  if (!selectedMainId) return classificationById
  let changed = false
  const next = Object.fromEntries(entries.map(([id, row]) => {
    if (id === selectedMainId && row.role !== 'atto_principale') {
      changed = true
      return [id, { ...row, role: 'atto_principale' as DepositDocumentRole }]
    }
    if (row.selected && row.role === 'atto_principale' && id !== selectedMainId) {
      changed = true
      return [id, { ...row, role: 'allegato' as DepositDocumentRole }]
    }
    return [id, row]
  }))
  return changed ? next : classificationById
}

function depositSelectionRole(doc: FascicoloDocument, isMainAct: boolean, selectedRole?: DepositDocumentRole): { label: string; tone: FascicoloRow['tone'] } {
  if (selectedRole) {
    const role = depositRoleLabel(selectedRole)
    if (selectedRole === 'atto_principale') return { label: role.label, tone: doc.signed ? 'success' : 'warning' }
    return role
  }
  if (isMainAct) return { label: 'Atto principale', tone: doc.signed ? 'success' : 'warning' }
  const proof = notificationProofKind(doc)
  if (proof) return { label: notificationProofLabel(doc), tone: 'info' }
  if (isMainActCandidateDocument(doc)) return { label: 'Atto candidato', tone: doc.signed ? 'success' : 'warning' }
  const role = documentOperationalRole(doc)
  if (role.label === 'Candidato busta') return { label: 'Allegato', tone: role.tone }
  return { label: role.label, tone: role.tone }
}

function depositDocumentMatchesSlot(slot: Record<string, unknown>, doc: FascicoloDocument): boolean {
  const slotText = normaliseText([
    recordText(slot, 'slotKey'),
    recordText(slot, 'label'),
    recordText(slot, 'type'),
    recordText(slot, 'message'),
  ].join(' '))
  const docText = documentSearchText(doc)
  if (/atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slotText)) return isMainActCandidateDocument(doc)
  if (/procura/.test(slotText)) return doc.catalogRole === 'procura' || /procura/.test(docText)
  if (/contributo|pagamento|pagopa/.test(slotText)) return doc.catalogRole === 'contributo_unificato' || /(contributo|unificato|pagopa|ricevuta telematica|rt xml)/.test(docText)
  if (/marca|bollo/.test(slotText)) return /(marca|bollo)/.test(docText)
  if (/nota iscrizione|nir/.test(slotText)) return /(nota iscrizione|nir|iscrizione a ruolo)/.test(docText)
  if (/prova|notifica|ricevuta/.test(slotText)) return Boolean(notificationProofKind(doc)) || /(prova|notifica|ricevut)/.test(docText)
  if (/allegat|documento/.test(slotText)) return isDepositCandidateDocument(doc) && !isMainActCandidateDocument(doc)
  return false
}

function slotMatchesDepositRole(slot: Record<string, unknown>, role: DepositDocumentRole): boolean {
  const uiRole = normaliseDepositRoleForUi(role)
  const slotText = normaliseText(`${recordText(slot, 'slotKey')} ${recordText(slot, 'label')} ${recordText(slot, 'type')}`)
  if (/atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slotText)) return uiRole === 'atto_principale'
  if (/procura/.test(slotText)) return uiRole === 'procura'
  if (/prova|notifica|ricevuta|rac|rdac/.test(slotText)) return uiRole === 'prova_notifica'
  if (/allegat|documento/.test(slotText)) return uiRole === 'allegato'
  return false
}

function depositSelectionSatisfiesSlot(
  slot: Record<string, unknown>,
  selectedDocuments: FascicoloDocument[],
  mainAct: FascicoloDocument | undefined,
  classificationById: Record<string, DepositDocumentClassification> = {},
): boolean {
  const linkedDocumentId = recordText(slot, 'documentId')
  if (linkedDocumentId) return selectedDocuments.some((doc) => doc.id === linkedDocumentId)
  const slotText = normaliseText(`${recordText(slot, 'slotKey')} ${recordText(slot, 'label')} ${recordText(slot, 'type')}`)
  if (/atto principale|atto_principale|atto da notificare|atto_da_notificare/.test(slotText)) return Boolean(mainAct)
  if (selectedDocuments.some((doc) => slotMatchesDepositRole(slot, classificationById[doc.id]?.role || defaultDepositRoleForDocument(doc)))) return true
  return selectedDocuments.some((doc) => depositDocumentMatchesSlot(slot, doc))
}

function slotStatusDisplay(value: string, linked = false): { label: string; tone: FascicoloRow['tone'] } {
  const key = String(value || '').trim().toUpperCase()
  if (key === 'VALIDO') return { label: 'Collegato', tone: 'success' }
  if (key === 'WARNING') return { label: 'Da verificare', tone: 'warning' }
  if (key === 'NON_APPLICABILE') return { label: 'Non richiesto', tone: 'neutral' }
  if (key === 'MANCANTE') return { label: linked ? 'Collegato' : 'Da scegliere', tone: linked ? 'primary' : 'warning' }
  if (key === 'NON_VALIDO') return { label: linked ? 'Da correggere' : 'Da scegliere', tone: 'warning' }
  return { label: linked ? 'Collegato' : 'Da scegliere', tone: linked ? 'primary' : 'warning' }
}

function depositCatalogRequirementLabel(value: string): string {
  const clean = value.trim().replace(/\s+/g, ' ')
  return clean ? clean.charAt(0).toUpperCase() + clean.slice(1) : 'Requisito deposito'
}

function depositCatalogRequirementKind(label: string): 'file' | 'data' {
  const text = normaliseText(label)
  if (/(anagrafica|valore causa|data citazione|istanze|riferimento procedimento|dati procedura|dati terzi|modifiche anagrafica)/.test(text)) return 'data'
  return 'file'
}

function depositCatalogSlotKey(label: string, index: number): string {
  const text = normaliseText(label)
  if (/atto da notificare/.test(text)) return 'ATTO_DA_NOTIFICARE'
  if (/atto principale/.test(text)) return 'ATTO_PRINCIPALE'
  if (/procura/.test(text)) return 'PROCURA'
  if (/contributo/.test(text)) return 'CONTRIBUTO_UNIFICATO'
  if (/nota iscrizione|nir/.test(text)) return 'NOTA_ISCRIZIONE_RUOLO'
  if (/provvedimento impugnato/.test(text)) return 'PROVVEDIMENTO_IMPUGNATO'
  if (/prova notifica/.test(text)) return 'PROVA_NOTIFICA'
  if (/relata|richiesta/.test(text)) return 'RELATA_NOTIFICA'
  if (/destinatari/.test(text)) return 'DESTINATARI'
  if (/ricevute/.test(text)) return 'RICEVUTE'
  if (/allegati/.test(text)) return 'ALLEGATI'
  return `REQUISITO_CATALOGO_${index + 1}`
}

function depositCatalogSlotType(label: string): string {
  const text = normaliseText(label)
  if (/atto da notificare/.test(text)) return 'ATTO_DA_NOTIFICARE'
  if (/atto principale/.test(text)) return 'ATTO_PRINCIPALE'
  if (/procura/.test(text)) return 'PROCURA'
  if (/contributo/.test(text)) return 'CONTRIBUTO_UNIFICATO'
  if (/nota iscrizione|nir/.test(text)) return 'NOTA_ISCRIZIONE_RUOLO'
  if (/prova notifica|provvedimento impugnato|relata|ricevute|allegati/.test(text)) return 'DOCUMENTO'
  return depositCatalogRequirementKind(label) === 'data' ? 'DATO_DEPOSITO' : 'DOCUMENTO'
}

function depositCatalogSlotRequired(label: string): boolean {
  const text = normaliseText(label)
  if (depositCatalogRequirementKind(label) === 'data') return false
  if (/allegati|ricevute|destinatari/.test(text)) return false
  return true
}

function buildDepositCatalogSlots(
  selectedType: FascicoloDepositCatalogEntry | undefined,
  baseSlots: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const catalogDocuments = (selectedType?.ui.documents || []).map((item) => item.trim()).filter(Boolean)
  if (!catalogDocuments.length) return [...baseSlots]
  const baseByKey = new Map<string, Record<string, unknown>>()
  baseSlots.forEach((slot) => {
    const key = recordText(slot, 'slotKey').toUpperCase()
    if (key) baseByKey.set(key, slot)
  })
  const mainActBaseSlot = baseSlots.find((slot) => /atto principale|atto_principale/.test(normaliseText([
    recordText(slot, 'slotKey'),
    recordText(slot, 'label'),
    recordText(slot, 'type'),
  ].join(' '))))
  const used = new Set<string>()
  const catalogSlots: Array<Record<string, unknown>> = catalogDocuments.map((label, index) => {
    const slotKey = depositCatalogSlotKey(label, index)
    const baseSlotKey = slotKey === 'ATTO_DA_NOTIFICARE' ? 'ATTO_PRINCIPALE' : slotKey
    const baseSlot = baseByKey.get(slotKey) || baseByKey.get(baseSlotKey) || (slotKey === 'ATTO_DA_NOTIFICARE' ? mainActBaseSlot : undefined)
    if (baseSlot) used.add(baseSlotKey)
    if (baseSlot) {
      const actualBaseKey = recordText(baseSlot, 'slotKey').toUpperCase()
      if (actualBaseKey) used.add(actualBaseKey)
    }
    if (baseSlot && baseSlotKey !== slotKey) used.add(slotKey)
    const kind = depositCatalogRequirementKind(label)
    const labelText = depositCatalogRequirementLabel(label)
    const useCatalogLabel = slotKey === 'ATTO_DA_NOTIFICARE'
    return {
      ...(baseSlot || {}),
      slotKey,
      label: useCatalogLabel ? labelText : (recordText(baseSlot, 'label') || labelText),
      type: useCatalogLabel ? depositCatalogSlotType(label) : (recordText(baseSlot, 'type') || depositCatalogSlotType(label)),
      required: baseSlot ? recordBool(baseSlot, 'required') : depositCatalogSlotRequired(label),
      sortOrder: recordText(baseSlot, 'sortOrder') || String((index + 1) * 10),
      status: recordText(baseSlot, 'status') || (kind === 'data' ? 'WARNING' : 'MANCANTE'),
      catalogOnly: !baseSlot,
      catalogRequirementKind: kind,
      message: recordText(baseSlot, 'message') || (
        kind === 'data'
          ? 'Dato richiesto dal tipo deposito selezionato: verifica nel pannello dati deposito.'
          : 'Documento richiesto dal tipo deposito selezionato.'
      ),
      suggestedAction: recordText(baseSlot, 'suggestedAction') || (
        kind === 'data'
          ? 'Controlla il dato prima della generazione della busta.'
        : 'Classifica o seleziona il documento corretto nella lista Documenti da inviare.'
      ),
    }
  })
  const catalogUsesNotifiableAct = catalogSlots.some((slot) => recordText(slot, 'slotKey').toUpperCase() === 'ATTO_DA_NOTIFICARE')
  const linkedExtraSlots = baseSlots.filter((slot) => {
    const key = recordText(slot, 'slotKey').toUpperCase()
    const text = normaliseText([key, recordText(slot, 'label'), recordText(slot, 'type')].join(' '))
    if (catalogUsesNotifiableAct && /atto principale|atto_principale/.test(text)) return false
    return key && !used.has(key) && recordText(slot, 'documentId')
  })
  return [...catalogSlots, ...linkedExtraSlots]
}

function depositPackageKindLabel(value: string): string {
  const key = normaliseText(value)
  if (key.includes('pct_busta_enc')) return 'Pacchetto deposito'
  if (key.includes('sigp')) return 'Pacchetto Giudice di Pace'
  if (key.includes('pdp')) return 'Pacchetto deposito penale'
  if (key.includes('pat')) return 'Pacchetto giustizia amministrativa'
  if (key.includes('ptt')) return 'Pacchetto giustizia tributaria'
  if (key.includes('unep')) return 'Richiesta ufficio notifiche'
  if (key.includes('pec')) return 'Messaggio PEC con ricevute'
  if (key.includes('portal') || key.includes('upload')) return 'Pacchetto per portale ufficiale'
  return 'Pacchetto da verificare'
}

function depositDeliveryNote(note: string, officialChannel: string, practiceProfileName: string, fallbackChannel: string): string {
  const clean = note.trim()
  if (!clean) return ''
  const context = normaliseText(`${officialChannel} ${practiceProfileName} ${fallbackChannel}`)
  if (/(lavoro|rgl|retribuzion)/.test(context) && /pct civile|civile sicid/.test(normaliseText(clean))) {
    return 'Profilo lavoro applicato: usare il canale PCT lavoro/SICID; per altri registri la Regia richiede il canale corrispondente.'
  }
  return clean
}

function depositVisibleReference(primary: string, fallback: string): string {
  const value = String(primary || '').trim()
  const normalized = normaliseText(value).replace(/\s+/g, '')
  if (value && normalized !== 'nd' && normalized !== 'n.d.') return value
  return String(fallback || '').trim() || 'Da verificare'
}

function depositActCodeFromDocument(doc: FascicoloDocument | undefined, profile: Record<string, unknown>): string {
  const text = normaliseText(`${doc?.type || ''} ${doc?.name || ''} ${recordText(profile, 'procedureCode')} ${recordText(profile, 'practiceId')}`)
  if (/comparsa/.test(text)) return 'COMPARSA_RISPOSTA'
  if (/decreto ingiuntivo|ingiuntiv/.test(text)) return 'DECRETO_INGIUNTIVO'
  if (/appello|impugnazion|reclamo/.test(text)) return 'APPELLO'
  if (/citazion/.test(text)) return 'ATTO_DI_CITAZIONE'
  if (/ricorso/.test(text)) return 'RICORSO'
  if (/memoria|note scritte|conclusionale|replica/.test(text)) return 'MEMORIA'
  if (/istanza/.test(text)) return 'ISTANZA'
  return 'ATTO_GENERICO'
}

function depositRegistryCode(fascicolo: FascicoloFull): string {
  const text = normaliseText(`${fascicolo.type} ${fascicolo.procedureType} ${fascicolo.rg}`)
  if (/lavoro|rgl/.test(text)) return 'RGL'
  if (/volontaria|vg/.test(text)) return 'VG'
  if (/esecuz|rge/.test(text)) return 'RGE'
  return 'RG'
}

function depositActionBlockedReason(ready: boolean, mainAct: FascicoloDocument | undefined, missingSlots: number, unsignedDocs = 0): string {
  if (!mainAct) return 'Seleziona l’atto principale prima di generare la busta.'
  if (missingSlots === 1) return '1 scelta obbligatoria richiede la conferma dell’avvocato.'
  if (missingSlots) return `${missingSlots} scelte obbligatorie richiedono la conferma dell’avvocato.`
  if (unsignedDocs === 1) return '1 documento sarà firmato da IUSENTRA prima della busta.'
  if (unsignedDocs) return `${unsignedDocs} documenti saranno firmati da IUSENTRA prima della busta.`
  if (!ready) return 'Esegui e supera la verifica deposito prima dell’azione finale.'
  return ''
}

function depositGenerationBlockedReason(mainAct: FascicoloDocument | undefined, missingSlots: number): string {
  if (!mainAct) return 'Seleziona l’atto principale prima di generare la busta.'
  if (missingSlots) return `${missingSlots} scelte obbligatorie richiedono la selezione dell’avvocato.`
  return ''
}

function portalDepositHref(officialChannel: string, fallbackChannel: string): string {
  const text = normaliseText(`${officialChannel} ${fallbackChannel}`)
  if (/pdp|penale/.test(text)) return '/portali/pdp/acquisizione'
  if (/pat|siga|amministrativ/.test(text)) return '/portali/pat/acquisizione'
  if (/ptt|sigit|tributar/.test(text)) return '/portali/ptt/acquisizione'
  if (/sigp|giudice di pace|gdp/.test(text)) return '/portali/pst/acquisizione'
  return '/portali/pst/acquisizione'
}

function buildPortalCatalogRows(data: FascicoloDetailData): PortalCatalogRow[] {
  const rows: PortalCatalogRow[] = []
  const add = (row: Omit<PortalCatalogRow, 'id' | 'role' | 'tone'>, seed: string) => {
    const role = portalCatalogRole(`${row.type} ${row.name}`)
    const id = normaliseText([seed, row.name, row.type, row.date, row.sender].filter(Boolean).join('|'))
    if (!id || rows.some((item) => item.id === id)) return
    rows.push({ ...row, id, role: role.label, tone: role.tone })
  }
  for (const dep of data.deposits) {
    for (const doc of dep.portalDocuments) {
      add({
        name: doc.name || 'Documento ufficiale',
        type: doc.type || dep.actType || 'Documento',
        date: doc.date || dep.timestamp,
        sender: doc.sender || dep.pec,
        source: dep.source || 'Portale Servizi',
        imported: doc.imported,
        available: doc.available,
      }, `deposito-${dep.id}`)
    }
  }
  for (const doc of data.documents.filter(isPortalAcquiredDocument)) {
    add({
      name: doc.portalName || doc.name || 'Documento ufficiale',
      type: doc.portalClass || doc.type || 'Documento',
      date: doc.portalDate || doc.documentDate || doc.uploadedAt,
      sender: doc.portalSender,
      source: doc.source || 'Portale Servizi',
      imported: true,
      available: true,
    }, `documento-${doc.id}`)
  }
  return rows.sort((a, b) => `${b.date} ${b.name}`.localeCompare(`${a.date} ${a.name}`, 'it'))
}

function documentAutoSectionId(doc: FascicoloDocument): string {
  if (['atti', 'provvedimenti', 'comunicazioni', 'pagamenti', 'allegati', 'da-verificare'].includes(doc.catalogSection)) return doc.catalogSection
  const text = documentSearchText(doc)
  if (/(pec|cancelleria|comunicazion|notifica|relata|busta|rdac|rac|esito|ricevut|accettazion)/.test(text)) return 'comunicazioni'
  if (/(sentenza|ordinanza|decreto|provvediment|verbale)/.test(text)) return 'provvedimenti'
  if (/(atto giudiziario|ricorso|citazione|comparsa|memoria|conclusionale|replica)/.test(text)) return 'atti'
  if (/(procura|contratto|parcella|fattura|allegato|documento ufficiale)/.test(text)) return 'allegati'
  return 'da-verificare'
}

function depositCommunicationText(dep: FascicoloDeposit): string {
  return normaliseText([
    dep.status,
    dep.actType,
    dep.message,
    dep.pec,
    dep.source,
    dep.timestamp,
    dep.roleNumber,
    dep.externalId,
    dep.acceptedAt,
    dep.acceptedBy,
  ].join(' '))
}

function depositMetaLine(dep: FascicoloDeposit): string {
  const docs = dep.documentsCount === 1 ? '1 documento' : dep.documentsCount > 1 ? `${dep.documentsCount} documenti` : ''
  const date = dep.acceptedAt
    ? `Accettato il ${dep.acceptedAt}`
    : dep.sentAt
      ? `Depositato il ${dep.sentAt}`
      : dep.timestamp || 'Data non indicata'
  const role = dep.roleNumber ? `RG ${dep.roleNumber}` : ''
  const external = dep.externalId ? `IDBUSTA ${dep.externalId}` : ''
  const registered = dep.registeredBy ? `registrato da ${dep.registeredBy}` : ''
  return [date, role, external, registered, docs, dep.source].filter(Boolean).join(' - ')
}

function depositStatusLabel(status: string): string {
  const clean = normaliseText(status).replace(/_/g, ' ').trim()
  if (!clean) return 'Da verificare'
  if (/importato da portale/.test(clean)) return 'Importato da portale'
  if (/accettato cancelleria/.test(clean)) return 'Deposito confermato'
  if (/warn controlli/.test(clean)) return 'Controlli con avvisi'
  if (/accettato pec/.test(clean)) return 'Accettato PEC'
  if (/consegnato/.test(clean)) return 'Consegnato'
  if (/errore/.test(clean)) return 'Errore'
  return clean
    .split(/\s+/)
    .map((word) => word ? `${word.charAt(0).toUpperCase()}${word.slice(1)}` : word)
    .join(' ')
}

function depositHasPersistedDryRunProof(dep: FascicoloDeposit): boolean {
  const text = normaliseText(`${dep.status} ${dep.message} ${dep.checks} ${dep.source}`)
  return dep.simulated || /prova\s+senza\s+invio/.test(text)
}

function isCancelleriaCommunication(dep: FascicoloDeposit): boolean {
  const text = depositCommunicationText(dep)
  return /(accettazion|consegna|rdac|rac|esito|cancelleria|deposito|busta)/.test(text)
}

function depositNextSimulationLabel(dep: FascicoloDeposit): string {
  const next = dep.receiptSteps.find((step) => !step.done)
  if (!next) return 'Prova completata'
  if (next.id === 'accettazione') return 'Genera accettazione'
  if (next.id === 'consegna') return 'Genera consegna'
  if (next.id === 'controlli') return 'Genera controlli'
  if (next.id === 'cancelleria') return 'Genera conferma'
  return `Genera ${next.label.toLowerCase()}`
}

function depositPhaseSummary(dep: FascicoloDeposit): { label: string; body: string; tone: FascicoloRow['tone'] } {
  const status = normaliseText(`${dep.status} ${dep.checks}`)
  const done = new Set(dep.receiptSteps.filter((step) => step.done).map((step) => step.id))
  if (/accettato cancelleria/.test(status) || done.has('cancelleria')) {
    return { label: 'Deposito confermato', body: 'La conferma di cancelleria è registrata nel fascicolo.', tone: 'success' }
  }
  if (/errore|rifiutato/.test(status)) {
    return { label: 'Deposito da presidiare', body: 'È presente un esito negativo o un blocco: verifica le ricevute e gli allegati.', tone: 'danger' }
  }
  if (/warn controlli|warn/.test(status)) {
    return { label: 'Controlli automatici con avvisi', body: "La PEC dei controlli è arrivata: serve verifica dell'avvocato prima della conferma finale.", tone: 'warning' }
  }
  if (done.has('controlli')) {
    return { label: 'Controlli automatici ricevuti', body: 'La fase tecnica è registrata; resta da attendere la conferma della cancelleria.', tone: 'warning' }
  }
  if (done.has('consegna')) {
    return { label: 'Consegna PEC ricevuta', body: 'Il messaggio risulta consegnato: attendi i controlli automatici.', tone: 'primary' }
  }
  if (done.has('accettazione') || /accettato pec/.test(status)) {
    return { label: 'Accettazione PEC ricevuta', body: 'Il gestore PEC ha accettato il messaggio di deposito.', tone: 'success' }
  }
  if (/inviato/.test(status)) {
    return { label: 'Deposito inviato', body: 'Il deposito è registrato: verifica l’arrivo delle ricevute PEC.', tone: 'primary' }
  }
  return { label: 'Deposito da verificare', body: 'Apri il flusso PEC per controllare accettazione, consegna, controlli e conferma.', tone: 'neutral' }
}

function DepositReceiptSteps({ dep }:{dep:FascicoloDeposit}) {
  const visible = dep.simulated || dep.receiptSteps.some((step) => step.done)
  if (!visible || !dep.receiptSteps.length) return null
  return (
    <div className="iu-fas-receipt-steps" aria-label="Stato ricevute deposito">
      {dep.receiptSteps.map((step) => (
        <span className={step.done ? 'is-done' : ''} key={`${dep.id}-${step.id}`}>
          {step.done ? <CheckCircle2 size={13}/> : <Clock3 size={13}/>}
          {step.label}
        </span>
      ))}
    </div>
  )
}

function DepositReceiptActions({ dep, onDone, onError }:{dep:FascicoloDeposit; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const done = dep.receiptSteps.length > 0 && dep.receiptSteps.every((step) => step.done)
  if (!dep.checkReceiptsAction && !dep.nextSimulationAction && !dep.simulated) return null
  return (
    <div className="iu-fas-comm-actions">
      {!dep.simulated && dep.checkReceiptsAction ? <PostAction action={dep.checkReceiptsAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={14}/> Controlla PEC</PostAction> : null}
      {dep.nextSimulationAction ? <PostAction action={dep.nextSimulationAction} tone="primary" onDone={onDone} onError={onError}><CheckCircle2 size={14}/> {depositNextSimulationLabel(dep)}</PostAction> : null}
      {dep.simulated ? <small>{done ? 'Prova senza invio reale completata' : 'Prova senza invio reale'}</small> : null}
      {!dep.simulated ? <small>La PEC viene sincronizzata automaticamente; usa il controllo manuale solo per anticipare.</small> : null}
    </div>
  )
}

function DepositStateSummary({ dep }:{dep:FascicoloDeposit}) {
  const summary = depositPhaseSummary(dep)
  const facts = [
    dep.roleNumber ? `RG ${dep.roleNumber}` : '',
    dep.externalId ? `IDBUSTA ${dep.externalId}` : '',
    dep.acceptedAt ? `Accettato il ${dep.acceptedAt}` : '',
    dep.acceptedBy ? `Da ${dep.acceptedBy}` : '',
    dep.registeredBy ? `Registrato da ${dep.registeredBy}` : '',
    dep.sourceMessageId ? `Messaggio deposito ${dep.sourceMessageId}` : '',
  ].filter(Boolean)
  return (
    <div className={`iu-fas-deposit-state iu-fas-deposit-state--${summary.tone}`}>
      <Badge tone={summary.tone}>{summary.label}</Badge>
      <span>{summary.body}</span>
      {facts.length ? <small>{facts.join(' - ')}</small> : null}
    </div>
  )
}

function buildDocumentSections(documents: FascicoloDocument[]): DocumentAutoSection[] {
  const grouped = new Map<string, FascicoloDocument[]>()
  for (const doc of documents) {
    const sectionId = documentAutoSectionId(doc)
    grouped.set(sectionId, [...(grouped.get(sectionId) || []), doc])
  }
  return documentAutoSectionOrder
    .map((section) => ({ ...section, documents: grouped.get(section.id) || [] }))
    .filter((section) => section.documents.length > 0)
}

function DocumentUploadWorkspace({
  data,
  onDone,
  onError,
}: {
  data: FascicoloDetailData
  onDone: (message?: string) => void
  onError: (message: string) => void
}) {
  const [files, setFiles] = useState<File[]>([])
  const [mode, setMode] = useState<'auto' | 'manuale'>('auto')
  const [busy, setBusy] = useState(false)
  if (!data.actions.uploadDocument) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    const selectedFiles = formData.getAll('files').filter((value): value is File => value instanceof File && Boolean(value.name))
    if (!selectedFiles.length) {
      onError('Seleziona almeno un documento da caricare.')
      return
    }
    setBusy(true)
    try {
      const result = await submitFormJson(data.actions.uploadDocument, formData)
      form.reset()
      setFiles([])
      setMode('auto')
      onDone(result.message || 'Documenti caricati.')
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Caricamento non riuscito.')
    } finally {
      setBusy(false)
    }
  }
  const typeOptions = data.options.documentTypes.length ? data.options.documentTypes : [{ value: 'ALTRO', label: 'Altro' }]
  return (
    <section className="iu-fas-doc-workspace" aria-label="Documenti e atti del fascicolo">
      <form className="iu-fas-doc-upload" onSubmit={submit} encType="multipart/form-data">
        <input type="hidden" name="classificazione_modalita" value={mode}/>
        <label className="iu-fas-field iu-fas-field--wide">
          <span>Carica documenti</span>
          <input
            type="file"
            name="files"
            multiple
            onChange={(event) => setFiles(Array.from(event.currentTarget.files || []))}
          />
          <small className="iu-fas-field-help">Puoi selezionare più file. IUSENTRA li classifica dal nome, oppure puoi scegliere il tipo per ogni documento.</small>
        </label>
        <label className="iu-fas-field">
          <span>Classificazione</span>
          <select value={mode} onChange={(event) => setMode(event.target.value as 'auto' | 'manuale')}>
            <option value="auto">Automatica</option>
            <option value="manuale">Manuale</option>
          </select>
        </label>
        <label className="iu-fas-field">
          <span>Data documento</span>
          <input type="date" name="data_documento"/>
        </label>
        <label className="iu-fas-field">
          <span>Etichette</span>
          <input name="tags" placeholder="urgenza, deposito, prova"/>
        </label>
        <label className="iu-fas-field">
          <span>Note</span>
          <input name="note" placeholder="Nota interna sul documento"/>
        </label>
        <label className="iu-fas-check-field">
          <input type="checkbox" name="firmato" value="1"/>
          <span>Già firmato</span>
        </label>
        {mode === 'manuale' ? (
          <div className="iu-fas-upload-preview" aria-label="Classificazione manuale dei file selezionati">
            {files.length ? files.map((file, index) => (
              <label key={`${file.name}-${index}`}>
                <span>{file.name}</span>
                <select name={`tipo_doc_${index}`} defaultValue="ALTRO">
                  {typeOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                </select>
              </label>
            )) : <p className="iu-empty">Seleziona uno o più file per assegnare il tipo documento.</p>}
          </div>
        ) : null}
        <button type="submit" disabled={busy}><UploadCloud size={15}/> {busy ? 'Caricamento...' : 'Carica documenti'}</button>
      </form>
    </section>
  )
}

function DocumentRow({ doc, onPreview, onDone, onError }:{doc:FascicoloDocument; onPreview:(preview:PreviewDocument)=>void; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(doc.name)
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameMessage, setRenameMessage] = useState('')
  const tags = visibleDocumentTags(doc)
  const catalogTone: FascicoloRow['tone'] =
    doc.catalogSection === 'atti' ? 'primary'
      : doc.catalogSection === 'provvedimenti' ? 'purple'
        : doc.catalogSection === 'comunicazioni' ? 'info'
          : doc.catalogSection === 'pagamenti' ? 'success'
            : doc.catalogSection === 'allegati' ? 'neutral'
              : 'warning'

  const startRename = () => {
    setDraftName(doc.name)
    setRenameMessage('')
    setRenaming(true)
  }

  const submitRename = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!doc.actions.rename || renameBusy) return
    const value = draftName.trim()
    if (!value) {
      setRenameMessage('Indica il nuovo nome del documento.')
      return
    }
    setRenameBusy(true)
    setRenameMessage('')
    const formData = new FormData()
    formData.set('nome_file', value)
    try {
      const response = await fetch(doc.actions.rename, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken(),
        },
        body: formData,
      })
      const payload = await response.json().catch(() => ({})) as Record<string, unknown>
      const message = String(payload.message || payload.messaggio || '')
      if (!response.ok || payload.ok === false) throw new Error(message || 'Rinomina non completata.')
      setRenaming(false)
      onDone(message || 'Nome documento aggiornato.')
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Rinomina non completata.'
      setRenameMessage(message)
      onError(message)
    } finally {
      setRenameBusy(false)
    }
  }

  return (
    <article className="iu-fas-doc-row">
      <div className="iu-fas-doc-icon-cell">
        <FileText size={18}/>
        {doc.actions.rename ? (
          <button type="button" title="Rinomina file" aria-label={`Rinomina file ${doc.name}`} onClick={startRename}>
            <PencilLine size={13}/>
          </button>
        ) : null}
      </div>
      <div><strong>{doc.name}</strong><span>{doc.type} · {doc.size || 'dimensione n.d.'} · {doc.documentDate || doc.uploadedAt || 'data n.d.'}</span>{doc.notes ? <p>{doc.notes}</p> : null}{tags.length ? <em>{tags.join(', ')}</em> : null}</div>
      {renaming ? (
        <form className="iu-fas-doc-rename-form" onSubmit={submitRename}>
          <input value={draftName} onChange={(event) => setDraftName(event.currentTarget.value)} aria-label={`Nuovo nome file ${doc.name}`} />
          <button type="submit" disabled={renameBusy}>{renameBusy ? 'Salvo...' : 'Salva nome'}</button>
          <button type="button" onClick={() => setRenaming(false)} disabled={renameBusy}>Annulla</button>
          {renameMessage ? <small>{renameMessage}</small> : null}
        </form>
      ) : null}
      <div className="iu-fas-doc-badges"><Badge tone={doc.statusTone}>{doc.statusLabel || (doc.signed ? 'Firmato' : 'Da firmare')}</Badge>{doc.catalogLabel && doc.catalogConfidence >= 70 ? <Badge tone={catalogTone}>{doc.catalogLabel}</Badge> : null}{doc.source ? <Badge tone="neutral">{doc.source}</Badge> : null}{doc.portalClass ? <Badge tone="info">{doc.portalClass}</Badge> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {doc.actions.preview ? <button type="button" title="Anteprima interna" onClick={() => onPreview({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}><Eye size={15}/></button> : null}
        {doc.actions.download ? <a href={doc.actions.download} title="Scarica"><Download size={15}/></a> : null}
        {doc.actions.edit ? <a href={doc.actions.edit} title="Modifica documento" aria-label={`Modifica documento ${doc.name}`}><PencilLine size={15}/></a> : null}
        {doc.actions.sign ? <a href={doc.actions.sign} title="Firma digitale"><ShieldCheck size={15}/></a> : null}
        {doc.actions.attest ? <PostAction action={doc.actions.attest} tone="secondary" onDone={onDone} onError={onError}><BadgeCheck size={14}/></PostAction> : null}
        {doc.actions.pdfa ? <PostAction action={doc.actions.pdfa} tone="secondary" confirm="Convertire il documento in PDF/A-2B?" confirmTitle="Conversione PDF/A" onDone={onDone} onError={onError}><FileCheck2 size={14}/></PostAction> : null}
        {doc.actions.delete ? <PostAction action={doc.actions.delete} tone="danger" confirm="Eliminare il documento dal fascicolo?" confirmTitle="Elimina documento" onDone={onDone} onError={onError}><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

type DocumentFlowMode = 'notifica' | 'deposito'

function documentFlowTitle(mode: DocumentFlowMode): string {
  return mode === 'deposito' ? 'Prepara deposito telematico' : 'Prepara notifica'
}

function documentFlowPrimaryLabel(mode: DocumentFlowMode): string {
  return mode === 'deposito' ? 'Continua al deposito' : 'Continua alla notifica'
}

function appendSelectedDocumentsToHref(href: string, documentIds: string[]): string {
  if (!documentIds.length) return href
  try {
    const base = typeof window !== 'undefined' ? window.location.origin : 'https://app.iusentra.it'
    const parsed = new URL(href, base)
    parsed.searchParams.set('documenti', documentIds.join(','))
    return `${parsed.pathname}${parsed.search}${parsed.hash}`
  } catch {
    const separator = href.includes('?') ? '&' : '?'
    return `${href}${separator}documenti=${encodeURIComponent(documentIds.join(','))}`
  }
}

function isNotificationSelectableDocument(doc: FascicoloDocument): boolean {
  const name = doc.name || ''
  const text = normaliseText(`${doc.name} ${doc.type} ${doc.rawType} ${doc.catalogLabel} ${doc.catalogRole} ${doc.notes} ${doc.tags.join(' ')}`)
  if (/\.(eml|msg)$/i.test(name)) return false
  if (/\.(pdf|pdfa|p7m)$/i.test(name)) return true
  return /(atto|ricorso|procura|decreto|sentenza|provvedimento|contratto|relata|documento)/.test(text)
}

function documentFlowDateTimestamp(value: string): number {
  const raw = value.trim()
  if (!raw) return 0

  const italian = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/)
  if (italian) {
    const [, day, month, year, hour = '0', minute = '0', second = '0'] = italian
    return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second))
  }

  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?/)
  if (iso) {
    const [, year, month, day, hour = '0', minute = '0', second = '0'] = iso
    return Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second))
  }

  const parsed = Date.parse(raw)
  return Number.isFinite(parsed) ? parsed : 0
}

function documentFlowDocumentTimestamp(doc: FascicoloDocument): number {
  return documentFlowDateTimestamp(doc.documentDate)
    || documentFlowDateTimestamp(doc.uploadedAt)
    || documentFlowDateTimestamp(doc.portalDate)
}

function compareDocumentFlowByRecentDate(a: FascicoloDocument, b: FascicoloDocument): number {
  const byDate = documentFlowDocumentTimestamp(b) - documentFlowDocumentTimestamp(a)
  if (byDate !== 0) return byDate
  return normaliseText(a.name).localeCompare(normaliseText(b.name), 'it')
}

function DocumentFlowSelectionModal({
  mode,
  documents,
  loading,
  baseHref,
  onClose,
}: {
  mode: DocumentFlowMode
  documents: FascicoloDocument[]
  loading: boolean
  baseHref: string
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const documentSignature = documents.map((doc) => doc.id).join('|')
  useEffect(() => {
    setQuery('')
    setSelectedIds([])
  }, [documentSignature, mode])
  const sortedDocuments = useMemo(() => [...documents].sort(compareDocumentFlowByRecentDate), [documents])
  const visibleDocuments = useMemo(() => {
    const tokens = normaliseText(query).split(' ').filter(Boolean)
    if (!tokens.length) return sortedDocuments
    return sortedDocuments.filter((doc) => {
      const search = normaliseText(`${doc.name} ${doc.type} ${doc.rawType} ${doc.catalogLabel} ${doc.source} ${doc.tags.join(' ')}`)
      return tokens.every((token) => search.includes(token))
    })
  }, [query, sortedDocuments])
  const suggestedIds = useMemo(() => sortedDocuments
    .filter((doc) => mode === 'deposito' ? (doc.depositCandidate || isDepositCandidateDocument(doc) || isDepositManualSelectableDocument(doc)) : isNotificationSelectableDocument(doc))
    .map((doc) => doc.id)
    .filter(Boolean), [mode, sortedDocuments])
  const selectedDocuments = sortedDocuments.filter((doc) => selectedIds.includes(doc.id))
  const targetHref = appendSelectedDocumentsToHref(baseHref, selectedIds)
  const toggleDocument = (doc: FascicoloDocument, checked: boolean) => {
    setSelectedIds((current) => checked
      ? Array.from(new Set([...current, doc.id]))
      : current.filter((id) => id !== doc.id))
  }
  return (
    <div className="iu-fas-document-flow-modal" role="dialog" aria-modal="true" aria-label={documentFlowTitle(mode)}>
      <section className="iu-fas-document-flow-modal__box">
        <header>
          <div className="iu-fas-preview-modal__title">
            <span><FileText size={14}/> Documenti del fascicolo</span>
            <strong>{documentFlowTitle(mode)}</strong>
          </div>
          <button type="button" onClick={onClose} aria-label="Chiudi selezione documenti"><X size={16}/> Chiudi</button>
        </header>
        <div className="iu-fas-document-flow-toolbar">
          <label>
            <Search size={16}/>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.currentTarget.value)}
              placeholder="Cerca documento, tipo o tag"
            />
          </label>
          <button type="button" onClick={() => setSelectedIds(suggestedIds)} disabled={!suggestedIds.length}>
            <CheckCircle2 size={15}/> Seleziona proposti
          </button>
          <button type="button" onClick={() => setSelectedIds([])} disabled={!selectedIds.length}>
            <Trash2 size={15}/> Svuota
          </button>
        </div>
        <div className="iu-fas-document-flow-summary">
          <strong>{selectedIds.length ? `${selectedIds.length} documenti selezionati` : 'Nessun documento selezionato'}</strong>
          <span>{selectedIds.length ? 'La pagina successiva riceverà solo questi documenti come perimetro iniziale.' : 'Documenti ordinati dal più recente: puoi continuare senza selezione oppure scegliere i file da usare.'}</span>
        </div>
        <div className="iu-fas-document-flow-list">
          {loading ? <p className="iu-empty">Caricamento documenti del fascicolo...</p> : null}
          {!loading && visibleDocuments.map((doc) => (
            <label className="iu-fas-document-flow-row" key={doc.id}>
              <input
                type="checkbox"
                checked={selectedIds.includes(doc.id)}
                onChange={(event) => toggleDocument(doc, event.currentTarget.checked)}
              />
              <span>
                <strong>{doc.name}</strong>
                <small>{[doc.type, doc.documentDate || doc.uploadedAt, doc.statusLabel].filter(Boolean).join(' · ')}</small>
                {doc.notes ? <em>{doc.notes}</em> : null}
              </span>
            </label>
          ))}
          {!loading && !visibleDocuments.length ? <p className="iu-empty">Nessun documento corrisponde alla ricerca.</p> : null}
        </div>
        <footer>
          <a className="iu-button iu-button--secondary" href={baseHref}>Apri senza selezione</a>
          <a className="iu-button iu-button--primary" href={targetHref}>
            <Send size={15}/> {documentFlowPrimaryLabel(mode)}
          </a>
        </footer>
        {selectedDocuments.length ? (
          <div className="iu-fas-document-flow-selected" aria-label="Documenti scelti">
            {selectedDocuments.slice(0, 5).map((doc) => <span key={`chosen-${doc.id}`}>{doc.name}</span>)}
            {selectedDocuments.length > 5 ? <span>+{selectedDocuments.length - 5} altri</span> : null}
          </div>
        ) : null}
      </section>
    </div>
  )
}

type LocalSignerToken = { slot_id?: number | string; label?: string; manufacturer?: string; model?: string; serial?: string }
type LocalSignerWindowsCertificate = {
  thumbprint?: string
  soggetto?: string
  soggetto_completo?: string
  emittente?: string
  emittente_completo?: string
  scadenza?: string
  codice_fiscale?: string
  auto_selezionato?: boolean
}
type LocalSignerStatus = {
  ok?: boolean
  token?: LocalSignerToken[]
  token_probe_fresh?: LocalSignerToken[]
  certificato_windows_firma_selezionato?: LocalSignerWindowsCertificate
  certificato_windows_selezionato?: LocalSignerWindowsCertificate
  versione?: string
  version?: string
  piattaforma?: string
  messaggio?: string
  error?: string
  errore_token?: string
  errore_libreria?: string
  riavvio_signer_consigliato?: boolean
  nota_riavvio_signer?: string
  __iusentra_base_url?: string
  __iusentra_probe_urls?: string[]
  __iusentra_last_error?: string
}
type LocalSignerRecoveryOptions = {
  onMessage?: (message: string) => void
}
type LocalNetworkRequestInit = RequestInit & { targetAddressSpace?: 'loopback' }
type FirmaInfo = {
  firme?: unknown[]
  nome?: string
  errore?: string
  signed_status?: Record<string, unknown>
  signed_ui?: { label?: string; tone?: FascicoloRow['tone']; detail?: string }
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize))
  }
  return btoa(binary)
}

function base64ToUint8Array(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  return bytes
}

const CMS_ENVELOPED_DATA_OID = [0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x07, 0x03]

function bytesIncludeSequence(bytes: Uint8Array, sequence: number[], limit = bytes.length): boolean {
  const end = Math.min(bytes.length, limit)
  if (!sequence.length || end < sequence.length) return false
  for (let index = 0; index <= end - sequence.length; index += 1) {
    let ok = true
    for (let offset = 0; offset < sequence.length; offset += 1) {
      if (bytes[index + offset] !== sequence[offset]) {
        ok = false
        break
      }
    }
    if (ok) return true
  }
  return false
}

function looksLikeCmsEnvelopedData(bytes: Uint8Array): boolean {
  return bytes.length > 128 && bytes[0] === 0x30 && bytesIncludeSequence(bytes, CMS_ENVELOPED_DATA_OID, 512)
}

function assertLocalPecAttoEncBase64(localPayload: Record<string, unknown>): void {
  const attachments = Array.isArray(localPayload.attachments) ? localPayload.attachments : []
  const attoEnc = attachments.find((item) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false
    return recordText(item as Record<string, unknown>, 'filename').toLowerCase() === 'atto.enc'
  })
  if (!attoEnc || typeof attoEnc !== 'object' || Array.isArray(attoEnc)) {
    throw new Error('Pacchetto deposito mancante. Rigenera la prova deposito prima dell’invio reale.')
  }
  const contentBase64 = recordText(attoEnc as Record<string, unknown>, 'content_base64').trim()
  if (!contentBase64) {
    throw new Error('Pacchetto deposito non leggibile. Rigenera la prova deposito prima dell’invio reale.')
  }
  let decoded: Uint8Array
  try {
    decoded = base64ToUint8Array(contentBase64)
  } catch {
    throw new Error('Pacchetto deposito non valido. Rigenera la prova deposito prima dell’invio reale.')
  }
  if (!decoded.length || !looksLikeCmsEnvelopedData(decoded)) {
    throw new Error('Pacchetto deposito non conforme. Rigenera la prova prima dell’invio reale.')
  }
  if (!recordBool(attoEnc as Record<string, unknown>, 'ministerial_busta_verified')) {
    throw new Error('Pacchetto deposito non verificato. Ripeti Simula invio PEC prima dell’invio reale.')
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

const LOCAL_SIGNER_RESTART_URI = 'iusentra-local-signer://restart'
const LOCAL_SIGNER_UPDATE_URI = 'iusentra-local-signer://update'
const LOCAL_SIGNER_BATCH_TIMEOUT_MS = 45000
const LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS = 9000
const LOCAL_SIGNER_DEFAULT_BASE_URLS = ['http://127.0.0.1:27272', 'http://localhost:27272']

function isDesktopLocalSignerHost(): boolean {
  if (typeof navigator === 'undefined') return true
  const userAgent = String(navigator.userAgent || '').toLowerCase()
  const platformName = String(navigator.platform || '').toLowerCase()
  const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent)
  const isIpadDesktopMode = platformName.includes('mac') && Number(navigator.maxTouchPoints || 0) > 1
  return !isMobileOrTablet && !isIpadDesktopMode
}

function canRequestLocalSignerProtocol(): boolean {
  if (!isDesktopLocalSignerHost()) return false
  if (typeof navigator === 'undefined') return true
  const activation = (navigator as Navigator & { userActivation?: { isActive?: boolean } }).userActivation
  return activation?.isActive !== false
}

function requestLocalSignerStart(): boolean {
  if (!canRequestLocalSignerProtocol()) return false
  const link = document.createElement('a')
  link.href = LOCAL_SIGNER_RESTART_URI
  link.rel = 'noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => link.remove(), 1500)
  return true
}

function requestLocalSignerUpdate(): boolean {
  if (!canRequestLocalSignerProtocol()) return false
  const link = document.createElement('a')
  link.href = LOCAL_SIGNER_UPDATE_URI
  link.rel = 'noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => link.remove(), 1500)
  return true
}

function localSignerTokenLabel(token?: LocalSignerToken): string {
  if (!token) return ''
  return [token.label, token.manufacturer, token.model].filter(Boolean).join(' - ') || 'Dispositivo USB'
}

function localSignerWindowsCertificate(status?: LocalSignerStatus | null): LocalSignerWindowsCertificate | null {
  const cert = status?.certificato_windows_firma_selezionato || status?.certificato_windows_selezionato
  return cert?.thumbprint ? cert : null
}

function localSignerWindowsCertificateLabel(cert?: LocalSignerWindowsCertificate | null): string {
  if (!cert) return ''
  return cert.soggetto || cert.soggetto_completo || 'Certificato Windows'
}

type VisibleSignatureMode = 'laterale' | 'basso_sinistra' | 'basso_destra'
const visibleSignatureOptions: Array<{ value: VisibleSignatureMode; label: string }> = [
  { value: 'laterale', label: 'Laterale verticale' },
  { value: 'basso_sinistra', label: 'In basso a sinistra' },
  { value: 'basso_destra', label: 'In basso a destra' },
]
type VisibleSignatureDatetimeMode = 'data_ora' | 'solo_data' | 'nessuna'
const visibleSignatureDatetimeOptions: Array<{ value: VisibleSignatureDatetimeMode; label: string }> = [
  { value: 'data_ora', label: 'Data e ora' },
  { value: 'solo_data', label: 'Solo data' },
  { value: 'nessuna', label: 'Senza data' },
]
const visibleSignatureStorageKey = 'hacs.firma_visibile.mode'
const visibleSignatureDatetimeStorageKey = 'hacs.firma_visibile.data_ora'

declare global {
  interface Window {
    __IUSENTRA_LOCAL_SIGNER_URL__?: string
    __IUSENTRA_LOCAL_SIGNER_LATEST_VERSION__?: string
  }
}

function normalizeLocalSignerBaseUrl(value?: string): string {
  return String(value || '').trim().replace(/\/+$/, '')
}

function localSignerCandidateBaseUrls(): string[] {
  const configured = typeof window !== 'undefined' ? normalizeLocalSignerBaseUrl(window.__IUSENTRA_LOCAL_SIGNER_URL__) : ''
  const urls = configured ? [configured, ...LOCAL_SIGNER_DEFAULT_BASE_URLS] : LOCAL_SIGNER_DEFAULT_BASE_URLS
  return Array.from(new Set(urls.map((url) => normalizeLocalSignerBaseUrl(url)).filter(Boolean)))
}

function localSignerBaseUrl(): string {
  return localSignerCandidateBaseUrls()[0] || LOCAL_SIGNER_DEFAULT_BASE_URLS[0]
}

function localSignerEndpoint(path: string, baseUrl = localSignerBaseUrl()): string {
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${normalizeLocalSignerBaseUrl(baseUrl)}${suffix}`
}

function localSignerStatusBaseUrl(status?: LocalSignerStatus | null): string {
  return normalizeLocalSignerBaseUrl(status?.__iusentra_base_url) || localSignerBaseUrl()
}

function localSignerEndpointForStatus(path: string, status?: LocalSignerStatus | null): string {
  return localSignerEndpoint(path, localSignerStatusBaseUrl(status))
}

function localSignerEndpointForPayload(endpoint: string, path: string, status?: LocalSignerStatus | null): string {
  const fallback = localSignerEndpointForStatus(path, status)
  const raw = String(endpoint || '').trim()
  if (!raw) return fallback
  try {
    const parsed = new URL(raw)
    if (['127.0.0.1', 'localhost'].includes(parsed.hostname) && (!parsed.port || parsed.port === '27272')) {
      return `${localSignerStatusBaseUrl(status)}${parsed.pathname}${parsed.search}${parsed.hash}`
    }
  } catch {
    return raw
  }
  return raw
}

function localSignerProbeFailureMessage(status: LocalSignerStatus | null | undefined, action: string): string {
  const probes = Array.isArray(status?.__iusentra_probe_urls) ? status?.__iusentra_probe_urls?.join(', ') : ''
  const detail = String(status?.__iusentra_last_error || status?.messaggio || status?.error || '').trim()
  const suffix = [probes ? `Endpoint provati: ${probes}.` : '', detail ? `Dettaglio browser: ${detail}.` : ''].filter(Boolean).join(' ')
  return `Local Signer non raggiungibile dal browser per ${action}. Avvia il servizio locale sul PC in uso e ripeti la prova deposito.${suffix ? ` ${suffix}` : ''}`
}

function localSignerLatestVersion(): string {
  if (typeof window === 'undefined') return ''
  const configured = window.__IUSENTRA_LOCAL_SIGNER_LATEST_VERSION__
  const monitor = document.getElementById('iusentra-local-signer-monitor') as HTMLElement | null
  return String(configured || monitor?.dataset.latestVersion || '').trim()
}

function compareLocalSignerVersions(left: string, right: string): number {
  const parse = (value: string) => String(value || '').split('.').map((part) => Number.parseInt(part, 10) || 0)
  const a = parse(left)
  const b = parse(right)
  const max = Math.max(a.length, b.length)
  for (let index = 0; index < max; index += 1) {
    const delta = (a[index] || 0) - (b[index] || 0)
    if (delta !== 0) return delta
  }
  return 0
}

function localSignerInstalledVersion(status?: LocalSignerStatus | null): string {
  return String(status?.versione || status?.version || '').trim()
}

function localSignerStatusOutdated(status?: LocalSignerStatus | null): boolean {
  const latest = localSignerLatestVersion()
  const installed = localSignerInstalledVersion(status)
  return Boolean(latest && installed && compareLocalSignerVersions(installed, latest) < 0)
}

function localSignerNeedsRestart(status?: LocalSignerStatus | null): boolean {
  return Boolean((status?.token_probe_fresh?.length && !status?.token?.length) || (status?.riavvio_signer_consigliato && !status?.token?.length))
}

function localSignerStatusCanSign(status?: LocalSignerStatus | null): boolean {
  return Boolean((status?.token?.[0] || localSignerWindowsCertificate(status)) && !localSignerNeedsRestart(status) && !localSignerStatusOutdated(status))
}

async function fetchLocalSignerStatus(timeoutMs = 3500): Promise<LocalSignerStatus | null> {
  const candidateBaseUrls = localSignerCandidateBaseUrls()
  const candidateEndpoints = candidateBaseUrls.length
    ? candidateBaseUrls.map((baseUrl) => ({ baseUrl, endpoint: localSignerEndpoint('/ping', baseUrl) }))
    : [{ baseUrl: localSignerBaseUrl(), endpoint: localSignerEndpoint('/ping') }]
  let lastError = ''
  for (const candidate of candidateEndpoints) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
    try {
      const requestOptions: LocalNetworkRequestInit = {
        cache: 'no-store',
        mode: 'cors',
        targetAddressSpace: 'loopback',
        signal: controller.signal,
      }
      const response = await fetch(candidate.endpoint, requestOptions)
      const payload = await response.json().catch(() => ({} as LocalSignerStatus))
      return {
        ...payload,
        ok: response.ok ? payload.ok : false,
        __iusentra_base_url: candidate.baseUrl,
        __iusentra_probe_urls: candidateEndpoints.map((item) => item.endpoint),
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error || '')
    } finally {
      window.clearTimeout(timeout)
    }
  }
  return {
    ok: false,
    messaggio: 'Local Signer non rilevato su questo PC.',
    __iusentra_base_url: localSignerBaseUrl(),
    __iusentra_probe_urls: candidateEndpoints.map((item) => item.endpoint),
    __iusentra_last_error: lastError,
  }
}

async function pollLocalSignerStatus(
  attempts = 10,
  delayMs = 900,
  minimumVersion = '',
  maxDurationMs = 0,
): Promise<LocalSignerStatus | null> {
  const startedAt = Date.now()
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (maxDurationMs > 0 && Date.now() - startedAt >= maxDurationMs) break
    if (attempt > 0) await sleep(delayMs)
    const payload = await fetchLocalSignerStatus(minimumVersion ? 1500 : 3500)
    const installedVersion = localSignerInstalledVersion(payload)
    if (
      payload
      && payload.ok !== false
      && (!minimumVersion || (installedVersion && compareLocalSignerVersions(installedVersion, minimumVersion) >= 0))
    ) return payload
  }
  return null
}

async function recoverLocalSignerAutomatically(
  status: LocalSignerStatus,
  options: LocalSignerRecoveryOptions = {},
): Promise<LocalSignerStatus> {
  if (localSignerStatusOutdated(status)) {
    const latest = localSignerLatestVersion()
    const installed = localSignerInstalledVersion(status)
    options.onMessage?.(`Local Signer ${installed || 'installato'} da aggiornare alla versione ${latest}. IUSENTRA avvia l'aggiornamento automatico e ricontrolla il servizio.`)
    try {
      const updateRequestOptions: LocalNetworkRequestInit = {
        method: 'POST',
        cache: 'no-store',
        mode: 'cors',
        targetAddressSpace: 'loopback',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: window.location.origin }),
      }
      const updateResponse = await fetch(localSignerEndpointForStatus('/update', status), updateRequestOptions)
      const updatePayload = await updateResponse.json().catch(() => ({} as Record<string, unknown>))
      if (!updateResponse.ok || updatePayload.ok === false) throw new Error('Aggiornamento locale non avviato')
    } catch {
      requestLocalSignerUpdate()
    }
    const updated = await pollLocalSignerStatus(240, 1500, latest, 360000)
    return updated || status
  }
  if (localSignerNeedsRestart(status)) {
    options.onMessage?.('IUSENTRA sta riallineando automaticamente Local Signer perché il dispositivo di firma è stato rilevato da un controllo fresco.')
    requestLocalSignerStart()
    const restarted = await pollLocalSignerStatus(12, 900)
    return restarted || status
  }
  return status
}

function normalizeVisibleSignatureMode(value?: string): VisibleSignatureMode {
  const raw = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
  if (['bottom_left', 'left', 'sinistra', 'sx', 'basso_sx'].includes(raw)) return 'basso_sinistra'
  if (['bottom_right', 'right', 'destra', 'dx', 'basso_dx'].includes(raw)) return 'basso_destra'
  if (['laterale', 'side', 'verticale', 'margine', 'margine_destro', 'laterale_dx'].includes(raw)) return 'laterale'
  return raw === 'basso_sinistra' || raw === 'basso_destra' ? raw : 'laterale'
}

function normalizeVisibleSignatureDatetimeMode(value?: string): VisibleSignatureDatetimeMode {
  const raw = String(value || '').trim().toLowerCase().replace(/[-\s]+/g, '_')
  if (['solo_data', 'data', 'date', 'giorno'].includes(raw)) return 'solo_data'
  if (['nessuna', 'nessuno', 'none', 'off', 'senza_data', 'no'].includes(raw)) return 'nessuna'
  return 'data_ora'
}

function loadVisibleSignatureMode(defaultMode: string): VisibleSignatureMode {
  try {
    const stored = window.localStorage.getItem(visibleSignatureStorageKey)
    return normalizeVisibleSignatureMode(stored || defaultMode)
  } catch {
    return normalizeVisibleSignatureMode(defaultMode)
  }
}

function loadVisibleSignatureDatetimeMode(defaultMode: string): VisibleSignatureDatetimeMode {
  try {
    const stored = window.localStorage.getItem(visibleSignatureDatetimeStorageKey)
    return normalizeVisibleSignatureDatetimeMode(stored || defaultMode)
  } catch {
    return normalizeVisibleSignatureDatetimeMode(defaultMode)
  }
}

function SignaturePage({ id, documentId }:{id:string; documentId:string}) {
  const [data, setData] = useState<FascicoloDetailData>(emptyFascicoloDetail)
  const [loading, setLoading] = useState(true)
  const [info, setInfo] = useState<FirmaInfo | null>(null)
  const [localSigner, setLocalSigner] = useState<LocalSignerStatus | null>(null)
  const [checkingSigner, setCheckingSigner] = useState(false)
  const [pin, setPin] = useState('')
  const [confirmResign, setConfirmResign] = useState(false)
  const [visibleSignatureMode, setVisibleSignatureMode] = useState<VisibleSignatureMode>('laterale')
  const [visibleSignaturePlace, setVisibleSignaturePlace] = useState('')
  const [visibleSignatureDatetimeMode, setVisibleSignatureDatetimeMode] = useState<VisibleSignatureDatetimeMode>('data_ora')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const encodedId = encodeURIComponent(id)
  const encodedDocId = encodeURIComponent(documentId)
  const firmaUrl = `/fascicoli/${encodedId}/documenti/${encodedDocId}/firma`
  const infoUrl = `/api/fascicoli/${encodedId}/documenti/${encodedDocId}/info-firma`
  const detailUrl = `/fascicoli/${encodedId}#documenti`
  const doc = data.documents.find((item) => item.id === documentId)
  const primaryToken = localSigner?.token?.[0]
  const freshToken = localSigner?.token_probe_fresh?.[0]
  const selectedWindowsCertificate = localSignerWindowsCertificate(localSigner)
  const restartSuggested = localSignerNeedsRestart(localSigner)
  const displayToken = primaryToken || (restartSuggested ? freshToken : selectedWindowsCertificate ? undefined : freshToken)
  const signerRestartRequired = Boolean(restartSuggested && freshToken && !primaryToken)
  const localSignerReachable = Boolean(localSigner && localSigner.ok !== false && (localSigner.versione || localSigner.version || localSigner.piattaforma || localSigner.token || localSigner.token_probe_fresh || selectedWindowsCertificate))
  const localSignerOutdated = localSignerStatusOutdated(localSigner)
  const localSignerCanSign = localSignerStatusCanSign(localSigner)
  const localSignerVersion = localSigner?.versione || localSigner?.version || ''
  const localSignerStatusTitle = restartSuggested
    ? 'Dispositivo di firma rilevato, riallineamento automatico'
    : selectedWindowsCertificate
    ? 'Local Signer pronto con certificato Windows'
    : displayToken
    ? (localSignerOutdated ? 'Local Signer da aggiornare' : 'Local Signer rilevato')
    : localSignerReachable
      ? (localSignerOutdated ? 'Local Signer da aggiornare' : 'Local Signer attivo senza dispositivo di firma')
      : checkingSigner
        ? 'Verifica Local Signer...'
        : 'Local Signer non rilevato'
  const localSignerStatusMessage = restartSuggested
    ? localSigner?.nota_riavvio_signer || 'Il dispositivo di firma è stato rilevato da un controllo fresco. IUSENTRA sta riallineando Local Signer prima della firma.'
    : selectedWindowsCertificate
    ? `${localSignerWindowsCertificateLabel(selectedWindowsCertificate)}${selectedWindowsCertificate.scadenza ? ` - scadenza ${selectedWindowsCertificate.scadenza}` : ''}`
    : displayToken
    ? (localSignerOutdated
        ? `Versione rilevata ${localSignerVersion || 'non disponibile'}: IUSENTRA avvia l'aggiornamento automatico prima della firma.`
        : restartSuggested
        ? localSigner?.nota_riavvio_signer || 'Il dispositivo di firma è stato rilevato da un controllo fresco. IUSENTRA sta riallineando Local Signer prima della firma.'
        : `${localSignerTokenLabel(displayToken)} - lettore ${displayToken.slot_id}`)
    : localSignerReachable
      ? localSigner?.errore_token || localSigner?.errore_libreria || localSigner?.messaggio || 'Servizio locale attivo, ma nessun dispositivo di firma disponibile.'
      : localSigner?.messaggio || localSigner?.error || 'Usa Riallinea automaticamente per avviare il Local Signer dal PC in uso.'
  const signatureCount = info?.firme?.length || 0
  const alreadySigned = Boolean(doc?.signed || signatureCount > 0)
  const setVisibleSignatureChoice = (mode: VisibleSignatureMode) => {
    const normalized = normalizeVisibleSignatureMode(mode)
    setVisibleSignatureMode(normalized)
    try {
      window.localStorage.setItem(visibleSignatureStorageKey, normalized)
    } catch {
      // La preferenza locale e' un aiuto UX, non deve bloccare la firma.
    }
  }

  const setVisibleSignatureDatetimeChoice = (mode: VisibleSignatureDatetimeMode) => {
    const normalized = normalizeVisibleSignatureDatetimeMode(mode)
    setVisibleSignatureDatetimeMode(normalized)
    try {
      window.localStorage.setItem(visibleSignatureDatetimeStorageKey, normalized)
    } catch {
      // La preferenza locale e' un aiuto UX, non deve bloccare la firma.
    }
  }

  const scheduleLocalSignerRestartCheck = () => {
    setError('')
    setMessage('IUSENTRA sta riallineando automaticamente Local Signer e ricontrolla il dispositivo di firma.')
    requestLocalSignerStart()
    for (const delay of [2500, 5000, 8500, 12000]) {
      window.setTimeout(() => { void checkLocalSigner(false) }, delay)
    }
  }

  const refreshInfo = () => {
    fetch(infoUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((response) => response.json())
      .then((payload) => setInfo(payload as FirmaInfo))
      .catch(() => setInfo({ errore: 'Stato firma non disponibile.' }))
  }

  const checkLocalSigner = async (tryStart = false): Promise<LocalSignerStatus | null> => {
    setCheckingSigner(true)
    setError('')
    if (tryStart) {
      setMessage('IUSENTRA sta avviando e verificando automaticamente Local Signer su questo PC.')
      requestLocalSignerStart()
    }
    const attempts = tryStart ? 10 : 1
    try {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        if (attempt > 0) await sleep(900)
        const payload = await fetchLocalSignerStatus()
        if (payload) {
          const next = await recoverLocalSignerAutomatically(payload, { onMessage: setMessage })
          setLocalSigner(next)
          if (localSignerStatusCanSign(next)) setMessage('')
          return next
        } else {
          if (attempt === attempts - 1) {
            setLocalSigner({ ok: false, messaggio: 'Local Signer non rilevato su questo PC.' })
          }
        }
      }
      return null
    } finally {
      setCheckingSigner(false)
    }
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getFascicoloDetail(id, { include: 'all' }).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  useEffect(() => {
    const settings = data.signature
    setVisibleSignatureMode(loadVisibleSignatureMode(settings?.visibleSignatureMode || 'laterale'))
    setVisibleSignaturePlace(settings?.visibleSignaturePlace || '')
    setVisibleSignatureDatetimeMode(loadVisibleSignatureDatetimeMode(settings?.visibleSignatureDatetimeMode || 'data_ora'))
  }, [data.signature?.visibleSignatureMode, data.signature?.visibleSignaturePlace, data.signature?.visibleSignatureDatetimeMode])

  useEffect(() => {
    refreshInfo()
    checkLocalSigner(false)
  }, [infoUrl])

  const firmaConLocalSigner = async () => {
    if (!doc) return
    if (restartSuggested || localSignerOutdated) {
      const next = await checkLocalSigner(true)
      if (!localSignerStatusCanSign(next)) {
        setError('IUSENTRA ha tentato il riallineamento automatico del Local Signer. Il PIN verrà richiesto solo quando il dispositivo sarà pronto per la firma.')
      }
      return
    }
    if (!selectedWindowsCertificate && !primaryToken?.slot_id && primaryToken?.slot_id !== 0) {
      const next = await checkLocalSigner(true)
      if (!localSignerStatusCanSign(next)) {
        setError('Local Signer non ha restituito un dispositivo di firma utilizzabile. Se il dispositivo fisico è inserito, IUSENTRA ha già tentato avvio, aggiornamento e riverifica.')
      }
      return
    }
    if (!pin.trim()) {
      setError('Inserisci il PIN nel pannello Local Signer. Il PIN resta sul PC e non viene salvato.')
      return
    }
    setBusy(true)
    setError('')
    setMessage('Firma in corso tramite Local Signer...')
    try {
      const downloadResponse = await fetch(doc.actions.download, { credentials: 'same-origin' })
      if (!downloadResponse.ok) throw new Error(`Download documento non riuscito: HTTP ${downloadResponse.status}`)
      const sourceBuffer = await downloadResponse.arrayBuffer()
      const signRequestOptions: LocalNetworkRequestInit = {
        method: 'POST',
        mode: 'cors',
        targetAddressSpace: 'loopback',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          documento: arrayBufferToBase64(sourceBuffer),
          pin,
          slot_id: primaryToken?.slot_id,
          cert_thumbprint: selectedWindowsCertificate?.thumbprint,
          visible_signature_mode: visibleSignatureMode,
          visible_signature_place: visibleSignaturePlace,
          visible_signature_datetime_mode: visibleSignatureDatetimeMode,
        }),
      }
      const signResponse = await fetch(localSignerEndpointForStatus('/firma', localSigner), signRequestOptions)
      const signedPayload = await parseLocalSignerResponse(signResponse)
      if (!signResponse.ok || !signedPayload.ok) {
        throw new Error(String(signedPayload.errore || signedPayload.messaggio || `Firma non riuscita: HTTP ${signResponse.status}`))
      }
      const signedBytes = base64ToUint8Array(String(signedPayload.firmato_b64 || ''))
      if (!signedBytes.length) throw new Error('Local Signer non ha restituito il file firmato.')
      const form = new FormData()
      const signedName = doc.name.toLowerCase().endsWith('.p7m') ? doc.name : `${doc.name}.p7m`
      const signedBuffer = new ArrayBuffer(signedBytes.byteLength)
      new Uint8Array(signedBuffer).set(signedBytes)
      form.append('file', new File([signedBuffer], signedName, { type: 'application/pkcs7-mime' }))
      form.append('note', 'Versione firmata tramite Local Signer')
      form.append('visible_signature_mode', visibleSignatureMode)
      form.append('visible_signature_place', visibleSignaturePlace)
      form.append('visible_signature_datetime_mode', visibleSignatureDatetimeMode)
      if (alreadySigned && confirmResign) form.append('confirm_resign', '1')
      const uploadResponse = await fetch(firmaUrl, {
        method: 'POST',
        body: form,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
      const uploadPayload = await uploadResponse.json().catch(() => ({}))
      if (!uploadResponse.ok || uploadPayload.ok === false) {
        throw new Error(String(uploadPayload.messaggio || `Caricamento firma non riuscito: HTTP ${uploadResponse.status}`))
      }
      setPin('')
      setMessage(String(uploadPayload.messaggio || 'Documento firmato e registrato correttamente.'))
      refreshInfo()
      getFascicoloDetail(id, { include: 'all' }).then(setData)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
      setMessage('')
    } finally {
      setBusy(false)
    }
  }

  if (!loading && data.notFound) {
    const requestError = data.requestError || ''
    return (
      <main className="iu-content iu-fascicoli-page">
        <EmptyState icon={<ShieldCheck size={34}/>} title={requestError ? 'Dati fascicolo non caricati' : 'Fascicolo non disponibile'} action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>
          {requestError || 'Il fascicolo non è disponibile o non hai i permessi per aprire la firma del documento.'}
        </EmptyState>
      </main>
    )
  }

  if (!loading && !doc) {
    return (
      <main className="iu-content iu-fascicoli-page">
        <EmptyState icon={<FileText size={34}/>} title="Documento non trovato" action={<Button href={detailUrl}>Torna ai documenti</Button>}>
          Il documento richiesto non risulta collegato al fascicolo.
        </EmptyState>
      </main>
    )
  }

  return (
    <main className="iu-content iu-fascicoli-page iu-fascicolo-signature-page">
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div>
          <span className="iu-fas-eyebrow"><ShieldCheck size={16}/> Firma documento</span>
          <h1>{doc?.name || 'Documento in caricamento'}</h1>
          <p><Badge tone={doc?.signed ? 'success' : 'warning'}>{doc?.signed ? 'Firmato' : 'Da firmare'}</Badge><span>{data.fascicolo.ref} - {data.fascicolo.client}</span></p>
        </div>
        <div className="iu-fas-hero__actions">
          <Button href={detailUrl}><ArrowLeft size={15}/> Torna al fascicolo</Button>
          {doc?.actions.preview ? <Button href={doc.actions.preview}><Eye size={15}/> Anteprima</Button> : null}
          {doc?.actions.download ? <Button variant="primary" href={doc.actions.download}><Download size={15}/> Scarica originale</Button> : null}
        </div>
      </section>

      {message ? <section className="iu-fas-signature-alert iu-fas-signature-alert--ok"><CheckCircle2 size={18}/><span>{message}</span></section> : null}
      {error ? <section className="iu-fas-signature-alert iu-fas-signature-alert--error"><ShieldCheck size={18}/><span>{error}</span></section> : null}
      {alreadySigned ? (
        <section className="iu-fas-signature-alert iu-fas-signature-alert--warning">
          <ShieldCheck size={18}/>
          <span>
            <strong>Attenzione: documento già firmato.</strong> Se continui rischi di corrompere il file o di creare
            una versione firmata non valida. Procedi solo se devi sostituire consapevolmente il file firmato.
          </span>
        </section>
      ) : null}

      <section className="iu-fas-signature-grid">
        <Panel title="Documento" subtitle="Dati operativi del fascicolo" icon={<FileText size={17}/>}>
          <KvGrid items={[
            { label: 'Nome', value: doc?.name || 'n.d.' },
            { label: 'Tipo', value: doc?.type || 'n.d.' },
            { label: 'Dimensione', value: doc?.size || 'n.d.' },
            { label: 'Data documento', value: doc?.documentDate || doc?.uploadedAt || 'n.d.' },
            { label: 'Impronta', value: doc?.hash || 'n.d.', mono: true },
            { label: 'Fonte', value: doc?.source || 'Studio' },
          ]}/>
        </Panel>

        <Panel title="Modalità firma visibile nel PDF" subtitle="Impostazioni e firma sul PC dell'avvocato" icon={<ShieldCheck size={17}/>} action={<button className="iu-fas-mini-action" type="button" onClick={() => checkLocalSigner(false)} disabled={checkingSigner}><RefreshCw size={14}/> Riverifica</button>}>
          <div className="iu-fas-signature-box">
            <div className="iu-fas-visible-signature">
              <strong>Modalità firma visibile nel PDF</strong>
              <small>Scegli come mostrare la dicitura grafica sul PDF. La validità legale resta nella firma digitale.</small>
              <span>Posizione firma visibile</span>
              <div>
                {visibleSignatureOptions.map((option) => (
                  <label key={option.value}>
                    <input type="radio" name="firma_visibile_mode" value={option.value} checked={visibleSignatureMode === option.value} onChange={() => setVisibleSignatureChoice(option.value)}/>
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
              <label className="iu-fas-field iu-fas-visible-signature-field">
                <span>Luogo firma</span>
                <input type="text" value={visibleSignaturePlace} onChange={(event) => setVisibleSignaturePlace(event.target.value)} placeholder="Luogo da mostrare nel timbro" maxLength={48}/>
              </label>
              <span>Data e orario nel timbro</span>
              <div>
                {visibleSignatureDatetimeOptions.map((option) => (
                  <label key={option.value}>
                    <input type="radio" name="firma_visibile_data_ora" value={option.value} checked={visibleSignatureDatetimeMode === option.value} onChange={() => setVisibleSignatureDatetimeChoice(option.value)}/>
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className={`iu-fas-signer-status ${localSignerCanSign ? 'is-ok' : 'is-warn'}`}>
              <strong>{localSignerStatusTitle}</strong>
              <span>{depositUserFacingMessage(localSignerStatusMessage)}</span>
              {displayToken && signerRestartRequired ? <small>{localSignerTokenLabel(displayToken)} - lettore {displayToken.slot_id}</small> : null}
              {selectedWindowsCertificate?.codice_fiscale ? <small>Codice fiscale certificato {selectedWindowsCertificate.codice_fiscale}</small> : null}
              {localSignerVersion ? <small>Versione {localSignerVersion}</small> : null}
            </div>
            {restartSuggested || localSignerOutdated || !localSignerReachable ? (
              <div className="iu-fas-signer-actions">
                <a className="iu-fas-mini-action iu-fas-mini-action--restart" href={LOCAL_SIGNER_RESTART_URI} onClick={scheduleLocalSignerRestartCheck}>
                  <RefreshCw size={14}/> Riallinea automaticamente
                </a>
                <button className="iu-fas-mini-action" type="button" onClick={() => checkLocalSigner(false)} disabled={checkingSigner}>
                  <RefreshCw size={14}/> Riverifica
                </button>
                {localSignerReachable ? <a className="iu-fas-mini-action" href={localSignerEndpoint('/diagnosi')} target="_blank" rel="noreferrer">Diagnosi locale</a> : null}
              </div>
            ) : null}
            <label className="iu-fas-field">
              <span>PIN dispositivo <b>*</b></span>
              <input type="password" value={pin} onChange={(event) => setPin(event.target.value)} autoComplete="off" placeholder="Il PIN non viene salvato" disabled={!localSignerCanSign}/>
            </label>
            {alreadySigned ? (
              <label className="iu-fas-resign-confirm">
                <input type="checkbox" checked={confirmResign} onChange={(event) => setConfirmResign(event.target.checked)}/>
                <span>Ho verificato che il documento è già firmato e autorizzo una nuova firma/sostituzione del file.</span>
              </label>
            ) : null}
            <button className="iu-fas-submit" type="button" disabled={busy || !localSignerCanSign || (alreadySigned && !confirmResign)} onClick={firmaConLocalSigner}>
              <ShieldCheck size={16}/> {busy ? 'Firma in corso...' : 'Firma tramite Local Signer'}
            </button>
            <p className="iu-fas-signature-help">La firma integrata usa il servizio locale installato su questo PC. IUSENTRA non salva PIN, password o credenziali del dispositivo.</p>
            {!localSignerCanSign ? (
              <div className="iu-fas-signer-next-step">
                <strong>{signerRestartRequired || localSignerOutdated ? 'Riallineamento automatico in corso.' : 'Dispositivo non pronto per la firma.'}</strong>
                <span>{signerRestartRequired || localSignerOutdated ? 'Il PIN comparirà solo quando il dispositivo sarà pronto.' : 'Inserisci il dispositivo di firma: IUSENTRA gestisce avvio e aggiornamento del Local Signer.'}</span>
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel title="Firma esterna" subtitle="ArubaSign, Dike o altro software di firma" icon={<UploadCloud size={17}/>}>
          <JsonPostForm className="iu-fas-signature-form" action={firmaUrl} encType="multipart/form-data">
            <p>Scarica il documento, firmalo con il software di firma e carica qui il file firmato.</p>
            <label className="iu-fas-field">
              <span>File firmato <b>*</b></span>
              <input type="file" name="file" accept=".p7m,.sig,.pkcs7,.pdf" required/>
            </label>
            <label className="iu-fas-field">
              <span>Note operative</span>
              <input type="text" name="note" defaultValue="Versione firmata per deposito"/>
            </label>
            <input type="hidden" name="visible_signature_mode" value={visibleSignatureMode}/>
            <input type="hidden" name="visible_signature_place" value={visibleSignaturePlace}/>
            <input type="hidden" name="visible_signature_datetime_mode" value={visibleSignatureDatetimeMode}/>
            {alreadySigned ? (
              <label className="iu-fas-resign-confirm">
                <input type="checkbox" checked={confirmResign} onChange={(event) => setConfirmResign(event.target.checked)}/>
                <span>Ho verificato che il documento è già firmato e autorizzo una nuova firma/sostituzione del file.</span>
              </label>
            ) : null}
            {alreadySigned && confirmResign ? <input type="hidden" name="confirm_resign" value="1"/> : null}
            <button className="iu-fas-submit" type="submit" disabled={alreadySigned && !confirmResign}><UploadCloud size={16}/> Carica file firmato</button>
          </JsonPostForm>
        </Panel>

        <Panel title="Verifica firma" subtitle="Esito letto dal documento salvato" icon={<FileCheck2 size={17}/>} count={info?.firme?.length || 0}>
          <div className="iu-fas-signature-box">
            {info?.errore ? <p className="iu-empty">{info.errore}</p> : null}
            <KvGrid items={[
              { label: 'Nome verificato', value: info?.nome || doc?.name || 'n.d.' },
              { label: 'Firme rilevate', value: String(info?.firme?.length || 0) },
              { label: 'Stato UI', value: info?.signed_ui?.label || doc?.statusLabel || 'n.d.' },
            ]}/>
            <button className="iu-fas-mini-action" type="button" onClick={refreshInfo}><RefreshCw size={14}/> Aggiorna verifica</button>
          </div>
        </Panel>
      </section>
      <FloatingLex context="firma-documento" title="Lex AI firma" body="Posso spiegare differenze tra firma integrata, firma esterna e controlli prima del deposito, senza sostituire la verifica del documento." primaryHref="#lex" primaryLabel="Apri Lex firma" secondaryHref={detailUrl} secondaryLabel="Torna ai documenti" />
    </main>
  )
}

const activityUrlPattern = /(https?:\/\/[^\s<>"']+)/gi

function renderActivityText(value: string): ReactNode {
  if (!value) return null
  const parts = value.split(activityUrlPattern)
  return parts.map((part, index) => {
    if (!/^https?:\/\//i.test(part)) return <Fragment key={`text-${index}`}>{part}</Fragment>
    const cleanHref = part.replace(/[),.;:]+$/g, '')
    const suffix = part.slice(cleanHref.length)
    return (
      <Fragment key={`url-${index}`}>
        <a className="iu-fas-inline-link" href={cleanHref} target="_blank" rel="noopener noreferrer">{cleanHref}</a>
        {suffix}
      </Fragment>
    )
  })
}

function ActivityRow({ activity }:{activity:FascicoloActivity}) {
  const resultText = normaliseText(activity.result)
  const badgeText = !resultText || /non applicabile/.test(resultText)
    ? (activity.type || 'Evento')
    : depositStatusLabel(activity.result)
  const metaLine = [activity.type, activity.place, activity.lawyer].filter(Boolean).join(' - ')
  const remoteUrl = activity.remoteHearingVerified ? activity.remoteHearingUrl || '' : ''
  const remoteMeta = [
    activity.remoteHearingMode ? `Modalità: ${activity.remoteHearingMode.replaceAll('_', ' ')}` : '',
    activity.hearingTime ? `Ora: ${activity.hearingTime}` : '',
    activity.remoteHearingPlatform ? `Piattaforma: ${activity.remoteHearingPlatform}` : '',
    activity.remoteHearingMeetingId ? `ID riunione: ${activity.remoteHearingMeetingId}` : '',
    activity.remoteHearingPasscode ? `Codice di accesso: ${activity.remoteHearingPasscode}` : '',
    activity.remoteHearingSource ? `Fonte: ${activity.remoteHearingSource}` : '',
  ].filter(Boolean)
  return (
    <article className="iu-fas-activity-row">
      <div className="iu-fas-activity-date"><Badge tone={activity.tone}>{badgeText}</Badge><time>{activity.date || 'n.d.'}</time></div>
      <div className="iu-fas-activity-main">
        <strong>{activity.title}</strong>
        {metaLine ? <span>{metaLine}</span> : null}
        {activity.description ? <p>{renderActivityText(activity.description)}</p> : null}
        {activity.notes ? <em>{renderActivityText(activity.notes)}</em> : null}
        {activity.remoteHearingDetected ? (
          <div className="iu-fas-activity-remote">
            {remoteMeta.map((item) => <small key={item}>{item}</small>)}
            {activity.remoteHearingAccessInfo ? <small>{activity.remoteHearingAccessInfo}</small> : null}
            {remoteUrl ? (
              <a href={remoteUrl} target="_blank" rel="noopener noreferrer">
                <Video size={14}/>
                Collegati all'udienza
              </a>
            ) : <small>Collegamento audiovisivo da verificare.</small>}
          </div>
        ) : null}
      </div>
      <div className="iu-fas-actions iu-fas-actions--wrap iu-fas-activity-actions">
        {activity.updateAction ? <JsonPostForm action={activity.updateAction} className="iu-fas-mini-form iu-fas-mini-form--activity"><select name="esito" defaultValue={activity.result || 'IN_ATTESA'} aria-label="Esito attivita"><option value="IN_ATTESA">In attesa</option><option value="FAVOREVOLE">Favorevole</option><option value="PARZIALE">Parziale</option><option value="SFAVOREVOLE">Sfavorevole</option><option value="RINVIATO">Rinviato</option><option value="ANNULLATO">Annullato</option></select><button type="submit"><CheckCircle2 size={13}/> Salva</button></JsonPostForm> : null}
        {activity.deleteAction ? <PostAction action={activity.deleteAction} tone="danger" confirm="Eliminare questa attività?"><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

function DeadlineRow({ deadline }:{deadline:FascicoloDeadline}) {
  return <a className="iu-fas-deadline-row" href={deadline.href}><Badge tone={deadline.tone}>{deadline.priority || deadline.type || 'termine'}</Badge><strong>{deadline.title}</strong><span>{deadline.date}{deadline.peremptory ? ' · perentorio' : ''}</span></a>
}

function DocumentPresidioPanel({ data }:{data:FascicoloDetailData}) {
  const presidio = data.documentPresidio
  const actions = presidio.actions || []
  const next = presidio.nextAction || actions[0]
  return (
    <section className={`iu-fas-document-presidio iu-fas-document-presidio--${presidio.tone}`}>
      <header>
        <div>
          <Badge tone={presidio.tone}>{actions.length ? `${actions.length} controlli` : 'Da controllare'}</Badge>
          <strong>{next?.title || 'Presidio documenti fascicolo'}</strong>
          <span>{next?.date || presidio.summary}</span>
        </div>
        <FileCheck2 size={20}/>
      </header>
      {actions.length ? (
        <div className="iu-fas-presidio-actions">
          {actions.slice(0, 6).map((action) => (
            <article key={action.id}>
              <Badge tone={action.tone}>{action.date || 'Data da confermare'}</Badge>
              <strong>{action.title}</strong>
              <span>{action.description}</span>
              <small>
                {visibleDocumentSource(action.source)}
                {action.peremptory ? ' · termine perentorio' : ''}
                {action.requiresCommunicationDate ? ' · serve data comunicazione' : ''}
              </small>
            </article>
          ))}
        </div>
      ) : <p className="iu-empty">{presidio.summary}</p>}
      {presidio.warnings.length ? (
        <div className="iu-fas-presidio-warnings">
          {presidio.warnings.slice(0, 3).map((warning) => <span key={warning}><AlertTriangle size={13}/>{warning}</span>)}
        </div>
      ) : null}
    </section>
  )
}

function operationalSectorIcon(sectorId: string): ReactNode {
  if (sectorId === 'pec') return <Mail size={18}/>
  if (sectorId === 'documenti') return <FileText size={18}/>
  if (sectorId === 'relata') return <FileSignature size={18}/>
  if (sectorId === 'economico') return <WalletCards size={18}/>
  if (sectorId === 'doppioni') return <Copy size={18}/>
  return <ClipboardCheck size={18}/>
}

function OperationalPresidioPanel({ data, onOpenSector }:{data:FascicoloDetailData; onOpenSector:(href:string, lazySection?:FascicoloDetailSection)=>void}) {
  const presidio = data.operationalPresidio
  const next = presidio.nextAction || presidio.actions[0]
  const remainingActions = presidio.actions.filter((action) => action.id !== next?.id)
  const sectors = presidio.sectors.length ? presidio.sectors : []
  const sectorTargets: Record<string, FascicoloDetailSection | undefined> = {
    pec: 'depositi',
    documenti: 'documenti',
    relata: 'relata',
    economico: undefined,
    doppioni: undefined,
  }
  const handleSectorClick = (href: string, sectorId?: string) => (event: MouseEvent<HTMLAnchorElement>) => {
    const hashIndex = href.indexOf('#')
    const target = hashIndex >= 0 ? href.slice(hashIndex) : href
    if (!target || !target.startsWith('#')) return
    event.preventDefault()
    onOpenSector(target, sectorTargets[sectorId || ''])
  }
  return (
    <section id="presidio-operativo" className={`iu-fas-operational-presidio iu-fas-operational-presidio--${presidio.tone}`} aria-label="Presidio operativo del fascicolo">
      <header>
        <div>
          <span><ShieldCheck size={16}/> Presidio operativo</span>
          <strong>{next?.title || presidio.statusLabel}</strong>
          <p>{next?.reason || presidio.summary}</p>
        </div>
        <Badge tone={presidio.tone}>{presidio.statusLabel}</Badge>
      </header>
      {next ? (
        <div className="iu-fas-operational-next">
          <Badge tone={next.tone}>{next.priority}</Badge>
          <strong>{next.date || 'Data da confermare'}</strong>
          <span>{next.legalBasis || next.source || 'Fonte fascicolo'}</span>
          {next.href ? <a href={next.href} onClick={handleSectorClick(next.href, next.sector)}>Apri controllo</a> : null}
        </div>
      ) : null}
      <div className="iu-fas-operational-sectors">
        {sectors.map((sector) => (
          <a href={sector.href || '#'} onClick={handleSectorClick(sector.href, sector.id)} className={`iu-fas-operational-sector iu-fas-operational-sector--${sector.tone}`} key={sector.id}>
            <span>{operationalSectorIcon(sector.id)}</span>
            <div>
              <Badge tone={sector.tone}>{sector.statusLabel}</Badge>
              <strong>{sector.label}</strong>
              <small>{sector.summary}</small>
            </div>
          </a>
        ))}
      </div>
      <div className="iu-fas-operational-actions">
        {remainingActions.slice(0, 5).map((action) => (
          <article key={action.id}>
            <Badge tone={action.tone}>{action.priority}</Badge>
            <div>
              <strong>{action.title}</strong>
              <span>{action.date ? `${action.date} - ` : ''}{action.reason}</span>
              <small>{[action.legalBasis, visibleDocumentSource(action.source || action.evidence)].filter(Boolean).join(' - ')}</small>
            </div>
            {action.href ? <a href={action.href} onClick={handleSectorClick(action.href, action.sector)}>Apri</a> : null}
          </article>
        ))}
      </div>
      <details className="iu-fas-operational-questions">
        <summary>Domande che il software presidia prima dell'avvocato</summary>
        <ul>
          {(presidio.questions.length ? presidio.questions : sectors.flatMap((sector) => sector.questions)).slice(0, 8).map((question) => <li key={question}>{question}</li>)}
        </ul>
      </details>
    </section>
  )
}

function formatAuditDate(value: string) {
  if (!value) return 'n.d.'
  return formatDateTimeIt(value, value, { includeTimezone: true })
}

function copyAuditHash(value: string) {
  if (!value || typeof navigator === 'undefined' || !navigator.clipboard) return
  void navigator.clipboard.writeText(value)
}

function sentenzeEconomicheCount(data: FascicoloSentenzeEconomiche | null) {
  if (!data) return 0
  return Math.max(data.worklist.length, data.totals.sentenze_lette ? 1 : 0)
}

function SentenzeEconomicheSection({
  data,
  onOpenDocuments,
  onOpenEconomia,
  defaultOpen = false,
}:{
  data: FascicoloSentenzeEconomiche | null
  onOpenDocuments: (event: MouseEvent<HTMLAnchorElement>) => void
  onOpenEconomia: (event: MouseEvent<HTMLAnchorElement>) => void
  defaultOpen?: boolean
}) {
  const count = sentenzeEconomicheCount(data)
  return (
    <DetailSection id="sentenze-economiche" title="Sentenze: controllo economico" icon={<WalletCards size={17}/>} count={count} defaultOpen={defaultOpen}>
      {data && data.worklist.length ? (
        <div className="iu-fas-side-cards iu-fas-sentenze-economiche">
          <article>
            <Badge tone={data.kpi.tone}>{data.kpi.label || 'Controllo economico'}</Badge>
            <strong>{data.kpi.value || 'Evidenze lette'}</strong>
            <span>{data.totals.sentenze_lette} sentenze lette, {data.totals.da_verificare} verifiche economiche aperte</span>
          </article>
          {data.worklist.map((item) => (
            <article key={`${item.label}-${item.value}-${item.hint}`}>
              <Badge tone={item.tone}>{item.label}</Badge>
              <strong>{item.value}</strong>
              <span>{item.hint}</span>
            </article>
          ))}
        </div>
      ) : (
        <div className="iu-fas-empty-action">
          <Badge tone="warning">Da alimentare</Badge>
          <strong>Nessuna sentenza economica letta per questo fascicolo.</strong>
          <p>Serve una sentenza o un provvedimento conclusivo classificato nel fascicolo: quando il documento contiene liquidazione, distrazione, contributo o spese, il controllo economico viene popolato qui.</p>
          <div>
            <a href="#documenti" onClick={onOpenDocuments}><FileText size={14}/> Apri documenti</a>
            <a href="#economia" onClick={onOpenEconomia}><WalletCards size={14}/> Contesto economico</a>
          </div>
        </div>
      )}
    </DetailSection>
  )
}

function AuditTrailSection({ audit, bundleHref, onOpen, loading = false, defaultOpen = false }:{audit:FascicoloAuditTrail; bundleHref:string; onOpen?:()=>void; loading?:boolean; defaultOpen?:boolean}) {
  const effectiveBundleHref = audit.enabled ? (audit.actions.bundle || bundleHref) : ''
  const hasEvents = audit.events.length > 0
  return (
    <DetailSection id="audit" title="Audit" icon={<Fingerprint size={17}/>} count={audit.summary.total} defaultOpen={defaultOpen} onOpen={onOpen}>
      {loading ? <p className="iu-empty">Caricamento audit...</p> : null}
      {hasEvents ? (
        <>
          <div className="iu-fas-audit-summary">
            <span><Badge tone={audit.summary.signed === audit.summary.total && audit.summary.total ? 'success' : 'warning'}>{audit.summary.signed}</Badge><strong>Firmati</strong></span>
            <span><Badge tone={audit.summary.worm === audit.summary.total && audit.summary.total ? 'success' : 'warning'}>{audit.summary.worm}</Badge><strong>WORM</strong></span>
            <span><Badge tone={audit.summary.snapshotted ? 'success' : 'neutral'}>{audit.summary.snapshotted}</Badge><strong>In snapshot</strong></span>
            <span><Badge tone={audit.summary.tsaVerified ? 'success' : 'neutral'}>{audit.summary.tsaVerified}</Badge><strong>TSA verificata</strong></span>
          </div>
          <div className="iu-fas-audit-actions">
            {effectiveBundleHref ? <a href={effectiveBundleHref}><PackageCheck size={15}/> Scarica bundle fascicolo</a> : null}
          </div>
        </>
      ) : !loading ? (
        <div className="iu-fas-empty-action">
          <Badge tone={audit.enabled ? 'warning' : 'neutral'}>{audit.enabled ? 'Nessuna evidenza' : 'Da configurare'}</Badge>
          <strong>{audit.enabled ? 'Nessun evento probatorio registrato per questo fascicolo.' : 'Presidio probatorio non attivo per questo studio.'}</strong>
          <p>{audit.message || (audit.enabled ? 'Le evidenze audit nascono quando il fascicolo registra consultazioni, download, depositi, ricevute o pacchetti probatori.' : 'Attivare il presidio audit prima di usare il bundle come prova operativa.')}</p>
          <div>
            <a href="#documenti"><FileText size={14}/> Apri documenti</a>
            {effectiveBundleHref ? <a href={effectiveBundleHref}><PackageCheck size={14}/> Scarica bundle</a> : null}
          </div>
        </div>
      ) : null}
      <div className="iu-fas-audit-list">
        {audit.events.map((event) => (
          <article className="iu-fas-audit-row" key={event.eventId}>
            <div>
              <Badge tone={event.tone}>{event.kindLabel}</Badge>
              <time>{formatAuditDate(event.eventTsUtc)}</time>
            </div>
            <div>
              <strong>{event.eventHashShort || event.eventHash || 'impronta non disponibile'}</strong>
              <span>{event.prevEventHash ? 'Concatenato al precedente evento' : 'Primo evento del fascicolo'}</span>
            </div>
            <div className="iu-fas-audit-badges">
              {event.signed ? <Badge tone="success">Firmato</Badge> : <Badge tone="warning">Firma da verificare</Badge>}
              {event.worm ? <Badge tone="success">WORM</Badge> : <Badge tone="warning">Conservazione da verificare</Badge>}
              {event.inSnapshot ? <Badge tone="success">In snapshot</Badge> : <Badge tone="neutral">Snapshot in attesa</Badge>}
              {event.tsaVerified ? <Badge tone="success">TSA verificata</Badge> : null}
            </div>
            <div className="iu-fas-actions iu-fas-actions--wrap">
              {event.eventHash ? <button type="button" title="Copia impronta completa" onClick={() => copyAuditHash(event.eventHash)}><Copy size={15}/></button> : null}
              {event.proofHref ? <a href={event.proofHref} title="Scarica prova"><Download size={15}/></a> : null}
            </div>
          </article>
        ))}
      </div>
    </DetailSection>
  )
}

function DetailPage({ id }:{id:string}) {
  const [data, setData] = useState<FascicoloDetailData>(emptyFascicoloDetail)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [previewDoc, setPreviewDoc] = useState<PreviewDocument | null>(null)
  const [embeddedRecord, setEmbeddedRecord] = useState<EmbeddedRecordState | null>(null)
  const [documentFlowMode, setDocumentFlowMode] = useState<DocumentFlowMode | null>(null)
  const [contextMenu, setContextMenu] = useState<FascicoloContextMenuState | null>(null)
  const [contributoModalOpen, setContributoModalOpen] = useState(false)
  const [economicControlOpen, setEconomicControlOpen] = useState(false)
  const [contributoMemory, setContributoMemory] = useState<ContributoUnificatoMemory | null>(null)
  const [officePortalOpenRequest, setOfficePortalOpenRequest] = useState(0)
  const [lazyStatus, setLazyStatus] = useState<Record<FascicoloDetailSection, LazySectionStatus>>(emptyLazySections)
  const [activeHashSection, setActiveHashSection] = useState(() => currentDetailHashSectionId())
  useEffect(() => {
    let active = true
    const initialIncludes = initialDetailIncludesFromHash()
    setActiveHashSection(currentDetailHashSectionId())
    setLoading(true)
    setLazyStatus(() => {
      const next = { ...emptyLazySections }
      for (const section of initialIncludes) next[section] = 'loading'
      if (initialIncludes.includes('documenti')) next.lex = 'loading'
      return next
    })
    getFascicoloDetail(id, initialIncludes.length ? { include: initialIncludes } : undefined).then((payload) => {
      if (active) {
        setData(payload)
        if (initialIncludes.length) {
          setLazyStatus((current) => {
            const next = { ...current }
            for (const section of initialIncludes) next[section] = 'loaded'
            if (initialIncludes.includes('documenti')) next.lex = 'loaded'
            return next
          })
        }
      }
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])
  const f = data.fascicolo
  const encodedId = encodeURIComponent(f.id || id)
  const operationalHref = f.operationalHref || `/fascicoli/${encodedId}`
  const quadroHref = `/fascicoli/${encodedId}/quadro`
  const notificationHref = `/notifiche-legali?id_fascicolo=${encodedId}&fase=notifica`
  const compilerHref = `/template-atti/catalogo?id_fascicolo=${encodedId}`
  const detailReturnHref = `/fascicoli/${encodeURIComponent(f.id || id)}#conformita`
  const exportPdfHref = data.actions.exportPdf || f.exportPdfHref
  const depositTelematicHref = data.telematic.find((item) => /deposito telematico/i.test(item.label))?.href || `/fascicoli/${encodedId}/deposito/prepara`
  const clientId = data.client?.id || f.clientId
  const clientRecordHref = clientId ? `/clienti/${encodeURIComponent(clientId)}/modifica` : '/clienti'
  const partiesRecordHref = `/soggetti?fascicolo=${encodedId}`
  const pagoPaEmbeddedHref = `${PAGOPA_PROXY_NEW_PAYMENT_URL}?iusentra_fascicolo=${encodedId}`
  const openPagoPaModal = () => setEmbeddedRecord({ kind: 'pagopa', title: 'Nuovo pagamento PagoPA PST', href: pagoPaEmbeddedHref, externalHref: PAGOPA_PST_NEW_PAYMENT_URL })
  const signedDocuments = data.documents.filter((doc) => doc.signed).length
  const documentsCount = data.quickCounts.documenti || data.documents.length
  const unsignedDocuments = Math.max(0, documentsCount - signedDocuments)
  const notificationRelata = data.notificationRelata
  const notificationRelataCount = data.quickCounts.relata_notifica || notificationRelata.pendingPortalDocuments || notificationRelata.relataDocuments || notificationRelata.signedRelataDocuments || notificationRelata.proofDocuments || 0
  const qualityIssues = data.quality.filter((item) => !item.ok).length + (Number(f.alerts) || 0)
  const nextDeadline = data.deadlines[0]
  const nextAppointment = data.appointments[0]
  const preventivo = data.workflow.find((item) => /preventiv/i.test(item.label))
  const conferimento = data.workflow.find((item) => /conferiment|incaric/i.test(item.label))
  const documentSections = buildDocumentSections(data.documents)
  const notificationCommunicationDocuments = data.documents.filter(isNotificationCommunicationDocument)
  const comunicazioniRows = data.deposits.filter((dep) => !isCancelleriaCommunication(dep))
  const cancelleriaRows = data.deposits.filter(isCancelleriaCommunication)
  const communicationTotal = notificationCommunicationDocuments.length + comunicazioniRows.length + cancelleriaRows.length
  const displayedCommunicationTotal = communicationTotal || data.quickCounts.comunicazioni || 0
  const operationalPresidio = data.operationalPresidio
  const contributionContext = f.paymentSummary.items.contributo_unificato
  const contributionContextLabel = contributionContext.status === 'non_previsto'
    ? 'Contributo non dovuto o esente dal presidio economico'
    : contributionContext.status === 'pagato'
      ? 'Ricevuta contributo acquisita dal presidio economico'
      : 'Contributo da verificare dal presidio economico'
  const loadLazySection = (section: FascicoloDetailSection) => {
    if (lazyStatus[section] === 'loaded' || lazyStatus[section] === 'loading') return
    setLazyStatus((current) => ({ ...current, [section]: 'loading' }))
    getFascicoloDetailSection(id, section)
      .then((payload) => {
        setData((current) => ({
          ...current,
          quickCounts: { ...current.quickCounts, ...payload.quickCounts },
          documents: section === 'documenti' || (section === 'depositi' && payload.documents.length) ? payload.documents : current.documents,
          activities: section === 'attivita' ? payload.activities : current.activities,
          requests: section === 'attivita' ? payload.requests : current.requests,
          deadlines: section === 'scadenze' ? payload.deadlines : current.deadlines,
          appointments: section === 'scadenze' ? payload.appointments : current.appointments,
          documentPresidio: section === 'scadenze' || section === 'documenti' ? payload.documentPresidio : current.documentPresidio,
          operationalPresidio: section === 'scadenze' || section === 'documenti' || section === 'depositi' || section === 'relata' ? payload.operationalPresidio : current.operationalPresidio,
          deposits: section === 'depositi' ? payload.deposits : current.deposits,
          regia: section === 'regia' ? payload.regia : current.regia,
          notificationRelata: section === 'relata' ? payload.notificationRelata : current.notificationRelata,
          auditTrail: section === 'audit' ? payload.auditTrail : current.auditTrail,
          lexIndexing: section === 'lex' || section === 'documenti' ? payload.lexIndexing : current.lexIndexing,
        }))
        setLazyStatus((current) => ({
          ...current,
          [section]: 'loaded',
          ...(section === 'documenti' ? { lex: 'loaded' as LazySectionStatus } : {}),
        }))
      })
      .catch((err) => {
        setLazyStatus((current) => ({ ...current, [section]: 'error' }))
        setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Caricamento sezione non riuscito.' })
      })
  }
  const openDocumentFlow = (mode: DocumentFlowMode) => {
    setContextMenu(null)
    setDocumentFlowMode(mode)
    if (lazyStatus.documenti === 'idle') loadLazySection('documenti')
  }
  const openSectionFromContext = (sectionId: string, lazySection?: FascicoloDetailSection) => {
    setContextMenu(null)
    if (lazySection) loadLazySection(lazySection)
    openDetailSectionById(sectionId)
  }
  const openOfficePortalFromContext = () => {
    setContextMenu(null)
    if (lazyStatus.documenti === 'idle') loadLazySection('documenti')
    openDetailSectionById('documenti')
    setOfficePortalOpenRequest((current) => current + 1)
  }
  const openContributoUnificatoFromContext = () => {
    setContextMenu(null)
    setContributoModalOpen(true)
  }
  const openEconomicControlFromContext = () => {
    setContextMenu(null)
    setEconomicControlOpen(true)
  }
  const rememberContributoUnificato = (memory: ContributoUnificatoMemory, message?: string) => {
    setContributoMemory(memory)
    if (message) setToast({ tone: 'success', message })
  }
  const copyContributionMemory = (memory: ContributoUnificatoMemory) => {
    void copyTextForUser(memory.copyText)
      .then(() => setToast({ tone: 'success', message: 'Calcolo contributo copiato negli appunti.' }))
      .catch(() => setToast({ tone: 'danger', message: 'Il browser ha bloccato la copia negli appunti.' }))
  }
  const openFascicoloContextMenu = (event: MouseEvent<HTMLElement>) => {
    if (shouldUseNativeContextMenu(event.target)) return
    event.preventDefault()
    setContextMenu(clampFascicoloContextMenuPosition(event.clientX, event.clientY))
  }
  useEffect(() => {
    if (!contextMenu) return undefined
    const close = () => setContextMenu(null)
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    const onScroll = (event: Event) => {
      if (event.target instanceof Element && event.target.closest('.iu-fas-context-menu')) return
      close()
    }
    window.addEventListener('click', close)
    window.addEventListener('resize', close)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('resize', close)
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [contextMenu])
  useEffect(() => {
    const currentId = f.id || id
    setContributoMemory(readContributionMemory(currentId))
  }, [f.id, id])
  useEffect(() => {
    if (loading) return undefined
    const openHashSection = () => {
      const sectionId = currentDetailHashSectionId()
      if (!sectionId) return
      setActiveHashSection(sectionId)
      const lazySection = lazySectionForDetailHash(sectionId)
      if (lazySection) loadLazySection(lazySection)
      window.setTimeout(() => openDetailSectionById(sectionId), 80)
    }
    openHashSection()
    window.addEventListener('hashchange', openHashSection)
    return () => window.removeEventListener('hashchange', openHashSection)
  }, [loading, data.fascicolo.id])
  const refreshDetail = (message?: string) => {
    if (message) setToast({ tone: 'success', message })
    getFascicoloDetail(id, { include: 'all' }).then((payload) => {
      setData(payload)
      setLazyStatus({ documenti: 'loaded', attivita: 'loaded', scadenze: 'loaded', depositi: 'loaded', regia: 'loaded', relata: 'loaded', audit: 'loaded', lex: 'loaded' })
    }).catch((err) => setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Aggiornamento fascicolo non riuscito.' }))
  }
  const refreshDocuments = (message?: string) => {
    if (message) setToast({ tone: 'success', message })
    getFascicoloDetailSection(id, 'documenti').then((payload) => {
      setData((current) => ({
        ...current,
        quickCounts: { ...current.quickCounts, ...payload.quickCounts },
        documents: payload.documents,
        documentPresidio: payload.documentPresidio,
        operationalPresidio: payload.operationalPresidio,
        lexIndexing: payload.lexIndexing,
      }))
      setLazyStatus((current) => ({ ...current, documenti: 'loaded', lex: 'loaded' }))
    }).catch((err) => setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Aggiornamento documenti non riuscito.' }))
  }
  const failDetail = (message: string) => setToast({ tone: 'danger', message })
  const handleDetailPaymentSaved = useCallback((savedId: string, paymentSummary: FascicoloRow['paymentSummary'], message?: string) => {
    setData((current) => {
      const currentId = current.fascicolo.id || id
      if (savedId && currentId && savedId !== currentId) return current
      return {
        ...current,
        fascicolo: {
          ...current.fascicolo,
          paymentSummary,
        },
      }
    })
    setToast({ tone: 'success', message: message || 'Controllo economico aggiornato.' })
  }, [id])
  const openSection = (sectionId: string, lazySection?: FascicoloDetailSection) => (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    if (lazySection) loadLazySection(lazySection)
    openDetailSectionById(sectionId)
  }
  if (loading && !data.fascicolo.id) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<FolderOpen size={34}/>} title="Caricamento fascicolo">Lettura dei dati e dei documenti in corso.</EmptyState></main>
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<FolderOpen size={34}/>} title={data.requestError ? 'Dati fascicolo non caricati' : 'Fascicolo non trovato'} action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>{data.requestError || 'Il fascicolo non è disponibile o non hai i permessi per aprirlo.'}</EmptyState></main>
  return (
    <main id="fascicolo-top" className="iu-content iu-fascicoli-page iu-fascicolo-detail-page" onContextMenu={openFascicoloContextMenu}>
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div><span className="iu-fas-eyebrow"><FolderOpen size={16}/> Fascicolo</span><h1>{f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge>{f.archiveReady ? <Badge tone="warning">Pronto per archivio</Badge> : null}<span>{f.object || f.subtitle}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><ArrowLeft size={15}/> Fascicoli</Button><button className="iu-button iu-button--primary" type="button" onClick={() => openDocumentFlow('deposito')}><Send size={15}/> Deposito telematico</button><RecordOverlayButton icon={<UserRound size={15}/>} label="Cliente" title="Visualizza cliente nel fascicolo" onClick={() => setEmbeddedRecord({ kind: 'cliente', title: 'Cliente', href: clientRecordHref })}/><RecordOverlayButton icon={<UsersRound size={15}/>} label="Soggetti" title="Visualizza soggetti e parti nel fascicolo" onClick={() => setEmbeddedRecord({ kind: 'soggetti', title: 'Soggetti e parti', href: partiesRecordHref })}/><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={quadroHref}><Gauge size={15}/> Quadro AI</Button><button className="iu-button iu-button--secondary" type="button" title="Prepara una notifica legale per questa pratica" onClick={() => openDocumentFlow('notifica')}><Bell size={15}/> Notifica</button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button href={exportPdfHref} disabled={!exportPdfHref} title={!exportPdfHref ? 'PDF fascicolo non disponibile' : undefined}><FileDown size={15}/> PDF</Button><PagoPaActionButton onClick={openPagoPaModal}/></div>
      </section>
      <section className="iu-fas-case-strip"><strong>{f.ref}</strong><span>Rif. interno {f.internalRef}</span><span>{f.client}</span><span>{f.court}</span><span>{loading ? 'Caricamento...' : 'Dati aggiornati'}</span></section>
      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}
      <nav className="iu-fas-section-nav" aria-label="Sezioni fascicolo"><a href="#profilo">Profilo <b>{data.quickCounts.profilo || 0}</b></a><a href="#guida-pratica">Guida pratica</a><a href="#presidio-operativo">Presidio <b>{data.quickCounts.presidio_operativo || operationalPresidio.actions.length || 0}</b></a><a href="#uffici-competenti">Uffici</a><a href="#regia-operativa">Regia Operativa <b>{data.regia.documentSlots.length}</b></a><a href="#documenti">Documenti e atti <b>{data.quickCounts.documenti || 0}</b></a><a href="#relata-notifica">Relata notifica <b>{notificationRelataCount}</b></a><a href="#attivita">Attività <b>{data.quickCounts.attivita || 0}</b></a><a href="#udienze">Udienze / scadenze <b>{data.quickCounts.udienze_scadenze || 0}</b></a><a href="#cancelleria">Comunicazioni / Cancelleria <b>{displayedCommunicationTotal}</b></a><a href="#audit">Audit <b>{data.auditTrail.summary.total}</b></a><a href="#gestione">Gestione</a><a href="#economia">Contesto economico</a><a href="#conformita">Conformità</a><a href="#soggetti">Soggetti <b>{data.parties.length}</b></a></nav>
      <section className="iu-fas-detail-grid iu-fas-detail-grid--with-guide">
        <aside className="iu-fas-guide-column" aria-label="Guida pratica facoltativa del fascicolo">
          <GuidaPraticaSidebar fascicoloId={f.id || id} codice={f.codiceOggettoPst} fascicoloTitle={f.title}/>
        </aside>
        <div className="iu-fas-detail-content-column">
        <div className="iu-fas-detail-main">
      <section className="iu-fas-ai-board" aria-label="Quadro intelligente AI del fascicolo">
        <div><span><Sparkles size={16}/> Quadro intelligente AI</span><strong>Presidio operativo aggiornato</strong><p>{contributionContextLabel}. Analisi di documenti, scadenze, attività e prossime azioni usando i dati reali della pratica.</p></div>
        <div className="iu-fas-ai-actions">
          <a href={quadroHref}><Gauge size={15}/> Quadro completo</a>
          <a href="#documenti"><FileText size={15}/> Documenti e atti</a>
          <a href={compilerHref}><ClipboardCheck size={15}/> Compilatore atti</a>
          <a href="#documenti"><BrainCircuit size={15}/> Indice Lex</a>
          <PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina fascicolo</PostAction>
        </div>
      </section>
      <section className="iu-fas-smart-board" aria-label="Quadro intelligente del fascicolo">
        <header>
          <div><span><Gauge size={16}/> Quadro intelligente</span><strong>Sintesi fascicolo</strong></div>
          <a href={quadroHref}>Apri quadro completo</a>
        </header>
        <div>
          <a href="#documenti"><Badge tone={unsignedDocuments ? 'warning' : 'success'}>Documenti</Badge><strong>{unsignedDocuments ? `${unsignedDocuments} da firmare/verificare` : `${signedDocuments} firmati o verificati`}</strong><span>Controlla atti, allegati e file acquisiti nel fascicolo.</span></a>
          <a href="#relata-notifica"><Badge tone={notificationRelata.tone}>Relata</Badge><strong>{notificationRelata.statusLabel}</strong><span>{notificationRelata.systemNotification || 'Presidio sempre visibile per notifica e prova.'}</span></a>
          <a href="#udienze"><Badge tone={nextDeadline || nextAppointment ? 'warning' : 'neutral'}>Scadenze</Badge><strong>{nextDeadline?.date || nextAppointment?.date || 'Nessuna data critica'}</strong><span>{nextDeadline?.title || nextAppointment?.title || 'Apri lo scadenziario per programmare il presidio.'}</span></a>
          <a href="#workflow"><Badge tone={conferimento?.tone || preventivo?.tone || 'neutral'}>Incarico</Badge><strong>{conferimento?.value || preventivo?.value || 'Da verificare'}</strong><span>{conferimento?.note || preventivo?.note || 'Verifica preventivo, conferimento e collegamenti economici.'}</span></a>
          <a href="#conformita"><Badge tone={qualityIssues ? 'warning' : 'success'}>Conformità</Badge><strong>{qualityIssues ? `${qualityIssues} verifiche aperte` : 'Presidio OK'}</strong><span>Controlli qualità, parti, sync portale e dati principali.</span></a>
        </div>
      </section>
          <OperationalPresidioPanel data={data} onOpenSector={(href, lazySection) => {
            if (lazySection) loadLazySection(lazySection)
            openDetailSectionById(href.replace(/^#/, ''))
          }}/>
          <section className="iu-fas-cockpit"><StatCard icon={<ClipboardCheck size={19}/>} label="Regia" value={`${data.regia.header.completion}%`} note={data.regia.header.operationalState || 'da verificare'} tone={data.regia.validation.ready ? 'success' : data.regia.validation.blockers.length ? 'danger' : 'warning'} href="#regia-operativa" onClick={openSection('regia-operativa', 'regia')}/><StatCard icon={<MapPin size={19}/>} label="Uffici" value="Cerca" note="competenza per Comune" tone="success" href="#uffici-competenti" onClick={openSection('uffici-competenti')}/><StatCard icon={<FileText size={19}/>} label="Documenti" value={data.quickCounts.documenti || 0} note="carica e classifica" tone="primary" href="#documenti" onClick={openSection('documenti', 'documenti')}/><StatCard icon={<FileSignature size={19}/>} label="Relata" value={notificationRelataCount} note={notificationRelata.statusLabel} tone={notificationRelata.tone} href="#relata-notifica" onClick={openSection('relata-notifica', 'relata')}/><StatCard icon={<CalendarDays size={19}/>} label="Scadenze" value={data.quickCounts.udienze_scadenze || 0} note="gestisci agenda" tone="warning" href="#udienze" onClick={openSection('udienze', 'scadenze')}/><StatCard icon={<ListChecks size={19}/>} label="Attività" value={data.quickCounts.attivita || 0} note="aggiorna timeline" tone="success" href="#attivita" onClick={openSection('attivita', 'attivita')}/><StatCard icon={<Fingerprint size={19}/>} label="Audit" value={data.auditTrail.summary.total} note={data.auditTrail.summary.snapshotted ? 'prove in snapshot' : 'prove disponibili'} tone={data.auditTrail.summary.total ? 'success' : 'neutral'} href="#audit" onClick={openSection('audit', 'audit')}/><StatCard icon={<WalletCards size={19}/>} label="Contesto economico" value={data.economics.length} note="incarico e incassi" tone="purple" href="#economia" onClick={openSection('economia')}/></section>
          <DetailSection id="profilo" title="Profilo fascicolo" icon={<BadgeCheck size={17}/>}><KvGrid items={data.profile}/><SourceSnapshotPanel fascicolo={f}/>{f.notes ? <div className="iu-fas-note"><strong>Note</strong><p>{f.notes}</p></div> : null}</DetailSection>
          <DetailSection id="uffici-competenti" title="Uffici giudiziari per Comune" icon={<MapPin size={17}/>} defaultOpen>
            <FascicoloUfficiCompetentiPanel fascicolo={f}/>
          </DetailSection>
          <RegiaOperativaSection data={data} onDone={refreshDetail} onError={failDetail} onOpen={() => loadLazySection('regia')} loading={lazyStatus.regia === 'loading'}/>
          <DetailSection id="relata-notifica" title="Relata notifica" icon={<FileSignature size={17}/>} count={notificationRelataCount} defaultOpen={activeHashSection === 'relata-notifica' || notificationRelata.releaseDetected || notificationRelata.status !== 'monitoraggio'} onOpen={() => loadLazySection('relata')}>
            <NotificationRelataMonitor data={data}/>
          </DetailSection>
          <DetailSection id="documenti" title="Documenti e atti" icon={<FileText size={17}/>} count={data.quickCounts.documenti || 0} defaultOpen={activeHashSection === 'documenti'} onOpen={() => { loadLazySection('documenti') }}>
            <Suspense fallback={<p className="iu-empty">Preparazione ricerca documenti d’ufficio…</p>}>
              <OfficeDocumentsPanel data={data} onDone={refreshDocuments} onError={failDetail} openPortalRequest={officePortalOpenRequest}/>
            </Suspense>
            <DocumentUploadWorkspace data={data} onDone={refreshDetail} onError={failDetail}/>
            <LexIndexingPanel summary={data.lexIndexing} refreshAction={data.actions.refreshLexIndex} retryAction={data.actions.retryLexIndexErrors} onDone={refreshDetail} onError={failDetail}/>
            <div className="iu-fas-doc-section-list">
              {lazyStatus.documenti === 'loading' ? <p className="iu-empty">Caricamento documenti...</p> : null}
              {documentSections.map((section) => (
                <section className="iu-fas-doc-auto-section" key={section.id}>
                  <header>
                    <Badge tone={section.tone}>{section.documents.length}</Badge>
                    <div>
                      <strong>{section.title}</strong>
                      <span>{section.note}</span>
                    </div>
                  </header>
                  <div className="iu-fas-doc-list">
                    {section.documents.map((doc) => <DocumentRow doc={doc} key={doc.id} onPreview={setPreviewDoc} onDone={refreshDetail} onError={failDetail}/>)}
                  </div>
                </section>
              ))}
              {lazyStatus.documenti === 'loaded' && !data.documents.length ? <p className="iu-empty">Nessun documento caricato.</p> : null}
              {lazyStatus.documenti === 'idle' ? <p className="iu-empty">Apri la sezione per caricare, classificare o modificare i documenti del fascicolo.</p> : null}
            </div>
          </DetailSection>
          <DetailSection id="attivita" title="Attività processuali" icon={<ListChecks size={17}/>} count={data.quickCounts.attivita || 0} defaultOpen={activeHashSection === 'attivita'} onOpen={() => loadLazySection('attivita')}>
            <JsonPostForm className="iu-fas-add-activity" action={data.actions.addActivity}><select name="tipo" defaultValue="ALTRO">{data.options.activityTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input type="date" name="data" required/><input name="titolo" placeholder="Titolo attività" required/><input name="luogo" placeholder="Luogo"/><select name="esito" defaultValue="IN_ATTESA">{data.options.activityResults.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input name="avvocato" placeholder="Avvocato"/><textarea name="descrizione" placeholder="Descrizione"/><button type="submit"><Plus size={15}/> Aggiungi</button></JsonPostForm>
            <div className="iu-fas-activity-list">{lazyStatus.attivita === 'loading' ? <p className="iu-empty">Caricamento attività...</p> : null}{data.activities.map((activity) => <ActivityRow activity={activity} key={activity.id}/>)}{lazyStatus.attivita === 'loaded' && !data.activities.length ? <p className="iu-empty">Nessuna attività processuale registrata.</p> : null}{lazyStatus.attivita === 'idle' ? <p className="iu-empty">Apri la sezione per caricare la timeline processuale.</p> : null}</div>
          </DetailSection>
          <DetailSection id="udienze" title="Udienze e scadenze" icon={<CalendarDays size={17}/>} count={data.quickCounts.udienze_scadenze || 0} defaultOpen={activeHashSection === 'udienze'} onOpen={() => loadLazySection('scadenze')}>
            {lazyStatus.scadenze === 'loading' ? <p className="iu-empty">Caricamento udienze e scadenze...</p> : null}
            {lazyStatus.scadenze === 'idle' ? <p className="iu-empty">Apri la sezione per caricare udienze e scadenze collegate.</p> : null}
            <DocumentPresidioPanel data={data}/>
            <div className="iu-fas-two-cols"><div><h3>Scadenze</h3>{data.deadlines.map((deadline) => <DeadlineRow deadline={deadline} key={deadline.id}/>)}{lazyStatus.scadenze === 'loaded' && !data.deadlines.length ? <p className="iu-empty">Nessuna scadenza collegata.</p> : null}<a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuova scadenza</a></div><div><h3>Agenda</h3>{data.appointments.map((app) => <a className="iu-fas-deadline-row" href={app.href} key={app.id}><Badge tone={app.tone}>{app.type || 'agenda'}</Badge><strong>{app.title}</strong><span>{app.date} {app.time} {app.place}</span></a>)}{lazyStatus.scadenze === 'loaded' && !data.appointments.length ? <p className="iu-empty">Nessun appuntamento trovato.</p> : null}<a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo appuntamento</a></div></div>
          </DetailSection>
          <DetailSection id="cancelleria" title="Comunicazioni / Cancelleria" icon={<Mail size={17}/>} count={displayedCommunicationTotal} defaultOpen={activeHashSection === 'cancelleria'} onOpen={() => { loadLazySection('depositi'); loadLazySection('documenti') }}>
            <div className="iu-fas-comm-dep-grid">
              <div className="iu-fas-comm-column">
                <Panel title="Comunicazioni" icon={<Mail size={17}/>} count={notificationCommunicationDocuments.length + comunicazioniRows.length}>
                  <div className="iu-fas-comm-list">
                    {lazyStatus.depositi === 'loading' || lazyStatus.documenti === 'loading' ? <p className="iu-empty">Caricamento comunicazioni...</p> : null}
                    {notificationCommunicationDocuments.map((doc) => (
                      <article className="iu-fas-comm-row" key={`notifica-prova-${doc.id}`}>
                        <Badge tone="info">{notificationProofLabel(doc)}</Badge>
                        <strong>{doc.name}</strong>
                        <span>{[doc.portalDate || doc.documentDate || doc.uploadedAt, doc.source, doc.size].filter(Boolean).join(' - ')}</span>
                        <small>{notificationCommunicationDetail(doc)}</small>
                        {doc.actions.preview ? <a className="iu-fas-inline-link" href={doc.actions.preview} onClick={(event) => { event.preventDefault(); setPreviewDoc({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download }) }}><Eye size={14}/> Visualizza</a> : null}
                      </article>
                    ))}
                    {comunicazioniRows.map((dep) => (
                      <article className="iu-fas-comm-row" key={`comm-${dep.id}`}>
                        <Badge tone={dep.tone}>{depositStatusLabel(dep.status)}</Badge>
                        <strong>{dep.message || dep.pec || dep.actType || 'Comunicazione PEC'}</strong>
                        <span>{depositMetaLine(dep)}</span>
                        {dep.actType ? <small>{dep.actType}</small> : null}
                        <DepositStateSummary dep={dep}/>
                        <DepositReceiptSteps dep={dep}/>
                        <DepositReceiptActions dep={dep} onDone={refreshDetail} onError={failDetail}/>
                      </article>
                    ))}
                    {lazyStatus.depositi === 'loaded' && lazyStatus.documenti === 'loaded' && !notificationCommunicationDocuments.length && !comunicazioniRows.length ? <p className="iu-empty">Nessuna comunicazione PEC collegata al fascicolo.</p> : null}
                    {lazyStatus.depositi === 'idle' && lazyStatus.documenti === 'idle' ? <p className="iu-empty">Apri la sezione per caricare comunicazioni PEC e prove notifica del fascicolo.</p> : null}
                  </div>
                </Panel>
              </div>
              <div className="iu-fas-deposit-column">
                <Panel title="Cancelleria" icon={<Mail size={17}/>} count={cancelleriaRows.length}>
                  <p className="iu-fas-sync-note">
                    <RefreshCw size={14}/>
                    La casella PEC viene sincronizzata automaticamente: le nuove ricevute aggiornano stato deposito e fascicolo.
                  </p>
                  <div className="iu-fas-comm-list">
                    {lazyStatus.depositi === 'loading' ? <p className="iu-empty">Caricamento cancelleria...</p> : null}
                    {cancelleriaRows.map((dep) => (
                      <article className="iu-fas-comm-row" key={`canc-${dep.id}`}>
                        <Badge tone={dep.tone}>{depositStatusLabel(dep.status)}</Badge>
                        <strong>{dep.message || dep.actType || 'PEC di accettazione deposito'}</strong>
                        <span>{depositMetaLine(dep)}</span>
                        {dep.actType ? <small>{dep.actType}</small> : null}
                        <DepositStateSummary dep={dep}/>
                        <DepositReceiptSteps dep={dep}/>
                        <DepositReceiptActions dep={dep} onDone={refreshDetail} onError={failDetail}/>
                      </article>
                    ))}
                    {lazyStatus.depositi === 'loaded' && !cancelleriaRows.length ? <p className="iu-empty">Nessuna PEC di accettazione o esito collegata.</p> : null}
                    {lazyStatus.depositi === 'idle' ? <p className="iu-empty">Apri la sezione per caricare le PEC di accettazione del deposito.</p> : null}
                  </div>
                </Panel>
              </div>
            </div>
          </DetailSection>
          <DetailSection id="avanzamento" title="Avanzamento pratica" icon={<Clock3 size={17}/>} count={data.history.length}><div className="iu-fas-timeline">{data.history.map((item) => <article key={`${item.date}-${item.description}`}><time>{item.date}</time><strong>{item.description}</strong><span>{item.from} → {item.to}</span><p>{item.notes}</p></article>)}{!data.history.length ? <p className="iu-empty">Nessun avanzamento registrato.</p> : null}</div></DetailSection>
          <AuditTrailSection audit={data.auditTrail} bundleHref={data.actions.auditBundle} onOpen={() => loadLazySection('audit')} loading={lazyStatus.audit === 'loading'} defaultOpen={activeHashSection === 'audit'}/>
        </div>
        <aside className="iu-fas-detail-side">
          <DetailSection id="gestione" title="Gestione fascicolo" icon={<Gauge size={17}/>} defaultOpen={activeHashSection === 'gestione'}>
            <JsonPostForm className="iu-fas-side-form" action={data.actions.changeState}><label><span>Cambia stato</span><select name="stato" defaultValue={f.status.toUpperCase()}>{data.options.states.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note cambio stato"/><button type="submit"><RefreshCw size={15}/> Aggiorna stato</button></JsonPostForm>
            <div className="iu-fas-action-stack"><JsonPostForm action={data.actions.define}><input name="esito_finale" placeholder="Esito finale"/><input name="motivo" placeholder="Motivo"/><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note definizione"/><button type="submit"><CheckCircle2 size={15}/> Definisci</button></JsonPostForm><PostAction action={data.actions.archive} tone="primary" confirm="Archiviare il fascicolo?" confirmTitle="Archivia fascicolo"><Archive size={15}/> Archivia con ZIP</PostAction><PostAction action={data.actions.restore} tone="secondary" confirm="Ripristinare il fascicolo?" confirmTitle="Ripristina fascicolo"><RotateCcw size={15}/> Ripristina</PostAction>{exportPdfHref ? <a className="iu-fas-side-link" href={exportPdfHref}><FileDown size={15}/> PDF fascicolo</a> : <button className="iu-fas-side-link is-disabled" type="button" disabled title="PDF fascicolo non disponibile"><FileDown size={15}/> PDF fascicolo</button>}<PagoPaActionButton variant="side" onClick={openPagoPaModal}/>{data.actions.archiveZip ? <a className="iu-fas-side-link" href={data.actions.archiveZip}><FileArchive size={15}/> Scarica ZIP</a> : null}<PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina</PostAction></div>
          </DetailSection>
          <DetailSection id="economia" title="Contesto economico" icon={<WalletCards size={17}/>} count={data.economics.length} defaultOpen={activeHashSection === 'economia'}><div className="iu-fas-side-cards">{data.economics.map((item) => <a href={item.href} onClick={item.href.startsWith('#') ? openSection(item.href.slice(1)) : undefined} key={item.id}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}{!data.economics.length ? <p className="iu-empty">Nessun dato economico collegato.</p> : null}</div></DetailSection>
          <SentenzeEconomicheSection data={data.sentenzeEconomiche} onOpenDocuments={openSection('documenti', 'documenti')} onOpenEconomia={openSection('economia')} defaultOpen={activeHashSection === 'sentenze-economiche'}/>
          <DetailSection id="workflow" title="Percorso cliente-incasso" icon={<Sparkles size={17}/>} count={data.workflow.length}><div className="iu-fas-side-cards">{data.workflow.map((item) => item.href ? <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a> : <article key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></article>)}</div></DetailSection>
          <DetailSection id="conformita" title="Conformità e qualità" icon={<ShieldCheck size={17}/>} count={data.quality.length} defaultOpen={activeHashSection === 'conformita'}><div className="iu-fas-quality-list">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}</div><JsonPostForm className={`iu-fas-compliance-toggle ${f.complianceControlsEnabled ? 'is-on' : 'is-off'}`} action={f.complianceControlsEnabled ? data.actions.complianceOff : data.actions.complianceOn} redirectTo={detailReturnHref}><input type="hidden" name="enabled" value={f.complianceControlsEnabled ? '0' : '1'}/><input type="hidden" name="next" value={detailReturnHref}/><button type="submit" aria-pressed={f.complianceControlsEnabled}><span className="iu-fas-compliance-toggle__switch" aria-hidden="true"><i/></span><span><strong>{f.complianceControlsEnabled ? 'Controlli automatici attivi' : 'Controlli automatici disattivati'}</strong><small>{f.complianceControlsEnabled ? 'Disattiva i controlli qualità sul fascicolo' : 'Riattiva i controlli qualità sul fascicolo'}</small></span></button></JsonPostForm></DetailSection>
          <DetailSection id="telematico" title="Servizi telematici" icon={<Send size={17}/>} count={data.telematic.length}><div className="iu-fas-side-cards">{data.telematic.map((item) => <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}</div></DetailSection>
          <DetailSection id="cliente" title="Cliente" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}>{data.client ? <KvGrid items={[{ label: 'Nome', value: data.client.name, href: data.client.href }, { label: 'Codice fiscale', value: data.client.taxCode, mono: true }, { label: 'P. IVA', value: data.client.vat, mono: true }, { label: 'Email', value: data.client.email }, { label: 'PEC', value: data.client.pec }, { label: 'Telefono', value: data.client.phone }, { label: 'Indirizzo', value: data.client.address }]}/> : <p className="iu-empty">Cliente non collegato.</p>}</DetailSection>
          <DetailSection id="soggetti" title="Soggetti e parti" icon={<UsersRound size={17}/>} count={data.parties.length} defaultOpen={activeHashSection === 'soggetti'}><div className="iu-fas-party-list">{data.parties.map((party) => <a href={party.href} key={party.id}><strong>{party.name}</strong><span>{party.role || 'Soggetto'} · {party.taxCode || 'C.F. n.d.'}</span><small>{party.email || party.pec || party.phone}</small></a>)}{!data.parties.length ? <p className="iu-empty">Nessun soggetto collegato.</p> : null}</div><a className="iu-fas-inline-link" href={`/soggetti/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo soggetto</a></DetailSection>
        </aside>
        </div>
      </section>
      <FascicoloContextMenu
        position={contextMenu}
        title={f.title}
        reference={f.ref}
        fascicoloId={f.id || id}
        clientName={data.client?.name || f.client}
        editHref={f.editHref}
        compilerHref={compilerHref}
        exportPdfHref={exportPdfHref}
        archiveZipHref={data.actions.archiveZip || f.archiveZipHref}
        auditBundleHref={data.actions.auditBundle}
        onClose={() => setContextMenu(null)}
        onDeposit={() => openDocumentFlow('deposito')}
        onClient={() => {
          setContextMenu(null)
          setEmbeddedRecord({ kind: 'cliente', title: 'Modifica anagrafica cliente', href: clientRecordHref })
        }}
        onParties={() => {
          setContextMenu(null)
          setEmbeddedRecord({ kind: 'soggetti', title: 'Soggetti e parti', href: partiesRecordHref })
        }}
        onOfficePortal={openOfficePortalFromContext}
        onNotification={() => openDocumentFlow('notifica')}
        onContributoUnificato={openContributoUnificatoFromContext}
        onPagoPa={() => {
          setContextMenu(null)
          openPagoPaModal()
        }}
        onEconomicControl={openEconomicControlFromContext}
        onSection={openSectionFromContext}
      />
      {documentFlowMode ? (
        <DocumentFlowSelectionModal
          mode={documentFlowMode}
          documents={data.documents}
          loading={lazyStatus.documenti === 'loading'}
          baseHref={documentFlowMode === 'deposito' ? depositTelematicHref : notificationHref}
          onClose={() => setDocumentFlowMode(null)}
        />
      ) : null}
      <ContributoUnificatoModal
        open={contributoModalOpen}
        fascicolo={f}
        clientName={data.client?.name || f.client}
        onClose={() => setContributoModalOpen(false)}
        onMemory={rememberContributoUnificato}
        onOpenPagoPa={openPagoPaModal}
      />
      <PdfPreviewModal preview={previewDoc} onClose={() => setPreviewDoc(null)}/>
      <EmbeddedRecordModal
        record={embeddedRecord}
        contributoMemory={contributoMemory}
        onCopyContributoMemory={copyContributionMemory}
        onClose={() => setEmbeddedRecord(null)}
      />
      <EconomicControlModal
        open={economicControlOpen}
        data={data}
        contributoMemory={contributoMemory}
        onClose={() => setEconomicControlOpen(false)}
        onPaymentSaved={handleDetailPaymentSaved}
        onError={failDetail}
        onOpenPagoPa={() => {
          setEconomicControlOpen(false)
          openPagoPaModal()
        }}
      />
      <a className="iu-fas-back-top" href="#fascicolo-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex
        context="fascicolo-dettaglio"
        contextType="case"
        caseId={f.id || id}
        clientId={clientId}
        activeContext={{ context_type: 'case', case_id: f.id || id, client_id: clientId }}
        title="Lex AI fascicolo"
        body="Posso sintetizzare profilo, documenti, attività, scadenze, cancelleria, parti e prossime azioni del fascicolo aperto."
        primaryHref="#lex"
        primaryLabel="Apri Lex fascicolo"
        secondaryHref={quadroHref}
        secondaryLabel="Quadro fascicolo"
      />
    </main>
  )
}

function moneyFrom(data: FascicoloDetailData, id: string, fallback = '€ 0,00') {
  return data.economics.find((item) => item.id === id)?.value || fallback
}

function workflowFrom(data: FascicoloDetailData, matcher: RegExp, fallbackLabel: string) {
  return data.workflow.find((item) => matcher.test(item.label)) || { label: fallbackLabel, value: 'Non collegato', note: 'Collega la fase operativa registrata quando serve.', tone: 'neutral' as const, href: '/preventivi/' }
}

function QuadroMiniCard({ label, value, note, tone = 'neutral', href }:{label:string; value:string|number; note?:string; tone?:FascicoloRow['tone']; href?:string}) {
  const body = <><Badge tone={tone}>{label}</Badge><strong>{value}</strong>{note ? <span>{note}</span> : null}</>
  return href && href !== '#' ? <a className="iu-fas-quadro-mini" href={href}>{body}</a> : <article className="iu-fas-quadro-mini">{body}</article>
}

function QuadroAxis({ id, title, icon, status, tone = 'primary', children }:{id:string; title:string; icon:ReactNode; status:string; tone?:FascicoloRow['tone']; children:ReactNode}) {
  return (
    <section id={id} className="iu-fas-quadro-axis">
      <header>
        <span>{icon}</span>
        <div><strong>{title}</strong><small>{status}</small></div>
        <Badge tone={tone}>{status}</Badge>
      </header>
      <div className="iu-fas-quadro-axis__body">{children}</div>
    </section>
  )
}

function QuadroPage({ id }:{id:string}) {
  const [data, setData] = useState<FascicoloDetailData>(emptyFascicoloDetail)
  const [loading, setLoading] = useState(true)
  useEffect(() => { let active = true; getFascicoloDetail(id, { include: 'all' }).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [id])
  const f = data.fascicolo
  const clientId = data.client?.id || f.clientId
  const encodedId = encodeURIComponent(f.id || id)
  const operationalHref = f.operationalHref || `/fascicoli/${encodedId}`
  const detailHref = f.href || `/fascicoli/${encodedId}`
  const exportPdfHref = data.actions.exportPdf || f.exportPdfHref
  const preventivo = workflowFrom(data, /preventiv/i, 'Preventivo')
  const conferimento = workflowFrom(data, /conferiment|incaric/i, 'Conferimento')
  const signedDocuments = data.documents.filter((doc) => doc.signed).length
  const unsignedDocuments = Math.max(0, data.documents.length - signedDocuments)
  const qualityOk = data.quality.filter((item) => item.ok).length
  const qualityIssues = Math.max(0, data.quality.length - qualityOk + (Number(f.alerts) || 0))
  const qualityStatus = qualityIssues ? `${qualityIssues} verifiche` : 'OK'
  const nextDeadline = data.deadlines[0]
  const nextAppointment = data.appointments[0]
  const valore = moneyFrom(data, 'valore', f.value || '€ 0,00')
  const compenso = moneyFrom(data, 'compenso', f.agreedFee || f.quotedValue || '€ 0,00')
  const parcelle = moneyFrom(data, 'parcelle')
  const tempo = moneyFrom(data, 'tempo', '0 h')
  const fatturaPa = data.economics.find((item) => item.id === 'fatturapa')
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<Gauge size={34}/>} title={data.requestError ? 'Dati fascicolo non caricati' : 'Quadro non disponibile'} action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>{data.requestError || 'Il fascicolo non è disponibile o non hai i permessi per aprire il quadro.'}</EmptyState></main>
  return (
    <main id="fascicolo-quadro-top" className="iu-content iu-fascicoli-page iu-fascicolo-quadro-page">
      <section className="iu-fas-hero iu-fas-quadro-hero">
        <div><span className="iu-fas-eyebrow"><Gauge size={16}/> Quadro fascicolo</span><h1>{f.ref} - {f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge><span>{f.object || f.subtitle || 'Vista sinottica della pratica'}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href={detailHref}><FolderOpen size={15}/> Dettaglio</Button><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button variant="primary" href={exportPdfHref} disabled={!exportPdfHref} title={!exportPdfHref ? 'PDF fascicolo non disponibile' : undefined}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-quadro-strip"><strong>{f.rg}</strong><span>{f.court}</span><span>{f.client}</span><span>{loading ? 'Caricamento quadro...' : 'Dati aggiornati'}</span></section>
      <section className="iu-fas-quadro-kpis" aria-label="Indicatori quadro fascicolo">
        <StatCard icon={<FileText size={19}/>} label="Documenti" value={data.documents.length} note={`${signedDocuments} firmati`} tone="primary"/>
        <StatCard icon={<FileCheck2 size={19}/>} label="Da firmare" value={unsignedDocuments} note="firma / verifica" tone={unsignedDocuments ? 'warning' : 'success'}/>
        <StatCard icon={<Send size={19}/>} label="Cancelleria" value={data.deposits.length} note={data.deposits[0]?.status || 'nessuna PEC'} tone="purple"/>
        <StatCard icon={<Clock3 size={19}/>} label="Scadenze aperte" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.date || nextAppointment?.date || 'nessuna data'} tone="info"/>
        <StatCard icon={<WalletCards size={19}/>} label="Parcelle" value={parcelle} note={`valore ${valore}`} tone="orange"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Conformità" value={qualityStatus} note={qualityIssues ? 'da verificare' : 'nessun blocco critico'} tone={qualityIssues ? 'warning' : 'success'} href="#conformita"/>
      </section>
      <section className="iu-fas-quadro-client">
        <Panel title="Cliente e dati processuali" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}><KvGrid items={[{ label: 'Cliente', value: f.client, href: data.client?.href }, { label: 'Tribunale', value: f.court }, { label: 'RG', value: f.rg, mono: true }, { label: 'Giudice', value: f.judge || 'n.d.' }, { label: 'Sezione', value: f.section || 'n.d.' }, { label: 'Valore', value: valore }]}/></Panel>
      </section>
      <section className="iu-fas-quadro-grid">
        <QuadroAxis id="commerciale" title="Commerciale" icon={<BriefcaseBusiness size={18}/>} status={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'Conferito' : preventivo.value !== 'Non collegato' && preventivo.value !== '0' ? 'Da conferire' : 'Da creare'} tone={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Preventivo" value={preventivo.value} note={preventivo.note} tone={preventivo.tone} href={preventivo.href}/><QuadroMiniCard label="Conferimento" value={conferimento.value} note={conferimento.note} tone={conferimento.tone} href={conferimento.href}/><QuadroMiniCard label="Compenso" value={compenso} note="dato contrattuale del fascicolo" tone="purple" href="/preventivi/"/></div><a className="iu-fas-inline-link" href="/preventivi/"><Plus size={14}/> Gestisci preventivi e incarichi</a></QuadroAxis>
        <QuadroAxis id="operativo" title="Operativo" icon={<ClipboardCheck size={18}/>} status={formatFascicoloStatus(f.status)} tone={f.tone}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Stato" value={formatFascicoloStatus(f.status)} note={f.nextDeadline || 'nessuna prossima scadenza'} tone={f.tone} href={detailHref}/><QuadroMiniCard label="Udienze / scadenze" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.title || nextAppointment?.title || 'nessun evento aperto'} tone="info" href={`${detailHref}#udienze`}/><QuadroMiniCard label="Cancelleria" value={data.deposits.length} note={data.deposits[0]?.status || 'nessuna PEC collegata'} tone="purple" href={`${detailHref}#cancelleria`}/></div></QuadroAxis>
        <QuadroAxis id="conformita" title="Conformità" icon={<ShieldCheck size={18}/>} status={qualityStatus} tone={qualityIssues ? 'warning' : 'success'}><div className="iu-fas-quadro-quality">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}{!data.quality.length ? <p className="iu-empty">Nessuna verifica registrata.</p> : null}</div><a className="iu-fas-inline-link" href={`${detailHref}#conformita`}><ShieldCheck size={14}/> Apri controlli qualità</a></QuadroAxis>
        <QuadroAxis id="economico" title="Contesto economico" icon={<WalletCards size={18}/>} status={parcelle === '€ 0,00' ? 'Da valorizzare' : 'Valorizzato'} tone={parcelle === '€ 0,00' ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Valore causa" value={valore} note="profilo fascicolo" tone="primary" href={`${detailHref}#profilo`}/><QuadroMiniCard label="Parcelle" value={parcelle} note="documenti economici collegati" tone="success" href="/fatturazione/"/>{fatturaPa ? <QuadroMiniCard label={fatturaPa.label} value={fatturaPa.value} note={fatturaPa.note} tone={fatturaPa.tone} href={fatturaPa.href}/> : null}<QuadroMiniCard label="Tempo" value={tempo} note="voci timesheet valorizzabili" tone="info" href="/timesheet"/></div></QuadroAxis>
        <QuadroAxis id="documenti" title="Documenti" icon={<FileText size={18}/>} status={unsignedDocuments ? `${unsignedDocuments} da firmare` : 'Completi'} tone={unsignedDocuments ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.documents.length} note="documenti fascicolo" tone="primary" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Firmati" value={signedDocuments} note="depositabili / verificati" tone="success" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Da firmare" value={unsignedDocuments} note="controllo operativo" tone={unsignedDocuments ? 'warning' : 'success'} href={`${detailHref}#documenti`}/></div></QuadroAxis>
        <QuadroAxis id="soggetti" title="Soggetti e parti" icon={<UsersRound size={18}/>} status={data.parties.length ? `${data.parties.length} collegati` : 'Da verificare'} tone={data.parties.length ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.parties.length} note="assistiti, controparti e ruoli" tone={data.parties.length ? 'success' : 'warning'} href={`${detailHref}#soggetti`}/><QuadroMiniCard label="Cliente" value={data.client?.name || f.client || 'n.d.'} note="assistito principale" tone="primary" href={data.client?.href || `${detailHref}#profilo`}/><QuadroMiniCard label="Controparte" value={f.counterparty || 'n.d.'} note="dato fascicolo o parte strutturata" tone={f.counterparty ? 'orange' : 'neutral'} href={`${detailHref}#soggetti`}/></div></QuadroAxis>
        <QuadroAxis id="cancelleria" title="Comunicazioni e cancelleria" icon={<Gavel size={18}/>} status={data.deposits.length ? `${data.deposits.length} PEC` : 'Nessuna PEC'} tone={data.deposits.length ? 'purple' : 'neutral'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Comunicazioni" value={data.deposits.length} note={data.deposits[0]?.message || 'nessuna PEC collegata'} tone="purple" href={`${detailHref}#cancelleria`}/><QuadroMiniCard label="Storico" value={data.history.length} note="transizioni e stati fascicolo" tone="info" href={`${detailHref}#gestione`}/></div></QuadroAxis>
        <QuadroAxis id="telematico" title="Servizi telematici" icon={<Send size={18}/>} status={data.telematic.length ? 'Presidiati' : 'Da configurare'} tone={data.telematic.length ? 'primary' : 'warning'}><div className="iu-fas-quadro-flow">{data.telematic.slice(0, 3).map((item) => <QuadroMiniCard key={item.label} label={item.label} value={item.value} note={item.note} tone={item.tone} href={item.href}/>)}</div><a className="iu-fas-inline-link" href="/telematico"><Send size={14}/> Apri servizi telematici</a></QuadroAxis>
      </section>
      <a className="iu-fas-back-top" href="#fascicolo-quadro-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex
        context="fascicolo-quadro"
        contextType="case"
        caseId={f.id || id}
        clientId={clientId}
        activeContext={{ context_type: 'case', case_id: f.id || id, client_id: clientId }}
        title="Lex AI quadro"
        body="Posso leggere il quadro della pratica, riassumere commerciale, operativo, conformità, economico e documenti, e suggerire la prossima azione utile."
        primaryHref="#lex"
        primaryLabel="Apri Lex quadro"
        secondaryHref={detailHref}
        secondaryLabel="Apri dettaglio"
      />
    </main>
  )
}

function ExportPage() {
  const [data, setData] = useState<FascicoliExportData>(emptyFascicoliExport)
  const [loading, setLoading] = useState(true)
  const [format, setFormat] = useState('pdf')
  const [type, setType] = useState<FascicoloTipo>('tutti')
  const [status, setStatus] = useState<FascicoloStato>('tutti')
  const [query, setQuery] = useState('')
  useEffect(() => { let active = true; getFascicoliExport().then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [])
  const params = new URLSearchParams()
  if (query) params.set('q', query)
  if (type !== 'tutti') params.set('tipo', type.toUpperCase())
  if (status !== 'tutti') params.set('stato', status.toUpperCase())
  const href = `/fascicoli/export.${format === 'csv' ? 'csv' : 'pdf'}${params.toString() ? `?${params.toString()}` : ''}`
  return (
    <main className="iu-content iu-fascicoli-page iu-fas-export-page">
      <section className="iu-fas-hero"><div><span className="iu-fas-eyebrow"><Download size={16}/> Esporta</span><h1>Esporta fascicoli</h1><p>PDF lista, CSV operativo, PDF fascicolo singolo e ZIP archivio, con operazioni tracciate.</p></div><div className="iu-fas-hero__actions"><Button href="/fascicoli"><FolderOpen size={15}/> Fascicoli</Button><Button href="/fascicoli/archivio"><Archive size={15}/> Archivio</Button></div></section>
      <section className="iu-fas-stats"><StatCard icon={<FolderOpen size={19}/>} label="Totali" value={data.summary.total} note="in archivio" tone="primary"/><StatCard icon={<Archive size={19}/>} label="Archiviati" value={data.summary.archived} note="da conservare" tone="neutral"/><StatCard icon={<FileText size={19}/>} label="Documenti" value={data.summary.documents} note="conteggio fascicoli" tone="purple"/></section>
      <section className="iu-fas-export-layout"><Panel title="Esportazione fascicoli" subtitle={loading ? 'Caricamento...' : `Archivio ${data.source}`} icon={<FileDown size={17}/>}><div className="iu-fas-export-builder"><label><span>Formato</span><select value={format} onChange={(event) => setFormat(event.target.value)}><option value="pdf">PDF lista</option><option value="csv">CSV</option></select></label><label><span>Ricerca</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="numero, titolo, cliente..."/></label><label><span>Tipo</span><select value={type} onChange={(event) => setType(event.target.value as FascicoloTipo)}>{data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label}</option>)}</select></label><label><span>Stato</span><select value={status} onChange={(event) => setStatus(event.target.value as FascicoloStato)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label}</option>)}</select></label><a className="iu-fas-download-main" href={href}><Download size={16}/> Scarica export</a></div></Panel><Panel title="Campi inclusi" icon={<ListChecks size={17}/>}><div className="iu-fas-export-fields">{data.fields.map((field) => <label key={field.key}><input type="checkbox" defaultChecked={field.checked} readOnly/> {field.label}</label>)}</div></Panel><Panel title="Preset rapidi" icon={<Sparkles size={17}/>}><div className="iu-fas-side-cards">{data.presets.map((preset) => <a href={preset.href} key={preset.label}><Badge tone={preset.tone}>{preset.label}</Badge><span>{preset.description}</span></a>)}</div></Panel></section>
      <Panel title="Fascicoli recenti esportabili singolarmente" icon={<FolderOpen size={17}/>} count={data.recent.length}><div className="iu-fas-export-recent">{data.recent.map((item) => <a href={item.exportPdfHref} key={item.id}><FileDown size={15}/><strong>{item.ref}</strong><span>{item.title}</span></a>)}</div></Panel>
      <FloatingLex context="export-fascicoli" title="Lex AI export" body="Posso suggerire quali campi esportare, preparare una sintesi per il cliente o controllare se mancano dati prima dell'archiviazione." primaryHref="#lex" primaryLabel="Apri Lex export" secondaryHref="/fascicoli/esporta" secondaryLabel="Esporta fascicoli" />
    </main>
  )
}

function FascicoloDepositoLoading({ id }: { id: string }) {
  return (
    <main className="iu-content iu-fascicoli-page iu-fascicolo-deposit-page">
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div>
          <span className="iu-fas-eyebrow"><Send size={16}/> Deposito telematico</span>
          <h1>Prepara deposito</h1>
          <p>Caricamento del modulo deposito richiesto dall'avvocato.</p>
        </div>
        <div className="iu-fas-hero__actions">
          <Button href={`/fascicoli/${encodeURIComponent(id)}`}><ArrowLeft size={15}/> Torna al fascicolo</Button>
        </div>
      </section>
      <section className="iu-fas-loading-panel" aria-live="polite">
        <RefreshCw size={18}/>
        <div>
          <strong>Sto aprendo il deposito</strong>
          <span>Il resto dell'applicazione resta leggero: busta, firme e controlli vengono caricati solo adesso.</span>
        </div>
      </section>
    </main>
  )
}

export function FascicoliPage() {
  const route = parseRoute()
  if (route.kind === 'archive') return <ArchivePage/>
  if (route.kind === 'new') return <FascicoloFormPage mode="new"/>
  if (route.kind === 'export') return <ExportPage/>
  if (route.kind === 'quadro') return <QuadroPage id={route.id}/>
  if (route.kind === 'depositPrepare') {
    return (
      <Suspense fallback={<FascicoloDepositoLoading id={route.id}/>}>
        <FascicoloDepositoPage id={route.id}/>
      </Suspense>
    )
  }
  if (route.kind === 'signature') return <SignaturePage id={route.id} documentId={route.documentId}/>
  if (route.kind === 'edit') return <FascicoloFormPage mode="edit" id={route.id}/>
  if (route.kind === 'detail') return <DetailPage id={route.id}/>
  return <FascicoliListPage/>
}
