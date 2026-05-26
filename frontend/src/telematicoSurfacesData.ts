import type { Tone } from './data'
import { sanitizeDisplayText } from './displayText'
import type {
  TelematicoCase,
  TelematicoChannel,
  TelematicoControlTower,
  TelematicoEvent,
} from './telematicoData'

export type TelematicoSurfaceId =
  | 'polisweb'
  | 'pdp'
  | 'pat'
  | 'ptt'
  | 'tribunali'
  | 'checklist'
  | 'firma'

export type SurfaceAction = {
  id: string
  label: string
  href: string
  tone: Tone
  method: 'GET' | 'POST'
  external: boolean
}

export type SurfaceCard = {
  id: string
  title: string
  body: string
  tone: Tone
  icon: string
  actions: SurfaceAction[]
  metrics: Array<{ label: string; value: number | string }>
}

export type ChecklistItem = {
  id: string
  label: string
  description: string
  critical: boolean
}

export type ChecklistGroup = {
  id: string
  title: string
  items: ChecklistItem[]
}

export type OfficeRow = {
  id: string
  codice: string
  codiceMinistero: string
  nome: string
  descrizione: string
  tipo: string
  distretto: string
  pec: string
  regione: string
  provincia: string
  comune: string
  servizioPst: string
  servizi: string[]
}

export type TelematicoSurfaceData = {
  source: string
  generatedAt: string
  contracts: {
    mock_fallback: boolean
    read_only: boolean
    writes: string
    route_owner: string
  }
  surface: {
    id: TelematicoSurfaceId
    portal: string
    title: string
    eyebrow: string
    subtitle: string
    tone: Tone
    appHref: string
    legacyHref: string
    officialHref: string
  }
  summary: {
    total: number
    imports: number
    attention: number
    blocked: number
    warnings: number
  }
  channel: TelematicoChannel | null
  operationCards: SurfaceCard[]
  checklistGroups: ChecklistGroup[]
  controlTower: TelematicoControlTower
  recentCases: TelematicoCase[]
  recentEvents: TelematicoEvent[]
  links: Array<{ label: string; href: string; kind: string }>
  notices: Array<{ tone: Tone; title: string; body: string }>
  lexSuggestions: string[]
  offices: OfficeRow[]
  officeSummary: {
    source: string
    updatedAt: string
    cachePath: string
    expired: boolean
    perType: Record<string, number>
  }
  localSigner: {
    browserUrl: string
    latestVersion: string
    downloadPage: string
    windowsUrl: string
    macosUrl: string
    linuxUrl: string
  }
}

const emptyControlTower: TelematicoControlTower = {
  pendingOutcomes: [],
  incompleteImports: [],
  warnings: [],
  blockedCases: [],
  predeposito: [],
}

export const emptyTelematicoSurface: TelematicoSurfaceData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: {
    mock_fallback: false,
    read_only: true,
    writes: 'operational_routes',
    route_owner: 'react_shell',
  },
  surface: {
    id: 'polisweb',
    portal: 'pst',
    title: 'PolisWeb / PST',
    eyebrow: 'Servizi telematici',
    subtitle: 'Pagina operativa in caricamento.',
    tone: 'primary',
    appHref: '/polisWeb',
    legacyHref: '/polisWeb',
    officialHref: '',
  },
  summary: { total: 0, imports: 0, attention: 0, blocked: 0, warnings: 0 },
  channel: null,
  operationCards: [],
  checklistGroups: [],
  controlTower: emptyControlTower,
  recentCases: [],
  recentEvents: [],
  links: [],
  notices: [],
  lexSuggestions: [],
  offices: [],
  officeSummary: { source: '', updatedAt: '', cachePath: '', expired: false, perType: {} },
  localSigner: {
    browserUrl: 'http://127.0.0.1:27272',
    latestVersion: '',
    downloadPage: '/impostazioni?tab=firma',
    windowsUrl: '/polisWeb/local-signer/setup/windows',
    macosUrl: '/polisWeb/local-signer/setup/macos',
    linuxUrl: '/polisWeb/local-signer/setup/linux',
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function canonicalHref(value: unknown, fallback = ''): string {
  const raw = text(value, fallback)
  if (!raw.startsWith('/app-v2')) return raw
  if (raw === '/app-v2') return '/'
  return raw.replace(/^\/app-v2(?=\/|$)/, '') || '/'
}

function display(value: unknown, fallback = ''): string {
  return sanitizeDisplayText(text(value, fallback))
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function tone(value: unknown, fallback: Tone = 'neutral'): Tone {
  const raw = text(value).toLowerCase()
  if (['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw)) {
    return raw as Tone
  }
  return fallback
}

function method(value: unknown): 'GET' | 'POST' {
  return text(value).toUpperCase() === 'POST' ? 'POST' : 'GET'
}

function surfaceId(value: unknown): TelematicoSurfaceId {
  const raw = text(value).toLowerCase()
  if (['polisweb', 'pdp', 'pat', 'ptt', 'tribunali', 'checklist', 'firma'].includes(raw)) {
    return raw as TelematicoSurfaceId
  }
  return 'polisweb'
}

function normaliseAction(value: unknown, index: number): SurfaceAction {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `azione-${index}`),
    label: display(item.label, 'Apri'),
    href: canonicalHref(item.href, '#'),
    tone: tone(item.tone, 'primary'),
    method: method(item.method),
    external: bool(item.external),
  }
}

function normaliseCard(value: unknown, index: number): SurfaceCard {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `card-${index}`),
    title: display(item.title, 'Azione operativa'),
    body: display(item.body, ''),
    tone: tone(item.tone, 'primary'),
    icon: text(item.icon, 'workflow'),
    actions: asList(item.actions).map(normaliseAction),
    metrics: asList(item.metrics).map((metric, metricIndex) => {
      const row = isRecord(metric) ? metric : {}
      return {
        label: display(row.label, `Indicatore ${metricIndex + 1}`),
        value: typeof row.value === 'string' ? display(row.value) : number(row.value),
      }
    }),
  }
}

function normaliseChecklistGroup(value: unknown, index: number): ChecklistGroup {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `gruppo-${index}`),
    title: display(item.title, 'Checklist'),
    items: asList(item.items).map((raw, itemIndex) => {
      const row = isRecord(raw) ? raw : {}
      return {
        id: text(row.id, `item-${index}-${itemIndex}`),
        label: display(row.label, 'Controllo'),
        description: display(row.description, ''),
        critical: bool(row.critical),
      }
    }),
  }
}

function normaliseOffice(value: unknown, index: number): OfficeRow {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `ufficio-${index}`),
    codice: text(item.codice),
    codiceMinistero: text(item.codiceMinistero ?? item.codice_ministero),
    nome: display(item.nome, 'Ufficio giudiziario'),
    descrizione: display(item.descrizione ?? item.descrizioneMinistero ?? item.descrizione_ministero),
    tipo: display(item.tipo, 'ALTRO'),
    distretto: display(item.distretto),
    pec: text(item.pec),
    regione: display(item.regione),
    provincia: display(item.provincia),
    comune: display(item.comune),
    servizioPst: display(item.servizioPst ?? item.servizio_pst_predefinito),
    servizi: asList(item.servizi ?? item.serviziMinistero ?? item.servizi_ministero).map((servizio) => display(servizio)).filter(Boolean),
  }
}

function normaliseLocalSigner(value: unknown): TelematicoSurfaceData['localSigner'] {
  const item = isRecord(value) ? value : {}
  return {
    browserUrl: text(item.browserUrl ?? item.browser_url, emptyTelematicoSurface.localSigner.browserUrl),
    latestVersion: text(item.latestVersion ?? item.latest_version ?? item.version),
    downloadPage: text(item.downloadPage ?? item.download_page, emptyTelematicoSurface.localSigner.downloadPage),
    windowsUrl: text(item.windowsUrl ?? item.windows_url, emptyTelematicoSurface.localSigner.windowsUrl),
    macosUrl: text(item.macosUrl ?? item.macos_url, emptyTelematicoSurface.localSigner.macosUrl),
    linuxUrl: text(item.linuxUrl ?? item.linux_url, emptyTelematicoSurface.localSigner.linuxUrl),
  }
}

function normaliseControlItem(value: unknown, index: number, fallbackBadge: string) {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `control-${fallbackBadge}-${index}`),
    portal: text(item.portal) as 'pst' | 'pdp' | 'pat' | 'ptt' | 'altro',
    title: display(item.title, 'Elemento da presidiare'),
    subtitle: display(item.subtitle ?? item.description),
    href: canonicalHref(item.href, '/telematico'),
    tone: tone(item.tone, 'warning'),
    badge: display(item.badge, fallbackBadge),
  }
}

function normaliseControlTower(value: unknown): TelematicoControlTower {
  const item = isRecord(value) ? value : {}
  return {
    pendingOutcomes: asList(item.pendingOutcomes).map((row, index) => normaliseControlItem(row, index, 'esito')),
    incompleteImports: asList(item.incompleteImports).map((row, index) => normaliseControlItem(row, index, 'import')),
    warnings: asList(item.warnings).map((row, index) => normaliseControlItem(row, index, 'warning')),
    blockedCases: asList(item.blockedCases).map((row, index) => normaliseControlItem(row, index, 'bloccato')),
    predeposito: asList(item.predeposito).map((row, index) => normaliseControlItem(row, index, 'predeposito')),
  }
}

function normaliseCase(value: unknown, index: number): TelematicoCase {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `case-${index}`),
    practiceId: text(item.practiceId ?? item.practice_id ?? item.id_fascicolo),
    portal: text(item.portal, 'altro') as TelematicoCase['portal'],
    portalLabel: display(item.portalLabel, 'Telematico'),
    title: display(item.title, 'Pratica telematica'),
    subtitle: display(item.subtitle, ''),
    subject: display(item.subject),
    statusText: display(item.statusText, 'Da verificare'),
    documentsCount: number(item.documentsCount),
    openTasks: number(item.openTasks),
    syncedAt: text(item.syncedAt),
    href: canonicalHref(item.href, '/telematico'),
    tone: tone(item.tone, 'neutral'),
    badges: asList(item.badges).map((badge) => display(badge)).filter(Boolean),
  }
}

function normaliseEvent(value: unknown, index: number): TelematicoEvent {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `event-${index}`),
    portal: text(item.portal, 'altro') as TelematicoEvent['portal'],
    title: display(item.title, 'Attivita telematica'),
    subtitle: display(item.subtitle, ''),
    timestamp: text(item.timestamp),
    href: canonicalHref(item.href, '/telematico'),
    tone: tone(item.tone, 'primary'),
    badge: display(item.badge),
  }
}

function normaliseSurfacePayload(payload: unknown): TelematicoSurfaceData {
  if (!isRecord(payload)) return emptyTelematicoSurface
  const surface = isRecord(payload.surface) ? payload.surface : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  const summary = isRecord(payload.summary) ? payload.summary : {}
  const officeSummary = isRecord(payload.officeSummary) ? payload.officeSummary : {}
  const perType = isRecord(officeSummary.perType) ? officeSummary.perType : {}
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: {
      mock_fallback: bool(contracts.mock_fallback),
      read_only: contracts.read_only !== false,
      writes: text(contracts.writes, 'operational_routes'),
      route_owner: text(contracts.route_owner, 'react_shell'),
    },
    surface: {
      id: surfaceId(surface.id),
      portal: text(surface.portal),
      title: display(surface.title, 'Servizi telematici'),
      eyebrow: display(surface.eyebrow, 'IUSENTRA'),
      subtitle: display(surface.subtitle),
      tone: tone(surface.tone, 'primary'),
      appHref: canonicalHref(surface.appHref, '/telematico'),
      legacyHref: canonicalHref(surface.legacyHref),
      officialHref: text(surface.officialHref),
    },
    summary: {
      total: number(summary.total),
      imports: number(summary.imports),
      attention: number(summary.attention),
      blocked: number(summary.blocked),
      warnings: number(summary.warnings),
    },
    channel: isRecord(payload.channel) ? payload.channel as TelematicoChannel : null,
    operationCards: asList(payload.operationCards).map(normaliseCard),
    checklistGroups: asList(payload.checklistGroups).map(normaliseChecklistGroup),
    controlTower: normaliseControlTower(payload.controlTower),
    recentCases: asList(payload.recentCases).map(normaliseCase),
    recentEvents: asList(payload.recentEvents).map(normaliseEvent),
    links: asList(payload.links).map((link) => {
      const item = isRecord(link) ? link : {}
      return { label: display(item.label, 'Link'), href: canonicalHref(item.href, '#'), kind: display(item.kind, 'link') }
    }),
    notices: asList(payload.notices).map((notice) => {
      const item = isRecord(notice) ? notice : {}
      return { tone: tone(item.tone, 'warning'), title: display(item.title, 'Avviso'), body: display(item.body) }
    }),
    lexSuggestions: asList(payload.lexSuggestions).map((item) => display(item)).filter(Boolean),
    offices: asList(payload.offices).map(normaliseOffice),
    officeSummary: {
      source: text(officeSummary.source),
      updatedAt: text(officeSummary.updatedAt),
      cachePath: text(officeSummary.cachePath),
      expired: bool(officeSummary.expired),
      perType: Object.fromEntries(Object.entries(perType).map(([key, value]) => [key, number(value)])),
    },
    localSigner: normaliseLocalSigner(payload.localSigner),
  }
}

export async function getTelematicoSurfacePage(surface: TelematicoSurfaceId): Promise<TelematicoSurfaceData> {
  try {
    const response = await fetch(`/api/v1/ui/telematico/surface/${encodeURIComponent(surface)}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyTelematicoSurface
    return normaliseSurfacePayload(await response.json())
  } catch {
    return emptyTelematicoSurface
  }
}
