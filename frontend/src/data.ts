export type Tone = 'primary'|'info'|'success'|'warning'|'danger'|'purple'|'orange'|'neutral'
export type Metric = { id:string; label:string; value:string|number; tag?:string; tone:Tone; href?:string; actionLabel?:string }
export type Row = { id:string; title:string; subtitle:string; time?:string; avatar?:string; unread?:boolean; badge?:string; tone?:Tone; href?:string }
export type DashboardData = {
  metrics: Metric[]
  pec: Row[]
  emails: Row[]
  messages: Row[]
  agenda: Row[]
  operations: Row[]
  completion: { percent:number; totalMissing:number; items:Array<{label:string; count:number}> }
  engagements: Row[]
  matters: Row[]
  deadlines: Array<{label:string; count:number; percent:number; tone:Tone}>
  economic: Array<{label:string; value:string; note?:string; delta?:string}>
  lex: string[]
}

const emptyMetrics: Metric[] = [
  {id:'urgent',label:'Azioni urgenti',value:0,tag:'',tone:'danger',href:'/workspace-intelligente',actionLabel:'Vai alle azioni'},
  {id:'pec',label:'PEC da leggere',value:0,tag:'',tone:'primary',href:'/email',actionLabel:'Apri PEC'},
  {id:'messages',label:'Messaggi clienti',value:0,tag:'',tone:'success',href:'/messaggi',actionLabel:'Vai ai messaggi'},
  {id:'quotes',label:'Preventivi in scadenza',value:0,tag:'',tone:'purple',href:'/preventivi',actionLabel:'Apri preventivi'},
  {id:'engagements',label:'Conferimenti mancanti',value:0,tag:'',tone:'orange',href:'/preventivi',actionLabel:'Completa ora'}
]

export const emptyDashboard: DashboardData = {
  metrics: emptyMetrics,
  pec: [],
  emails: [],
  messages: [],
  agenda: [],
  operations: [],
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
    {label:'Fatturato mese',value:'EUR 0,00',note:'0 parcelle emesse'},
    {label:'Incassi mese',value:'EUR 0,00',note:'0 pagamenti registrati'},
    {label:'Da incassare',value:'EUR 0,00',note:'0 parcelle aperte'},
    {label:'Ore lavorate',value:'0 h',note:'0 voci timesheet'}
  ],
  lex: []
}

export const mockDashboard = emptyDashboard

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function asRows(value: unknown): Row[] {
  if (Array.isArray(value)) return value as Row[]
  if (isRecord(value) && Array.isArray(value.items)) return value.items as Row[]
  return []
}

function asMetrics(payload: Record<string, unknown>): Metric[] {
  if (Array.isArray(payload.metrics) && payload.metrics.length) return payload.metrics as Metric[]
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
  return {
    percent: Number(value.percent ?? emptyDashboard.completion.percent),
    totalMissing: Number(value.totalMissing ?? value.total_missing ?? emptyDashboard.completion.totalMissing),
    items: Array.isArray(value.items) ? value.items as Array<{label:string; count:number}> : emptyDashboard.completion.items
  }
}

export async function getDashboard(): Promise<DashboardData> {
  try {
    const res = await fetch('/api/v1/ui/dashboard', { credentials:'same-origin', headers:{Accept:'application/json'} })
    if (!res.ok) return emptyDashboard
    const payload = await res.json() as Record<string, unknown>
    return {
      metrics: asMetrics(payload),
      pec: asRows(payload.pec),
      emails: asRows(payload.emails),
      messages: asRows(payload.client_messages ?? payload.messages),
      agenda: asRows(payload.agenda),
      operations: asRows(payload.today_operations ?? payload.operations),
      completion: asCompletion(payload.incomplete_registry),
      engagements: asRows(payload.missing_engagements),
      matters: asRows(payload.high_priority_matters),
      deadlines: Array.isArray(payload.deadline_distribution) ? payload.deadline_distribution as DashboardData['deadlines'] : emptyDashboard.deadlines,
      economic: Array.isArray(payload.economic) ? payload.economic as DashboardData['economic'] : emptyDashboard.economic,
      lex: Array.isArray(payload.lex_suggestions) ? payload.lex_suggestions as string[] : emptyDashboard.lex
    }
  } catch {
    return emptyDashboard
  }
}
