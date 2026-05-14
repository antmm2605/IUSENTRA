import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  Archive,
  ArrowLeft,
  CalendarCheck,
  CalendarDays,
  CalendarPlus,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  Edit3,
  Eye,
  FileDown,
  Filter,
  Gavel,
  ListChecks,
  MoreHorizontal,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TimerReset,
  Trash2,
  Wand2,
  X,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyScadenziarioPage,
  calculateProcessDeadline,
  createProcessDeadline,
  getScadenziarioPage,
  type DeadlineCalculatorResult,
  type DeadlineCalculatorTemplate,
  type ScadenziarioActionCard,
  type ScadenziarioPageData,
  type ScadenziarioPriority,
  type ScadenziarioQuery,
  type ScadenziarioRow,
  type ScadenziarioView,
} from '../scadenziarioData'
import './ScadenziarioPage.css'

type SortKey = 'scadenza' | 'priorita' | 'titolo' | 'fascicolo' | 'giorni'

type CalculatorForm = {
  templateCode: string
  inputDate: string
  caseReference: string
  title: string
  baseValue: string
  periodType: 'days' | 'months'
  direction: 'forward' | 'backward'
  suspendAugust: boolean
  ferialPolicy: 'applies' | 'excluded' | 'partial' | 'manual_review'
  freeTerm: boolean
  urgent: boolean
  extendSaturday: boolean
}

const sortLabels: Record<SortKey, string> = {
  scadenza: 'Data scadenza',
  priorita: 'Priorità',
  titolo: 'Titolo',
  fascicolo: 'Fascicolo',
  giorni: 'Giorni residui',
}

const priorityWeight: Record<ScadenziarioPriority, number> = {
  CRITICA: 0,
  ALTA: 1,
  MEDIA: 2,
  BASSA: 3,
}

function initialView(): ScadenziarioView {
  const params = new URLSearchParams(window.location.search)
  const raw = params.get('vista') || 'aperte'
  const allowed: ScadenziarioView[] = ['aperte', 'critiche', 'alte', 'completate', 'scadute', 'imminenti', 'avanzate', 'operative', 'da_presidiare', 'tutte']
  return allowed.includes(raw as ScadenziarioView) ? raw as ScadenziarioView : 'aperte'
}

function initialQuery(): string {
  return new URLSearchParams(window.location.search).get('q') || ''
}

function routeDeadlineId(): string {
  const parts = window.location.pathname.split('/').filter(Boolean)
  if (parts[0] !== 'scadenziario' || !parts[1] || parts[1] === 'nuova') return ''
  return decodeURIComponent(parts[1])
}

function normaliseText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function isInsideQuery(item: ScadenziarioRow, query: string): boolean {
  const needle = normaliseText(query.trim())
  if (!needle) return true
  return normaliseText([
    item.title,
    item.description,
    item.typeLabel,
    item.priorityLabel,
    item.statusLabel,
    item.fascicoloLabel,
    item.ownerLabel,
    item.officeLabel,
  ].join(' ')).includes(needle)
}

function sortRows(rows: ScadenziarioRow[], sort: SortKey): ScadenziarioRow[] {
  const copy = [...rows]
  if (sort === 'priorita') return copy.sort((a, b) => priorityWeight[a.priority] - priorityWeight[b.priority] || a.date.localeCompare(b.date))
  if (sort === 'titolo') return copy.sort((a, b) => a.title.localeCompare(b.title, 'it'))
  if (sort === 'fascicolo') return copy.sort((a, b) => a.fascicoloLabel.localeCompare(b.fascicoloLabel, 'it'))
  if (sort === 'giorni') return copy.sort((a, b) => (a.days ?? 99999) - (b.days ?? 99999))
  return copy.sort((a, b) => a.date.localeCompare(b.date) || priorityWeight[a.priority] - priorityWeight[b.priority])
}

function actionIcon(icon: ScadenziarioActionCard['icon']) {
  if (icon === 'alert') return <AlertTriangle size={19}/>
  if (icon === 'check') return <CheckCircle2 size={19}/>
  if (icon === 'calculator') return <Wand2 size={19}/>
  if (icon === 'export') return <FileDown size={19}/>
  if (icon === 'lex') return <Sparkles size={19}/>
  if (icon === 'archive') return <Archive size={19}/>
  return <CalendarDays size={19}/>
}

function StatCard({
  icon,
  label,
  value,
  note,
  tone,
  active,
  onClick,
}:{
  icon: ReactNode
  label: string
  value: number | string
  note: string
  tone: ScadenziarioRow['tone']
  active?: boolean
  onClick?: () => void
}) {
  return (
    <button className={`iu-scad-stat iu-scad-stat--${tone} ${active ? 'is-active' : ''}`} type="button" onClick={onClick}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </button>
  )
}

async function postDeadlineAction(url: string, label: string, body?: URLSearchParams): Promise<string> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json,text/html',
      'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: body ?? new URLSearchParams(),
  })
  if (!response.ok) throw new Error(`${label}: operazione non completata`)
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) return `${label}: operazione eseguita.`
  const payload = await response.json() as { ok?: boolean; messaggio?: string; errore?: string }
  if (payload.ok === false) throw new Error(payload.errore || `${label}: errore operativo`)
  return payload.messaggio || `${label}: operazione eseguita.`
}

function DeadlineFlags({ item }:{item:ScadenziarioRow}) {
  return (
    <span className="iu-scad-flags">
      {item.peremptory ? <Badge tone="danger">Perentorio</Badge> : null}
      {item.advanced ? <Badge tone="purple">Calcolo</Badge> : null}
      {item.operative ? <Badge tone="info">Operativa</Badge> : null}
      {item.traceCount ? <em>{item.traceCount} step</em> : null}
    </span>
  )
}

function DeadlineActions({ item, onComplete, onDelete }:{item:ScadenziarioRow; onComplete:(item:ScadenziarioRow)=>void; onDelete:(item:ScadenziarioRow)=>void}) {
  return (
    <div className="iu-scad-actions" aria-label={`Azioni per ${item.title}`}>
      <a href={item.href} title="Apri dettaglio" aria-label="Apri dettaglio"><Eye size={15}/></a>
      <a href={item.editHref} title="Modifica" aria-label="Modifica"><Edit3 size={15}/></a>
      {item.status !== 'COMPLETATO' ? <button type="button" onClick={() => onComplete(item)} title="Completa" aria-label="Completa"><CheckCircle2 size={15}/></button> : null}
      <button type="button" onClick={() => onDelete(item)} title="Elimina" aria-label="Elimina"><Trash2 size={15}/></button>
    </div>
  )
}

function DeadlineTable({
  rows,
  selectedIds,
  onToggle,
  onToggleAll,
  onComplete,
  onDelete,
}:{
  rows: ScadenziarioRow[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onToggleAll: () => void
  onComplete: (item: ScadenziarioRow) => void
  onDelete: (item: ScadenziarioRow) => void
}) {
  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.includes(row.id))
  return (
    <div className="iu-scad-table-wrap">
      <table className="iu-scad-table">
        <thead>
          <tr>
            <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutte le scadenze visibili"/></th>
            <th>Scadenza</th>
            <th>Titolo</th>
            <th>Tipo</th>
            <th>Operativa</th>
            <th>Priorità</th>
            <th>Fascicolo</th>
            <th>Giorni</th>
            <th>Azioni</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <tr className={`${item.overdue ? 'is-overdue' : ''} ${item.dueToday ? 'is-today' : ''}`} key={item.id}>
              <td><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.title}`}/></td>
              <td><strong>{item.dateLabel}</strong><span>{item.statusLabel}</span></td>
              <td>
                <a className="iu-scad-title" href={item.href}>{item.title}</a>
                <small>{item.description || item.sourceEventLabel || 'Nessuna descrizione operativa.'}</small>
                <DeadlineFlags item={item}/>
              </td>
              <td><Badge tone="neutral">{item.typeLabel}</Badge></td>
              <td>{item.operative ? <span className="iu-scad-operative"><TimerReset size={14}/>{item.operationalDueLabel}</span> : <span className="iu-scad-muted">—</span>}</td>
              <td><Badge tone={item.tone}>{item.priorityLabel}</Badge></td>
              <td><span className="iu-scad-fascicolo">{item.fascicoloLabel}</span><small>{item.ownerLabel}</small></td>
              <td><b className={`iu-scad-days ${item.overdue ? 'is-negative' : item.dueToday ? 'is-zero' : ''}`}>{item.daysLabel}</b></td>
              <td><DeadlineActions item={item} onComplete={onComplete} onDelete={onDelete}/></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DeadlineCardList({
  rows,
  selectedIds,
  onToggle,
  onComplete,
  onDelete,
}:{
  rows: ScadenziarioRow[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onComplete: (item: ScadenziarioRow) => void
  onDelete: (item: ScadenziarioRow) => void
}) {
  return (
    <div className="iu-scad-card-list">
      {rows.map((item) => (
        <article className={`iu-scad-mobile-card ${item.overdue ? 'is-overdue' : ''}`} key={item.id}>
          <header>
            <label><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)}/><span>{item.dateLabel}</span></label>
            <Badge tone={item.tone}>{item.priorityLabel}</Badge>
          </header>
          <a href={item.href}>{item.title}</a>
          <p>{item.description || item.fascicoloLabel || 'Scadenza senza descrizione.'}</p>
          <div className="iu-scad-mobile-meta">
            <span><CalendarDays size={14}/>{item.daysLabel}</span>
            <span><Gavel size={14}/>{item.typeLabel}</span>
            <span><ShieldCheck size={14}/>{item.statusLabel}</span>
          </div>
          <DeadlineFlags item={item}/>
          <DeadlineActions item={item} onComplete={onComplete} onDelete={onDelete}/>
        </article>
      ))}
    </div>
  )
}

function defaultCalculatorForm(templates: DeadlineCalculatorTemplate[]): CalculatorForm {
  const first = templates[0]
  return {
    templateCode: first?.code || 'CUSTOM_PROCESSUALE',
    inputDate: new Date().toISOString().slice(0, 10),
    caseReference: '',
    title: first?.name || 'Termine processuale',
    baseValue: String(first?.base_value || 30),
    periodType: first?.period_type || 'days',
    direction: first?.direction || 'forward',
    suspendAugust: first?.suspend_august ?? true,
    ferialPolicy: first?.ferial_suspension_policy || 'applies',
    freeTerm: first?.free_term ?? false,
    urgent: first?.urgent ?? false,
    extendSaturday: first?.extend_saturday ?? true,
  }
}

function formFromTemplate(current: CalculatorForm, template: DeadlineCalculatorTemplate | undefined): CalculatorForm {
  if (!template) return current
  return {
    ...current,
    templateCode: template.code,
    title: template.name,
    baseValue: String(template.base_value),
    periodType: template.period_type,
    direction: template.direction,
    suspendAugust: template.suspend_august,
    ferialPolicy: template.ferial_suspension_policy,
    freeTerm: template.free_term,
    urgent: template.urgent,
    extendSaturday: template.extend_saturday,
  }
}

function calculatorRequest(form: CalculatorForm): Record<string, unknown> {
  return {
    template_code: form.templateCode,
    input_date: form.inputDate,
    case_reference: form.caseReference,
    title: form.title,
    base_value: Number(form.baseValue || 0),
    period_type: form.periodType,
    direction: form.direction,
    suspend_august: form.suspendAugust,
    ferial_suspension_policy: form.ferialPolicy,
    free_term: form.freeTerm,
    urgent: form.urgent,
    extend_saturday: form.extendSaturday,
    extend_holiday: true,
  }
}

function ProcessDeadlineCalculator({
  templates,
  result,
  form,
  busy,
  status,
  onForm,
  onCalculate,
  onCreate,
}:{
  templates: DeadlineCalculatorTemplate[]
  result: DeadlineCalculatorResult | null
  form: CalculatorForm
  busy: boolean
  status: string
  onForm: (form: CalculatorForm) => void
  onCalculate: () => void
  onCreate: () => void
}) {
  const selected = templates.find((template) => template.code === form.templateCode)
  return (
    <section className="iu-scad-calculator" aria-label="Calcolatore termini processuali">
      <header>
        <div>
          <span><Gavel size={16}/> Calcolatore termini processuali</span>
          <h2>Calcolo spiegabile con audit</h2>
          <p>Template versionati, sospensione feriale parametrica, sabato configurabile e conferma professionale quando il caso lo richiede.</p>
        </div>
        <Badge tone={result?.requiresLegalReview ? 'warning' : 'success'}>{result?.requiresLegalReview ? 'richiede verifica' : 'assistente verificabile'}</Badge>
      </header>
      <div className="iu-scad-calculator__grid">
        <div className="iu-scad-calculator__form">
          <label>
            <span>Template</span>
            <select value={form.templateCode} onChange={(event) => onForm(formFromTemplate(form, templates.find((template) => template.code === event.target.value)))}>
              {templates.map((template) => <option value={template.code} key={template.code}>{template.name}</option>)}
            </select>
          </label>
          <label>
            <span>Data evento</span>
            <input type="date" value={form.inputDate} onChange={(event) => onForm({ ...form, inputDate: event.target.value })}/>
          </label>
          <label>
            <span>Riferimento pratica</span>
            <input value={form.caseReference} onChange={(event) => onForm({ ...form, caseReference: event.target.value })} placeholder="RG, fascicolo o cliente"/>
          </label>
          <label>
            <span>Titolo scadenza</span>
            <input value={form.title} onChange={(event) => onForm({ ...form, title: event.target.value })}/>
          </label>
          <label>
            <span>Valore</span>
            <input type="number" min="1" value={form.baseValue} onChange={(event) => onForm({ ...form, baseValue: event.target.value })}/>
          </label>
          <label>
            <span>Periodo</span>
            <select value={form.periodType} onChange={(event) => onForm({ ...form, periodType: event.target.value as CalculatorForm['periodType'] })}>
              <option value="days">Giorni</option>
              <option value="months">Mesi</option>
            </select>
          </label>
          <label>
            <span>Direzione</span>
            <select value={form.direction} onChange={(event) => onForm({ ...form, direction: event.target.value as CalculatorForm['direction'] })}>
              <option value="forward">In avanti</option>
              <option value="backward">A ritroso</option>
            </select>
          </label>
          <label>
            <span>Sospensione feriale</span>
            <select value={form.ferialPolicy} onChange={(event) => onForm({ ...form, ferialPolicy: event.target.value as CalculatorForm['ferialPolicy'], suspendAugust: event.target.value === 'applies' })}>
              <option value="applies">Applica 1-31 agosto</option>
              <option value="excluded">Esclusa</option>
              <option value="partial">Parziale</option>
              <option value="manual_review">Verifica manuale</option>
            </select>
          </label>
          <div className="iu-scad-calculator__checks">
            <label><input type="checkbox" checked={form.freeTerm} onChange={(event) => onForm({ ...form, freeTerm: event.target.checked })}/> Termine libero</label>
            <label><input type="checkbox" checked={form.urgent} onChange={(event) => onForm({ ...form, urgent: event.target.checked })}/> Materia urgente</label>
            <label><input type="checkbox" checked={form.extendSaturday} onChange={(event) => onForm({ ...form, extendSaturday: event.target.checked })}/> Proroga sabato</label>
          </div>
          <div className="iu-scad-calculator__actions">
            <button type="button" onClick={onCalculate} disabled={busy || !form.inputDate}><Wand2 size={15}/> Calcola e spiega</button>
            <button type="button" onClick={onCreate} disabled={busy || !result}><CalendarPlus size={15}/> Crea scadenza auditata</button>
          </div>
          {selected ? <small>{selected.reference_law || 'Template configurabile'} · versione {selected.version}</small> : null}
          {status ? <p className="iu-scad-calculator__status">{status}</p> : null}
        </div>
        <div className="iu-scad-calculator__result">
          {result ? (
            <>
              <div className="iu-scad-calculator__deadline">
                <span>Scadenza calcolata</span>
                <strong>{result.deadline}</strong>
                <Badge tone={result.confidence === 'alta' ? 'success' : result.confidence === 'media' ? 'warning' : 'danger'}>confidenza {result.confidence}</Badge>
              </div>
              <p>{result.explanation}</p>
              <div className="iu-scad-calculator__rules">
                {result.rulesApplied.map((rule) => <Badge tone="neutral" key={rule}>{rule.split('_').join(' ')}</Badge>)}
              </div>
              <ol>
                {result.steps.slice(0, 6).map((step) => <li key={`${step.code}-${step.date}`}>{step.date} · {step.label}</li>)}
              </ol>
              <dl>
                <div><dt>Motore</dt><dd>{result.engineVersion}</dd></div>
                <div><dt>Regole</dt><dd>{result.rulesetVersion}</dd></div>
                <div><dt>Calendario</dt><dd>{result.calendarVersion}</dd></div>
                <div><dt>Hash audit</dt><dd>{result.audit?.immutableHash.slice(0, 12) || result.resultHash.slice(0, 12)}</dd></div>
              </dl>
              <div className="iu-scad-calculator__pec">
                <strong>Promemoria PEC pianificabili</strong>
                <span>{result.notificationPlan.map((item) => `T-${item.daysLeft}`).join(' · ')}</span>
              </div>
            </>
          ) : (
            <div className="iu-scad-calculator__empty">
              <Wand2 size={28}/>
              <strong>Pronto per il calcolo</strong>
              <span>Il risultato mostrera data, regole applicate, spiegazione, versioni e hash audit.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function OperativeCards({
  cards,
  selectedCount,
  onFilter,
  onBulkComplete,
}:{
  cards: ScadenziarioActionCard[]
  selectedCount: number
  onFilter: (view: ScadenziarioView) => void
  onBulkComplete: () => void
}) {
  if (!cards.length) return null
  return (
    <section className="iu-scad-actions-grid" aria-label="Card operative scadenziario">
      {cards.map((card) => {
        const isBulk = card.action.kind === 'bulk_complete'
        return (
          <article className={`iu-scad-action-card iu-scad-action-card--${card.tone}`} key={card.id}>
            <div>{actionIcon(card.icon)}</div>
            <span>{card.title}</span>
            <strong>{card.value}</strong>
            <p>{card.description}</p>
            {card.action.kind === 'filter' && card.action.view ? (
              <button type="button" onClick={() => onFilter(card.action.view!)}>{card.action.label}</button>
            ) : isBulk ? (
              <button type="button" onClick={onBulkComplete} disabled={!selectedCount}>{card.action.label}{selectedCount ? ` (${selectedCount})` : ''}</button>
            ) : card.action.href ? (
              <a href={card.action.href}>{card.action.label}</a>
            ) : null}
          </article>
        )
      })}
    </section>
  )
}

function Inspector({ data, rows }:{data:ScadenziarioPageData; rows:ScadenziarioRow[]}) {
  const watch = rows.filter((item) => item.overdue || item.dueToday || item.priority === 'CRITICA').slice(0, 5)
  const advanced = rows.filter((item) => item.advanced || item.operative).slice(0, 5)
  return (
    <aside className="iu-scad-inspector">
      <Panel title="Briefing Lex" subtitle="Contesto pronto per la prossima azione" icon={<Sparkles size={17}/>}>
        <div className="iu-scad-briefing">
          <article>
            <span>Da presidiare ora</span>
            <strong>{watch.length}</strong>
            <small>Scadute, odierne o critiche nella vista corrente.</small>
          </article>
          <div>
            <Button variant="primary" href={data.actions.lex}><Sparkles size={15}/> Chiedi a Lex</Button>
            <Button href={data.actions.agenda}><CalendarDays size={15}/> Agenda</Button>
          </div>
        </div>
      </Panel>
      <Panel title="Scadenze da presidiare" icon={<AlertTriangle size={17}/>} count={watch.length}>
        {watch.length ? (
          <div className="iu-scad-watch-list">
            {watch.map((item) => (
              <a href={item.href} key={item.id}>
                <Badge tone={item.tone}>{item.priorityLabel}</Badge>
                <strong>{item.title}</strong>
                <span>{item.dateLabel} · {item.daysLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun termine critico nella vista corrente.</p>}
      </Panel>
      <Panel title="Calcoli e operatività" icon={<TimerReset size={17}/>} count={advanced.length}>
        {advanced.length ? (
          <div className="iu-scad-watch-list">
            {advanced.map((item) => (
              <a href={item.href} key={item.id}>
                <Badge tone={item.operative ? 'info' : 'purple'}>{item.operative ? 'operativa' : 'calcolo'}</Badge>
                <strong>{item.title}</strong>
                <span>{item.operationalDueLabel || item.sourceEventLabel || item.dateLabel}</span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessun calcolo avanzato nella vista corrente.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<MoreHorizontal size={17}/>}>
        <div className="iu-scad-quick-actions">
          <a href={data.actions.new}><CalendarPlus size={15}/> Nuova scadenza</a>
          <a href={data.actions.exportIcs}><Download size={15}/> iCal scadenze</a>
          <a href={data.actions.calendarSettings}><Clock3 size={15}/> Sincronizzazione</a>
          <a href="/deposito/checklist"><ListChecks size={15}/> Checklist deposito</a>
        </div>
      </Panel>
    </aside>
  )
}

export function ScadenziarioPage() {
  const [data, setData] = useState<ScadenziarioPageData>(emptyScadenziarioPage)
  const [loading, setLoading] = useState(true)
  const [calculatorForm, setCalculatorForm] = useState<CalculatorForm>(() => defaultCalculatorForm(emptyScadenziarioPage.calculator.templates))
  const [calculatorResult, setCalculatorResult] = useState<DeadlineCalculatorResult | null>(null)
  const [calculatorBusy, setCalculatorBusy] = useState(false)
  const [calculatorStatus, setCalculatorStatus] = useState('')
  const [view, setView] = useState<ScadenziarioView>(() => initialView())
  const [query, setQuery] = useState(() => initialQuery())
  const [type, setType] = useState('')
  const [priority, setPriority] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [peremptory, setPeremptory] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [operative, setOperative] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [sort, setSort] = useState<SortKey>('scadenza')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [statusLine, setStatusLine] = useState('')

  const buildQuery = (): ScadenziarioQuery => ({ view, q: query, type, priority, from, to, peremptory, advanced, operative })

  const syncCalculatorDefaults = (payload: ScadenziarioPageData) => {
    setCalculatorForm((current) => {
      if (current.templateCode && payload.calculator.templates.some((template) => template.code === current.templateCode)) return current
      return defaultCalculatorForm(payload.calculator.templates)
    })
  }

  const load = () => {
    setLoading(true)
    getScadenziarioPage(buildQuery()).then((payload) => {
      setData(payload)
      syncCalculatorDefaults(payload)
      setSelectedIds((current) => current.filter((id) => payload.items.some((item) => item.id === id)))
    }).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getScadenziarioPage(buildQuery()).then((payload) => {
      if (!active) return
      setData(payload)
      syncCalculatorDefaults(payload)
      setSelectedIds((current) => current.filter((id) => payload.items.some((item) => item.id === id)))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [view, type, priority, from, to, peremptory, advanced, operative])

  const visibleRows = useMemo(() => sortRows(data.items.filter((item) => isInsideQuery(item, query)), sort), [data.items, query, sort])

  const toggleSelection = (id: string) => {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  const toggleAll = () => {
    setSelectedIds((current) => {
      const visibleIds = visibleRows.map((item) => item.id)
      const allSelected = visibleIds.length > 0 && visibleIds.every((id) => current.includes(id))
      if (allSelected) return current.filter((id) => !visibleIds.includes(id))
      return Array.from(new Set([...current, ...visibleIds]))
    })
  }

  const runComplete = (item: ScadenziarioRow) => {
    setStatusLine(`Completamento di "${item.title}"...`)
    postDeadlineAction(item.completeHref, 'Completa scadenza')
      .then((message) => { setStatusLine(message); load() })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : 'Completamento non riuscito'))
  }

  const runDelete = (item: ScadenziarioRow) => {
    if (!window.confirm(`Eliminare la scadenza "${item.title}"?`)) return
    setStatusLine(`Eliminazione di "${item.title}"...`)
    postDeadlineAction(item.deleteHref, 'Elimina scadenza')
      .then((message) => { setStatusLine(message); load() })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : 'Eliminazione non riuscita'))
  }

  const runBulkComplete = () => {
    if (!selectedIds.length) return
    const body = new URLSearchParams()
    selectedIds.forEach((id) => body.append('ids', id))
    setStatusLine(`Completamento di ${selectedIds.length} scadenze...`)
    postDeadlineAction(data.actions.bulkComplete, 'Completa selezionate', body)
      .then((message) => { setStatusLine(message); setSelectedIds([]); load() })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : 'Completamento massivo non riuscito'))
  }

  const resetFilters = () => {
    setView('aperte')
    setQuery('')
    setType('')
    setPriority('')
    setFrom('')
    setTo('')
    setPeremptory(false)
    setAdvanced(false)
    setOperative(false)
  }

  const runCalculator = () => {
    setCalculatorBusy(true)
    setCalculatorStatus('Calcolo termine processuale in corso...')
    calculateProcessDeadline(data.calculator.endpoints.calculate, calculatorRequest(calculatorForm))
      .then((result) => {
        setCalculatorResult(result)
        setCalculatorStatus('Calcolo completato e audit hashato registrato.')
      })
      .catch((error) => setCalculatorStatus(error instanceof Error ? error.message : 'Calcolo non riuscito'))
      .finally(() => setCalculatorBusy(false))
  }

  const runCreateCalculatedDeadline = () => {
    if (!calculatorResult) return
    setCalculatorBusy(true)
    setCalculatorStatus('Creazione della scadenza auditata...')
    createProcessDeadline(data.calculator.endpoints.createDeadline, calculatorRequest(calculatorForm))
      .then((result) => {
        setCalculatorStatus(result.messaggio)
        window.history.replaceState(null, '', result.href)
        load()
      })
      .catch((error) => setCalculatorStatus(error instanceof Error ? error.message : 'Creazione scadenza non riuscita'))
      .finally(() => setCalculatorBusy(false))
  }
  const focusedId = routeDeadlineId()
  const focusedRow = focusedId ? data.items.find((item) => item.id === focusedId) : undefined

  return (
    <main className="iu-content iu-scad-page">
      <section className="iu-scad-hero">
        <div>
          <span className="iu-scad-eyebrow"><CalendarCheck size={16}/> Scadenziario Legale</span>
          <h1>Scadenziario Legale</h1>
          <p>Termini, udienze, depositi, calcoli avanzati e priorità operative dello studio in una cabina professionale.</p>
        </div>
        <div className="iu-scad-hero__actions">
          <Button href="/workspace-intelligente"><Sparkles size={15}/> Cabina</Button>
          <Button href={data.actions.exportCsv}><Download size={15}/> CSV</Button>
          <Button href={data.actions.exportPdf}><FileDown size={15}/> PDF</Button>
          <Button href={data.actions.exportIcs}><ChevronDown size={15}/> iCal</Button>
          <Button variant="primary" href={data.actions.new}><CalendarPlus size={16}/> Nuova scadenza</Button>
        </div>
      </section>

      {data.overduePreview.length ? (
        <section className="iu-scad-alert" role="alert">
          <AlertTriangle size={22}/>
          <div>
            <strong>{data.summary.overdue} scadenze scadute non ancora completate.</strong>
            <p>{data.overduePreview.slice(0, 3).map((item) => `${item.title} — ${item.dateLabel}`).join(' · ')}</p>
          </div>
          <button type="button" onClick={() => setView('scadute')}>Apri scadute</button>
        </section>
      ) : null}

      <section className="iu-scad-stats" aria-label="Indicatori scadenziario">
        <StatCard icon={<CalendarDays size={19}/>} label="Aperte" value={data.summary.open} note="da lavorare" tone="primary" active={view === 'aperte'} onClick={() => setView('aperte')}/>
        <StatCard icon={<AlertTriangle size={19}/>} label="Critiche" value={data.summary.critical} note="massima priorità" tone={data.summary.critical ? 'danger' : 'neutral'} active={view === 'critiche'} onClick={() => setView('critiche')}/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Alta priorità" value={data.summary.high} note="da presidiare" tone={data.summary.high ? 'warning' : 'neutral'} active={view === 'alte'} onClick={() => setView('alte')}/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="Completate" value={data.summary.completed} note="chiuse" tone="success" active={view === 'completate'} onClick={() => setView('completate')}/>
        <StatCard icon={<TimerReset size={19}/>} label="Scadute" value={data.summary.overdue} note="non completate" tone={data.summary.overdue ? 'danger' : 'neutral'} active={view === 'scadute'} onClick={() => setView('scadute')}/>
        <StatCard icon={<Clock3 size={19}/>} label="Entro 7 gg" value={data.summary.within7} note="orizzonte breve" tone={data.summary.within7 ? 'orange' : 'neutral'} active={view === 'imminenti'} onClick={() => setView('imminenti')}/>
        <StatCard icon={<Wand2 size={19}/>} label="Avanzate" value={data.summary.advanced} note="calcolo legale" tone="purple" active={view === 'avanzate'} onClick={() => setView('avanzate')}/>
        <StatCard icon={<ListChecks size={19}/>} label="Operative" value={data.summary.operative} note="anticipo studio" tone="info" active={view === 'operative'} onClick={() => setView('operative')}/>
      </section>

      <section className="iu-scad-toolbar" aria-label="Filtri scadenziario">
        <label className="iu-scad-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') load() }} placeholder="Cerca per titolo, descrizione, fascicolo, ufficio..."/></label>
        <label className="iu-scad-select"><Filter size={16}/><select value={type} onChange={(event) => setType(event.target.value)}>{data.facets.types.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label}{facet.count ? ` (${facet.count})` : ''}</option>)}</select></label>
        <label className="iu-scad-select"><ShieldCheck size={16}/><select value={priority} onChange={(event) => setPriority(event.target.value)}>{data.facets.priorities.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label}{facet.count ? ` (${facet.count})` : ''}</option>)}</select></label>
        <button className="iu-scad-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><SlidersHorizontal size={16}/> Filtri</button>
        <button className="iu-scad-icon-btn" type="button" onClick={load} aria-label="Aggiorna scadenziario"><RefreshCw size={17}/></button>
        <button className="iu-scad-reset" type="button" onClick={resetFilters}><X size={15}/> Reset</button>
      </section>

      {advancedOpen ? (
        <section className="iu-scad-advanced" aria-label="Filtri avanzati scadenziario">
          <label><span>Dal</span><input type="date" value={from} onChange={(event) => setFrom(event.target.value)}/></label>
          <label><span>Al</span><input type="date" value={to} onChange={(event) => setTo(event.target.value)}/></label>
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((key) => <option value={key} key={key}>{sortLabels[key]}</option>)}</select></label>
          <label className="iu-scad-check"><input type="checkbox" checked={peremptory} onChange={(event) => setPeremptory(event.target.checked)}/><span>Solo perentorie</span></label>
          <label className="iu-scad-check"><input type="checkbox" checked={advanced} onChange={(event) => setAdvanced(event.target.checked)}/><span>Solo calcolo avanzato</span></label>
          <label className="iu-scad-check"><input type="checkbox" checked={operative} onChange={(event) => setOperative(event.target.checked)}/><span>Solo operative</span></label>
        </section>
      ) : null}

      <OperativeCards cards={data.operativeCards} selectedCount={selectedIds.length} onFilter={setView} onBulkComplete={runBulkComplete}/>

      <ProcessDeadlineCalculator
        templates={data.calculator.templates}
        result={calculatorResult}
        form={calculatorForm}
        busy={calculatorBusy}
        status={calculatorStatus}
        onForm={setCalculatorForm}
        onCalculate={runCalculator}
        onCreate={runCreateCalculatedDeadline}
      />

      <section className="iu-scad-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione scadenziario...' : 'Dati scadenziario aggiornati'}</span>
        <small><ShieldCheck size={14}/> Scritture e calcoli restano tracciati con controlli operativi.</small>
        {statusLine ? <small className="iu-scad-operation-status">{statusLine}</small> : null}
      </section>

      {selectedIds.length ? (
        <section className="iu-scad-bulkbar">
          <strong>{selectedIds.length} selezionate</strong>
          <button type="button" onClick={runBulkComplete}><CheckCircle2 size={15}/> Completa selezionate</button>
          <button type="button" onClick={() => setSelectedIds([])}>Annulla selezione</button>
        </section>
      ) : null}

      {focusedRow ? (
        <section className="iu-scad-focus-card">
          <div>
            <Badge tone={focusedRow.tone}>{focusedRow.statusLabel}</Badge>
            <h2>{focusedRow.title}</h2>
            <p>{focusedRow.description || focusedRow.fascicoloLabel || 'Dettaglio operativo della scadenza selezionata.'}</p>
            <dl>
              <div><dt>Scadenza legale</dt><dd>{focusedRow.dateLabel}</dd></div>
              <div><dt>Scadenza operativa</dt><dd>{focusedRow.operationalDueLabel || 'Non impostata'}</dd></div>
              <div><dt>Priorità</dt><dd>{focusedRow.priorityLabel}</dd></div>
              <div><dt>Responsabile</dt><dd>{focusedRow.ownerLabel || 'Non assegnato'}</dd></div>
            </dl>
          </div>
          <div className="iu-scad-focus-actions">
            <Button href={focusedRow.editHref}><Edit3 size={15}/> Modifica</Button>
            <button type="button" onClick={() => runComplete(focusedRow)}><CheckCircle2 size={15}/> Completa</button>
            <button type="button" onClick={() => runDelete(focusedRow)}><Trash2 size={15}/> Elimina</button>
            <Button href="/scadenziario"><ArrowLeft size={15}/> Torna allo scadenziario</Button>
          </div>
        </section>
      ) : null}

      <section className="iu-scad-layout">
        <div className="iu-scad-table-card">
          <header>
            <div><strong>{visibleRows.length} scadenze</strong><span>{data.facets.views.find((facet) => facet.value === view)?.label || 'Vista corrente'} · {data.source}</span></div>
            <div>
              <Badge tone={data.summary.overdue ? 'danger' : 'success'}>{data.summary.overdue ? `${data.summary.overdue} scadute` : 'presidiata'}</Badge>
              <a href={data.actions.exportCsv}><Download size={15}/> Esporta</a>
            </div>
          </header>
          {visibleRows.length ? (
            <>
              <DeadlineTable rows={visibleRows} selectedIds={selectedIds} onToggle={toggleSelection} onToggleAll={toggleAll} onComplete={runComplete} onDelete={runDelete}/>
              <DeadlineCardList rows={visibleRows} selectedIds={selectedIds} onToggle={toggleSelection} onComplete={runComplete} onDelete={runDelete}/>
            </>
          ) : (
            <div className="iu-scad-empty">
              <CalendarCheck size={38}/>
              <strong>Nessuna scadenza nella vista corrente</strong>
              <span>Modifica i filtri, passa a “Tutte” oppure crea una nuova scadenza.</span>
              <Button variant="primary" href={data.actions.new}><CalendarPlus size={15}/> Nuova scadenza</Button>
            </div>
          )}
        </div>
        <Inspector data={data} rows={visibleRows}/>
      </section>

      <section className="iu-scad-lower-grid">
        <Panel title="Qualità scadenziario" subtitle="Cosa ho integrato oltre alla pagina storica" icon={<ShieldCheck size={17}/>}>
          <div className="iu-scad-checklist">
            <span><CheckCircle2 size={16}/> Card operative con azioni associate: filtra, completa selezionate, esporta, apri Lex.</span>
            <span><TimerReset size={16}/> Separazione tra scadenza legale e scadenza operativa interna quando il calcolo avanzato è presente.</span>
            <span><Sparkles size={16}/> Lex AI flottante e trascinabile, contestualizzato sullo scadenziario.</span>
          </div>
        </Panel>
        <Panel title="Integrazioni" subtitle="Agenda, fascicoli, deposito e calendario" icon={<CalendarDays size={17}/>}>
          <div className="iu-scad-integrations">
            <a href={data.actions.agenda}>Agenda</a>
            <a href="/fascicoli">Fascicoli</a>
            <a href="/deposito/checklist">Checklist deposito</a>
            <a href={data.actions.calendarSettings}>Calendari</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context="scadenziario"
        title="Lex AI Scadenziario"
        body="Posso preparare il briefing dei termini, spiegare il calcolo, suggerire priorità operative e collegare scadenze, agenda e fascicoli."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex sulle scadenze"
        secondaryHref="/workspace-intelligente"
        secondaryLabel="Regia operativa"
      />
    </main>
  )
}
