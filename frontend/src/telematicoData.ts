import type { Tone } from './data'
import { sanitizeDisplayText } from './displayText'

export type TelematicoChannelId = 'pst' | 'pdp' | 'pat' | 'ptt'

export type TelematicoChannel = {
  id: TelematicoChannelId
  label: string
  title: string
  description: string
  tone: Tone
  statusText: string
  environmentLabel: string
  cases: number
  importCompleted: number
  attentionNeeded: number
  lastSyncAt: string
  homeHref: string
  importHref: string
  presideHref: string
  browserChannelRequired: boolean
  demoMode: boolean
  pkcs11Mode: boolean
  badges: string[]
  quickActions: Array<{ label: string; href: string; tone?: Tone }>
}

export type TelematicoCase = {
  id: string
  portal: TelematicoChannelId | 'altro'
  portalLabel: string
  title: string
  subtitle: string
  subject: string
  statusText: string
  documentsCount: number
  openTasks: number
  syncedAt: string
  href: string
  tone: Tone
  badges: string[]
}

export type TelematicoEvent = {
  id: string
  portal: TelematicoChannelId | 'altro'
  title: string
  subtitle: string
  timestamp: string
  href: string
  tone: Tone
  badge: string
}

export type TelematicoControlItem = {
  id: string
  portal: TelematicoChannelId | 'altro'
  title: string
  subtitle: string
  href: string
  tone: Tone
  badge: string
}

export type TelematicoControlTower = {
  pendingOutcomes: TelematicoControlItem[]
  incompleteImports: TelematicoControlItem[]
  warnings: TelematicoControlItem[]
  blockedCases: TelematicoControlItem[]
  predeposito: TelematicoControlItem[]
}

export type TelematicoSummary = {
  total: number
  pst: number
  pdp: number
  pat: number
  ptt: number
  pendingOutcomes: number
  incompleteImports: number
  warnings: number
  blocked: number
  attentionNeeded: number
}

export type TelematicoPageData = {
  source: string
  generatedAt: string
  contracts: {
    mock_fallback: boolean
    read_only: boolean
    writes?: string
    route_owner?: string
  }
  summary: TelematicoSummary
  channels: TelematicoChannel[]
  recentCases: TelematicoCase[]
  recentEvents: TelematicoEvent[]
  controlTower: TelematicoControlTower
  notices: Array<{ tone: Tone; title: string; body: string }>
  actions: {
    checklistHref: string
    firmaDigitaleHref: string
    localSignerHref: string
    connectionStatusHref: string
    lexHref: string
    emailHref: string
  }
  lexSuggestions: string[]
}

const channelDefaults: Record<TelematicoChannelId, Omit<TelematicoChannel, 'cases' | 'importCompleted' | 'attentionNeeded' | 'lastSyncAt' | 'statusText' | 'environmentLabel' | 'browserChannelRequired' | 'demoMode' | 'pkcs11Mode' | 'badges' | 'quickActions'>> = {
  pst: {
    id: 'pst',
    label: 'PST / PolisWeb',
    title: 'PST / PolisWeb',
    description: 'Consultazione civile, SIGP e import autorizzato dei fascicoli già scaricati.',
    tone: 'primary',
    homeHref: '/polisWeb',
    importHref: '/portali/pst/acquisizione',
    presideHref: '/telematico?focus=pst',
  },
  pdp: {
    id: 'pdp',
    label: 'PDP Penale',
    title: 'PDP Penale',
    description: 'Workflow penale, esiti, documenti collegati e controllo manual review.',
    tone: 'danger',
    homeHref: '/pdp',
    importHref: '/portali/pdp/acquisizione',
    presideHref: '/telematico?focus=pdp',
  },
  pat: {
    id: 'pat',
    label: 'PAT / SIGA',
    title: 'PAT Amministrativo',
    description: 'Portale avvocato, fascicolo amministrativo e import guidato documenti.',
    tone: 'success',
    homeHref: '/pat',
    importHref: '/portali/pat/acquisizione',
    presideHref: '/telematico?focus=pat',
  },
  ptt: {
    id: 'ptt',
    label: 'PTT / SIGIT',
    title: 'PTT Tributario',
    description: 'Telecontenzioso, SIGIT, fascicoli tributari e ricevute importate.',
    tone: 'warning',
    homeHref: '/app-v2/ptt',
    importHref: '/portali/ptt/acquisizione',
    presideHref: '/telematico?focus=ptt',
  },
}

const emptySummary: TelematicoSummary = {
  total: 0,
  pst: 0,
  pdp: 0,
  pat: 0,
  ptt: 0,
  pendingOutcomes: 0,
  incompleteImports: 0,
  warnings: 0,
  blocked: 0,
  attentionNeeded: 0,
}

const emptyChannels: TelematicoChannel[] = (Object.keys(channelDefaults) as TelematicoChannelId[]).map((id) => ({
  ...channelDefaults[id],
  statusText: 'Da configurare',
  environmentLabel: 'Canale non ancora allineato',
  cases: 0,
  importCompleted: 0,
  attentionNeeded: 0,
  lastSyncAt: '',
  browserChannelRequired: false,
  demoMode: false,
  pkcs11Mode: false,
  badges: ['Da presidiare'],
  quickActions: [
    { label: 'Apri portale', href: channelDefaults[id].homeHref, tone: channelDefaults[id].tone },
    { label: 'Importa da portale', href: channelDefaults[id].importHref, tone: 'primary' },
  ],
}))

export const emptyTelematicoPage: TelematicoPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes', route_owner: 'react_shell' },
  summary: emptySummary,
  channels: emptyChannels,
  recentCases: [],
  recentEvents: [],
  controlTower: {
    pendingOutcomes: [],
    incompleteImports: [],
    warnings: [],
    blockedCases: [],
    predeposito: [],
  },
  notices: [],
  actions: {
    checklistHref: '/deposito/checklist',
    firmaDigitaleHref: '/guida/firma-digitale',
    localSignerHref: '/local-signer',
    connectionStatusHref: '/api/telematico/connection-status',
    lexHref: '#lex',
    emailHref: '/email/',
  },
  lexSuggestions: [],
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
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

function channelId(value: unknown, fallback: TelematicoChannelId = 'pst'): TelematicoChannelId {
  const raw = text(value).toLowerCase()
  if (raw === 'pst' || raw === 'pdp' || raw === 'pat' || raw === 'ptt') return raw
  if (raw.includes('polis')) return 'pst'
  if (raw.includes('penale')) return 'pdp'
  if (raw.includes('amministr')) return 'pat'
  if (raw.includes('tribut')) return 'ptt'
  return fallback
}

function optionalChannelId(value: unknown): TelematicoChannelId | 'altro' {
  const raw = text(value).toLowerCase()
  if (!raw) return 'altro'
  if (raw.includes('polisweb') || raw.includes('pst')) return 'pst'
  if (raw.includes('pdp') || raw.includes('penale')) return 'pdp'
  if (raw.includes('pat') || raw.includes('siga')) return 'pat'
  if (raw.includes('ptt') || raw.includes('sigit') || raw.includes('tribut')) return 'ptt'
  return 'altro'
}

function tone(value: unknown, fallback: Tone = 'neutral'): Tone {
  const raw = text(value).toLowerCase()
  if (['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw)) return raw as Tone
  return fallback
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function textArray(value: unknown): string[] {
  return asList(value).map((item) => display(item)).filter(Boolean)
}

function normaliseAction(value: unknown, fallback: { label: string; href: string; tone?: Tone }) {
  const item = isRecord(value) ? value : {}
  return {
    label: display(item.label, fallback.label),
    href: text(item.href, fallback.href),
    tone: tone(item.tone, fallback.tone || 'neutral'),
  }
}

function normaliseChannel(value: unknown, index: number): TelematicoChannel {
  const item = isRecord(value) ? value : {}
  const id = channelId(item.id ?? item.portale, (Object.keys(channelDefaults) as TelematicoChannelId[])[index] || 'pst')
  const defaults = channelDefaults[id]
  const rawActions = item.quickActions ?? item.quick_actions
  const quickActions = asList(rawActions).length
    ? asList(rawActions).map((action, actionIndex) => normaliseAction(action, [
      { label: 'Apri portale', href: defaults.homeHref, tone: defaults.tone },
      { label: 'Importa da portale', href: defaults.importHref, tone: 'primary' as Tone },
      { label: 'Presidia', href: defaults.presideHref, tone: 'warning' as Tone },
    ][actionIndex] || { label: 'Apri', href: defaults.presideHref }))
    : [
      { label: 'Apri portale', href: text(item.homeHref ?? item.home_url, defaults.homeHref), tone: defaults.tone },
      { label: 'Importa da portale', href: text(item.importHref ?? item.acquisizione_url, defaults.importHref), tone: 'primary' as Tone },
      { label: 'Presidia', href: text(item.presideHref ?? item.preside_href, defaults.presideHref), tone: 'warning' as Tone },
    ]
  return {
    ...defaults,
    label: display(item.label, defaults.label),
    title: display(item.title, defaults.title),
    description: display(item.description, defaults.description),
    tone: tone(item.tone, defaults.tone),
    statusText: display(item.statusText ?? item.status_text, 'Da configurare'),
    environmentLabel: display(item.environmentLabel ?? item.environment_label, ''),
    cases: number(item.cases ?? item.totale),
    importCompleted: number(item.importCompleted ?? item.import_completed),
    attentionNeeded: number(item.attentionNeeded ?? item.attention_needed),
    lastSyncAt: text(item.lastSyncAt ?? item.last_sync_at),
    homeHref: text(item.homeHref ?? item.home_url, defaults.homeHref),
    importHref: text(item.importHref ?? item.acquisizione_url, defaults.importHref),
    presideHref: text(item.presideHref ?? item.preside_href, defaults.presideHref),
    browserChannelRequired: bool(item.browserChannelRequired ?? item.browser_channel_required),
    demoMode: bool(item.demoMode ?? item.demo_mode),
    pkcs11Mode: bool(item.pkcs11Mode ?? item.pkcs11_mode),
    badges: textArray(item.badges).length ? textArray(item.badges) : ['Operativo'],
    quickActions,
  }
}

function normaliseCase(value: unknown, index: number): TelematicoCase {
  const item = isRecord(value) ? value : {}
  const portal = optionalChannelId(item.portal ?? item.portale ?? item.service_code)
  const portalLabel = portal !== 'altro' ? channelDefaults[portal].label : text(item.portalLabel ?? item.portal_label, 'Telematico')
  return {
    id: text(item.id, `case-${index}`),
    portal,
    portalLabel: display(item.portalLabel ?? item.portal_label, portalLabel),
    title: display(item.title, 'Pratica telematica'),
    subtitle: display(item.subtitle, 'Fascicolo collegato al repository telematico'),
    subject: display(item.subject ?? item.oggetto),
    statusText: display(item.statusText ?? item.status_text, 'Da verificare'),
    documentsCount: number(item.documentsCount ?? item.documents_count ?? item.documents),
    openTasks: number(item.openTasks ?? item.open_tasks ?? item.task_aperti),
    syncedAt: text(item.syncedAt ?? item.synced_at ?? item.last_sync_at),
    href: text(item.href, '/telematico'),
    tone: tone(item.tone, 'neutral'),
    badges: textArray(item.badges),
  }
}

function normaliseEvent(value: unknown, index: number): TelematicoEvent {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `event-${index}`),
    portal: optionalChannelId(item.portal ?? item.portale ?? item.service_code),
    title: display(item.title, 'Attivita telematica'),
    subtitle: display(item.subtitle ?? item.description, ''),
    timestamp: text(item.timestamp ?? item.created_at ?? item.time),
    href: text(item.href, '/telematico'),
    tone: tone(item.tone, 'primary'),
    badge: display(item.badge, ''),
  }
}

function normaliseControlItem(value: unknown, index: number, fallbackBadge: string): TelematicoControlItem {
  const item = isRecord(value) ? value : {}
  return {
    id: text(item.id, `control-${fallbackBadge}-${index}`),
    portal: optionalChannelId(item.portal ?? item.portale ?? item.service_code),
    title: display(item.title, 'Elemento da presidiare'),
    subtitle: display(item.subtitle ?? item.description, ''),
    href: text(item.href, '/telematico'),
    tone: tone(item.tone, fallbackBadge === 'bloccato' ? 'danger' : 'warning'),
    badge: display(item.badge, fallbackBadge),
  }
}

function normaliseSummary(payload: Record<string, unknown>, channels: TelematicoChannel[], controlTower: TelematicoControlTower): TelematicoSummary {
  const raw = isRecord(payload.summary) ? payload.summary : {}
  const byId = Object.fromEntries(channels.map((channel) => [channel.id, channel.cases])) as Record<TelematicoChannelId, number>
  const attentionNeeded = channels.reduce((total, channel) => total + channel.attentionNeeded, 0)
  return {
    total: number(raw.total ?? raw.totale ?? channels.reduce((total, channel) => total + channel.cases, 0)),
    pst: number(raw.pst ?? byId.pst),
    pdp: number(raw.pdp ?? byId.pdp),
    pat: number(raw.pat ?? byId.pat),
    ptt: number(raw.ptt ?? byId.ptt),
    pendingOutcomes: number(raw.pendingOutcomes ?? raw.pending_outcomes ?? controlTower.pendingOutcomes.length),
    incompleteImports: number(raw.incompleteImports ?? raw.incomplete_imports ?? controlTower.incompleteImports.length),
    warnings: number(raw.warnings ?? raw.avvisi ?? controlTower.warnings.length),
    blocked: number(raw.blocked ?? raw.bloccati ?? controlTower.blockedCases.length),
    attentionNeeded: number(raw.attentionNeeded ?? raw.attention_needed ?? attentionNeeded),
  }
}

function normalisePayload(payload: unknown): TelematicoPageData {
  if (!isRecord(payload)) return emptyTelematicoPage
  const channels = Array.isArray(payload.channels) && payload.channels.length
    ? payload.channels.map(normaliseChannel)
    : emptyTelematicoPage.channels
  const rawControlValue = payload.controlTower ?? payload.control_tower
  const rawControl = isRecord(rawControlValue) ? rawControlValue : {}
  const controlTower: TelematicoControlTower = {
    pendingOutcomes: asList(rawControl.pendingOutcomes ?? rawControl.pending_outcomes).map((item, index) => normaliseControlItem(item, index, 'esito')),
    incompleteImports: asList(rawControl.incompleteImports ?? rawControl.incomplete_imports).map((item, index) => normaliseControlItem(item, index, 'import')),
    warnings: asList(rawControl.warnings ?? rawControl.warning_cases).map((item, index) => normaliseControlItem(item, index, 'warning')),
    blockedCases: asList(rawControl.blockedCases ?? rawControl.blocked_cases).map((item, index) => normaliseControlItem(item, index, 'bloccato')),
    predeposito: asList(rawControl.predeposito).map((item, index) => normaliseControlItem(item, index, 'predeposito')),
  }
  const actions = isRecord(payload.actions) ? payload.actions : {}
  const contracts = isRecord(payload.contracts) ? payload.contracts : {}
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: {
      mock_fallback: Boolean(contracts.mock_fallback),
      read_only: contracts.read_only !== false,
      writes: text(contracts.writes, 'operational_routes'),
      route_owner: text(contracts.route_owner, 'react_shell'),
    },
    summary: normaliseSummary(payload, channels, controlTower),
    channels,
    recentCases: asList(payload.recentCases ?? payload.recent_cases).map(normaliseCase),
    recentEvents: asList(payload.recentEvents ?? payload.recent_events).map(normaliseEvent),
    controlTower,
    notices: Array.isArray(payload.notices) ? payload.notices.map((notice) => {
      const item = isRecord(notice) ? notice : {}
      return { tone: tone(item.tone, 'warning'), title: display(item.title, 'Avviso operativo'), body: display(item.body) }
    }).filter((item) => item.body || item.title) : [],
    actions: {
      checklistHref: text(actions.checklistHref ?? actions.checklist_href, emptyTelematicoPage.actions.checklistHref),
      firmaDigitaleHref: text(actions.firmaDigitaleHref ?? actions.firma_digitale_href, emptyTelematicoPage.actions.firmaDigitaleHref),
      localSignerHref: text(actions.localSignerHref ?? actions.local_signer_href, emptyTelematicoPage.actions.localSignerHref),
      connectionStatusHref: text(actions.connectionStatusHref ?? actions.connection_status_href, emptyTelematicoPage.actions.connectionStatusHref),
      lexHref: text(actions.lexHref ?? actions.lex_href, emptyTelematicoPage.actions.lexHref),
      emailHref: text(actions.emailHref ?? actions.email_href, emptyTelematicoPage.actions.emailHref),
    },
    lexSuggestions: asList(payload.lexSuggestions ?? payload.lex_suggestions).map((item) => display(item)).filter(Boolean),
  }
}

export async function getTelematicoPage(): Promise<TelematicoPageData> {
  try {
    const response = await fetch('/api/v1/ui/telematico', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyTelematicoPage
    return normalisePayload(await response.json())
  } catch {
    return emptyTelematicoPage
  }
}
