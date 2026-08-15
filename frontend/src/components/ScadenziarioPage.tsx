import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  FileSearch,
  Filter,
  Gavel,
  Link2,
  ListChecks,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TimerReset,
  Trash2,
  UsersRound,
  Wand2,
  X,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { SourceDocumentModal } from './SourceDocumentModal'
import { OperationalModal } from './OperationalModal'
import {
  emptyScadenziarioPage,
  calculateProcessDeadline,
  createProcessDeadline,
  getDeadlineCalculator,
  getScadenziarioPage,
  importPdfDeadlines,
  previewPdfDeadlines,
  type DeadlineCalculatorResult,
  type DeadlineCalculatorState,
  type DeadlineCalculatorTemplate,
  type PdfDeadlinePreview,
  type ScadenziarioActionCard,
  type ScadenziarioDraftProposal,
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

function formatItalianDate(value?: string): string {
  if (!value) return '-'
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return value
  return `${match[3]}/${match[2]}/${match[1]}`
}

function initialView(): ScadenziarioView {
  const params = new URLSearchParams(window.location.search)
  const focusId = routeDeadlineId()
  const raw = params.get('vista') || (focusId ? 'tutte' : 'aperte')
  const allowed: ScadenziarioView[] = ['aperte', 'critiche', 'alte', 'completate', 'scadute', 'imminenti', 'avanzate', 'operative', 'pec', 'da_presidiare', 'tutte']
  return allowed.includes(raw as ScadenziarioView) ? raw as ScadenziarioView : 'aperte'
}

function initialQuery(): string {
  return new URLSearchParams(window.location.search).get('q') || ''
}

function initialGuidaPratica(): string {
  const params = new URLSearchParams(window.location.search)
  return params.get('guida_pratica') || params.get('codice_guida') || params.get('guidaPratica') || ''
}

function initialFascicoloId(): string {
  const params = new URLSearchParams(window.location.search)
  return params.get('id_fascicolo') || params.get('fascicolo') || params.get('fascicoloId') || ''
}

function routeDeadlineId(): string {
  const parts = window.location.pathname.split('/').filter(Boolean)
  if (parts[0] !== 'scadenziario' || !parts[1] || parts[1] === 'nuova') return ''
  return decodeURIComponent(parts[1])
}

function normaliseText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function sourceLabel(source: string): string {
  if (source === 'repository_reali') return 'dati dello studio'
  if (source === 'errore_controllato') return 'dati parziali'
  return source || 'dati aggiornati'
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
    item.clientLabel,
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
  return copy.sort((a, b) => {
    if (a.overdue !== b.overdue) return a.overdue ? 1 : -1
    if (a.overdue && b.overdue) return b.date.localeCompare(a.date) || priorityWeight[a.priority] - priorityWeight[b.priority]
    return a.date.localeCompare(b.date) || priorityWeight[a.priority] - priorityWeight[b.priority]
  })
}

function useScadenziarioMobileLayout(): boolean {
  const [mobile, setMobile] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(max-width: 760px)').matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined
    const media = window.matchMedia('(max-width: 760px)')
    const update = () => setMobile(media.matches)
    update()
    media.addEventListener?.('change', update)
    return () => media.removeEventListener?.('change', update)
  }, [])

  return mobile
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

function DraftProposalsPanel({ proposals, onConfirm, onDiscard }:{proposals:ScadenziarioDraftProposal[]; onConfirm:(item:ScadenziarioDraftProposal)=>void; onDiscard:(item:ScadenziarioDraftProposal)=>void}) {
  if (!proposals.length) return null
  const daRegistro = proposals.filter((item) => item.sourceOrigin === 'registro').length
  const daPec = proposals.length - daRegistro
  const fonti = [daPec ? `${daPec} da PEC` : '', daRegistro ? `${daRegistro} dal registro di cancelleria` : ''].filter(Boolean).join(' · ')
  return (
    <section className="iu-scad-proposals" aria-label="Proposte di scadenza da confermare">
      <header className="iu-scad-proposals__head">
        <span className="iu-scad-proposals__eyebrow"><FileSearch size={15}/> Date da confermare</span>
        <strong>{proposals.length === 1 ? '1 proposta di scadenza attende la tua conferma' : `${proposals.length} proposte di scadenza attendono la tua conferma`}</strong>
        <p>Provenienza: {fonti}. Nessuna è operativa finché non la confermi: verifica la fonte e decidi.</p>
      </header>
      <div className="iu-scad-proposals__list">
        {proposals.map((item) => (
          <article key={item.id} className="iu-scad-proposal">
            <div className="iu-scad-proposal__top">
              <Badge tone={item.sourceOrigin === 'registro' ? 'purple' : 'info'}>{item.sourceOriginLabel}</Badge>
              <Badge tone="neutral">{item.sourceSnippetLabel || 'Data letta'}</Badge>
              <strong>{item.dateLabel}</strong>
              {item.sourceConfidence ? <em>affidabilità lettura {item.sourceConfidence}%</em> : null}
            </div>
            <p className="iu-scad-proposal__title">{item.title}</p>
            {item.sourceSnippet ? <blockquote className="iu-scad-proposal__quote">«{item.sourceSnippet}»</blockquote> : null}
            <p className="iu-scad-proposal__source">
              Fonte: {item.sourceDocumentName || item.sourceLabel || (item.sourceOrigin === 'registro' ? 'registro di cancelleria' : 'messaggio PEC')}
              {item.sourceHref ? <> — <a href={item.sourceHref}>Apri fonte</a></> : null}
              {item.fascicoloLabel ? <> · {item.fascicoloLabel}</> : null}
            </p>
            <div className="iu-scad-proposal__actions">
              <button type="button" className="iu-scad-proposal__confirm" onClick={() => onConfirm(item)}><CheckCircle2 size={15}/> Conferma scadenza</button>
              <button type="button" className="iu-scad-proposal__discard" onClick={() => onDiscard(item)}><X size={15}/> Scarta</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function DeadlineFlags({ item }:{item:ScadenziarioRow}) {
  return (
    <span className="iu-scad-flags">
      {item.peremptory ? <Badge tone="danger">Perentorio</Badge> : null}
      {item.advanced ? <Badge tone="purple">Calcolo</Badge> : null}
      {item.operative ? <Badge tone="info">Operativa</Badge> : null}
      {item.hearingMode ? <Badge tone="info">{item.hearingMode}{item.hearingTime ? `, ore ${item.hearingTime}` : ''}</Badge> : null}
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

function RemoteHearingNotice({ item }: { item: ScadenziarioRow }) {
  if (!item.remoteHearingUrl && !item.remoteHearingPdfRequired && !item.remoteHearingSource) return null
  return (
    <div className="iu-scad-remote-box">
      {item.remoteHearingUrl ? (
        <a className="iu-scad-remote-link" href={item.remoteHearingUrl} target="_blank" rel="noreferrer">
          <Link2 size={13}/> Apri link udienza audiovisiva
        </a>
      ) : item.remoteHearingPdfRequired ? (
        <span className="iu-scad-remote-pending"><FileSearch size={13}/> Link udienza nel PDF allegato da acquisire</span>
      ) : null}
      {!item.remoteHearingUrl && item.remoteHearingAccessInfo ? (
        <span className="iu-scad-remote-access">{item.remoteHearingAccessInfo}</span>
      ) : null}
      {item.remoteHearingSource ? (
        <span className="iu-scad-remote-source"><FileSearch size={13}/> Allegato udienza: {item.remoteHearingSource}</span>
      ) : null}
      {item.remoteHearingPlatform ? <span>Piattaforma: {item.remoteHearingPlatform}</span> : null}
      {item.remoteHearingMeetingId ? <span>ID riunione: {item.remoteHearingMeetingId}</span> : null}
      {item.remoteHearingPasscode ? <span>Codice di accesso: {item.remoteHearingPasscode}</span> : null}
      {item.remoteHearingUrl ? (
        <span className={`iu-scad-remote-check ${item.remoteHearingVerified ? 'is-verified' : 'is-review'}`}>
          <CheckCircle2 size={13}/> {item.remoteHearingVerified ? 'Link verificato sull’allegato' : 'Link da controllare sull’allegato'}
        </span>
      ) : null}
    </div>
  )
}

function SourceEvidenceLink({ item, onOpen }: { item: ScadenziarioRow; onOpen: (item: ScadenziarioRow) => void }) {
  if (!item.sourceHref) return null
  const sourceLabel = item.sourceLabel || 'Fonte originaria'
  return (
    <button
      type="button"
      className="iu-scad-source-link"
      onClick={() => onOpen(item)}
      title={`Apri fonte: ${sourceLabel}`}
      aria-label={`Apri fonte: ${sourceLabel}`}
    >
      <FileSearch size={13}/>
      <span>Visualizza fonte</span>
      <small>{sourceLabel}</small>
      {item.sourceVerified ? <CheckCircle2 size={12} aria-label="Fonte verificata"/> : null}
    </button>
  )
}

function DeadlineTable({
  rows,
  selectedIds,
  onToggle,
  onToggleAll,
  onComplete,
  onDelete,
  onOpenSource,
  onOpenDetail,
}:{
  rows: ScadenziarioRow[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onToggleAll: () => void
  onComplete: (item: ScadenziarioRow) => void
  onDelete: (item: ScadenziarioRow) => void
  onOpenSource: (item: ScadenziarioRow) => void
  onOpenDetail: (item: ScadenziarioRow) => void
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
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <tr className={`${item.overdue ? 'is-overdue' : ''} ${item.dueToday ? 'is-today' : ''}`} key={item.id}>
              <td><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.title}`}/></td>
              <td><strong>{item.dateLabel}</strong><span>{item.statusLabel}</span></td>
              <td>
                <a className="iu-scad-title" href={item.href} onClick={(clickEvent) => {
                  if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
                  clickEvent.preventDefault()
                  onOpenDetail(item)
                }}>{item.title}</a>
                <small>{item.description || item.sourceEventLabel || 'Nessuna descrizione operativa.'}</small>
                {item.sourceEventTypeLabel || item.officeLabel ? (
                  <span className="iu-scad-event-line">
                    {item.sourceEventTypeLabel ? `Evento: ${item.sourceEventTypeLabel}` : ''}
                    {item.sourceEventTypeLabel && item.officeLabel ? ' · ' : ''}
                    {item.officeLabel ? `Ufficio: ${item.officeLabel}` : ''}
                  </span>
                ) : null}
                <RemoteHearingNotice item={item}/>
                <SourceEvidenceLink item={item} onOpen={onOpenSource}/>
                <DeadlineFlags item={item}/>
              </td>
              <td className="iu-scad-type-cell">
                <Badge tone="neutral">{item.typeLabel}</Badge>
                <DeadlineActions item={item} onComplete={onComplete} onDelete={onDelete}/>
              </td>
              <td>{item.operative ? <span className="iu-scad-operative"><TimerReset size={14}/>{item.operationalDueLabel}</span> : <span className="iu-scad-muted">—</span>}</td>
              <td><Badge tone={item.tone}>{item.priorityLabel}</Badge></td>
              <td>
                <span className="iu-scad-fascicolo">{item.fascicoloLabel}</span>
                <small>{item.clientLabel && item.clientLabel !== '-' ? item.clientLabel : 'Cliente da collegare'}</small>
              </td>
              <td><b className={`iu-scad-days ${item.overdue ? 'is-negative' : item.dueToday ? 'is-zero' : ''}`}>{item.daysLabel}</b></td>
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
  onOpenSource,
  onOpenDetail,
}:{
  rows: ScadenziarioRow[]
  selectedIds: string[]
  onToggle: (id: string) => void
  onComplete: (item: ScadenziarioRow) => void
  onDelete: (item: ScadenziarioRow) => void
  onOpenSource: (item: ScadenziarioRow) => void
  onOpenDetail: (item: ScadenziarioRow) => void
}) {
  return (
    <div className="iu-scad-card-list">
      {rows.map((item) => (
        <article className={`iu-scad-mobile-card ${item.overdue ? 'is-overdue' : ''}`} key={item.id}>
          <header>
            <label><input type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => onToggle(item.id)}/><span>{item.dateLabel}</span></label>
            <Badge tone={item.tone}>{item.priorityLabel}</Badge>
          </header>
          <a href={item.href} onClick={(clickEvent) => {
            if (clickEvent.button !== 0 || clickEvent.metaKey || clickEvent.ctrlKey || clickEvent.shiftKey || clickEvent.altKey) return
            clickEvent.preventDefault()
            onOpenDetail(item)
          }}>{item.title}</a>
          <p>{item.description || item.fascicoloLabel || 'Scadenza senza descrizione.'}</p>
          {item.sourceEventTypeLabel || item.officeLabel ? (
            <span className="iu-scad-event-line">
              {item.sourceEventTypeLabel ? `Evento: ${item.sourceEventTypeLabel}` : ''}
              {item.sourceEventTypeLabel && item.officeLabel ? ' · ' : ''}
              {item.officeLabel ? `Ufficio: ${item.officeLabel}` : ''}
            </span>
          ) : null}
          <RemoteHearingNotice item={item}/>
          <SourceEvidenceLink item={item} onOpen={onOpenSource}/>
          <div className="iu-scad-mobile-meta">
            <span><CalendarDays size={14}/>{item.daysLabel}</span>
            <span><Gavel size={14}/>{item.typeLabel}</span>
            <span><UsersRound size={14}/>{item.clientLabel && item.clientLabel !== '-' ? item.clientLabel : 'Cliente da collegare'}</span>
            <span><ShieldCheck size={14}/>{item.statusLabel}</span>
          </div>
          <DeadlineFlags item={item}/>
          <DeadlineActions item={item} onComplete={onComplete} onDelete={onDelete}/>
        </article>
      ))}
    </div>
  )
}

const MemoDeadlineTable = memo(DeadlineTable, (previous, next) => (
  previous.rows === next.rows &&
  previous.selectedIds === next.selectedIds
))

const MemoDeadlineCardList = memo(DeadlineCardList, (previous, next) => (
  previous.rows === next.rows &&
  previous.selectedIds === next.selectedIds
))

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

function templateOptionLabel(template: DeadlineCalculatorTemplate, sameNameCount: number): string {
  if (template.displayName) return template.displayName
  if (sameNameCount <= 1) return template.name
  const period = template.period_type === 'months' ? 'mesi' : 'giorni'
  const direction = template.direction === 'backward' ? 'a ritroso' : 'in avanti'
  const reference = template.reference_law ? ` · ${template.reference_law}` : ''
  return `${template.name} · ${template.base_value} ${period} ${direction}${reference}`
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
  const templateNameCounts = templates.reduce((acc, template) => {
    acc.set(template.name, (acc.get(template.name) || 0) + 1)
    return acc
  }, new Map<string, number>())
  return (
    <section id="calcolatore-termini-processuali" className="iu-scad-calculator" aria-label="Calcolatore termini processuali">
      <header>
        <div>
          <span><Gavel size={16}/> Calcolatore termini processuali</span>
          <h2>Calcolo motivato e tracciabile</h2>
          <p>Template versionati, sospensione feriale parametrica, sabato configurabile e conferma professionale quando il caso lo richiede.</p>
        </div>
        <Badge tone={result?.requiresLegalReview ? 'warning' : 'success'}>{result?.requiresLegalReview ? 'richiede verifica' : 'assistente verificabile'}</Badge>
      </header>
      <div className="iu-scad-calculator__grid">
        <div className="iu-scad-calculator__form">
          <label>
            <span>Template</span>
            <select value={form.templateCode} onChange={(event) => onForm(formFromTemplate(form, templates.find((template) => template.code === event.target.value)))}>
              {templates.map((template) => (
                <option value={template.code} key={template.code}>
                  {templateOptionLabel(template, templateNameCounts.get(template.name) || 0)}
                </option>
              ))}
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
            <button type="button" onClick={onCreate} disabled={busy || !result}><CalendarPlus size={15}/> Crea scadenza controllata</button>
          </div>
          {selected ? <small>{selected.reference_law || 'Template configurabile'} · versione {selected.version}</small> : null}
          {status ? <p className="iu-scad-calculator__status">{status}</p> : null}
        </div>
        <div className="iu-scad-calculator__result">
          {result ? (
            <>
              <div className="iu-scad-calculator__deadline">
                <span>Scadenza calcolata</span>
                <strong>{formatItalianDate(result.deadline)}</strong>
                <Badge tone={result.confidence === 'alta' ? 'success' : result.confidence === 'media' ? 'warning' : 'danger'}>confidenza {result.confidence}</Badge>
              </div>
              <p>{result.explanation}</p>
              <div className="iu-scad-calculator__rules">
                {result.rulesApplied.map((rule) => <Badge tone="neutral" key={rule}>{rule.split('_').join(' ')}</Badge>)}
              </div>
              <ol>
                {result.steps.slice(0, 6).map((step) => <li key={`${step.code}-${step.date}`}>{formatItalianDate(step.date)} · {step.label}</li>)}
              </ol>
              <dl>
                <div><dt>Motore</dt><dd>{result.engineVersion}</dd></div>
                <div><dt>Regole</dt><dd>{result.rulesetVersion}</dd></div>
                <div><dt>Calendario</dt><dd>{result.calendarVersion}</dd></div>
                <div><dt>Prova di controllo</dt><dd>{result.audit?.immutableHash.slice(0, 12) || result.resultHash.slice(0, 12)}</dd></div>
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
              <span>Il risultato mostrerà la data, le regole applicate, la spiegazione, le versioni e la prova di controllo.</span>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export function CalcolaTerminiPage() {
  const [calculator, setCalculator] = useState<DeadlineCalculatorState>(emptyScadenziarioPage.calculator)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState<CalculatorForm>(() => defaultCalculatorForm(emptyScadenziarioPage.calculator.templates))
  const [result, setResult] = useState<DeadlineCalculatorResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const guidaPratica = new URLSearchParams(window.location.search).get('guida_pratica') || new URLSearchParams(window.location.search).get('codice_guida') || ''

  useEffect(() => {
    let active = true
    void getDeadlineCalculator({ guidaPratica })
      .then((payload) => {
        if (!active) return
        setCalculator(payload)
        setForm((current) => current.templateCode && payload.templates.some((template) => template.code === current.templateCode)
          ? current
          : defaultCalculatorForm(payload.templates))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [guidaPratica])

  const runCalculator = () => {
    setBusy(true)
    setStatus('Calcolo termine processuale in corso...')
    calculateProcessDeadline(calculator.endpoints.calculate, calculatorRequest(form))
      .then((nextResult) => {
        setResult(nextResult)
        setStatus('Calcolo completato e controllo registrato.')
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : 'Calcolo non riuscito'))
      .finally(() => setBusy(false))
  }

  const runCreateCalculatedDeadline = () => {
    if (!result) return
    setBusy(true)
    setStatus('Creazione della scadenza controllata...')
    createProcessDeadline(calculator.endpoints.createDeadline, calculatorRequest(form))
      .then((created) => {
        setStatus(created.messaggio)
        window.location.assign(created.href)
      })
      .catch((error) => setStatus(error instanceof Error ? error.message : 'Creazione scadenza non riuscita'))
      .finally(() => setBusy(false))
  }

  return (
    <main className="iu-content iu-scad-page iu-scad-calculator-page iusentra-route-sequence">
      <section className="iu-scad-hero" data-iusentra-sequence-slot="page-header">
        <div>
          <span className="iu-scad-eyebrow"><Gavel size={16}/> Calcola termini processuali</span>
          <h1>Calcola termini processuali</h1>
          <p>Calcolo separato dallo scadenziario: carica solo template, regole e fonti necessarie, senza leggere l'elenco delle scadenze.</p>
        </div>
        <div className="iu-scad-hero__actions">
          <Button href="/scadenziario"><ArrowLeft size={15}/> Torna allo scadenziario</Button>
        </div>
      </section>

      {loading ? <section className="iu-scad-status-line"><span>Caricamento delle regole di calcolo...</span></section> : null}
      <ProcessDeadlineCalculator
        templates={calculator.templates}
        result={result}
        form={form}
        busy={busy}
        status={status}
        onForm={setForm}
        onCalculate={runCalculator}
        onCreate={runCreateCalculatedDeadline}
      />
    </main>
  )
}

function PdfDeadlineImportPanel({
  preview,
  selectedIds,
  busy,
  status,
  onScan,
  onImport,
  onToggle,
  onToggleAll,
  onRemove,
  onRemoveSelected,
  onClearAll,
}:{
  preview: PdfDeadlinePreview | null
  selectedIds: string[]
  busy: boolean
  status: string
  onScan: () => void
  onImport: () => void
  onToggle: (id: string) => void
  onToggleAll: () => void
  onRemove: (id: string) => void
  onRemoveSelected: () => void
  onClearAll: () => void
}) {
  const candidates = preview?.candidates || []
  const importable = candidates.filter((candidate) => !candidate.duplicate)
  const allSelected = importable.length > 0 && importable.every((candidate) => selectedIds.includes(candidate.id))
  return (
    <section className="iu-scad-pdf-panel" aria-label="Importazione scadenze dai PDF">
      <header>
        <div>
          <span><FileSearch size={16}/> Scadenze dai PDF</span>
          <h2>Trova termini nei documenti dei fascicoli</h2>
          <p>Prima mostra un'anteprima: importi solo le righe confermate e le scadenze già presenti vengono saltate.</p>
        </div>
        <div>
          <button type="button" onClick={onScan} disabled={busy}><FileSearch size={15}/> Analizza PDF</button>
          <button type="button" onClick={onImport} disabled={busy || !selectedIds.length}><CalendarPlus size={15}/> Importa selezionate{selectedIds.length ? ` (${selectedIds.length})` : ''}</button>
          <button type="button" className="iu-scad-pdf-danger-btn" onClick={onRemoveSelected} disabled={busy || !selectedIds.length}><Trash2 size={15}/> Elimina selezionate</button>
          <button type="button" className="iu-scad-pdf-danger-btn" onClick={onClearAll} disabled={busy || !candidates.length}><Trash2 size={15}/> Elimina tutto</button>
        </div>
      </header>
      {status ? <p className="iu-scad-pdf-panel__status">{status}</p> : null}
      {preview ? (
        <div className="iu-scad-pdf-panel__summary">
          <Badge tone="primary">{preview.summary.scannedDocuments} PDF letti</Badge>
          <Badge tone={preview.summary.newCandidates ? 'success' : 'neutral'}>{preview.summary.newCandidates} nuove</Badge>
          <Badge tone={preview.summary.duplicates ? 'warning' : 'neutral'}>{preview.summary.duplicates} già presenti</Badge>
          <Badge tone={preview.summary.warnings ? 'warning' : 'neutral'}>{preview.summary.warnings} avvisi</Badge>
        </div>
      ) : null}
      {candidates.length ? (
        <div className="iu-scad-pdf-candidates">
          <label className="iu-scad-pdf-select-all">
            <input type="checkbox" checked={allSelected} onChange={onToggleAll}/>
            <span>Seleziona tutte le nuove scadenze</span>
          </label>
          {candidates.slice(0, 40).map((candidate) => (
            <article className={`iu-scad-pdf-candidate ${candidate.duplicate ? 'is-duplicate' : ''}`} key={candidate.id}>
              <label>
                <input type="checkbox" disabled={candidate.duplicate} checked={selectedIds.includes(candidate.id)} onChange={() => onToggle(candidate.id)}/>
                <span>{candidate.dueDate}</span>
              </label>
              <div>
                <strong>{candidate.title}</strong>
                <p>{candidate.context}</p>
                <small>{candidate.fascicoloLabel} · {candidate.documentName} · pag. {candidate.page}</small>
                <div className="iu-scad-pdf-links">
                  <a href={candidate.documentHref} target="_blank" rel="noreferrer"><FileDown size={13}/> Documento</a>
                  {candidate.urls.slice(0, 2).map((url) => <a href={url} target="_blank" rel="noreferrer" key={url}><Link2 size={13}/> Link PDF</a>)}
                </div>
              </div>
              <div className="iu-scad-pdf-candidate__actions">
                <Badge tone={candidate.duplicate ? 'warning' : candidate.confidence >= 0.85 ? 'success' : 'primary'}>
                  {candidate.duplicate ? 'già presente' : `${Math.round(candidate.confidence * 100)}%`}
                </Badge>
                <button type="button" className="iu-scad-pdf-row-delete" onClick={() => onRemove(candidate.id)} disabled={busy} aria-label={`Elimina ${candidate.title}`}>
                  <Trash2 size={14}/>
                </button>
              </div>
            </article>
          ))}
          {candidates.length > 40 ? <p className="iu-scad-pdf-panel__status">Mostro le prime 40 righe: importa quelle utili o filtra per fascicolo dalla pagina del fascicolo.</p> : null}
        </div>
      ) : preview ? (
        <div className="iu-scad-pdf-empty">
          <FileSearch size={28}/>
          <strong>Nessuna nuova scadenza trovata nei PDF letti</strong>
          <span>Se il PDF è una scansione, serve testo OCR leggibile; se la data non è un termine, resta fuori dall'importazione automatica.</span>
        </div>
      ) : null}
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
        const value = isBulk ? selectedCount : card.value
        return (
          <article className={`iu-scad-action-card iu-scad-action-card--${card.tone}`} key={card.id}>
            <div>{actionIcon(card.icon)}</div>
            <span>{card.title}</span>
            <strong>{value}</strong>
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
  const watch = rows.filter((item) => !item.overdue && (item.dueToday || item.priority === 'CRITICA' || item.operative || item.remoteHearingDetected)).slice(0, 5)
  const advanced = rows.filter((item) => !item.overdue && (item.advanced || item.operative)).slice(0, 5)
  return (
    <aside className="iu-scad-inspector">
      <Panel title="Briefing Lex" subtitle="Contesto pronto per la prossima azione" icon={<Sparkles size={17}/>}>
        <div className="iu-scad-briefing">
          <article>
            <span>Da presidiare ora</span>
            <strong>{watch.length}</strong>
            <small>Aperte, odierne, critiche o con udienza da remoto nella vista corrente.</small>
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
        ) : <p className="iu-empty">Nessun termine aperto e critico nella vista corrente.</p>}
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
  const deadlineTableRef = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<ScadenziarioPageData>(emptyScadenziarioPage)
  const [loading, setLoading] = useState(true)
  const [backgroundLoading, setBackgroundLoading] = useState(false)
  const [view, setView] = useState<ScadenziarioView>(() => initialView())
  const [query, setQuery] = useState(() => initialQuery())
  const [guidaPratica] = useState(() => initialGuidaPratica())
  const [fascicoloId] = useState(() => initialFascicoloId())
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
  const [pdfPanelOpen, setPdfPanelOpen] = useState(false)
  const [pdfPreview, setPdfPreview] = useState<PdfDeadlinePreview | null>(null)
  const [pdfSelectedIds, setPdfSelectedIds] = useState<string[]>([])
  const [pdfBusy, setPdfBusy] = useState(false)
  const [pdfStatus, setPdfStatus] = useState('')
  const [sourcePreview, setSourcePreview] = useState<ScadenziarioRow | null>(null)
  const [detailPreviewId, setDetailPreviewId] = useState<string>(() => routeDeadlineId())
  const [tableFullscreen, setTableFullscreen] = useState(false)

  useEffect(() => {
    const syncFullscreenState = () => setTableFullscreen(document.fullscreenElement === deadlineTableRef.current)
    document.addEventListener('fullscreenchange', syncFullscreenState)
    return () => document.removeEventListener('fullscreenchange', syncFullscreenState)
  }, [])

  useEffect(() => {
    if (!tableFullscreen) return undefined
    const previousOverflow = document.body.style.overflow
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setTableFullscreen(false)
    }
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [tableFullscreen])

  const buildQuery = (compact = false): ScadenziarioQuery => ({
    view,
    q: query,
    type,
    priority,
    from,
    to,
    peremptory,
    advanced,
    operative,
    guidaPratica,
    fascicoloId,
    focusId: compact ? routeDeadlineId() : undefined,
    compact,
    includeCalculator: false,
  })

  const load = () => {
    setLoading(true)
    setBackgroundLoading(false)
    getScadenziarioPage(buildQuery(false)).then((payload) => {
      setData(payload)
      setSelectedIds((current) => current.filter((id) => payload.items.some((item) => item.id === id)))
    }).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    setBackgroundLoading(false)

    const applyPayload = (payload: ScadenziarioPageData) => {
      if (!active) return
      setData(payload)
      setSelectedIds((current) => current.filter((id) => payload.items.some((item) => item.id === id)))
    }

    const focusedId = routeDeadlineId()
    const loadPage = async () => {
      if (focusedId) {
        const compactPayload = await getScadenziarioPage(buildQuery(true))
        if (!active) return
        applyPayload(compactPayload)
        setLoading(false)
        setBackgroundLoading(false)
        return
      }

      const payload = await getScadenziarioPage(buildQuery(false))
      if (!active) return
      applyPayload(payload)
      setLoading(false)
    }

    const timer = window.setTimeout(() => {
      void loadPage().finally(() => {
        if (active) {
          setLoading(false)
          setBackgroundLoading(false)
        }
      })
    }, query.trim() ? 250 : 0)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [view, query, type, priority, from, to, peremptory, advanced, operative, guidaPratica, fascicoloId])

  const visibleRows = useMemo(() => sortRows(data.items.filter((item) => isInsideQuery(item, query)), sort), [data.items, query, sort])
  const mobileLayout = useScadenziarioMobileLayout()

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

  const runConfirmProposal = (item: ScadenziarioDraftProposal) => {
    setStatusLine(`Conferma della proposta "${item.title}"...`)
    postDeadlineAction(item.confirmHref, 'Conferma proposta')
      .then((message) => { setStatusLine(message); load() })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : 'Conferma non riuscita'))
  }

  const runDiscardProposal = (item: ScadenziarioDraftProposal) => {
    const motivo = window.prompt('Scartare la proposta? Indica il motivo (facoltativo):', '')
    if (motivo === null) return
    const body = new URLSearchParams()
    body.set('motivo', motivo)
    setStatusLine(`Scarto della proposta "${item.title}"...`)
    postDeadlineAction(item.discardHref, 'Scarta proposta', body)
      .then((message) => { setStatusLine(message); load() })
      .catch((error) => setStatusLine(error instanceof Error ? error.message : 'Scarto non riuscito'))
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

  const changeView = (nextView: ScadenziarioView) => {
    setView(nextView)
    setSelectedIds([])
    const url = new URL(window.location.href)
    url.searchParams.set('vista', nextView)
    window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}`)
  }

  const resetFilters = () => {
    changeView('aperte')
    setQuery('')
    setType('')
    setPriority('')
    setFrom('')
    setTo('')
    setPeremptory(false)
    setAdvanced(false)
    setOperative(false)
  }

  const toggleDeadlineTableFullscreen = async () => {
    const tableCard = deadlineTableRef.current
    if (!tableCard) return
    if (tableFullscreen) {
      if (document.fullscreenElement === tableCard) {
        try {
          await document.exitFullscreen()
        } catch {
          // La vista espansa dell'app resta disponibile anche quando il browser nega l'uscita nativa.
        }
      }
      setTableFullscreen(false)
      return
    }
    if (tableCard.requestFullscreen) {
      try {
        await tableCard.requestFullscreen()
        setTableFullscreen(true)
        return
      } catch {
        // La vista espansa dell'app mantiene la tabella operativa quando il browser nega il fullscreen nativo.
      }
    }
    setTableFullscreen(true)
  }

  const pdfRequestOptions = () => ({
    fascicoloId: fascicoloId || undefined,
    maxDocuments: fascicoloId ? 0 : 25,
  })

  const runPdfPreview = () => {
    setPdfPanelOpen(true)
    setPdfBusy(true)
    setPdfStatus('Lettura dei PDF dei fascicoli in corso...')
    previewPdfDeadlines(data.calculator.endpoints.pdfPreview, pdfRequestOptions())
      .then((payload) => {
        setPdfPreview(payload)
        setPdfSelectedIds(payload.candidates.filter((candidate) => candidate.selected && !candidate.duplicate).map((candidate) => candidate.id))
        setPdfStatus(`Analisi completata: ${payload.summary.newCandidates} nuove scadenze e ${payload.summary.duplicates} già presenti.`)
      })
      .catch((error) => setPdfStatus(error instanceof Error ? error.message : 'Scansione PDF non completata'))
      .finally(() => setPdfBusy(false))
  }

  const togglePdfCandidate = (id: string) => {
    const candidate = pdfPreview?.candidates.find((item) => item.id === id)
    if (!candidate || candidate.duplicate) return
    setPdfSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  }

  const toggleAllPdfCandidates = () => {
    const importableIds = (pdfPreview?.candidates || []).filter((candidate) => !candidate.duplicate).map((candidate) => candidate.id)
    setPdfSelectedIds((current) => {
      const allSelected = importableIds.length > 0 && importableIds.every((id) => current.includes(id))
      return allSelected ? [] : importableIds
    })
  }

  const updatePdfPreviewCandidates = (nextCandidates: PdfDeadlinePreview['candidates']) => {
    setPdfPreview((current) => {
      if (!current) return current
      return {
        ...current,
        candidates: nextCandidates,
        summary: {
          ...current.summary,
          newCandidates: nextCandidates.filter((candidate) => !candidate.duplicate).length,
          duplicates: nextCandidates.filter((candidate) => candidate.duplicate).length,
          warnings: nextCandidates.reduce((total, candidate) => total + candidate.warnings.length, 0),
        },
      }
    })
  }

  const removePdfCandidates = (ids: string[], label: string) => {
    if (!pdfPreview || !ids.length) return
    const toRemove = new Set(ids)
    const nextCandidates = pdfPreview.candidates.filter((candidate) => !toRemove.has(candidate.id))
    updatePdfPreviewCandidates(nextCandidates)
    setPdfSelectedIds((current) => current.filter((id) => !toRemove.has(id) && nextCandidates.some((candidate) => candidate.id === id)))
    setPdfStatus(label)
  }

  const removePdfCandidate = (id: string) => {
    removePdfCandidates([id], 'Riga rimossa dall’anteprima PDF. Nulla è stato cancellato dallo scadenziario.')
  }

  const removeSelectedPdfCandidates = () => {
    removePdfCandidates(pdfSelectedIds, `${pdfSelectedIds.length} righe rimosse dall’anteprima PDF. Nulla è stato cancellato dallo scadenziario.`)
  }

  const clearPdfCandidates = () => {
    if (!pdfPreview?.candidates.length) return
    updatePdfPreviewCandidates([])
    setPdfSelectedIds([])
    setPdfStatus('Anteprima PDF svuotata. Nulla è stato cancellato dallo scadenziario.')
  }

  const runPdfImport = () => {
    if (!pdfSelectedIds.length) return
    setPdfBusy(true)
    setPdfStatus('Importazione nello Scadenziario in corso...')
    const options = pdfRequestOptions()
    importPdfDeadlines(data.calculator.endpoints.pdfImport, pdfSelectedIds, options)
      .then((result) => {
        setPdfStatus(result.message)
        setPdfSelectedIds([])
        load()
        return previewPdfDeadlines(data.calculator.endpoints.pdfPreview, options)
      })
      .then((payload) => setPdfPreview(payload))
      .catch((error) => setPdfStatus(error instanceof Error ? error.message : 'Importazione PDF non completata'))
      .finally(() => setPdfBusy(false))
  }
  const focusedRow = detailPreviewId ? data.items.find((item) => item.id === detailPreviewId) : undefined
  const isNotificationPresidio = focusedRow?.sourceEventType === 'legal_notification_presidio'

  useEffect(() => {
    const syncDetailFromRoute = () => {
      const routeId = routeDeadlineId()
      setDetailPreviewId(routeId)
    }
    window.addEventListener('popstate', syncDetailFromRoute)
    return () => window.removeEventListener('popstate', syncDetailFromRoute)
  }, [data.items])

  const openDeadlineDetail = (item: ScadenziarioRow) => {
    window.history.pushState(window.history.state, '', `/scadenziario/${encodeURIComponent(item.id)}${window.location.search}`)
    setDetailPreviewId(item.id)
  }

  const closeDeadlineDetail = () => {
    window.history.replaceState(window.history.state, '', `/scadenziario${window.location.search}`)
    setDetailPreviewId('')
    if (data.query.compact) {
      load()
    }
  }

  return (
    <main className="iu-content iu-scad-page iusentra-route-sequence">
      <section className="iu-scad-hero" data-iusentra-sequence-slot="page-header">
        <div>
          <span className="iu-scad-eyebrow"><CalendarCheck size={16}/> Scadenziario Legale</span>
          <h1>Scadenziario Legale</h1>
          <p>Termini, udienze, depositi, calcoli avanzati e priorità operative dello studio in una cabina professionale.</p>
        </div>
        <div className="iu-scad-hero__actions">
          <Button href="/workspace-intelligente"><Sparkles size={15}/> Cabina</Button>
          <button type="button" onClick={() => { setPdfPanelOpen((value) => !value); if (!pdfPreview) runPdfPreview() }}><FileSearch size={15}/> Scadenze PDF</button>
          <Button href={data.actions.exportCsv}><Download size={15}/> CSV</Button>
          <Button href={data.actions.exportPdf}><FileDown size={15}/> PDF</Button>
          <Button href={data.actions.exportIcs}><ChevronDown size={15}/> iCal</Button>
          <Button variant="primary" href={data.actions.new}><CalendarPlus size={16}/> Nuova scadenza</Button>
        </div>
      </section>

      {data.overduePreview.length && (view === 'scadute' || view === 'tutte') ? (
        <section className="iu-scad-alert" role="alert">
          <AlertTriangle size={22}/>
          <div>
            <strong>{data.summary.overdue} scadenze scadute nello storico.</strong>
            <p>{data.overduePreview.slice(0, 3).map((item) => `${item.title} — ${item.dateLabel}`).join(' · ')}</p>
          </div>
          <button type="button" onClick={() => changeView('scadute')}>Apri storico scadute</button>
        </section>
      ) : null}

      <section className="iu-scad-stats" aria-label="Indicatori scadenziario">
        <StatCard icon={<CalendarDays size={19}/>} label="Aperte" value={data.summary.open} note="da lavorare" tone="primary" active={view === 'aperte'} onClick={() => changeView('aperte')}/>
        <StatCard icon={<AlertTriangle size={19}/>} label="Critiche" value={data.summary.critical} note="massima priorità" tone={data.summary.critical ? 'danger' : 'neutral'} active={view === 'critiche'} onClick={() => changeView('critiche')}/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Alta priorità" value={data.summary.high} note="da presidiare" tone={data.summary.high ? 'warning' : 'neutral'} active={view === 'alte'} onClick={() => changeView('alte')}/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="Completate" value={data.summary.completed} note="chiuse" tone="success" active={view === 'completate'} onClick={() => changeView('completate')}/>
        <StatCard icon={<TimerReset size={19}/>} label="Storico scadute" value={data.summary.overdue} note="fuori dalla vista operativa" tone={data.summary.overdue ? 'warning' : 'neutral'} active={view === 'scadute'} onClick={() => changeView('scadute')}/>
        <StatCard icon={<Clock3 size={19}/>} label="Entro 7 gg" value={data.summary.within7} note="orizzonte breve" tone={data.summary.within7 ? 'orange' : 'neutral'} active={view === 'imminenti'} onClick={() => changeView('imminenti')}/>
        <StatCard icon={<Wand2 size={19}/>} label="Avanzate" value={data.summary.advanced} note="calcolo legale" tone="purple" active={view === 'avanzate'} onClick={() => changeView('avanzate')}/>
        <StatCard icon={<ListChecks size={19}/>} label="Operative" value={data.summary.operative} note="anticipo studio" tone="info" active={view === 'operative'} onClick={() => changeView('operative')}/>
        <StatCard icon={<Archive size={19}/>} label="Da PEC" value={data.summary.pec} note="aperte operative" tone="info" active={view === 'pec'} onClick={() => changeView('pec')}/>
      </section>

      <DraftProposalsPanel proposals={data.draftProposals} onConfirm={runConfirmProposal} onDiscard={runDiscardProposal}/>

      <section className="iu-scad-toolbar" aria-label="Filtri scadenziario">
        <label className="iu-scad-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') load() }} placeholder="Cerca per titolo, descrizione, fascicolo, ufficio..."/></label>
        <div className="iu-scad-toolbar__filters">
          <label className="iu-scad-select"><Filter size={16}/><select value={type} onChange={(event) => setType(event.target.value)}>{data.facets.types.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label}{facet.count ? ` (${facet.count})` : ''}</option>)}</select></label>
          <label className="iu-scad-select"><ShieldCheck size={16}/><select value={priority} onChange={(event) => setPriority(event.target.value)}>{data.facets.priorities.map((facet) => <option value={facet.value} key={facet.value || 'all'}>{facet.label}{facet.count ? ` (${facet.count})` : ''}</option>)}</select></label>
        </div>
        <div className="iu-scad-toolbar__actions">
          <button className="iu-scad-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><SlidersHorizontal size={16}/> Filtri</button>
          <button className="iu-scad-icon-btn" type="button" onClick={load} aria-label="Aggiorna scadenziario"><RefreshCw size={17}/></button>
          <button className="iu-scad-reset" type="button" onClick={resetFilters}><X size={15}/> Reset</button>
        </div>
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

      {pdfPanelOpen ? (
        <PdfDeadlineImportPanel
          preview={pdfPreview}
          selectedIds={pdfSelectedIds}
          busy={pdfBusy}
          status={pdfStatus}
          onScan={runPdfPreview}
          onImport={runPdfImport}
          onToggle={togglePdfCandidate}
          onToggleAll={toggleAllPdfCandidates}
          onRemove={removePdfCandidate}
          onRemoveSelected={removeSelectedPdfCandidates}
          onClearAll={clearPdfCandidates}
        />
      ) : null}

      <OperativeCards cards={data.operativeCards} selectedCount={selectedIds.length} onFilter={changeView} onBulkComplete={runBulkComplete}/>

      <section className="iu-scad-status-line">
        <span className={loading ? '' : 'is-ok'}>
          {loading ? 'Sincronizzazione scadenziario...' : backgroundLoading ? 'Dettaglio disponibile, aggiornamento elenco in corso...' : 'Dati scadenziario aggiornati'}
        </span>
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
        <OperationalModal
          open
          ariaLabel="Scadenza selezionata"
          eyebrow={<><CalendarCheck size={14}/> Scadenza selezionata</>}
          title={focusedRow.title}
          subtitle={[focusedRow.fascicoloLabel, focusedRow.clientLabel].filter(Boolean).join(' · ')}
          onClose={closeDeadlineDetail}
          boxClassName="iu-ag-source-modal__box--detail"
          bodyClassName="iu-ag-source-modal__body--detail"
        >
          <section className="iu-scad-focus-card" data-iusentra-sequence-slot="operational-subtitle" aria-label="Scadenza selezionata">
          <div>
            <Badge tone={focusedRow.tone}>{focusedRow.statusLabel}</Badge>
            <h2>{focusedRow.title}</h2>
            <p>{focusedRow.detailDescription || focusedRow.description || focusedRow.fascicoloLabel || 'Dettaglio operativo della scadenza selezionata.'}</p>
            <dl>
              <div><dt>{isNotificationPresidio ? 'Attività da presidiare' : 'Scadenza legale'}</dt><dd>{focusedRow.dateLabel}</dd></div>
              {isNotificationPresidio ? <div><dt>Visibilità</dt><dd>Calendario e notifiche operative</dd></div> : <div><dt>Scadenza operativa</dt><dd>{focusedRow.operationalDueLabel || 'Non impostata'}</dd></div>}
              <div><dt>Priorità</dt><dd>{focusedRow.priorityLabel}</dd></div>
              <div><dt>Responsabile</dt><dd>{focusedRow.ownerLabel || 'Non assegnato'}</dd></div>
              {focusedRow.sourceEventTypeLabel ? <div><dt>Evento</dt><dd>{focusedRow.sourceEventTypeLabel}</dd></div> : null}
              {focusedRow.officeLabel ? <div><dt>Ufficio</dt><dd>{focusedRow.officeLabel}</dd></div> : null}
              {focusedRow.hearingMode ? <div><dt>Modalità udienza</dt><dd>{focusedRow.hearingMode}</dd></div> : null}
              {focusedRow.hearingTime ? <div><dt>Orario udienza</dt><dd>{focusedRow.hearingTime}</dd></div> : null}
              {focusedRow.hearingModeSource ? <div><dt>Fonte modalità</dt><dd>{focusedRow.hearingModeSource}</dd></div> : null}
              {focusedRow.remoteHearingSource ? <div><dt>Allegato udienza</dt><dd>{focusedRow.remoteHearingSource}</dd></div> : null}
              {focusedRow.remoteHearingPlatform ? <div><dt>Piattaforma</dt><dd>{focusedRow.remoteHearingPlatform}</dd></div> : null}
              {focusedRow.remoteHearingMeetingId ? <div><dt>ID riunione</dt><dd>{focusedRow.remoteHearingMeetingId}</dd></div> : null}
              {focusedRow.remoteHearingPasscode ? <div><dt>Codice di accesso</dt><dd>{focusedRow.remoteHearingPasscode}</dd></div> : null}
              {focusedRow.remoteHearingUrl ? <div><dt>Controllo link</dt><dd>{focusedRow.remoteHearingVerified ? 'Verificato sull’allegato' : 'Da controllare sull’allegato'}</dd></div> : null}
              {focusedRow.remoteHearingPdfRequired ? <div><dt>Link udienza</dt><dd>Da acquisire dal PDF allegato</dd></div> : null}
              {focusedRow.officeModeLabel ? <div><dt>Operatività ufficio</dt><dd>{focusedRow.officeModeLabel}</dd></div> : null}
              {focusedRow.officePatronLabel ? <div><dt>Patrono ufficio</dt><dd>{focusedRow.officePatronLabel}</dd></div> : null}
              {focusedRow.octoberObservanceBlocks ? <div><dt>Osservanza</dt><dd>Osservanza bloccante</dd></div> : null}
            </dl>
            {focusedRow.remoteHearingAccessInfo ? <p className="iu-scad-remote-access">{focusedRow.remoteHearingAccessInfo}</p> : null}
          </div>
          <div className="iu-scad-focus-actions">
            {focusedRow.remoteHearingUrl ? (
              <a className="iu-scad-remote-action" href={focusedRow.remoteHearingUrl} target="_blank" rel="noreferrer">
                <Link2 size={15}/> Apri link udienza
              </a>
            ) : null}
            {focusedRow.sourceHref ? <button type="button" onClick={() => setSourcePreview(focusedRow)}><FileSearch size={15}/> Apri fonte</button> : null}
            <Button href={focusedRow.editHref}><Edit3 size={15}/> Modifica</Button>
            <button type="button" onClick={() => runComplete(focusedRow)}><CheckCircle2 size={15}/> Completa</button>
            <button type="button" onClick={() => runDelete(focusedRow)}><Trash2 size={15}/> Elimina</button>
            <button type="button" onClick={closeDeadlineDetail}><ArrowLeft size={15}/> Torna allo scadenziario</button>
          </div>
          </section>
        </OperationalModal>
      ) : null}

      <section className="iu-scad-layout">
        <div className={`iu-scad-table-card${tableFullscreen ? ' iu-scad-table-card--fullscreen' : ''}`} ref={deadlineTableRef}>
          <header>
            <div><strong>{visibleRows.length} scadenze</strong><span>{query.trim() ? 'Ricerca in tutto lo scadenziario' : (data.facets.views.find((facet) => facet.value === view)?.label || 'Vista corrente')} · {sourceLabel(data.source)}</span></div>
            <div>
              <Badge tone={query.trim() || view === 'scadute' || view === 'tutte' ? 'warning' : 'success'}>
                {query.trim() ? 'tutti gli stati' : (view === 'scadute' || view === 'tutte' ? `${data.summary.overdue} nello storico` : 'vista operativa')}
              </Badge>
              <button
                className="iu-scad-table-fullscreen"
                type="button"
                onClick={() => void toggleDeadlineTableFullscreen()}
                aria-label={tableFullscreen ? 'Chiudi elenco scadenze a schermo intero' : 'Apri elenco scadenze a schermo intero'}
                aria-pressed={tableFullscreen}
                title={tableFullscreen ? 'Chiudi schermo intero' : 'Apri a schermo intero'}
              >
                {tableFullscreen ? <Minimize2 size={15}/> : <Maximize2 size={15}/>}
                <span>{tableFullscreen ? 'Chiudi schermo intero' : 'Apri a schermo intero'}</span>
              </button>
              <a href={data.actions.exportCsv}><Download size={15}/> Esporta</a>
            </div>
          </header>
          {visibleRows.length ? (
            <>
              {mobileLayout ? (
                <MemoDeadlineCardList rows={visibleRows} selectedIds={selectedIds} onToggle={toggleSelection} onComplete={runComplete} onDelete={runDelete} onOpenSource={setSourcePreview} onOpenDetail={openDeadlineDetail}/>
              ) : (
                <MemoDeadlineTable rows={visibleRows} selectedIds={selectedIds} onToggle={toggleSelection} onToggleAll={toggleAll} onComplete={runComplete} onDelete={runDelete} onOpenSource={setSourcePreview} onOpenDetail={openDeadlineDetail}/>
              )}
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
        <Panel title="Qualità scadenziario" subtitle="Controlli disponibili nella pagina" icon={<ShieldCheck size={17}/>}>
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
      <SourceDocumentModal
        source={sourcePreview ? {
          href: sourcePreview.sourceHref,
          label: sourcePreview.sourceLabel || 'Fonte originaria',
          context: [sourcePreview.title, sourcePreview.fascicoloLabel, sourcePreview.clientLabel].filter(Boolean).join(' · '),
          kind: sourcePreview.sourceKind,
        } : null}
        onClose={() => setSourcePreview(null)}
      />
    </main>
  )
}
