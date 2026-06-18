import { useEffect, useMemo, useRef, useState, type ChangeEvent, type MouseEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  Clock3,
  ClipboardCheck,
  Copy,
  Download,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderOpen,
  Mail,
  MonitorCheck,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
type LucideIcon,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyTelematicoSurface,
  getTelematicoSurfacePage,
  type ChecklistGroup,
  type OfficeRow,
  type SurfaceAction,
  type SurfaceCard,
  type TelematicoSurfaceData,
  type TelematicoSurfaceId,
} from '../telematicoSurfacesData'
import type { Tone } from '../data'
import './TelematicoSurfacePage.css'

const iconMap: Record<string, LucideIcon> = {
  monitor: MonitorCheck,
  download: Download,
  external: ExternalLink,
  shield: ShieldCheck,
  folder: FolderOpen,
  mail: Mail,
  search: Search,
  refresh: RefreshCw,
  workflow: ClipboardCheck,
}

const surfaceFallbacks: Record<TelematicoSurfaceId, { title: string; context: string }> = {
  polisweb: { title: 'PolisWeb / PST', context: 'telematico-polisweb' },
  pdp: { title: 'PDP Penale', context: 'telematico-pdp' },
  pat: { title: 'PAT Amministrativo', context: 'telematico-pat' },
  ptt: { title: 'PTT Tributario', context: 'telematico-ptt' },
  tribunali: { title: 'Tribunali / PEC', context: 'telematico-tribunali' },
  checklist: { title: 'Controlli Atti', context: 'telematico-checklist' },
  firma: { title: 'Guida firma digitale', context: 'telematico-firma' },
}

const surfaceAppPaths: Record<TelematicoSurfaceId, string> = {
  polisweb: '/polisWeb',
  pdp: '/pdp',
  pat: '/pat',
  ptt: '/sigit',
  tribunali: '/tribunali',
  checklist: '/deposito/checklist',
  firma: '/guida/firma-digitale',
}

const surfacePortals: Partial<Record<TelematicoSurfaceId, 'pst' | 'pdp' | 'pat' | 'ptt'>> = {
  polisweb: 'pst',
  pdp: 'pdp',
  pat: 'pat',
  ptt: 'ptt',
}

type JsonRecord = Record<string, unknown>

type AcquisitionQuery = {
  ufficio: string
  ufficioCodice: string
  ufficioNome: string
  numero: string
  anno: string
  assistito: string
  controparte: string
  cf: string
  oggetto: string
  materia: string
  registro: string
  schema: string
}

type AcquisitionFile = {
  nome: string
  nome_file_originale: string
  contenuto_b64: string
  payload_json: JsonRecord | null
  origine: string
  data_documento: string
  content_type: string
  id_documento_portale: string
  id_deposito_esterno: string
  id_deposito_pct: string
  tipo_atto: string
  tipo: string
  id_cat?: string
  id_repeatto?: string
  id_reperto?: string
  msg_id?: string
  numero_documento?: string
  id_doc_mittente?: string
  id_documento_padre?: string
  parent_nome?: string
  is_allegato?: boolean
  original_documento_portale: boolean
  modalita_documento_portale: 'originale' | 'copia'
}

type AcquisitionResult = {
  id: string
  title: string
  subtitle: string
  badge: string
  meta: string
  raw: JsonRecord
}

type AcquisitionOptions = {
  scarica_originale_portale: boolean
  mantieni_albero_originale: boolean
  importa_documenti: boolean
  importa_eventi: boolean
  importa_scadenze: boolean
  importa_parti: boolean
}

type AcquisitionMapping = {
  mode: 'create_new' | 'attach_existing' | 'update_existing'
  target_fascicolo_id: string
  procedimento: string
  materia: string
  grado: string
}

type AcquisitionTargetDocument = {
  singleDocument: boolean
  documento: string
  idDocumento: string
  hash: string
  pecId: string
  nonDuplicare: boolean
  faseSuccessiva: string
}

const acquisitionMappingModes: Array<[AcquisitionMapping['mode'], string, string]> = [
  ['create_new', 'Crea nuova pratica', 'Precompila area, procedimento, RG e parti dal portale.'],
  ['update_existing', 'Usa pratica esistente', 'Inserisce dati e documenti nel fascicolo locale scelto.'],
]

type BrowserLocalSignerStatus = {
  checked: boolean
  checking: boolean
  ok: boolean
  outdated: boolean
  unsupported: boolean
  version: string
  tokenLabel: string
  message: string
}

type AssistantSession = {
  session_id: string
  portale: string
  official_url: string
  status: string
  local_connector_available: boolean
  downloaded_files: JsonRecord[]
  message: string
}

type PstCertificate = {
  thumbprint: string
  soggetto: string
  emittente: string
  scadenza: string
  tokenSlot: string
  codiceFiscale: string
}

type PstSession = {
  sessionId: string
  tribunale: string
  certThumbprint: string
  expiresAt: number
}

type ImportProgress = {
  active: boolean
  phase: string
  current: string
  completed: number
  total: number
  failures: string[]
}

type AcquisitionHistoryEvent = TelematicoSurfaceData['recentEvents'][number] & {
  local?: boolean
}

const REACT_PST_CERT_KEY = 'iusentra.react.pst.cert.v2'
const REACT_PST_SESSION_KEY = 'iusentra.react.pst.session.v2'
const REACT_PST_SESSION_PURPOSE = 'view'
const REACT_ACQUISITION_HISTORY_KEY = 'iusentra.react.portali.acquisition.history'
const REACT_ACQUISITION_HISTORY_LIMIT = 10
const LOCAL_SIGNER_DEFAULT_TIMEOUT_MS = 45_000
const LOCAL_SIGNER_PST_SEARCH_TIMEOUT_MS = 360_000
const LOCAL_SIGNER_PST_DOWNLOAD_TIMEOUT_MS = 480_000
const LOCAL_SIGNER_PST_STATUS_TIMEOUT_MS = 60_000
const LOCAL_SIGNER_BROWSER_BRIDGE_TIMEOUT_MS = 8_000

function surfaceFromCurrentPath(): TelematicoSurfaceId {
  const raw = window.location.pathname.replace(/\/+$/, '') || '/'
  const route = raw.toLowerCase().startsWith('/app-v2/') ? raw.slice('/app-v2'.length).toLowerCase() : raw.toLowerCase()
  if (route.startsWith('/pdp') || route.startsWith('/portali/pdp')) return 'pdp'
  if (route.startsWith('/pat') || route.startsWith('/portali/pat')) return 'pat'
  if (route.startsWith('/ptt') || route.startsWith('/sigit') || route.startsWith('/portali/ptt') || route.startsWith('/portali/sigit')) return 'ptt'
  if (route.startsWith('/tribunali')) return 'tribunali'
  if (route.startsWith('/deposito/checklist')) return 'checklist'
  if (route.startsWith('/guida/firma-digitale')) return 'firma'
  if (
    route.startsWith('/polisweb') ||
    route.startsWith('/pst') ||
    route.startsWith('/portali/pst')
  ) return 'polisweb'
  return 'polisweb'
}

function normaliseSearch(value: string) {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asText(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim()
  return raw || fallback
}

function asNumber(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function asRecord(value: unknown): JsonRecord {
  return isRecord(value) ? value : {}
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function readStoredRecord(key: string): JsonRecord | null {
  try {
    const raw = window.sessionStorage?.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    return isRecord(parsed) ? parsed : null
  } catch {
    return null
  }
}

function writeStoredRecord(key: string, value: JsonRecord | null) {
  try {
    if (!value) {
      window.sessionStorage?.removeItem(key)
      return
    }
    window.sessionStorage?.setItem(key, JSON.stringify(value))
  } catch {
    // sessionStorage puo essere disabilitato: il flusso resta valido in memoria.
  }
}

function normaliseAcquisitionHistoryEvent(value: unknown): AcquisitionHistoryEvent | null {
  const row = asRecord(value)
  const href = asText(row.href)
  const title = asText(row.title)
  if (!href || !title) return null
  return {
    id: asText(row.id, `local-acq-${Date.now()}`),
    portal: asText(row.portal || 'pst') as AcquisitionHistoryEvent['portal'],
    title,
    subtitle: asText(row.subtitle),
    timestamp: asText(row.timestamp),
    href,
    tone: asText(row.tone, 'warning') as Tone,
    badge: asText(row.badge, 'Riprova'),
    local: row.local !== false,
  }
}

function readAcquisitionHistory(portal = ''): AcquisitionHistoryEvent[] {
  try {
    const raw = window.localStorage?.getItem(REACT_ACQUISITION_HISTORY_KEY)
    const parsed = JSON.parse(raw || '[]') as unknown
    return asList(parsed)
      .map(normaliseAcquisitionHistoryEvent)
      .filter((item): item is AcquisitionHistoryEvent => Boolean(item))
      .filter((item) => !portal || item.portal === portal)
      .slice(0, REACT_ACQUISITION_HISTORY_LIMIT)
  } catch {
    return []
  }
}

function writeAcquisitionHistory(items: AcquisitionHistoryEvent[]) {
  try {
    window.localStorage?.setItem(
      REACT_ACQUISITION_HISTORY_KEY,
      JSON.stringify(items.slice(0, REACT_ACQUISITION_HISTORY_LIMIT)),
    )
  } catch {
    // La cronologia locale e' un aiuto operativo: non deve bloccare il wizard.
  }
}

function acquisitionRetryHref(portal: string, query: AcquisitionQuery, mapping: AcquisitionMapping): string {
  const params = new URLSearchParams()
  const add = (key: string, value: string) => {
    const clean = asText(value)
    if (clean) params.set(key, clean)
  }
  add('ufficio', query.ufficioNome || query.ufficio)
  add('ufficio_codice', query.ufficioCodice)
  add('numero', query.numero)
  add('anno', query.anno)
  add('oggetto', query.oggetto)
  add('materia', query.materia)
  add('registro', query.registro)
  add('schema', query.schema)
  if (mapping.target_fascicolo_id) {
    params.set('fascicolo_id', mapping.target_fascicolo_id)
    params.set('mode', mapping.mode === 'create_new' ? 'update_existing' : mapping.mode)
  }
  if (portal === 'pst' && query.numero && query.anno && (query.ufficio || query.ufficioCodice)) {
    params.set('auto_pst_test', '1')
  }
  const queryString = params.toString()
  return `/portali/${encodeURIComponent(portal)}/acquisizione${queryString ? `?${queryString}` : ''}#wizard-acquisizione`
}

function friendlyAcquisitionReason(value: unknown): string {
  const raw = asText(value, 'Operazione non completata.')
  const lower = raw.toLowerCase()
  if (lower.includes('tempo massimo') || lower.includes('timeout') || lower.includes('non ha risposto')) {
    return 'Il portale ufficiale non ha risposto entro il tempo massimo; possibile sovraffollamento, puoi riprovare con gli stessi dati.'
  }
  if (lower.includes('401') || lower.includes('unauthorized') || lower.includes('pin') || lower.includes('certificato') || lower.includes('autentic')) {
    return 'Certificato o PIN non confermati/accettati sul PC; verifica il dispositivo e riprova.'
  }
  if (lower.includes('documenti reali presenti') || lower.includes('primo elemento da verificare')) {
    return raw
  }
  if (lower.includes('file reali') || lower.includes('solo catalogo') || lower.includes('metadati') || lower.includes('lotto scaricato')) {
    return 'Il PST ha esposto il catalogo, ma non ha consegnato file reali al Local Signer.'
  }
  if (lower.includes('sessione')) {
    return 'Sessione del portale scaduta o non più valida; riapri il canale e riprova.'
  }
  if (lower.includes('nessun fascicolo')) {
    return 'Nessun fascicolo restituito dal portale con questi dati; verifica ufficio, numero e anno.'
  }
  return raw
}

function acquisitionHistorySubtitle(query: AcquisitionQuery, reason: string): string {
  const rg = [query.numero, query.anno].filter(Boolean).join('/')
  const parts = [
    query.ufficioNome || query.ufficio || 'Ufficio non indicato',
    rg ? `R.G. ${rg}` : '',
    reason,
  ].filter(Boolean)
  return parts.join(' - ')
}

function pushAcquisitionHistoryEvent(event: AcquisitionHistoryEvent) {
  const current = readAcquisitionHistory()
  const next = [
    event,
    ...current.filter((item) => item.id !== event.id && item.href !== event.href),
  ].slice(0, REACT_ACQUISITION_HISTORY_LIMIT)
  writeAcquisitionHistory(next)
  window.dispatchEvent(new CustomEvent('iusentra:portal-acquisition-history', { detail: event }))
}

function loadPstCertificate(): PstCertificate | null {
  const saved = readStoredRecord(REACT_PST_CERT_KEY)
  const thumbprint = asText(saved?.thumbprint)
  if (!thumbprint) return null
  return {
    thumbprint,
    soggetto: asText(saved?.soggetto),
    emittente: asText(saved?.emittente),
    scadenza: asText(saved?.scadenza),
    tokenSlot: asText(saved?.tokenSlot || saved?.token_slot),
    codiceFiscale: asText(saved?.codiceFiscale || saved?.codice_fiscale),
  }
}

function storePstCertificate(cert: PstCertificate | null) {
  writeStoredRecord(REACT_PST_CERT_KEY, cert ? {
    thumbprint: cert.thumbprint,
    soggetto: cert.soggetto,
    emittente: cert.emittente,
    scadenza: cert.scadenza,
    tokenSlot: cert.tokenSlot,
    codiceFiscale: cert.codiceFiscale,
  } : null)
}

function extractItalianFiscalCode(value: unknown): string {
  const match = asText(value).toUpperCase().match(/\b([A-Z]{6}[0-9A-Z]{2}[A-Z][0-9A-Z]{2}[A-Z][0-9A-Z]{3}[A-Z])\b/)
  return match?.[1] || ''
}

function coercePstCertificate(value: unknown): PstCertificate | null {
  const root = asRecord(value)
  const record = asRecord(root.certificato_windows_selezionato || root.certificato || root)
  const thumbprint = asText(record.thumbprint)
  if (!thumbprint) return null
  return {
    thumbprint,
    soggetto: asText(record.soggetto || record.subject || record.soggetto_completo),
    emittente: asText(record.emittente || record.issuer || record.emittente_completo),
    scadenza: asText(record.scadenza),
    tokenSlot: asText(record.tokenSlot || record.token_slot),
    codiceFiscale: extractItalianFiscalCode(
      record.codice_fiscale
      || record.codiceFiscale
      || record.codice_fiscale_avvocato
      || `${asText(record.soggetto)} ${asText(record.soggetto_completo)}`,
    ),
  }
}

function certificateMatchesPstPreferences(cert: PstCertificate | null, prefs: JsonRecord, status: JsonRecord): cert is PstCertificate {
  if (!cert?.thumbprint) return false
  const preferCf = extractItalianFiscalCode(prefs.prefer_cf || status.codice_fiscale_avvocato)
  if (!preferCf) return true
  const certText = `${cert.codiceFiscale} ${cert.soggetto}`.toUpperCase()
  return certText.includes(preferCf)
}

function statusHasPstCertificatePreference(status: JsonRecord): boolean {
  const prefs = asRecord(status.cert_preferences)
  return Boolean(extractItalianFiscalCode(prefs.prefer_cf || status.codice_fiscale_avvocato))
}

function loadPstSession(): PstSession | null {
  const saved = readStoredRecord(REACT_PST_SESSION_KEY)
  const sessionId = asText(saved?.sessionId || saved?.session_id)
  if (!sessionId) return null
  return {
    sessionId,
    tribunale: asText(saved?.tribunale),
    certThumbprint: asText(saved?.certThumbprint || saved?.cert_thumbprint),
    expiresAt: asNumber(saved?.expiresAt || saved?.expires_at),
  }
}

function storePstSession(session: PstSession | null) {
  writeStoredRecord(REACT_PST_SESSION_KEY, session ? {
    sessionId: session.sessionId,
    tribunale: session.tribunale,
    certThumbprint: session.certThumbprint,
    expiresAt: session.expiresAt,
  } : null)
}

function isPstSessionActive(session: PstSession | null, tribunale: string, cert: PstCertificate): session is PstSession {
  if (!session?.sessionId) return false
  if (session.expiresAt && session.expiresAt < Date.now()) return false
  const wantedTribunale = asText(tribunale)
  if (wantedTribunale && session.tribunale && wantedTribunale !== session.tribunale) return false
  const savedThumb = session.certThumbprint.toUpperCase()
  const currentThumb = cert.thumbprint.toUpperCase()
  if (savedThumb && currentThumb && savedThumb !== currentThumb) return false
  return true
}

function parsePstSessionExpiry(value: unknown, ttlSeconds: unknown): number {
  const numeric = Number(value ?? 0)
  if (Number.isFinite(numeric) && numeric > 0) {
    return numeric < 100000000000 ? numeric * 1000 : numeric
  }
  const parsedDate = Date.parse(asText(value))
  if (Number.isFinite(parsedDate)) return parsedDate
  const ttl = asNumber(ttlSeconds) || 900
  return Date.now() + ttl * 1000
}

function coercePstSessionFromPayload(value: unknown, tribunale: string, cert: PstCertificate): PstSession | null {
  const record = asRecord(value)
  const sessionId = asText(
    record.sessionId
    || record.session_id
    || record.pst_session_id
    || record.view_session_id
    || record.import_session_id,
  )
  if (!sessionId) return null
  const session: PstSession = {
    sessionId,
    tribunale: asText(record.tribunale || record.codice_ufficio || tribunale),
    certThumbprint: asText(record.certThumbprint || record.cert_thumbprint || record.cert_key || cert.thumbprint),
    expiresAt: parsePstSessionExpiry(
      record.expiresAt || record.expires_at || record.view_expires_at || record.import_expires_at,
      record.pst_session_ttl_seconds,
    ),
  }
  return isPstSessionActive(session, tribunale, cert) ? session : null
}

function acquisitionInitialFascicoloId(): string {
  const params = new URLSearchParams(window.location.search)
  return asText(
    params.get('id_fasc')
    || params.get('fascicolo_id')
    || params.get('target_fascicolo_id'),
  )
}

function acquisitionInitialQuery(): AcquisitionQuery {
  const params = new URLSearchParams(window.location.search)
  const documento = asText(params.get('documento') || params.get('documento_portale'))
  const schema = asText(params.get('schema') || params.get('tabella') || params.get('tabella_ministeriale') || params.get('quick_filter'))
  const materia = asText(params.get('materia') || schema || params.get('oggetto') || documento)
  const registro = asText(params.get('registro') || params.get('tipo_registro') || params.get('quick_filter') || schema)
  return {
    ufficio: asText(params.get('ufficio')),
    ufficioCodice: asText(params.get('ufficio_codice')),
    ufficioNome: asText(params.get('ufficio')),
    numero: asText(params.get('numero')),
    anno: asText(params.get('anno'), String(new Date().getFullYear())),
    assistito: asText(params.get('assistito')),
    controparte: asText(params.get('controparte')),
    cf: asText(params.get('cf') || params.get('codice_fiscale')),
    oggetto: asText(params.get('oggetto') || materia || documento),
    materia,
    registro,
    schema,
  }
}

function acquisitionTargetDocument(): AcquisitionTargetDocument {
  const params = new URLSearchParams(window.location.search)
  const singleRaw = asText(params.get('single_document')).toLowerCase()
  const noDuplicateRaw = asText(params.get('non_duplicare_documenti')).toLowerCase()
  return {
    singleDocument: ['1', 'true', 'si', 'sì'].includes(singleRaw),
    documento: asText(params.get('documento') || params.get('documento_portale')),
    idDocumento: asText(params.get('id_documento')),
    hash: asText(params.get('hash')).toLowerCase(),
    pecId: asText(params.get('pec_id')),
    nonDuplicare: ['1', 'true', 'si', 'sì'].includes(noDuplicateRaw),
    faseSuccessiva: asText(params.get('fase_successiva')),
  }
}

function acquisitionTargetPayload(target: AcquisitionTargetDocument): JsonRecord {
  if (!target.singleDocument) return {}
  return {
    singleDocument: target.singleDocument,
    documento: target.documento,
    idDocumento: target.idDocumento,
    hash: target.hash,
    pecId: target.pecId,
    nonDuplicare: target.nonDuplicare,
    faseSuccessiva: target.faseSuccessiva,
  }
}

function ministerialSchemaFromQuery(query: AcquisitionQuery): string {
  return asText(query.schema || query.registro || query.materia || query.oggetto)
}

function ministerialHintsFromQuery(query: AcquisitionQuery): JsonRecord {
  const schema = ministerialSchemaFromQuery(query)
  return {
    materia: asText(query.materia || query.oggetto || schema),
    registro: asText(query.registro || schema),
    schema,
    tipo_registro: asText(query.registro || schema),
    quick_filter: schema,
  }
}

function acquisitionInitialMappingMode(targetFascicoloId = acquisitionInitialFascicoloId()): AcquisitionMapping['mode'] {
  const params = new URLSearchParams(window.location.search)
  const requestedMode = asText(params.get('mode')).toLowerCase()
  if (requestedMode === 'attach_existing' || requestedMode === 'update_existing') return 'update_existing'
  if (requestedMode === 'create_new' && !targetFascicoloId) return 'create_new'
  return targetFascicoloId ? 'update_existing' : 'create_new'
}

function isPstSessionExpiredError(error: unknown): boolean {
  const text = String(error instanceof Error ? error.message : error || '')
  return text.includes('session_expired') || text.includes('Sessione accesso PST scaduta') || text.includes('riaprire il canale autenticato')
}

function italianDate(value: unknown): string {
  const raw = asText(value)
  if (!raw) return 'n.d.'
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2}))?/)
  if (iso) {
    const [, year, month, day, hour, minute] = iso
    return hour && minute ? `${day}/${month}/${year} ${hour}:${minute}` : `${day}/${month}/${year}`
  }
  return raw
}

function portalFromSurface(surfaceId: TelematicoSurfaceId, data: TelematicoSurfaceData): 'pst' | 'pdp' | 'pat' | 'ptt' | '' {
  const fromPayload = data.surface.portal
  if (fromPayload === 'pst' || fromPayload === 'pdp' || fromPayload === 'pat' || fromPayload === 'ptt') return fromPayload
  return surfacePortals[surfaceId] || ''
}

function isAcquisitionPath(portal: string): boolean {
  if (!portal) return false
  const route = normalizeAppPath(window.location.pathname)
  if (portal === 'ptt' && (route === '/portali/sigit/acquisizione' || route.startsWith('/portali/sigit/acquisizione/'))) return true
  return route === `/portali/${portal}/acquisizione` || route.startsWith(`/portali/${portal}/acquisizione/`)
}

function formatGeneratedAt(value: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function linkKindLabel(kind: string) {
  const labels: Record<string, string> = {
    react: 'Operativo',
    operativo: 'Modulo',
    esterno: 'Esterno',
    download: 'Download',
    api: 'Servizio',
    link: 'Link',
  }
  return labels[kind] || 'Link'
}

function sameOriginUrl(href: string): URL | null {
  try {
    const url = new URL(href, window.location.origin)
    return url.origin === window.location.origin ? url : null
  } catch {
    return null
  }
}

function normalizeAppPath(pathname: string): string {
  const clean = pathname.replace(/\/+$/, '').toLowerCase() || '/'
  return clean.startsWith('/app-v2/') ? clean.slice('/app-v2'.length) || '/' : clean
}

function isSameSurfaceAction(surfaceId: TelematicoSurfaceId, action: SurfaceAction): boolean {
  if (action.method === 'POST' || action.external) return false
  const url = sameOriginUrl(action.href)
  if (!url) return false
  const actionPath = normalizeAppPath(url.pathname)
  const currentSurfacePath = normalizeAppPath(surfaceAppPaths[surfaceId])
  const aliases: Partial<Record<TelematicoSurfaceId, string[]>> = {
    polisweb: ['/polisweb', '/pst', '/portali/pst', '/portali/pst/acquisizione'],
    pdp: ['/pdp', '/portali/pdp', '/portali/pdp/acquisizione'],
    pat: ['/pat', '/portali/pat', '/portali/pat/acquisizione'],
    ptt: ['/ptt', '/sigit', '/portali/ptt', '/portali/sigit', '/portali/ptt/acquisizione', '/portali/sigit/acquisizione'],
  }
  return actionPath === currentSurfacePath || Boolean(aliases[surfaceId]?.some((alias) => actionPath === alias || actionPath.startsWith(`${alias}/`)))
}

function scrollToSurfaceTarget(targetId: string) {
  const target = document.getElementById(targetId)
  if (!target) return
  const topbar = document.querySelector<HTMLElement>('.iu-topbar')
  if (!topbar) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  const offset = (topbar?.getBoundingClientRect().height || 76) + 18
  const top = Math.max(0, target.getBoundingClientRect().top + window.scrollY - offset)
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  window.scrollTo({ top, behavior: reducedMotion ? 'auto' : 'smooth' })
}

function statToneClass(tone: Tone) {
  return `iu-tel-surface-stat iu-tel-surface-stat--${tone}`
}

function Stat({ label, value, tone = 'primary', icon }:{ label:string; value:number|string; tone?:Tone; icon:ReactNode }) {
  return (
    <article className={statToneClass(tone)}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function ActionLink({
  action,
  onPost,
  onNavigate,
}:{
  action:SurfaceAction
  onPost:(action:SurfaceAction)=>void
  onNavigate:(event: MouseEvent<HTMLAnchorElement>, action:SurfaceAction)=>void
}) {
  if (action.method === 'POST') {
    return (
      <button type="button" onClick={() => onPost(action)}>
        <RefreshCw size={15}/> {action.label}
      </button>
    )
  }
  return (
    <a href={action.href} onClick={(event) => onNavigate(event, action)} target={action.external ? '_blank' : undefined} rel={action.external ? 'noreferrer' : undefined}>
      {action.external ? <ExternalLink size={15}/> : <ArrowRight size={15}/>} {action.label}
    </a>
  )
}

function OperationCard({
  card,
  selected,
  onPost,
  onNavigate,
}:{
  card:SurfaceCard
  selected:boolean
  onPost:(action:SurfaceAction)=>void
  onNavigate:(event: MouseEvent<HTMLAnchorElement>, card:SurfaceCard, action:SurfaceAction)=>void
}) {
  const Icon = iconMap[card.icon] || ClipboardCheck
  return (
    <article className={`iu-tel-op-card iu-tel-op-card--${card.tone} ${selected ? 'is-selected' : ''}`}>
      <header>
        <div><Icon size={20}/></div>
        <span>{card.title}</span>
      </header>
      <p>{card.body}</p>
      {card.metrics.length ? (
        <dl>
          {card.metrics.map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {card.actions.length ? (
        <footer>
          {card.actions.map((action) => (
            <ActionLink
              action={action}
              onPost={onPost}
              onNavigate={(event, selectedAction) => onNavigate(event, card, selectedAction)}
              key={action.id}
            />
          ))}
        </footer>
      ) : null}
    </article>
  )
}

function ActiveOperationPanel({
  surfaceId,
  title,
  card,
  action,
  onLex,
}:{
  surfaceId: TelematicoSurfaceId
  title:string
  card:SurfaceCard
  action:SurfaceAction
  onLex:()=>void
}) {
  const Icon = iconMap[card.icon] || ClipboardCheck
  const checklistHref = surfaceId === 'checklist' ? surfaceAppPaths.checklist : `${surfaceAppPaths[surfaceId]}#checklist-operativa`
  return (
    <section id="operazione-attiva" className={`iu-tel-active-op iu-tel-active-op--${card.tone}`}>
      <div className="iu-tel-active-op__icon"><Icon size={23}/></div>
      <div className="iu-tel-active-op__copy">
        <span>Operazione pronta</span>
        <h2>{action.label || card.title}</h2>
        <p>{card.body}</p>
        <dl>
          <div><dt>Superficie</dt><dd>{title}</dd></div>
          <div><dt>Modalità</dt><dd>Operativa</dd></div>
          <div><dt>Canale</dt><dd>{surfaceId === 'polisweb' ? 'PST / PolisWeb' : surfaceId.toUpperCase()}</dd></div>
        </dl>
      </div>
      <div className="iu-tel-active-op__actions">
        <a href="/fascicoli">Scegli fascicolo</a>
        <a href={checklistHref}>Controlli</a>
        <button type="button" onClick={onLex}>Chiedi a Lex</button>
      </div>
    </section>
  )
}

function ChecklistPanel({
  groups,
  surfaceId,
}:{
  groups: ChecklistGroup[]
  surfaceId: TelematicoSurfaceId
}) {
  const storagePrefix = `iusentra.telematico.${surfaceId}.check.`
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const next: Record<string, boolean> = {}
    groups.forEach((group) => {
      group.items.forEach((item) => {
        next[item.id] = window.localStorage.getItem(`${storagePrefix}${item.id}`) === '1'
      })
    })
    setChecked(next)
  }, [groups, storagePrefix])

  const total = groups.reduce((sum, group) => sum + group.items.length, 0)
  const done = Object.values(checked).filter(Boolean).length
  if (!groups.length) return null

  return (
    <section id="checklist-operativa" className="iu-tel-anchor-target">
      <Panel title="Checklist operativa" subtitle="Le spunte restano salvate sulla postazione in uso" icon={<ClipboardCheck size={17}/>} count={`${done}/${total}`}>
        <div className="iu-tel-checklist">
          {groups.map((group) => (
            <section key={group.id}>
              <h3>{group.title}</h3>
              {group.items.map((item) => {
                const itemId = `${surfaceId}-${group.id}-${item.id}`
                return (
                  <label className="iu-tel-check-item" htmlFor={itemId} key={item.id}>
                    <input
                      id={itemId}
                      type="checkbox"
                      checked={Boolean(checked[item.id])}
                      onChange={(event) => {
                        const value = event.currentTarget.checked
                        setChecked((current) => ({ ...current, [item.id]: value }))
                        window.localStorage.setItem(`${storagePrefix}${item.id}`, value ? '1' : '0')
                      }}
                    />
                    <span>
                      <strong>{item.label}</strong>
                      <small>{item.description}</small>
                    </span>
                    {item.critical ? <Badge tone="danger">Critico</Badge> : null}
                  </label>
                )
              })}
            </section>
          ))}
        </div>
      </Panel>
    </section>
  )
}

function ControlList({ title, items, empty }:{ title:string; items:TelematicoSurfaceData['controlTower']['warnings']; empty:string }) {
  return (
    <Panel title={title} icon={<ShieldCheck size={17}/>} count={items.length}>
      {items.length ? (
        <div className="iu-tel-surface-list">
          {items.map((item) => (
            <a href={item.href} key={item.id}>
              <Badge tone={item.tone}>{item.badge}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
              </div>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">{empty}</p>}
    </Panel>
  )
}

function CasesPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Pratiche collegate" subtitle="Fascicoli e import del canale" icon={<FolderOpen size={17}/>} count={data.recentCases.length}>
      {data.recentCases.length ? (
        <div className="iu-tel-surface-cases">
          {data.recentCases.map((item) => (
            <a href={item.href} key={item.id}>
              <Badge tone={item.tone}>{item.portalLabel}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
                <small>{item.subject || 'Oggetto non indicato'}</small>
              </div>
              <em>{item.documentsCount} documenti</em>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">Nessuna pratica collegata a questa pagina.</p>}
    </Panel>
  )
}

function mergeAcquisitionEvents(
  serverEvents: TelematicoSurfaceData['recentEvents'],
  localEvents: AcquisitionHistoryEvent[],
): AcquisitionHistoryEvent[] {
  const seen = new Set<string>()
  return [...localEvents, ...serverEvents].filter((event) => {
    const key = `${event.href}|${event.title}|${event.timestamp}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).slice(0, 14)
}

function EventsPanel({ data, localEvents = [] }:{ data:TelematicoSurfaceData; localEvents?: AcquisitionHistoryEvent[] }) {
  const events = mergeAcquisitionEvents(data.recentEvents, localEvents)
  return (
    <Panel title="Cronologia" subtitle="Import, esiti e azioni recenti" icon={<RefreshCw size={17}/>} count={events.length}>
      {events.length ? (
        <div className="iu-tel-surface-events">
          {events.map((item) => (
            <a href={item.href} key={item.id} className={item.local ? 'is-retry-event' : undefined}>
              <Badge tone={item.tone}>{item.badge || 'Evento'}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
                <time>{item.timestamp}</time>
              </div>
              {item.local ? <em>Riprova</em> : null}
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">Nessun evento telematico recente.</p>}
    </Panel>
  )
}

function AcquisitionProgressView({ progress }: { progress: ImportProgress }) {
  if (!(progress.active || progress.phase || progress.failures.length)) return null
  return (
    <div className="iu-tel-acq-progress" aria-live="polite">
      <div>
        <strong>{progress.phase || 'Operazione in corso'}</strong>
        <span>{progress.current || 'Preparazione dati'}</span>
        <small>{progress.total ? `${progress.completed}/${progress.total} passaggi` : 'Operazione in corso'}</small>
      </div>
      <progress value={progress.total ? progress.completed : undefined} max={progress.total || undefined}/>
      {progress.failures.length ? (
        <ul>
          {progress.failures.slice(0, 5).map((failure) => <li key={failure}>{failure}</li>)}
        </ul>
      ) : null}
    </div>
  )
}

function shortHash(value: string): string {
  const clean = value.trim()
  return clean.length > 12 ? `${clean.slice(0, 12)}...` : clean
}

function certificateTone(office: OfficeRow): Tone {
  if (!office.certificatoCifratura.richiesto) return 'neutral'
  if (office.certificatoCifratura.verificato) return 'success'
  return office.certificatoCifratura.presente ? 'warning' : 'danger'
}

function certificateLabel(office: OfficeRow): string {
  const cert = office.certificatoCifratura
  if (!cert.richiesto) return 'Non richiesto'
  if (cert.verificato) return '.cer verificato'
  if (cert.presente) return '.cer da validare'
  return '.cer da acquisire'
}

function OfficeDirectory({ data }:{ data:TelematicoSurfaceData }) {
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('tutti')
  const [copied, setCopied] = useState('')
  const types = useMemo(() => ['tutti', ...Object.keys(data.officeSummary.perType || {}).sort()], [data.officeSummary.perType])
  const certificateSummary = data.officeSummary.certificates
  const offices = useMemo(() => {
    const needle = normaliseSearch(query)
    return data.offices.filter((office) => {
      const haystack = normaliseSearch([
        office.nome,
        office.codice,
        office.codiceMinistero,
        office.pec,
        office.tipo,
        office.distretto,
        office.comune,
        office.provincia,
        office.nomeCertificatoCifra,
        office.certificatoMimetype,
        office.certificatoCifratura.codiceUfficio,
        office.certificatoCifratura.stato,
        office.certificatoCifratura.nomeCertificatoCifra,
      ].join(' '))
      const typeOk = typeFilter === 'tutti' || office.tipo === typeFilter
      return typeOk && (!needle || haystack.includes(needle))
    }).slice(0, 80)
  }, [data.offices, query, typeFilter])

  const copyPec = async (office: OfficeRow) => {
    if (!office.pec) return
    try {
      await navigator.clipboard.writeText(office.pec)
      setCopied(office.id)
      window.setTimeout(() => setCopied(''), 1400)
    } catch {
      setCopied('')
    }
  }

  return (
    <section className="iu-tel-offices">
      <header>
        <div>
          <span>Elenco uffici</span>
          <h2>Tribunali e indirizzi PEC</h2>
          <p>{certificateSummary.present} certificati .cer associati su {certificateSummary.required} uffici PCT/SIGP con cifratura.</p>
        </div>
        <label><Search size={16}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca ufficio, PEC, distretto, codice..."/></label>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filtra tipo ufficio">
          {types.map((type) => <option value={type} key={type}>{type === 'tutti' ? 'Tutti i tipi' : type}</option>)}
        </select>
      </header>
      <div className="iu-tel-office-list">
        {offices.map((office) => (
          <article key={office.id}>
            <div>
              <Badge tone="primary">{office.tipo || 'Ufficio'}</Badge>
              <Badge tone={certificateTone(office)}>{certificateLabel(office)}</Badge>
              <strong>{office.nome}</strong>
              <span>{[office.codice || office.codiceMinistero, office.distretto, office.comune || office.provincia].filter(Boolean).join(' - ')}</span>
              <small className="iu-tel-office-cert">
                <ShieldCheck size={14}/>
                {office.certificatoCifratura.richiesto
                  ? [
                      `Codice PST ${office.certificatoCifratura.codiceUfficio || 'n.d.'}`,
                      office.nomeCertificatoCifra || office.certificatoCifratura.nomeCertificatoCifra
                        ? `file ${office.nomeCertificatoCifra || office.certificatoCifratura.nomeCertificatoCifra}`
                        : 'recupero diretto per codice',
                      office.certificatoCifratura.notValidAfter ? `scade ${office.certificatoCifratura.notValidAfter.slice(0, 10)}` : '',
                      office.certificatoCifratura.sha256 ? `SHA256 ${shortHash(office.certificatoCifratura.sha256)}` : '',
                    ].filter(Boolean).join(' - ')
                  : 'Canale senza cifratura PCT Atto.enc'}
              </small>
            </div>
            <button type="button" onClick={() => copyPec(office)} disabled={!office.pec}>
              <Copy size={15}/> {office.pec ? (copied === office.id ? 'Copiata' : office.pec) : 'PEC assente'}
            </button>
          </article>
        ))}
      </div>
    </section>
  )
}

function LinksPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Collegamenti rapidi" icon={<ExternalLink size={17}/>} count={data.links.length}>
      <div className="iu-tel-surface-links">
        {data.links.map((link) => (
          <a href={link.href} key={`${link.kind}-${link.href}`}>
            <span>{linkKindLabel(link.kind)}</span>
            <strong>{link.label}</strong>
            <ArrowRight size={15}/>
          </a>
        ))}
      </div>
    </Panel>
  )
}

function SurfaceSidePanels({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <>
      <ControlList title="Esiti in attesa" items={data.controlTower.pendingOutcomes} empty="Nessun esito in attesa."/>
      <ControlList title="Import incompleti" items={data.controlTower.incompleteImports} empty="Nessun import incompleto."/>
      <ControlList title="Controlli predeposito" items={[...data.controlTower.blockedCases, ...data.controlTower.predeposito]} empty="Nessun blocco predeposito."/>
      <LinksPanel data={data}/>
    </>
  )
}

function LexPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Suggerimenti Lex AI" icon={<Sparkles size={17}/>} count={data.lexSuggestions.length}>
      {data.lexSuggestions.length ? (
        <div className="iu-tel-surface-lex">
          {data.lexSuggestions.map((item) => <span key={item}><Sparkles size={15}/>{item}</span>)}
        </div>
      ) : <p className="iu-empty">Lex non segnala ulteriori priorita su questa pagina.</p>}
    </Panel>
  )
}

function portalLabel(portal: string): string {
  const labels: Record<string, string> = {
    pst: 'PST / PolisWeb',
    pdp: 'PDP Penale',
    pat: 'PAT / SIGA',
    ptt: 'PTT / SIGIT',
  }
  return labels[portal] || 'Portale'
}

function compareVersions(left: string, right: string): number {
  const leftParts = left.split('.').map((part) => Number.parseInt(part, 10) || 0)
  const rightParts = right.split('.').map((part) => Number.parseInt(part, 10) || 0)
  const max = Math.max(leftParts.length, rightParts.length)
  for (let index = 0; index < max; index += 1) {
    const diff = (leftParts[index] || 0) - (rightParts[index] || 0)
    if (diff !== 0) return diff
  }
  return 0
}

function localSignerInstallHref(data: TelematicoSurfaceData): string {
  const platform = navigator.platform.toLowerCase()
  if (platform.includes('mac')) return data.localSigner.macosUrl
  if (platform.includes('linux')) return data.localSigner.linuxUrl
  return data.localSigner.windowsUrl
}

function isDesktopLocalSignerHost(): boolean {
  if (typeof navigator === 'undefined') return true
  const userAgent = String(navigator.userAgent || '').toLowerCase()
  const platformName = String(navigator.platform || '').toLowerCase()
  const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent)
  const isIpadDesktopMode = platformName.includes('mac') && Number(navigator.maxTouchPoints || 0) > 1
  return !isMobileOrTablet && !isIpadDesktopMode
}

function requestLocalSignerProtocol(uri: string) {
  if (!isDesktopLocalSignerHost()) return
  const iframe = document.createElement('iframe')
  iframe.hidden = true
  iframe.src = uri
  document.body.appendChild(iframe)
  window.setTimeout(() => iframe.remove(), 3000)
}

function requestLocalSignerStart() {
  requestLocalSignerProtocol('iusentra-local-signer://restart')
}

function requestLocalSignerUpdate() {
  requestLocalSignerProtocol('iusentra-local-signer://update')
}

function requestLocalSignerInstallerDownload(data: TelematicoSurfaceData) {
  if (!isDesktopLocalSignerHost()) return
  const iframe = document.createElement('iframe')
  iframe.hidden = true
  iframe.src = localSignerInstallHref(data)
  document.body.appendChild(iframe)
  window.setTimeout(() => iframe.remove(), 30000)
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function officialPortalHref(portal: string): string {
  const urls: Record<string, string> = {
    pst: 'https://pst.giustizia.it/PST/it/services.page',
    pdp: 'https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp',
    pat: 'https://pe.prod.cloud.giustizia-amministrativa.it',
    ptt: 'https://sigit.giustiziatributaria.gov.it/Sigit/index.do',
  }
  return urls[portal] || ''
}

function isOfficialAssistantPortal(portal: string): boolean {
  return ['pdp', 'pat', 'ptt'].includes(portal)
}

function diagnosticPayloadForServer(value: unknown): unknown {
  if (Array.isArray(value)) return value.slice(0, 80).map(diagnosticPayloadForServer)
  if (isRecord(value)) {
    const cleaned: JsonRecord = {}
    Object.entries(value).slice(0, 120).forEach(([key, item]) => {
      const lowered = key.toLowerCase()
      if (['pin', 'password', 'password_pec', 'authorization', 'access_token', 'refresh_token', 'secret', 'api_key'].includes(lowered)) {
        cleaned[key] = '[omesso]'
        return
      }
      const safeKey = lowered === 'token' ? 'dispositivi' : key
      cleaned[safeKey] = diagnosticPayloadForServer(item)
    })
    return cleaned
  }
  if (typeof value === 'string') return value.length > 12000 ? `${value.slice(0, 12000)}... [troncato]` : value
  return value
}

async function saveLocalSignerDiagnostic(payload: JsonRecord): Promise<void> {
  try {
    await fetch('/api/v1/ui/local-signer/diagnostics', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(diagnosticPayloadForServer(payload)),
    })
  } catch {
    // La diagnosi non deve bloccare l'operazione principale sul portale.
  }
}

async function portalJson(portal: string, endpoint: string, body?: JsonRecord): Promise<JsonRecord> {
  const response = await fetch(`/api/portali/${encodeURIComponent(portal)}/acquisizione/${endpoint}`, {
    method: body ? 'POST' : 'GET',
    credentials: 'same-origin',
    headers: body ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const payload = await response.json().catch(() => ({}))
  return isRecord(payload) ? payload : {}
}

function normaliseAcquisitionResult(value: unknown, index: number): AcquisitionResult {
  const row = asRecord(value)
  const title = asText(row.title || row.titolo || row.numero_rg || row.rg || row.numero, `Fascicolo ${index + 1}`)
  const office = asText(row.ufficio || row.tribunale || row.office_name || row.court)
  const party = asText(row.assistito || row.cliente || row.parte || row.ricorrente || row.imputato)
  const counterparty = asText(row.controparte || row.resistente || row.parte_offesa)
  return {
    id: asText(row.id || row.id_fascicolo || row.practice_id || row.numero_rg || row.numero, `result-${index}`),
    title,
    subtitle: [office, party, counterparty].filter(Boolean).join(' - ') || 'Risultato dal canale autorizzato',
    badge: asText(row.stato || row.status || row.registro || row.tipo, 'Fascicolo'),
    meta: italianDate(row.data || row.data_iscrizione || row.updated_at || row.last_sync_at),
    raw: row,
  }
}

function normalisePstAcquisitionResult(value: unknown, index: number, query: AcquisitionQuery, tribunale: string): AcquisitionResult {
  const row = asRecord(value)
  const partiDettaglio = asList(row.parti_dettaglio).map(asRecord)
  const contropartiDaRuolo = partiDettaglio
    .filter((item) => /convenuto|resistente|controparte/i.test(asText(item.tipo)))
    .map((item) => asText(item.nome))
    .filter(Boolean)
  const partiDaRuolo = partiDettaglio
    .filter((item) => !/convenuto|resistente|controparte/i.test(asText(item.tipo)))
    .map((item) => asText(item.nome))
    .filter(Boolean)
  const numero = asText(row.numero_rg || row.numero)
  const anno = asNumber(row.anno_rg || row.anno)
  const procedimento = asText(row.ruolo || row.procedimento || row.tipo)
  const codiceUfficio = asText(row.codice_ufficio || row.ufficio_codice || tribunale)
  const nomeUfficio = asText(row.nome_ufficio || row.ufficio_nome || query.ufficioNome || query.ufficio)
  const parti = asList(row.parti).map((item) => asText(item)).filter(Boolean)
  const controparti = asList(row.controparti).map((item) => asText(item)).filter(Boolean)
  const raw = {
    external_id: `${codiceUfficio}:${numero}:${anno || ''}:${procedimento}`,
    id_fascicolo: asText(row.id_fascicolo),
    numero,
    anno,
    ufficio_codice: codiceUfficio,
    ufficio_nome: nomeUfficio,
    procedimento,
    sub_procedimento: asText(row.sub_procedimento),
    sezione: asText(row.sezione),
    stato: asText(row.stato),
    oggetto: asText(row.oggetto || query.oggetto),
    parti: parti.length ? parti : (partiDaRuolo.length ? partiDaRuolo : query.assistito.split(/[;,]/).map((item) => item.trim()).filter(Boolean)),
    controparti: controparti.length ? controparti : (contropartiDaRuolo.length ? contropartiDaRuolo : query.controparte.split(/[;,]/).map((item) => item.trim()).filter(Boolean)),
    data_iscrizione: asText(row.data_iscrizione),
    data_udienza: asText(row.data_udienza),
    ultima_attivita: asText(row.data_udienza || row.data_iscrizione || row.ultima_attivita),
    servizio_pst: asText(row.servizio_pst),
    registro_portale: asText(row.registro_portale || row.tipo_registro),
    tabella_ministeriale: asText(row.tabella_ministeriale),
    payload: row,
  }
  return {
    id: asText(raw.id_fascicolo || raw.external_id || numero, `pst-${index}`),
    title: numero && anno ? `RG ${numero}/${anno}` : asText(row.title || row.titolo, `Fascicolo ${index + 1}`),
    subtitle: [nomeUfficio, raw.parti[0], raw.controparti[0]].filter(Boolean).join(' - ') || 'Risultato dal canale autorizzato',
    badge: asText(raw.stato || raw.procedimento, 'Fascicolo'),
    meta: italianDate(raw.ultima_attivita),
    raw,
  }
}

function previewCount(preview: JsonRecord, key: string): number {
  const counts = asRecord(preview.counts)
  const counted = asNumber(counts[key])
  if (key === 'documenti') {
    const docs = pstPreviewDocuments(preview)
    if (docs.length) return docs.length
  }
  if (key === 'eventi') {
    const timelineRows = previewEvents(preview)
    if (timelineRows.length) return Math.max(counted, timelineRows.length)
  }
  if (counted) return counted
  const value = preview[key]
  if (Array.isArray(value)) return value.length
  if (isRecord(value)) return Object.keys(value).length
  return 0
}

function previewIdentity(preview: JsonRecord): JsonRecord {
  return asRecord(preview.identity || preview.fascicolo || preview.procedimento || preview.ricorso || preview.controversia)
}

function rawPreviewDocumentTitle(row: JsonRecord): string {
  return asText(row.nome || row.nome_documento || row.nome_file_originale || row.filename || row.name)
}

function pstPreviewDocumentIsDownloadable(row: JsonRecord, index: number): boolean {
  const identifiers = pstDocumentIdentifierValues(row)
  if (!identifiers.length) return false
  const title = rawPreviewDocumentTitle(row)
  const type = asText(row.tipo_atto || row.tipo)
  const date = asText(row.data_deposito || row.data_documento || row.data)
  const searchable = normaliseSearch([title, type].filter(Boolean).join(' '))
  if (/\.(pdf|p7m|xml|eml|msg|docx?|rtf|txt)$/i.test(title)) return true
  if (type && normaliseSearch(type) !== 'documento' && (date || identifiers.some((id) => /\d{4,}/.test(id)))) return true
  if (date && title && !/^[A-ZÀ-Ý' -]{2,42}$/.test(title)) return true
  return /\b(citazione|sentenza|verbale|ordinanza|decreto|scritti|note|produzione|intimazione|consegna)\b/.test(searchable)
}

function pstPreviewDocumentContentKey(row: JsonRecord, index: number): string {
  const rawTitle = rawPreviewDocumentTitle(row) || previewDocumentTitle(row, index)
  const title = normaliseSearch(rawTitle)
  if (!title || /^documento(\s+\d+)?$/.test(title)) return ''
  const specificTitle = /\.(pdf|p7m|xml|eml|msg|docx?|rtf|txt)$/i.test(rawTitle) || title.length > 8
  if (!specificTitle) return ''
  const date = asText(row.data_documento || row.data_deposito || row.data)
  const type = normaliseSearch(asText(row.tipo_atto || row.tipo))
  const sender = normaliseSearch(asText(row.mittente || row.depositante))
  const parent = normaliseSearch(asText(row.id_documento_padre || row.parent_id_documento || row.parent_nome))
  const role = row.is_allegato || parent ? 'allegato' : 'principale'
  return [title, date, type, sender, parent, role].filter(Boolean).join('::')
}

function pstPreviewDocuments(preview: JsonRecord): JsonRecord[] {
  const flatten = (rows: JsonRecord[], parent?: JsonRecord): JsonRecord[] => rows.flatMap((row) => {
    const current = parent && !asText(row.parent_id_documento || row.id_documento_padre)
      ? {
          ...row,
          parent_id_documento: asText(parent.id_documento || parent.id_cat || parent.id_reperto),
          id_documento_padre: asText(parent.id_documento || parent.id_cat || parent.id_reperto),
          parent_nome: asText(parent.nome || parent.nome_documento),
          is_allegato: true,
        }
      : row
    const children = [
      ...asList(row.allegati).map(asRecord),
      ...asList(row.attachments).map(asRecord),
      ...asList(row.children).map(asRecord),
      ...asList(row.documenti_collegati).map(asRecord),
      ...asList(row.docs_secondari).map(asRecord),
      ...asList(row.docsSecondari).map(asRecord),
    ]
    return children.length ? [current, ...flatten(children, current)] : [current]
  })
  const keepDownloadable = (rows: JsonRecord[]) => rows.filter((row, index) => pstPreviewDocumentIsDownloadable(row, index))
  const snapshot = asRecord(preview.snapshot)
  const mergedRows: JsonRecord[] = []
  const seenIdentity = new Set<string>()
  const seenContent = new Set<string>()
  const appendRows = (rows: JsonRecord[]) => {
    for (const row of rows) {
      const ids = pstDocumentIdentifierValues(row).join('|')
      const identityKey = [
        ids,
        normaliseSearch(rawPreviewDocumentTitle(row)),
        asText(row.data_documento || row.data_deposito || row.data),
        asText(row.id_deposito || row.id_deposito_esterno || row.id_deposito_pct),
      ].filter(Boolean).join('::')
      const contentKey = pstPreviewDocumentContentKey(row, mergedRows.length)
      if ((identityKey && seenIdentity.has(identityKey)) || (contentKey && seenContent.has(contentKey))) continue
      if (identityKey) seenIdentity.add(identityKey)
      if (contentKey) seenContent.add(contentKey)
      mergedRows.push(row)
    }
  }
  appendRows(flatten(asList(preview.documenti || preview.documents || preview.catalogo).map(asRecord)))
  appendRows(flatten(asList(snapshot.catalogo || snapshot.documenti || snapshot.documents).map(asRecord)))
  appendRows(asList(preview.depositi).map(asRecord).flatMap((deposito) => {
    const docs = flatten(asList(deposito.documenti).map(asRecord))
    return docs.map((documento) => ({
      ...documento,
      id_deposito_pct: asText(documento.id_deposito_pct || deposito.id_deposito_pct),
      id_deposito_esterno: asText(documento.id_deposito_esterno || deposito.id_deposito_esterno || deposito.id_deposito),
      tipo_atto: asText(documento.tipo_atto || deposito.tipo_atto),
      data_deposito: asText(documento.data_deposito || deposito.data_deposito),
      mittente: asText(documento.mittente || deposito.mittente),
    }))
  }))
  return keepDownloadable(mergedRows)
}

function previewPersonName(item: unknown): string {
  if (!isRecord(item)) return asText(item)
  const nested = item.parte || item.soggetto || item.anagrafica
  const cognome = asText(item.cognome || item.cognome_persona)
  const nome = asText(item.nome_persona || item.nome_proprio)
  if (cognome && nome) return `${cognome} ${nome}`
  const direct = asText(
    item.nominativo
    || item.nome
    || item.denominazione
    || item.ragione_sociale
    || item.name
    || item.label,
  )
  if (direct) return direct
  return isRecord(nested) ? previewPersonName(nested) : ''
}

function previewPeople(preview: JsonRecord): string[] {
  const values: string[] = []
  const seen = new Set<string>()
  const append = (value: unknown) => {
    const text = asText(value)
    const key = normaliseSearch(text)
    if (text && !seen.has(key)) {
      seen.add(key)
      values.push(text)
    }
  }
  const identity = previewIdentity(preview)
  const payload = asRecord(preview.payload)
  const snapshot = asRecord(preview.snapshot)
  const snapshotIdentity = asRecord(snapshot.fascicolo || snapshot.identity || snapshot.procedimento || snapshot.ricorso || snapshot.controversia)
  const collect = (source: unknown) => {
    const rows = Array.isArray(source) ? source : (isRecord(source) ? Object.values(source) : [])
    rows.forEach((item) => append(previewPersonName(item)))
  }
  ;[
    preview.parti,
    preview.controparti,
    preview.parti_dettaglio,
    preview.anagrafiche,
    identity.parti,
    identity.controparti,
    identity.parti_dettaglio,
    identity.anagrafiche,
    payload.parti,
    payload.controparti,
    payload.parti_dettaglio,
    snapshot.parti,
    snapshot.controparti,
    snapshot.parti_dettaglio,
    snapshotIdentity.parti,
    snapshotIdentity.controparti,
    snapshotIdentity.parti_dettaglio,
  ].forEach(collect)
  return values
}

function previewPartyMetric(preview: JsonRecord, parties: string[]): number {
  return parties.length || previewCount(preview, 'parti')
}

function previewPartyCountLabel(preview: JsonRecord, parties: string[]): string {
  const rawRows = previewCount(preview, 'parti')
  const uniqueNames = parties.length
  if (!uniqueNames && rawRows) return 'Righe PST rilevate'
  if (!uniqueNames) return 'Nessuna parte indicata'
  if (rawRows > uniqueNames) return `${uniqueNames} nominativi unici, ${rawRows} righe PST`
  return `${uniqueNames} nominativi visualizzati`
}

function previewEvents(preview: JsonRecord): JsonRecord[] {
  const rows = [
    ...asList(preview.eventi).map(asRecord),
    ...asList(preview.udienze).map(asRecord),
    ...asList(preview.comunicazioni).map(asRecord),
    ...asList(preview.istanze).map(asRecord),
    ...asList(preview.depositi_telematici).map(asRecord),
  ]
  const seen = new Set<string>()
  return rows.filter((row) => {
    const key = [
      asText(row.label || row.tipo || row.tipo_atto || row.oggetto),
      asText(row.data || row.data_evento || row.data_udienza || row.data_deposito),
      asText(row.id || row.evento_uid || row.udienza_uid),
    ].join('|')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function previewDocumentTitle(row: JsonRecord, index: number): string {
  return asText(
    row.nome
    || row.nome_documento
    || row.nome_file_originale
    || row.filename
    || row.name,
    `Documento ${index + 1}`,
  )
}

function previewDocumentMeta(row: JsonRecord): string {
  return [
    asText(row.tipo_atto || row.tipo),
    italianDate(row.data_deposito || row.data_documento || row.data),
    asText(row.mittente),
  ].filter(Boolean).join(' - ')
}

const scadenziarioDocumentHints: Array<[string, string[]]> = [
  ['Fissazione termine', ['fissazione', 'termine']],
  ['Fissazione udienza', ['fissazione', 'udienza']],
  ['Sostituzione udienza', ['sostituzione', 'udienza']],
  ['Rinvio udienza', ['rinvio', 'udienza']],
  ['Trattazione scritta', ['trattazione', 'scritta']],
  ['Termine note', ['termine', 'note']],
  ['Verbale udienza', ['verbale', 'udienza']],
  ['Comunicazione udienza', ['comunicazione', 'udienza']],
  ['Ordinanza con termini', ['ordinanza', 'termine']],
  ['Decreto con termini', ['decreto', 'termine']],
  ['Provvedimento con termini', ['provvedimento', 'termine']],
]

function compactDeadlineText(value: string): string {
  return normaliseSearch(value).replace(/[^a-z0-9]+/g, '')
}

function deadlineDocumentReason(row: JsonRecord, index: number): string {
  const searchable = [
    previewDocumentTitle(row, index),
    asText(row.tipo_atto || row.tipo),
    asText(row.descrizione || row.oggetto),
  ].join(' ')
  const compact = compactDeadlineText(searchable)
  const match = scadenziarioDocumentHints.find(([, tokens]) => (
    tokens.every((token) => compact.includes(compactDeadlineText(token)))
  ))
  return match ? match[0] : ''
}

function previewDeadlineSourceDocuments(preview: JsonRecord): JsonRecord[] {
  const direct = asList(preview.documenti_scadenziario || preview.documentiScadenziario).map(asRecord)
  if (direct.length) return direct
  const identity = previewIdentity(preview)
  if (asText(identity.data_udienza) || asList(preview.udienze).length) return []
  return pstPreviewDocuments(preview)
    .map((row, index) => ({ ...row, motivo: deadlineDocumentReason(row, index) }))
    .filter((row) => asText(row.motivo))
}

function previewStructuredHearingLabel(preview: JsonRecord): string {
  const identity = previewIdentity(preview)
  const identityDate = italianDate(identity.data_udienza)
  if (identityDate) return identityDate
  const structured = asList(preview.udienze).map(asRecord).find((row) => italianDate(row.data || row.data_udienza))
  return structured ? italianDate(structured.data || structured.data_udienza) : ''
}

function previewIdentityRows(identity: JsonRecord, selection: AcquisitionResult | null): Array<[string, string]> {
  return [
    ['R.G.', asText(identity.numero_rg || identity.rg || identity.numero || selection?.title, 'n.d.')],
    ['Ufficio', asText(identity.ufficio_nome || identity.ufficio || identity.tribunale || identity.court, 'Ufficio non indicato')],
    ['Procedimento', asText(identity.procedimento || identity.ruolo || identity.tipo_registro || identity.tipo, 'n.d.')],
    ['Stato', asText(identity.stato || identity.fase, 'n.d.')],
    ['Sezione', asText(identity.sezione || identity.sub_procedimento, 'n.d.')],
    ['Oggetto', asText(identity.oggetto || identity.materia || identity.reato, 'n.d.')],
    ['Iscrizione', italianDate(identity.data_iscrizione || identity.data_deposito)],
    ['Ultima attività', italianDate(identity.ultima_attivita || identity.data_udienza)],
  ]
}

function formatDownloadFailure(row: JsonRecord, index: number): string {
  const name = asText(row.nome_documento || row.nome || row.id_documento, `Documento ${index + 1}`)
  const detail = asText(row.errore || row.message, 'non scaricato')
  return `${name}: ${detail}`
}

function pstDocumentIdentifierValues(item: JsonRecord): string[] {
  const values: string[] = []
  const weakValues: string[] = []
  const appendTo = (target: string[], value: unknown) => {
    const text = asText(value)
    if (!text || text.startsWith('#') || target.includes(text)) return
    target.push(text)
  }
  ;[
    item.id_reperto,
    item.idReperto,
    item.idRaccoglitore,
    item.id_raccoglitore,
    item.msg_id,
    item.msgId,
    item.msgid,
  ].forEach((value) => appendTo(weakValues, value))
  const appendStrong = (value: unknown) => {
    const text = asText(value)
    if (!text || weakValues.includes(text)) return
    appendTo(values, text)
  }
  asList(item.id_documento_candidates).forEach(appendStrong)
  ;[
    item.id_documento,
    item.id_documento_portale,
    item.idDocumento,
    item.idDoc,
    item.id_cat,
    item.idCat,
    item.id_repeatto,
    item.idRepeatto,
    item.idRepeatTo,
    item.numero_documento,
    item.numeroDocumento,
    item.id_doc_mittente,
    item.idDocMittente,
  ].forEach(appendStrong)
  return values.length ? values : weakValues
}

function pstDocumentSelectionKey(item: JsonRecord, index: number): string {
  const identifiers = pstDocumentIdentifierValues(item).join('|')
  const deposito = asText(item.id_deposito_pct || item.id_deposito_esterno || item.id_deposito)
  const title = normaliseSearch(previewDocumentTitle(item, index))
  const date = asText(item.data_documento || item.data_deposito || item.data)
  const type = normaliseSearch(asText(item.tipo_atto || item.tipo))
  return [identifiers, deposito, title, date, type, String(index)].filter(Boolean).join('::')
}

function pstDocumentsMatch(left: JsonRecord, right: JsonRecord): boolean {
  const leftIds = new Set(pstDocumentIdentifierValues(left))
  const rightIds = pstDocumentIdentifierValues(right)
  if (rightIds.some((id) => leftIds.has(id))) return true
  const leftName = normaliseSearch(previewDocumentTitle(left, 0))
  const rightName = normaliseSearch(previewDocumentTitle(right, 0))
  if (!leftName || leftName !== rightName) return false
  const leftDeposit = asText(left.id_deposito_pct || left.id_deposito_esterno || left.id_deposito)
  const rightDeposit = asText(right.id_deposito_pct || right.id_deposito_esterno || right.id_deposito)
  const leftDate = asText(left.data_documento || left.data_deposito || left.data)
  const rightDate = asText(right.data_documento || right.data_deposito || right.data)
  return (!leftDeposit || !rightDeposit || leftDeposit === rightDeposit)
    && (!leftDate || !rightDate || leftDate === rightDate)
}

function acquisitionFilePstRecord(file: AcquisitionFile): JsonRecord {
  return {
    nome: file.nome,
    nome_documento: file.nome,
    nome_file_originale: file.nome_file_originale,
    filename: file.nome_file_originale || file.nome,
    data_documento: file.data_documento,
    data_deposito: file.data_documento,
    id_documento: file.id_documento_portale,
    id_documento_portale: file.id_documento_portale,
    id_deposito: file.id_deposito_esterno,
    id_deposito_esterno: file.id_deposito_esterno,
    id_deposito_pct: file.id_deposito_pct,
    tipo_atto: file.tipo_atto,
    tipo: file.tipo,
    id_cat: file.id_cat,
    idCat: file.id_cat,
    id_repeatto: file.id_repeatto,
    idRepeatto: file.id_repeatto,
    id_reperto: asText(file.id_reperto),
    idReperto: asText(file.id_reperto),
    msg_id: file.msg_id,
    msgId: file.msg_id,
    numero_documento: file.numero_documento,
    numeroDocumento: file.numero_documento,
    id_doc_mittente: file.id_doc_mittente,
    idDocMittente: file.id_doc_mittente,
  }
}

function filterDownloadedFilesForSelectedPstDocuments(files: AcquisitionFile[], selectedDocuments: JsonRecord[]): AcquisitionFile[] {
  if (!selectedDocuments.length) return files
  return files.filter((file) => selectedDocuments.some((doc) => pstDocumentsMatch(acquisitionFilePstRecord(file), doc)))
}

function missingPstDocumentsForDownload(selectedDocuments: JsonRecord[], files: AcquisitionFile[]): JsonRecord[] {
  if (!selectedDocuments.length) return []
  return selectedDocuments.filter((doc) => !files.some((file) => pstDocumentsMatch(acquisitionFilePstRecord(file), doc)))
}

function pstDocumentIsProvision(row: JsonRecord): boolean {
  return /sentenza|ordinanza|decreto|provvedimento/i.test(asText(row.tipo_atto || row.tipo))
}

function filterPreviewForSelectedDocuments(preview: JsonRecord, selectedDocuments: JsonRecord[]): JsonRecord {
  if (!selectedDocuments.length) return preview
  const allDocuments = pstPreviewDocuments(preview)
  if (!allDocuments.length || selectedDocuments.length >= allDocuments.length) return preview
  const selected = selectedDocuments.map(asRecord)
  const documenti = allDocuments.filter((doc) => selected.some((candidate) => pstDocumentsMatch(doc, candidate)))
  const depositi: JsonRecord[] = []
  asList(preview.depositi).map(asRecord).forEach((deposito) => {
    const depositoDocumenti = asList(deposito.documenti)
      .map(asRecord)
      .filter((doc) => selected.some((candidate) => pstDocumentsMatch(doc, candidate)))
    if (depositoDocumenti.length) {
      depositi.push({ ...deposito, documenti: depositoDocumenti })
    }
  })
  const documentiScadenziario = previewDeadlineSourceDocuments({ ...preview, documenti, documenti_scadenziario: [] })
  return {
    ...preview,
    documenti,
    documenti_scadenziario: documentiScadenziario,
    depositi,
    counts: {
      ...asRecord(preview.counts),
      documenti: documenti.length,
      provvedimenti: documenti.filter(pstDocumentIsProvision).length,
      depositi: depositi.length,
      fonti_scadenziario: documentiScadenziario.length,
    },
  }
}

function pstDownloadDocumentPayload(item: JsonRecord, original: boolean): JsonRecord {
  return {
    id_documento: asText(item.id_documento || item.id_documento_portale),
    nome_documento: asText(item.nome || item.nome_documento || item.nome_file_originale),
    id_cat: asText(item.id_cat),
    id_repeatto: asText(item.id_repeatto),
    id_reperto: asText(item.id_reperto),
    msg_id: asText(item.msg_id),
    numero_documento: asText(item.numero_documento),
    id_doc_mittente: asText(item.id_doc_mittente),
    id_documento_candidates: pstDocumentIdentifierValues(item),
    data_documento: asText(item.data_documento || item.data_deposito),
    id_deposito_esterno: asText(item.id_deposito_esterno || item.id_deposito),
    id_deposito_pct: asText(item.id_deposito_pct),
    tipo_atto: asText(item.tipo_atto),
    tipo: asText(item.tipo),
    id_documento_padre: asText(item.id_documento_padre || item.parent_id_documento),
    parent_nome: asText(item.parent_nome),
    is_allegato: Boolean(item.is_allegato),
    original,
  }
}

function issueRows(analysis: JsonRecord, key: string): JsonRecord[] {
  const direct = asList(analysis[key]).map(asRecord)
  if (direct.length) return direct
  const grouped = asRecord(analysis.issues)
  return asList(grouped[key]).map(asRecord)
}

function importSummary(result: JsonRecord): JsonRecord {
  const summary = asRecord(result.summary)
  if (Object.keys(summary).length) return summary
  const nested = asRecord(asRecord(result.result).summary)
  if (Object.keys(nested).length) return nested
  return asRecord(result.result || result)
}

function fileDate(value: number): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toISOString().slice(0, 10)
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Impossibile leggere il file ${file.name}`))
    reader.onload = () => resolve(String(reader.result || ''))
    reader.readAsDataURL(file)
  })
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Impossibile leggere il file ${file.name}`))
    reader.onload = () => resolve(String(reader.result || ''))
    reader.readAsText(file)
  })
}

async function collectAcquisitionFiles(files: FileList | null, originalMode: boolean): Promise<AcquisitionFile[]> {
  const rows = Array.from(files || []).filter((file) => file.name)
  const collected: AcquisitionFile[] = []
  for (const file of rows) {
    const dataUrl = await readFileAsDataUrl(file)
    const [, content = dataUrl] = dataUrl.split(',', 2)
    let payloadJson: JsonRecord | null = null
    if (/\.json$/i.test(file.name)) {
      const parsed = JSON.parse(await readFileAsText(file)) as unknown
      payloadJson = isRecord(parsed) ? parsed : null
    }
    const path = asText((file as File & { webkitRelativePath?: string }).webkitRelativePath)
    collected.push({
      nome: file.name,
      nome_file_originale: file.name,
      contenuto_b64: content,
      payload_json: payloadJson,
      origine: path ? `upload-cartella:${path}` : `upload:${file.name}`,
      data_documento: fileDate(file.lastModified),
      content_type: asText(file.type),
      id_documento_portale: '',
      id_deposito_esterno: '',
      id_deposito_pct: '',
      tipo_atto: '',
      tipo: '',
      original_documento_portale: originalMode,
      modalita_documento_portale: originalMode ? 'originale' : 'copia',
    })
  }
  return collected
}

function assistantFilesToAcquisitionFiles(rows: unknown[], originalMode: boolean): AcquisitionFile[] {
  const collected: AcquisitionFile[] = []
  for (const value of rows) {
    const row = asRecord(value)
    const filename = asText(row.filename || row.name || row.nome || row.nome_file || row.nomeFile || row.nome_documento || row.nomeDocumento)
    const content = asText(row.content_base64 || row.base64 || row.contenuto_b64 || row.contenuto_base64 || row.contenutoBase64 || row.file_base64 || row.fileBase64 || row.bytes_base64 || row.bytesBase64)
    if (!filename || !content) continue
    collected.push({
      nome: filename,
      nome_file_originale: asText(row.nome_file_originale || row.nomeFileOriginale || filename),
      contenuto_b64: content,
      payload_json: null,
      origine: asText(row.source || row.local_temp_ref, `sessione-assistita:${filename}`),
      data_documento: asText(row.detected_at).slice(0, 10),
      content_type: asText(row.content_type),
      id_documento_portale: asText(row.id_documento_portale || row.id_documento || row.idDocumento || row.idDoc),
      id_deposito_esterno: asText(row.id_deposito_esterno || row.id_deposito || row.idDeposito),
      id_deposito_pct: asText(row.id_deposito_pct),
      tipo_atto: asText(row.tipo_atto),
      tipo: asText(row.tipo),
      id_cat: asText(row.id_cat || row.idCat),
      id_repeatto: asText(row.id_repeatto || row.idRepeatto || row.idRepeatTo),
      id_reperto: asText(row.id_reperto || row.idReperto),
      msg_id: asText(row.msg_id || row.msgId || row.msgid),
      numero_documento: asText(row.numero_documento || row.numeroDocumento),
      id_doc_mittente: asText(row.id_doc_mittente || row.idDocMittente),
      id_documento_padre: asText(row.id_documento_padre || row.parent_id_documento),
      parent_nome: asText(row.parent_nome),
      is_allegato: Boolean(row.is_allegato),
      original_documento_portale: originalMode,
      modalita_documento_portale: originalMode ? 'originale' : 'copia',
    })
  }
  return collected
}

function signerFilesToAcquisitionFiles(rows: unknown[], originalMode: boolean): AcquisitionFile[] {
  const collected: AcquisitionFile[] = []
  for (const value of rows) {
    const row = asRecord(value)
    const filename = asText(row.nome || row.filename || row.name || row.nome_documento || row.nomeDocumento || row.nome_file || row.nomeFile || row.nome_file_originale || row.nomeFileOriginale)
    const content = asText(row.contenuto_b64 || row.content_base64 || row.base64 || row.contenuto_base64 || row.contenutoBase64 || row.file_base64 || row.fileBase64 || row.bytes_base64 || row.bytesBase64)
    if (!filename || !content) continue
    collected.push({
      nome: filename,
      nome_file_originale: asText(row.nome_file_originale || row.nomeFileOriginale || row.filename || row.name || row.nome_file || filename),
      contenuto_b64: content,
      payload_json: null,
      origine: asText(row.origine || row.source, `pst:${filename}`),
      data_documento: asText(row.data_documento || row.data_deposito || row.detected_at).slice(0, 10),
      content_type: asText(row.content_type),
      id_documento_portale: asText(row.id_documento_portale || row.id_documento || row.idDocumento || row.idDoc),
      id_deposito_esterno: asText(row.id_deposito_esterno || row.id_deposito || row.idDeposito),
      id_deposito_pct: asText(row.id_deposito_pct),
      tipo_atto: asText(row.tipo_atto),
      tipo: asText(row.tipo),
      id_cat: asText(row.id_cat || row.idCat),
      id_repeatto: asText(row.id_repeatto || row.idRepeatto || row.idRepeatTo),
      id_reperto: asText(row.id_reperto || row.idReperto),
      msg_id: asText(row.msg_id || row.msgId || row.msgid),
      numero_documento: asText(row.numero_documento || row.numeroDocumento),
      id_doc_mittente: asText(row.id_doc_mittente || row.idDocMittente),
      id_documento_padre: asText(row.id_documento_padre || row.parent_id_documento),
      parent_nome: asText(row.parent_nome),
      is_allegato: Boolean(row.is_allegato),
      original_documento_portale: 'original_documento_portale' in row ? Boolean(row.original_documento_portale) : originalMode,
      modalita_documento_portale: asText(row.modalita_documento_portale) === 'originale' || ('original_documento_portale' in row ? Boolean(row.original_documento_portale) : originalMode) ? 'originale' : 'copia',
    })
  }
  return collected
}

function acquisitionFileMergeKey(file: AcquisitionFile): string {
  const portalIds = [
    file.id_cat,
    file.id_documento_portale,
    file.id_deposito_pct,
    file.id_deposito_esterno,
    file.id_repeatto,
    file.id_reperto,
    file.msg_id,
    file.numero_documento,
    file.id_doc_mittente,
  ].map((value) => asText(value)).filter(Boolean).join('|')
  const name = file.nome_file_originale.toLowerCase() || file.nome.toLowerCase()
  const metadata = [
    file.data_documento,
    file.tipo_atto,
    file.tipo,
    file.id_documento_padre,
    file.parent_nome,
    file.is_allegato ? 'allegato' : '',
  ].map((value) => asText(value)).filter(Boolean).join('|')
  if (portalIds) return `pst:${portalIds}::${name}::${metadata}`
  return `file:${name}::${file.contenuto_b64.length}::${file.contenuto_b64.slice(0, 96)}`
}

function mergeAcquisitionFiles(current: AcquisitionFile[], incoming: AcquisitionFile[]): AcquisitionFile[] {
  const merged = [...current]
  const seen = new Set(current.map(acquisitionFileMergeKey))
  for (const file of incoming) {
    const key = acquisitionFileMergeKey(file)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(file)
  }
  return merged
}

function authorisedPayload(files: AcquisitionFile[]): JsonRecord | null {
  for (const file of files) {
    const payload = file.payload_json
    if (!payload) continue
    const nested = payload.payload || payload.raw_payload
    if (isRecord(nested)) return nested
    if (payload.selection || payload.preview || payload.fascicolo || payload.procedimento || payload.ricorso || payload.controversia) {
      return payload
    }
  }
  return null
}

function AcquisitionWizard({
  surfaceId,
  data,
  localEvents = [],
}:{
  surfaceId: TelematicoSurfaceId
  data: TelematicoSurfaceData
  localEvents?: AcquisitionHistoryEvent[]
}) {
  const portal = portalFromSurface(surfaceId, data)
  const visible = isAcquisitionPath(portal)
  const portalUsesOfficialAssistant = isOfficialAssistantPortal(portal)
  const [step, setStep] = useState(() => (portalUsesOfficialAssistant ? 1 : 2))
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState<JsonRecord>({})
  const targetDocument = useMemo(() => acquisitionTargetDocument(), [])
  const targetDocumentPayload = useMemo(() => acquisitionTargetPayload(targetDocument), [targetDocument])
  const [query, setQuery] = useState<AcquisitionQuery>(() => acquisitionInitialQuery())
  const [results, setResults] = useState<AcquisitionResult[]>([])
  const [selection, setSelection] = useState<AcquisitionResult | null>(null)
  const [preview, setPreview] = useState<JsonRecord>({})
  const [analysis, setAnalysis] = useState<JsonRecord>({})
  const [files, setFiles] = useState<AcquisitionFile[]>([])
  const [selectedDocumentKeys, setSelectedDocumentKeys] = useState<string[]>([])
  const [importResult, setImportResult] = useState<JsonRecord>({})
  const [importProgress, setImportProgress] = useState<ImportProgress>({
    active: false,
    phase: '',
    current: '',
    completed: 0,
    total: 0,
    failures: [],
  })
  const [options, setOptions] = useState<AcquisitionOptions>({
    scarica_originale_portale: portal !== 'pst',
    mantieni_albero_originale: false,
    importa_documenti: true,
    importa_eventi: true,
    importa_scadenze: true,
    importa_parti: true,
  })
  const initialTargetFascicoloId = useMemo(() => acquisitionInitialFascicoloId(), [])
  const [mapping, setMapping] = useState<AcquisitionMapping>({
    mode: acquisitionInitialMappingMode(initialTargetFascicoloId),
    target_fascicolo_id: initialTargetFascicoloId,
    procedimento: '',
    materia: '',
    grado: '',
  })
  const [officeTypeFilter, setOfficeTypeFilter] = useState('tutti')
  const localSignerDesktopSupported = useMemo(() => isDesktopLocalSignerHost(), [])
  const [localSigner, setLocalSigner] = useState<BrowserLocalSignerStatus>({
    checked: false,
    checking: false,
    ok: false,
    outdated: false,
    unsupported: !isDesktopLocalSignerHost(),
    version: '',
    tokenLabel: '',
    message: isDesktopLocalSignerHost()
      ? 'Controllo Local Signer non ancora eseguito su questo PC.'
      : 'Local Signer disponibile solo su PC desktop Windows, macOS o Linux. Da mobile o tablet il controllo non viene eseguito.',
  })
  const [pstCert, setPstCert] = useState<PstCertificate | null>(() => loadPstCertificate())
  const [pstSession, setPstSession] = useState<PstSession | null>(() => loadPstSession())
  const [assistantSession, setAssistantSession] = useState<AssistantSession | null>(null)
  const [assistantMonitoring, setAssistantMonitoring] = useState(false)
  const assistantTimerRef = useRef<number | null>(null)
  const autoPstTestStartedRef = useRef(false)
  const mappingTargetOptions = useMemo(() => {
    const rows: Array<{ id: string; title: string }> = []
    const add = (id: string, title: string) => {
      const cleanId = asText(id)
      if (!cleanId || rows.some((item) => item.id === cleanId)) return
      rows.push({ id: cleanId, title: asText(title, 'Pratica locale selezionata') })
    }
    add(initialTargetFascicoloId, 'Pratica locale selezionata')
    data.recentCases.forEach((item) => {
      add(item.practiceId || item.id, item.title)
    })
    return rows
  }, [data.recentCases, initialTargetFascicoloId])
  const previewDocuments = useMemo(() => pstPreviewDocuments(preview), [preview])
  const structuredHearingLabel = useMemo(() => previewStructuredHearingLabel(preview), [preview])
  const deadlineSourceDocuments = useMemo(() => previewDeadlineSourceDocuments(preview), [preview])
  const previewDocumentKeys = useMemo(
    () => previewDocuments.map((doc, index) => pstDocumentSelectionKey(doc, index)),
    [previewDocuments],
  )
  const previewDocumentKeySignature = previewDocumentKeys.join('\u001f')
  useEffect(() => {
    setSelectedDocumentKeys((current) => {
      if (!previewDocumentKeys.length) return current.length ? [] : current
      const available = new Set(previewDocumentKeys)
      const kept = current.filter((key) => available.has(key))
      if (kept.length) return kept
      return previewDocumentKeys
    })
  }, [previewDocumentKeySignature])
  const selectedDocumentKeySet = useMemo(() => new Set(selectedDocumentKeys), [selectedDocumentKeys])
  const selectedPreviewDocuments = useMemo(
    () => previewDocuments.filter((doc, index) => selectedDocumentKeySet.has(pstDocumentSelectionKey(doc, index))),
    [previewDocuments, selectedDocumentKeySet],
  )
  const downloadedPstDocumentCount = useMemo(
    () => files.filter((file) => (
      !file.payload_json
      && (
        asText(file.origine).startsWith('pst:')
        || Boolean(file.id_documento_portale)
        || Boolean(file.id_cat)
        || Boolean(file.id_repeatto)
        || Boolean(file.msg_id)
      )
    )).length,
    [files],
  )
  const downloadedPstDocumentKeySet = useMemo(() => {
    const downloaded = files
      .filter((file) => !file.payload_json)
      .map(acquisitionFilePstRecord)
    const keys = new Set<string>()
    previewDocuments.forEach((doc, index) => {
      if (downloaded.some((file) => pstDocumentsMatch(file, doc))) {
        keys.add(pstDocumentSelectionKey(doc, index))
      }
    })
    return keys
  }, [files, previewDocuments])

  useEffect(() => {
    if (!visible || !portal) return
    setStep(portalUsesOfficialAssistant ? 1 : 2)
  }, [portal, portalUsesOfficialAssistant, visible])

  useEffect(() => {
    if (!visible || !portal) return
    let active = true
    portalJson(portal, 'status')
      .then((payload) => {
        if (!active) return
        setStatus(asRecord(payload.status))
      })
      .catch((error: unknown) => {
        if (active) setMessage(asText(error, 'Stato canale non disponibile.'))
      })
    return () => { active = false }
  }, [portal, visible])

  const checkLocalSigner = async (tryStart = false): Promise<BrowserLocalSignerStatus> => {
    if (!localSignerDesktopSupported) {
      const next = {
        checked: true,
        checking: false,
        ok: false,
        outdated: false,
        unsupported: true,
        version: '',
        tokenLabel: '',
        message: 'Local Signer disponibile solo su PC desktop Windows, macOS o Linux. Da mobile o tablet il controllo non viene eseguito.',
      }
      setLocalSigner(next)
      return next
    }
    if (tryStart) requestLocalSignerStart()
    setLocalSigner((current) => ({
      ...current,
      checked: true,
      checking: true,
      message: tryStart ? 'Avvio Local Signer e verifico il servizio locale...' : 'Verifica Local Signer in corso...',
    }))
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 3500)
    try {
      const response = await fetch(`${data.localSigner.browserUrl}/ping?light=1`, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
      })
      const payload = asRecord(await response.json().catch(() => ({})))
      const version = asText(payload.versione || payload.version || payload.local_signer_version)
      const tokenList = asList(payload.token || payload.tokens)
      const firstToken = asRecord(tokenList[0])
      const tokenLabel = asText(firstToken.label || firstToken.manufacturer || firstToken.subject)
      const outdated = Boolean(data.localSigner.latestVersion && version && compareVersions(version, data.localSigner.latestVersion) < 0)
      const reachable = response.ok && Boolean(payload.ok !== false)
      const next = {
        checked: true,
        checking: false,
        ok: reachable,
        outdated,
        unsupported: false,
        version,
        tokenLabel,
        message: outdated && reachable
          ? `Local Signer rilevato su questo PC, ma serve la versione ${data.localSigner.latestVersion}. Aggiorno prima di avviare la ricerca.`
          : reachable
            ? 'Local Signer rilevato su questo PC. La ricerca può usare il canale locale autorizzato.'
            : asText(payload.messaggio || payload.error, 'Local Signer raggiunto ma non pronto.'),
      }
      setLocalSigner(next)
      return next
    } catch {
      const next = {
        checked: true,
        checking: false,
        ok: false,
        outdated: false,
        unsupported: false,
        version: '',
        tokenLabel: '',
        message: 'Local Signer non rilevato su questo PC. Avvialo o installa il pacchetto aggiornato, poi ripeti la verifica.',
      }
      setLocalSigner(next)
      return next
    } finally {
      window.clearTimeout(timer)
    }
  }

  const updateLocalSignerAutomatically = async (): Promise<BrowserLocalSignerStatus | null> => {
    if (!localSignerDesktopSupported) return null
    setLocalSigner((current) => ({
      ...current,
      checked: true,
      checking: true,
      message: 'Aggiornamento automatico Local Signer avviato. IUSENTRA usa il pacchetto ufficiale e poi ricontrolla il servizio locale.',
    }))
    let updateStarted = false
    try {
      const updatePayload = await localSignerJson('/update', {}, 8000)
      updateStarted = updatePayload.ok !== false
    } catch {
      updateStarted = false
    }
    if (!updateStarted) {
      requestLocalSignerUpdate()
      window.setTimeout(() => requestLocalSignerInstallerDownload(data), 1500)
    }
    for (let attempt = 0; attempt < 70; attempt += 1) {
      await wait(1200)
      const next = await checkLocalSigner(false)
      if (next.ok && !next.outdated) {
        setMessage(`Local Signer aggiornato alla versione ${next.version || data.localSigner.latestVersion}.`)
        return next
      }
    }
    const next = {
      checked: true,
      checking: false,
      ok: Boolean(localSigner.ok),
      outdated: true,
      unsupported: false,
      version: localSigner.version,
      tokenLabel: localSigner.tokenLabel,
      message: 'Aggiornamento automatico non completato. Se Windows non ha autorizzato l’avvio, usa il pacchetto ufficiale e poi verifica di nuovo.',
    }
    setLocalSigner(next)
    return next
  }

  const loadPortalStatus = async (): Promise<JsonRecord> => {
    const payload = await portalJson(portal, 'status')
    const nextStatus = asRecord(payload.status)
    setStatus(nextStatus)
    return nextStatus
  }

  const statusForPstCertificate = async (): Promise<JsonRecord> => {
    if (statusHasPstCertificatePreference(status)) return status
    try {
      const refreshed = await loadPortalStatus()
      return Object.keys(refreshed).length ? refreshed : status
    } catch {
      return status
    }
  }

  const localSignerJson = async (path: string, body?: JsonRecord, timeoutMs = LOCAL_SIGNER_DEFAULT_TIMEOUT_MS): Promise<JsonRecord> => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(`${data.localSigner.browserUrl}${path}`, {
        method: body ? 'POST' : 'GET',
        cache: 'no-store',
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })
      const payload = asRecord(await response.json().catch(() => ({ ok: false, errore: 'Risposta non valida dal Local Signer.' })))
      if (!response.ok || payload.ok === false) {
        throw new Error(asText(payload.errore || payload.error || payload.message, `Local Signer non disponibile (${response.status}).`))
      }
      return payload
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        if (path.includes('/pst/download-documenti-batch')) {
          throw new Error('Scaricamento dal PST ancora in attesa: il portale ufficiale non ha risposto entro il tempo massimo. Il Local Signer era attivo; riprova dalla stessa schermata senza riselezionare il certificato.')
        }
        if (path.includes('/pst/')) {
          throw new Error('Consultazione PST ancora in attesa: il portale ufficiale sta rispondendo lentamente. Il Local Signer era attivo; riprova dalla stessa schermata mantenendo inserito il token.')
        }
        throw new Error('Il servizio locale non ha risposto entro il tempo massimo. Verifica che Local Signer sia avviato sul PC e riprova.')
      }
      throw error
    } finally {
      window.clearTimeout(timer)
    }
  }

  const localSignerDelay = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms))

  const localSignerPstFascicoloSnapshotJob = async (body: JsonRecord, timeoutMs = LOCAL_SIGNER_PST_SEARCH_TIMEOUT_MS): Promise<JsonRecord> => {
    const startedAt = Date.now()
    let jobPayload = await localSignerJson('/pst/fascicolo-snapshot-job', body, LOCAL_SIGNER_PST_STATUS_TIMEOUT_MS)
    const jobId = asText(jobPayload.job_id)
    if (!jobId) throw new Error('Local Signer non ha avviato il lavoro di visualizzazione PST.')

    while (Date.now() - startedAt < timeoutMs) {
      const status = asText(jobPayload.status)
      const phase = asText(jobPayload.phase, 'Visualizzazione fascicolo PST')
      const current = asText(jobPayload.current, 'Lettura scheda ministeriale in corso')
      const elapsed = asNumber(jobPayload.elapsed_seconds)
      setImportProgress((progress) => ({
        ...progress,
        active: status !== 'completed' && status !== 'failed',
        phase,
        current: elapsed ? `${current} · attesa ${Math.round(elapsed)}s` : current,
        completed: Math.max(progress.completed, status === 'completed' ? (progress.total || 3) : 1),
      }))
      if (status === 'completed') {
        const result = asRecord(jobPayload.result)
        if (result.ok === false) throw new Error(asText(result.errore || result.error, 'Visualizzazione PST non completata.'))
        return result
      }
      if (status === 'failed') {
        throw new Error(asText(jobPayload.errore || jobPayload.error, 'Visualizzazione PST non completata dal Local Signer.'))
      }
      await localSignerDelay(2500)
      jobPayload = await localSignerJson(`/pst/jobs/${encodeURIComponent(jobId)}`, undefined, LOCAL_SIGNER_PST_STATUS_TIMEOUT_MS)
    }
    throw new Error('Visualizzazione PST ancora in attesa: il portale ufficiale non ha completato la scheda entro il tempo massimo. Riprova dalla stessa schermata mantenendo inserito il token.')
  }

  const requireLocalSignerBrowserBridge = async () => {
    try {
      await localSignerJson('/ping?light=1', undefined, LOCAL_SIGNER_BROWSER_BRIDGE_TIMEOUT_MS)
    } catch (error: unknown) {
      throw new Error(
        'Local Signer non ha risposto dal browser entro pochi secondi: non apro il PIN e non lascio la ricerca bloccata. ' +
        'Verifica che il servizio locale sia avviato su questo PC, poi premi di nuovo Cerca fascicolo.',
      )
    }
  }

  const signerCertPreferenceQuery = (sourceStatus: JsonRecord = status) => {
    const prefs = asRecord(sourceStatus.cert_preferences)
    const params = new URLSearchParams()
    const autoPref = asText(prefs.auto).toLowerCase()
    if (prefs.auto !== false && autoPref !== '0' && autoPref !== 'false') params.set('auto', '1')
    const preferIssuer = asText(prefs.prefer_issuer)
    const preferSubject = asText(prefs.prefer_subject)
    const preferCf = asText(prefs.prefer_cf || sourceStatus.codice_fiscale_avvocato)
    if (preferIssuer) params.set('prefer_issuer', preferIssuer)
    if (preferSubject) params.set('prefer_subject', preferSubject)
    if (preferCf) params.set('prefer_cf', preferCf)
    const queryString = params.toString()
    return queryString ? `?${queryString}` : ''
  }

  const ensurePstCertificate = async (forceDialog = false): Promise<PstCertificate> => {
    const certificateStatus = await statusForPstCertificate()
    const prefs = asRecord(certificateStatus.cert_preferences)
    if (!forceDialog) {
      const savedCert = pstCert || loadPstCertificate()
      const savedThumbprint = asText(savedCert?.thumbprint)
      if (certificateMatchesPstPreferences(savedCert, prefs, certificateStatus)) {
        if (!pstCert) setPstCert(savedCert)
        return savedCert
      }
      if (savedThumbprint) {
        setPstCert(null)
        storePstCertificate(null)
      }
      try {
        const signerStatus = await localSignerJson(`/ping${signerCertPreferenceQuery(certificateStatus)}`, undefined, LOCAL_SIGNER_PST_STATUS_TIMEOUT_MS)
        const autoCert = coercePstCertificate(signerStatus)
        if (certificateMatchesPstPreferences(autoCert, prefs, certificateStatus)) {
          setPstCert(autoCert)
          storePstCertificate(autoCert)
          return autoCert
        }
      } catch {
        // La selezione esplicita gestira' il messaggio operativo se il servizio locale non risponde.
      }
    }
    const payload = await localSignerJson(`/seleziona-certificato${signerCertPreferenceQuery(certificateStatus)}`, undefined, 120000)
    const cert = coercePstCertificate(payload)
    if (!cert?.thumbprint) throw new Error('Seleziona il certificato di firma sul PC e riprova.')
    setPstCert(cert)
    storePstCertificate(cert)
    return cert
  }

  const pstAttorneyFiscalCode = (cert?: PstCertificate | null) => asText(
    cert?.codiceFiscale || status.codice_fiscale_avvocato || '',
  )

  const pstAttorneyFiscalCodeSource = (cert?: PstCertificate | null) => (
    asText(cert?.codiceFiscale) ? 'certificato' : (asText(status.codice_fiscale_avvocato) ? 'impostazioni_studio' : '')
  )

  const rememberPstSession = (payload: JsonRecord, tribunale: string, cert: PstCertificate): PstSession | null => {
    const sessionId = asText(payload.pst_session_id)
    if (!sessionId) return null
    const ttlSeconds = asNumber(payload.pst_session_ttl_seconds) || 900
    const session = {
      sessionId,
      tribunale: asText(payload.tribunale || tribunale),
      certThumbprint: cert.thumbprint,
      expiresAt: Date.now() + ttlSeconds * 1000,
    }
    setPstSession(session)
    storePstSession(session)
    return session
  }

  const clearPstSession = () => {
    setPstSession(null)
    storePstSession(null)
  }

  const keepPstSession = (session: PstSession | null): PstSession | null => {
    if (!session) return null
    setPstSession(session)
    storePstSession(session)
    return session
  }

  const activePstSessionFor = (tribunale: string, cert: PstCertificate): PstSession | null => {
    const currentSession = isPstSessionActive(pstSession, tribunale, cert) ? pstSession : null
    if (currentSession) return currentSession
    const recoveredSession = (
      coercePstSessionFromPayload(selection?.raw?.pst_session, tribunale, cert)
      || coercePstSessionFromPayload(preview.pst_session, tribunale, cert)
    )
    return keepPstSession(recoveredSession)
  }

  const pstSessionForServer = (session: PstSession, cert: PstCertificate): JsonRecord => ({
    session_id: session.sessionId,
    pst_session_id: session.sessionId,
    purpose: REACT_PST_SESSION_PURPOSE,
    cert_thumbprint: cert.thumbprint,
    cert_key: cert.thumbprint,
    expires_at: session.expiresAt,
  })

  const updateQuery = (key: keyof AcquisitionQuery, value: string) => setQuery((current) => ({ ...current, [key]: value }))
  const updateOption = (key: keyof AcquisitionOptions, value: boolean) => setOptions((current) => ({ ...current, [key]: value }))
  const updateMapping = (key: keyof AcquisitionMapping, value: string) => setMapping((current) => {
    const next = { ...current, [key]: value } as AcquisitionMapping
    if (key === 'target_fascicolo_id' && value && current.mode === 'create_new') {
      next.mode = 'update_existing'
    }
    if (key === 'mode' && value === 'create_new') {
      next.target_fascicolo_id = ''
    }
    return next
  })
  const portalNeedsLocalSigner = ['pst', 'pdp', 'pat', 'ptt'].includes(portal)
  const requiresBrowserLocalSigner = portalNeedsLocalSigner && localSignerDesktopSupported

  const officeTypes = useMemo(() => ['tutti', ...Array.from(new Set(data.offices.map((office) => office.tipo).filter(Boolean))).sort()], [data.offices])
  const officeMatches = useMemo(() => {
    const needle = normaliseSearch(query.ufficio)
    if (needle.length < 2) return []
    return data.offices.filter((office) => {
      if (officeTypeFilter !== 'tutti' && office.tipo !== officeTypeFilter) return false
      const haystack = normaliseSearch([
        office.nome,
        office.descrizione,
        office.codice,
        office.codiceMinistero,
        office.distretto,
        office.comune,
        office.provincia,
        office.regione,
        office.servizioPst,
        ...office.servizi,
      ].filter(Boolean).join(' '))
      return haystack.includes(needle)
    }).slice(0, 10)
  }, [data.offices, officeTypeFilter, query.ufficio])

  const officeMatchesCode = (office: OfficeRow, value: string) => {
    const needle = normaliseSearch(value)
    return Boolean(needle) && (
      normaliseSearch(office.codice) === needle
      || normaliseSearch(office.codiceMinistero) === needle
    )
  }

  const selectedOfficeMatches = (office: OfficeRow) => officeMatchesCode(office, asText(query.ufficioCodice))

  const selectOffice = (office: OfficeRow) => {
    setQuery((current) => ({
      ...current,
      ufficio: office.nome,
      ufficioCodice: office.codice || office.codiceMinistero,
      ufficioNome: office.nome,
    }))
  }

  const resolvedOfficeCode = () => {
    const explicitOfficeCode = asText(query.ufficioCodice)
    if (explicitOfficeCode) {
      const fromExistingCode = data.offices.find((office) => officeMatchesCode(office, explicitOfficeCode))
      return fromExistingCode?.codice || explicitOfficeCode
    }
    const typed = normaliseSearch(query.ufficio)
    const exact = data.offices.find((office) => {
      return normaliseSearch(office.nome) === typed
        || normaliseSearch(office.codice) === typed
        || normaliseSearch(office.codiceMinistero) === typed
    })
    return exact?.codice || exact?.codiceMinistero || query.ufficio
  }

  const currentLocalSignerDiagnosticContext = (event: string, extra: JsonRecord = {}): JsonRecord => ({
    event,
    portal,
    ufficio: query.ufficioNome || query.ufficio,
    ufficio_codice: resolvedOfficeCode(),
    ufficio_codice_input: asText(query.ufficioCodice),
    numero: query.numero,
    anno: query.anno,
    schema: ministerialSchemaFromQuery(query),
    registro: asText(query.registro),
    materia: asText(query.materia || query.oggetto),
    local_signer_version: localSigner.version,
    latest_local_signer_version: data.localSigner.latestVersion,
    generated_at: new Date().toISOString(),
    ...extra,
  })

  const recordAcquisitionHistory = (
    kind: 'empty' | 'failed' | 'warning',
    title: string,
    reason: unknown,
  ) => {
    const friendlyReason = friendlyAcquisitionReason(reason)
    const retryHref = acquisitionRetryHref(portal, query, mapping)
    const timestamp = new Date().toISOString()
    pushAcquisitionHistoryEvent({
      id: `local-${portal}-${kind}-${Date.now()}`,
      portal: portal as AcquisitionHistoryEvent['portal'],
      title,
      subtitle: acquisitionHistorySubtitle(query, friendlyReason),
      timestamp,
      href: retryHref,
      tone: kind === 'failed' ? 'danger' : 'warning',
      badge: kind === 'failed' ? 'Non scaricato' : 'Riprova',
      local: true,
    })
  }

  const collectAndSaveLocalSignerDiagnostic = async (event: string, extra: JsonRecord = {}) => {
    if (!portalNeedsLocalSigner || localSigner.unsupported) return
    const diagnosi = await localSignerJson('/diagnosi', undefined, 45000).catch((error: unknown) => ({
      ok: false,
      errore: asText(error instanceof Error ? error.message : error),
    }))
    const logs = await localSignerJson('/logs/recent?lines=240', undefined, 45000).catch((error: unknown) => ({
      ok: false,
      errore: asText(error instanceof Error ? error.message : error),
      nota: 'Coda log disponibile dal Local Signer 1.6.41.',
    }))
    await saveLocalSignerDiagnostic({
      source: 'browser-local-signer',
      context: currentLocalSignerDiagnosticContext(event, extra),
      local_signer: diagnosi,
      local_logs: logs,
    })
  }

  const officeLooksLikeSigp = () => /giudice\s+di\s+pace|\bgdp\b/i.test(`${query.ufficio} ${query.ufficioNome} ${resolvedOfficeCode()}`)
  const pstHasPartySearch = () => Boolean(
    asText(query.assistito)
    || asText(query.controparte)
    || asText(query.cf),
  )
  const pstHasExactOrPartySearch = () => Boolean(
    (asText(query.numero) && asText(query.anno))
    || pstHasPartySearch(),
  )
  const pstHasYearSearch = () => portal === 'pst' && Boolean(asText(query.anno) && !asText(query.numero) && !pstHasPartySearch())
  const pstHasSearchCriteria = () => pstHasExactOrPartySearch() || pstHasYearSearch()

  const canUsePstSearchSnapshot = () => Boolean(
    portal === 'pst'
    && asText(resolvedOfficeCode())
    && asText(query.numero)
    && asText(query.anno)
    && !officeLooksLikeSigp(),
  )

  const searchPayload = () => ({
    ufficio_codice: resolvedOfficeCode(),
    ufficio: query.ufficioNome || query.ufficio,
    numero: query.numero,
    anno: query.anno,
    assistito: query.assistito,
    controparte: query.controparte,
    cf: query.cf,
    oggetto: query.oggetto,
    ...ministerialHintsFromQuery(query),
    target_document: targetDocumentPayload,
  })

  const runSearch = async () => {
    if (portalUsesOfficialAssistant) {
      setStep(1)
      setMessage('Per questo canale la ricerca e la consultazione avvengono nella sessione assistita IUSENTRA. Raccogli file o dati autorizzati e poi importali nel fascicolo interno.')
      return
    }
    if (portalNeedsLocalSigner && !localSignerDesktopSupported) {
      setStep(1)
      setMessage('Il canale Local Signer è disponibile solo da PC desktop Windows, macOS o Linux. Da mobile o tablet il controllo non viene eseguito.')
      return
    }
    if (requiresBrowserLocalSigner) {
      setStep(1)
      setMessage('Verifico Local Signer sul PC e proseguo appena il servizio locale risponde.')
      let checkedSigner = localSigner.ok ? localSigner : await checkLocalSigner(false)
      if (!checkedSigner.ok) {
        setMessage('Local Signer non raggiungibile sul PC. Avvialo dal pacchetto installato e ripeti la ricerca.')
        return
      }
      if (checkedSigner.outdated) {
        setMessage(`Local Signer ${checkedSigner.version || ''} da aggiornare alla versione ${data.localSigner.latestVersion}. Avvio l'aggiornamento prima della ricerca.`)
        const updatedSigner = await updateLocalSignerAutomatically()
        checkedSigner = updatedSigner || checkedSigner
        if (!checkedSigner.ok || checkedSigner.outdated) {
          setMessage('Aggiornamento Local Signer non completato: installa il pacchetto ufficiale aperto dal browser, poi premi Cerca di nuovo.')
          return
        }
      }
      setStep(2)
    }
    if (portal === 'pst' && (query.ufficio || query.ufficioCodice) && !data.offices.length) {
      setStep(1)
      setMessage('Il catalogo uffici non è ancora pronto. Attendo il caricamento per inviare al PST il codice ufficiale corretto.')
      return
    }
    setBusy('search')
    setMessage(portal === 'pst'
      ? 'Ricerca PST in corso: verifico certificato, sessione e dati del fascicolo. Se Windows mostra il PIN, inseriscilo una sola volta per la consultazione.'
      : '')
    setImportResult({})
    setImportProgress(portal === 'pst'
      ? {
        active: true,
        phase: 'Ricerca fascicolo sul PST',
        current: 'Verifica certificato e sessione locale',
        completed: 0,
        total: 4,
        failures: [],
      }
      : { active: false, phase: '', current: '', completed: 0, total: 0, failures: [] })
    let rows: AcquisitionResult[] = []
    let pstSignerPayload: JsonRecord | null = null
    let pstCertForDiagnostic: PstCertificate | null = null
    let pstCfForDiagnostic = ''
    let pstCfSourceForDiagnostic = ''
    const progressStartedAt = Date.now()
    let progressHeartbeat: number | null = null
    if (portal === 'pst') {
      progressHeartbeat = window.setInterval(() => {
        setImportProgress((current) => {
          if (!current.active) return current
          const baseCurrent = current.current.replace(/\s·\sattesa\s+\d+s$/i, '')
          const elapsedSeconds = Math.max(1, Math.round((Date.now() - progressStartedAt) / 1000))
          return {
            ...current,
            current: `${baseCurrent} · attesa ${elapsedSeconds}s`,
          }
        })
      }, 15_000)
    }
    try {
      if (portal === 'pst') {
        setImportProgress((current) => ({
          ...current,
          current: 'Controllo collegamento Local Signer dal browser',
        }))
        await requireLocalSignerBrowserBridge()
        const tribunale = resolvedOfficeCode()
        let signerPayload: JsonRecord | null = null
        let cert = await ensurePstCertificate()
        setImportProgress((current) => ({
          ...current,
          current: 'Certificato confermato; lettura dati dal portale ufficiale',
          completed: Math.max(current.completed, 1),
        }))
        pstCertForDiagnostic = cert
        pstCfForDiagnostic = pstAttorneyFiscalCode(cert)
        pstCfSourceForDiagnostic = pstAttorneyFiscalCodeSource(cert)
        let session = activePstSessionFor(tribunale, cert)
        const exactPstSearch = Boolean(asText(query.numero) && asText(query.anno))
        if (!pstHasSearchCriteria()) {
          throw new Error("Indica numero e anno, un anno per vedere l'elenco fascicoli, oppure almeno una parte o un codice fiscale per interrogare il PST.")
        }
        if (canUsePstSearchSnapshot()) {
          try {
            signerPayload = await localSignerJson('/pst/ricerca-snapshot', {
              tribunale,
              numero_rg: query.numero,
              anno_rg: query.anno,
              nome_parte: exactPstSearch ? '' : (query.assistito || query.controparte),
              cf_parte: exactPstSearch ? '' : query.cf,
              oggetto: query.oggetto,
              ...ministerialHintsFromQuery(query),
              ufficio_nome: query.ufficioNome || query.ufficio,
              cf_avvocato: pstCfForDiagnostic,
              cert_thumbprint: cert.thumbprint || null,
              cert_key: cert.thumbprint || '',
              purpose: REACT_PST_SESSION_PURPOSE,
              pst_session_id: session?.sessionId || '',
            }, LOCAL_SIGNER_PST_SEARCH_TIMEOUT_MS)
          } catch (error: unknown) {
            const message = asText(error instanceof Error ? error.message : error)
            if (!/not found/i.test(message)) throw error
          }
        }
        if (!signerPayload) {
          cert = await ensurePstCertificate()
          setImportProgress((current) => ({
            ...current,
            current: 'Uso il percorso di ricerca alternativo del PST',
            completed: Math.max(current.completed, 1),
          }))
          pstCertForDiagnostic = cert
          pstCfForDiagnostic = pstAttorneyFiscalCode(cert)
          pstCfSourceForDiagnostic = pstAttorneyFiscalCodeSource(cert)
          session = activePstSessionFor(tribunale, cert)
          signerPayload = await localSignerJson('/pst/ricerca', {
            tribunale,
            numero_rg: query.numero,
            anno_rg: query.anno,
            nome_parte: exactPstSearch ? '' : (query.assistito || query.controparte),
            cf_parte: exactPstSearch ? '' : query.cf,
            oggetto: query.oggetto,
            ...ministerialHintsFromQuery(query),
            cf_avvocato: pstCfForDiagnostic,
            cert_thumbprint: cert.thumbprint || null,
            cert_key: cert.thumbprint || '',
            purpose: REACT_PST_SESSION_PURPOSE,
            pst_session_id: session?.sessionId || '',
          }, LOCAL_SIGNER_PST_SEARCH_TIMEOUT_MS)
        }
        setImportProgress((current) => ({
          ...current,
          current: 'Dati fascicolo ricevuti; preparo la lista documenti',
          completed: Math.max(current.completed, 3),
        }))
        const nextSession = rememberPstSession(signerPayload, tribunale, cert) || session
        if (!nextSession) throw new Error('Sessione PST non inizializzata dal Local Signer.')
        pstSignerPayload = signerPayload
        const snapshot = asRecord(signerPayload.snapshot)
        const signerRows = asList(signerPayload.fascicoli || signerPayload.results)
        const snapshotFascicolo = asRecord(snapshot.fascicolo)
        const snapshotDocumenti = asList(snapshot.documenti || snapshot.catalogo)
        const sourceRows = signerRows.length
          ? signerRows
          : (Object.keys(snapshotFascicolo).length || snapshotDocumenti.length ? [snapshotFascicolo] : [])
        rows = sourceRows.map((row, index) => {
          const item = normalisePstAcquisitionResult(row, index, query, tribunale)
          return {
            ...item,
            raw: {
              ...item.raw,
              ...(Object.keys(snapshot).length ? { snapshot } : {}),
              pst_session: pstSessionForServer(nextSession, cert),
            },
          }
        })
      } else {
        const payload = await portalJson(portal, 'search', searchPayload())
        if (payload.ok === false) throw new Error(asText(payload.errore, 'Ricerca non completata.'))
        rows = asList(payload.results || payload.fascicoli).map(normaliseAcquisitionResult)
      }
      setResults(rows)
      setSelection(rows[0] || null)
      setStep(2)
      setMessage(rows.length ? `${rows.length} risultati trovati.` : 'Nessun fascicolo trovato con questi filtri.')
      setImportProgress((current) => ({
        ...current,
        active: false,
        phase: rows.length ? 'Ricerca completata' : 'Ricerca completata senza risultati',
        current: rows.length ? 'Seleziona il fascicolo da visualizzare' : 'Nessun fascicolo trovato con questi filtri',
        completed: current.total || 4,
        total: current.total || 4,
      }))
      if (!rows.length) {
        recordAcquisitionHistory('empty', 'Fascicolo non scaricato dal portale', 'Nessun fascicolo trovato con questi filtri.')
      }
      if (portal === 'pst') {
        void collectAndSaveLocalSignerDiagnostic(rows.length ? 'pst_search_success' : 'pst_search_empty', {
          risultati: rows.length,
          cf_avvocato_usato: pstCfForDiagnostic,
          cf_avvocato_fonte: pstCfSourceForDiagnostic,
          cf_avvocato_certificato: asText(pstCertForDiagnostic?.codiceFiscale),
          cf_avvocato_impostazioni: asText(status.codice_fiscale_avvocato),
          cert_thumbprint: asText(pstCertForDiagnostic?.thumbprint),
          signer_result: pstSignerPayload ? {
            ok: pstSignerPayload.ok !== false,
            raw_xml: asText(pstSignerPayload.raw_xml),
            fascicoli: asList(pstSignerPayload.fascicoli || pstSignerPayload.results).length,
            documenti: asList(pstSignerPayload.documenti).length,
            snapshot: asRecord(pstSignerPayload.snapshot),
            pst_session_purpose: asText(pstSignerPayload.pst_session_purpose),
          } : {},
        })
      }
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      const errorMessage = asText(error instanceof Error ? error.message : error, 'Ricerca non disponibile.')
      setMessage(errorMessage)
      setImportProgress((current) => ({
        ...current,
        active: false,
        phase: current.phase || 'Ricerca non completata',
        failures: current.failures.length ? current.failures : [errorMessage],
      }))
      recordAcquisitionHistory('failed', 'Fascicolo non scaricato dal portale', errorMessage)
      if (portal === 'pst') {
        void collectAndSaveLocalSignerDiagnostic('pst_search_error', {
          errore: errorMessage,
          cf_avvocato_usato: pstCfForDiagnostic,
          cf_avvocato_fonte: pstCfSourceForDiagnostic,
          cf_avvocato_certificato: asText(pstCertForDiagnostic?.codiceFiscale),
          cf_avvocato_impostazioni: asText(status.codice_fiscale_avvocato),
          cert_thumbprint: asText(pstCertForDiagnostic?.thumbprint),
        })
      }
    } finally {
      if (progressHeartbeat !== null) window.clearInterval(progressHeartbeat)
      setBusy('')
    }
  }

  useEffect(() => {
    if (!visible || portal !== 'pst') return
    const params = new URLSearchParams(window.location.search)
    if (params.get('auto_pst_test') !== '1') return
    if (autoPstTestStartedRef.current) return
    if (!query.numero || !query.anno || !(query.ufficio || query.ufficioCodice)) return
    if ((query.ufficio || query.ufficioCodice) && !data.offices.length) return
    autoPstTestStartedRef.current = true
    const timer = window.setTimeout(() => {
      void runSearch()
    }, 600)
    return () => window.clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.offices.length, query.anno, query.numero, query.ufficio, query.ufficioCodice, visible, portal])

  const runPreview = async (activeSelection: AcquisitionResult | null = selection) => {
    if (!activeSelection) {
      setMessage('Seleziona prima un fascicolo dal risultato della ricerca.')
      return
    }
    setSelection(activeSelection)
    setBusy('preview')
    try {
      let payload: JsonRecord
      if (portal === 'pst') {
        setImportProgress({
          active: true,
          phase: 'Visualizzazione fascicolo PST',
          current: 'Carico scheda, documenti, eventi e comunicazioni disponibili',
          completed: 0,
          total: 3,
          failures: [],
        })
        const tribunale = asText(activeSelection.raw.ufficio_codice || resolvedOfficeCode())
        let snapshot = asRecord(activeSelection.raw.snapshot)
        let documenti = asList(snapshot.catalogo || snapshot.documenti).map(asRecord)
        let pstSessionPayload = asRecord(activeSelection.raw.pst_session)
        const cert = await ensurePstCertificate()
        const session = activePstSessionFor(tribunale, cert)
        setImportProgress((current) => ({
          ...current,
          current: 'Aggiorno scheda ministeriale, allegati e comunicazioni disponibili',
          completed: Math.max(current.completed, 1),
        }))
        const signerPayload = await localSignerPstFascicoloSnapshotJob({
          selection: activeSelection.raw,
          codice_ufficio: tribunale,
          numero_rg: asText(activeSelection.raw.numero || query.numero),
          anno_rg: asText(activeSelection.raw.anno || query.anno),
          id_fascicolo: asText(activeSelection.raw.id_fascicolo),
          sub_procedimento: asText(activeSelection.raw.sub_procedimento),
          servizio_pst: asText(activeSelection.raw.servizio_pst || asRecord(asRecord(activeSelection.raw.snapshot).fascicolo).servizio_pst),
          registro_portale: asText(activeSelection.raw.registro_portale || asRecord(asRecord(activeSelection.raw.snapshot).fascicolo).registro_portale),
          tabella_ministeriale: asText(activeSelection.raw.tabella_ministeriale || asRecord(asRecord(activeSelection.raw.snapshot).fascicolo).tabella_ministeriale),
          ...ministerialHintsFromQuery(query),
          cf_avvocato: pstAttorneyFiscalCode(cert),
          cert_thumbprint: cert.thumbprint || null,
          cert_key: cert.thumbprint || '',
          purpose: REACT_PST_SESSION_PURPOSE,
          pst_session_id: session?.sessionId || '',
        }, LOCAL_SIGNER_PST_SEARCH_TIMEOUT_MS)
        const nextSession = rememberPstSession(signerPayload, tribunale, cert) || session
        if (!nextSession) throw new Error('Sessione PST non inizializzata dal Local Signer.')
        const refreshedSnapshot = asRecord(signerPayload.snapshot)
        if (Object.keys(refreshedSnapshot).length) {
          snapshot = refreshedSnapshot
        }
        const refreshedDocumenti = asList(snapshot.documenti || snapshot.catalogo || signerPayload.documenti).map(asRecord)
        if (refreshedDocumenti.length) {
          documenti = refreshedDocumenti
        }
        pstSessionPayload = pstSessionForServer(nextSession, cert)
        payload = await portalJson(portal, 'preview', {
          selection: {
            ...activeSelection.raw,
            snapshot,
            pst_session: pstSessionPayload,
          },
          snapshot,
          documenti,
          pst_session: pstSessionPayload,
          target_document: targetDocumentPayload,
        })
      } else {
        payload = await portalJson(portal, 'preview', { selection: activeSelection.raw, target_document: targetDocumentPayload })
      }
      if (payload.ok === false) throw new Error(asText(payload.errore, 'Anteprima non completata.'))
      setPreview(asRecord(payload.preview))
      setStep(3)
      setMessage('Anteprima caricata: verifica dati, parti, eventi e documenti.')
      if (portal === 'pst') {
        setImportProgress((current) => ({
          ...current,
          active: false,
          phase: 'Fascicolo visualizzato',
          current: 'Dati fascicolo, documenti ed eventi caricati',
          completed: current.total || 3,
          total: current.total || 3,
        }))
      }
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      const errorMessage = asText(error instanceof Error ? error.message : error, 'Anteprima non disponibile.')
      setMessage(errorMessage)
      if (portal === 'pst') {
        setImportProgress((current) => ({
          ...current,
          active: false,
          phase: current.phase || 'Visualizzazione non completata',
          failures: current.failures.length ? current.failures : [errorMessage],
        }))
      }
    } finally {
      setBusy('')
    }
  }

  const runAnalysis = async () => {
    if (portalUsesOfficialAssistant && (!selection || !Object.keys(preview).length)) {
      const hasFiles = Boolean(files.length || assistantSession?.downloaded_files?.length)
      const localBlockers: JsonRecord[] = []
      if (!mapping.target_fascicolo_id) {
        localBlockers.push({ code: 'Fascicolo interno', message: 'Seleziona il fascicolo interno in cui importare file, ricevute ed esiti.' })
      }
      if (!hasFiles) {
        localBlockers.push({ code: 'File ufficiali', message: 'Raccogli file dalla sessione assistita o seleziona dati autorizzati.' })
      }
      setAnalysis({
        status: localBlockers.length ? 'block' : 'ok',
        score: localBlockers.length ? 40 : 100,
        blockers: localBlockers,
        warnings: [],
        ok: localBlockers.length ? [] : [
          { code: 'Sessione IUSENTRA', message: 'Importazione pronta nel fascicolo interno selezionato.' },
        ],
      })
      setStep(6)
      setMessage(localBlockers.length ? 'Completa fascicolo interno e file raccolti prima di importare.' : 'Verifica completata: puoi importare nel fascicolo interno.')
      return
    }
    if (!selection || !Object.keys(preview).length) {
      setMessage("Carica prima l'anteprima del fascicolo.")
      return
    }
    setBusy('analysis')
    try {
      const previewForAnalysis = portal === 'pst' && options.importa_documenti && selectedPreviewDocuments.length
        ? filterPreviewForSelectedDocuments(preview, selectedPreviewDocuments)
        : preview
      const payload = await portalJson(portal, 'analyze', {
        selection: selection.raw,
        preview: previewForAnalysis,
        options,
        mapping,
        target_document: targetDocumentPayload,
      })
      if (payload.ok === false) throw new Error(asText(payload.errore, 'Analisi non completata.'))
      setAnalysis(asRecord(payload.analysis))
      setStep(6)
      setMessage("Analisi completata: controlla blocchi, avvisi e corrispondenze prima dell'importazione.")
    } catch (error: unknown) {
      setMessage(asText(error instanceof Error ? error.message : error, 'Analisi non disponibile.'))
    } finally {
      setBusy('')
    }
  }

  const onFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    setBusy('files')
    setMessage('Preparazione dei file selezionati...')
    try {
      const collected = await collectAcquisitionFiles(event.currentTarget.files, options.scarica_originale_portale)
      setFiles(collected)
      setMessage(collected.length ? `${collected.length} file pronti per l'importazione manuale.` : 'Nessun file selezionato.')
    } catch (error: unknown) {
      setFiles([])
      setMessage(asText(error instanceof Error ? error.message : error, 'File non leggibile.'))
    } finally {
      setBusy('')
    }
  }

  const togglePreviewDocument = (doc: JsonRecord, index: number, checked: boolean) => {
    const key = pstDocumentSelectionKey(doc, index)
    setSelectedDocumentKeys((current) => {
      const next = new Set(current)
      if (checked) next.add(key)
      else next.delete(key)
      const values = Array.from(next)
      if (!values.length) setOptions((currentOptions) => ({ ...currentOptions, importa_documenti: false }))
      else setOptions((currentOptions) => ({ ...currentOptions, importa_documenti: true }))
      return values
    })
  }

  const selectAllPreviewDocuments = () => {
    setSelectedDocumentKeys(previewDocumentKeys)
    if (previewDocumentKeys.length) setOptions((current) => ({ ...current, importa_documenti: true }))
  }

  const clearPreviewDocumentSelection = () => {
    setSelectedDocumentKeys([])
    setOptions((current) => ({ ...current, importa_documenti: false }))
  }

  const downloadPstDocumentsFromSigner = async (
    documentsToDownload: JsonRecord[],
    activeSelection: JsonRecord = selection?.raw || {},
  ): Promise<{ files: AcquisitionFile[]; failures: string[]; selection: JsonRecord }> => {
    const documenti = documentsToDownload
      .map((item) => pstDownloadDocumentPayload(item, options.scarica_originale_portale))
      .filter((item) => pstDocumentIdentifierValues(item).length)
    if (!documenti.length) {
      throw new Error('Nessun documento selezionato contiene identificativi PST scaricabili.')
    }
    const firstName = asText(documenti[0]?.nome_documento || documenti[0]?.id_documento, 'documenti del fascicolo')
    setImportProgress({
      active: true,
      phase: 'Scaricamento documenti dal PST',
      current: firstName,
      completed: 0,
      total: documenti.length,
      failures: [],
    })
    const tribunale = asText(activeSelection.ufficio_codice || resolvedOfficeCode())
    const cert = await ensurePstCertificate()
    const session = activePstSessionFor(tribunale, cert)
    const signerPayload = await localSignerJson('/pst/download-documenti-batch', {
      tribunale,
      cf_avvocato: pstAttorneyFiscalCode(cert),
      cert_thumbprint: cert.thumbprint || null,
      cert_key: cert.thumbprint || '',
      purpose: REACT_PST_SESSION_PURPOSE,
      pst_session_id: session?.sessionId || '',
      preflight_auth: false,
      original: options.scarica_originale_portale,
      servizio_pst: asText(activeSelection.servizio_pst || asRecord(asRecord(activeSelection.snapshot).fascicolo).servizio_pst),
      registro_portale: asText(activeSelection.registro_portale || asRecord(asRecord(activeSelection.snapshot).fascicolo).registro_portale),
      tabella_ministeriale: asText(activeSelection.tabella_ministeriale || asRecord(asRecord(activeSelection.snapshot).fascicolo).tabella_ministeriale),
      ...ministerialHintsFromQuery(query),
      documents: documenti,
    }, LOCAL_SIGNER_PST_DOWNLOAD_TIMEOUT_MS)
    const nextSession = rememberPstSession(signerPayload, tribunale, cert) || session
    if (!nextSession) throw new Error('Sessione PST non inizializzata dal Local Signer.')
    const signerRows = asList(signerPayload.files).map(asRecord)
    const signerFiles = signerFilesToAcquisitionFiles(signerRows, options.scarica_originale_portale)
    const failures = asList(signerPayload.failures).map(asRecord)
    const failureMessages = failures.map(formatDownloadFailure)
    setImportProgress({
      active: true,
      phase: signerFiles.length ? 'Documenti ricevuti dal PST' : 'Scaricamento non completato',
      current: signerFiles.length ? asText(signerFiles[signerFiles.length - 1]?.nome || firstName) : firstName,
      completed: signerFiles.length,
      total: asNumber(signerPayload.documenti_richiesti) || documenti.length,
      failures: failureMessages,
    })
    if (!signerFiles.length) {
      throw new Error(asText(failures[0]?.errore || failures[0]?.message, 'Nessun documento scaricato dal portale ufficiale.'))
    }
    return {
      files: signerFiles,
      failures: failureMessages,
      selection: {
        ...activeSelection,
        pst_session: pstSessionForServer(nextSession, cert),
      },
    }
  }

  const downloadSelectedPstDocuments = async (documentsOverride?: JsonRecord[]) => {
    const docsToDownload = documentsOverride || selectedPreviewDocuments
    if (!docsToDownload.length) {
      setMessage('Seleziona almeno un documento PST da scaricare.')
      return
    }
    setBusy('download')
    try {
      const downloaded = await downloadPstDocumentsFromSigner(docsToDownload)
      const merged = mergeAcquisitionFiles(files, downloaded.files)
      setFiles(merged)
      setImportProgress((current) => ({
        ...current,
        active: false,
        phase: downloaded.failures.length ? 'Documenti ricevuti con avvisi' : 'Documenti ricevuti',
        completed: downloaded.files.length,
        total: current.total || docsToDownload.length,
        failures: downloaded.failures,
      }))
      setMessage(`${downloaded.files.length} documenti PST scaricati e pronti per l'importazione.`)
      if (downloaded.failures.length) {
        recordAcquisitionHistory('warning', 'Scarico completato con documenti da riprovare', downloaded.failures.join(' | '))
      }
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      const errorMessage = asText(error instanceof Error ? error.message : error, 'Scaricamento documenti non completato.')
      setMessage(errorMessage)
      recordAcquisitionHistory('failed', 'Fascicolo non scaricato dal portale', errorMessage)
      setImportProgress((current) => ({
        ...current,
        active: false,
        phase: current.phase || 'Scaricamento non completato',
        failures: current.failures.length ? current.failures : [errorMessage],
      }))
    } finally {
      setBusy('')
    }
  }

  const runImport = async (overrideFiles?: AcquisitionFile[]) => {
    let activeFiles = overrideFiles || files
    if (portalUsesOfficialAssistant && assistantSession?.downloaded_files?.length) {
      activeFiles = mergeAcquisitionFiles(
        activeFiles,
        assistantFilesToAcquisitionFiles(assistantSession.downloaded_files, options.scarica_originale_portale),
      )
    }
    const payloadJson = authorisedPayload(activeFiles)
    const selectedDocsForImport = portal === 'pst' && options.importa_documenti ? selectedPreviewDocuments : []
    let downloadedFiles = activeFiles.filter((file) => !file.payload_json)
    if (portal === 'pst' && selectedDocsForImport.length) {
      downloadedFiles = filterDownloadedFilesForSelectedPstDocuments(downloadedFiles, selectedDocsForImport)
    }
    if (!payloadJson && portalUsesOfficialAssistant && downloadedFiles.length && !mapping.target_fascicolo_id) {
      setMessage('Seleziona il fascicolo interno in cui importare file, ricevute ed esiti.')
      setStep(5)
      return
    }
    if (!payloadJson && !portalUsesOfficialAssistant && (!selection || !Object.keys(preview).length)) {
      setMessage('Import bloccato: selezione e anteprima sono obbligatorie.')
      return
    }
    if (!payloadJson && portalUsesOfficialAssistant && !downloadedFiles.length && (!selection || !Object.keys(preview).length)) {
      setMessage('Raccogli file dalla sessione assistita o seleziona dati autorizzati prima di importare.')
      setStep(4)
      return
    }
    setBusy('import')
    setImportProgress({ active: true, phase: 'Preparazione importazione', current: '', completed: 0, total: 0, failures: [] })
    let downloadFailureMessages: string[] = []
    try {
      let activeSelection: JsonRecord = selection?.raw || {}
      let activePreview = preview
      if (selectedDocsForImport.length) {
        activePreview = filterPreviewForSelectedDocuments(preview, selectedDocsForImport)
      }
      if (!payloadJson && portal === 'pst' && options.importa_documenti) {
        const documentsToDownload = selectedDocsForImport.length ? selectedDocsForImport : pstPreviewDocuments(preview)
        const missingDocuments = selectedDocsForImport.length
          ? missingPstDocumentsForDownload(selectedDocsForImport, downloadedFiles)
          : (downloadedFiles.length ? [] : documentsToDownload)
        if (missingDocuments.length) {
          const downloaded = await downloadPstDocumentsFromSigner(missingDocuments, activeSelection)
          downloadFailureMessages = downloaded.failures
          downloadedFiles.push(...downloaded.files)
          activeFiles = mergeAcquisitionFiles(activeFiles, downloaded.files)
          if (selectedDocsForImport.length) {
            downloadedFiles = filterDownloadedFilesForSelectedPstDocuments(downloadedFiles, selectedDocsForImport)
          }
          activeSelection = downloaded.selection
        }
      }
      let payload: JsonRecord
      if (payloadJson) {
        payload = await portalJson(portal, 'importa-payload', {
            payload: payloadJson,
            options,
            mapping,
            fascicolo_locale_id: mapping.target_fascicolo_id,
            downloaded_files: downloadedFiles,
            target_document: targetDocumentPayload,
          })
      } else if (portalUsesOfficialAssistant && downloadedFiles.length) {
        payload = await portalJson(portal, 'importa-file', {
          fascicolo_id: mapping.target_fascicolo_id,
          assistant_session_id: assistantSession?.session_id || '',
          downloaded_files: downloadedFiles,
          options,
          target_document: targetDocumentPayload,
          mapping: {
            ...mapping,
            mode: mapping.mode === 'create_new' ? 'update_existing' : mapping.mode,
          },
        })
      } else {
        if (!selection || !Object.keys(preview).length) {
          throw new Error('Selezione e anteprima sono obbligatorie per questo canale.')
        }
        payload = await portalJson(portal, 'import', {
            selection: activeSelection,
            preview: activePreview,
            options,
            mapping,
            downloaded_files: downloadedFiles,
            pst_session: isRecord(activeSelection.pst_session) ? activeSelection.pst_session : {},
            target_document: targetDocumentPayload,
          })
      }
      if (payload.ok === false) throw new Error(asText(payload.errore, 'Importazione non completata.'))
      setImportProgress((current) => ({
        ...current,
        active: false,
        phase: current.failures.length ? 'Importazione completata con avvisi' : 'Importazione completata',
        completed: current.failures.length && downloadedFiles.length
          ? Math.min(downloadedFiles.length, current.total || downloadedFiles.length)
          : current.total || downloadedFiles.length || activeFiles.length,
        total: current.total || downloadedFiles.length || activeFiles.length,
      }))
      setImportResult(payload)
      setFiles(activeFiles)
      setStep(7)
      if (downloadFailureMessages.length) {
        recordAcquisitionHistory('warning', 'Scarico completato con documenti da riprovare', downloadFailureMessages.join(' | '))
      }
      setMessage(downloadFailureMessages.length
        ? `Importazione completata con ${downloadFailureMessages.length} avviso da verificare sul portale ufficiale.`
        : 'Importazione completata o presa in carico dal gestionale operativo.')
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      setImportProgress((current) => ({
        ...current,
        active: false,
        phase: current.phase || 'Importazione non completata',
        failures: current.failures.length ? current.failures : [asText(error instanceof Error ? error.message : error, 'Importazione non completata.')],
      }))
      const errorMessage = asText(error instanceof Error ? error.message : error, 'Importazione non disponibile.')
      setMessage(errorMessage)
      recordAcquisitionHistory('failed', 'Fascicolo non scaricato dal portale', errorMessage)
    } finally {
      setBusy('')
    }
  }

  const stopAssistantMonitor = () => {
    if (assistantTimerRef.current !== null) {
      window.clearInterval(assistantTimerRef.current)
      assistantTimerRef.current = null
    }
    setAssistantMonitoring(false)
  }

  const assistantJson = async (path: string, body?: JsonRecord, method: 'GET' | 'POST' = 'POST'): Promise<JsonRecord> => {
    const response = await fetch(`/api/portali/${encodeURIComponent(portal)}/assistant${path}`, {
      method,
      credentials: 'same-origin',
      headers: method === 'POST' ? { Accept: 'application/json', 'Content-Type': 'application/json' } : { Accept: 'application/json' },
      body: method === 'POST' ? JSON.stringify(body || {}) : undefined,
    })
    const payload = asRecord(await response.json().catch(() => ({ ok: false, errore: 'Risposta non valida.' })))
    if (!response.ok || payload.ok === false) {
      throw new Error(asText(payload.errore || payload.message, 'Sessione assistita non disponibile.'))
    }
    return payload
  }

  const rememberAssistantSession = (payload: JsonRecord): AssistantSession => {
    const session = {
      session_id: asText(payload.session_id),
      portale: asText(payload.portale || portal),
      official_url: asText(payload.official_url),
      status: asText(payload.status),
      local_connector_available: Boolean(payload.local_connector_available),
      downloaded_files: asList(payload.downloaded_files).map(asRecord),
      message: asText(payload.message),
    }
    setAssistantSession(session)
    return session
  }

  const collectAssistantDownloads = async (silent = false, forcedSessionId = '') => {
    const sessionId = forcedSessionId || assistantSession?.session_id
    if (!portalUsesOfficialAssistant || !sessionId) return
    const payload = await assistantJson(`/${encodeURIComponent(sessionId)}/collect`)
    const session = rememberAssistantSession(payload)
    const collected = assistantFilesToAcquisitionFiles(session.downloaded_files, options.scarica_originale_portale)
    if (!collected.length) {
      if (!silent) setMessage(session.message || 'Nessun file ufficiale raccolto dalla sessione assistita.')
      return
    }
    const merged = mergeAcquisitionFiles(files, collected)
    setFiles(merged)
    stopAssistantMonitor()
    const canImportNow = Boolean(
      (selection && Object.keys(preview).length && !asList(analysis.blockers).length)
      || (portalUsesOfficialAssistant && mapping.target_fascicolo_id),
    )
    if (canImportNow) {
      setMessage(`${collected.length} file ufficiali raccolti. Importazione nel fascicolo interno in corso...`)
      await runImport(merged)
    } else if (portalUsesOfficialAssistant && !mapping.target_fascicolo_id) {
      setMessage(`${collected.length} file ufficiali raccolti. Seleziona il fascicolo interno e conferma l'importazione finale.`)
      setStep(5)
    } else {
      setMessage(`${collected.length} file ufficiali raccolti. Completa verifica e importazione finale per registrarli nel fascicolo interno.`)
    }
  }

  const startAssistantMonitor = async (sessionId: string) => {
    stopAssistantMonitor()
    await assistantJson(`/${encodeURIComponent(sessionId)}/watch-downloads`)
    setAssistantMonitoring(true)
    assistantTimerRef.current = window.setInterval(() => {
      collectAssistantDownloads(true, sessionId).catch((error: unknown) => {
        setMessage(asText(error instanceof Error ? error.message : error, 'Monitor download non disponibile.'))
      })
    }, 5000)
  }

  const startAssistantSession = async () => {
    if (!portalUsesOfficialAssistant) return
    setBusy('assistant')
    try {
      const started = rememberAssistantSession(await assistantJson('/start', {
        fascicolo_id: mapping.target_fascicolo_id || acquisitionInitialFascicoloId(),
      }))
      if (!started.local_connector_available) {
        setMessage(started.message || 'Avvia Local Signer su questo PC e riprova la sessione assistita.')
        return
      }
      const opened = rememberAssistantSession(await assistantJson(`/${encodeURIComponent(started.session_id)}/open`))
      await startAssistantMonitor(opened.session_id)
      setMessage(opened.message || 'Sessione locale aperta. Resta in IUSENTRA: i file raccolti verranno importati nel fascicolo scelto.')
    } catch (error: unknown) {
      setMessage(asText(error instanceof Error ? error.message : error, 'Sessione assistita non avviata.'))
    } finally {
      setBusy('')
    }
  }

  const closeAssistantSession = async () => {
    const sessionId = assistantSession?.session_id
    if (!sessionId) return
    stopAssistantMonitor()
    setBusy('assistant')
    try {
      const closed = rememberAssistantSession(await assistantJson(`/${encodeURIComponent(sessionId)}/close`))
      setMessage(closed.message || 'Sessione assistita chiusa.')
    } catch (error: unknown) {
      setMessage(asText(error instanceof Error ? error.message : error, 'Chiusura sessione non riuscita.'))
    } finally {
      setBusy('')
    }
  }

  useEffect(() => () => {
    if (assistantTimerRef.current !== null) {
      window.clearInterval(assistantTimerRef.current)
      assistantTimerRef.current = null
    }
  }, [])

  if (!visible || !portal) return null

  const identity = previewIdentity(preview)
  const previewParties = previewPeople(preview)
  const previewTimeline = previewEvents(preview)
  const identityRows = previewIdentityRows(identity, selection)
  const blockers = issueRows(analysis, 'blockers')
  const warnings = issueRows(analysis, 'warnings')
  const oks = issueRows(analysis, 'ok')
  const summary = importSummary(importResult)
  const documentReport = asRecord(summary.report_documentale)
  const reportValue = (primary: unknown, fallback: unknown, empty = '0') => asText(primary ?? fallback, empty)
  const documentReportCards = [
    ['Documenti reali', reportValue(documentReport.documenti_reali, summary.documenti_reali ?? summary.documenti)],
    ['Informazioni', reportValue(documentReport.documenti_informativi, summary.documenti_informativi)],
    ['Solo catalogo', reportValue(documentReport.documenti_catalogo, summary.documenti_catalogo)],
    ['Senza contenuto', reportValue(documentReport.documenti_senza_contenuto, summary.documenti_senza_contenuto)],
    ['Scartati', reportValue(documentReport.documenti_scartati, summary.documenti_scartati)],
  ]
  const missingImportNames = asList(documentReport.documenti_senza_contenuto_elenco || documentReport.documenti_mancanti_elenco)
    .map((item) => asText(item))
    .filter(Boolean)
  const official = officialPortalHref(portal)
  const steps = [
    { id: 1, label: 'Accesso', help: 'Sorgente e connessione' },
    { id: 2, label: 'Ricerca', help: 'Trova il fascicolo' },
    { id: 3, label: 'Anteprima', help: 'Verifica dati trovati' },
    { id: 4, label: 'Selezione', help: 'Scegli cosa importare' },
    { id: 5, label: 'Mappatura', help: 'Collega al gestionale' },
    { id: 6, label: 'Verifica', help: 'Conflitti e semafori' },
    { id: 7, label: 'Importa', help: 'Acquisizione finale' },
  ]
  const currentStep = steps.find((item) => item.id === step) || steps[1]
  const retryEvents = localEvents.filter((item) => item.portal === portal).slice(0, 3)
  const previewRecovered = Boolean(Object.keys(preview).length || previewCount(preview, 'documenti') || previewCount(preview, 'eventi'))
  const visibleRetryEvents = previewRecovered || files.length || Object.keys(importResult).length ? [] : retryEvents

  return (
    <section className="iu-tel-acquisition" id="wizard-acquisizione">
      <header className="iu-tel-acquisition__head">
        <div>
          <span><Download size={16}/> {portalLabel(portal)} · Acquisizione guidata</span>
          <h2>Importa pratica da {portalLabel(portal)}</h2>
          <p>Ricerca, verifica e acquisizione guidata del fascicolo telematico. Credenziali, token e sessione restano sul portale ufficiale o sul Local Signer del PC.</p>
        </div>
        <aside>
          <strong>Step {step}/7</strong>
          <span>{busy ? 'Operazione in corso...' : currentStep.help}</span>
          {portalUsesOfficialAssistant ? (
            <button type="button" disabled={busy === 'assistant'} onClick={startAssistantSession}>
              <ExternalLink size={14}/> Sessione IUSENTRA
            </button>
          ) : null}
          {official ? <a href={official} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Portale ufficiale</a> : null}
        </aside>
      </header>

      <div className="iu-tel-acquisition__steps" aria-label="Passaggi acquisizione">
        {steps.map((item) => (
          <button
            type="button"
            className={step === item.id ? 'is-active' : step > item.id ? 'is-done' : ''}
            onClick={() => setStep(item.id)}
            key={item.id}
            aria-current={step === item.id ? 'step' : undefined}
          >
            <span>{item.id}</span>
            <strong>{item.label}</strong>
            <small>{item.help}</small>
          </button>
        ))}
      </div>

      {message ? <div className="iu-tel-acquisition__message"><AlertTriangle size={17}/>{message}</div> : null}
      <AcquisitionProgressView progress={importProgress} />

      {targetDocument.singleDocument ? (
        <div className="iu-tel-acquisition__target">
          <FileText size={18}/>
          <div>
            <strong>Acquisizione mirata da PEC dell'ufficio</strong>
            <span>
              La PEC ha indicato il provvedimento
              {targetDocument.documento ? <b> {targetDocument.documento}</b> : ' da notificare'}.
              Il portale è già compilato con ufficio, R.G. e fascicolo: procedi con l'avvocato allo scaricamento del solo documento e collegalo ai Documenti e atti.
            </span>
            <small>
              {targetDocument.pecId ? `PEC: ${targetDocument.pecId}. ` : ''}
              {targetDocument.hash ? `Hash comunicato: ${targetDocument.hash.slice(0, 12)}... ` : ''}
              {targetDocument.nonDuplicare ? 'IUSENTRA evita duplicati già presenti nel fascicolo.' : 'Controlla i documenti già presenti prima di importare.'}
            </small>
          </div>
        </div>
      ) : null}

      <div className="iu-tel-acquisition__grid">
        <div className="iu-tel-acquisition__main">
          {step === 1 ? (
            <Panel title="Step 1 - Accesso" subtitle="Stato tecnico del canale autorizzato" icon={<MonitorCheck size={17}/>}>
              <div className="iu-tel-acq-status">
                <span><strong>Canale</strong>{portalLabel(portal)}</span>
                <span><strong>Stato</strong>{asText(status.status_text || status.label || status.mode, 'Da verificare')}</span>
                <span><strong>Local Signer</strong>{localSigner.unsupported ? 'Solo desktop' : localSigner.outdated ? 'Da aggiornare' : localSigner.ok ? 'Rilevato sul PC' : 'Da verificare dal PC'}</span>
                <button type="button" disabled={localSigner.checking || localSigner.unsupported} onClick={() => checkLocalSigner(false)}>
                  <RefreshCw size={15}/> {localSigner.checking ? 'Verifica...' : 'Verifica Local Signer'}
                </button>
              </div>
              <div className={`iu-tel-local-signer-card ${localSigner.outdated ? 'is-warning' : localSigner.ok ? 'is-ok' : 'is-missing'}`}>
                <ShieldCheck size={18}/>
                <div>
                  <strong>{localSigner.unsupported ? 'Disponibile solo su desktop' : localSigner.outdated ? 'Aggiornamento richiesto' : localSigner.ok ? 'Local Signer pronto' : 'Controllo locale richiesto'}</strong>
                  <span>{localSigner.message}</span>
                  <small>
                    Servizio locale IUSENTRA sul PC in uso
                    {data.localSigner.latestVersion ? ` - ultima versione ${data.localSigner.latestVersion}` : ''}
                    {localSigner.version ? ` - rilevata ${localSigner.version}` : ''}
                    {localSigner.tokenLabel ? ` - token ${localSigner.tokenLabel}` : ''}
                  </small>
                </div>
              </div>
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={localSigner.unsupported} onClick={() => checkLocalSigner(true)}><RefreshCw size={15}/> Avvia e verifica</button>
                {localSigner.unsupported ? null : <button type="button" disabled={localSigner.checking} onClick={updateLocalSignerAutomatically}><Download size={15}/> Aggiorna automaticamente</button>}
                {localSigner.unsupported ? null : <a href={localSignerInstallHref(data)}><Download size={15}/> Installa o aggiorna</a>}
                <button type="button" disabled={localSigner.unsupported} onClick={() => setStep(2)}><ArrowRight size={15}/> Vai alla ricerca</button>
              </div>
              {portalUsesOfficialAssistant ? (
                <div className={`iu-tel-local-signer-card ${assistantSession?.local_connector_available ? 'is-ok' : 'is-missing'}`}>
                  <MonitorCheck size={18}/>
                  <div>
                    <strong>{assistantMonitoring ? 'Monitor download attivo' : assistantSession ? 'Sessione assistita pronta' : 'Sessione assistita portale'}</strong>
                    <span>{assistantSession?.message || 'IUSENTRA apre una sessione locale assistita, raccoglie i file ufficiali e li importa nel fascicolo interno scelto.'}</span>
                    <small>{assistantSession?.downloaded_files?.length ? `${assistantSession.downloaded_files.length} file raccolti` : 'Nessun file ufficiale ancora raccolto'}</small>
                  </div>
                  <div className="iu-tel-acq-actions">
                    <button type="button" disabled={busy === 'assistant'} onClick={startAssistantSession}><ExternalLink size={15}/> Apri sessione IUSENTRA</button>
                    <button type="button" disabled={!assistantSession?.session_id || busy === 'assistant'} onClick={() => collectAssistantDownloads(false)}><Download size={15}/> Raccogli file nel software</button>
                    <button type="button" disabled={!assistantSession?.session_id || busy === 'assistant'} onClick={closeAssistantSession}><CheckCircle2 size={15}/> Chiudi sessione</button>
                  </div>
                </div>
              ) : null}
            </Panel>
          ) : null}

          {step === 2 ? (
            <Panel
              title={portalUsesOfficialAssistant ? 'Step 2 - Dati di riferimento' : 'Step 2 - Ricerca fascicolo'}
              subtitle={portalUsesOfficialAssistant ? 'La ricerca resta nella sessione assistita IUSENTRA' : "Cerca l'ufficio mentre scrivi e usa i filtri del portale"}
              icon={<Search size={17}/>}
            >
              {portalUsesOfficialAssistant ? (
                <div className="iu-tel-local-signer-inline">
                  <MonitorCheck size={16}/>
                  <span>Per questo canale la consultazione avviene nella sessione locale assistita. Qui puoi completare i dati utili, poi importare file o dati autorizzati nel fascicolo interno.</span>
                  <button type="button" disabled={busy === 'assistant'} onClick={startAssistantSession}>Apri sessione IUSENTRA</button>
                </div>
              ) : null}
              {portalNeedsLocalSigner && !localSignerDesktopSupported ? (
                <div className="iu-tel-local-signer-inline">
                  <ShieldCheck size={16}/>
                  <span>Local Signer è disponibile solo da PC desktop Windows, macOS o Linux. Da mobile o tablet il controllo non viene eseguito.</span>
                </div>
              ) : requiresBrowserLocalSigner && localSigner.outdated ? (
                <div className="iu-tel-local-signer-inline">
                  <ShieldCheck size={16}/>
                  <span>È disponibile una nuova versione del Local Signer. IUSENTRA può aggiornarla automaticamente dal pacchetto ufficiale.</span>
                  <button type="button" disabled={localSigner.checking} onClick={updateLocalSignerAutomatically}>
                    {localSigner.checking ? 'Aggiornamento...' : 'Aggiorna automaticamente'}
                  </button>
                </div>
              ) : requiresBrowserLocalSigner && localSigner.checked && !localSigner.ok ? (
                <div className="iu-tel-local-signer-inline">
                  <ShieldCheck size={16}/>
                  <span>Local Signer non raggiungibile sul PC. Avvialo dal pacchetto installato e ripeti la ricerca.</span>
                  <button type="button" disabled={localSigner.checking} onClick={() => checkLocalSigner(true)}>
                    {localSigner.checking ? 'Verifica...' : 'Avvia e verifica'}
                  </button>
                </div>
              ) : null}
              <div className="iu-tel-acq-form">
                <label className="iu-tel-acq-form__wide">
                  <span>Ufficio giudiziario</span>
                  <div className="iu-tel-acq-office-search">
                    <input
                      value={query.ufficio}
                      onChange={(event) => {
                        const nextOffice = event.currentTarget.value
                        setQuery((current) => ({
                          ...current,
                          ufficio: nextOffice,
                          ufficioCodice: '',
                          ufficioNome: '',
                        }))
                      }}
                      placeholder="Cerca mentre scrivi: es. Tribunale di Vibo Valentia"
                      autoComplete="off"
                    />
                    <select value={officeTypeFilter} onChange={(event) => setOfficeTypeFilter(event.currentTarget.value)} aria-label="Filtra tipo ufficio">
                      {officeTypes.map((type) => <option key={type} value={type}>{type === 'tutti' ? 'Tutti gli uffici' : type}</option>)}
                    </select>
                  </div>
                  <div className="iu-tel-acq-office-results" aria-live="polite">
                    {query.ufficio.trim().length < 2 ? (
                      <span>Scrivi almeno 2 caratteri per cercare nel catalogo uffici importato.</span>
                    ) : officeMatches.length ? (
                      officeMatches.map((office) => (
                        <button type="button" key={office.id} onClick={() => selectOffice(office)} className={selectedOfficeMatches(office) ? 'is-selected' : ''}>
                          <strong>{office.nome}</strong>
                          <small>{[office.tipo, office.distretto, office.comune || office.provincia, office.codice || office.codiceMinistero, office.servizioPst].filter(Boolean).join(' - ')}</small>
                        </button>
                      ))
                    ) : (
                      <span>Nessun ufficio trovato nel catalogo importato. Prova con comune, distretto, codice o tipo ufficio.</span>
                    )}
                  </div>
                </label>
                <label><span>Numero</span><input value={query.numero} onChange={(event) => updateQuery('numero', event.currentTarget.value)} placeholder="Es. 466"/></label>
                <label><span>Anno</span><input value={query.anno} onChange={(event) => updateQuery('anno', event.currentTarget.value)} inputMode="numeric"/></label>
                <label>
                  <span>Tabella ministeriale</span>
                  <select
                    value={query.schema}
                    onChange={(event) => {
                      const schema = event.currentTarget.value
                      setQuery((current) => ({
                        ...current,
                        schema,
                        registro: schema || current.registro,
                        materia: schema || current.materia,
                      }))
                    }}
                  >
                    <option value="">Automatica</option>
                    <option value="civile">Civile contenzioso</option>
                    <option value="lavoro">Lavoro e previdenza</option>
                    <option value="volontaria">Volontaria giurisdizione</option>
                    <option value="minori">Minori</option>
                    <option value="esecuzioni">Esecuzioni e concorsuali</option>
                    <option value="giudice di pace">Giudice di pace</option>
                    <option value="cassazione civile">Cassazione civile</option>
                    <option value="cassazione penale">Cassazione penale</option>
                  </select>
                </label>
                <label><span>Parte assistita</span><input value={query.assistito} onChange={(event) => updateQuery('assistito', event.currentTarget.value)} placeholder="Cliente, imputato, ricorrente..."/></label>
                <label><span>Controparte</span><input value={query.controparte} onChange={(event) => updateQuery('controparte', event.currentTarget.value)} placeholder="Controparte, resistente, parte offesa..."/></label>
                <label><span>CF / P.IVA</span><input value={query.cf} onChange={(event) => updateQuery('cf', event.currentTarget.value)} placeholder="Codice fiscale o partita IVA"/></label>
                <label className="iu-tel-acq-form__wide"><span>Oggetto / materia</span><input value={query.oggetto} onChange={(event) => updateQuery('oggetto', event.currentTarget.value)} placeholder="Oggetto, materia, reato, rito..."/></label>
              </div>
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={busy === 'search' || portalUsesOfficialAssistant || (portalNeedsLocalSigner && !localSignerDesktopSupported)} onClick={runSearch}><Search size={15}/> {portalUsesOfficialAssistant ? 'Ricerca nella sessione assistita' : (pstHasYearSearch() ? 'Cerca fascicoli' : 'Cerca fascicolo')}</button>
                <button type="button" disabled={!selection || busy === 'preview' || portalUsesOfficialAssistant} onClick={() => runPreview()}><FileText size={15}/> Carica anteprima</button>
                {portalUsesOfficialAssistant ? <button type="button" onClick={() => setStep(4)}><ArrowRight size={15}/> Vai ai file raccolti</button> : null}
              </div>
              <div className="iu-tel-acq-results">
                {results.map((result) => (
                  <button type="button" className={selection?.id === result.id ? 'is-selected' : ''} onClick={() => {
                    setSelection(result)
                    if (portal === 'pst' && pstHasYearSearch()) void runPreview(result)
                  }} key={result.id}>
                    <strong>{result.title}</strong>
                    <span>{result.subtitle}</span>
                    <em>{result.badge} {result.meta ? `- ${result.meta}` : ''}</em>
                  </button>
                ))}
              </div>
            </Panel>
          ) : null}

          {step === 3 ? (
            <Panel title="Step 3 - Anteprima" subtitle="Verifica i dati trovati prima della selezione" icon={<FileCheck2 size={17}/>}>
              {Object.keys(preview).length ? (
                <>
                  <div className="iu-tel-acq-preview">
                    <article><span>Procedimento</span><strong>{asText(identity.numero_rg || identity.rg || identity.numero || selection?.title, 'n.d.')}</strong><small>{asText(identity.ufficio_nome || identity.ufficio || identity.tribunale || identity.court, 'Ufficio non indicato')}</small></article>
                    <article><span>Parti</span><strong>{previewPartyMetric(preview, previewParties)}</strong><small>{previewPartyCountLabel(preview, previewParties)}</small></article>
                    <article><span>Documenti</span><strong>{previewCount(preview, 'documenti')}</strong><small>{previewCount(preview, 'depositi')} buste o gruppi</small></article>
                    <article><span>Eventi</span><strong>{previewCount(preview, 'eventi')}</strong><small>Cronologia importabile</small></article>
                    <article>
                      <span>Scadenziario</span>
                      <strong>{structuredHearingLabel ? 'Data ministeriale' : deadlineSourceDocuments.length ? `${deadlineSourceDocuments.length} fonte` : 'Non esposta'}</strong>
                      <small>{structuredHearingLabel || (deadlineSourceDocuments[0] ? previewDocumentTitle(deadlineSourceDocuments[0], 0) : 'Nessuna data strutturata')}</small>
                    </article>
                  </div>
                  <div className="iu-tel-acq-detail-grid">
                    <section>
                      <header><FileText size={16}/><strong>Dati fascicolo</strong></header>
                      <dl>
                        {identityRows.map(([label, value]) => (
                          <div key={label}>
                            <dt>{label}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                      </dl>
                    </section>
                    <section>
                      <header><BadgeCheck size={16}/><strong>Parti</strong></header>
                      <div className="iu-tel-acq-list">
                        {previewParties.length ? previewParties.map((name) => <span key={name}>{name}</span>) : <em>Nessuna parte indicata nell'anteprima.</em>}
                      </div>
                    </section>
                    <section className="iu-tel-acq-detail-grid__wide">
                      <header><Clock3 size={16}/><strong>Scadenziario</strong></header>
                      {structuredHearingLabel ? (
                        <p className="iu-tel-acq-note">Il portale espone una data strutturata: IUSENTRA userà {structuredHearingLabel} per udienza e scadenziario.</p>
                      ) : deadlineSourceDocuments.length ? (
                        <div className="iu-tel-acq-documents">
                          <p className="iu-tel-acq-note">Il portale non espone una prossima udienza strutturata. IUSENTRA userà questi documenti fonte dopo lo scarico, senza creare scadenze non verificate.</p>
                          {deadlineSourceDocuments.slice(0, 6).map((doc, index) => (
                            <article key={`${previewDocumentTitle(doc, index)}-deadline-${index}`}>
                              <Clock3 size={15}/>
                              <div>
                                <strong>{previewDocumentTitle(doc, index)}</strong>
                                <small>{[asText(doc.motivo), previewDocumentMeta(doc)].filter(Boolean).join(' - ') || 'Documento fonte per termine o udienza'}</small>
                              </div>
                              <Badge tone="warning">Fonte</Badge>
                            </article>
                          ))}
                        </div>
                      ) : (
                        <p className="iu-tel-acq-note">Il portale non espone una prossima udienza e il catalogo non indica documenti fonte riconoscibili per termini o udienze.</p>
                      )}
                    </section>
                    <section className="iu-tel-acq-detail-grid__wide">
                      <header><FileCheck2 size={16}/><strong>Documenti nel fascicolo</strong></header>
                      <div className="iu-tel-acq-documents">
                        {previewDocuments.length ? previewDocuments.slice(0, 24).map((doc, index) => (
                          <article key={`${previewDocumentTitle(doc, index)}-${index}`}>
                            <FileText size={15}/>
                            <div>
                              <strong>{previewDocumentTitle(doc, index)}</strong>
                              <small>{previewDocumentMeta(doc) || 'Metadati documento non indicati'}</small>
                            </div>
                          </article>
                        )) : <em>Nessun documento disponibile nell'anteprima.</em>}
                      </div>
                    </section>
                    <section className="iu-tel-acq-detail-grid__wide">
                      <header><ClipboardCheck size={16}/><strong>Cronologia</strong></header>
                      <div className="iu-tel-acq-timeline">
                        {previewTimeline.length ? previewTimeline.slice(0, 10).map((event, index) => (
                          <article key={`${asText(event.id || event.evento_uid || event.label, 'evento')}-${index}`}>
                            <strong>{asText(event.label || event.tipo || event.tipo_atto || event.oggetto, 'Evento')}</strong>
                            <small>{italianDate(event.data || event.data_evento || event.data_udienza || event.data_deposito)}{asText(event.descrizione || event.stato) ? ` - ${asText(event.descrizione || event.stato)}` : ''}</small>
                          </article>
                        )) : <em>Nessun evento indicato nell'anteprima.</em>}
                      </div>
                    </section>
                  </div>
                </>
              ) : <p className="iu-empty">Carica l'anteprima dopo aver selezionato il fascicolo.</p>}
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={!Object.keys(preview).length} onClick={() => setStep(4)}><ArrowRight size={15}/> Scegli cosa importare</button>
              </div>
            </Panel>
          ) : null}

          {step === 4 ? (
            <Panel title="Step 4 - Selezione" subtitle="Scegli documenti, eventi, parti e file autorizzati" icon={<ClipboardCheck size={17}/>}>
              <div className="iu-tel-acq-switches">
                <label><input type="checkbox" checked={options.importa_documenti} onChange={(event) => {
                  const checked = event.currentTarget.checked
                  updateOption('importa_documenti', checked)
                  if (checked && previewDocumentKeys.length && !selectedDocumentKeys.length) setSelectedDocumentKeys(previewDocumentKeys)
                  if (!checked) setSelectedDocumentKeys([])
                }}/> Importa documenti</label>
                <label><input type="checkbox" checked={options.importa_eventi} onChange={(event) => updateOption('importa_eventi', event.currentTarget.checked)}/> Importa eventi</label>
                <label><input type="checkbox" checked={options.importa_scadenze} onChange={(event) => updateOption('importa_scadenze', event.currentTarget.checked)}/> Scadenziario</label>
                <label><input type="checkbox" checked={options.importa_parti} onChange={(event) => updateOption('importa_parti', event.currentTarget.checked)}/> Importa parti</label>
                <label><input type="checkbox" checked={options.scarica_originale_portale} onChange={(event) => updateOption('scarica_originale_portale', event.currentTarget.checked)}/> Originale portale</label>
                <label><input type="checkbox" checked={options.mantieni_albero_originale} onChange={(event) => updateOption('mantieni_albero_originale', event.currentTarget.checked)}/> Mantieni struttura originale</label>
              </div>
              {!structuredHearingLabel && deadlineSourceDocuments.length && options.importa_scadenze ? (
                <p className="iu-tel-acq-note">Scadenziario: manca la data ministeriale, quindi verranno usati i documenti fonte selezionati per estrarre termine o udienza dopo lo scarico.</p>
              ) : null}
              {portal === 'pst' ? <p className="iu-tel-acq-note">Default PST: copia di consultazione con annotazioni ministeriali. L'originale si usa solo se selezionato espressamente.</p> : null}
              {previewDocuments.length ? (
                <>
                  <div className="iu-tel-acq-selection-toolbar">
                    <strong>{selectedPreviewDocuments.length}/{previewDocuments.length} documenti selezionati</strong>
                    <span>{downloadedPstDocumentCount ? `${downloadedPstDocumentCount} scaricati in questa sessione` : 'Nessun documento ancora scaricato'}</span>
                    <button type="button" onClick={selectAllPreviewDocuments}><CheckCircle2 size={14}/> Seleziona tutti</button>
                    <button type="button" onClick={clearPreviewDocumentSelection}><ClipboardCheck size={14}/> Nessuno</button>
                    {portal === 'pst' ? (
                      <>
                        <button type="button" disabled={busy === 'download' || !options.importa_documenti || !selectedPreviewDocuments.length} onClick={() => downloadSelectedPstDocuments()}>
                          <Download size={14}/> Scarica selezionati
                        </button>
                        <button type="button" disabled={busy === 'download'} onClick={() => {
                          selectAllPreviewDocuments()
                          void downloadSelectedPstDocuments(previewDocuments)
                        }}>
                          <Download size={14}/> Scarica tutti
                        </button>
                      </>
                    ) : null}
                  </div>
                  <div className="iu-tel-acq-documents iu-tel-acq-documents--selection">
                    {previewDocuments.map((doc, index) => {
                      const documentKey = pstDocumentSelectionKey(doc, index)
                      const selected = options.importa_documenti && selectedDocumentKeySet.has(documentKey)
                      const downloaded = downloadedPstDocumentKeySet.has(documentKey)
                      return (
                        <article className={selected ? 'is-selected' : 'is-excluded'} key={`${previewDocumentTitle(doc, index)}-select-${index}`}>
                          <label className="iu-tel-acq-doc-check">
                            <input
                              type="checkbox"
                              checked={selected}
                              onChange={(event) => togglePreviewDocument(doc, index, event.currentTarget.checked)}
                              aria-label={`Seleziona ${previewDocumentTitle(doc, index)}`}
                            />
                            <FileText size={15}/>
                          </label>
                          <div>
                            <strong>{previewDocumentTitle(doc, index)}</strong>
                            <small>{previewDocumentMeta(doc) || 'Pronto per lo scaricamento dal PST'}</small>
                          </div>
                          <Badge tone={downloaded ? 'primary' : selected ? 'success' : 'neutral'}>
                            {downloaded ? 'Scaricato' : selected ? 'Da scaricare' : 'Escluso'}
                          </Badge>
                        </article>
                      )
                    })}
                  </div>
                </>
              ) : null}
              <div className="iu-tel-acq-mapping-mode" aria-label="Destinazione pratica">
                {acquisitionMappingModes.map(([value, label, help]) => (
                  <label key={value} className={mapping.mode === value ? 'is-selected' : ''}>
                    <input type="radio" checked={mapping.mode === value} onChange={() => updateMapping('mode', value)} />
                    <strong>{label}</strong>
                    <span>{help}</span>
                  </label>
                ))}
              </div>
              <div className="iu-tel-acq-form iu-tel-acq-form--mapping">
                <label><span>Fascicolo locale</span><select value={mapping.target_fascicolo_id} onChange={(event) => updateMapping('target_fascicolo_id', event.currentTarget.value)}>
                  <option value="">Seleziona se necessario</option>
                  {mappingTargetOptions.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}
                </select></label>
              </div>
              <label className="iu-tel-acq-file">
                <span>File, ZIP o dati autorizzati</span>
                <input type="file" multiple accept=".zip,.pdf,.p7m,.eml,.msg,.xml,.json,.html,.htm,.txt" onChange={onFiles}/>
              </label>
              <div className="iu-tel-acq-results iu-tel-acq-results--compact">
                {files.map((file) => <span key={`${file.nome}-${file.contenuto_b64.length}`}>{file.nome}{file.payload_json ? ' - dati autorizzati' : ''}</span>)}
              </div>
              <div className="iu-tel-acq-actions">
                {mapping.target_fascicolo_id ? (
                  <button type="button" disabled={busy === 'import'} onClick={() => runImport()}><UploadCloud size={15}/> Importa nel fascicolo</button>
                ) : null}
                <button type="button" onClick={() => setStep(5)}><ArrowRight size={15}/> {mapping.target_fascicolo_id ? 'Verifica destinazione' : 'Scegli destinazione'}</button>
              </div>
            </Panel>
          ) : null}

          {step === 5 ? (
            <Panel title="Step 5 - Destinazione" subtitle="Crea una nuova pratica o usa un fascicolo locale" icon={<FolderOpen size={17}/>}>
              <div className="iu-tel-acq-mapping-mode">
                {acquisitionMappingModes.map(([value, label, help]) => (
                  <label key={value} className={mapping.mode === value ? 'is-selected' : ''}>
                    <input type="radio" checked={mapping.mode === value} onChange={() => updateMapping('mode', value)} />
                    <strong>{label}</strong>
                    <span>{help}</span>
                  </label>
                ))}
              </div>
              <div className="iu-tel-acq-form iu-tel-acq-form--mapping">
                <label><span>Fascicolo locale</span><select value={mapping.target_fascicolo_id} onChange={(event) => updateMapping('target_fascicolo_id', event.currentTarget.value)}>
                  <option value="">Seleziona se necessario</option>
                  {mappingTargetOptions.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}
                </select></label>
                <label><span>Procedimento</span><input value={mapping.procedimento} onChange={(event) => updateMapping('procedimento', event.currentTarget.value)}/></label>
                <label><span>Materia</span><input value={mapping.materia} onChange={(event) => updateMapping('materia', event.currentTarget.value)}/></label>
                <label><span>Grado</span><input value={mapping.grado} onChange={(event) => updateMapping('grado', event.currentTarget.value)}/></label>
              </div>
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={busy === 'analysis'} onClick={runAnalysis}><ShieldCheck size={15}/> {portalUsesOfficialAssistant ? 'Verifica importazione' : 'Analizza conflitti'}</button>
              </div>
            </Panel>
          ) : null}

          {step === 6 ? (
            <Panel title="Step 6 - Verifica" subtitle="Blocchi, avvisi e semafori prima dell'import" icon={<ShieldCheck size={17}/>}>
              {Object.keys(analysis).length ? (
                <div className="iu-tel-acq-analysis">
                  <article><span>Punteggio</span><strong>{asText(analysis.score || analysis.punteggio, 'n.d.')}</strong></article>
                  <article><span>Blocchi</span><strong>{blockers.length}</strong></article>
                  <article><span>Avvisi</span><strong>{warnings.length}</strong></article>
                  <article><span>OK</span><strong>{oks.length}</strong></article>
                </div>
              ) : <p className="iu-empty">Esegui l'analisi dalla mappatura per vedere conflitti, blocchi e avvisi.</p>}
              {[...blockers, ...warnings].slice(0, 8).map((issue, index) => {
                const issueDocuments = asList(issue.documenti).map(asRecord)
                return (
                  <div className="iu-tel-acq-issue" key={`${asText(issue.code || issue.label, 'issue')}-${index}`}>
                    <strong>{asText(issue.code || issue.label || issue.title || issue.categoria, 'Controllo')}</strong>
                    <span>{asText(issue.message || issue.human_message || issue.detail || issue.descrizione, 'Verifica richiesta')}</span>
                    {issueDocuments.length ? (
                      <div className="iu-tel-acq-issue__docs">
                        {issueDocuments.slice(0, 4).map((doc, docIndex) => (
                          <span key={`${previewDocumentTitle(doc, docIndex)}-${docIndex}`}>
                            {previewDocumentTitle(doc, docIndex)}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )
              })}
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={!Object.keys(analysis).length || blockers.length > 0} onClick={() => setStep(7)}><ArrowRight size={15}/> Vai all'importazione</button>
                <button type="button" disabled={busy === 'analysis'} onClick={runAnalysis}><ShieldCheck size={15}/> Rianalizza</button>
              </div>
            </Panel>
          ) : null}

          {step === 7 ? (
            <Panel title="Step 7 - Importazione finale" subtitle="Registrazione controllata nel gestionale" icon={<UploadCloud size={17}/>}>
              <p className="iu-tel-acq-note">{portalUsesOfficialAssistant ? 'IUSENTRA importa nel fascicolo interno i file raccolti dalla sessione locale assistita o i dati autorizzati selezionati.' : "L'importazione non scarica dati dai portali in modo nascosto: usa dati autorizzati, file selezionati dall'utente o canale Local Signer quando disponibile."}</p>
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={busy === 'import'} onClick={() => runImport()}><UploadCloud size={15}/> Importa nel gestionale</button>
              </div>
              {Object.keys(documentReport).length ? (
                <div className="iu-tel-acq-document-report" aria-label="Report documenti importazione">
                  {documentReportCards.map(([label, value]) => (
                    <article key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </article>
                  ))}
                  {missingImportNames.length ? (
                    <div className="iu-tel-acq-document-report__notes">
                      <strong>Da verificare</strong>
                      {missingImportNames.slice(0, 4).map((name) => <span key={name}>{name}</span>)}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {Object.keys(importResult).length ? (
                <div className="iu-tel-acq-import-result">
                  <strong>Import completato</strong>
                  <span>{asText(summary.numero_pratica || summary.fascicolo_id || summary.id_fascicolo || summary.message, 'Risultato registrato nel gestionale.')}</span>
                  {asText(summary.fascicolo_url || summary.redirect_url || summary.url) ? <a href={asText(summary.fascicolo_url || summary.redirect_url || summary.url)}>Apri fascicolo importato</a> : null}
                </div>
              ) : null}
            </Panel>
          ) : null}
        </div>

        <aside className="iu-tel-acquisition__side">
          <Panel title="Riepilogo sempre visibile" icon={<BadgeCheck size={17}/>} count={selection ? '1' : '0'}>
            <div className="iu-tel-acq-summary">
              <span><strong>Portale</strong>{portalLabel(portal)}</span>
              <span><strong>Ufficio</strong>{query.ufficioNome || query.ufficio || 'Non indicato'}</span>
              <span><strong>Selezione</strong>{selection?.title || 'Nessun fascicolo selezionato'}</span>
              <span><strong>File manuali</strong>{files.length}</span>
              <span><strong>Mappatura</strong>{mapping.mode.replace('_', ' ')}</span>
              <span><strong>Documenti</strong>{previewCount(preview, 'documenti')}</span>
              <span><strong>Eventi</strong>{previewCount(preview, 'eventi')}</span>
            </div>
          </Panel>
          {visibleRetryEvents.length ? (
            <Panel title="Riprova scarico" subtitle="Tentativi non completati" icon={<RefreshCw size={17}/>} count={visibleRetryEvents.length}>
              <div className="iu-tel-acq-retry-list">
                {visibleRetryEvents.map((item) => (
                  <a href={item.href} key={item.id}>
                    <Badge tone={item.tone}>{item.badge || 'Riprova'}</Badge>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.subtitle}</span>
                      <small>{italianDate(item.timestamp)}</small>
                    </div>
                  </a>
                ))}
              </div>
            </Panel>
          ) : null}
        </aside>
      </div>
    </section>
  )
}

export function TelematicoSurfacePage() {
  const surfaceId = surfaceFromCurrentPath()
  const [data, setData] = useState<TelematicoSurfaceData>(emptyTelematicoSurface)
  const [loading, setLoading] = useState(true)
  const [actionMessage, setActionMessage] = useState('')
  const [activeOperation, setActiveOperation] = useState<{ cardId:string; actionId:string } | null>(null)
  const [localAcquisitionEvents, setLocalAcquisitionEvents] = useState<AcquisitionHistoryEvent[]>(() => readAcquisitionHistory())
  const currentPortalForHistory = portalFromSurface(surfaceId, data)

  useEffect(() => {
    let active = true
    setActiveOperation(null)
    setLoading(true)
    getTelematicoSurfacePage(surfaceId)
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [surfaceId])

  useEffect(() => {
    const refresh = (event?: Event) => {
      const stored = readAcquisitionHistory(currentPortalForHistory)
      const detail = normaliseAcquisitionHistoryEvent((event as CustomEvent | undefined)?.detail)
      if (detail && (!currentPortalForHistory || detail.portal === currentPortalForHistory)) {
        setLocalAcquisitionEvents([
          detail,
          ...stored.filter((item) => item.id !== detail.id && item.href !== detail.href),
        ].slice(0, REACT_ACQUISITION_HISTORY_LIMIT))
        return
      }
      setLocalAcquisitionEvents(stored)
    }
    refresh()
    window.addEventListener('iusentra:portal-acquisition-history', refresh)
    return () => window.removeEventListener('iusentra:portal-acquisition-history', refresh)
  }, [currentPortalForHistory])

  useEffect(() => {
    if (loading || !window.location.hash) return
    const targetId = decodeURIComponent(window.location.hash.slice(1))
    window.requestAnimationFrame(() => scrollToSurfaceTarget(targetId))
  }, [data.surface.id, loading])

  useEffect(() => {
    if (!data.operationCards.length) return
    const hash = window.location.hash
    const card = hash
      ? data.operationCards.find((item) => item.actions.some((action) => action.href.includes(hash))) || data.operationCards[0]
      : data.operationCards[0]
    const action = card.actions.find((item) => hash && item.href.includes(hash)) || card.actions[0]
    if (card && action) {
      setActiveOperation((current) => current || { cardId: card.id, actionId: action.id })
    }
  }, [data.operationCards])

  const postAction = async (action: SurfaceAction) => {
    setActionMessage(`Esecuzione: ${action.label}...`)
    try {
      const response = await fetch(action.href, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'react_surface' }),
      })
      const payload = await response.json().catch(() => ({}))
      const message = typeof payload.messaggio === 'string'
        ? payload.messaggio
        : typeof payload.errore === 'string'
          ? payload.errore
          : response.ok ? 'Operazione completata.' : 'Operazione non completata.'
      setActionMessage(message)
    } catch {
      setActionMessage('Operazione non disponibile in questo momento.')
    }
  }

  const title = data.surface.title || surfaceFallbacks[surfaceId].title
  const tone = data.surface.tone || 'primary'
  const generatedAt = formatGeneratedAt(data.generatedAt)
  const acquisitionVisible = isAcquisitionPath(portalFromSurface(surfaceId, data))
  const selectedCard = data.operationCards.find((card) => card.id === activeOperation?.cardId) || data.operationCards[0]
  const selectedAction = selectedCard?.actions.find((action) => action.id === activeOperation?.actionId) || selectedCard?.actions[0]

  const openSurfaceLex = () => {
    window.dispatchEvent(new CustomEvent('iusentra:lex-context', {
      detail: {
        context: surfaceFallbacks[data.surface.id]?.context || surfaceFallbacks[surfaceId].context,
        title: `Lex AI - ${title}`,
        body: selectedCard?.body || 'Contesto telematico operativo',
        page_path: window.location.pathname,
        context_label: title,
      },
    }))
    window.dispatchEvent(new CustomEvent('iusentra:open-floating-lex'))
  }

  const navigateAction = (event: MouseEvent<HTMLAnchorElement>, card: SurfaceCard, action: SurfaceAction) => {
    if (!isSameSurfaceAction(surfaceId, action)) return
    event.preventDefault()
    setActiveOperation({ cardId: card.id, actionId: action.id })
    const url = sameOriginUrl(action.href)
    if (url) {
      const nextUrl = `${url.pathname}${url.search}${url.hash}`
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`
      if (nextUrl !== currentUrl) {
        window.history.pushState({ telematicoSurface: surfaceId, card: card.id, action: action.id }, '', nextUrl)
      }
    }
    window.requestAnimationFrame(() => scrollToSurfaceTarget('operazione-attiva'))
  }

  return (
    <main className={`iu-content iu-tel-surface-page iu-tel-surface-page--${data.surface.id}`}>
      <section className={`iu-tel-surface-hero iu-tel-surface-hero--${tone}`}>
        <div>
          <span className="iu-tel-surface-hero__eyebrow"><ShieldCheck size={16}/> {data.surface.eyebrow}</span>
          <h1>{title}</h1>
          <p>{data.surface.subtitle}</p>
          <div className="iu-tel-surface-hero__badges">
            <Badge tone="primary">Superficie operativa</Badge>
            <Badge tone="success">Dati aggiornati</Badge>
            <Badge tone="warning">Import autorizzato</Badge>
            <Badge tone="purple">Lex AI</Badge>
          </div>
        </div>
        <aside className="iu-tel-surface-hero__meta">
          <strong>{loading ? 'Sincronizzazione...' : 'Dati aggiornati'}</strong>
          <small>{generatedAt || 'Aggiornamento in corso'}</small>
          {data.surface.officialHref ? <a href={data.surface.officialHref} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Portale ufficiale</a> : null}
        </aside>
      </section>

      {data.notices.length || actionMessage ? (
        <section className="iu-tel-surface-notices">
          {actionMessage ? <article><CheckCircle2 size={18}/><div><strong>Esito azione</strong><span>{actionMessage}</span></div></article> : null}
          {data.notices.map((notice) => (
            <article key={`${notice.title}-${notice.body}`}>
              <AlertTriangle size={18}/>
              <div><strong>{notice.title}</strong><span>{notice.body}</span></div>
            </article>
          ))}
        </section>
      ) : null}

      <section className="iu-tel-surface-stats">
        <Stat label="Pratiche" value={data.summary.total} tone="primary" icon={<FolderOpen size={19}/>}/>
        <Stat label={data.surface.id === 'tribunali' ? 'PEC censite' : 'Import'} value={data.summary.imports} tone="success" icon={<UploadCloud size={19}/>}/>
        <Stat label="Da presidiare" value={data.summary.attention} tone={data.summary.attention ? 'warning' : 'success'} icon={<BadgeCheck size={19}/>}/>
        <Stat label="Blocchi" value={data.summary.blocked} tone={data.summary.blocked ? 'danger' : 'neutral'} icon={<AlertTriangle size={19}/>}/>
        <Stat label="Avvisi" value={data.summary.warnings} tone={data.summary.warnings ? 'warning' : 'neutral'} icon={<FileCheck2 size={19}/>}/>
      </section>

      {!acquisitionVisible ? (
        <section id="acquisizione-portale" className="iu-tel-op-grid iu-tel-anchor-target">
          {data.operationCards.map((card) => (
            <OperationCard
              card={card}
              selected={selectedCard?.id === card.id}
              onPost={postAction}
              onNavigate={navigateAction}
              key={card.id}
            />
          ))}
        </section>
      ) : null}

      {!acquisitionVisible && selectedCard && selectedAction ? (
        <ActiveOperationPanel
          surfaceId={data.surface.id}
          title={title}
          card={selectedCard}
          action={selectedAction}
          onLex={openSurfaceLex}
        />
      ) : null}

      <AcquisitionWizard surfaceId={surfaceId} data={data} localEvents={localAcquisitionEvents}/>

      {data.surface.id === 'tribunali' ? (
        <section className="iu-tel-tribunali-workspace">
          <OfficeDirectory data={data}/>
          <aside className="iu-tel-tribunali-side">
            <SurfaceSidePanels data={data}/>
          </aside>
        </section>
      ) : (
        <section className="iu-tel-surface-grid">
          <div className="iu-tel-surface-main">
            <ChecklistPanel groups={data.checklistGroups} surfaceId={data.surface.id}/>
            <CasesPanel data={data}/>
          </div>
          <aside>
            <SurfaceSidePanels data={data}/>
          </aside>
        </section>
      )}

      <section className="iu-tel-surface-bottom">
        <EventsPanel data={data} localEvents={localAcquisitionEvents}/>
        <LexPanel data={data}/>
      </section>

      <FloatingLex
        context={surfaceFallbacks[data.surface.id]?.context || surfaceFallbacks[surfaceId].context}
        title={`Lex AI - ${title}`}
        body="Posso aiutarti a leggere stato canale, checklist, uffici, documenti, ricevute e prossima azione senza uscire dalla nuova UI."
        primaryHref="#lex"
        primaryLabel="Apri Lex"
        secondaryHref="/telematico"
        secondaryLabel="Centro telematico"
      />
    </main>
  )
}
