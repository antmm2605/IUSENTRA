export type Tone = 'primary'|'info'|'success'|'warning'|'danger'|'purple'|'orange'|'neutral'
export type Metric = { id:string; label:string; value:string|number; tag?:string; tone:Tone; href?:string; actionLabel?:string }
export type Row = { id:string; title:string; subtitle:string; time?:string; avatar?:string; unread?:boolean; badge?:string; tone?:Tone; href?:string }
export type Dossier = { id:string; area:string; title:string; meta:string; score:number; moves:string[]; href:string; tone:Tone }
export type Source = { id:string; title:string; description:string; href:string; badge?:string; tone:Tone }
/**
 * Stato del quadro operativo:
 * - `ok`       tutti gli archivi hanno risposto;
 * - `parziale` una o piu' sorgenti non hanno risposto (conteggi non attendibili);
 * - `errore`   la Panoramica non e' raggiungibile: i valori mostrati sono zeri di cortesia.
 */
export type DashboardStatus = 'ok'|'parziale'|'errore'
export type DashboardData = {
  status: DashboardStatus
  warning: string
  degradedSources: string[]
  generatedAt: string
  metrics: Metric[]
  pec: Row[]
  emails: Row[]
  messages: Row[]
  agenda: Row[]
  operations: Row[]
  /** Coda «Da lavorare adesso»: processi aperti ordinati per urgenza, ogni voce apre il suo evento. */
  worklist: Row[]
  completion: { percent:number; totalMissing:number; items:Array<{label:string; count:number}> }
  engagements: Row[]
  matters: Row[]
  deadlines: Array<{label:string; count:number; percent:number; tone:Tone}>
  economic: Array<{label:string; value:string; note?:string; delta?:string}>
  notificationPresidia: Row[]
  billingWork: Row[]
  lex: string[]
  dossiers: Dossier[]
  sources: Source[]
}

const emptyMetrics: Metric[] = [
  {id:'urgent',label:'Azioni urgenti',value:0,tag:'',tone:'danger',href:'/workspace-intelligente',actionLabel:'Vai alle azioni'},
  {id:'pec',label:'PEC da leggere',value:0,tag:'',tone:'primary',href:'/email/',actionLabel:'Apri PEC'},
  {id:'messages',label:'Messaggi clienti',value:0,tag:'',tone:'success',href:'/messaggi',actionLabel:'Vai ai messaggi'},
  {id:'quotes',label:'Preventivi in scadenza',value:0,tag:'',tone:'purple',href:'/preventivi',actionLabel:'Apri preventivi'},
  {id:'engagements',label:'Conferimenti mancanti',value:0,tag:'',tone:'orange',href:'/preventivi',actionLabel:'Completa ora'}
]

export const emptyDashboard: DashboardData = {
  status: 'ok',
  warning: '',
  degradedSources: [],
  generatedAt: '',
  metrics: emptyMetrics,
  pec: [],
  emails: [],
  messages: [],
  agenda: [],
  operations: [],
  worklist: [],
  completion: {percent:100,totalMissing:0,items:[{label:'Clienti',count:0},{label:'Soggetti',count:0}]},
  engagements: [],
  matters: [],
  deadlines: [
    {label:'0 scadenze critiche',count:0,percent:0,tone:'danger'},
    {label:'0 scadenze ad alta priorita',count:0,percent:0,tone:'warning'},
    {label:'0 scadenze a priorita media',count:0,percent:0,tone:'primary'},
    {label:'0 scadenze a bassa priorita',count:0,percent:0,tone:'success'}
  ],
  economic: [
    {label:'Fatturato mese',value:'€ 0,00',note:'0 parcelle emesse'},
    {label:'Incassi mese',value:'€ 0,00',note:'0 pagamenti registrati'},
    {label:'Da incassare',value:'€ 0,00',note:'0 parcelle aperte'},
    {label:'Ore lavorate',value:'0 h',note:'0 voci timesheet'}
  ],
  notificationPresidia: [],
  billingWork: [],
  lex: [],
  dossiers: [],
  sources: []
}

export const dashboardFallback = emptyDashboard
const DASHBOARD_MAILBOX_SYNC_TIMEOUT_MS = 18000
const DASHBOARD_UNREACHABLE_WARNING =
  'Panoramica non raggiungibile: i valori mostrati non provengono dagli archivi dello studio. Riprova con Aggiorna.'

/** Quadro non attendibile: zeri di cortesia dichiarati come tali, mai spacciati per dati reali. */
function unreachableDashboard(): DashboardData {
  return {...emptyDashboard, status: 'errore', warning: DASHBOARD_UNREACHABLE_WARNING}
}

function asDashboardStatus(value: unknown): DashboardStatus {
  return value === 'parziale' || value === 'errore' ? value : 'ok'
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? '')).filter(Boolean) : []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asTone(value: unknown, fallback: Tone = 'neutral'): Tone {
  return value === 'primary' || value === 'info' || value === 'success' || value === 'warning' || value === 'danger' || value === 'purple' || value === 'orange' || value === 'neutral'
    ? value
    : fallback
}

function asOptionalString(value: unknown): string | undefined {
  const normalized = String(value ?? '').trim()
  return normalized || undefined
}

function asRows(value: unknown): Row[] {
  const rows = Array.isArray(value) ? value : isRecord(value) && Array.isArray(value.items) ? value.items : []
  return rows.flatMap((entry, index): Row[] => {
    if (!isRecord(entry)) return []
    const title = asOptionalString(entry.title ?? entry.subject ?? entry.label)
    // Un record incompleto non deve far cadere la pagina: resta comunque
    // riconoscibile nella lista e permette al dato successivo di essere letto.
    return [{
      id: asOptionalString(entry.id ?? entry.key) ?? `riga-${index}`,
      title: title ?? 'Elemento operativo senza titolo',
      subtitle: String(entry.subtitle ?? entry.description ?? ''),
      time: asOptionalString(entry.time ?? entry.datetime ?? entry.date),
      avatar: asOptionalString(entry.avatar),
      unread: entry.unread === true || entry.unread === 1,
      badge: asOptionalString(entry.badge),
      tone: asTone(entry.tone),
      href: asOptionalString(entry.href ?? entry.url),
    }]
  })
}

function asMetrics(payload: Record<string, unknown>): Metric[] {
  if (Array.isArray(payload.metrics) && payload.metrics.length) {
    const metrics = payload.metrics.flatMap((entry, index): Metric[] => {
      if (!isRecord(entry)) return []
      const fallback = emptyMetrics.find((metric) => metric.id === entry.id) ?? emptyMetrics[index] ?? emptyMetrics[0]
      return [{
        id: asOptionalString(entry.id) ?? fallback.id,
        label: asOptionalString(entry.label) ?? fallback.label,
        value: typeof entry.value === 'string' || typeof entry.value === 'number' ? entry.value : fallback.value,
        tag: asOptionalString(entry.tag),
        tone: asTone(entry.tone, fallback.tone),
        href: asOptionalString(entry.href) ?? fallback.href,
        actionLabel: asOptionalString(entry.actionLabel ?? entry.action_label) ?? fallback.actionLabel,
      }]
    })
    if (metrics.length) return metrics
  }
  const stats = isRecord(payload.stats) ? payload.stats : {}
  return emptyMetrics.map((metric) => {
    const value =
      metric.id === 'urgent' ? stats.urgentActions :
      metric.id === 'pec' ? stats.pecUnread :
      metric.id === 'messages' ? stats.clientMessages :
      metric.id === 'quotes' ? stats.expiringQuotes :
      metric.id === 'engagements' ? stats.missingAssignments :
      metric.value
    return {...metric, value: (value as string|number|undefined) ?? metric.value}
  })
}

function asCompletion(value: unknown) {
  if (!isRecord(value)) return emptyDashboard.completion
  const items = Array.isArray(value.items)
    ? value.items.flatMap((entry): Array<{label:string; count:number}> => isRecord(entry) ? [{
        label: asOptionalString(entry.label) ?? 'Dato da completare',
        count: asNumber(entry.count),
      }] : [])
    : emptyDashboard.completion.items
  return {
    percent: asNumber(value.percent ?? emptyDashboard.completion.percent),
    totalMissing: asNumber(value.totalMissing ?? value.total_missing ?? emptyDashboard.completion.totalMissing),
    items: items.length ? items : emptyDashboard.completion.items,
  }
}

function asNumber(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function dossierScore(row: Row, index: number): number {
  if (row.tone === 'danger') return 18 - index
  if (row.tone === 'orange' || row.tone === 'warning') return 12 - index
  return Math.max(1, 8 - index)
}

function asDossiers(payload: Record<string, unknown>): Dossier[] {
  const rows = asRows(payload.high_priority_matters)
  return rows.map((row, index) => ({
    id: row.id || `dossier-${index}`,
    area: row.badge || 'FASCICOLO',
    title: row.title,
    meta: row.subtitle || 'Dati fascicolo collegati agli archivi operativi',
    score: dossierScore(row, index),
    moves: [
      'Verificare scadenze, udienze e documenti recenti del fascicolo.',
      'Aggiornare attività e prossime azioni nella regia operativa.',
      'Avviare una ricerca giurisprudenziale collegata all’oggetto della pratica.'
    ],
    href: row.href || '/fascicoli',
    tone: asTone(row.tone),
  }))
}

function asDeadlineDistribution(value: unknown): DashboardData['deadlines'] {
  if (!Array.isArray(value)) return emptyDashboard.deadlines
  const deadlines = value.flatMap((entry): DashboardData['deadlines'] => isRecord(entry) ? [{
    label: asOptionalString(entry.label) ?? 'Scadenze non classificate',
    count: asNumber(entry.count),
    percent: asNumber(entry.percent),
    tone: asTone(entry.tone),
  }] : [])
  return deadlines.length ? deadlines : emptyDashboard.deadlines
}

function asEconomic(value: unknown): DashboardData['economic'] {
  if (!Array.isArray(value)) return emptyDashboard.economic
  const rows = value.flatMap((entry): DashboardData['economic'] => isRecord(entry) ? [{
    label: asOptionalString(entry.label) ?? 'Voce economica',
    value: String(entry.value ?? '€ 0,00'),
    note: asOptionalString(entry.note),
    delta: asOptionalString(entry.delta),
  }] : [])
  return rows.length ? rows : emptyDashboard.economic
}

function asSources(payload: Record<string, unknown>, dashboard: Omit<DashboardData, 'dossiers'|'sources'>): Source[] {
  const stats = isRecord(payload.stats) ? payload.stats : {}
  const openMatters = asNumber(stats.openMatters)
  const urgentDeadlines = asNumber(stats.urgentDeadlines)
  const pecUnread = asNumber(stats.pecUnread)
  const clientMessages = asNumber(stats.clientMessages)
  const unpaidAmount = String(stats.unpaidAmount ?? '€ 0,00')
  const totalDeadlines = dashboard.deadlines.reduce((total, item) => total + asNumber(item.count), 0)
  return [
    {
      id: 'source-scadenziario',
      title: 'Scadenziario',
      description: `${totalDeadlines} termini aperti classificati per priorità; ${urgentDeadlines} risultano urgenti nel riepilogo operativo.`,
      href: '/scadenziario',
      badge: `${totalDeadlines}`,
      tone: totalDeadlines ? 'warning' : 'neutral',
    },
    {
      id: 'source-agenda',
      title: 'Agenda e calendari',
      description: `${dashboard.agenda.length} appuntamenti nell’orizzonte della dashboard, pronti per sincronizzazione calendari.`,
      href: '/agenda',
      badge: `${dashboard.agenda.length}`,
      tone: dashboard.agenda.length ? 'primary' : 'neutral',
    },
    {
      id: 'source-fascicoli',
      title: 'Fascicoli',
      description: `${openMatters} fascicoli attivi e ${dashboard.matters.length} pratiche con priorita alta nel riepilogo operativo.`,
      href: '/fascicoli',
      badge: `${openMatters}`,
      tone: dashboard.matters.length ? 'orange' : 'neutral',
    },
    {
      id: 'source-comunicazioni',
      title: 'PEC, email e messaggi',
      description: `${pecUnread} PEC da leggere, ${dashboard.emails.length} email recenti e ${clientMessages} messaggi cliente recenti.`,
      href: '/email/',
      badge: `${pecUnread + clientMessages}`,
      tone: pecUnread || clientMessages ? 'primary' : 'neutral',
    },
    {
      id: 'source-economico',
      title: 'Economico rapido',
      description: `Importo da incassare: ${unpaidAmount}. La sezione usa fatturazione, pagamenti e timesheet reali.`,
      href: '/fatturazione/',
      badge: dashboard.economic.length ? 'OK' : '',
      tone: dashboard.economic.length ? 'success' : 'neutral',
    },
  ]
}

export async function getDashboard(options: { refresh?: boolean } = {}): Promise<DashboardData> {
  try {
    const query = new URLSearchParams()
    if (options.refresh) query.set('refresh', '1')
    const suffix = query.toString() ? `?${query.toString()}` : ''
    const res = await fetch(`/api/v1/ui/dashboard${suffix}`, {
      credentials:'same-origin',
      headers:{Accept:'application/json'}
    })
    if (!res.ok) return unreachableDashboard()
    const payload = await res.json() as Record<string, unknown>
    const warning = String(payload.warning ?? '')
    const status = asDashboardStatus(payload.status ?? (warning ? 'parziale' : 'ok'))
    const dashboard = {
      status,
      warning,
      degradedSources: asStringList(payload.degraded_sources),
      generatedAt: String(payload.generated_at_rome ?? payload.generated_at ?? ''),
      metrics: asMetrics(payload),
      pec: asRows(payload.pec),
      emails: asRows(payload.emails),
      messages: asRows(payload.client_messages ?? payload.messages),
      agenda: asRows(payload.agenda),
      operations: asRows(payload.today_operations ?? payload.operations),
      worklist: asRows(payload.worklist),
      completion: asCompletion(payload.incomplete_registry),
      engagements: asRows(payload.missing_engagements),
      matters: asRows(payload.high_priority_matters),
      deadlines: asDeadlineDistribution(payload.deadline_distribution),
      economic: asEconomic(payload.economic),
      notificationPresidia: asRows(payload.notification_presidia),
      billingWork: asRows(payload.billing_work),
      lex: asStringList(payload.lex_suggestions),
    }
    return {
      ...dashboard,
      dossiers: asDossiers(payload),
      sources: asSources(payload, dashboard),
    }
  } catch {
    return unreachableDashboard()
  }
}

export async function syncDashboardMailboxes(): Promise<boolean> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), DASHBOARD_MAILBOX_SYNC_TIMEOUT_MS)
  try {
    const res = await fetch('/api/v1/ui/dashboard/sync-mailboxes', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
    return res.ok
  } catch {
    return false
  } finally {
    window.clearTimeout(timeout)
  }
}
