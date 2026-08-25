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
  EyeOff,
  FileArchive,
  FileCheck2,
  FileDown,
  FileSignature,
  FileSearch2,
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
  List,
  LayoutGrid,
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
  Tags,
  TableProperties,
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
  type FascicoliFieldFilterKey,
  type FascicoliFieldFilters,
  type FascicoliDisplayMode,
  type FascicoliGroupMode,
  type FascicoliRowDensity,
  type FascicoliTableColumnKey,
  type FascicoliPageData,
  type FascicoliPageParams,
  type FascicoloPaymentFilter,
  type FascicoliExportData,
  type FascicoloActivity,
  type FascicoloAuditTrail,
  type FascicoloDeadline,
  type FascicoloDocumentPresidioAction,
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

type SortKey = 'recenti' | 'rg' | 'cliente' | 'scadenza' | 'documenti' | 'titolo' | 'ufficio' | 'apertura' | 'stato' | 'gruppo' | 'responsabile' | 'valore'
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
  titolo: 'Titolo',
  ufficio: 'Ufficio giudiziario',
  apertura: 'Data di apertura',
  stato: 'Stato',
  gruppo: 'Gruppo',
  responsabile: 'Responsabile',
  valore: 'Valore causa',
}

type PracticeFilterSection = 'pratica' | 'procedimento' | 'persone'

const practiceFieldFilters: Array<{
  key: FascicoliFieldFilterKey
  label: string
  placeholder: string
  section: PracticeFilterSection
  inputMode?: 'text' | 'numeric' | 'decimal'
}> = [
  { key: 'register', label: 'Registro', placeholder: 'Civile, lavoro, SICID...', section: 'pratica' },
  { key: 'value', label: 'Valore causa', placeholder: 'Importo', section: 'pratica', inputMode: 'decimal' },
  { key: 'object', label: 'Oggetto', placeholder: 'Oggetto della pratica', section: 'pratica' },
  { key: 'denomination', label: 'Denominazione', placeholder: 'Titolo del fascicolo', section: 'pratica' },
  { key: 'internal_ref', label: 'Riferimento cartaceo', placeholder: 'Riferimento interno', section: 'pratica' },
  { key: 'opened_year', label: 'Anno apertura', placeholder: 'es. 2026', section: 'pratica', inputMode: 'numeric' },
  { key: 'archived_year', label: 'Anno archiviazione', placeholder: 'es. 2025', section: 'pratica', inputMode: 'numeric' },
  { key: 'operational_status', label: 'Stato pratica', placeholder: 'Stato operativo', section: 'pratica' },
  { key: 'custom_1', label: 'Campo personalizzato 1', placeholder: 'Valore', section: 'pratica' },
  { key: 'custom_2', label: 'Campo personalizzato 2', placeholder: 'Valore', section: 'pratica' },
  { key: 'group', label: 'Gruppo', placeholder: 'Nome gruppo', section: 'pratica' },
  { key: 'rg_year', label: 'Anno RG', placeholder: 'es. 2026', section: 'procedimento', inputMode: 'numeric' },
  { key: 'rg', label: 'Numero RG', placeholder: 'Numero o RG completo', section: 'procedimento' },
  { key: 'section', label: 'Sezione', placeholder: 'Sezione giudiziaria', section: 'procedimento' },
  { key: 'section_role', label: 'Ruolo di sezione', placeholder: 'Numero di ruolo', section: 'procedimento' },
  { key: 'judge', label: 'Giudice', placeholder: 'Nome del giudice', section: 'procedimento' },
  { key: 'notes', label: 'Annotazioni', placeholder: 'Testo nelle annotazioni', section: 'procedimento' },
  { key: 'clerk', label: 'Cancelliere', placeholder: 'Nome del cancelliere', section: 'procedimento' },
  { key: 'holder', label: 'Titolare', placeholder: 'Avvocato titolare', section: 'persone' },
  { key: 'responsible', label: 'Responsabile', placeholder: 'Avvocato responsabile', section: 'persone' },
  { key: 'opposing_lawyer', label: 'Avvocato controparte', placeholder: 'Nome dell’avvocato', section: 'persone' },
  { key: 'ctu', label: 'CTU', placeholder: 'Consulente tecnico', section: 'persone' },
  { key: 'ctp', label: 'CTP', placeholder: 'Consulente di parte', section: 'persone' },
  { key: 'claimant', label: 'Attore o ricorrente', placeholder: 'Nome della parte', section: 'persone' },
  { key: 'respondent', label: 'Convenuto o resistente', placeholder: 'Nome della parte', section: 'persone' },
]

type FascicoliTableColumnGroup = 'Pratica' | 'Procedimento' | 'Persone' | 'Controlli'

type FascicoliTableColumnDefinition = {
  key: FascicoliTableColumnKey
  label: string
  group: FascicoliTableColumnGroup
  width: number
  required?: boolean
}

const fascicoliTableColumns: FascicoliTableColumnDefinition[] = [
  { key: 'ref', label: 'Riferimento', group: 'Pratica', width: 118, required: true },
  { key: 'internal_ref', label: 'Rif. cartaceo', group: 'Pratica', width: 130 },
  { key: 'title', label: 'Titolo / oggetto', group: 'Pratica', width: 300, required: true },
  { key: 'object', label: 'Oggetto', group: 'Pratica', width: 240 },
  { key: 'type', label: 'Tipo', group: 'Pratica', width: 105 },
  { key: 'client', label: 'Cliente', group: 'Persone', width: 170 },
  { key: 'court', label: 'Ufficio giudiziario', group: 'Procedimento', width: 190 },
  { key: 'procedure_type', label: 'Procedimento', group: 'Procedimento', width: 160 },
  { key: 'register', label: 'Registro', group: 'Procedimento', width: 130 },
  { key: 'section', label: 'Sezione', group: 'Procedimento', width: 130 },
  { key: 'section_role', label: 'Ruolo di sezione', group: 'Procedimento', width: 135 },
  { key: 'judge', label: 'Giudice', group: 'Persone', width: 160 },
  { key: 'opposing_lawyer', label: 'Avvocato controparte', group: 'Persone', width: 180 },
  { key: 'holder', label: 'Titolare', group: 'Persone', width: 160 },
  { key: 'responsible', label: 'Responsabile', group: 'Persone', width: 160 },
  { key: 'counterparty', label: 'Controparte', group: 'Persone', width: 180 },
  { key: 'claimant', label: 'Attore / ricorrente', group: 'Persone', width: 180 },
  { key: 'clerk', label: 'Cancelliere', group: 'Persone', width: 150 },
  { key: 'ctu', label: 'CTU', group: 'Persone', width: 150 },
  { key: 'ctp', label: 'CTP', group: 'Persone', width: 150 },
  { key: 'notes', label: 'Annotazioni', group: 'Pratica', width: 260 },
  { key: 'operational_status', label: 'Stato operativo', group: 'Controlli', width: 150 },
  { key: 'custom_1', label: 'Campo personalizzato 1', group: 'Pratica', width: 180 },
  { key: 'custom_2', label: 'Campo personalizzato 2', group: 'Pratica', width: 180 },
  { key: 'group', label: 'Gruppo', group: 'Pratica', width: 140 },
  { key: 'case_value', label: 'Valore causa', group: 'Pratica', width: 125 },
  { key: 'rg', label: 'N. causa', group: 'Procedimento', width: 130 },
  { key: 'rg_number', label: 'Numero RG', group: 'Procedimento', width: 110 },
  { key: 'rg_year', label: 'Anno RG', group: 'Procedimento', width: 95 },
  { key: 'next_deadline', label: 'Prossima scadenza', group: 'Controlli', width: 135 },
  { key: 'status', label: 'Stato', group: 'Controlli', width: 120 },
  { key: 'documents', label: 'Documenti', group: 'Controlli', width: 95 },
  { key: 'unread_communications', label: 'Comunicazioni', group: 'Controlli', width: 120 },
  { key: 'alerts', label: 'Avvisi', group: 'Controlli', width: 85 },
  { key: 'opened_at', label: 'Data apertura', group: 'Pratica', width: 120 },
  { key: 'closed_at', label: 'Data archiviazione', group: 'Pratica', width: 135 },
  { key: 'updated_at', label: 'Ultimo aggiornamento', group: 'Controlli', width: 155 },
]

const defaultFascicoliTableColumns = defaultFascicoliFilterPreferences.visibleColumns
const fascicoliTableColumnGroups: FascicoliTableColumnGroup[] = ['Pratica', 'Procedimento', 'Persone', 'Controlli']
const fascicoliTableColumnPresets: Array<{ label: string; columns: FascicoliTableColumnKey[] }> = [
  { label: 'Essenziali', columns: defaultFascicoliTableColumns },
  { label: 'Procedimento', columns: ['ref', 'title', 'court', 'register', 'section', 'section_role', 'rg', 'judge', 'next_deadline', 'status'] },
  { label: 'Persone', columns: ['ref', 'title', 'client', 'counterparty', 'claimant', 'opposing_lawyer', 'holder', 'responsible', 'ctu', 'ctp', 'status'] },
  { label: 'Tutte', columns: fascicoliTableColumns.map((column) => column.key) },
]

const emptyPracticeFieldFilters: FascicoliFieldFilters = {}

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

function initialDisplayMode(): FascicoliDisplayMode {
  const value = initialUrlParam('visualizzazione', 'tabella')
  return ['tabella', 'compatta', 'schede'].includes(value) ? value as FascicoliDisplayMode : 'tabella'
}

function initialGroupMode(): FascicoliGroupMode {
  const value = initialUrlParam('raggruppa', 'nessuno')
  return ['nessuno', 'gruppo', 'stato', 'tipo', 'ufficio', 'anno', 'responsabile'].includes(value) ? value as FascicoliGroupMode : 'nessuno'
}

function initialFieldFilters(): FascicoliFieldFilters {
  const params = new URLSearchParams(window.location.search)
  return Object.fromEntries(
    practiceFieldFilters
      .map(({ key }) => [key, params.get(`f_${key}`)?.trim() || ''] as const)
      .filter(([, value]) => value),
  ) as FascicoliFieldFilters
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
    'secondary_sort',
    'view',
    'vista',
    'visualizzazione',
    'raggruppa',
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
  ].some((name) => params.has(name)) || Array.from(params.keys()).some((name) => name.startsWith('f_'))
}

function initialStatusFilter(): FascicoloStato {
  const raw = initialUrlParam('status').toLowerCase()
  return ['aperto', 'in_corso', 'definito', 'da_archiviare', 'archiviato', 'sospeso'].includes(raw) ? raw as FascicoloStato : 'tutti'
}

function initialTypeFilter(): FascicoloTipo {
  const raw = initialUrlParam('type').toLowerCase()
  return ['civile', 'penale', 'amministrativo', 'tributario', 'lavoro', 'stragiudiziale', 'altro'].includes(raw)
    ? raw as FascicoloTipo
    : 'tutti'
}

function initialSortFilter(): SortKey {
  const raw = initialUrlParam('sort', 'rg').toLowerCase()
  return raw in sortLabels ? raw as SortKey : 'rg'
}

function initialPaymentFilter(name: string): FascicoloPaymentFilter {
  const raw = initialUrlParam(name).toLowerCase()
  return ['non_previsto', 'da_registrare', 'pagato', 'parziale', 'da_emettere'].includes(raw) ? raw as FascicoloPaymentFilter : 'tutti'
}

function toSavedSortKey(value: string): SortKey {
  return value in sortLabels ? value as SortKey : defaultFascicoliFilterPreferences.sort as SortKey
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
    secondarySort: preferences.secondarySort,
    view: preferences.view,
    displayMode: preferences.displayMode,
    groupBy: preferences.groupBy,
    visibleColumns: preferences.visibleColumns,
    rowDensity: preferences.rowDensity,
    court: preferences.court.trim(),
    fieldFilters: Object.fromEntries(Object.entries(preferences.fieldFilters).sort(([a], [b]) => a.localeCompare(b))),
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
    params.secondarySort || '',
    params.view || 'operativa',
    JSON.stringify(Object.fromEntries(Object.entries(params.fieldFilters || {}).sort(([a], [b]) => a.localeCompare(b)))),
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
  const section = element instanceof HTMLDetailsElement ? element : element?.closest('details')
  if (section instanceof HTMLDetailsElement && !section.open) section.open = true
  if (element) window.requestAnimationFrame(() => (section || element).scrollIntoView({ behavior: 'smooth', block: 'start' }))
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

type DeadlineAlertItem = FascicoliPageData['deadlines'][number]

function startOfLocalDay(value = new Date()): Date {
  const day = new Date(value)
  day.setHours(0, 0, 0, 0)
  return day
}

function parseDeadlineDate(value: string): Date | null {
  const raw = String(value || '').trim()
  if (!raw) return null
  const dateOnly = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (dateOnly) {
    return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
  }
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function deadlineAlertWindow(item: DeadlineAlertItem, today = new Date()) {
  const parsed = parseDeadlineDate(item.dateIso)
  if (!parsed) return 'unknown'
  const current = startOfLocalDay(today).getTime()
  const deadline = startOfLocalDay(parsed).getTime()
  const nextSevenDays = current + 7 * 24 * 60 * 60 * 1000
  if (deadline < current) return 'overdue'
  if (deadline <= nextSevenDays) return 'upcoming7'
  return 'outside'
}

function isDeadlineAlertUpcoming7(item: DeadlineAlertItem): boolean {
  return deadlineAlertWindow(item) === 'upcoming7'
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
  result = result.replace(/Studio Telematico|QuickOrganizer/gi, 'regole del deposito')
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

type CatalogAssignmentView = {
  id: string
  document_id: string
  profile_id: string
  document_nature: string
  document_label: string
  document_section: string
  deposit_role: string
  deposit_candidate: boolean
  status: 'proposed' | 'confirmed' | 'review_required' | 'superseded' | 'rejected' | string
  confidence: number
  source_state: 'verified_snapshot' | 'manual_browser_evidence' | 'review_required' | string
  reason: string
  legal_area?: string
  legal_branch?: string
  legal_subfamily?: string
  updated_at: string
  confirmed_at: string | null
  candidates: Array<{ profile_id: string; document_label: string; document_section: string; document_nature: string; deposit_role: string; confidence: number; reason: string }>
  evidence: Array<{ type: string; locator: string; excerpt: string; weight: number }>
}

function catalogProfileLabel(assignment: CatalogAssignmentView): string {
  return assignment.legal_subfamily || assignment.legal_branch || assignment.legal_area || 'Profilo da definire'
}

function catalogEvidenceTitle(type: string): string {
  if (type === 'document_identity') return 'Identità letta dal contenuto'
  if (type === 'extracted_text') return 'Testo indicizzato'
  if (type === 'procedural_signal') return 'Segnalazione procedurale'
  if (type === 'legal_source') return 'Fonte ufficiale del profilo'
  if (type === 'fascicolo_context') return 'Contesto del fascicolo'
  return 'Origine e metadati'
}

function CatalogEvidenceDisclosure({
  assignment,
  document,
  onPreview,
}: {
  assignment: CatalogAssignmentView
  document?: FascicoloDocument
  onPreview: (preview: PreviewDocument) => void
}) {
  const identityEvidence = assignment.evidence.filter((entry) => entry.type === 'document_identity' || entry.type === 'extracted_text')
  const proceduralEvidence = assignment.evidence.filter((entry) => entry.type === 'procedural_signal')
  const sources = assignment.evidence.filter((entry) => entry.type === 'legal_source')
  return (
    <section className="iu-fas-catalog__evidence" aria-label={`Prova della catalogazione ${assignment.document_label}`}>
      <div>
        <strong>Prova e fonti della catalogazione</strong>
        <span>La proposta nasce dal contenuto indicizzato; le segnalazioni processuali restano distinte dall'identità del documento.</span>
      </div>
      {identityEvidence.length ? <ul>{identityEvidence.map((entry, index) => <li key={`${entry.locator}-${index}`}><b>{catalogEvidenceTitle(entry.type)}</b><span>{entry.excerpt}</span></li>)}</ul> : null}
      {proceduralEvidence.length ? <div className="iu-fas-catalog__signals"><strong>Segnalazioni procedurali</strong><ul>{proceduralEvidence.map((entry, index) => <li key={`${entry.locator}-${index}`}><b>{entry.excerpt}</b></li>)}</ul></div> : null}
      {sources.length ? <div className="iu-fas-catalog__sources"><strong>Fonti ufficiali del profilo</strong><ul>{sources.map((entry, index) => <li key={`${entry.locator}-${index}`}>{entry.excerpt || 'Fonte ufficiale versionata nel catalogo.'}</li>)}</ul></div> : null}
      {document?.actions.preview ? <button type="button" title="Apri il documento sorgente nel lettore interno" onClick={() => onPreview({ name: document.name, url: document.actions.preview, downloadUrl: document.actions.download })}><Eye size={14}/> Apri la prova nel lettore</button> : null}
    </section>
  )
}

type CatalogDocumentView = {
  document_id: string
  filename: string
  supported: boolean
  indexed: boolean
  assignment: CatalogAssignmentView | null
}

type CatalogPayload = {
  summary: { total: number; proposed: number; confirmed: number; review_required: number; errors: number; waiting_for_index: number; source_documents: number }
  run: { processed: number; proposed: number; review_required: number; waiting_for_index: number; errors: string[] }
  documents: CatalogDocumentView[]
}

function catalogTone(status: string): FascicoloRow['tone'] {
  if (status === 'confirmed') return 'success'
  if (status === 'review_required') return 'warning'
  if (status === 'proposed') return 'info'
  return 'neutral'
}

function catalogStatusLabel(status: string): string {
  if (status === 'confirmed') return 'Confermato'
  if (status === 'review_required') return 'Da verificare'
  if (status === 'proposed') return 'Proposto'
  if (status === 'rejected') return 'Respinto'
  return 'In attesa'
}

function catalogSourceLabel(state: string): string {
  if (state === 'verified_snapshot') return 'Fonti ufficiali versionate'
  if (state === 'manual_browser_evidence') return 'Fonte istituzionale verificata nel browser'
  if (state === 'manual_override') return 'Classificazione confermata manualmente dall’avvocato'
  return 'Fonti da riesaminare'
}

type CatalogOverrideDraft = {
  document_label: string
  document_section: string
  document_nature: string
  deposit_role: string
  deposit_candidate: boolean
  note: string
}

const MANUAL_CATALOG_NATURES = new Set([
  'atto_principale', 'atto_processuale', 'provvedimento', 'procura', 'notifica',
  'comunicazione', 'contratto', 'economico', 'allegato', 'da_verificare',
])

function catalogNatureForManualCorrection(value: string): CatalogOverrideDraft['document_nature'] {
  const normalized = String(value || '').trim()
  if (MANUAL_CATALOG_NATURES.has(normalized)) return normalized
  if (['relata', 'prova_notifica', 'attestazione_conformita'].includes(normalized)) return 'notifica'
  if (['contributo_unificato', 'gratuito_patrocinio', 'liquidazione_spese_giustizia', 'economia_fascicolo'].includes(normalized)) return 'economico'
  if (['relazione_peritale_ctu', 'nomina_ctp'].includes(normalized)) return 'allegato'
  if (['provvedimento', 'decreto_liquidazione_ctu', 'ordinanza_ufficio'].includes(normalized)) return 'provvedimento'
  return 'atto_processuale'
}

function CatalogCorrectionForm({
  assignment,
  busy,
  onSubmit,
  onCancel,
}: {
  assignment: CatalogAssignmentView
  busy: boolean
  onSubmit: (draft: CatalogOverrideDraft) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState<CatalogOverrideDraft>({
    document_label: assignment.document_label,
    document_section: assignment.document_section || 'da-verificare',
    document_nature: catalogNatureForManualCorrection(assignment.document_nature),
    deposit_role: assignment.deposit_role || 'allegato',
    deposit_candidate: Boolean(assignment.deposit_candidate),
    note: '',
  })
  const update = <K extends keyof CatalogOverrideDraft>(key: K, value: CatalogOverrideDraft[K]) => setDraft((current) => ({ ...current, [key]: value }))
  return (
    <form className="iu-fas-catalog__correction" onSubmit={(event) => { event.preventDefault(); onSubmit(draft) }}>
      <strong>Correggi la catalogazione nel fascicolo</strong>
      <label>Denominazione<input value={draft.document_label} maxLength={160} required onChange={(event) => update('document_label', event.currentTarget.value)} /></label>
      <label>Sezione<select value={draft.document_section} onChange={(event) => update('document_section', event.currentTarget.value)}><option value="atti">Atti</option><option value="provvedimenti">Provvedimenti</option><option value="procure">Procure</option><option value="notifiche">Notifiche</option><option value="comunicazioni">Comunicazioni</option><option value="contratti">Contratti e incarichi</option><option value="pagamenti">Economia e pagamenti</option><option value="allegati">Allegati e supporti</option><option value="da-verificare">Da verificare</option></select></label>
      <label>Natura<select value={draft.document_nature} onChange={(event) => update('document_nature', event.currentTarget.value)}><option value="atto_principale">Atto principale</option><option value="atto_processuale">Atto processuale</option><option value="provvedimento">Provvedimento</option><option value="procura">Procura</option><option value="notifica">Notifica</option><option value="comunicazione">Comunicazione</option><option value="contratto">Contratto o incarico</option><option value="economico">Documento economico</option><option value="allegato">Allegato</option><option value="da_verificare">Da verificare</option></select></label>
      <label>Ruolo deposito<select value={draft.deposit_role} onChange={(event) => update('deposit_role', event.currentTarget.value)}><option value="atto_principale">Atto principale</option><option value="procura">Procura</option><option value="allegato">Allegato</option><option value="prova_notifica">Prova di notifica</option><option value="contributo_unificato">Contributo unificato</option><option value="fuori_busta">Fuori busta</option></select></label>
      <label className="iu-fas-catalog__check"><input type="checkbox" checked={draft.deposit_candidate} onChange={(event) => update('deposit_candidate', event.currentTarget.checked)} /> Valuta per il deposito</label>
      <label>Motivazione della correzione<textarea value={draft.note} maxLength={2000} onChange={(event) => update('note', event.currentTarget.value)} placeholder="Facoltativa: resta nella revisione del fascicolo." /></label>
      <div><button type="submit" disabled={busy}><CheckCircle2 size={14}/> {busy ? 'Salvataggio…' : 'Conferma catalogazione'}</button><button type="button" disabled={busy} onClick={onCancel}>Annulla</button></div>
    </form>
  )
}

function CatalogazioneDocumentalePanel({
  fascicoloId,
  enabled,
  documents,
  onPreview,
  onDone,
  onError,
}: {
  fascicoloId: string
  enabled: boolean
  documents: FascicoloDocument[]
  onPreview: (preview: PreviewDocument) => void
  onDone: (message?: string) => void
  onError: (message: string) => void
}) {
  const [payload, setPayload] = useState<CatalogPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [editingDocumentId, setEditingDocumentId] = useState('')
  const [evidenceDocumentId, setEvidenceDocumentId] = useState('')
  const [reviewedEvidenceDocumentIds, setReviewedEvidenceDocumentIds] = useState<Set<string>>(() => new Set())
  const [error, setError] = useState('')
  const endpoint = `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/catalogazione-documentale`
  const documentsById = useMemo(() => new Map(documents.map((document) => [document.id, document])), [documents])

  const load = useCallback(async () => {
    if (!fascicoloId) return
    setLoading(true)
    setError('')
    try {
      const response = await fetch(endpoint, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      const next = await response.json().catch(() => ({})) as CatalogPayload & { detail?: string; error?: string }
      if (!response.ok) throw new Error(next.detail || next.error || 'Catalogazione documentale non disponibile.')
      setPayload(next)
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Catalogazione documentale non disponibile.'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [endpoint, fascicoloId])

  useEffect(() => {
    if (enabled) void load()
  }, [enabled, load])

  const update = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${endpoint}/aggiorna`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({}),
      })
      const next = await response.json().catch(() => ({})) as CatalogPayload & { detail?: string; error?: string }
      if (!response.ok) throw new Error(next.detail || next.error || 'Aggiornamento della catalogazione non completato.')
      setPayload(next)
      const processed = Number(next.run?.processed || 0)
      onDone(processed ? `Catalogazione aggiornata: ${processed} documenti elaborati.` : 'Indice e catalogazione aggiornati.')
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Aggiornamento della catalogazione non completato.'
      setError(message)
      onError(message)
    } finally {
      setBusy(false)
    }
  }

  const confirm = async (documentId: string, status: 'confirmed' | 'review_required', evidenceAcknowledged = false) => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(
        `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai/${encodeURIComponent(documentId)}/catalogazione-documentale/revisione`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({ status, evidence_acknowledged: evidenceAcknowledged }),
        },
      )
      const next = await response.json().catch(() => ({})) as { assignment?: CatalogAssignmentView; detail?: string; error?: string; message?: string }
      if (!response.ok || !next.assignment) throw new Error(next.detail || next.error || 'Revisione della catalogazione non registrata.')
      setPayload((current) => current ? {
        ...current,
        documents: current.documents.map((item) => item.document_id === documentId ? { ...item, assignment: next.assignment || item.assignment } : item),
      } : current)
      onDone(next.message || 'Revisione della catalogazione registrata nel fascicolo.')
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Revisione della catalogazione non registrata.'
      setError(message)
      onError(message)
    } finally {
      setBusy(false)
    }
  }

  const override = async (documentId: string, draft: CatalogOverrideDraft) => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(
        `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-ai/${encodeURIComponent(documentId)}/catalogazione-documentale/sovrascrivi`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify(draft),
        },
      )
      const next = await response.json().catch(() => ({})) as { assignment?: CatalogAssignmentView; detail?: string; error?: string; message?: string }
      if (!response.ok || !next.assignment) throw new Error(next.detail || next.error || 'Correzione della catalogazione non registrata.')
      setPayload((current) => current ? {
        ...current,
        documents: current.documents.map((item) => item.document_id === documentId ? { ...item, assignment: next.assignment || item.assignment } : item),
      } : current)
      setEditingDocumentId('')
      onDone(next.message || 'Catalogazione corretta e confermata nel fascicolo.')
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Correzione della catalogazione non registrata.'
      setError(message)
      onError(message)
    } finally {
      setBusy(false)
    }
  }

  if (!enabled) return <p className="iu-empty">Apri la sezione documenti per leggere il catalogo SQL del fascicolo.</p>
  const summary = payload?.summary
  return (
    <section id="catalogazione-documentale" className="iu-fas-catalog" aria-label="Catalogazione documentale del fascicolo">
      <header>
        <div>
          <span><FolderSearch2 size={16}/> Catalogazione documentale</span>
          <strong>Ogni esito resta collegato al fascicolo, al documento, alle evidenze e alle fonti.</strong>
          <p>La classificazione automatica deriva dal contenuto indicizzato. Nome file e metadati del portale non sono lettura del contenuto; puoi correggere ogni proposta nel catalogo SQL del fascicolo.</p>
        </div>
        <div className="iu-fas-catalog__header-actions">
          <Badge tone={summary?.review_required ? 'warning' : summary?.total ? 'success' : 'neutral'}>{summary?.review_required ? 'Revisione richiesta' : summary?.total ? 'Catalogo letto' : 'Da aggiornare'}</Badge>
          <button type="button" disabled={busy} onClick={() => void update()} title="Riesegui la catalogazione sul contenuto SQL corrente"><RefreshCw className={busy ? 'iu-spin' : ''} size={15}/> {busy ? 'Catalogazione in corso…' : 'Aggiorna catalogazione'}</button>
        </div>
      </header>
      <dl>
        <div><dt>Documenti</dt><dd>{summary?.source_documents ?? 0}</dd></div>
        <div><dt>Catalogati</dt><dd>{summary?.total ?? 0}</dd></div>
        <div><dt>Proposti</dt><dd>{summary?.proposed ?? 0}</dd></div>
        <div><dt>Confermati</dt><dd>{summary?.confirmed ?? 0}</dd></div>
        <div><dt>Da verificare</dt><dd>{summary?.review_required ?? 0}</dd></div>
        <div><dt>In attesa indice</dt><dd>{summary?.waiting_for_index ?? 0}</dd></div>
      </dl>
      {loading ? <p className="iu-fas-catalog__state"><RefreshCw className="iu-spin" size={15}/> Lettura catalogo SQL in corso…</p> : null}
      {error ? <p className="iu-fas-catalog__state iu-fas-catalog__state--error" role="alert"><AlertTriangle size={15}/> {error}</p> : null}
      {payload?.run.errors?.length ? <div className="iu-fas-catalog__warnings"><strong>Elaborazioni da riesaminare</strong><ul>{payload.run.errors.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul></div> : null}
      <div className="iu-fas-catalog__list">
        {(payload?.documents || []).map((item) => {
          const assignment = item.assignment
          const document = documentsById.get(item.document_id)
          const needsConfirmation = assignment?.status === 'review_required' || assignment?.status === 'proposed'
          const hasEvidence = Boolean(assignment?.evidence?.length)
          const evidenceReviewed = reviewedEvidenceDocumentIds.has(item.document_id)
          return (
            <article key={item.document_id || item.filename} className={`iu-fas-catalog__row is-${assignment?.status || 'waiting'}`}>
              <FileText size={17}/>
              <div className="iu-fas-catalog__copy">
                <strong>{item.filename || 'Documento del fascicolo'}</strong>
                {assignment ? <span>{assignment.document_label} · {catalogProfileLabel(assignment)}{assignment.source_state === 'manual_override' ? ' · confermata manualmente' : ` · confidenza ${assignment.confidence}%`}</span> : <span>{item.supported ? 'In attesa dell’indice Document AI: nessuna classificazione dal contenuto è ancora disponibile.' : 'Formato da acquisire o verificare prima della catalogazione'}</span>}
                {assignment ? <small>{assignment.reason}</small> : null}
                {assignment?.evidence?.length ? <em>{catalogSourceLabel(assignment.source_state)} · {assignment.evidence.filter((entry) => entry.type === 'legal_source').length} fonti collegate</em> : null}
                {needsConfirmation && hasEvidence && !evidenceReviewed ? <small className="iu-fas-catalog__review-hint">Prima apri “Prova e fonti”: la conferma registra anche l’avvenuta lettura delle evidenze.</small> : null}
                {needsConfirmation && !hasEvidence ? <small className="iu-fas-catalog__review-hint">Manca una prova dal contenuto: correggi il catalogo manualmente oppure aggiorna l’indice.</small> : null}
              </div>
              <div className="iu-fas-catalog__badges">
                <Badge tone={catalogTone(assignment?.status || 'waiting')}>{catalogStatusLabel(assignment?.status || 'waiting')}</Badge>
                {assignment?.deposit_candidate ? <Badge tone="primary">Valuta per deposito</Badge> : null}
              </div>
              <div className="iu-fas-catalog__actions">
                {document?.actions.preview ? <button type="button" title="Apri nel lettore interno" aria-label={`Apri ${document.name} nel lettore interno`} onClick={() => onPreview({ name: document.name, url: document.actions.preview, downloadUrl: document.actions.download })}><Eye size={15}/> Visualizza</button> : null}
                {assignment?.evidence?.length ? <button type="button" disabled={busy} aria-expanded={evidenceDocumentId === item.document_id} onClick={() => { setEvidenceDocumentId((current) => current === item.document_id ? '' : item.document_id); setReviewedEvidenceDocumentIds((current) => new Set(current).add(item.document_id)) }}><FileSearch2 size={14}/> {evidenceDocumentId === item.document_id ? 'Nascondi prova' : 'Prova e fonti'}</button> : null}
                {assignment?.status === 'review_required' && hasEvidence ? <button type="button" disabled={busy || !evidenceReviewed} title={evidenceReviewed ? 'Conferma la catalogazione dopo la lettura delle fonti' : 'Apri prima Prova e fonti'} onClick={() => void confirm(item.document_id, 'confirmed', true)}><CheckCircle2 size={14}/> Conferma</button> : null}
                {assignment?.status === 'proposed' && hasEvidence ? <button type="button" disabled={busy || !evidenceReviewed} title={evidenceReviewed ? 'Conferma la proposta dopo la lettura delle fonti' : 'Apri prima Prova e fonti'} onClick={() => void confirm(item.document_id, 'confirmed', true)}><CheckCircle2 size={14}/> Conferma proposta</button> : null}
                {assignment ? <button type="button" disabled={busy} onClick={() => setEditingDocumentId((current) => current === item.document_id ? '' : item.document_id)}><PencilLine size={14}/> Correggi catalogo</button> : null}
              </div>
              {assignment && evidenceDocumentId === item.document_id ? <CatalogEvidenceDisclosure assignment={assignment} document={document} onPreview={onPreview} /> : null}
              {assignment && editingDocumentId === item.document_id ? <CatalogCorrectionForm assignment={assignment} busy={busy} onSubmit={(draft) => void override(item.document_id, draft)} onCancel={() => setEditingDocumentId('')} /> : null}
            </article>
          )
        })}
      </div>
      {!loading && payload && !payload.documents.length ? <p className="iu-empty">Nessun documento disponibile per la catalogazione nel fascicolo.</p> : null}
      <footer>
        <span>La lettura non scarica fonti esterne e non modifica il documento originale.</span>
      </footer>
    </section>
  )
}

function RowActions({ item, archive = false, onDeleted, onError, className = '' }:{item:FascicoloRow; archive?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; className?:string}) {
  const deleteHref = item.deleteHref || `/fascicoli/${encodeURIComponent(item.id)}/elimina`
  const depositoSelectionHref = quickPanelFascicoloActionHref(item, 'selezione_documenti', 'deposito')
  const notificationSelectionHref = quickPanelFascicoloActionHref(item, 'selezione_documenti', 'notifica')
  return (
    <div className={`iu-fas-actions ${className}`.trim()} aria-label={`Azioni fascicolo ${item.ref}`}>
      <a href={item.href} aria-label="Apri fascicolo" title="Apri fascicolo"><Eye size={15}/><span>Apri</span></a>
      {item.relataStatusLabel ? <a href={relataListHref(item)} aria-label={`Apri Relata notifica ${item.ref}`} title="Relata notifica"><FileSignature size={15}/><span>Relata</span></a> : null}
      {!archive ? <a href={item.editHref} aria-label="Modifica fascicolo" title="Modifica fascicolo"><PencilLine size={15}/><span>Modifica</span></a> : null}
      {!archive ? <a href={depositoSelectionHref} aria-label={`Deposito telematico fascicolo ${item.ref}`} title="Prepara deposito telematico"><UploadCloud size={15}/><span>Deposito</span></a> : null}
      {!archive ? <a href={notificationSelectionHref} aria-label={`Notifica in proprio fascicolo ${item.ref}`} title="Prepara notifica"><Send size={15}/><span>Notifica</span></a> : null}
      <a href={item.exportPdfHref} aria-label="Esporta PDF fascicolo" title="Esporta PDF fascicolo"><FileDown size={15}/><span>PDF</span></a>
      {archive && item.archive?.zipAvailable ? <a href={item.archiveZipHref} aria-label="Scarica ZIP archivio" title="Scarica archivio ZIP"><FileArchive size={15}/><span>ZIP</span></a> : null}
      <PostAction action={deleteHref} tone="danger" confirm={`Eliminare definitivamente il fascicolo ${item.ref}?`} confirmTitle="Elimina fascicolo" onDone={(message) => onDeleted?.(item.id, message)} onError={onError} title="Elimina fascicolo" ariaLabel={`Elimina fascicolo ${item.ref}`}><Trash2 size={15}/><span>Elimina</span></PostAction>
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

type QuickPanelState = { item: FascicoloRow; x: number; y: number }

type QuickPanelPstProfile = {
  schema: string
  tabellaMinisteriale: string
  servizioPstPreferito: string
  registroPortale: string
}

function quickPanelPstProfile(item: FascicoloRow): QuickPanelPstProfile {
  const raw = normaliseText([
    item.register,
    item.type,
    item.procedureType,
    item.section,
    item.sectionRole,
    item.court,
    item.title,
    item.object,
    item.subtitle,
  ].join(' '))
  if (raw.includes('cass') && raw.includes('penal')) {
    return { schema: 'cassazione penale', tabellaMinisteriale: 'JPW_CASSPE', servizioPstPreferito: 'JPW_CASSPE', registroPortale: 'CASSPE' }
  }
  if (raw.includes('cass') && raw.includes('civil')) {
    return { schema: 'cassazione civile', tabellaMinisteriale: 'JPW_CASSCI', servizioPstPreferito: 'JPW_CASSCI', registroPortale: 'CASSCI' }
  }
  if (raw.includes('lavor') || raw.includes('previd') || raw.includes('assistenz') || raw.includes('sicid_lavoro') || raw.includes('jpw_sil') || raw.includes('retribuz')) {
    return { schema: 'lavoro', tabellaMinisteriale: 'SICID_LAVORO', servizioPstPreferito: raw.includes('silp') ? 'JPW_SILP_DISTR' : 'JPW_SIL_DISTR', registroPortale: 'LAV' }
  }
  if (raw.includes('volontar') || raw.includes('sivg')) {
    return { schema: 'volontaria', tabellaMinisteriale: 'SICID_VOLONTARIA_GIURISDIZIONE', servizioPstPreferito: 'JPW_SIVG', registroPortale: 'VG' }
  }
  if (raw.includes('simin')) {
    return { schema: 'minori', tabellaMinisteriale: 'SICID_SIMIN', servizioPstPreferito: 'JPW_SIMIN', registroPortale: 'MIN' }
  }
  if (raw.includes('minor') || raw.includes('minoren') || raw.includes('sicid_minori') || raw.includes('jpw_min')) {
    return { schema: 'minori', tabellaMinisteriale: 'SICID_MINORI', servizioPstPreferito: 'JPW_MIN', registroPortale: 'MIN' }
  }
  if (raw.includes('falliment') || raw.includes('concors')) {
    return { schema: 'procedure concorsuali', tabellaMinisteriale: 'SIECIC_PROCEDURE_CONCORSUALI', servizioPstPreferito: 'JPW_SIECIC', registroPortale: 'FALL' }
  }
  if (raw.includes('immobil') || raw.includes('pignor')) {
    return { schema: 'esecuzioni immobiliari', tabellaMinisteriale: 'SIECIC_ESECUZIONI_IMMOBILIARI', servizioPstPreferito: 'JPW_SIECIC', registroPortale: 'ESIM' }
  }
  if (raw.includes('mobil') || raw.includes('esecuz') || raw.includes('siecic')) {
    const registro = raw.includes('siecic') && !raw.includes('esecuz') ? 'SIECIC' : 'ESM'
    return { schema: 'esecuzioni mobiliari', tabellaMinisteriale: 'SIECIC_ESECUZIONI_MOBILIARI', servizioPstPreferito: 'JPW_SIECIC', registroPortale: registro }
  }
  if (raw.includes('giudice di pace') || raw.includes('sigp') || raw.includes('gdp')) {
    return { schema: 'giudice di pace', tabellaMinisteriale: 'SIGP_GIUDICE_DI_PACE', servizioPstPreferito: 'JPW_SIGP', registroPortale: 'GDP' }
  }
  return { schema: 'civile', tabellaMinisteriale: 'SICID_CONTENZIOSO_CIVILE', servizioPstPreferito: 'JPW_SICID', registroPortale: 'CC' }
}

function quickPanelRegistroPortaleHref(item: FascicoloRow): string {
  const query = new URLSearchParams()
  const hasRg = !item.rgMissing && Boolean(item.rgNumber) && Boolean(item.rgYear)
  const hasOffice = Boolean(item.court && item.court !== 'n.d.' && item.court !== 'Ufficio non impostato')
  const profile = quickPanelPstProfile(item)
  query.set('fascicolo_id', item.id)
  query.set('mode', 'update_existing')
  if (hasRg) {
    query.set('numero', String(item.rgNumber))
    query.set('anno', String(item.rgYear))
  }
  if (hasOffice) query.set('ufficio', item.court)
  if (item.client && item.client !== 'n.d.') query.set('assistito', item.client)
  if (item.counterparty && item.counterparty !== 'n.d.') query.set('controparte', item.counterparty)
  if (item.title && item.title !== 'n.d.') query.set('oggetto', item.title)
  query.set('schema', profile.schema)
  query.set('tabella_ministeriale', profile.tabellaMinisteriale)
  query.set('servizio_pst_preferito', profile.servizioPstPreferito)
  query.set('registro_portale', profile.registroPortale)
  if (hasRg && hasOffice) query.set('auto_pst_test', '1')
  const suffix = query.toString()
  return `/portali/pst/acquisizione${suffix ? `?${suffix}` : ''}#wizard-acquisizione`
}

function quickPanelFascicoloActionHref(item: FascicoloRow, key: string, value: string): string {
  const [base, hash = ''] = item.href.split('#')
  const separator = base.includes('?') ? '&' : '?'
  return `${base}${separator}${encodeURIComponent(key)}=${encodeURIComponent(value)}${hash ? `#${hash}` : ''}`
}

function fascicoloGroupLabel(item: FascicoloRow, mode: FascicoliGroupMode): string {
  if (mode === 'gruppo') return item.groupName || 'Senza gruppo'
  if (mode === 'stato') return formatFascicoloStatus(item.status)
  if (mode === 'tipo') return formatFascicoloType(item.type)
  if (mode === 'ufficio') return item.court || 'Ufficio non impostato'
  if (mode === 'anno') return item.rgYear ? String(item.rgYear) : 'Anno RG non indicato'
  if (mode === 'responsabile') return item.responsible || 'Responsabile non indicato'
  return ''
}

function orderFascicoliByGroup(items: FascicoloRow[], mode: FascicoliGroupMode): FascicoloRow[] {
  if (mode === 'nessuno') return items
  return items
    .map((item, sourceIndex) => ({ item, sourceIndex }))
    .sort((left, right) => {
      const groupOrder = fascicoloGroupLabel(left.item, mode).localeCompare(fascicoloGroupLabel(right.item, mode), 'it', { sensitivity: 'base' })
      return groupOrder || left.sourceIndex - right.sourceIndex
    })
    .map(({ item }) => item)
}

function FascicoloQuickPanel({ state, onClose }:{state:QuickPanelState; onClose:()=>void}) {
  const { item } = state
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    const onDown = (event: Event) => {
      if (panelRef.current && event.target instanceof Node && !panelRef.current.contains(event.target)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onDown) }
  }, [onClose])
  // Il pannello resta nel viewport anche vicino ai bordi.
  const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1024
  const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 768
  const width = 300
  const maxPanelHeight = Math.min(560, Math.max(280, viewportHeight - 16))
  const position = {
    x: Math.max(8, Math.min(state.x, viewportWidth - width - 8)),
    y: Math.max(8, Math.min(state.y, viewportHeight - maxPanelHeight - 8)),
  }
  const registroPortaleHref = quickPanelRegistroPortaleHref(item)
  const pagoPaHref = quickPanelFascicoloActionHref(item, 'pagopa', 'nuovo')
  const depositoSelectionHref = quickPanelFascicoloActionHref(item, 'selezione_documenti', 'deposito')
  const notificationSelectionHref = quickPanelFascicoloActionHref(item, 'selezione_documenti', 'notifica')
  const pecQuery = !item.rgMissing && item.rg && item.rg !== 'n.d.' ? item.rg : item.client
  const generaProforma = async () => {
    setBusy(true); setMessage('Generazione proforma...')
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(item.id)}/proforma/genera`, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: '{}',
      })
      const payload = await response.json().catch(() => ({})) as { message?:string; messaggio?:string; ok?:boolean }
      setMessage(payload.message || payload.messaggio || (response.ok ? 'Proforma collegata al fascicolo.' : 'Generazione non riuscita.'))
    } catch { setMessage('Generazione non riuscita.') } finally { setBusy(false) }
  }
  const caricaRicevuta = async (file: File) => {
    setBusy(true); setMessage('Verifica ricevuta telematica...')
    try {
      const form = new FormData()
      form.append('ricevuta', file)
      const response = await fetch(`/fascicoli/${encodeURIComponent(item.id)}/ricevuta-pagamento`, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: form,
      })
      const payload = await response.json().catch(() => ({})) as { message?:string; ok?:boolean }
      setMessage(payload.message || 'Caricamento non riuscito.')
    } catch { setMessage('Caricamento non riuscito.') } finally { setBusy(false) }
  }
  const copiaRiferimento = async () => {
    try {
      await navigator.clipboard.writeText(`${item.ref} — ${item.client}`)
      setMessage('Riferimento copiato negli appunti.')
    } catch { setMessage('Copia non disponibile in questo browser.') }
  }
  return (
    <div className="iu-fas-quick-panel" ref={panelRef} role="menu" aria-label={`Pannello rapido ${item.ref}`} data-iusentra-quick-panel style={{ left: position.x, top: position.y, maxHeight: maxPanelHeight }}>
      <header>
        <strong>{item.ref}</strong>
        <span>{item.client}</span>
      </header>
      <a role="menuitem" href={item.href}><Eye size={15}/> Apri fascicolo</a>
      <a role="menuitem" href={registroPortaleHref}><Landmark size={15}/> Registro su portale servizi</a>
      <a role="menuitem" href={`/strumenti-legali/?tool=contributo_unificato&id_fascicolo=${encodeURIComponent(item.id)}`}><Calculator size={15}/> Calcola contributo unificato</a>
      <a role="menuitem" href={pagoPaHref}><Euro size={15}/> Paga contributo su pagoPA</a>
      <button role="menuitem" type="button" disabled={busy} onClick={() => fileRef.current?.click()}><FileCheck2 size={15}/> Carica ricevuta pagamento (RT)</button>
      <input ref={fileRef} type="file" accept=".xml,.p7m" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) caricaRicevuta(file); event.target.value = '' }}/>
      <button role="menuitem" type="button" disabled={busy} onClick={generaProforma}><Euro size={15}/> Genera fattura proforma</button>
      <a role="menuitem" href={depositoSelectionHref}><UploadCloud size={15}/> Deposito telematico</a>
      <a role="menuitem" href={notificationSelectionHref}><Send size={15}/> Notifica in proprio</a>
      <a role="menuitem" href={`/email/?q=${encodeURIComponent(pecQuery)}`}><Mail size={15}/> PEC del fascicolo</a>
      <button role="menuitem" type="button" onClick={copiaRiferimento}><Copy size={15}/> Copia riferimento</button>
      {message ? <p className="iu-fas-quick-panel__msg" role="status">{message}</p> : null}
      <footer>Il pagamento e il download della ricevuta avvengono sul portale ufficiale autenticato; qui la RT viene verificata e archiviata.</footer>
    </div>
  )
}

function FascicoliTableColumnsControl({ visibleColumns, rowDensity, onColumnsChange, onRowDensityChange }:{visibleColumns:FascicoliTableColumnKey[]; rowDensity:FascicoliRowDensity; onColumnsChange:(columns:FascicoliTableColumnKey[])=>void; onRowDensityChange:(density:FascicoliRowDensity)=>void}) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = useMemo(() => new Set(visibleColumns), [visibleColumns])

  useEffect(() => {
    if (!open) return
    const closeOnOutside = (event: globalThis.MouseEvent) => {
      if (rootRef.current && event.target instanceof Node && !rootRef.current.contains(event.target)) setOpen(false)
    }
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const applySelection = (columns: FascicoliTableColumnKey[]) => {
    const requested = new Set<FascicoliTableColumnKey>(['ref', 'title', ...columns])
    onColumnsChange(fascicoliTableColumns.filter((column) => requested.has(column.key)).map((column) => column.key))
  }
  const toggleColumn = (key: FascicoliTableColumnKey) => {
    const next = new Set(selected)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    applySelection(Array.from(next))
  }

  return (
    <div className="iu-fas-table-options">
      <div className="iu-fas-column-picker" ref={rootRef}>
        <button type="button" className="iu-fas-column-button" aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen((current) => !current)}>
          <TableProperties size={15}/>
          <span>Colonne</span>
          <strong>{visibleColumns.length}</strong>
          <ChevronDown size={14}/>
        </button>
        {open ? (
          <>
          <div className="iu-fas-column-backdrop" aria-hidden="true" onClick={() => setOpen(false)}/>
          <section className="iu-fas-column-panel" role="dialog" aria-modal="true" aria-label="Scegli colonne della tabella">
            <header>
              <div>
                <strong>Colonne della tabella</strong>
                <span>{visibleColumns.length} di {fascicoliTableColumns.length} visibili</span>
              </div>
              <button type="button" onClick={() => setOpen(false)} aria-label="Chiudi scelta colonne"><X size={16}/></button>
            </header>
            <div className="iu-fas-column-presets" aria-label="Composizioni rapide">
              {fascicoliTableColumnPresets.map((preset) => (
                <button type="button" onClick={() => applySelection(preset.columns)} key={preset.label}>{preset.label}</button>
              ))}
            </div>
            <div className="iu-fas-column-groups">
              {fascicoliTableColumnGroups.map((group) => (
                <fieldset key={group}>
                  <legend>{group}</legend>
                  {fascicoliTableColumns.filter((column) => column.group === group).map((column) => (
                    <label key={column.key}>
                      <input type="checkbox" checked={selected.has(column.key)} disabled={column.required} onChange={() => toggleColumn(column.key)}/>
                      <span>{column.label}</span>
                    </label>
                  ))}
                </fieldset>
              ))}
            </div>
          </section>
          </>
        ) : null}
      </div>
      <label className="iu-fas-density-select">
        <span>Righe</span>
        <select value={rowDensity} onChange={(event) => onRowDensityChange(event.currentTarget.value as FascicoliRowDensity)}>
          <option value="compatta">Compatte</option>
          <option value="adattiva">Adattive</option>
        </select>
      </label>
    </div>
  )
}

function FascicoliTable({ items, selected, onToggle, onToggleAll, archive = false, filtered = false, onDeleted, onError, pagination, pageSize, onPageSizeChange, onPageChange, onPagePrefetch, pendingPage = null, view = 'operativa', displayMode = 'tabella', groupBy = 'nessuno', visibleColumns = defaultFascicoliTableColumns, rowDensity = 'compatta', viewToggle, onPaymentSaved, onStatusSaved }:{items:FascicoloRow[]; selected:Set<string>; onToggle:(id:string)=>void; onToggleAll:()=>void; archive?:boolean; filtered?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; pagination?:FascicoliPagination; pageSize?:number; onPageSizeChange?:(value:number)=>void; onPageChange?:(value:number)=>void; onPagePrefetch?:(value:number)=>void; pendingPage?:number | null; view?:ListView; displayMode?:FascicoliDisplayMode; groupBy?:FascicoliGroupMode; visibleColumns?:FascicoliTableColumnKey[]; rowDensity?:FascicoliRowDensity; viewToggle?:ReactNode; onPaymentSaved?:(id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string)=>void; onStatusSaved?:(id:string, status:FascicoloRow['status'], tone:FascicoloRow['tone'], message?:string)=>void}) {
  const stageRef = useRef<HTMLDivElement>(null)
  const [expanded, setExpanded] = useState(false)
  const economic = view === 'economica' && !archive
  const displayItems = useMemo(() => orderFascicoliByGroup(items, groupBy), [groupBy, items])
  const allSelected = displayItems.length > 0 && displayItems.every((item) => selected.has(item.id))
  const total = pagination?.total ?? items.length
  const totalLabel = filtered ? 'fascicoli filtrati' : 'fascicoli'
  const handleError = onError || (() => {})
  const [expandedEconomicId, setExpandedEconomicId] = useState<string | null>(null)
  const [quickPanel, setQuickPanel] = useState<QuickPanelState | null>(null)
  useEffect(() => {
    const syncFullscreenState = () => setExpanded(document.fullscreenElement === stageRef.current)
    document.addEventListener('fullscreenchange', syncFullscreenState)
    return () => document.removeEventListener('fullscreenchange', syncFullscreenState)
  }, [])
  useEffect(() => {
    document.body.classList.toggle('iu-fascicoli-table-expanded', expanded)
    return () => document.body.classList.remove('iu-fascicoli-table-expanded')
  }, [expanded])
  const toggleExpanded = async () => {
    if (expanded) {
      setExpanded(false)
      if (document.fullscreenElement === stageRef.current) void document.exitFullscreen().catch(() => {})
      return
    }
    // Applica subito la superficie estesa: alcuni browser espongono requestFullscreen
    // ma non ne risolvono la Promise quando la richiesta viene negata.
    setExpanded(true)
    if (stageRef.current?.requestFullscreen) {
      void stageRef.current.requestFullscreen().catch(() => {})
    }
  }
  const statusCell = (item: FascicoloRow) => (
    !archive && onStatusSaved
      ? <StatusEditCell item={item} onSaved={onStatusSaved} onError={handleError}/>
      : <Badge tone={item.tone}>{formatFascicoloStatus(item.status)}</Badge>
  )
  const activeColumns = useMemo(() => {
    const selectedColumns = new Set<FascicoliTableColumnKey>(['ref', 'title', ...visibleColumns])
    return fascicoliTableColumns.filter((column) => selectedColumns.has(column.key))
  }, [visibleColumns])
  const activeColumnKeys = useMemo(() => new Set(activeColumns.map((column) => column.key)), [activeColumns])
  const textCell = (value: string | number | null | undefined) => {
    const label = String(value ?? '').trim() || 'n.d.'
    return <span className="iu-fas-table-value" title={label}>{label}</span>
  }
  const renderOperationalCell = (item: FascicoloRow, column: FascicoliTableColumnDefinition) => {
    let content: ReactNode
    switch (column.key) {
      case 'ref':
        content = <><strong>{item.ref}</strong>{!activeColumnKeys.has('internal_ref') && item.internalRef ? <span>{item.internalRef}</span> : null}</>
        break
      case 'internal_ref': content = textCell(item.internalRef); break
      case 'title':
        content = (
          <>
            <div className="iu-fas-title-line"><a href={item.href}>{item.title}</a></div>
            <span>{item.subtitle || item.court}</span>
            <RowActions item={item} archive={archive} onDeleted={onDeleted} onError={onError} className="iu-fas-title-actions"/>
            <DuplicatePracticeBadge item={item}/>
            <MissingRgBadge item={item}/>
            {item.relataStatusLabel ? (
              <a className={`iu-fas-relata-list-link iu-fas-relata-list-link--${item.relataTone}`} href={relataListHref(item)}>
                <FileSignature size={14}/><span>Relata notifica</span><strong>{item.relataStatusLabel}</strong>
              </a>
            ) : null}
          </>
        )
        break
      case 'object': content = textCell(item.object); break
      case 'type': content = <Badge tone="neutral">{formatFascicoloType(item.type)}</Badge>; break
      case 'client': content = textCell(item.client); break
      case 'court': content = textCell(item.court); break
      case 'procedure_type': content = textCell(item.procedureType); break
      case 'register': content = textCell(item.register); break
      case 'section': content = textCell(item.section); break
      case 'section_role': content = textCell(item.sectionRole); break
      case 'judge': content = textCell(item.judge); break
      case 'opposing_lawyer': content = textCell(item.opposingLawyer); break
      case 'holder': content = textCell(item.holder); break
      case 'responsible': content = textCell(item.responsible); break
      case 'counterparty': content = textCell(item.counterparty); break
      case 'claimant': content = textCell(item.claimant); break
      case 'clerk': content = textCell(item.clerk); break
      case 'ctu': content = textCell(item.ctu); break
      case 'ctp': content = textCell(item.ctp); break
      case 'notes': content = textCell(item.notes); break
      case 'operational_status': content = textCell(item.operationalStatus); break
      case 'custom_1': content = textCell(item.customText1); break
      case 'custom_2': content = textCell(item.customText2); break
      case 'group': content = textCell(item.groupName); break
      case 'case_value': content = textCell(item.caseValue > 0 ? formatCurrency(item.caseValue) : 'n.d.'); break
      case 'rg': content = item.rgMissing ? <MissingRgBadge item={item} compact/> : textCell(item.rg); break
      case 'rg_number': content = textCell(item.rgNumber || 'n.d.'); break
      case 'rg_year': content = textCell(item.rgYear || 'n.d.'); break
      case 'next_deadline': content = archive ? <span>{item.archive?.outcome || 'n.d.'}<small>{item.archive?.archivedAt || ''}</small></span> : textCell(item.nextDeadline); break
      case 'status': content = statusCell(item); break
      case 'documents': content = <span className="iu-fas-doc-count">{item.documents}</span>; break
      case 'unread_communications': content = textCell(item.unreadCommunications); break
      case 'alerts': content = textCell(item.alerts); break
      case 'opened_at': content = textCell(formatDateIt(item.openedAt, 'n.d.')); break
      case 'closed_at': content = textCell(formatDateIt(item.closedAt || item.archive?.archivedAt, 'n.d.')); break
      case 'updated_at': content = textCell(formatDateTimeIt(item.updatedAt, 'n.d.')); break
      default: content = textCell('n.d.')
    }
    return <td className={`iu-fas-col iu-fas-col--${column.key} ${column.key === 'title' ? 'iu-fas-title-cell' : ''}`} key={column.key}>{content}</td>
  }
  const currentPage = pagination?.page ?? 1
  const totalPages = pagination?.pages ?? (items.length ? 1 : 0)
  const tableColumnCount = economic ? 6 : activeColumns.length + 1
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
    <div ref={stageRef} className={`iu-fas-table-stage ${expanded ? 'is-expanded' : ''}`}>
    <IusentraDataSurface
      title={`${total} ${totalLabel}`}
      subtitle={archive
        ? 'Archivio pratiche chiuse'
        : economic
          ? 'Elenco unico dello studio — vista economica (contributo, spese/esborsi, liquidazione, parcella)'
          : 'Elenco unico dello studio — vista operativa'}
      toolbar={(
        <div className="iu-fas-table-toolbar">
          <div className="iu-fas-table-toolbar__top">
            <button
              type="button"
              className="iu-fas-table-expand"
              onClick={() => void toggleExpanded()}
              aria-label={expanded ? 'Riduci elenco fascicoli' : 'Apri elenco fascicoli a tutto schermo'}
              title={expanded ? 'Riduci' : 'Tutto schermo'}
            >
              {expanded ? <Minimize2 size={16}/> : <Maximize2 size={16}/>}
              <span>{expanded ? 'Riduci' : 'Tutto schermo'}</span>
            </button>
          </div>
          {viewToggle}
          {pageSizeControl}
        </div>
      )}
      footer={paginationControls}
      fill
      className="iu-fas-table-card"
      ariaLabel={archive ? 'Archivio fascicoli' : 'Elenco fascicoli'}
      empty={!items.length ? <p className="iu-empty">Nessun fascicolo corrisponde ai filtri impostati.</p> : null}
    >
      <SyncedTopScrollbar className={`iu-fas-table-wrap ${economic ? 'iu-fas-table-wrap--economic' : 'iu-fas-table-wrap--operational'} iusentra-data-surface__scroll ${displayMode !== 'tabella' ? 'iu-fas-table-wrap--hidden' : ''}`}>
        <table className={economic ? 'iu-fas-table iu-fas-table--economic' : `iu-fas-table iu-fas-table--operational iu-fas-table--density-${rowDensity}`}>
          <thead>
            <tr>
              <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutti i fascicoli visibili"/></th>
              {economic ? (
                <>
                  <th>Rif.</th>
                  <th>Cliente</th>
                  <th>Prossima scad.</th>
                  <th>Stato</th>
                  <th>Controllo economico</th>
                </>
              ) : activeColumns.map((column) => (
                <th className={`iu-fas-col iu-fas-col--${column.key}`} key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayItems.map((item, itemIndex) => {
              const economicEditorOpen = economic && expandedEconomicId === item.id
              const economicEditorId = `economic-editor-${item.id.replace(/[^a-zA-Z0-9_-]/g, '-')}`
              const startsGroup = groupBy !== 'nessuno' && (itemIndex === 0 || fascicoloGroupLabel(displayItems[itemIndex - 1], groupBy) !== fascicoloGroupLabel(item, groupBy))
              return (
                <Fragment key={item.id}>
                  {startsGroup ? (
                    <tr className="iu-fas-table-group-row">
                      <td colSpan={tableColumnCount}>{fascicoloGroupLabel(item, groupBy)}</td>
                    </tr>
                  ) : null}
                  <tr
                    className={[economicEditorOpen ? 'is-economic-open' : '', item.duplicateCount > 1 ? 'iu-fas-row--duplicate' : ''].filter(Boolean).join(' ') || undefined}
                    onContextMenu={(event) => { event.preventDefault(); setQuickPanel({ item, x: event.clientX, y: event.clientY }) }}
                  >
                    <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.ref}`}/></td>
                    {economic ? (
                      <>
                        <td><span className="iu-fas-economic-ref"><a href={item.href}><strong>{item.ref}</strong></a><span>{item.title}</span><MissingRgBadge item={item} compact/></span></td>
                        <td className="iu-fas-economic-client-cell">
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
                        </td>
                        <td>{item.nextDeadline || 'n.d.'}</td>
                        <td>{statusCell(item)}</td>
                        <td className="iu-fas-economic-matrix">
                          <div className="iu-fas-economic-summary-grid" aria-label={`Sintesi economica ${item.ref}`}>
                            {economicPaymentKinds.map((kind) => (
                              <EconomicPaymentSummary payment={item.paymentSummary.items[kind]} kind={kind} key={kind}/>
                            ))}
                          </div>
                          <EconomicEvidenceStrip row={item}/>
                        </td>
                      </>
                    ) : activeColumns.map((column) => renderOperationalCell(item, column))}
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
      {displayMode !== 'tabella' ? (
        <div className={displayMode === 'schede' ? 'iu-fas-card-grid' : 'iu-fas-compact-list'}>
          {displayItems.map((item, itemIndex) => {
            const startsGroup = groupBy !== 'nessuno' && (itemIndex === 0 || fascicoloGroupLabel(displayItems[itemIndex - 1], groupBy) !== fascicoloGroupLabel(item, groupBy))
            return (
              <Fragment key={`${displayMode}-${item.id}`}>
                {startsGroup ? <h3 className="iu-fas-collection-group">{fascicoloGroupLabel(item, groupBy)}</h3> : null}
                <article className="iu-fas-collection-item" onContextMenu={(event) => { event.preventDefault(); setQuickPanel({ item, x: event.clientX, y: event.clientY }) }}>
                  <label className="iu-fas-collection-select"><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.ref}`}/></label>
                  <div className="iu-fas-collection-main">
                    <span>{item.ref}{item.internalRef && item.internalRef !== 'n.d.' ? ` · ${item.internalRef}` : ''}</span>
                    <a href={item.href}>{item.title}</a>
                    <small>{[item.client, item.court, item.rgMissing ? '' : item.rg].filter(Boolean).join(' · ')}</small>
                  </div>
                  <div className="iu-fas-collection-meta">
                    <Badge tone="neutral">{formatFascicoloType(item.type)}</Badge>
                    {statusCell(item)}
                    {economic ? <strong>{item.paymentSummary.statoLabel}</strong> : <span><CalendarDays size={14}/>{item.nextDeadline || 'n.d.'}</span>}
                    <span><FileText size={14}/>{item.documents}</span>
                  </div>
                  <RowActions item={item} archive={archive} onDeleted={onDeleted} onError={onError}/>
                  {economic ? (
                    <div className="iu-fas-collection-economic">
                      <div className="iu-fas-economic-summary-grid">
                        {economicPaymentKinds.map((kind) => (
                          <EconomicPaymentSummary payment={item.paymentSummary.items[kind]} kind={kind} key={kind}/>
                        ))}
                      </div>
                      <EconomicEvidenceStrip row={item}/>
                      <button
                        type="button"
                        className="iu-fas-economic-edit-toggle"
                        aria-expanded={expandedEconomicId === item.id}
                        onClick={() => setExpandedEconomicId((current) => current === item.id ? null : item.id)}
                      >
                        {expandedEconomicId === item.id ? <ChevronUp size={14}/> : <PencilLine size={14}/>}
                        <span>{expandedEconomicId === item.id ? 'Chiudi controllo economico' : 'Modifica controllo economico'}</span>
                      </button>
                      {expandedEconomicId === item.id ? (
                        <section className="iu-fas-economic-editor" aria-label={`Modifica controllo economico ${item.ref}`}>
                          <EconomicEditorPanel row={item} onSaved={onPaymentSaved || (() => {})} onError={handleError}/>
                        </section>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              </Fragment>
            )
          })}
        </div>
      ) : null}
      <div className="iu-fas-mobile-list">
        {displayItems.map((item) => <DossierMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} archive={archive} economic={economic} onDeleted={onDeleted} onError={onError} onPaymentSaved={onPaymentSaved} key={item.id}/>) }
      </div>
      {quickPanel ? <FascicoloQuickPanel state={quickPanel} onClose={() => setQuickPanel(null)}/> : null}
    </IusentraDataSurface>
    </div>
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
      <button className="iu-fas-filter-btn" type="button" onClick={() => setAdvancedOpen(!advancedOpen)} aria-expanded={advancedOpen} aria-label="Filtri avanzati" title="Filtri avanzati"><Filter size={16}/><span className="iu-fas-toolbar-btn-label">Filtri</span></button>
      <button className={`iu-fas-filter-save iu-fas-filter-save--${preferencesState}`} type="button" onClick={onSavePreferences} disabled={preferencesState === 'saving'} aria-label={saveLabel} title={saveTitle}>
        {preferencesState === 'saving' ? <RefreshCw size={16}/> : <Save size={16}/>}
        <span className="iu-fas-toolbar-btn-label">{saveLabel}</span>
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
  const [type, setType] = useState<FascicoloTipo>(initialTypeFilter)
  const [status, setStatus] = useState<FascicoloStato>(initialStatusFilter)
  const [sort, setSort] = useState<SortKey>(initialSortFilter)
  const [secondarySort, setSecondarySort] = useState<SortKey | ''>(() => {
    const value = initialUrlParam('secondary_sort')
    return value in sortLabels ? value as SortKey : ''
  })
  const [court, setCourt] = useState(() => initialUrlParam('court'))
  const [debouncedCourt, setDebouncedCourt] = useState(() => initialUrlParam('court'))
  const [fieldFilters, setFieldFilters] = useState<FascicoliFieldFilters>(initialFieldFilters)
  const [debouncedFieldFilters, setDebouncedFieldFilters] = useState<FascicoliFieldFilters>(initialFieldFilters)
  const [filterSection, setFilterSection] = useState<PracticeFilterSection>('pratica')
  const [alertsOnly, setAlertsOnly] = useState(() => initialUrlBool('alerts_only', 'alertsOnly'))
  const [paymentsOnly, setPaymentsOnly] = useState(() => initialUrlBool('payments_only', 'paymentsOnly'))
  const [missingRgOnly, setMissingRgOnly] = useState(() => initialUrlBool('missing_rg_only', 'missingRgOnly'))
  const [duplicatesOnly, setDuplicatesOnly] = useState(() => initialUrlBool('duplicates_only', 'duplicatesOnly'))
  const [view, setView] = useState<ListView>(initialListView)
  const [displayMode, setDisplayMode] = useState<FascicoliDisplayMode>(initialDisplayMode)
  const [groupBy, setGroupBy] = useState<FascicoliGroupMode>(initialGroupMode)
  const [visibleColumns, setVisibleColumns] = useState<FascicoliTableColumnKey[]>(() => [...defaultFascicoliTableColumns])
  const [rowDensity, setRowDensity] = useState<FascicoliRowDensity>('compatta')
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
    secondarySort,
    groupBy,
    view,
    fieldFilters: debouncedFieldFilters,
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
    secondarySort,
    view,
    displayMode,
    groupBy,
    visibleColumns,
    rowDensity,
    court: court.trim(),
    fieldFilters,
    alertsOnly,
    paymentsOnly,
    missingRgOnly,
    duplicatesOnly,
    cu: cuFilter,
    liquidazione: liquidazioneFilter,
    parcella: parcellaFilter,
    pageSize,
  }), [alertsOnly, court, cuFilter, displayMode, duplicatesOnly, fieldFilters, groupBy, liquidazioneFilter, missingRgOnly, pageSize, parcellaFilter, paymentsOnly, rowDensity, secondarySort, sort, status, type, view, visibleColumns])

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
      || Object.values(params.fieldFilters || {}).some((value) => value?.trim())
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
          setSecondarySort(preferences.secondarySort ? toSavedSortKey(String(preferences.secondarySort)) : '')
          setView(toSavedListView(String(preferences.view)))
          setDisplayMode(preferences.displayMode)
          setGroupBy(preferences.groupBy)
          setVisibleColumns(preferences.visibleColumns)
          setRowDensity(preferences.rowDensity)
          setCourt(preferences.court)
          setDebouncedCourt(preferences.court.trim())
          setFieldFilters(preferences.fieldFilters)
          setDebouncedFieldFilters(preferences.fieldFilters)
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
            || Object.values(preferences.fieldFilters).some((value) => value.trim())
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
      setDebouncedFieldFilters(Object.fromEntries(
        Object.entries(fieldFilters).map(([key, value]) => [key, value.trim()]).filter(([, value]) => value),
      ) as FascicoliFieldFilters)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [court, fieldFilters, query])

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
  }, [alertsOnly, cuFilter, debouncedCourt, debouncedFieldFilters, debouncedQuery, duplicatesOnly, liquidazioneFilter, missingRgOnly, page, pageSize, parcellaFilter, paymentsOnly, preferencesReady, secondarySort, sort, status, type, view])

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
  }, [alertsOnly, cuFilter, data.pagination.page, data.pagination.pages, debouncedCourt, debouncedFieldFilters, debouncedQuery, duplicatesOnly, groupBy, liquidazioneFilter, loading, missingRgOnly, page, pageSize, parcellaFilter, paymentsOnly, pendingPage, preferencesReady, secondarySort, sort, status, type, view])

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
  const filtersActive = Boolean(query.trim() || type !== 'tutti' || status !== 'tutti' || court.trim() || Object.values(fieldFilters).some((value) => value.trim()) || alertsOnly || paymentsOnly || missingRgOnly || duplicatesOnly || economicFiltersActive)
  const updateType = (value: FascicoloTipo) => { setPage(1); setType(value) }
  const updateStatus = (value: FascicoloStato) => { setPage(1); setStatus(value) }
  const updateSort = (value: SortKey) => { setPage(1); setSort(value) }
  const updateFieldFilter = (key: FascicoliFieldFilterKey, value: string) => {
    setPage(1)
    setFieldFilters((current) => ({ ...current, [key]: value }))
  }
  const resetPracticeFieldFilters = () => { setPage(1); setFieldFilters(emptyPracticeFieldFilters); setCourt('') }
  const updateAlertsOnly = (value: boolean) => { setPage(1); setAlertsOnly(value) }
  const updatePaymentsOnly = (value: boolean) => { setPage(1); setPaymentsOnly(value) }
  const updateCuFilter = (value: FascicoloPaymentFilter) => { setPage(1); setCuFilter(value) }
  const updateLiquidazioneFilter = (value: FascicoloPaymentFilter) => { setPage(1); setLiquidazioneFilter(value) }
  const updateParcellaFilter = (value: FascicoloPaymentFilter) => { setPage(1); setParcellaFilter(value) }
  const updateView = (value: ListView) => { setView(value); syncListViewInUrl(value) }
  const updateDisplayMode = (value: FascicoliDisplayMode) => {
    setDisplayMode(value)
    const url = new URL(window.location.href)
    if (value === 'tabella') url.searchParams.delete('visualizzazione')
    else url.searchParams.set('visualizzazione', value)
    window.history.replaceState({}, '', url.toString())
  }
  const updateGroupBy = (value: FascicoliGroupMode) => {
    setPage(1)
    setGroupBy(value)
    const url = new URL(window.location.href)
    if (value === 'nessuno') url.searchParams.delete('raggruppa')
    else url.searchParams.set('raggruppa', value)
    window.history.replaceState({}, '', url.toString())
  }
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
    <>
      <div className="iu-fas-viewtoggle" role="tablist" aria-label="Contenuto elenco fascicoli">
        <button type="button" role="tab" aria-selected={view === 'operativa'} className={view === 'operativa' ? 'is-active' : ''} onClick={() => updateView('operativa')}>
          <FolderOpen size={14}/> Operativa
        </button>
        <button type="button" role="tab" aria-selected={view === 'economica'} className={view === 'economica' ? 'is-active' : ''} onClick={() => updateView('economica')}>
          <Euro size={14}/> Economica
        </button>
      </div>
      <div className="iu-fas-display-toggle" role="group" aria-label="Modalità di visualizzazione">
        <button type="button" className={displayMode === 'tabella' ? 'is-active' : ''} onClick={() => updateDisplayMode('tabella')} aria-pressed={displayMode === 'tabella'} title="Visualizzazione tabellare"><TableProperties size={15}/><span>Tabella</span></button>
        <button type="button" className={displayMode === 'compatta' ? 'is-active' : ''} onClick={() => updateDisplayMode('compatta')} aria-pressed={displayMode === 'compatta'} title="Visualizzazione compatta"><List size={15}/><span>Compatta</span></button>
        <button type="button" className={displayMode === 'schede' ? 'is-active' : ''} onClick={() => updateDisplayMode('schede')} aria-pressed={displayMode === 'schede'} title="Visualizzazione a schede"><LayoutGrid size={15}/><span>Schede</span></button>
      </div>
      <label className="iu-fas-group-select">
        <span>Raggruppa</span>
        <select value={groupBy} onChange={(event) => updateGroupBy(event.currentTarget.value as FascicoliGroupMode)}>
          <option value="nessuno">Nessun raggruppamento</option>
          <option value="gruppo">Gruppo</option>
          <option value="stato">Stato</option>
          <option value="tipo">Tipo</option>
          <option value="ufficio">Ufficio</option>
          <option value="anno">Anno RG</option>
          <option value="responsabile">Responsabile</option>
        </select>
      </label>
      {view === 'operativa' && displayMode === 'tabella' ? (
        <FascicoliTableColumnsControl visibleColumns={visibleColumns} rowDensity={rowDensity} onColumnsChange={setVisibleColumns} onRowDensityChange={setRowDensity}/>
      ) : null}
    </>
  )
  const deadlineCopy = deadlineUrgencyCopy(data.summary)
  const deadlineAlertItems = data.deadlines
    .filter(isDeadlineAlertUpcoming7)
    .sort((a, b) => (parseDeadlineDate(a.dateIso)?.getTime() || 0) - (parseDeadlineDate(b.dateIso)?.getTime() || 0))
    .slice(0, 4)
  const deadlineAlertHeading = 'Scadenze entro 7 giorni'

  return (
    <div className="iu-content iu-fascicoli-page">
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

        {deadlineAlertItems.length ? (
          <section className="iu-fas-deadline-alert" id="scadenze-urgenti">
            <AlertIcon />
            <div>
              <strong>{deadlineAlertHeading}</strong>
              <div>{deadlineAlertItems.map((item) => <a href={item.href} key={item.id}>{item.matterRef} - {item.title} <span>{item.date}</span></a>)}</div>
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
        <div className="iu-fas-filter-tabs" role="tablist" aria-label="Categorie filtri fascicoli">
          {([['pratica', 'Pratica'], ['procedimento', 'Procedimento'], ['persone', 'Persone']] as Array<[PracticeFilterSection, string]>).map(([key, label]) => (
            <button type="button" role="tab" aria-selected={filterSection === key} className={filterSection === key ? 'is-active' : ''} onClick={() => setFilterSection(key)} key={key}>{label}</button>
          ))}
        </div>
        <div className="iu-fas-practice-filters">
          {filterSection === 'procedimento' ? <label><span>Ufficio giudiziario</span><input value={court} onChange={(event) => setCourt(event.target.value)} placeholder="Tribunale, TAR, GDP..."/></label> : null}
          {practiceFieldFilters.filter((field) => field.section === filterSection).map((field) => (
            <label key={field.key}>
              <span>{field.label}</span>
              <input value={fieldFilters[field.key] || ''} onChange={(event) => updateFieldFilter(field.key, event.currentTarget.value)} placeholder={field.placeholder} inputMode={field.inputMode}/>
            </label>
          ))}
        </div>
        <div className="iu-fas-filter-options">
          <label><span>Primo ordinamento</span><select value={sort} onChange={(event) => updateSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label><span>Secondo ordinamento</span><select value={secondarySort} onChange={(event) => { setPage(1); setSecondarySort(event.target.value as SortKey | '') }}><option value="">Nessuno</option>{(Object.keys(sortLabels) as SortKey[]).filter((item) => item !== sort).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label className="iu-fas-check"><input type="checkbox" checked={alertsOnly} onChange={(event) => updateAlertsOnly(event.target.checked)}/><span>Solo fascicoli con alert o comunicazioni</span></label>
          <label className="iu-fas-check"><input type="checkbox" checked={paymentsOnly} onChange={(event) => updatePaymentsOnly(event.target.checked)}/><span>Solo controllo economico da completare</span></label>
          <button type="button" className="iu-fas-reset-filters" onClick={resetPracticeFieldFilters}><RotateCcw size={15}/> Azzera ricerca dettagliata</button>
        </div>
        <div className="iu-fas-economic-filters" role="group" aria-label="Filtri per voce economica">
          <label><span>Contributo</span><select value={cuFilter} onChange={(event) => updateCuFilter(event.target.value as FascicoloPaymentFilter)}>{paymentFilterOptions.filter((option) => option.value !== 'da_emettere').map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
          <label><span>Liquidazione</span><select value={liquidazioneFilter} onChange={(event) => updateLiquidazioneFilter(event.target.value as FascicoloPaymentFilter)}>{paymentFilterOptions.filter((option) => option.value !== 'da_emettere').map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
          <label><span>Parcella</span><select value={parcellaFilter} onChange={(event) => updateParcellaFilter(event.target.value as FascicoloPaymentFilter)}>{paymentFilterOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
        </div>
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
          <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll} onDeleted={handleFascicoloDeleted} onError={handleListError} filtered={filtersActive} pagination={data.pagination} pageSize={pageSize} onPageSizeChange={updatePageSize} onPageChange={updatePage} onPagePrefetch={prefetchPage} pendingPage={pendingPage} view={view} displayMode={displayMode} groupBy={groupBy} visibleColumns={visibleColumns} rowDensity={rowDensity} viewToggle={viewToggle} onPaymentSaved={handlePaymentSaved} onStatusSaved={handleStatusSaved}/>
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
    </div>
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

function CounterpartyFields({
  data,
  required,
  fascicoloId,
  onSubjectLinked,
}: {
  data: FascicoloFormData
  required: boolean
  fascicoloId?: string
  onSubjectLinked?: () => void
}) {
  const initialName = getValue(data, 'counterparty')
  const initialCode = getValue(data, 'counterpartyTaxCode') || getValue(data, 'cf_controparte')
  const [selectedId, setSelectedId] = useState('')
  const [counterpartyName, setCounterpartyName] = useState(initialName)
  const [counterpartyCode, setCounterpartyCode] = useState(initialCode)
  const [createSubject, setCreateSubject] = useState(false)
  const [subjectType, setSubjectType] = useState('PERSONA_GIURIDICA')
  const [linkingSubject, setLinkingSubject] = useState(false)
  const [linkMessage, setLinkMessage] = useState('')
  useEffect(() => {
    setCounterpartyName(initialName)
    setCounterpartyCode(initialCode)
  }, [initialName, initialCode])
  const selected = data.subjects.find((subject) => subject.id === selectedId)
  const selectedAlreadyLinked = Boolean(selected && data.linkedSubjects.some((subject) => subject.id === selected.id))
  const handleSubjectChange = (value: string) => {
    setSelectedId(value)
    setLinkMessage('')
    const subject = data.subjects.find((item) => item.id === value)
    if (subject) {
      setCreateSubject(false)
      setCounterpartyName(subject.label)
      setCounterpartyCode(subject.taxCode || subject.vat)
    }
  }
  const linkSelectedSubject = async () => {
    if (!fascicoloId || !selected) {
      setLinkMessage('Seleziona prima una controparte già censita.')
      return
    }
    setLinkingSubject(true)
    setLinkMessage('Collegamento in corso...')
    try {
      const body = new FormData()
      body.set('id_soggetto', selected.id)
      body.set('ruolo', 'CONTROPARTE')
      body.set('note', 'Aggiunta dalla modifica del fascicolo.')
      body.set('next_url', `/fascicoli/${fascicoloId}/modifica`)
      const result = await submitFormJson(`/fascicoli/${encodeURIComponent(fascicoloId)}/parti/aggiungi`, body)
      setLinkMessage(result.message || 'Controparte collegata al fascicolo.')
      onSubjectLinked?.()
    } catch (error) {
      setLinkMessage(error instanceof Error ? error.message : 'Non ho potuto collegare la controparte.')
    } finally {
      setLinkingSubject(false)
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
            <div className="iu-fas-choice-card__actions">
              {selected.href ? <a href={selected.href}>Apri soggetto</a> : null}
              {fascicoloId ? (
                <button type="button" onClick={linkSelectedSubject} disabled={linkingSubject || selectedAlreadyLinked}>
                  <Plus size={13}/>{selectedAlreadyLinked ? 'Già collegata' : linkingSubject ? 'Collego...' : 'Aggiungi controparte al fascicolo'}
                </button>
              ) : null}
            </div>
            <em>Già in anagrafica: salvi il fascicolo o usi il pulsante per collegarla qui come controparte, senza creare duplicati.</em>
          </div>
        ) : <small className="iu-fas-field-help">Se il soggetto esiste già, selezionalo: nome e identificativo vengono riportati nel fascicolo e resta riutilizzabile negli altri fascicoli.</small>}
        {linkMessage ? <small className="iu-fas-field-help" role="status">{linkMessage}</small> : null}
      </div>
      {data.linkedSubjects.length ? (
        <div className="iu-fas-linked-parties iu-fas-field--wide" aria-label="Parti già collegate al fascicolo">
          <strong>Parti già collegate al fascicolo</strong>
          <div>
            {data.linkedSubjects.map((subject) => (
              <a href={subject.href || '/soggetti'} key={`${subject.id}-${subject.role}`}>
                <span>{subject.role || 'Soggetto'}</span>
                <b>{subject.name}</b>
                <small>{compactMeta([subject.taxCode, subject.pec || subject.email])}</small>
              </a>
            ))}
          </div>
        </div>
      ) : (
        <small className="iu-fas-field-help iu-fas-field--wide">Nessuna parte processuale collegata: seleziona un soggetto già censito o crea una nuova scheda, poi salva/collega.</small>
      )}
      <Field label="Controparte" name="controparte" required={required}>
        <input name="controparte" value={counterpartyName} onChange={(event) => setCounterpartyName(event.currentTarget.value)} required={required} placeholder="Nome o ragione sociale della controparte"/>
      </Field>
      <Field label="Codice fiscale / P. IVA controparte" name="cf_controparte" required={required}>
        <input name="cf_controparte" value={counterpartyCode} onChange={(event) => setCounterpartyCode(event.currentTarget.value)} required={required} placeholder="Dato necessario per la scheda soggetto"/>
      </Field>
      <Field label={NUOVO_FASCICOLO_LABELS.fields.attorePrincipale} name="attore_principale" defaultValue={getValue(data, 'attorePrincipale')}/>
      {!selected ? (
        <label className="iu-fas-check-field iu-fas-check-field--wide">
          <input type="checkbox" name="crea_soggetto_controparte" value="1" checked={createSubject} onChange={(event) => setCreateSubject(event.currentTarget.checked)}/>
          <span>Crea una nuova scheda soggetto della controparte</span>
          <small>Al salvataggio del fascicolo viene creata in Soggetti e Parti, collegata qui come controparte e resta riutilizzabile negli altri fascicoli.</small>
        </label>
      ) : (
        <small className="iu-fas-field-help iu-fas-field--wide">Per aggiungere una controparte diversa non ancora censita, svuota la selezione e attiva la creazione della nuova scheda.</small>
      )}
      {createSubject && !selected ? (
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
  const [refreshKey, setRefreshKey] = useState(0)
  useEffect(() => {
    let active = true
    setLoading(true)
    getFascicoloForm(mode === 'edit' ? id : undefined, window.location.search)
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, mode, refreshKey])
  const labels = NUOVO_FASCICOLO_LABELS
  const subjectContextParams = new URLSearchParams()
  subjectContextParams.set('tab', 'soggetto')
  subjectContextParams.set('ruolo', 'CONTROPARTE')
  if (id) {
    subjectContextParams.set('id_fascicolo', id)
    subjectContextParams.set('next_url', `/fascicoli/${id}/modifica`)
  }
  const contextualSubjectHref = `/soggetti/nuovo?${subjectContextParams.toString()}`
  if (!loading && data.notFound) {
    return (
      <main className="iu-content iu-fascicoli-page">
        <EmptyState icon={<FolderOpen size={34}/>} title={data.requestError ? 'Dati fascicolo non caricati' : 'Fascicolo non trovato'} action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>
          {data.requestError || 'Il fascicolo non è disponibile o non hai i permessi per modificarlo.'}
        </EmptyState>
      </main>
    )
  }
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
              <CounterpartyFields
                data={data}
                required={fascicoloVeloce}
                fascicoloId={mode === 'edit' ? id : undefined}
                onSubjectLinked={() => setRefreshKey((value) => value + 1)}
              />
              {mode === 'edit' && id ? (
                <div className="iu-fas-party-context iu-fas-field--wide">
                  <div>
                    <strong>Altre controparti e parti</strong>
                    <span>Crea un nuovo soggetto processuale e rientra qui: verrà collegato al fascicolo come controparte.</span>
                  </div>
                  <a className="iu-fas-inline-link" href={contextualSubjectHref}><Plus size={14}/> Aggiungi altra controparte</a>
                </div>
              ) : (
                <a className="iu-fas-inline-link" href={contextualSubjectHref} target="_blank" rel="noreferrer"><Plus size={14}/> Nuovo soggetto</a>
              )}
            </div>
          </CollapsibleFormPanel>
          <CollapsibleFormPanel title={labels.sections.identificazioneGiudiziale} subtitle="Autorità, numero di ruolo e riferimenti dell'ufficio" icon={<Landmark size={17}/>}>
            <div className="iu-fas-form-grid">
              <JudicialOfficeField data={data} required={fascicoloVeloce}/>
              <Field label={labels.fields.numeroRuolo} name="numero_rg" defaultValue={getValue(data, 'numeroRg')}/>
              <Field label="Anno iscrizione" name="anno_rg" type="number" defaultValue={getValue(data, 'annoRg') || new Date().getFullYear()}/>
              <Field label="Sezione" name="sezione" defaultValue={getValue(data, 'section')}/>
              <Field label="Ruolo di sezione" name="ruolo_sezione" defaultValue={getValue(data, 'sectionRole')}/>
              <Field label={labels.fields.istruttorePmGip} name="istruttore_pm_gip" defaultValue={getValue(data, 'istruttorePmGip') || getValue(data, 'judge')}/>
              <Field label={labels.fields.cancelliere} name="cancelliere" defaultValue={getValue(data, 'cancelliere')}/>
              <Field label={labels.fields.ctu} name="ctu" defaultValue={getValue(data, 'ctu')}/>
              <Field label={labels.fields.ctp} name="ctp" defaultValue={getValue(data, 'ctp')}/>
              <Field label="Numero attori o ricorrenti" name="numero_attori" type="number" defaultValue={getValue(data, 'claimantsCount')} min="0" step="1" inputMode="numeric"/>
              <Field label="Numero convenuti o resistenti" name="numero_convenuti" type="number" defaultValue={getValue(data, 'respondentsCount')} min="0" step="1" inputMode="numeric"/>
              <Field label="Numero CCI" name="numero_cci" defaultValue={getValue(data, 'cciNumber')}/>
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
            <div className="iu-fas-form-grid">
              <Field label="Avvocato referente" name="avvocato_referente" defaultValue={getValue(data, 'leadLawyer')}/>
              <Field label="Avvocato dominus" name="avvocato_dominus" defaultValue={getValue(data, 'dominus')}/>
              <Field label="Avvocato della controparte" name="avvocato_controparte" defaultValue={getValue(data, 'opposingLawyer')}/>
              <Field label="Qualifica processuale del titolare" name="qualifica_giudiziale_titolare" defaultValue={getValue(data, 'holderRole')}/>
              <Field label="Gruppo fascicolo" name="nome_gruppo" defaultValue={getValue(data, 'groupName')} placeholder="es. Contenzioso lavoro"/>
              <Field label="Collegamento cartella esterna" name="link_cartella_esterna" defaultValue={getValue(data, 'externalFolderLink')} placeholder="Percorso o collegamento"/>
              <Field label="Campo personalizzato 1" name="testo_personalizzabile_1" defaultValue={getValue(data, 'customText1')}/>
              <Field label="Campo personalizzato 2" name="testo_personalizzabile_2" defaultValue={getValue(data, 'customText2')}/>
              <TextAreaField label={labels.fields.annotazioni} name="note" defaultValue={getValue(data, 'notes')} rows={4}/>
            </div>
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

function RegistroSyncButton({ fascicoloId, lastSyncAt }:{fascicoloId:string; lastSyncAt?:string}) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [tone, setTone] = useState<'info'|'success'|'warning'|'danger'>('info')
  const run = async () => {
    setBusy(true)
    setMessage('Interrogazione del registro di cancelleria in corso...')
    setTone('info')
    try {
      const response = await fetch(`/fascicoli/${encodeURIComponent(fascicoloId)}/sincronizza-registro`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await response.json() as { ok?:boolean; message?:string; requires_local_signer?:boolean; rg_mancante?:boolean }
      setMessage(payload.message || (payload.ok ? 'Registro allineato.' : 'Allineamento non riuscito.'))
      setTone(payload.ok ? 'success' : payload.requires_local_signer || payload.rg_mancante ? 'warning' : 'danger')
      if (payload.ok) setTimeout(() => window.location.reload(), 900)
    } catch {
      setMessage('Registro non raggiungibile in questo momento.')
      setTone('danger')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="iu-fas-registro-sync">
      <button type="button" onClick={run} disabled={busy} className="iu-fas-registro-sync__btn">
        <RefreshCw size={15}/> {busy ? 'Aggiornamento...' : 'Aggiorna dal registro'}
      </button>
      <span className="iu-fas-registro-sync__meta">{lastSyncAt ? `Registro aggiornato al ${lastSyncAt}` : 'Mai allineato dal registro'}</span>
      {message ? <p className={`iu-fas-registro-sync__msg iu-fas-registro-sync__msg--${tone}`}>{message}</p> : null}
    </div>
  )
}

type CtuIncarico = {
  id: string
  ruoloStudio: string
  statoLabel: string
  nomeCtu: string
  timeline: Array<{ chiave: string; label: string; data: string }>
  avvisi: string[]
  consulentiParte: Array<{ nome: string; parte: string }>
  actions: { proponiScadenze: string }
}

function addDaysToIsoDate(base: string, days: string): string {
  const cleanBase = String(base || '').slice(0, 10)
  const amount = Number(days)
  if (!cleanBase || !Number.isFinite(amount) || amount < 0) return ''
  const parts = cleanBase.split('-').map((part) => Number(part))
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return ''
  const [year, month, day] = parts
  const date = new Date(Date.UTC(year, month - 1, day))
  if (Number.isNaN(date.getTime())) return ''
  date.setUTCDate(date.getUTCDate() + Math.trunc(amount))
  return date.toISOString().slice(0, 10)
}

function CtuSection({ fascicoloId }:{fascicoloId:string}) {
  const [incarichi, setIncarichi] = useState<CtuIncarico[]>([])
  const [message, setMessage] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ ruoloStudio: 'PARTE', nomeCtu: '', dataNomina: '', termineBozza: '', termineOsservazioni: '', termineDeposito: '' })
  const [ctuCalc, setCtuCalc] = useState({ decorrenza: '', giorniBozza: '', giorniOsservazioni: '', giorniDeposito: '' })
  const load = () => {
    fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/ctu`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((response) => response.ok ? response.json() : { incarichi: [] })
      .then((payload) => setIncarichi(Array.isArray(payload.incarichi) ? payload.incarichi : []))
      .catch(() => setIncarichi([]))
  }
  useEffect(() => { load() }, [fascicoloId])
  const post = async (href: string, body: Record<string, unknown>) => {
    setBusy(true)
    try {
      const response = await fetch(href, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify(body),
      })
      const payload = await response.json().catch(() => ({})) as { ok?:boolean; message?:string }
      setMessage(payload.message || (response.ok ? 'Operazione completata.' : 'Operazione non riuscita.'))
      if (payload.ok) { setFormOpen(false); load() }
    } catch { setMessage('Operazione non riuscita.') } finally { setBusy(false) }
  }
  const applyCtuTermini = () => {
    const decorrenza = ctuCalc.decorrenza || form.dataNomina
    if (!decorrenza) {
      setMessage('Indica la decorrenza riportata nell’ordinanza prima di applicare i termini.')
      return
    }
    const next = { ...form }
    const bozza = addDaysToIsoDate(decorrenza, ctuCalc.giorniBozza)
    const osservazioni = addDaysToIsoDate(decorrenza, ctuCalc.giorniOsservazioni)
    const deposito = addDaysToIsoDate(decorrenza, ctuCalc.giorniDeposito)
    let applicati = 0
    if (bozza) { next.termineBozza = bozza; applicati += 1 }
    if (osservazioni) { next.termineOsservazioni = osservazioni; applicati += 1 }
    if (deposito) { next.termineDeposito = deposito; applicati += 1 }
    if (!applicati) {
      setMessage('Inserisci almeno un termine in giorni indicato nell’ordinanza.')
      return
    }
    setForm(next)
    setMessage('Date CTU calcolate dai termini dell’ordinanza e pronte per la verifica.')
  }
  return (
    <div className="iu-fas-ctu">
      {message ? <p className="iu-fas-ctu__msg" role="status">{message}</p> : null}
      {incarichi.map((incarico) => (
        <article className="iu-fas-ctu__card" key={incarico.id}>
          <header>
            <strong>{incarico.nomeCtu || 'CTU da indicare'}</strong>
            <Badge tone="neutral">{incarico.statoLabel}</Badge>
            <span>{incarico.ruoloStudio === 'AUSILIARIO' ? 'Lo studio assiste il CTU' : 'Lo studio assiste una parte'}</span>
          </header>
          <ol className="iu-fas-ctu__timeline">
            {incarico.timeline.map((tappa) => (
              <li className={tappa.data ? 'is-set' : ''} key={tappa.chiave}><span>{tappa.label}</span><strong>{tappa.data ? formatDateIt(tappa.data) : '—'}</strong></li>
            ))}
          </ol>
          {incarico.avvisi.map((avviso) => <p className="iu-fas-ctu__warn" key={avviso}><AlertTriangle size={13}/> {avviso}</p>)}
          {incarico.consulentiParte.length ? (
            <p className="iu-fas-ctu__ctp">CTP: {incarico.consulentiParte.map((c) => `${c.nome} (${c.parte || 'parte'})`).join(', ')}</p>
          ) : null}
          <footer>
            <button type="button" disabled={busy} onClick={() => post(incarico.actions.proponiScadenze, {})}><CalendarDays size={14}/> Proponi scadenze</button>
          </footer>
        </article>
      ))}
      {formOpen ? (
        <div className="iu-fas-ctu__form" role="form" aria-label="Nuovo incarico CTU">
          <label><span>Ruolo studio</span>
            <select value={form.ruoloStudio} onChange={(e) => setForm({ ...form, ruoloStudio: e.target.value })}>
              <option value="PARTE">Assistiamo una parte</option>
              <option value="AUSILIARIO">Assistiamo il CTU</option>
            </select>
          </label>
          <label><span>Nome CTU</span><input value={form.nomeCtu} onChange={(e) => setForm({ ...form, nomeCtu: e.target.value })} placeholder="Es. Ing. Bruni"/></label>
          <label><span>Ordinanza di nomina</span><input type="date" value={form.dataNomina} onChange={(e) => setForm({ ...form, dataNomina: e.target.value })}/></label>
          <label><span>Termine bozza (art. 195)</span><input type="date" value={form.termineBozza} onChange={(e) => setForm({ ...form, termineBozza: e.target.value })}/></label>
          <label><span>Termine osservazioni</span><input type="date" value={form.termineOsservazioni} onChange={(e) => setForm({ ...form, termineOsservazioni: e.target.value })}/></label>
          <label><span>Termine deposito</span><input type="date" value={form.termineDeposito} onChange={(e) => setForm({ ...form, termineDeposito: e.target.value })}/></label>
          <section className="iu-fas-ctu__calc" aria-label="Calcolo assistito dall’ordinanza">
            <header>
              <strong>Calcolo assistito dall’ordinanza</strong>
              <span>Usa solo decorrenza e giorni indicati dal giudice.</span>
            </header>
            <label><span>Decorrenza indicata</span><input type="date" value={ctuCalc.decorrenza} onChange={(e) => setCtuCalc({ ...ctuCalc, decorrenza: e.target.value })}/></label>
            <label><span>Giorni bozza</span><input type="number" min="0" inputMode="numeric" value={ctuCalc.giorniBozza} onChange={(e) => setCtuCalc({ ...ctuCalc, giorniBozza: e.target.value })}/></label>
            <label><span>Giorni osservazioni</span><input type="number" min="0" inputMode="numeric" value={ctuCalc.giorniOsservazioni} onChange={(e) => setCtuCalc({ ...ctuCalc, giorniOsservazioni: e.target.value })}/></label>
            <label><span>Giorni deposito</span><input type="number" min="0" inputMode="numeric" value={ctuCalc.giorniDeposito} onChange={(e) => setCtuCalc({ ...ctuCalc, giorniDeposito: e.target.value })}/></label>
            <button type="button" onClick={applyCtuTermini}>Applica date</button>
            <p>I termini non sono standard: vanno copiati dall’ordinanza. Le date calcolate restano modificabili prima del salvataggio.</p>
          </section>
          <div className="iu-fas-ctu__form-actions">
            <button type="button" disabled={busy || !form.nomeCtu.trim()} onClick={() => post(`/fascicoli/${encodeURIComponent(fascicoloId)}/ctu/nuovo`, form)}>Registra incarico</button>
            <button type="button" className="iu-fas-ctu__cancel" onClick={() => setFormOpen(false)}>Annulla</button>
          </div>
          <p className="iu-fas-ctu__note">L’ordinanza fissa i termini ex art. 195 c.3 c.p.c.: IUSENTRA calcola solo le date ricavabili dai giorni o dalle date indicati nell’ordinanza.</p>
        </div>
      ) : (
        <button type="button" className="iu-fas-ctu__add" onClick={() => setFormOpen(true)}><Gavel size={15}/> Nuovo incarico CTU</button>
      )}
    </div>
  )
}

type RegistroDifferenza = { id:string; tipo:string; messaggio:string; rilevataIl:string }

function RegistroCancelleriaPanel({ fascicoloId }:{fascicoloId:string}) {
  const [differenze, setDifferenze] = useState<RegistroDifferenza[]>([])
  const [monitorato, setMonitorato] = useState(false)
  const [expanded, setExpanded] = useState(false)
  useEffect(() => {
    fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/registro-cancelleria`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((response) => response.ok ? response.json() : {})
      .then((payload: { monitorato?: boolean; differenze?: RegistroDifferenza[] }) => {
        setMonitorato(Boolean(payload.monitorato))
        setDifferenze(Array.isArray(payload.differenze) ? payload.differenze.filter((d) => d && d.messaggio) : [])
      })
      .catch(() => {})
  }, [fascicoloId])
  if (!monitorato && !differenze.length) return null
  const visibili = expanded ? differenze : differenze.slice(0, 3)
  return (
    <div className="iu-fas-registro-diff" aria-label="Storico variazioni dal registro di cancelleria">
      <header>
        <span><Landmark size={14}/> Variazioni dal registro</span>
        {differenze.length ? <em>{differenze.length} rilevate</em> : <em>nessuna variazione dalle letture</em>}
      </header>
      {visibili.length ? (
        <ul>
          {visibili.map((diff) => (
            <li key={diff.id} className={`iu-fas-registro-diff__item--${diff.tipo}`}>
              <span>{diff.messaggio}</span>
              <small>{formatDateTimeIt(diff.rilevataIl, '')}</small>
            </li>
          ))}
        </ul>
      ) : null}
      {differenze.length > 3 ? (
        <button type="button" onClick={() => setExpanded(!expanded)}>
          {expanded ? 'Mostra meno' : `Mostra tutte (${differenze.length})`}
        </button>
      ) : null}
    </div>
  )
}

type RegistroRgCandidate = { numeroRg:string; annoRg:number; ufficio:string; oggetto:string; parti:string }

function RegistroRgSearch({ fascicoloId }:{fascicoloId:string}) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [candidates, setCandidates] = useState<RegistroRgCandidate[]>([])
  const search = async () => {
    setBusy(true); setMessage('Ricerca nel registro di cancelleria...'); setCandidates([])
    try {
      const response = await fetch(`/fascicoli/${encodeURIComponent(fascicoloId)}/cerca-rg-registro`, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await response.json() as { ok?:boolean; message?:string; candidati?:RegistroRgCandidate[] }
      setMessage(payload.message || '')
      setCandidates(Array.isArray(payload.candidati) ? payload.candidati : [])
    } catch {
      setMessage('Registro non raggiungibile in questo momento.')
    } finally { setBusy(false) }
  }
  const attach = async (candidate: RegistroRgCandidate) => {
    setBusy(true); setMessage(`Aggancio RG ${candidate.numeroRg}/${candidate.annoRg}...`)
    try {
      const response = await fetch(`/fascicoli/${encodeURIComponent(fascicoloId)}/aggancia-rg`, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ numeroRg: candidate.numeroRg, annoRg: candidate.annoRg }),
      })
      const payload = await response.json() as { ok?:boolean; message?:string }
      setMessage(payload.message || (payload.ok ? 'RG agganciato.' : 'Aggancio non riuscito.'))
      if (payload.ok) setTimeout(() => window.location.reload(), 900)
    } catch {
      setMessage('Aggancio non riuscito.')
    } finally { setBusy(false) }
  }
  return (
    <div className="iu-fas-registro-sync">
      <button type="button" onClick={search} disabled={busy} className="iu-fas-registro-sync__btn"><Search size={15}/> Cerca RG nel registro</button>
      <span className="iu-fas-registro-sync__meta">Cerca il fascicolo nel registro per parte e ufficio, poi aggancia il numero di ruolo.</span>
      {message ? <p className="iu-fas-registro-sync__msg iu-fas-registro-sync__msg--info">{message}</p> : null}
      {candidates.length ? (
        <ul className="iu-fas-rg-candidates">
          {candidates.map((c) => (
            <li key={`${c.numeroRg}-${c.annoRg}`}>
              <div><strong>RG {c.numeroRg}/{c.annoRg}</strong><span>{c.ufficio}</span>{c.oggetto ? <em>{c.oggetto}</em> : null}</div>
              <button type="button" onClick={() => attach(c)} disabled={busy}><CheckCircle2 size={14}/> Aggancia</button>
            </li>
          ))}
        </ul>
      ) : null}
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
  if (section === 'scadenze') return ['scadenze', 'documenti']
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
    case 'presidio-fascicolo':
    case 'cabina-regia':
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

function downloadDocumentFile(downloadUrl: string, fallbackName: string): string {
  const href = downloadUrl.trim()
  if (!href) throw new Error('Download non disponibile: manca il collegamento al documento.')
  const filename = fallbackName.replace(/[\\/:*?"<>|]/g, '_').trim() || 'documento'
  const anchor = document.createElement('a')
  // Il browser usa direttamente la route interna autorizzata: il lettore non
  // dipende da fetch/blob e il download conserva il nome dato dal server.
  anchor.href = href
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  return filename
}

function isInternalDocumentDownload(value: string): boolean {
  try {
    const url = new URL(value, window.location.origin)
    return url.origin === window.location.origin && /^\/fascicoli\/[^/]+\/documenti\/[^/]+\/scarica$/.test(url.pathname)
  } catch {
    return false
  }
}

function DocumentDownloadAction({ downloadUrl, name, onDone, onError }:{downloadUrl:string; name:string; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [busy, setBusy] = useState(false)
  const download = async () => {
    if (busy) return
    setBusy(true)
    try {
      const filename = await downloadDocumentFile(downloadUrl, name)
      onDone(`Download avviato per ${filename}.`)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Download non riuscito.')
    } finally {
      setBusy(false)
    }
  }
  return <button type="button" className="iu-fas-doc-action" onClick={() => void download()} disabled={busy} title="Scarica una copia locale del documento" aria-label={`Scarica ${name}`}><Download size={15}/><span>{busy ? 'Preparo…' : 'Scarica'}</span></button>
}

function PdfPreviewModal({ preview, onClose, overDocumentFlow = false }:{preview:PreviewDocument | null; onClose:()=>void; overDocumentFlow?:boolean}) {
  const [downloadState, setDownloadState] = useState('')
  const [downloading, setDownloading] = useState(false)
  const startDownload = useCallback(async (downloadUrl = preview?.downloadUrl || '', fallbackName = preview?.name || 'documento') => {
    if (downloading || !downloadUrl) return false
    setDownloading(true)
    setDownloadState('')
    try {
      const filename = await downloadDocumentFile(downloadUrl, fallbackName)
      setDownloadState(`Download avviato: ${filename}.`)
      return true
    } catch (error) {
      setDownloadState(error instanceof Error ? error.message : 'Download non riuscito.')
      return false
    } finally {
      setDownloading(false)
    }
  }, [downloading, preview?.downloadUrl, preview?.name])

  useEffect(() => {
    const objectUrl = preview?.objectUrl
    setDownloadState('')
    setDownloading(false)
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [preview?.downloadUrl, preview?.objectUrl])

  useEffect(() => {
    const receiveFrameDownload = (event: MessageEvent<unknown>) => {
      if (event.origin !== window.location.origin || !event.data || typeof event.data !== 'object') return
      const request = event.data as { type?: unknown; url?: unknown; filename?: unknown }
      if (request.type !== 'iusentra.document.download' || typeof request.url !== 'string' || !isInternalDocumentDownload(request.url)) return
      const filename = typeof request.filename === 'string' && request.filename.trim() ? request.filename.trim() : (preview?.name || 'documento')
      void startDownload(request.url, filename).then((ok) => {
        const destination = event.source as WindowProxy | null
        if (!destination) return
        destination.postMessage({
          type: 'iusentra.document.download.result',
          ok,
          message: ok ? 'Download avviato dal lettore IUSENTRA.' : 'Download non riuscito: controlla il messaggio nel lettore.',
        }, event.origin)
      })
    }
    window.addEventListener('message', receiveFrameDownload)
    return () => window.removeEventListener('message', receiveFrameDownload)
  }, [preview?.name, startDownload])

  if (!preview) return null
  const mobileUrl = preview.mobileUrl || mobilePreviewUrl(preview.url)
  const viewerUrl = mobileUrl || preview.url
  const previewModalClassName = ['iu-fas-preview-modal', overDocumentFlow ? 'iu-fas-preview-modal--over-document-flow' : ''].filter(Boolean).join(' ')
  return (
    <div className={previewModalClassName} role="dialog" aria-modal="true" aria-label={`Anteprima ${preview.name}`}>
      <div className="iu-fas-preview-modal__box">
        <header>
          <div className="iu-fas-preview-modal__title">
            <span><Eye size={14}/> Lettore documento</span>
            <strong>{preview.name}</strong>
            {downloadState ? <small className="iu-fas-preview-download-status" role="status">{downloadState}</small> : null}
          </div>
          <nav>
            <button type="button" onClick={() => void startDownload()} disabled={downloading} aria-label={`Scarica ${preview.name}`}><Download size={15}/> {downloading ? 'Preparo…' : 'Scarica'}</button>
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
      <Landmark size={16} aria-hidden="true"/>
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
  onOpenDocuments,
  onCalculateContribution,
}:{
  open: boolean
  data: FascicoloDetailData
  contributoMemory: ContributoUnificatoMemory | null
  onClose: () => void
  onPaymentSaved: (id:string, paymentSummary:FascicoloRow['paymentSummary'], message?:string) => void
  onError: (message:string) => void
  onOpenPagoPa: () => void
  onOpenDocuments: () => void
  onCalculateContribution: () => void
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
            <span><WalletCards size={15}/> Presidio economico del fascicolo</span>
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
            <section className="iu-fas-economic-control-modal__sentenze" aria-label="Evidenze economiche da provvedimenti">
              <header>
                <div>
                  <Badge tone={data.sentenzeEconomiche?.kpi.tone || 'neutral'}>{data.sentenzeEconomiche?.kpi.label || 'Provvedimenti economici'}</Badge>
                  <strong>{data.sentenzeEconomiche?.kpi.value || 'Nessuna evidenza economica letta'}</strong>
                  <small>{data.sentenzeEconomiche ? `${data.sentenzeEconomiche.totals.sentenze_lette} provvedimenti letti · ${data.sentenzeEconomiche.totals.da_verificare} verifiche aperte` : 'Il controllo si alimenta solo da provvedimenti acquisiti e indicizzati nel fascicolo.'}</small>
                </div>
                <button type="button" onClick={onOpenDocuments}><FileText size={15}/> Apri documenti sorgente</button>
              </header>
              {data.sentenzeEconomiche?.worklist.length ? (
                <div>
                  {data.sentenzeEconomiche.worklist.map((item) => (
                    <article key={`${item.label}-${item.value}-${item.hint}`}>
                      <div><span>{item.label}</span><strong>{item.value}</strong><small>{item.hint}</small></div>
                      <Badge tone={item.tone}>{item.label.includes('verificare') ? 'Verifica' : 'Rilevato'}</Badge>
                    </article>
                  ))}
                </div>
              ) : <p>Nessun importo o avviso viene inventato: qui compariranno soltanto gli esiti estratti da una fonte documentale del fascicolo.</p>}
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
          <button type="button" onClick={onCalculateContribution}><Calculator size={15}/> Calcola contributo</button>
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

function regiaOperationalStateLabel(value: string): string {
  const technical = String(value || '').trim().toUpperCase()
  const labels: Record<string, string> = {
    DOCUMENTI_DA_COMPLETARE: 'Documenti da completare',
    ATTO_DA_REDIGERE: 'Atto da redigere',
    ATTO_DA_FIRMARE: 'Atto da firmare',
    VALIDAZIONE_IN_CORSO: 'Validazione in corso',
    BLOCCATO_DA_ERRORI: 'Bloccato da requisiti mancanti',
    PRONTO_AL_DEPOSITO: 'Pronto al deposito',
    DEPOSITO_IN_PREPARAZIONE: 'Deposito in preparazione',
    DEPOSITO_INVIATO: 'Deposito inviato',
    IN_ATTESA_RICEVUTE: 'In attesa delle ricevute',
  }
  return labels[technical] || String(value || 'Da verificare').replace(/_/g, ' ')
}

function regiaWorkflowLabel(value: string): string {
  const technical = String(value || '').trim().toUpperCase()
  const labels: Record<string, string> = {
    WF_SIGP_GDP: 'SIGP — Giudice di Pace',
  }
  return labels[technical] || String(value || '').replace(/_/g, ' ')
}

function regiaChecklistStatusLabel(value: string): string {
  const technical = String(value || '').trim().toUpperCase()
  const labels: Record<string, string> = {
    BLOCCATO: 'Bloccato',
    COMPLETATO: 'Completato',
    DA_COMPLETARE: 'Da completare',
  }
  return labels[technical] || String(value || 'Da completare').replace(/_/g, ' ')
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

function RegiaActionButton({ label, value, note, onClick, tone = 'neutral' }:{label:string; value:string; note:string; onClick:()=>void; tone?:FascicoloRow['tone']}) {
  return (
    <button className={`iu-fas-regia-action iu-fas-regia-action--${tone}`} type="button" onClick={onClick}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
      <ChevronRight size={16} aria-hidden="true"/>
    </button>
  )
}

type ProceduralProfileCandidate = {
  code: string
  name: string
  area: string
  channel: string
  registry: string
  confidence: string
  reason: string
  source: string
}

function formatProceduralConfidence(value: string): string {
  const numeric = Number(value.trim().replace('%', '').replace(',', '.'))
  if (!Number.isFinite(numeric) || numeric <= 0) return 'da verificare'
  return `${Math.round((numeric > 1 ? numeric / 100 : numeric) * 100)}%`
}

function proceduralProfileCandidates(regia: FascicoloDetailData['regia']): ProceduralProfileCandidate[] {
  const profile = regia.profile
  const rows = [
    profile.candidate,
    ...(Array.isArray(profile.alternatives) ? profile.alternatives : []),
  ].filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object' && !Array.isArray(row))
  const seen = new Set<string>()
  return rows.flatMap((row) => {
    const code = recordText(row, 'code') || recordText(row, 'procedureCode') || recordText(row, 'procedure_code')
    if (!code || seen.has(code)) return []
    seen.add(code)
    const confidence = formatProceduralConfidence(recordText(row, 'confidence') || recordText(profile, 'confidence'))
    return [{
      code,
      name: recordText(row, 'name') || recordText(row, 'practiceType') || code,
      area: recordText(row, 'area'),
      channel: recordText(row, 'channel'),
      registry: recordText(row, 'registry'),
      confidence,
      reason: recordText(row, 'reason') || recordText(profile, 'reason') || 'Proposta del resolver procedurale.',
      source: recordText(row, 'source') || recordText(profile, 'source') || 'Catalogo procedurale IUSENTRA',
    }]
  })
}

function ProceduralProfileConfirmation({ data, onDone, onError }:{data:FascicoloDetailData; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const regia = data.regia
  const candidates = proceduralProfileCandidates(regia)
  const action = recordText(regia.actions, 'applyProfile')
  const resolverReason = recordText(regia.profile, 'reason') || 'Il sistema non ha applicato alcun profilo in autonomia.'
  return (
    <div className="iu-fas-regia iu-fas-regia--profile-review">
      <header className="iu-fas-regia__header">
        <div>
          <Badge tone="warning">Conferma necessaria</Badge>
          <h3>Profilo procedurale da confermare</h3>
          <p>Il sistema ha preparato una proposta, ma non crea requisiti, checklist o azioni finché l’avvocato non la conferma.</p>
        </div>
      </header>
      <section className="iu-fas-regia__profile-source" aria-label="Origine della proposta procedurale">
        <strong>Come è stata prodotta la proposta</strong>
        <p>{resolverReason}</p>
        <small>La conferma salva il profilo scelto e registra l’azione nel fascicolo. Nessun termine, deposito o notifica viene creato da questa scelta.</small>
      </section>
      <div className="iu-fas-regia__profile-candidates">
        {candidates.map((candidate) => (
          <article key={candidate.code}>
            <Badge tone="info">Confidenza {candidate.confidence}</Badge>
            <strong>{candidate.name}</strong>
            <span>{[candidate.area, candidate.channel, candidate.registry].filter(Boolean).join(' · ') || 'Canale e registro da verificare'}</span>
            <small>{candidate.reason}</small>
            <small className="iu-fas-regia__profile-source-label">Fonte del profilo: {candidate.source}</small>
            <JsonPostForm
              action={action}
              className="iu-fas-regia__profile-confirm"
              onDone={onDone}
              onError={onError}
            >
              <input type="hidden" name="profile_code" value={candidate.code}/>
              <input type="hidden" name="reason" value={`Conferma esplicita dell’avvocato del profilo ${candidate.code}.`}/>
              <button type="submit"><CheckCircle2 size={15}/> Conferma profilo</button>
            </JsonPostForm>
          </article>
        ))}
        {!candidates.length ? <p className="iu-empty">Nessun profilo candidato è disponibile. Completa i dati di procedimento o seleziona una procedura dal catalogo prima di creare controlli.</p> : null}
      </div>
    </div>
  )
}

function FascicoloCompliancePanel({ data, returnHref }:{data:FascicoloDetailData; returnHref:string}) {
  const fascicolo = data.fascicolo
  const qualityDestination = (label:string) => {
    const normalized = label.trim().toLowerCase()
    if (normalized === 'dati principali') return '#profilo'
    if (normalized === 'cliente') return data.client?.href || '#cliente'
    if (normalized === 'parti') return '#soggetti'
    if (normalized === 'documenti') return '#documenti'
    if (normalized === 'scadenze') return '#udienze'
    if (normalized === 'sync portale') return '#documenti'
    return '#presidio-conformita'
  }
  const qualityActionLabel = (label:string) => {
    const normalized = label.trim().toLowerCase()
    if (normalized === 'dati principali') return 'Apri dati principali e modifica il fascicolo'
    if (normalized === 'cliente') return 'Apri cliente e dati anagrafici'
    if (normalized === 'parti') return 'Apri soggetti e parti per la verifica'
    if (normalized === 'documenti') return 'Apri documenti e atti del fascicolo'
    if (normalized === 'scadenze') return 'Apri udienze e scadenze'
    if (normalized === 'sync portale') return 'Apri documenti acquisiti dal portale'
    return 'Apri il controllo di conformità'
  }
  const openQualityDestination = (event:MouseEvent<HTMLAnchorElement>, destination:string) => {
    // Per le sezioni del fascicolo non basta cambiare hash: il pannello può
    // essere chiuso. Lo apriamo, lo portiamo nel contesto visibile e lasciamo
    // il focus alla sua summary per la prosecuzione da tastiera.
    if (!destination.startsWith('#')) return
    event.preventDefault()
    const sectionId = destination.slice(1)
    openDetailSectionById(sectionId)
    window.requestAnimationFrame(() => {
      const target = document.getElementById(sectionId)
      const summary = target?.querySelector('summary')
      if (summary instanceof HTMLElement) summary.focus({ preventScroll: true })
    })
  }
  return (
    <section id="presidio-conformita" className="iu-fas-regia__quality" aria-labelledby="presidio-conformita-title">
      <span id="conformita" className="iu-fas-anchor-alias" aria-hidden="true"/>
      <header>
        <div>
          <h4 id="presidio-conformita-title">Conformità e qualità</h4>
          <p>I controlli restano nel presidio del fascicolo: apri ogni esito, correggi il dato e lascia traccia dell'azione.</p>
        </div>
        <Badge tone={data.quality.some((item) => !item.ok) ? 'warning' : 'success'}>{data.quality.some((item) => !item.ok) ? 'Da verificare' : 'Controlli attivi'}</Badge>
      </header>
      <div className="iu-fas-quality-list">{data.quality.map((item) => {
        const destination = qualityDestination(item.label)
        return <a key={item.label} className="iu-fas-quality-list__item" href={destination} onClick={(event) => openQualityDestination(event, destination)} aria-label={qualityActionLabel(item.label)} title={qualityActionLabel(item.label)}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></a>
      })}</div>
      <JsonPostForm className={`iu-fas-compliance-toggle ${fascicolo.complianceControlsEnabled ? 'is-on' : 'is-off'}`} action={fascicolo.complianceControlsEnabled ? data.actions.complianceOff : data.actions.complianceOn} redirectTo={returnHref}>
        <input type="hidden" name="enabled" value={fascicolo.complianceControlsEnabled ? '0' : '1'}/>
        <input type="hidden" name="next" value={returnHref}/>
        <button type="submit" aria-pressed={fascicolo.complianceControlsEnabled}><span className="iu-fas-compliance-toggle__switch" aria-hidden="true"><i/></span><span><strong>{fascicolo.complianceControlsEnabled ? 'Controlli automatici attivi' : 'Controlli automatici disattivati'}</strong><small>{fascicolo.complianceControlsEnabled ? 'Disattiva i controlli qualità sul fascicolo' : 'Riattiva i controlli qualità sul fascicolo'}</small></span></button>
      </JsonPostForm>
    </section>
  )
}

function RegiaOperativaSection({ data, onDone, onError, onOpen, onOpenEconomicControl, onCalculateContribution, returnHref, loading = false }:{data:FascicoloDetailData; onDone:(message?:string)=>void; onError:(message:string)=>void; onOpen?:()=>void; onOpenEconomicControl:()=>void; onCalculateContribution:()=>void; returnHref:string; loading?:boolean}) {
  const regia = data.regia
  if (regia.page_state === 'profilo_da_confermare') {
    return (
      <DetailSection id="presidio-fascicolo" title="Presidio del fascicolo" icon={<ClipboardCheck size={17}/>} count={proceduralProfileCandidates(regia).length} onOpen={onOpen}>
        <span id="cabina-regia" className="iu-fas-anchor-alias" aria-hidden="true"/>
        <span id="regia-operativa" className="iu-fas-anchor-alias" aria-hidden="true"/>
        {loading ? <p className="iu-empty">Caricamento Presidio del fascicolo...</p> : <ProceduralProfileConfirmation data={data} onDone={onDone} onError={onError}/>}
      </DetailSection>
    )
  }
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
    ['Percorso', regiaWorkflowLabel(h.workflow)],
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
  const operational = data.operationalPresidio
  const operationalNext = operational.nextAction || operational.actions[0]
  const nextDeadline = data.deadlines[0] || data.appointments[0]
  const notification = data.notificationRelata
  const sentenzeCount = sentenzeEconomicheCount(data.sentenzeEconomiche)
  const contributoUnificato = data.fascicolo.paymentSummary.items.contributo_unificato
  return (
    <DetailSection id="presidio-fascicolo" title="Presidio del fascicolo" icon={<ClipboardCheck size={17}/>} count={regia.checklist.length + regia.documentSlots.length + operational.actions.length} onOpen={onOpen}>
      <span id="cabina-regia" className="iu-fas-anchor-alias" aria-hidden="true"/>
      <span id="regia-operativa" className="iu-fas-anchor-alias" aria-hidden="true"/>
      {loading ? <p className="iu-empty">Caricamento Presidio del fascicolo...</p> : null}
      <div className="iu-fas-regia">
        <header className="iu-fas-regia__header">
          <div>
            <Badge tone={statusTone}>{regiaOperationalStateLabel(h.operationalState)}</Badge>
            <h3>{h.practiceType || fLabel(data.fascicolo.title)}</h3>
            <p>{h.nextAction || 'Completa i controlli operativi del fascicolo.'}</p>
          </div>
          <div className="iu-fas-regia__progress" aria-label="Completamento Presidio del fascicolo">
            <strong>{h.completion}%</strong>
            <span>completamento</span>
          </div>
        </header>
        {metaItems.length ? (
          <div className="iu-fas-regia__meta">
            {metaItems.map(([label, value]) => <span key={label}><strong>{label}</strong>{value}</span>)}
          </div>
        ) : null}
        <section className="iu-fas-regia__priorities" aria-label="Controlli prioritari del fascicolo">
          <h4>Controlli prioritari</h4>
          <div className="iu-fas-regia-action-list">
            <RegiaActionCard label="Presìdi del fascicolo" value={operational.statusLabel || 'Da verificare'} note={operationalNext?.reason || operational.summary || 'Apri i controlli del fascicolo'} href={operationalNext?.href || '#presidio-conformita'} tone={operational.tone}/>
            <RegiaActionCard label="Conformità e qualità" value={data.quality.some((item) => !item.ok) ? `${data.quality.filter((item) => !item.ok).length} verifiche` : 'Controlli attivi'} note="Esiti, qualità dei dati e comando di attivazione nello stesso presidio." href="#presidio-conformita" tone={data.quality.some((item) => !item.ok) ? 'warning' : 'success'}/>
            <RegiaActionCard label="Comunicazioni, PEC e notifica" value={notification.statusLabel || 'Da verificare'} note={notification.systemNotification || 'Controlla relata, ricevute e prova di notifica'} href="#comunicazioni-notifica" tone={notification.tone}/>
            <RegiaActionCard label="Udienze e scadenze" value={nextDeadline?.date || 'Nessun evento aperto'} note={nextDeadline?.title || 'Registra o verifica i termini della pratica'} href="#udienze" tone={nextDeadline ? nextDeadline.tone : 'neutral'}/>
            <RegiaActionCard label="Audit del fascicolo" value={data.auditTrail.summary.total ? `${data.auditTrail.summary.total} evidenze` : 'Nessuna evidenza'} note={data.auditTrail.summary.total ? 'Apri le prove registrate' : 'Le prove nascono da consultazioni, depositi e ricevute'} href="#audit" tone={data.auditTrail.summary.total ? 'success' : 'neutral'}/>
          </div>
        </section>
        <FascicoloCompliancePanel data={data} returnHref={returnHref}/>
        <div className="iu-fas-regia__grid">
          <article id="economia">
            <span id="workflow" className="iu-fas-anchor-alias" aria-hidden="true"/>
            <span id="sentenze-economiche" className="iu-fas-anchor-alias" aria-hidden="true"/>
            <h4>Presidio economico</h4>
            <div className="iu-fas-regia-action-list">
              <RegiaActionCard label="Preventivo accettato" value={recordBool(economics, 'preventivoAccepted') ? 'Si' : 'No'} note={recordBool(economics, 'preventivoAccepted') ? 'Apri preventivo' : 'Apri per accettare o creare'} href={preventivoHref} tone={recordBool(economics, 'preventivoAccepted') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Conferimento firmato" value={recordBool(economics, 'conferimentoSigned') ? 'Si' : 'No'} note={recordBool(economics, 'conferimentoSigned') ? 'Apri conferimento' : 'Apri il conferimento'} href={conferimentoHref} tone={recordBool(economics, 'conferimentoSigned') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Avviso / parcella" value={recordBool(economics, 'proformaIssued') ? 'Emesso' : 'Non emesso'} note={recordBool(economics, 'proformaIssued') ? 'Apri documento economico' : 'Crea la parcella'} href={proformaHref} tone={recordBool(economics, 'proformaIssued') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Pagamento" value={recordBool(economics, 'paymentRegistered') ? 'Registrato' : 'Da registrare'} note={recordBool(economics, 'paymentRegistered') ? 'Apri incassi' : 'Registra incasso'} href={paymentHref} tone={recordBool(economics, 'paymentRegistered') ? 'success' : 'warning'}/>
              <RegiaActionButton label="Contributo unificato" value={contributoUnificato.statusLabel || 'Da verificare'} note={contributoUnificato.note || contributoUnificato.documentoFonte || 'Apri il presidio economico per verificare ricevuta, esenzione o pagamento.'} onClick={onOpenEconomicControl} tone={contributoUnificato.tone}/>
              <RegiaActionButton label="Provvedimenti economici" value={sentenzeCount ? `${sentenzeCount} controlli` : 'Nessun controllo aperto'} note="Liquidazioni, spese, distrazioni e contributo unificato sono letti nello stesso presidio." onClick={onOpenEconomicControl} tone={sentenzeCount ? 'warning' : 'neutral'}/>
            </div>
            <ul className="iu-fas-regia__facts">
              <li><span>Compenso pattuito</span><strong>{recordText(economics, 'agreedFee', '€ 0,00')}</strong></li>
              <li><span>Spese vive / anticipazioni</span><strong>{recordText(economics, 'expenses', '€ 0,00')}</strong></li>
            </ul>
            <div className="iu-fas-regia__actions" aria-label="Azioni presidio economico">
              <button type="button" onClick={onOpenEconomicControl}><WalletCards size={15}/> Apri presidio economico</button>
              <button type="button" onClick={onCalculateContribution}><Calculator size={15}/> Calcola contributo unificato</button>
            </div>
            <div className="iu-fas-regia-action-list iu-fas-regia-action-list--compact">
              {data.economics.filter((item) => ['valore', 'controllo_pagamenti', 'fatturapa', 'tempo'].includes(item.id)).map((item) => <RegiaActionCard key={item.id} label={item.label} value={item.value} note={item.note} href={item.href || '#presidio-fascicolo'} tone={item.tone}/>) }
            </div>
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
              {regia.checklist.map((item) => {
                const itemStatus = recordText(item, 'status')
                return <article key={recordText(item, 'id') || recordText(item, 'key')}><Badge tone={itemStatus === 'BLOCCATO' ? 'danger' : itemStatus === 'COMPLETATO' ? 'success' : 'warning'}>{regiaChecklistStatusLabel(itemStatus)}</Badge><strong>{recordText(item, 'label')}</strong><span>{recordText(item, 'message')}</span><small>{recordText(item, 'suggestedAction')}</small></article>
              })}
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
  const canPrepareNotification = !alreadySent && ['monitoraggio', 'nessuna_notifica', 'da_preparare', 'da_firmare', 'pronta_invio'].includes(monitor.status)
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
          <small className="iu-fas-field-help">Puoi selezionare più file. Il nome e il tipo dichiarato servono solo a organizzare provvisoriamente: dopo l’indicizzazione IUSENTRA legge il contenuto, propone il catalogo e richiede conferma quando le evidenze non bastano.</small>
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

function documentCatalogMethodLabel(doc: FascicoloDocument): { label: string; tone: FascicoloRow['tone']; detail: string } {
  if (doc.catalogMethod === 'contenuto') return { label: 'Catalogato dal contenuto', tone: 'success', detail: doc.catalogEvidence || 'Classificazione prodotta dalla lettura indicizzata.' }
  if (doc.catalogMethod === 'manuale') return { label: 'Catalogazione confermata manualmente', tone: 'primary', detail: doc.catalogEvidence || 'Correzione registrata nel catalogo SQL del fascicolo.' }
  if (doc.catalogMethod === 'metadati_portale') return { label: 'Metadati del portale: contenuto non letto', tone: 'info', detail: doc.catalogEvidence || 'Acquisisci il file per permettere lettura e catalogazione.' }
  return { label: 'Da indicizzare: contenuto non letto', tone: 'warning', detail: doc.catalogEvidence || 'Esegui la lettura documentale prima di usare una classificazione.' }
}

function DocumentRow({ doc, onPreview, onDone, onError }:{doc:FascicoloDocument; onPreview:(preview:PreviewDocument)=>void; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(doc.name)
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameMessage, setRenameMessage] = useState('')
  const tags = visibleDocumentTags(doc)
  const catalogMethod = documentCatalogMethodLabel(doc)
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
      <div><strong>{doc.name}</strong><span>{doc.type} · {doc.size || 'dimensione n.d.'} · {doc.documentDate || doc.uploadedAt || 'data n.d.'}</span>{doc.notes ? <p>{doc.notes}</p> : null}<small className="iu-fas-doc-catalog-state"><Badge tone={catalogMethod.tone}>{catalogMethod.label}</Badge>{catalogMethod.detail}</small>{tags.length ? <em>{tags.join(', ')}</em> : null}</div>
      {renaming ? (
        <form className="iu-fas-doc-rename-form" onSubmit={submitRename}>
          <input value={draftName} onChange={(event) => setDraftName(event.currentTarget.value)} aria-label={`Nuovo nome file ${doc.name}`} />
          <button type="submit" disabled={renameBusy}>{renameBusy ? 'Salvo...' : 'Salva nome'}</button>
          <button type="button" onClick={() => setRenaming(false)} disabled={renameBusy}>Annulla</button>
          {renameMessage ? <small>{renameMessage}</small> : null}
        </form>
      ) : null}
      <div className="iu-fas-doc-badges"><Badge tone={doc.statusTone}>{doc.statusLabel || (doc.signed ? 'Firmato' : 'Da firmare')}</Badge>{doc.catalogLabel ? <Badge tone={catalogTone}>{doc.catalogLabel}</Badge> : null}{doc.source ? <Badge tone="neutral">{doc.source}</Badge> : null}{doc.portalClass ? <Badge tone="info">{doc.portalClass}</Badge> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap iu-fas-doc-actions" aria-label={`Azioni per ${doc.name}`}>
        {doc.actions.acquire ? <a className="iu-fas-doc-action" href={doc.actions.acquire} title="Acquisisci il file dal portale con sessione autenticata o Local Signer"><Download size={15}/><span>Acquisisci dal PST</span></a> : null}
        {doc.actions.preview ? <button type="button" className="iu-fas-doc-action" title="Apri il documento nel lettore interno" onClick={() => onPreview({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}><Eye size={15}/><span>Visualizza</span></button> : null}
        {doc.actions.download ? <DocumentDownloadAction downloadUrl={doc.actions.download} name={doc.name} onDone={onDone} onError={onError}/> : null}
        {doc.actions.edit ? <a className="iu-fas-doc-action" href={doc.actions.edit} title="Apri l’editor del documento" aria-label={`Modifica documento ${doc.name}`}><PencilLine size={15}/><span>Modifica</span></a> : null}
        {doc.actions.sign ? <a className="iu-fas-doc-action" href={doc.actions.sign} title="Apri la firma digitale del documento"><ShieldCheck size={15}/><span>Firma</span></a> : null}
        {doc.actions.attest ? <PostAction action={doc.actions.attest} tone="secondary" onDone={onDone} onError={onError} title="Crea l’attestazione di conformità"><BadgeCheck size={14}/><span>Attesta</span></PostAction> : null}
        {doc.actions.pdfa ? <PostAction action={doc.actions.pdfa} tone="secondary" confirm="Convertire il documento in PDF/A-2B?" confirmTitle="Conversione PDF/A" onDone={onDone} onError={onError} title="Converti in PDF/A-2B"><FileCheck2 size={14}/><span>PDF/A</span></PostAction> : null}
        {doc.actions.delete ? <PostAction action={doc.actions.delete} tone="danger" confirm="Eliminare il documento dal fascicolo?" confirmTitle="Elimina documento" onDone={onDone} onError={onError} title="Elimina documento"><Trash2 size={14}/><span>Elimina</span></PostAction> : null}
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
  onPreview,
  onClose,
}: {
  mode: DocumentFlowMode
  documents: FascicoloDocument[]
  loading: boolean
  baseHref: string
  onPreview: (doc: FascicoloDocument) => void
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
            <article className="iu-fas-document-flow-row" key={doc.id}>
              <label className="iu-fas-document-flow-row__selection">
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
              {doc.actions.preview ? (
                <button
                  type="button"
                  className="iu-fas-document-flow-row__preview"
                  onClick={() => onPreview(doc)}
                  title={'Visualizza ' + doc.name + ' prima di selezionarlo'}
                  aria-label={'Visualizza ' + doc.name + ' prima di selezionarlo'}
                >
                  <Eye size={15}/> Visualizza
                </button>
              ) : (
                <span className="iu-fas-document-flow-row__preview iu-fas-document-flow-row__preview--unavailable" title="Il contenuto non è disponibile localmente: acquisiscilo prima dal PST.">
                  <EyeOff size={15}/> Anteprima non disponibile
                </span>
              )}
            </article>
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

function activityTypeLabel(value: string): string {
  const text = normaliseText(value).replaceAll('_', ' ')
  return text ? `${text.slice(0, 1).toLocaleUpperCase('it-IT')}${text.slice(1).toLocaleLowerCase('it-IT')}` : 'Evento'
}

function ActivityRow({ activity, onPreview }:{activity:FascicoloActivity; onPreview?:(preview:PreviewDocument)=>void}) {
  const resultText = normaliseText(activity.result)
  const sourceDerived = Boolean(activity.sourceIsDerived)
  const readOnlySystemEvent = Boolean(activity.readOnly || sourceDerived)
  const typeLabel = activityTypeLabel(activity.type)
  const displayTitle = sourceDerived ? `${typeLabel} rilevata dal documento` : activity.title
  const displayDescription = sourceDerived ? '' : activity.description
  const badgeText = readOnlySystemEvent
    ? (sourceDerived ? 'Rilevazione' : activity.type || 'Evento estratto')
    : !resultText || /non applicabile/.test(resultText)
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
        <strong>{displayTitle}</strong>
        {sourceDerived ? <span className="iu-fas-activity-derived">Rilevazione dal contenuto: consulta la fonte prima di agire.</span> : null}
        {metaLine ? <span>{metaLine}</span> : null}
        {sourceDerived ? <p className="iu-fas-activity-derived-summary">Informazione estratta dal contenuto indicizzato: il passaggio verificabile è riportato nella fonte qui sotto.</p> : null}
        {displayDescription ? <p>{renderActivityText(displayDescription)}</p> : null}
        {activity.notes ? <em>{renderActivityText(activity.notes)}</em> : null}
        {activity.sourceDocumentHref ? (
          <section className="iu-fas-activity-source" aria-label="Fonte documentale dell'informazione">
            <div>
              <small>Fonte dell'informazione</small>
              <strong>{activity.sourceDocumentLabel || 'Documento indicizzato del fascicolo'}</strong>
              {activity.sourceExcerpt ? <p>Passaggio letto: {activity.sourceExcerpt}</p> : null}
            </div>
            {onPreview ? (
              <button
                type="button"
                onClick={() => onPreview({
                  name: activity.sourceDocumentLabel || 'Documento del fascicolo',
                  url: activity.sourceDocumentHref || '',
                  downloadUrl: activity.sourceDocumentDownloadHref || '',
                })}
                title="Apri nel lettore interno la fonte da cui deriva l'informazione"
              >
                <Eye size={14}/>
                Apri fonte
              </button>
            ) : null}
          </section>
        ) : null}
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
        {!readOnlySystemEvent && activity.updateAction ? <JsonPostForm action={activity.updateAction} className="iu-fas-mini-form iu-fas-mini-form--activity"><select name="esito" defaultValue={activity.result || 'IN_ATTESA'} aria-label="Esito attività"><option value="IN_ATTESA">In attesa</option><option value="FAVOREVOLE">Favorevole</option><option value="PARZIALE">Parziale</option><option value="SFAVOREVOLE">Sfavorevole</option><option value="RINVIATO">Rinviato</option><option value="ANNULLATO">Annullato</option></select><button type="submit"><CheckCircle2 size={13}/> Salva</button></JsonPostForm> : null}
        {!readOnlySystemEvent && activity.deleteAction ? <PostAction action={activity.deleteAction} tone="danger" confirm="Eliminare questa attività?"><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

function DeadlineRow({ deadline }:{deadline:FascicoloDeadline}) {
  return <a className="iu-fas-deadline-row" href={deadline.href}><Badge tone={deadline.tone}>{deadline.priority || deadline.type || 'termine'}</Badge><strong>{deadline.title}</strong><span>{deadline.date}{deadline.peremptory ? ' · perentorio' : ''}</span></a>
}

function documentPresidioDeadlineHref(action: FascicoloDocumentPresidioAction, fascicoloId: string): string {
  const params = new URLSearchParams({
    id_fascicolo: fascicoloId,
    titolo: action.title,
    data_scadenza: action.dateIso,
    tipo: normaliseText(action.type).includes('udienza') ? 'UDIENZA' : 'ALTRO',
    descrizione: action.description,
    note: `Proposta dal presidio documentale. Fonte: ${visibleDocumentSource(action.source)}.`,
  })
  if (action.peremptory) params.set('perentorio', '1')
  return `/scadenziario/nuova?${params.toString()}`
}

function DocumentPresidioPanel({ data, fascicoloId, onOpenDocuments, onPreview, onDone, onError }:{data:FascicoloDetailData; fascicoloId:string; onOpenDocuments:(event: MouseEvent<HTMLAnchorElement>)=>void; onPreview:(preview:PreviewDocument)=>void; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
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
          {actions.slice(0, 6).map((action) => {
            const sourceDocument = data.documents.find((document) => document.id === action.documentId)
            const canPrepareDeadline = Boolean(action.dateIso) && !action.requiresCommunicationDate
            return (
              <article key={action.id}>
                <Badge tone={action.tone}>{action.date || 'Data da confermare'}</Badge>
                <strong>{action.title}</strong>
                <span>{action.description}</span>
                <small>
                  {visibleDocumentSource(action.source)}
                  {action.peremptory ? ' · termine perentorio' : ''}
                  {action.requiresCommunicationDate ? ' · serve data comunicazione' : ''}
                </small>
                <div className="iu-fas-presidio-action-links">
                  {sourceDocument?.actions.preview ? (
                    <button type="button" className="iu-fas-inline-link" onClick={() => onPreview({ name: sourceDocument.name, url: sourceDocument.actions.preview, downloadUrl: sourceDocument.actions.download })}><Eye size={14}/> Apri fonte</button>
                  ) : (
                    <a className="iu-fas-inline-link" href="#documenti" onClick={onOpenDocuments}><FolderOpen size={14}/> Cerca la fonte</a>
                  )}
                  {canPrepareDeadline ? <a className="iu-fas-inline-link" href={documentPresidioDeadlineHref(action, fascicoloId)}><CalendarDays size={14}/> Prepara scadenza</a> : null}
                </div>
                {action.requiresCommunicationDate ? <p className="iu-fas-presidio-action-note">La data di comunicazione non è stata letta: apri la fonte e registrala prima di predisporre il termine.</p> : null}
              </article>
            )
          })}
        </div>
      ) : <p className="iu-empty">{presidio.summary}</p>}
      {presidio.warnings.length ? (
        <div className="iu-fas-presidio-warnings">
          {presidio.warnings.slice(0, 3).map((warning) => <span key={warning}><AlertTriangle size={13}/>{warning}</span>)}
        </div>
      ) : null}
      <div className="iu-fas-presidio-controls">
        <PostAction action={data.actions.refreshLexIndex} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={14}/> Riesegui lettura documentale</PostAction>
        <a className="iu-fas-inline-link" href="#documenti" onClick={onOpenDocuments}><FolderOpen size={14}/> Apri tutti i documenti</a>
      </div>
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
  return formatDateTimeIt(value, value)
}

function copyAuditHash(value: string) {
  if (!value || typeof navigator === 'undefined' || !navigator.clipboard) return
  void navigator.clipboard.writeText(value)
}

function sentenzeEconomicheCount(data: FascicoloSentenzeEconomiche | null) {
  if (!data) return 0
  return Math.max(data.worklist.length, data.totals.sentenze_lette ? 1 : 0)
}

function AuditTrailSection({ audit, bundleHref, onOpen, onOpenDocuments, onPreview, loading = false, defaultOpen = false }:{audit:FascicoloAuditTrail; bundleHref:string; onOpen?:()=>void; onOpenDocuments:(event: MouseEvent<HTMLAnchorElement>)=>void; onPreview:(preview:PreviewDocument)=>void; loading?:boolean; defaultOpen?:boolean}) {
  const hasEvents = audit.events.length > 0
  const effectiveBundleHref = audit.enabled && hasEvents ? (audit.actions.bundle || bundleHref) : ''
  const legalEvents = audit.events.filter((event) => !event.operational)
  const hasLegalEvidence = legalEvents.length > 0
  const operationalOnly = !hasLegalEvidence && audit.status === 'operational'
  return (
    <DetailSection id="audit" title="Audit" icon={<Fingerprint size={17}/>} count={audit.summary.total} defaultOpen={defaultOpen} onOpen={onOpen}>
      {loading ? <p className="iu-empty">Caricamento audit...</p> : null}
      {hasEvents ? (
        <>
          {audit.message ? <p className="iu-fas-audit-context"><Badge tone={operationalOnly ? 'info' : 'neutral'}>{operationalOnly ? 'Registro operativo' : 'Presidio probatorio'}</Badge>{audit.message}</p> : null}
          {hasLegalEvidence ? <div className="iu-fas-audit-summary">
            <span><Badge tone={audit.summary.signed === legalEvents.length && legalEvents.length ? 'success' : 'warning'}>{audit.summary.signed}</Badge><strong>Firmati</strong></span>
            <span><Badge tone={audit.summary.worm === legalEvents.length && legalEvents.length ? 'success' : 'warning'}>{audit.summary.worm}</Badge><strong>WORM</strong></span>
            <span><Badge tone={audit.summary.snapshotted ? 'success' : 'neutral'}>{audit.summary.snapshotted}</Badge><strong>In snapshot</strong></span>
            <span><Badge tone={audit.summary.tsaVerified ? 'success' : 'neutral'}>{audit.summary.tsaVerified}</Badge><strong>TSA verificata</strong></span>
          </div> : null}
          <div className="iu-fas-audit-actions">
            {effectiveBundleHref ? <a href={effectiveBundleHref}><PackageCheck size={15}/> Scarica bundle fascicolo</a> : null}
          </div>
        </>
      ) : !loading ? (
        <div className="iu-fas-empty-action">
          <Badge tone={audit.enabled ? 'warning' : 'neutral'}>{audit.enabled ? 'Nessuna evidenza' : 'Da configurare'}</Badge>
          <strong>{audit.enabled ? 'Nessun riscontro operativo o probatorio registrato per questo fascicolo.' : 'Presidio probatorio non attivo per questo studio.'}</strong>
          <p>{audit.message || (audit.enabled ? 'Le consultazioni e i download compaiono qui dopo l’azione; firme, ricevute e pacchetti probatori restano tracciati separatamente.' : 'Attivare il presidio audit prima di usare il bundle come prova operativa.')}</p>
          <div>
            <a href="#documenti" onClick={onOpenDocuments}><FileText size={14}/> Apri documenti e registra una verifica</a>
            {audit.enabled ? <span>Il bundle si abilita dopo il primo evento registrato.</span> : null}
          </div>
        </div>
      ) : null}
      <div className="iu-fas-audit-list">
        {audit.events.map((event) => (
          <article className={`iu-fas-audit-row${event.operational ? ' is-operational' : ''}`} key={event.eventId}>
            <div>
              <Badge tone={event.tone}>{event.kindLabel}</Badge>
              <time>{formatAuditDate(event.eventTsUtc)}</time>
            </div>
            <div>
              <strong>{event.message || event.eventHashShort || event.eventHash || 'Evento registrato'}</strong>
              <span>{event.reason || (event.prevEventHash ? 'Concatenato al precedente evento' : event.operational ? 'Tracciato nel registro operativo del fascicolo' : 'Primo evento del fascicolo')}</span>
            </div>
            <div className="iu-fas-audit-badges">
              {event.operational ? <Badge tone="info">Operativo</Badge> : event.signed ? <Badge tone="success">Firmato</Badge> : <Badge tone="warning">Firma da verificare</Badge>}
              {!event.operational ? (event.worm ? <Badge tone="success">WORM</Badge> : <Badge tone="warning">Conservazione da verificare</Badge>) : null}
              {!event.operational ? (event.inSnapshot ? <Badge tone="success">In snapshot</Badge> : <Badge tone="neutral">Snapshot in attesa</Badge>) : null}
              {event.tsaVerified ? <Badge tone="success">TSA verificata</Badge> : null}
            </div>
            <div className="iu-fas-actions iu-fas-actions--wrap">
              {event.eventHash ? <button type="button" title="Copia impronta completa" onClick={() => copyAuditHash(event.eventHash)}><Copy size={15}/></button> : null}
              {event.sourceDocumentHref ? <button type="button" className="iu-fas-inline-link" onClick={() => onPreview({ name: event.sourceDocumentLabel || 'Documento del fascicolo', url: event.sourceDocumentHref || '', downloadUrl: event.sourceDocumentDownloadHref || '' })}><Eye size={14}/> Apri documento</button> : null}
              {event.proofHref ? <a href={event.proofHref} title="Scarica prova"><Download size={15}/> Apri riscontro</a> : null}
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
  const detailReturnHref = `/fascicoli/${encodeURIComponent(f.id || id)}#presidio-conformita`
  const exportPdfHref = data.actions.exportPdf || f.exportPdfHref
  const depositTelematicHref = data.telematic.find((item) => /deposito telematico/i.test(item.label))?.href || `/fascicoli/${encodedId}/deposito/prepara`
  const clientId = data.client?.id || f.clientId
  const clientRecordHref = clientId ? `/clienti/${encodeURIComponent(clientId)}/modifica` : '/clienti'
  const partiesRecordHref = `/soggetti?fascicolo=${encodedId}`
  const pagoPaEmbeddedHref = `${PAGOPA_PROXY_NEW_PAYMENT_URL}?iusentra_fascicolo=${encodedId}`
  const openPagoPaModal = useCallback(() => {
    setEmbeddedRecord({ kind: 'pagopa', title: 'Nuovo pagamento PagoPA PST', href: pagoPaEmbeddedHref, externalHref: PAGOPA_PST_NEW_PAYMENT_URL })
  }, [pagoPaEmbeddedHref])
  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (params.get('pagopa') !== 'nuovo') return
    openPagoPaModal()
    params.delete('pagopa')
    const nextQuery = params.toString()
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}${window.location.hash}`
    window.history.replaceState(null, '', nextUrl)
  }, [openPagoPaModal])
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
          technicalEvents: section === 'attivita' ? payload.technicalEvents : current.technicalEvents,
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
  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    const requested = params.get('selezione_documenti')
    if (requested !== 'deposito' && requested !== 'notifica') return

    setContextMenu(null)
    setDocumentFlowMode(requested)
    if (lazyStatus.documenti === 'idle') loadLazySection('documenti')

    params.delete('selezione_documenti')
    const nextQuery = params.toString()
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}${window.location.hash}`
    window.history.replaceState(null, '', nextUrl)
  }, [id, lazyStatus.documenti])
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
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><ArrowLeft size={15}/> Fascicoli</Button><button className="iu-button iu-button--primary" type="button" onClick={() => openDocumentFlow('deposito')}><Send size={15}/> Deposito telematico</button><RecordOverlayButton icon={<UserRound size={15}/>} label="Cliente" title="Visualizza cliente nel fascicolo" onClick={() => setEmbeddedRecord({ kind: 'cliente', title: 'Cliente', href: clientRecordHref })}/><RecordOverlayButton icon={<UsersRound size={15}/>} label="Soggetti" title="Visualizza soggetti e parti nel fascicolo" onClick={() => setEmbeddedRecord({ kind: 'soggetti', title: 'Soggetti e parti', href: partiesRecordHref })}/><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href="#presidio-fascicolo"><Gauge size={15}/> Presidio fascicolo</Button><button className="iu-button iu-button--secondary" type="button" title="Prepara una notifica legale per questa pratica" onClick={() => openDocumentFlow('notifica')}><Bell size={15}/> Notifica</button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button href={exportPdfHref} disabled={!exportPdfHref} title={!exportPdfHref ? 'PDF fascicolo non disponibile' : undefined}><FileDown size={15}/> PDF</Button><PagoPaActionButton onClick={openPagoPaModal}/></div>
      </section>
      <section className="iu-fas-case-strip"><strong>{f.ref}</strong><span>Rif. interno {f.internalRef}</span><span>{f.client}</span><span>{f.court}</span><span>{loading ? 'Caricamento...' : 'Dati aggiornati'}</span></section>
      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}
      <nav className="iu-fas-section-nav" aria-label="Sezioni fascicolo"><a href="#presidio-fascicolo">Presidio fascicolo <b>{data.regia.documentSlots.length + operationalPresidio.actions.length}</b></a><a href="#profilo">Anagrafica <b>{data.quickCounts.profilo || 0}</b></a><a href="#documenti">Documenti e atti <b>{data.quickCounts.documenti || 0}</b></a><a href="#comunicazioni-notifica">Comunicazioni e notifica <b>{displayedCommunicationTotal + notificationRelataCount}</b></a><a href="#attivita">Cronologia <b>{data.quickCounts.attivita || 0}</b></a><a href="#udienze">Udienze / scadenze <b>{data.quickCounts.udienze_scadenze || 0}</b></a><a href="#audit">Audit <b>{data.auditTrail.summary.total}</b></a><a href="#conformita">Controlli <b>{data.quickCounts.presidio_operativo || operationalPresidio.actions.length || 0}</b></a><a href="#soggetti">Soggetti <b>{data.parties.length}</b></a><a href="#telematico">Servizi telematici</a></nav>
      <section className="iu-fas-detail-grid iu-fas-detail-grid--with-guide">
        <aside className="iu-fas-guide-column" aria-label="Guida pratica facoltativa del fascicolo">
          <GuidaPraticaSidebar fascicoloId={f.id || id} codice={f.codiceOggettoPst} fascicoloTitle={f.title}/>
        </aside>
        <div className="iu-fas-detail-content-column">
        <div className="iu-fas-detail-main">
          <RegiaOperativaSection
            data={data}
            onDone={refreshDetail}
            onError={failDetail}
            onOpen={() => loadLazySection('regia')}
            onOpenEconomicControl={() => setEconomicControlOpen(true)}
            onCalculateContribution={() => setContributoModalOpen(true)}
            returnHref={detailReturnHref}
            loading={lazyStatus.regia === 'loading'}
          />
          <DetailSection id="profilo" title="Profilo fascicolo" icon={<BadgeCheck size={17}/>}><KvGrid items={data.profile}/><a className="iu-fas-inline-link" href={f.editHref}><Edit3 size={14}/> Modifica dati fascicolo</a><SourceSnapshotPanel fascicolo={f}/>{f.notes ? <div className="iu-fas-note"><strong>Note</strong><p>{f.notes}</p></div> : null}</DetailSection>
          <DetailSection id="uffici-competenti" title="Uffici giudiziari per Comune" icon={<MapPin size={17}/>} defaultOpen>
            <FascicoloUfficiCompetentiPanel fascicolo={f}/>
          </DetailSection>
          <DetailSection id="documenti" title="Documenti e atti" icon={<FileText size={17}/>} count={data.quickCounts.documenti || 0} defaultOpen={activeHashSection === 'documenti'} onOpen={() => { loadLazySection('documenti') }}>
            <Suspense fallback={<p className="iu-empty">Preparazione ricerca documenti d’ufficio…</p>}>
              <OfficeDocumentsPanel data={data} onDone={refreshDocuments} onError={failDetail} openPortalRequest={officePortalOpenRequest}/>
            </Suspense>
            <DocumentUploadWorkspace data={data} onDone={refreshDetail} onError={failDetail}/>
            <LexIndexingPanel summary={data.lexIndexing} refreshAction={data.actions.refreshLexIndex} retryAction={data.actions.retryLexIndexErrors} onDone={refreshDetail} onError={failDetail}/>
            <CatalogazioneDocumentalePanel
              fascicoloId={f.id || id}
              enabled={lazyStatus.documenti === 'loaded'}
              documents={data.documents}
              onPreview={setPreviewDoc}
              onDone={refreshDetail}
              onError={failDetail}
            />
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
            <div className="iu-fas-activity-list">{lazyStatus.attivita === 'loading' ? <p className="iu-empty">Caricamento attività...</p> : null}{data.activities.map((activity) => <ActivityRow activity={activity} key={activity.id} onPreview={setPreviewDoc}/>)}{lazyStatus.attivita === 'loaded' && !data.activities.length ? <p className="iu-empty">Nessuna attività processuale registrata.</p> : null}{lazyStatus.attivita === 'idle' ? <p className="iu-empty">Apri la sezione per caricare la timeline processuale.</p> : null}</div>
          </DetailSection>
          <DetailSection id="eventi-tecnici" title="Eventi tecnici e acquisizioni" icon={<RefreshCw size={17}/>} count={data.quickCounts.eventi_tecnici || 0} defaultOpen={activeHashSection === 'eventi-tecnici'} onOpen={() => loadLazySection('attivita')}>
            <p className="iu-fas-section-intro">Le acquisizioni da PolisWeb/PST, le sincronizzazioni e i download ufficiali sono tracciati qui: non sono attività processuali e non alterano lo stato della pratica.</p>
            <div className="iu-fas-activity-list">{lazyStatus.attivita === 'loading' ? <p className="iu-empty">Caricamento eventi tecnici...</p> : null}{data.technicalEvents.map((activity) => <ActivityRow activity={activity} key={`technical-${activity.id}`} onPreview={setPreviewDoc}/>)}{lazyStatus.attivita === 'loaded' && !data.technicalEvents.length ? <p className="iu-empty">Nessuna acquisizione o sincronizzazione tecnica registrata.</p> : null}{lazyStatus.attivita === 'idle' ? <p className="iu-empty">Apri la sezione per leggere gli eventi tecnici del fascicolo.</p> : null}</div>
          </DetailSection>
          <DetailSection id="udienze" title="Udienze e scadenze" icon={<CalendarDays size={17}/>} count={data.quickCounts.udienze_scadenze || 0} defaultOpen={activeHashSection === 'udienze'} onOpen={() => { loadLazySection('scadenze'); loadLazySection('documenti') }}>
            {lazyStatus.scadenze === 'loading' ? <p className="iu-empty">Caricamento udienze e scadenze...</p> : null}
            {lazyStatus.scadenze === 'idle' ? <p className="iu-empty">Apri la sezione per caricare udienze e scadenze collegate.</p> : null}
          <DocumentPresidioPanel data={data} fascicoloId={f.id} onOpenDocuments={openSection('documenti', 'documenti')} onPreview={setPreviewDoc} onDone={refreshDocuments} onError={failDetail}/>
            <div className="iu-fas-two-cols"><div><h3>Scadenze</h3>{data.deadlines.map((deadline) => <DeadlineRow deadline={deadline} key={deadline.id}/>)}{lazyStatus.scadenze === 'loaded' && !data.deadlines.length ? <p className="iu-empty">Nessuna scadenza collegata.</p> : null}<a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuova scadenza</a></div><div><h3>Agenda</h3>{data.appointments.map((app) => <a className="iu-fas-deadline-row" href={app.href} key={app.id}><Badge tone={app.tone}>{app.type || 'agenda'}</Badge><strong>{app.title}</strong><span>{app.date} {app.time} {app.place}</span></a>)}{lazyStatus.scadenze === 'loaded' && !data.appointments.length ? <p className="iu-empty">Nessun appuntamento trovato.</p> : null}<a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo appuntamento</a></div></div>
          </DetailSection>
          <DetailSection id="comunicazioni-notifica" title="Comunicazioni, PEC e notifica" icon={<Mail size={17}/>} count={displayedCommunicationTotal + notificationRelataCount} defaultOpen={activeHashSection === 'cancelleria' || activeHashSection === 'comunicazioni-notifica' || activeHashSection === 'relata-notifica' || notificationRelata.releaseDetected || !['monitoraggio', 'nessuna_notifica'].includes(notificationRelata.status)} onOpen={() => { loadLazySection('depositi'); loadLazySection('documenti'); loadLazySection('relata') }}>
            <span id="cancelleria" className="iu-fas-anchor-alias" aria-hidden="true"/>
            <span id="relata-notifica" className="iu-fas-anchor-alias" aria-hidden="true"/>
            <NotificationRelataMonitor data={data}/>
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
          <DetailSection id="avanzamento" title="Avanzamento pratica" icon={<Clock3 size={17}/>} count={data.history.length}><div className="iu-fas-timeline">{data.history.map((item) => <article key={`${item.date}-${item.description}`}><time>{item.date}</time><strong>{item.description}</strong><span>{item.from} → {item.to}</span><p>{item.notes}</p></article>)}{!data.history.length ? <div className="iu-fas-empty-action"><Badge tone="neutral">Nessun evento</Badge><strong>Nessun avanzamento registrato.</strong><p>Registra l'attività o una scadenza effettiva: lo storico del fascicolo verrà aggiornato con data, autore ed esito.</p><div><a href="#attivita" onClick={openSection('attivita', 'attivita')}><ListChecks size={14}/> Registra attività processuale</a><a href="#udienze" onClick={openSection('udienze', 'scadenze')}><CalendarDays size={14}/> Registra udienza o termine</a></div></div> : null}</div></DetailSection>
          <AuditTrailSection audit={data.auditTrail} bundleHref={data.actions.auditBundle} onOpen={() => loadLazySection('audit')} onOpenDocuments={openSection('documenti', 'documenti')} onPreview={setPreviewDoc} loading={lazyStatus.audit === 'loading'} defaultOpen={activeHashSection === 'audit'}/>
        </div>
        <aside className="iu-fas-detail-side">
          <DetailSection id="gestione" title="Gestione fascicolo" icon={<Gauge size={17}/>} defaultOpen={activeHashSection === 'gestione'}>
            <JsonPostForm className="iu-fas-side-form" action={data.actions.changeState}><label><span>Cambia stato</span><select name="stato" defaultValue={f.status.toUpperCase()}>{data.options.states.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note cambio stato"/><button type="submit"><RefreshCw size={15}/> Aggiorna stato</button></JsonPostForm>
            <div className="iu-fas-action-stack"><JsonPostForm action={data.actions.define}><input name="esito_finale" placeholder="Esito finale"/><input name="motivo" placeholder="Motivo"/><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note definizione"/><button type="submit"><CheckCircle2 size={15}/> Definisci</button></JsonPostForm><PostAction action={data.actions.archive} tone="primary" confirm="Archiviare il fascicolo?" confirmTitle="Archivia fascicolo"><Archive size={15}/> Archivia con ZIP</PostAction><PostAction action={data.actions.restore} tone="secondary" confirm="Ripristinare il fascicolo?" confirmTitle="Ripristina fascicolo"><RotateCcw size={15}/> Ripristina</PostAction>{exportPdfHref ? <a className="iu-fas-side-link" href={exportPdfHref}><FileDown size={15}/> PDF fascicolo</a> : <button className="iu-fas-side-link is-disabled" type="button" disabled title="PDF fascicolo non disponibile"><FileDown size={15}/> PDF fascicolo</button>}<PagoPaActionButton variant="side" onClick={openPagoPaModal}/>{data.actions.archiveZip ? <a className="iu-fas-side-link" href={data.actions.archiveZip}><FileArchive size={15}/> Scarica ZIP</a> : null}<PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina</PostAction></div>
          </DetailSection>
          <DetailSection id="ctu" title="CTU e perizie" icon={<Gavel size={17}/>} count={0}><CtuSection fascicoloId={f.id}/></DetailSection>
          <DetailSection id="telematico" title="Servizi telematici" icon={<Send size={17}/>} count={data.telematic.length}><RegistroSyncButton fascicoloId={f.id} lastSyncAt={f.lastSyncAt}/><RegistroCancelleriaPanel fascicoloId={f.id}/><RegistroRgSearch fascicoloId={f.id}/><div className="iu-fas-side-cards">{data.telematic.map((item) => <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}</div></DetailSection>
          <DetailSection id="cliente" title="Cliente" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}>{data.client ? <><KvGrid items={[{ label: 'Nome', value: data.client.name, href: data.client.href }, { label: 'Codice fiscale', value: data.client.taxCode, mono: true }, { label: 'P. IVA', value: data.client.vat, mono: true }, { label: 'Email', value: data.client.email }, { label: 'PEC', value: data.client.pec }, { label: 'Telefono', value: data.client.phone }, { label: 'Indirizzo', value: data.client.address }]}/><a className="iu-fas-inline-link" href={data.client.href}><Edit3 size={14}/> Apri e modifica anagrafica cliente</a></> : <><p className="iu-empty">Cliente non collegato.</p><a className="iu-fas-inline-link" href={f.editHref}><Edit3 size={14}/> Collega un cliente al fascicolo</a></>}</DetailSection>
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
          onPreview={(doc) => setPreviewDoc({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}
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
      <PdfPreviewModal preview={previewDoc} onClose={() => setPreviewDoc(null)} overDocumentFlow={Boolean(documentFlowMode)}/>
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
        onOpenDocuments={() => {
          setEconomicControlOpen(false)
          loadLazySection('documenti')
          openDetailSectionById('documenti')
        }}
        onCalculateContribution={() => {
          setEconomicControlOpen(false)
          setContributoModalOpen(true)
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

function QuadroMiniCard({ label, value, note, tone = 'neutral', href, actionLabel = 'Apri controllo' }:{label:string; value:string|number; note?:string; tone?:FascicoloRow['tone']; href?:string; actionLabel?:string}) {
  const body = <><Badge tone={tone}>{label}</Badge><strong>{value}</strong>{note ? <span>{note}</span> : null}{href && href !== '#' ? <small className="iu-fas-quadro-mini__action"><ChevronRight size={14}/>{actionLabel}</small> : null}</>
  return href && href !== '#' ? <a className="iu-fas-quadro-mini" href={href}>{body}</a> : <article className="iu-fas-quadro-mini">{body}</article>
}

function QuadroAxis({ id, title, icon, status, tone = 'primary', actionHref, actionLabel, children }:{id:string; title:string; icon:ReactNode; status:string; tone?:FascicoloRow['tone']; actionHref?:string; actionLabel?:string; children:ReactNode}) {
  return (
    <section id={id} className="iu-fas-quadro-axis">
      <header>
        <span>{icon}</span>
        <div><strong>{title}</strong><small>{status}</small></div>
        <Badge tone={tone}>{status}</Badge>
      </header>
      <div className="iu-fas-quadro-axis__body">{children}{actionHref && actionLabel ? <a className="iu-fas-quadro-axis__action" href={actionHref}><ChevronRight size={15}/>{actionLabel}</a> : null}</div>
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
  const localDocuments = data.documents.filter((doc) => !doc.actions.acquire)
  const localDocumentCount = data.quickCounts.documenti || localDocuments.length
  const portalDocumentsToAcquire = Math.max(0, data.documents.length - localDocuments.length)
  const signedDocuments = localDocuments.filter((doc) => doc.signed).length
  const unsignedDocuments = Math.max(0, localDocumentCount - signedDocuments)
  const qualityOk = data.quality.filter((item) => item.ok).length
  const qualityIssues = Math.max(0, data.quality.length - qualityOk + (Number(f.alerts) || 0))
  const qualityStatus = qualityIssues ? `${qualityIssues} ${qualityIssues === 1 ? 'verifica' : 'verifiche'}` : 'OK'
  const nextDeadline = data.deadlines[0]
  const nextAppointment = data.appointments[0]
  const valore = moneyFrom(data, 'valore', f.value || '€ 0,00')
  const compenso = moneyFrom(data, 'compenso', f.agreedFee || f.quotedValue || '€ 0,00')
  const parcelle = moneyFrom(data, 'parcelle')
  const tempo = moneyFrom(data, 'tempo', '0 h')
  const fatturaPa = data.economics.find((item) => item.id === 'fatturapa')
  if (loading && !data.fascicolo.id) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<Gauge size={34}/>} title="Caricamento quadro fascicolo">Lettura dei dati operativi, documentali e di conformità in corso.</EmptyState></main>
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<Gauge size={34}/>} title={data.requestError ? 'Dati fascicolo non caricati' : 'Quadro non disponibile'} action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>{data.requestError || 'Il fascicolo non è disponibile o non hai i permessi per aprire il quadro.'}</EmptyState></main>
  return (
    <main id="fascicolo-quadro-top" className="iu-content iu-fascicoli-page iu-fascicolo-quadro-page">
      <section className="iu-fas-hero iu-fas-quadro-hero">
        <div><span className="iu-fas-eyebrow"><Gauge size={16}/> Quadro fascicolo</span><h1>{f.ref} - {f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge><span>{f.object || f.subtitle || 'Vista sinottica della pratica'}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href={detailHref}><FolderOpen size={15}/> Dettaglio</Button><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button variant="primary" href={exportPdfHref} disabled={!exportPdfHref} title={!exportPdfHref ? 'PDF fascicolo non disponibile' : undefined}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-quadro-strip"><strong>{f.rg}</strong><span>{f.court}</span><span>{f.client}</span><span>{loading ? 'Caricamento quadro...' : 'Dati aggiornati'}</span></section>
      <section className="iu-fas-quadro-kpis" aria-label="Indicatori quadro fascicolo">
        <StatCard icon={<FileText size={19}/>} label="Documenti" value={localDocumentCount} note={portalDocumentsToAcquire ? `${portalDocumentsToAcquire} dal portale da acquisire` : `${signedDocuments} firmati`} tone="primary" href={`${detailHref}#documenti`}/>
        <StatCard icon={<FileCheck2 size={19}/>} label="Da firmare" value={unsignedDocuments} note="firma / verifica" tone={unsignedDocuments ? 'warning' : 'success'} href={`${detailHref}#documenti`}/>
        <StatCard icon={<Send size={19}/>} label="Cancelleria" value={data.deposits.length} note={data.deposits[0]?.status || 'nessuna PEC'} tone="purple" href={`${detailHref}#cancelleria`}/>
        <StatCard icon={<Clock3 size={19}/>} label="Scadenze aperte" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.date || nextAppointment?.date || 'nessuna data'} tone="info" href={`${detailHref}#udienze`}/>
        <StatCard icon={<WalletCards size={19}/>} label="Parcelle" value={parcelle} note={`valore ${valore}`} tone="orange" href="/fatturazione/"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Conformità" value={qualityStatus} note={qualityIssues ? 'da verificare' : 'nessun blocco critico'} tone={qualityIssues ? 'warning' : 'success'} href="#conformita"/>
      </section>
      <section className="iu-fas-quadro-client">
        <Panel title="Cliente e dati processuali" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}><KvGrid items={[{ label: 'Cliente', value: f.client, href: data.client?.href }, { label: 'Tribunale', value: f.court }, { label: 'RG', value: f.rg, mono: true }, { label: 'Giudice', value: f.judge || 'n.d.' }, { label: 'Sezione', value: f.section || 'n.d.' }, { label: 'Valore', value: valore }]}/></Panel>
      </section>
      <section className="iu-fas-quadro-grid">
        <QuadroAxis id="commerciale" title="Commerciale" icon={<BriefcaseBusiness size={18}/>} status={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'Conferito' : preventivo.value !== 'Non collegato' && preventivo.value !== '0' ? 'Da conferire' : 'Da creare'} tone={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'success' : 'warning'} actionHref="/preventivi/" actionLabel="Gestisci preventivi e incarichi"><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Preventivo" value={preventivo.value} note={preventivo.note} tone={preventivo.tone} href={preventivo.href} actionLabel="Crea o apri preventivo"/><QuadroMiniCard label="Conferimento" value={conferimento.value} note={conferimento.note} tone={conferimento.tone} href={conferimento.href} actionLabel="Collega incarico"/><QuadroMiniCard label="Compenso" value={compenso} note="dato contrattuale del fascicolo" tone="purple" href="/preventivi/" actionLabel="Gestisci compenso"/></div></QuadroAxis>
        <QuadroAxis id="operativo" title="Operativo" icon={<ClipboardCheck size={18}/>} status={formatFascicoloStatus(f.status)} tone={f.tone} actionHref={`${detailHref}#gestione`} actionLabel="Aggiorna stato e avanzamento"><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Stato" value={formatFascicoloStatus(f.status)} note={f.nextDeadline || 'nessuna prossima scadenza'} tone={f.tone} href={`${detailHref}#gestione`} actionLabel="Apri gestione"/><QuadroMiniCard label="Udienze / scadenze" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.title || nextAppointment?.title || 'nessun evento registrato'} tone="info" href={`${detailHref}#udienze`} actionLabel="Registra o verifica"/><QuadroMiniCard label="Cancelleria" value={data.deposits.length} note={data.deposits[0]?.status || 'nessuna PEC collegata'} tone="purple" href={`${detailHref}#cancelleria`} actionLabel="Apri comunicazioni"/></div></QuadroAxis>
        <QuadroAxis id="conformita" title="Conformità" icon={<ShieldCheck size={18}/>} status={qualityStatus} tone={qualityIssues ? 'warning' : 'success'} actionHref={`${detailHref}#conformita`} actionLabel="Esamina controlli qualità"><div className="iu-fas-quadro-quality">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}{!data.quality.length ? <p className="iu-empty">Nessuna verifica registrata.</p> : null}</div></QuadroAxis>
        <QuadroAxis id="economico" title="Contesto economico" icon={<WalletCards size={18}/>} status={parcelle === '€ 0,00' ? 'Da valorizzare' : 'Valorizzato'} tone={parcelle === '€ 0,00' ? 'warning' : 'success'} actionHref={`${detailHref}#economia`} actionLabel="Apri controlli economici"><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Valore causa" value={valore} note="profilo fascicolo" tone="primary" href={`${detailHref}#profilo`} actionLabel="Apri profilo"/><QuadroMiniCard label="Parcelle" value={parcelle} note="documenti economici collegati" tone="success" href="/fatturazione/" actionLabel="Apri fatturazione"/>{fatturaPa ? <QuadroMiniCard label={fatturaPa.label} value={fatturaPa.value} note={fatturaPa.note} tone={fatturaPa.tone} href={fatturaPa.href} actionLabel="Genera FatturaPA"/> : null}<QuadroMiniCard label="Tempo" value={tempo} note="voci timesheet valorizzabili" tone="info" href="/timesheet" actionLabel="Apri timesheet"/></div></QuadroAxis>
        <QuadroAxis id="documenti" title="Documenti" icon={<FileText size={18}/>} status={unsignedDocuments ? `${unsignedDocuments} da firmare` : 'Completi'} tone={unsignedDocuments ? 'warning' : 'success'} actionHref={`${detailHref}#documenti`} actionLabel="Apri documenti e controlli"><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Nel fascicolo" value={localDocumentCount} note="documenti acquisiti" tone="primary" href={`${detailHref}#documenti`} actionLabel="Apri documenti"/><QuadroMiniCard label="Firmati" value={signedDocuments} note="depositabili / verificati" tone="success" href={`${detailHref}#documenti`} actionLabel="Verifica firme"/><QuadroMiniCard label="Da firmare" value={unsignedDocuments} note="controllo operativo" tone={unsignedDocuments ? 'warning' : 'success'} href={`${detailHref}#documenti`} actionLabel="Apri da firmare"/>{portalDocumentsToAcquire ? <QuadroMiniCard label="Dal portale" value={portalDocumentsToAcquire} note="ancora da acquisire" tone="info" href={`${detailHref}#documenti`} actionLabel="Acquisisci dal portale"/> : null}</div></QuadroAxis>
        <QuadroAxis id="soggetti" title="Soggetti e parti" icon={<UsersRound size={18}/>} status={data.parties.length ? `${data.parties.length} collegati` : 'Da verificare'} tone={data.parties.length ? 'success' : 'warning'} actionHref={`${detailHref}#soggetti`} actionLabel="Apri soggetti e parti"><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.parties.length} note="assistiti, controparti e ruoli" tone={data.parties.length ? 'success' : 'warning'} href={`${detailHref}#soggetti`} actionLabel="Apri soggetti"/><QuadroMiniCard label="Cliente" value={data.client?.name || f.client || 'n.d.'} note="assistito principale" tone="primary" href={data.client?.href || `${detailHref}#profilo`} actionLabel="Apri cliente"/><QuadroMiniCard label="Controparte" value={f.counterparty || 'n.d.'} note="dato fascicolo o parte strutturata" tone={f.counterparty ? 'orange' : 'neutral'} href={`${detailHref}#soggetti`} actionLabel="Verifica controparte"/></div></QuadroAxis>
        <QuadroAxis id="cancelleria" title="Comunicazioni e cancelleria" icon={<Gavel size={18}/>} status={data.deposits.length ? `${data.deposits.length} PEC` : 'Nessuna PEC'} tone={data.deposits.length ? 'purple' : 'neutral'} actionHref={`${detailHref}#cancelleria`} actionLabel="Apri comunicazioni"><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Comunicazioni" value={data.deposits.length} note={data.deposits[0]?.message || 'nessuna PEC collegata'} tone="purple" href={`${detailHref}#cancelleria`} actionLabel="Apri PEC"/><QuadroMiniCard label="Storico" value={data.history.length} note="transizioni e stati fascicolo" tone="info" href={`${detailHref}#avanzamento`} actionLabel="Apri avanzamento"/></div></QuadroAxis>
        <QuadroAxis id="telematico" title="Servizi telematici" icon={<Send size={18}/>} status={data.telematic.length ? 'Presidiati' : 'Da configurare'} tone={data.telematic.length ? 'primary' : 'warning'} actionHref="/telematico" actionLabel="Apri servizi telematici"><div className="iu-fas-quadro-flow">{data.telematic.slice(0, 3).map((item) => <QuadroMiniCard key={item.label} label={item.label} value={item.value} note={item.note} tone={item.tone} href={item.href} actionLabel="Apri servizio"/>)}</div></QuadroAxis>
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
