import { useEffect, useMemo, useRef, useState, type ChangeEvent, type MouseEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
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
  importa_parti: boolean
}

type AcquisitionMapping = {
  mode: 'create_new' | 'attach_existing' | 'update_existing'
  target_fascicolo_id: string
  procedimento: string
  materia: string
  grado: string
}

const acquisitionMappingModes: Array<[AcquisitionMapping['mode'], string, string]> = [
  ['create_new', 'Crea nuova pratica', 'Precompila area, procedimento, RG e parti dal portale.'],
  ['attach_existing', 'Collega a pratica esistente', "Mantieni il fascicolo locale come primario e collega l'origine telematica."],
  ['update_existing', 'Aggiorna pratica esistente', 'Aggiorna dati, eventi e sincronizzazione sul fascicolo locale.'],
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
}

type PstSession = {
  sessionId: string
  tribunale: string
  certThumbprint: string
  expiresAt: number
}

const REACT_PST_CERT_KEY = 'iusentra.react.pst.cert'
const REACT_PST_SESSION_KEY = 'iusentra.react.pst.session'
const REACT_PST_SESSION_PURPOSE = 'view'

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
  }
}

function storePstCertificate(cert: PstCertificate | null) {
  writeStoredRecord(REACT_PST_CERT_KEY, cert ? {
    thumbprint: cert.thumbprint,
    soggetto: cert.soggetto,
    emittente: cert.emittente,
    scadenza: cert.scadenza,
    tokenSlot: cert.tokenSlot,
  } : null)
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

function acquisitionInitialMappingMode(targetFascicoloId = acquisitionInitialFascicoloId()): AcquisitionMapping['mode'] {
  const params = new URLSearchParams(window.location.search)
  const requestedMode = asText(params.get('mode')).toLowerCase()
  if (requestedMode === 'attach_existing' || requestedMode === 'update_existing') return requestedMode
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
      <Panel title="Checklist operativa" subtitle="Le spunte restano salvate sul browser della postazione" icon={<ClipboardCheck size={17}/>} count={`${done}/${total}`}>
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

function EventsPanel({ data }:{ data:TelematicoSurfaceData }) {
  return (
    <Panel title="Cronologia" subtitle="Import, esiti e azioni recenti" icon={<RefreshCw size={17}/>} count={data.recentEvents.length}>
      {data.recentEvents.length ? (
        <div className="iu-tel-surface-events">
          {data.recentEvents.map((item) => (
            <a href={item.href} key={item.id}>
              <Badge tone={item.tone}>{item.badge || 'Evento'}</Badge>
              <div>
                <strong>{item.title}</strong>
                <span>{item.subtitle}</span>
                <time>{item.timestamp}</time>
              </div>
            </a>
          ))}
        </div>
      ) : <p className="iu-empty">Nessun evento telematico recente.</p>}
    </Panel>
  )
}

function OfficeDirectory({ data }:{ data:TelematicoSurfaceData }) {
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('tutti')
  const [copied, setCopied] = useState('')
  const types = useMemo(() => ['tutti', ...Object.keys(data.officeSummary.perType || {}).sort()], [data.officeSummary.perType])
  const offices = useMemo(() => {
    const needle = normaliseSearch(query)
    return data.offices.filter((office) => {
      const haystack = normaliseSearch([
        office.nome,
        office.codice,
        office.pec,
        office.tipo,
        office.distretto,
        office.comune,
        office.provincia,
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
              <strong>{office.nome}</strong>
              <span>{[office.codice, office.distretto, office.comune || office.provincia].filter(Boolean).join(' - ')}</span>
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

function requestLocalSignerStart() {
  if (!isDesktopLocalSignerHost()) return
  const iframe = document.createElement('iframe')
  iframe.hidden = true
  iframe.src = 'iusentra-local-signer://restart'
  document.body.appendChild(iframe)
  window.setTimeout(() => iframe.remove(), 3000)
}

function officialPortalHref(portal: string): string {
  const urls: Record<string, string> = {
    pst: 'https://pst.giustizia.it/PST/it/services.page',
    pdp: 'https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp',
    pat: 'https://www.giustizia-amministrativa.it/portale-avvocato',
    ptt: 'https://sigit.giustiziatributaria.gov.it/Sigit/index.do',
  }
  return urls[portal] || ''
}

function isOfficialAssistantPortal(portal: string): boolean {
  return ['pdp', 'pat', 'ptt'].includes(portal)
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
  const value = preview[key]
  if (Array.isArray(value)) return value.length
  if (isRecord(value)) return Object.keys(value).length
  return 0
}

function previewIdentity(preview: JsonRecord): JsonRecord {
  return asRecord(preview.identity || preview.fascicolo || preview.procedimento || preview.ricorso || preview.controversia)
}

function pstPreviewDocuments(preview: JsonRecord): JsonRecord[] {
  const direct = asList(preview.documenti).map(asRecord)
  if (direct.length) return direct
  return asList(preview.depositi).map(asRecord).flatMap((deposito) => {
    const docs = asList(deposito.documenti).map(asRecord)
    return docs.map((documento) => ({
      ...documento,
      id_deposito_pct: asText(documento.id_deposito_pct || deposito.id_deposito_pct),
      id_deposito_esterno: asText(documento.id_deposito_esterno || deposito.id_deposito_esterno || deposito.id_deposito),
      tipo_atto: asText(documento.tipo_atto || deposito.tipo_atto),
      data_deposito: asText(documento.data_deposito || deposito.data_deposito),
      mittente: asText(documento.mittente || deposito.mittente),
    }))
  })
}

function pstDocumentIdentifierValues(item: JsonRecord): string[] {
  const values: string[] = []
  const append = (value: unknown) => {
    const text = asText(value)
    if (!text || text.startsWith('#') || values.includes(text)) return
    values.push(text)
  }
  asList(item.id_documento_candidates).forEach(append)
  ;[
    item.id_documento,
    item.id_documento_portale,
    item.id_cat,
    item.id_repeatto,
    item.msg_id,
    item.numero_documento,
    item.id_doc_mittente,
  ].forEach(append)
  return values
}

function pstDownloadDocumentPayload(item: JsonRecord, original: boolean): JsonRecord {
  return {
    id_documento: asText(item.id_documento || item.id_documento_portale),
    nome_documento: asText(item.nome || item.nome_documento || item.nome_file_originale),
    id_cat: asText(item.id_cat),
    id_repeatto: asText(item.id_repeatto),
    msg_id: asText(item.msg_id),
    numero_documento: asText(item.numero_documento),
    id_doc_mittente: asText(item.id_doc_mittente),
    id_documento_candidates: pstDocumentIdentifierValues(item),
    data_documento: asText(item.data_documento || item.data_deposito),
    id_deposito_esterno: asText(item.id_deposito_esterno || item.id_deposito),
    id_deposito_pct: asText(item.id_deposito_pct),
    tipo_atto: asText(item.tipo_atto),
    tipo: asText(item.tipo),
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
    const filename = asText(row.filename || row.name || row.nome)
    const content = asText(row.content_base64 || row.base64 || row.contenuto_b64)
    if (!filename || !content) continue
    collected.push({
      nome: filename,
      nome_file_originale: filename,
      contenuto_b64: content,
      payload_json: null,
      origine: asText(row.source || row.local_temp_ref, `sessione-assistita:${filename}`),
      data_documento: asText(row.detected_at).slice(0, 10),
      content_type: asText(row.content_type),
      id_documento_portale: asText(row.id_documento_portale || row.id_documento),
      id_deposito_esterno: asText(row.id_deposito_esterno || row.id_deposito),
      id_deposito_pct: asText(row.id_deposito_pct),
      tipo_atto: asText(row.tipo_atto),
      tipo: asText(row.tipo),
      original_documento_portale: originalMode,
      modalita_documento_portale: originalMode ? 'originale' : 'copia',
    })
  }
  return collected
}

function mergeAcquisitionFiles(current: AcquisitionFile[], incoming: AcquisitionFile[]): AcquisitionFile[] {
  const merged = [...current]
  const seen = new Set(current.map((file) => `${file.nome_file_originale.toLowerCase()}::${file.contenuto_b64.slice(0, 48)}`))
  for (const file of incoming) {
    const key = `${file.nome_file_originale.toLowerCase()}::${file.contenuto_b64.slice(0, 48)}`
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
}:{
  surfaceId: TelematicoSurfaceId
  data: TelematicoSurfaceData
}) {
  const portal = portalFromSurface(surfaceId, data)
  const visible = isAcquisitionPath(portal)
  const portalUsesOfficialAssistant = isOfficialAssistantPortal(portal)
  const [step, setStep] = useState(() => (portalUsesOfficialAssistant ? 1 : 2))
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState<JsonRecord>({})
  const [query, setQuery] = useState<AcquisitionQuery>({
    ufficio: '',
    ufficioCodice: '',
    ufficioNome: '',
    numero: '',
    anno: String(new Date().getFullYear()),
    assistito: '',
    controparte: '',
    cf: '',
    oggetto: '',
  })
  const [results, setResults] = useState<AcquisitionResult[]>([])
  const [selection, setSelection] = useState<AcquisitionResult | null>(null)
  const [preview, setPreview] = useState<JsonRecord>({})
  const [analysis, setAnalysis] = useState<JsonRecord>({})
  const [files, setFiles] = useState<AcquisitionFile[]>([])
  const [importResult, setImportResult] = useState<JsonRecord>({})
  const [options, setOptions] = useState<AcquisitionOptions>({
    scarica_originale_portale: portal !== 'pst',
    mantieni_albero_originale: false,
    importa_documenti: true,
    importa_eventi: true,
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
          ? `Local Signer rilevato su questo PC. Aggiornamento consigliato alla versione ${data.localSigner.latestVersion}, ma puoi proseguire con la ricerca.`
          : reachable
            ? 'Local Signer rilevato su questo PC. La ricerca puo usare il canale locale autorizzato.'
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

  const localSignerJson = async (path: string, body?: JsonRecord, timeoutMs = 45000): Promise<JsonRecord> => {
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
        throw new Error('Timeout del Local Signer locale. Verifica che sia avviato e riprova.')
      }
      throw error
    } finally {
      window.clearTimeout(timer)
    }
  }

  const signerCertPreferenceQuery = () => {
    const prefs = asRecord(status.cert_preferences)
    const params = new URLSearchParams()
    if (prefs.auto) params.set('auto', '1')
    const preferIssuer = asText(prefs.prefer_issuer)
    const preferSubject = asText(prefs.prefer_subject)
    const preferCf = asText(prefs.prefer_cf || status.codice_fiscale_avvocato)
    if (preferIssuer) params.set('prefer_issuer', preferIssuer)
    if (preferSubject) params.set('prefer_subject', preferSubject)
    if (preferCf) params.set('prefer_cf', preferCf)
    const queryString = params.toString()
    return queryString ? `?${queryString}` : ''
  }

  const ensurePstCertificate = async (forceDialog = false): Promise<PstCertificate> => {
    if (!forceDialog && pstCert?.thumbprint) return pstCert
    const payload = await localSignerJson(`/seleziona-certificato${signerCertPreferenceQuery()}`, undefined, 120000)
    const cert = {
      thumbprint: asText(payload.thumbprint),
      soggetto: asText(payload.soggetto),
      emittente: asText(payload.emittente),
      scadenza: asText(payload.scadenza),
      tokenSlot: asText(payload.token_slot),
    }
    if (!cert.thumbprint) throw new Error('Seleziona il certificato di firma sul PC e riprova.')
    setPstCert(cert)
    storePstCertificate(cert)
    return cert
  }

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

  const selectOffice = (office: OfficeRow) => {
    setQuery((current) => ({
      ...current,
      ufficio: office.nome,
      ufficioCodice: office.codiceMinistero || office.codice,
      ufficioNome: office.nome,
    }))
  }

  const resolvedOfficeCode = () => {
    if (query.ufficioCodice) return query.ufficioCodice
    const typed = normaliseSearch(query.ufficio)
    const exact = data.offices.find((office) => {
      const code = office.codiceMinistero || office.codice
      return normaliseSearch(office.nome) === typed || normaliseSearch(code) === typed
    })
    return exact?.codiceMinistero || exact?.codice || query.ufficio
  }

  const officeLooksLikeSigp = () => /giudice\s+di\s+pace|\bgdp\b/i.test(`${query.ufficio} ${query.ufficioNome} ${resolvedOfficeCode()}`)

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
    materia: query.oggetto,
    registro: '',
    quick_filter: '',
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
    if (requiresBrowserLocalSigner && !localSigner.ok) {
      setStep(1)
      setMessage('Verifico Local Signer sul PC e proseguo appena il servizio locale risponde.')
      const checkedSigner = await checkLocalSigner(false)
      if (!checkedSigner.ok) {
        setMessage('Local Signer non raggiungibile sul PC. Avvialo dal pacchetto installato e ripeti la ricerca.')
        return
      }
      setStep(2)
    }
    setBusy('search')
    setMessage('')
    setImportResult({})
    try {
      let rows: AcquisitionResult[] = []
      if (portal === 'pst') {
        const tribunale = resolvedOfficeCode()
        let signerPayload: JsonRecord | null = null
        let cert = await ensurePstCertificate()
        let session = activePstSessionFor(tribunale, cert)
        if (canUsePstSearchSnapshot()) {
          try {
            signerPayload = await localSignerJson('/pst/ricerca-snapshot', {
              tribunale,
              numero_rg: query.numero,
              anno_rg: query.anno,
              nome_parte: query.assistito || query.controparte,
              cf_parte: query.cf,
              oggetto: query.oggetto,
              ufficio_nome: query.ufficioNome || query.ufficio,
              cf_avvocato: asText(status.codice_fiscale_avvocato),
              cert_thumbprint: cert.thumbprint || null,
              cert_key: cert.thumbprint || '',
              purpose: REACT_PST_SESSION_PURPOSE,
              pst_session_id: session?.sessionId || '',
            }, 120000)
          } catch (error: unknown) {
            const message = asText(error instanceof Error ? error.message : error)
            if (!/not found/i.test(message)) throw error
          }
        }
        if (!signerPayload) {
          cert = await ensurePstCertificate()
          session = activePstSessionFor(tribunale, cert)
          signerPayload = await localSignerJson('/pst/ricerca', {
            tribunale,
            numero_rg: query.numero,
            anno_rg: query.anno,
            nome_parte: query.assistito || query.controparte,
            cf_parte: query.cf,
            cf_avvocato: asText(status.codice_fiscale_avvocato),
            cert_thumbprint: cert.thumbprint || null,
            cert_key: cert.thumbprint || '',
            purpose: REACT_PST_SESSION_PURPOSE,
            pst_session_id: session?.sessionId || '',
          }, 120000)
        }
        const nextSession = rememberPstSession(signerPayload, tribunale, cert) || session
        if (!nextSession) throw new Error('Sessione PST non inizializzata dal Local Signer.')
        const snapshot = asRecord(signerPayload.snapshot)
        rows = asList(signerPayload.fascicoli || signerPayload.results).map((row, index) => {
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
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      setMessage(asText(error instanceof Error ? error.message : error, 'Ricerca non disponibile.'))
    } finally {
      setBusy('')
    }
  }

  const runPreview = async () => {
    if (!selection) {
      setMessage('Seleziona prima un fascicolo dal risultato della ricerca.')
      return
    }
    setBusy('preview')
    try {
      let payload: JsonRecord
      if (portal === 'pst') {
        const tribunale = asText(selection.raw.ufficio_codice || resolvedOfficeCode())
        let snapshot = asRecord(selection.raw.snapshot)
        let documenti = asList(snapshot.documenti).map(asRecord)
        let pstSessionPayload = asRecord(selection.raw.pst_session)
        if (!documenti.length) {
          const cert = await ensurePstCertificate()
          const session = activePstSessionFor(tribunale, cert)
          const signerPayload = await localSignerJson('/pst/fascicolo-snapshot', {
            selection: selection.raw,
            codice_ufficio: tribunale,
            numero_rg: asText(selection.raw.numero || query.numero),
            anno_rg: asText(selection.raw.anno || query.anno),
            id_fascicolo: asText(selection.raw.id_fascicolo),
            sub_procedimento: asText(selection.raw.sub_procedimento),
            cf_avvocato: asText(status.codice_fiscale_avvocato),
            cert_thumbprint: cert.thumbprint || null,
            cert_key: cert.thumbprint || '',
            purpose: REACT_PST_SESSION_PURPOSE,
            pst_session_id: session?.sessionId || '',
          }, 120000)
          const nextSession = rememberPstSession(signerPayload, tribunale, cert) || session
          if (!nextSession) throw new Error('Sessione PST non inizializzata dal Local Signer.')
          snapshot = asRecord(signerPayload.snapshot)
          documenti = asList(snapshot.documenti || signerPayload.documenti).map(asRecord)
          pstSessionPayload = pstSessionForServer(nextSession, cert)
        }
        payload = await portalJson(portal, 'preview', {
          selection: {
            ...selection.raw,
            snapshot,
            pst_session: pstSessionPayload,
          },
          snapshot,
          documenti,
          pst_session: pstSessionPayload,
        })
      } else {
        payload = await portalJson(portal, 'preview', { selection: selection.raw })
      }
      if (payload.ok === false) throw new Error(asText(payload.errore, 'Anteprima non completata.'))
      setPreview(asRecord(payload.preview))
      setStep(3)
      setMessage('Anteprima caricata: verifica dati, parti, eventi e documenti.')
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      setMessage(asText(error instanceof Error ? error.message : error, 'Anteprima non disponibile.'))
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
      const payload = await portalJson(portal, 'analyze', {
        selection: selection.raw,
        preview,
        options,
        mapping,
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

  const runImport = async (overrideFiles?: AcquisitionFile[]) => {
    let activeFiles = overrideFiles || files
    if (portalUsesOfficialAssistant && assistantSession?.downloaded_files?.length) {
      activeFiles = mergeAcquisitionFiles(
        activeFiles,
        assistantFilesToAcquisitionFiles(assistantSession.downloaded_files, options.scarica_originale_portale),
      )
    }
    const payloadJson = authorisedPayload(activeFiles)
    const downloadedFiles: unknown[] = activeFiles.filter((file) => !file.payload_json)
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
    try {
      let activeSelection: JsonRecord = selection?.raw || {}
      if (!payloadJson && portal === 'pst' && options.importa_documenti && !downloadedFiles.length) {
        const documenti = pstPreviewDocuments(preview)
          .map((item) => pstDownloadDocumentPayload(item, options.scarica_originale_portale))
          .filter((item) => pstDocumentIdentifierValues(item).length)
        if (documenti.length) {
          const tribunale = asText(activeSelection.ufficio_codice || resolvedOfficeCode())
          const cert = await ensurePstCertificate()
          let session = activePstSessionFor(tribunale, cert)
          const signerPayload = await localSignerJson('/pst/download-documenti-batch', {
            tribunale,
            cf_avvocato: asText(status.codice_fiscale_avvocato),
            cert_thumbprint: cert.thumbprint || null,
            cert_key: cert.thumbprint || '',
            purpose: REACT_PST_SESSION_PURPOSE,
            pst_session_id: session?.sessionId || '',
            preflight_auth: false,
            original: options.scarica_originale_portale,
            documents: documenti,
          }, 360000)
          const nextSession = rememberPstSession(signerPayload, tribunale, cert) || session
          if (!nextSession) throw new Error('Sessione PST non inizializzata dal Local Signer.')
          const signerFiles = asList(signerPayload.files).map(asRecord)
          const failures = asList(signerPayload.failures).map(asRecord)
          if (!signerFiles.length) {
            throw new Error(asText(failures[0]?.errore || failures[0]?.message, 'Nessun documento scaricato dal portale ufficiale.'))
          }
          downloadedFiles.push(...signerFiles)
          activeSelection = {
            ...activeSelection,
            pst_session: pstSessionForServer(nextSession, cert),
          }
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
          })
      } else if (portalUsesOfficialAssistant && downloadedFiles.length) {
        payload = await portalJson(portal, 'importa-file', {
          fascicolo_id: mapping.target_fascicolo_id,
          assistant_session_id: assistantSession?.session_id || '',
          downloaded_files: downloadedFiles,
          options,
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
            preview,
            options,
            mapping,
            downloaded_files: downloadedFiles,
            pst_session: isRecord(activeSelection.pst_session) ? activeSelection.pst_session : {},
          })
      }
      if (payload.ok === false) throw new Error(asText(payload.errore, 'Importazione non completata.'))
      setImportResult(payload)
      setFiles(activeFiles)
      setStep(7)
      setMessage('Importazione completata o presa in carico dal gestionale operativo.')
    } catch (error: unknown) {
      if (portal === 'pst' && isPstSessionExpiredError(error)) clearPstSession()
      setMessage(asText(error instanceof Error ? error.message : error, 'Importazione non disponibile.'))
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
  const blockers = issueRows(analysis, 'blockers')
  const warnings = issueRows(analysis, 'warnings')
  const oks = issueRows(analysis, 'ok')
  const summary = importSummary(importResult)
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
          ) : official ? <a href={official} target="_blank" rel="noreferrer"><ExternalLink size={14}/> Portale ufficiale</a> : null}
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

      <div className="iu-tel-acquisition__grid">
        <div className="iu-tel-acquisition__main">
          {step === 1 ? (
            <Panel title="Step 1 - Accesso" subtitle="Stato tecnico del canale autorizzato" icon={<MonitorCheck size={17}/>}>
              <div className="iu-tel-acq-status">
                <span><strong>Canale</strong>{portalLabel(portal)}</span>
                <span><strong>Stato</strong>{asText(status.status_text || status.label || status.mode, 'Da verificare')}</span>
                <span><strong>Local Signer</strong>{localSigner.unsupported ? 'Solo desktop' : localSigner.ok ? 'Rilevato sul PC' : localSigner.outdated ? 'Da aggiornare' : 'Da verificare dal browser'}</span>
                <button type="button" disabled={localSigner.checking || localSigner.unsupported} onClick={() => checkLocalSigner(false)}>
                  <RefreshCw size={15}/> {localSigner.checking ? 'Verifica...' : 'Verifica Local Signer'}
                </button>
              </div>
              <div className={`iu-tel-local-signer-card ${localSigner.ok ? 'is-ok' : localSigner.outdated ? 'is-warning' : 'is-missing'}`}>
                <ShieldCheck size={18}/>
                <div>
                  <strong>{localSigner.unsupported ? 'Disponibile solo su desktop' : localSigner.ok ? 'Local Signer pronto' : localSigner.outdated ? 'Aggiornamento richiesto' : 'Controllo locale richiesto'}</strong>
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
                        <button type="button" key={office.id} onClick={() => selectOffice(office)} className={(query.ufficioCodice && query.ufficioCodice === (office.codiceMinistero || office.codice)) ? 'is-selected' : ''}>
                          <strong>{office.nome}</strong>
                          <small>{[office.tipo, office.distretto, office.comune || office.provincia, office.codiceMinistero || office.codice, office.servizioPst].filter(Boolean).join(' - ')}</small>
                        </button>
                      ))
                    ) : (
                      <span>Nessun ufficio trovato nel catalogo importato. Prova con comune, distretto, codice o tipo ufficio.</span>
                    )}
                  </div>
                </label>
                <label><span>Numero</span><input value={query.numero} onChange={(event) => updateQuery('numero', event.currentTarget.value)} placeholder="Es. 466"/></label>
                <label><span>Anno</span><input value={query.anno} onChange={(event) => updateQuery('anno', event.currentTarget.value)} inputMode="numeric"/></label>
                <label><span>Parte assistita</span><input value={query.assistito} onChange={(event) => updateQuery('assistito', event.currentTarget.value)} placeholder="Cliente, imputato, ricorrente..."/></label>
                <label><span>Controparte</span><input value={query.controparte} onChange={(event) => updateQuery('controparte', event.currentTarget.value)} placeholder="Controparte, resistente, parte offesa..."/></label>
                <label><span>CF / P.IVA</span><input value={query.cf} onChange={(event) => updateQuery('cf', event.currentTarget.value)} placeholder="Codice fiscale o partita IVA"/></label>
                <label className="iu-tel-acq-form__wide"><span>Oggetto / materia</span><input value={query.oggetto} onChange={(event) => updateQuery('oggetto', event.currentTarget.value)} placeholder="Oggetto, materia, reato, rito..."/></label>
              </div>
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={busy === 'search' || portalUsesOfficialAssistant || (portalNeedsLocalSigner && !localSignerDesktopSupported)} onClick={runSearch}><Search size={15}/> {portalUsesOfficialAssistant ? 'Ricerca nella sessione assistita' : 'Cerca fascicolo'}</button>
                <button type="button" disabled={!selection || busy === 'preview' || portalUsesOfficialAssistant} onClick={runPreview}><FileText size={15}/> Carica anteprima</button>
                {portalUsesOfficialAssistant ? <button type="button" onClick={() => setStep(4)}><ArrowRight size={15}/> Vai ai file raccolti</button> : null}
              </div>
              <div className="iu-tel-acq-results">
                {results.map((result) => (
                  <button type="button" className={selection?.id === result.id ? 'is-selected' : ''} onClick={() => setSelection(result)} key={result.id}>
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
                <div className="iu-tel-acq-preview">
                  <article><span>Procedimento</span><strong>{asText(identity.numero_rg || identity.rg || identity.numero || selection?.title, 'n.d.')}</strong><small>{asText(identity.ufficio || identity.tribunale || identity.court, 'Ufficio non indicato')}</small></article>
                  <article><span>Parti</span><strong>{previewCount(preview, 'parti')}</strong><small>Parti/anagrafiche rilevate</small></article>
                  <article><span>Documenti</span><strong>{previewCount(preview, 'documenti') + previewCount(preview, 'depositi')}</strong><small>Documenti o buste disponibili</small></article>
                  <article><span>Eventi</span><strong>{previewCount(preview, 'eventi')}</strong><small>Cronologia importabile</small></article>
                </div>
              ) : <p className="iu-empty">Carica l'anteprima dopo aver selezionato il fascicolo.</p>}
              <div className="iu-tel-acq-actions">
                <button type="button" disabled={!Object.keys(preview).length} onClick={() => setStep(4)}><ArrowRight size={15}/> Scegli cosa importare</button>
              </div>
            </Panel>
          ) : null}

          {step === 4 ? (
            <Panel title="Step 4 - Selezione" subtitle="Scegli documenti, eventi, parti e file autorizzati" icon={<ClipboardCheck size={17}/>}>
              <div className="iu-tel-acq-switches">
                <label><input type="checkbox" checked={options.importa_documenti} onChange={(event) => updateOption('importa_documenti', event.currentTarget.checked)}/> Importa documenti</label>
                <label><input type="checkbox" checked={options.importa_eventi} onChange={(event) => updateOption('importa_eventi', event.currentTarget.checked)}/> Importa eventi</label>
                <label><input type="checkbox" checked={options.importa_parti} onChange={(event) => updateOption('importa_parti', event.currentTarget.checked)}/> Importa parti</label>
                <label><input type="checkbox" checked={options.scarica_originale_portale} onChange={(event) => updateOption('scarica_originale_portale', event.currentTarget.checked)}/> Originale portale</label>
                <label><input type="checkbox" checked={options.mantieni_albero_originale} onChange={(event) => updateOption('mantieni_albero_originale', event.currentTarget.checked)}/> Mantieni struttura originale</label>
              </div>
              {portal === 'pst' ? <p className="iu-tel-acq-note">Default PST: copia di consultazione con annotazioni ministeriali. L'originale si usa solo se selezionato espressamente.</p> : null}
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
                <label><span>Fascicolo locale da aggiornare</span><select value={mapping.target_fascicolo_id} onChange={(event) => updateMapping('target_fascicolo_id', event.currentTarget.value)}>
                  <option value="">Seleziona se necessario</option>
                  {data.recentCases.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}
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
                <button type="button" onClick={() => setStep(5)}><ArrowRight size={15}/> Vai alla mappatura</button>
              </div>
            </Panel>
          ) : null}

          {step === 5 ? (
            <Panel title="Step 5 - Mappatura nel gestionale" subtitle="Decidi se creare, collegare o aggiornare una pratica esistente" icon={<FolderOpen size={17}/>}>
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
                <label><span>Fascicolo locale target</span><select value={mapping.target_fascicolo_id} onChange={(event) => updateMapping('target_fascicolo_id', event.currentTarget.value)}>
                  <option value="">Seleziona se necessario</option>
                  {data.recentCases.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}
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
              {[...blockers, ...warnings].slice(0, 8).map((issue, index) => (
                <p className="iu-tel-acq-issue" key={`${asText(issue.code, 'issue')}-${index}`}>
                  <strong>{asText(issue.code || issue.title || issue.categoria, 'Controllo')}</strong>
                  <span>{asText(issue.message || issue.human_message || issue.detail || issue.descrizione, 'Verifica richiesta')}</span>
                </p>
              ))}
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
              <span><strong>Documenti</strong>{previewCount(preview, 'documenti') + previewCount(preview, 'depositi')}</span>
              <span><strong>Eventi</strong>{previewCount(preview, 'eventi')}</span>
            </div>
          </Panel>
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

      <AcquisitionWizard surfaceId={surfaceId} data={data}/>

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
        <EventsPanel data={data}/>
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
