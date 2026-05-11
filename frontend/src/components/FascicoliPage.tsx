import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  Archive,
  ArrowLeft,
  BadgeCheck,
  Bell,
  BrainCircuit,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Clock3,
  Download,
  Edit3,
  Eye,
  FileArchive,
  FileCheck2,
  FileDown,
  FileText,
  Filter,
  FolderOpen,
  FolderPlus,
  Gauge,
  Gavel,
  Landmark,
  ListChecks,
  Mail,
  PencilLine,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  UserRound,
  UsersRound,
  WalletCards,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
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
  getFascicoloDetail,
  getFascicoloDetailSection,
  getFascicoloForm,
  type FascicoliPageData,
  type FascicoliExportData,
  type FascicoloActivity,
  type FascicoloDeadline,
  type FascicoloDetailData,
  type FascicoloDocument,
  type FascicoloDetailSection,
  type LexIndexingSummary,
  type FascicoloFormData,
  type FascicoloRow,
  type FascicoloStato,
  type FascicoloTipo,
  type KeyValue,
  type SelectOption,
  type FascicoliPagination,
} from '../fascicoliData'
import {
  NUOVO_FASCICOLO_LABELS,
  PRATICHE_COLLEGATE,
  PRATICHE_COLLEGATE_CATALOG,
  STATI_PRATICA,
  findPraticaCollegata,
} from '../data/praticheCollegateCatalog'
import { redirectAfterSuccess, submitFormJson } from '../formSubmit'
import './FascicoliPage.css'

type SortKey = 'recenti' | 'rg' | 'cliente' | 'scadenza' | 'documenti'
type Route =
  | { kind: 'list' }
  | { kind: 'archive' }
  | { kind: 'new' }
  | { kind: 'export' }
  | { kind: 'detail'; id: string }
  | { kind: 'quadro'; id: string }
  | { kind: 'signature'; id: string; documentId: string }
  | { kind: 'edit'; id: string }

const sortLabels: Record<SortKey, string> = {
  recenti: 'Aggiornati di recente',
  rg: 'Numero RG',
  cliente: 'Cliente',
  scadenza: 'Prossima scadenza',
  documenti: 'Documenti',
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

function StatCard({ icon, label, value, note, tone = 'primary', href }:{icon:ReactNode; label:string; value:number|string; note:string; tone?:FascicoloRow['tone']; href?:string}) {
  const body = (
    <>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </>
  )
  return href ? <a className={`iu-fas-stat iu-fas-stat--${tone}`} href={href}>{body}</a> : <article className={`iu-fas-stat iu-fas-stat--${tone}`}>{body}</article>
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
      <button className={`iu-fas-post iu-fas-post--${tone}`} type="button" onClick={() => confirm ? setConfirming(true) : void run()} disabled={busy} title={title} aria-label={ariaLabel}>{children}</button>
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

function LexIndexingPanel({ summary, refreshAction, retryAction, onDone, onError }:{summary:LexIndexingSummary; refreshAction:string; retryAction:string; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const working = summary.queued + summary.indexing
  const tone = summary.status === 'ready' ? 'success' : summary.status === 'error' ? 'danger' : summary.status === 'stale' ? 'warning' : 'info'
  const statusLabel: Record<LexIndexingSummary['status'], string> = { ready: 'Pronto', partial: 'Parziale', working: 'In corso', error: 'Errore', stale: 'Da aggiornare' }
  const message = summary.errors > 0
    ? 'Alcuni documenti non sono stati indicizzati. Apri la diagnostica tecnica o riprova l’indicizzazione.'
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
        <Badge tone={tone}>{statusLabel[summary.status] || summary.status}</Badge>
      </header>
      <dl>
        <div><dt>Totali</dt><dd>{summary.total_documents}</dd></div>
        <div><dt>Pronti</dt><dd>{summary.ready}</dd></div>
        <div><dt>In coda</dt><dd>{summary.queued}</dd></div>
        <div><dt>In corso</dt><dd>{summary.indexing}</dd></div>
        <div><dt>Errori</dt><dd>{summary.errors}</dd></div>
        <div><dt>Da aggiornare</dt><dd>{summary.stale}</dd></div>
      </dl>
      <footer>
        <span>Ultimo indice: {summary.last_indexed_at ? new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(summary.last_indexed_at)) : 'mai'}</span>
        <div>
          {refreshAction ? <PostAction action={refreshAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={15}/> Aggiorna indice</PostAction> : null}
          {retryAction && summary.errors > 0 ? <PostAction action={retryAction} tone="secondary" onDone={onDone} onError={onError}><RotateCcw size={15}/> Riprova errori</PostAction> : null}
        </div>
      </footer>
    </section>
  )
}

function RowActions({ item, archive = false, onDeleted, onError }:{item:FascicoloRow; archive?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void}) {
  const deleteHref = item.deleteHref || `/fascicoli/${encodeURIComponent(item.id)}/elimina`
  return (
    <div className="iu-fas-actions" aria-label={`Azioni fascicolo ${item.ref}`}>
      <a href={item.href} aria-label="Apri fascicolo" title="Apri"><Eye size={15}/></a>
      {!archive ? <a href={item.editHref} aria-label="Modifica fascicolo" title="Modifica"><PencilLine size={15}/></a> : null}
      <a href={item.exportPdfHref} aria-label="Esporta PDF fascicolo" title="PDF"><FileDown size={15}/></a>
      {archive && item.archive?.zipAvailable ? <a href={item.archiveZipHref} aria-label="Scarica ZIP archivio" title="ZIP"><FileArchive size={15}/></a> : null}
      <PostAction action={deleteHref} tone="danger" confirm={`Eliminare definitivamente il fascicolo ${item.ref}?`} confirmTitle="Elimina fascicolo" onDone={(message) => onDeleted?.(item.id, message)} onError={onError} title="Elimina fascicolo" ariaLabel={`Elimina fascicolo ${item.ref}`}><Trash2 size={15}/></PostAction>
    </div>
  )
}

function DossierMobileCard({ item, checked, onToggle, archive = false, onDeleted, onError }:{item:FascicoloRow; checked:boolean; onToggle:()=>void; archive?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void}) {
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
      <dl>
        <div><dt>Cliente</dt><dd>{item.client}</dd></div>
        <div><dt>Tipo</dt><dd>{formatFascicoloType(item.type)}</dd></div>
        <div><dt>N. causa</dt><dd>{item.rg}</dd></div>
        <div><dt>{archive ? 'Archiviazione' : 'Prossima scad.'}</dt><dd>{archive ? item.archive?.archivedAt || 'n.d.' : item.nextDeadline || 'n.d.'}</dd></div>
      </dl>
      <footer>
        <span><FileText size={14}/> {item.documents}</span>
        {item.unreadCommunications ? <span><Bell size={14}/> {item.unreadCommunications}</span> : null}
        {item.alerts ? <span><ShieldCheck size={14}/> {item.alerts}</span> : null}
        <RowActions item={item} archive={archive} onDeleted={onDeleted} onError={onError}/>
      </footer>
    </article>
  )
}

function FascicoliTable({ items, selected, onToggle, onToggleAll, archive = false, onDeleted, onError, pagination, pageSize, onPageSizeChange, onPageChange }:{items:FascicoloRow[]; selected:Set<string>; onToggle:(id:string)=>void; onToggleAll:()=>void; archive?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; pagination?:FascicoliPagination; pageSize?:number; onPageSizeChange?:(value:number)=>void; onPageChange?:(value:number)=>void}) {
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  const total = pagination?.total ?? items.length
  const currentPage = pagination?.page ?? 1
  const totalPages = pagination?.pages ?? (items.length ? 1 : 0)
  return (
    <section className="iu-fas-table-card" aria-label={archive ? 'Archivio fascicoli' : 'Elenco fascicoli'}>
      <div className="iu-fas-table-head">
        <strong>{total} fascicoli</strong>
        {onPageSizeChange ? (
          <label>
            <span>Per pagina</span>
            <select value={pageSize || pagination?.pageSize || 25} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
        ) : null}
      </div>
      <div className="iu-fas-table-wrap">
        <table className="iu-fas-table">
          <thead>
            <tr>
              <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutti i fascicoli visibili"/></th>
              <th>Rif.</th>
              <th>Titolo / oggetto</th>
              <th>Tipo</th>
              <th>Cliente</th>
              <th>N. causa</th>
              <th>{archive ? 'Esito / archiviazione' : 'Prossima scad.'}</th>
              <th>Stato</th>
              <th>Documenti</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.ref}`}/></td>
                <td><strong>{item.ref}</strong><span>{item.internalRef}</span></td>
                <td className="iu-fas-title-cell"><a href={item.href}>{item.title}</a><span>{item.subtitle || item.court}</span></td>
                <td><Badge tone="neutral">{formatFascicoloType(item.type)}</Badge></td>
                <td>{item.client}</td>
                <td>{item.rg}</td>
                <td>{archive ? <span>{item.archive?.outcome || 'n.d.'}<small>{item.archive?.archivedAt || ''}</small></span> : item.nextDeadline || 'n.d.'}</td>
                <td><Badge tone={item.tone}>{formatFascicoloStatus(item.status)}</Badge></td>
                <td><span className="iu-fas-doc-count">{item.documents}</span></td>
                <td><RowActions item={item} archive={archive} onDeleted={onDeleted} onError={onError}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="iu-fas-mobile-list">
        {items.map((item) => <DossierMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} archive={archive} onDeleted={onDeleted} onError={onError} key={item.id}/>) }
      </div>
      {onPageChange && pagination ? (
        <div className="iu-fas-pagination" aria-label="Paginazione fascicoli">
          <button type="button" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1}>Precedente</button>
          <span>Pagina {currentPage} di {Math.max(1, totalPages)}</span>
          <button type="button" onClick={() => onPageChange(currentPage + 1)} disabled={totalPages === 0 || currentPage >= totalPages}>Successiva</button>
        </div>
      ) : null}
      {!items.length ? <p className="iu-empty">Nessun fascicolo corrisponde ai filtri impostati.</p> : null}
    </section>
  )
}

function ListFilters({ data, query, setQuery, type, setType, status, setStatus, advancedOpen, setAdvancedOpen, refresh }:{data:FascicoliPageData; query:string; setQuery:(value:string)=>void; type:FascicoloTipo; setType:(value:FascicoloTipo)=>void; status:FascicoloStato; setStatus:(value:FascicoloStato)=>void; advancedOpen:boolean; setAdvancedOpen:(value:boolean)=>void; refresh:()=>void}) {
  return (
    <section className="iu-fas-toolbar" aria-label="Filtri fascicoli">
      <label className="iu-fas-search">
        <Search size={17}/>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca per numero, titolo, cliente, n. causa..."/>
      </label>
      <label>
        <span>Tipo</span>
        <select value={type} onChange={(event) => setType(event.target.value as FascicoloTipo)}>
          {data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
        </select>
      </label>
      <label>
        <span>Stato</span>
        <select value={status} onChange={(event) => setStatus(event.target.value as FascicoloStato)}>
          {data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}
        </select>
      </label>
      <button className="iu-fas-filter-btn" type="button" onClick={() => setAdvancedOpen(!advancedOpen)} aria-expanded={advancedOpen}><Filter size={16}/> Filtri</button>
      <button className="iu-fas-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna fascicoli"><RefreshCw size={17}/></button>
    </section>
  )
}

function InsightPanel({ data, visible }:{data:FascicoliPageData; visible:FascicoloRow[]}) {
  const urgent = visible.filter((item) => item.alerts > 0 || item.unreadCommunications > 0).slice(0, 4)
  const withoutDeadline = visible.filter((item) => item.status !== 'archiviato' && !item.nextDeadlineIso && item.nextDeadline === 'n.d.').length
  return (
    <aside className="iu-fas-insights">
      <Panel title="Cabina fascicoli" subtitle="Controlli che conviene avere subito" icon={<Gauge size={17}/>}>
        <div className="iu-fas-briefing">
          <article>
            <span>Da governare ora</span>
            <strong>{data.summary.deadlines30} scadenze nei prossimi 30 giorni</strong>
            <small>{data.summary.deadlines7} entro 7 giorni.</small>
          </article>
          <article>
            <span>Qualità archivio</span>
            <strong>{data.summary.toArchive} fascicoli da chiudere o archiviare</strong>
            <small>{withoutDeadline} pratiche attive non hanno una prossima scadenza visibile.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Alert operativi" icon={<Bell size={17}/>} count={urgent.length}>
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
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17}/>}>
        <div className="iu-fas-quick-actions">
          <a href="/fascicoli/nuovo"><FolderPlus size={15}/> Nuovo fascicolo</a>
          <a href="/scadenziario/nuova"><CalendarDays size={15}/> Nuova scadenza</a>
          <a href="/redazione-atti"><FileCheck2 size={15}/> Redazione atti</a>
          <a href="/fascicoli/archivio"><Archive size={15}/> Archivio</a>
        </div>
      </Panel>
    </aside>
  )
}

function FascicoliListPage() {
  const [data, setData] = useState<FascicoliPageData>(emptyFascicoliPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [type, setType] = useState<FascicoloTipo>('tutti')
  const [status, setStatus] = useState<FascicoloStato>('tutti')
  const [sort, setSort] = useState<SortKey>('recenti')
  const [court, setCourt] = useState('')
  const [debouncedCourt, setDebouncedCourt] = useState('')
  const [alertsOnly, setAlertsOnly] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const refresh = () => {
    setLoading(true)
    getFascicoliPage({ page, pageSize, q: debouncedQuery, type, status, court: debouncedCourt, sort, alertsOnly }).then(setData).finally(() => setLoading(false))
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1)
      setDebouncedQuery(query.trim())
      setDebouncedCourt(court.trim())
    }, 350)
    return () => window.clearTimeout(timer)
  }, [court, query])

  useEffect(() => {
    let active = true
    setLoading(true)
    getFascicoliPage({ page, pageSize, q: debouncedQuery, type, status, court: debouncedCourt, sort, alertsOnly })
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [alertsOnly, debouncedCourt, debouncedQuery, page, pageSize, sort, status, type])

  const visible = data.items
  const updateType = (value: FascicoloTipo) => { setPage(1); setType(value) }
  const updateStatus = (value: FascicoloStato) => { setPage(1); setStatus(value) }
  const updateSort = (value: SortKey) => { setPage(1); setSort(value) }
  const updateAlertsOnly = (value: boolean) => { setPage(1); setAlertsOnly(value) }
  const updatePageSize = (value: number) => { setPage(1); setPageSize(value) }
  const updatePage = (value: number) => setPage(Math.max(1, Math.min(Math.max(1, data.pagination.pages || 1), value)))

  const selectedVisible = visible.filter((item) => selected.has(item.id)).length
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const toggleAll = () => setSelected((current) => {
    const allSelected = visible.length > 0 && visible.every((item) => current.has(item.id))
    if (allSelected) return new Set([...current].filter((id) => !visible.some((item) => item.id === id)))
    return new Set([...current, ...visible.map((item) => item.id)])
  })
  const handleFascicoloDeleted = (id: string, message?: string) => {
    setSelected((current) => { const next = new Set(current); next.delete(id); return next })
    setToast({ tone: 'success', message: message || 'Fascicolo eliminato.' })
    refresh()
  }
  const handleListError = (message: string) => setToast({ tone: 'danger', message })

  return (
    <main className="iu-content iu-fascicoli-page">
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
        <StatCard icon={<FolderOpen size={19}/>} label="Attivi" value={data.summary.active} note="non archiviati" tone="primary"/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="In corso" value={data.summary.inProgress} note="da lavorare" tone="success"/>
        <StatCard icon={<Archive size={19}/>} label="Da archiviare" value={data.summary.toArchive} note="definiti o pronti" tone="warning"/>
        <StatCard icon={<CalendarDays size={19}/>} label="Scadenze 7g" value={data.summary.deadlines7} note="priorità immediata" tone="danger"/>
        <StatCard icon={<FileText size={19}/>} label="Documenti" value={data.summary.documents} note="nel perimetro visibile" tone="purple"/>
        <StatCard icon={<Bell size={19}/>} label="Comunicazioni" value={data.summary.unreadCommunications} note="non lette o da associare" tone="info"/>
      </section>

      {data.deadlines.length ? (
        <section className="iu-fas-deadline-alert">
          <AlertIcon />
          <div>
            <strong>Scadenze entro 7 giorni</strong>
            <div>{data.deadlines.slice(0, 4).map((item) => <a href={item.href} key={item.id}>{item.matterRef} - {item.title} <span>{item.date}</span></a>)}</div>
          </div>
        </section>
      ) : null}

      <ListFilters data={data} query={query} setQuery={setQuery} type={type} setType={updateType} status={status} setStatus={updateStatus} advancedOpen={advancedOpen} setAdvancedOpen={setAdvancedOpen} refresh={refresh}/>

      {advancedOpen ? (
        <section className="iu-fas-advanced" aria-label="Filtri avanzati fascicoli">
          <label><span>Ufficio giudiziario</span><input value={court} onChange={(event) => setCourt(event.target.value)} placeholder="Tribunale, TAR, GDP..."/></label>
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => updateSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label className="iu-fas-check"><input type="checkbox" checked={alertsOnly} onChange={(event) => updateAlertsOnly(event.target.checked)}/><span>Solo fascicoli con alert o comunicazioni</span></label>
        </section>
      ) : null}

      <section className="iu-fas-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione fascicoli...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> Vista operativa aggiornata con salvataggi tracciati e controlli di studio già governati.</small>
        {selectedVisible ? <small className="iu-fas-selected">{selectedVisible} selezionati</small> : null}
      </section>

      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}

      <section className="iu-fas-layout">
        <div className="iu-fas-main-list">
          {selectedVisible ? (
            <div className="iu-fas-bulkbar">
              <strong>{selectedVisible} fascicoli selezionati</strong>
              <a href="/fascicoli/esporta"><Download size={14}/> Esporta selezione</a>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll} onDeleted={handleFascicoloDeleted} onError={handleListError} pagination={data.pagination} pageSize={pageSize} onPageSizeChange={updatePageSize} onPageChange={updatePage}/>
        </div>
        <InsightPanel data={data} visible={visible}/>
      </section>

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
            <a href="/app-v2/ptt">PTT Tributario</a>
          </div>
        </Panel>
      </section>

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

function Field({ label, name, defaultValue = '', type = 'text', required = false, readOnly = false, placeholder = '', children }:{label:string; name:string; defaultValue?:string|number|boolean; type?:string; required?:boolean; readOnly?:boolean; placeholder?:string; children?:ReactNode}) {
  return (
    <label className="iu-fas-field">
      <span>{label}{required ? <b>*</b> : null}</span>
      {children || <input type={type} name={name} defaultValue={String(defaultValue ?? '')} required={required} readOnly={readOnly} placeholder={placeholder}/>}
    </label>
  )
}

function SelectField({ label, name, options, defaultValue = '', required = false }:{label:string; name:string; options:SelectOption[]; defaultValue?:string; required?:boolean}) {
  return <Field label={label} name={name} required={required}><select name={name} defaultValue={defaultValue} required={required}>{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></Field>
}

function TextAreaField({ label, name, defaultValue = '', rows = 3, placeholder = '' }:{label:string; name:string; defaultValue?:string; rows?:number; placeholder?:string}) {
  return <label className="iu-fas-field iu-fas-field--wide"><span>{label}</span><textarea name={name} rows={rows} defaultValue={defaultValue} placeholder={placeholder}/></label>
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

function PraticheCollegateField({ data }:{data:FascicoloFormData}) {
  const initialCode = getValue(data, 'codiceOggettoPst')
  const [selectedCode, setSelectedCode] = useState(initialCode)
  useEffect(() => setSelectedCode(initialCode), [initialCode])
  const selected = findPraticaCollegata(selectedCode)
  const currentProcedure = selected?.label || getValue(data, 'procedureType')
  const currentArea = selected?.area || getValue(data, 'practiceArea')
  return (
    <div className="iu-fas-field iu-fas-field--wide iu-fas-catalog-field">
      <label>
        <span>{NUOVO_FASCICOLO_LABELS.fields.praticheCollegate}</span>
        <select
          name="codice_oggetto_pst"
          value={selectedCode}
          onChange={(event) => setSelectedCode(event.currentTarget.value)}
          aria-describedby="pratiche-collegate-help"
        >
          <option value="">Seleziona dal catalogo ufficiale</option>
          {PRATICHE_COLLEGATE.map((area) => (
            <optgroup label={area.label} key={area.area}>
              {area.items.flatMap((item) => {
                if (item.children?.length) {
                  return [
                    <option value={item.codice} disabled key={item.codice}>{item.codice} - {item.label}</option>,
                    ...item.children.map((child) => (
                      <option value={child.codice} key={child.codice}>{child.codice} - {child.label}</option>
                    )),
                  ]
                }
                return <option value={item.codice} key={item.codice}>{item.codice} - {item.label}</option>
              })}
            </optgroup>
          ))}
        </select>
      </label>
      <input type="hidden" name="tipo_procedimento" value={currentProcedure}/>
      <input type="hidden" name="area_pratica" value={currentArea}/>
      <input type="hidden" name="fonte_codice_oggetto" value={selectedCode ? PRATICHE_COLLEGATE_CATALOG.fonte.tipo : getValue(data, 'fonteCodiceOggetto')}/>
      <input type="hidden" name="file_fonte_codice_oggetto" value={selectedCode ? PRATICHE_COLLEGATE_CATALOG.fonte.fileFontePrevalente : getValue(data, 'fileFonteCodiceOggetto')}/>
      <small id="pratiche-collegate-help" className="iu-fas-field-help">
        Il codice scelto viene conservato nel fascicolo e sarà usato nei passaggi di deposito quando il flusso lo richiede.
      </small>
    </div>
  )
}

function FascicoloGuardrailsPanel({ guardrails }: { guardrails?: FascicoloFormData['guardrails'] }) {
  if (!guardrails?.available) return null
  const modeLabel = guardrails.mode === 'opening' ? 'apertura fascicolo' : 'deposito'
  return (
    <Panel title={guardrails.title || 'Guardrail deposito telematico'} subtitle={`${guardrails.channelLabel} - ${modeLabel}`} icon={<ShieldCheck size={17}/>}>
      <div className="iu-fas-checklist iu-fas-guardrails">
        <span><Landmark size={16}/> Canale suggerito: <strong>{guardrails.channelLabel}</strong></span>
        {guardrails.requiredOpeningFields.length ? <span><ClipboardCheck size={16}/> Campi minimi apertura: {guardrails.requiredOpeningFields.join(', ')}</span> : null}
        {guardrails.blocking.map((issue) => <span key={issue.code || issue.message} className="iu-fas-issue iu-fas-issue--block"><ShieldCheck size={16}/> {issue.message}</span>)}
        {guardrails.warnings.map((issue) => <span key={issue.code || issue.message} className="iu-fas-issue iu-fas-issue--warning"><Bell size={16}/> {issue.message}</span>)}
        {guardrails.nextStep?.href ? <a className="iu-fas-inline-link" href={guardrails.nextStep.href}>{guardrails.nextStep.label || 'Apri pre-deposito'}</a> : null}
      </div>
    </Panel>
  )
}

function FascicoloFormPage({ mode, id }:{mode:'new'|'edit'; id?:string}) {
  const [data, setData] = useState<FascicoloFormData>(emptyFascicoloForm)
  const [loading, setLoading] = useState(true)
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
      <section className="iu-fas-form-layout">
        <JsonPostForm className="iu-fas-form" action={data.action || (mode === 'edit' && id ? `/fascicoli/${encodeURIComponent(id)}/modifica` : '/fascicoli/nuovo')} redirectTo={data.detailHref || data.backHref}>
          {mode === 'new' ? <><input type="hidden" name="source_preventivo" value={data.query.source_preventivo || ''}/><input type="hidden" name="source_conferimento" value={data.query.source_conferimento || ''}/><input type="hidden" name="from_page" value={data.query.from_page || ''}/></> : null}
          <Panel title={labels.sections.datiGenerali} subtitle="Pratica, oggetto, stato e date principali" icon={<FolderOpen size={17}/>}>
            <div className="iu-fas-form-grid">
              <Field label={labels.fields.pratica} name="titolo" defaultValue={getValue(data, 'title')} required placeholder="es. Rossi c/ Bianchi - Inadempimento contrattuale"/>
              <Field label={labels.fields.rifCartaceo} name="riferimento_cartaceo" defaultValue={getValue(data, 'riferimentoCartaceo')}/>
              <SelectField label="Tipo fascicolo" name="tipo" options={data.types} defaultValue={getValue(data, 'typeRaw') || getValue(data, 'type').toUpperCase()} required/>
              <StatoPraticaField data={data}/>
              <Field label={labels.fields.dataApertura} name="data_apertura" type="date" defaultValue={getValue(data, 'dataAperturaIso') || new Date().toISOString().slice(0, 10)}/>
              <Field label={labels.fields.dataArchiviazione} name="data_chiusura" type="date" defaultValue={getValue(data, 'dataChiusuraIso')}/>
              <TextAreaField label={labels.fields.oggettoPratica} name="oggetto" defaultValue={getValue(data, 'object') || getValue(data, 'subtitle')} rows={2}/>
              <label className="iu-fas-check-field"><input type="checkbox" name="personalizzabile" value="1" defaultChecked={getBoolValue(data, 'personalizzabile')}/><span>{labels.fields.personalizzabile}</span></label>
            </div>
          </Panel>
          <Panel title="Parti" subtitle="Cliente, controparte e attore principale" icon={<UsersRound size={17}/>}>
            <div className="iu-fas-form-grid">
              <SelectField label="Cliente" name="id_cliente" options={[{ value: '', label: 'Seleziona cliente' }, ...data.clients.map((client) => ({ value: client.id, label: client.label }))]} defaultValue={getValue(data, 'clientId') || data.query.id_cliente || ''}/>
              <Field label="Controparte" name="controparte" defaultValue={getValue(data, 'counterparty')} placeholder="Cerca per nome, C.F. o digita"/>
              <Field label={labels.fields.attorePrincipale} name="attore_principale" defaultValue={getValue(data, 'attorePrincipale')}/>
              <a className="iu-fas-inline-link" href="/soggetti/nuovo" target="_blank" rel="noreferrer"><Plus size={14}/> Nuovo soggetto</a>
            </div>
          </Panel>
          <Panel title={labels.sections.identificazioneGiudiziale} subtitle="Autorità, numero di ruolo e catalogo ufficiale per il deposito" icon={<Landmark size={17}/>}>
            <div className="iu-fas-form-grid">
              <Field label={labels.fields.autoritaGiudiziaria} name="tribunale" defaultValue={getValue(data, 'court')}/>
              <Field label={labels.fields.numeroRuolo} name="numero_rg" defaultValue={getValue(data, 'numeroRg')}/>
              <Field label="Anno iscrizione" name="anno_rg" type="number" defaultValue={getValue(data, 'annoRg') || new Date().getFullYear()}/>
              <Field label="Sezione" name="sezione" defaultValue={getValue(data, 'section')}/>
              <Field label={labels.fields.istruttorePmGip} name="istruttore_pm_gip" defaultValue={getValue(data, 'istruttorePmGip') || getValue(data, 'judge')}/>
              <Field label={labels.fields.cancelliere} name="cancelliere" defaultValue={getValue(data, 'cancelliere')}/>
              <Field label={labels.fields.ctu} name="ctu" defaultValue={getValue(data, 'ctu')}/>
              <Field label={labels.fields.ctp} name="ctp" defaultValue={getValue(data, 'ctp')}/>
              <PraticheCollegateField data={data}/>
              <Field label="Valore causa (EUR)" name="valore_causa" type="number" defaultValue={getValue(data, 'valueRaw') || getValue(data, 'value')} placeholder="0.00"/>
              <Field label="Compenso pattuito (EUR)" name="compenso_pattuito" type="number" defaultValue={getValue(data, 'agreedFeeRaw') || getValue(data, 'agreedFee')} readOnly={Boolean(getValue(data, 'agreedFee'))}/>
              <Field label="Valore preventivato (EUR)" name="valore_preventivato" type="number" defaultValue={getValue(data, 'quotedValueRaw') || getValue(data, 'quotedValue')} readOnly={Boolean(getValue(data, 'quotedValue'))}/>
              <input type="hidden" name="id_pratica" value={getValue(data, 'practiceId')}/>
              <input type="hidden" name="procedura_operativa_codice" value={getValue(data, 'proceduraOperativaCodice')}/>
              <Field label="Data prima udienza / comparizione" name="data_prima_udienza" type="date" defaultValue={getValue(data, 'firstHearingIso') || getValue(data, 'firstHearing')}/>
              <Field label="Data notificazione citazione" name="data_notifica_citazione" type="date" defaultValue={getValue(data, 'citationNotificationIso') || getValue(data, 'citationNotification')}/>
            </div>
          </Panel>
          <Panel title={labels.sections.annotazioni} subtitle="Referente, dominus e note operative" icon={<BriefcaseBusiness size={17}/>}>
            <div className="iu-fas-form-grid"><Field label="Avvocato referente" name="avvocato_referente" defaultValue={getValue(data, 'leadLawyer')}/><Field label="Avvocato dominus" name="avvocato_dominus" defaultValue={getValue(data, 'dominus')}/><TextAreaField label={labels.fields.annotazioni} name="note" defaultValue={getValue(data, 'notes')} rows={4}/></div>
          </Panel>
          <div className="iu-fas-form-actions"><button className="iu-fas-submit" type="submit"><CheckCircle2 size={16}/> {mode === 'edit' ? 'Salva modifiche' : 'Crea fascicolo'}</button><a href={data.detailHref || data.backHref}>Annulla</a></div>
        </JsonPostForm>
        <aside className="iu-fas-form-side">
          <FascicoloGuardrailsPanel guardrails={data.guardrails} />
          {data.workflow ? <Panel title="Apertura pratica guidata" icon={<Sparkles size={17}/>}><div className="iu-fas-workflow-box"><div>{data.workflow.badges.map((badge) => <Badge tone="primary" key={badge}>{badge}</Badge>)}</div><p>{data.workflow.summary}</p>{data.workflow.values.map((item) => <span key={item.label}><strong>{item.label}</strong>{item.value}</span>)}<ul>{data.workflow.checklist.map((item) => <li key={item}>{item}</li>)}</ul></div></Panel> : null}
          <Panel title="Guida rapida" icon={<BadgeCheck size={17}/>}><div className="iu-fas-help"><p><strong>RG</strong>: numero assegnato dal tribunale all'iscrizione a ruolo.</p><p><strong>Sezione</strong>: sezione competente, utile per filtri e notifiche.</p><p><strong>Valore causa</strong>: alimenta compensi, quadro economico e controllo incassi.</p></div></Panel>
          <Panel title="Prossimi passi" icon={<ListChecks size={17}/>}><div className="iu-fas-help"><p>Dopo il salvataggio potrai aggiungere documenti, scadenze processuali, attività, depositi telematici e note.</p></div></Panel>
        </aside>
      </section>
      <FloatingLex context="fascicolo-form" title="Lex AI fascicolo" body="Posso aiutarti a completare oggetto, tipo procedimento, checklist iniziale, scadenze e dati mancanti prima della creazione o modifica." primaryHref="#lex" primaryLabel="Apri Lex fascicolo" secondaryHref="/fascicoli" secondaryLabel="Torna ai fascicoli" />
    </main>
  )
}

function KvGrid({ items }:{items:KeyValue[]}) {
  return <div className="iu-fas-kv-grid">{items.map((item) => <div key={`${item.label}-${item.value}`}><span>{item.label}</span>{item.href ? <a href={item.href} className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</a> : <strong className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</strong>}</div>)}</div>
}

function DetailSection({ id, title, icon, count, defaultOpen = false, onOpen, children }:{id:string; title:string; icon:ReactNode; count?:number; defaultOpen?:boolean; onOpen?:()=>void; children:ReactNode}) {
  return (
    <details id={id} className="iu-fas-detail-section" {...(defaultOpen ? { open: true } : {})} onToggle={(event) => { if (event.currentTarget.open) onOpen?.() }}>
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

type PreviewDocument = { name: string; url: string; downloadUrl: string }
type LazySectionStatus = 'idle' | 'loading' | 'loaded' | 'error'

const emptyLazySections: Record<FascicoloDetailSection, LazySectionStatus> = {
  documenti: 'idle',
  attivita: 'idle',
  scadenze: 'idle',
  depositi: 'idle',
  regia: 'idle',
}

function PdfPreviewModal({ preview, onClose }:{preview:PreviewDocument | null; onClose:()=>void}) {
  if (!preview) return null
  return (
    <div className="iu-fas-preview-modal" role="dialog" aria-modal="true" aria-label={`Anteprima ${preview.name}`}>
      <div className="iu-fas-preview-modal__box">
        <header>
          <div><Eye size={16}/><strong>{preview.name}</strong></div>
          <nav>
            <a href={preview.downloadUrl}><Download size={15}/> Scarica</a>
            <button type="button" onClick={onClose} aria-label="Chiudi anteprima">Chiudi</button>
          </nav>
        </header>
        <iframe src={preview.url} title={`Anteprima documento ${preview.name}`}/>
      </div>
    </div>
  )
}

function recordText(row: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = row?.[key]
  return String(value ?? fallback).trim()
}

function recordBool(row: Record<string, unknown> | undefined, key: string) {
  const value = row?.[key]
  return value === true || value === 'true' || value === '1' || value === 1
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
  const evidenceHref = recordText(evidence, 'href')
  const blockReasons = Array.isArray(deposit.blockReasons) ? deposit.blockReasons.map((item) => String(item || '').trim()).filter(Boolean) : []
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
        <div className="iu-fas-regia__meta">
          <span><strong>Area</strong>{h.area || 'n.d.'}</span>
          <span><strong>Canale</strong>{h.channel || 'n.d.'}</span>
          <span><strong>Registro</strong>{h.registry || 'n.d.'}</span>
          <span><strong>Percorso</strong>{h.workflow || 'n.d.'}</span>
        </div>
        <div className="iu-fas-regia__grid">
          <article>
            <h4>Economia e incarico</h4>
            <ul className="iu-fas-regia__facts">
              <li><span>Preventivo accettato</span><strong>{recordBool(economics, 'preventivoAccepted') ? 'Si' : 'No'}</strong></li>
              <li><span>Conferimento firmato</span><strong>{recordBool(economics, 'conferimentoSigned') ? 'Si' : 'No'}</strong></li>
              <li><span>Avviso / parcella</span><strong>{recordBool(economics, 'proformaIssued') ? 'Emesso' : 'Non emesso'}</strong></li>
              <li><span>Pagamento</span><strong>{recordBool(economics, 'paymentRegistered') ? 'Registrato' : 'Da registrare'}</strong></li>
              <li><span>Compenso pattuito</span><strong>{recordText(economics, 'agreedFee', 'EUR 0,00')}</strong></li>
              <li><span>Spese vive / anticipazioni</span><strong>{recordText(economics, 'expenses', 'EUR 0,00')}</strong></li>
            </ul>
            {Array.isArray(economics.overrides) && economics.overrides.length ? <p className="iu-fas-regia__warn">Variazione economica presente e registrata.</p> : null}
          </article>
          <article>
            <h4>Validazione</h4>
            <Badge tone={statusTone}>{regia.validation.status || 'Da eseguire'}</Badge>
            <p>{regia.validation.blockers[0] ? recordText(regia.validation.blockers[0], 'message') : regia.validation.warnings[0] ? recordText(regia.validation.warnings[0], 'message') : 'Nessun blocco critico rilevato.'}</p>
            <div className="iu-fas-regia__actions">
              {predepositAction ? <PostAction action={predepositAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={15}/> Verifica di nuovo</PostAction> : null}
              {prepareAction ? <PostAction action={prepareAction} tone="secondary" onDone={onDone} onError={onError}><ClipboardCheck size={15}/> Prepara deposito</PostAction> : null}
            </div>
          </article>
        </div>
        <div className="iu-fas-regia__columns">
          <section>
            <h4>Checklist dinamica</h4>
            <div className="iu-fas-regia-list">
              {regia.checklist.map((item) => <article key={recordText(item, 'id') || recordText(item, 'key')}><Badge tone={recordText(item, 'status') === 'BLOCCATO' ? 'danger' : recordText(item, 'status') === 'COMPLETATO' ? 'success' : 'warning'}>{recordText(item, 'status', 'Da completare')}</Badge><strong>{recordText(item, 'label')}</strong><span>{recordText(item, 'message')}</span><small>{recordText(item, 'suggestedAction')}</small></article>)}
              {!regia.checklist.length ? <p className="iu-empty">Checklist non ancora generata.</p> : null}
            </div>
          </section>
          <section>
            <h4>Slot documentali</h4>
            <div className="iu-fas-regia-list">
              {regia.documentSlots.map((slot) => <article key={recordText(slot, 'slotKey')}><Badge tone={recordText(slot, 'status') === 'VALIDO' ? 'success' : recordText(slot, 'status') === 'WARNING' ? 'warning' : recordText(slot, 'status') === 'NON_APPLICABILE' ? 'neutral' : 'danger'}>{recordText(slot, 'status')}</Badge><strong>{recordText(slot, 'label')}</strong><span>{recordText(slot, 'documentId') ? `Documento ${recordText(slot, 'documentId')}` : recordText(slot, 'message', 'Documento non collegato')}</span><small>{recordText(slot, 'suggestedAction')}</small></article>)}
              {!regia.documentSlots.length ? <p className="iu-empty">Nessuno slot documentale generato.</p> : null}
            </div>
          </section>
        </div>
        <div className="iu-fas-regia__deposit">
          <div>
            <Badge tone={recordText(deposit, 'status') === 'ACQUISITO' ? 'success' : blocked ? 'danger' : ready ? 'success' : 'warning'}>{recordText(deposit, 'status', 'NON_INVIATO')}</Badge>
            <strong>{recordText(deposit, 'label', 'Deposito')}</strong>
            <p>{recordText(deposit, 'message') || blockReasons[0] || 'Stato deposito non avviato.'}</p>
            {blockReasons.length ? <ul>{blockReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}
          </div>
          <div className="iu-fas-regia__actions">
            {ready && sendAction ? <PostAction action={sendAction} tone="primary" onDone={onDone} onError={onError} confirm="Inviare il deposito con il canale configurato?" confirmTitle="Invia deposito"><Send size={15}/> Invia deposito</PostAction> : <button type="button" disabled><Send size={15}/> Deposito non disponibile</button>}
            {evidenceHref ? <a className="iu-fas-side-link" href={evidenceHref}><FileArchive size={15}/> Evidence pack</a> : null}
          </div>
        </div>
        <section>
          <h4>Timeline ricevute</h4>
          <div className="iu-fas-timeline">
            {regia.timeline.map((event) => <article key={recordText(event, 'id')}><time>{recordText(event, 'createdAt')}</time><strong>{recordText(event, 'status')}</strong><p>{recordText(event, 'message')}</p></article>)}
            {!regia.timeline.length ? <p className="iu-empty">Nessuna ricevuta o esito importato.</p> : null}
          </div>
        </section>
      </div>
    </DetailSection>
  )
}

function fLabel(value: string) {
  return value || 'Fascicolo'
}

function UploadDocumentForm({ action, documentTypes, onDone, onError }:{action:string; documentTypes:SelectOption[]; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [busy, setBusy] = useState(false)
  if (!action) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    const file = formData.get('file')
    if (!(file instanceof File) || !file.name) {
      onError('Seleziona un file da caricare.')
      return
    }
    setBusy(true)
    try {
      const response = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        body: formData,
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await response.json().catch(() => ({} as ActionPayload))
      if (!response.ok || payload.ok === false) throw new Error(String(payload.messaggio || payload.errore || 'Caricamento non riuscito.'))
      form.reset()
      onDone(String(payload.messaggio || payload.message || 'Documento caricato.'))
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Caricamento non riuscito.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="iu-fas-upload" onSubmit={submit} encType="multipart/form-data">
      <input type="file" name="file"/>
      <select name="tipo_doc" defaultValue="ALTRO">{documentTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select>
      <input type="date" name="data_documento"/>
      <input name="tags" placeholder="tag separati da virgola"/>
      <input name="note" placeholder="note documento"/>
      <label><input type="checkbox" name="firmato" value="1"/> Firmato</label>
      <button type="submit" disabled={busy}><UploadCloud size={15}/> {busy ? 'Carico...' : 'Carica'}</button>
    </form>
  )
}

function PortalImportForm({ action, onDone, onError }:{action:string; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [busy, setBusy] = useState(false)
  if (!action) return null
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const formData = new FormData(form)
    setBusy(true)
    try {
      const response = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        body: formData,
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      })
      const payload = await response.json().catch(() => ({} as ActionPayload))
      if (!response.ok || payload.ok === false) throw new Error(String(payload.messaggio || payload.errore || 'Importazione non riuscita.'))
      form.reset()
      onDone(String(payload.messaggio || payload.message || 'Importazione completata.'))
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Importazione non riuscita.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <form className="iu-fas-upload iu-fas-upload--portal" onSubmit={submit} encType="multipart/form-data">
      <input type="file" name="files" multiple/>
      <input name="note_importazione" placeholder="note importazione portale"/>
      <label><input type="checkbox" name="mantieni_albero_originale" value="1"/> Mantieni albero originale</label>
      <label><input type="checkbox" name="scarica_originale_portale" value="1"/> Originale portale</label>
      <button type="submit" disabled={busy}><Download size={15}/> {busy ? 'Importo...' : 'Importa portale'}</button>
    </form>
  )
}

function DocumentRow({ doc, onPreview, onDone, onError }:{doc:FascicoloDocument; onPreview:(preview:PreviewDocument)=>void; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  return (
    <article className="iu-fas-doc-row">
      <div><FileText size={18}/></div>
      <div><strong>{doc.name}</strong><span>{doc.type} · {doc.size || 'dimensione n.d.'} · {doc.documentDate || doc.uploadedAt || 'data n.d.'}</span>{doc.notes ? <p>{doc.notes}</p> : null}{doc.tags.length ? <em>{doc.tags.join(', ')}</em> : null}</div>
      <div className="iu-fas-doc-badges"><Badge tone={doc.statusTone}>{doc.statusLabel || (doc.signed ? 'Firmato' : 'Da firmare')}</Badge>{doc.source ? <Badge tone="neutral">{doc.source}</Badge> : null}{doc.portalClass ? <Badge tone="info">{doc.portalClass}</Badge> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {doc.actions.preview ? <button type="button" title="Anteprima interna" onClick={() => onPreview({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}><Eye size={15}/></button> : null}
        {doc.actions.download ? <a href={doc.actions.download} title="Scarica"><Download size={15}/></a> : null}
        {doc.actions.edit ? <a href={doc.actions.edit} title="Editor professionale"><PencilLine size={15}/></a> : null}
        {doc.actions.sign ? <a href={doc.actions.sign} title="Firma digitale"><ShieldCheck size={15}/></a> : null}
        {doc.actions.attest ? <PostAction action={doc.actions.attest} tone="secondary" onDone={onDone} onError={onError}><BadgeCheck size={14}/></PostAction> : null}
        {doc.actions.pdfa ? <PostAction action={doc.actions.pdfa} tone="secondary" confirm="Convertire il documento in PDF/A-2B?" confirmTitle="Conversione PDF/A" onDone={onDone} onError={onError}><FileCheck2 size={14}/></PostAction> : null}
        {doc.actions.delete ? <PostAction action={doc.actions.delete} tone="danger" confirm="Eliminare il documento dal fascicolo?" confirmTitle="Elimina documento" onDone={onDone} onError={onError}><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

type LocalSignerToken = { slot_id?: number | string; label?: string; manufacturer?: string; model?: string; serial?: string }
type LocalSignerStatus = {
  ok?: boolean
  token?: LocalSignerToken[]
  token_probe_fresh?: LocalSignerToken[]
  versione?: string
  version?: string
  piattaforma?: string
  messaggio?: string
  error?: string
  errore_token?: string
  errore_libreria?: string
  riavvio_signer_consigliato?: boolean
  nota_riavvio_signer?: string
}
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

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

const LOCAL_SIGNER_RESTART_URI = 'iusentra-local-signer://restart'

function isDesktopLocalSignerHost(): boolean {
  if (typeof navigator === 'undefined') return true
  const userAgent = String(navigator.userAgent || '').toLowerCase()
  const platformName = String(navigator.platform || '').toLowerCase()
  const isMobileOrTablet = /android|iphone|ipad|ipod|mobile|tablet|silk|kindle/.test(userAgent)
  const isIpadDesktopMode = platformName.includes('mac') && Number(navigator.maxTouchPoints || 0) > 1
  return !isMobileOrTablet && !isIpadDesktopMode
}

function requestLocalSignerStart(): boolean {
  if (!isDesktopLocalSignerHost()) return false
  const link = document.createElement('a')
  link.href = LOCAL_SIGNER_RESTART_URI
  link.rel = 'noreferrer'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  window.setTimeout(() => link.remove(), 1500)
  return true
}

function localSignerTokenLabel(token?: LocalSignerToken): string {
  if (!token) return ''
  return [token.label, token.manufacturer, token.model].filter(Boolean).join(' - ') || 'Token USB'
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
  }
}

function localSignerBaseUrl(): string {
  const configured = typeof window !== 'undefined' ? window.__IUSENTRA_LOCAL_SIGNER_URL__ : ''
  return String(configured || 'http://127.0.0.1:27272').replace(/\/+$/, '')
}

function localSignerEndpoint(path: string): string {
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${localSignerBaseUrl()}${suffix}`
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
  const displayToken = primaryToken || freshToken
  const signerRestartRequired = Boolean(freshToken && !primaryToken)
  const localSignerCanSign = Boolean(primaryToken && !signerRestartRequired)
  const localSignerReachable = Boolean(localSigner && localSigner.ok !== false && (localSigner.versione || localSigner.version || localSigner.piattaforma || localSigner.token || localSigner.token_probe_fresh))
  const restartSuggested = Boolean(signerRestartRequired || (localSigner?.riavvio_signer_consigliato && !primaryToken))
  const localSignerVersion = localSigner?.versione || localSigner?.version || ''
  const localSignerStatusTitle = displayToken
    ? (freshToken && !primaryToken ? 'Token rilevato, riavvio consigliato' : 'Local Signer rilevato')
    : localSignerReachable
      ? 'Local Signer attivo senza token PKCS#11'
      : checkingSigner
        ? 'Verifica Local Signer...'
        : 'Local Signer non rilevato'
  const localSignerStatusMessage = displayToken
    ? (restartSuggested
        ? localSigner?.nota_riavvio_signer || 'Il token e stato rilevato da un controllo fresco. Riavvia il Local Signer se la firma non parte.'
        : `${localSignerTokenLabel(displayToken)} - slot ${displayToken.slot_id}`)
    : localSignerReachable
      ? localSigner?.errore_token || localSigner?.errore_libreria || localSigner?.messaggio || 'Servizio locale attivo, ma nessun token PKCS#11 disponibile.'
      : localSigner?.messaggio || localSigner?.error || 'Avvia Local Signer sul PC e riprova.'
  const signatureCount = info?.firme?.length || 0
  const alreadySigned = Boolean(doc?.signed || signatureCount > 0 || doc?.name.toLowerCase().match(/\.(p7m|sig|pkcs7)$/))
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
    setMessage("Sto chiedendo a Windows di riavviare Local Signer. Se il browser chiede conferma, consenti l'apertura dell'app locale.")
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

  const checkLocalSigner = async (tryStart = false) => {
    setCheckingSigner(true)
    setError('')
    if (tryStart) requestLocalSignerStart()
    const attempts = tryStart ? 10 : 1
    try {
      for (let attempt = 0; attempt < attempts; attempt += 1) {
        if (attempt > 0) await sleep(900)
        const controller = new AbortController()
        const timeout = window.setTimeout(() => controller.abort(), 3500)
        try {
          const response = await fetch(localSignerEndpoint('/ping'), {
            cache: 'no-store',
            signal: controller.signal,
          })
          const payload = await response.json().catch(() => ({}))
          setLocalSigner(payload as LocalSignerStatus)
          return
        } catch {
          if (attempt === attempts - 1) {
            setLocalSigner({ ok: false, messaggio: 'Local Signer non rilevato su questo PC.' })
          }
        } finally {
          window.clearTimeout(timeout)
        }
      }
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
    checkLocalSigner()
  }, [infoUrl])

  const firmaConLocalSigner = async () => {
    if (!doc) return
    if (signerRestartRequired) {
      setError('Prima riavvia e riverifica Local Signer: il PIN verra richiesto solo quando il token sara pronto per la firma.')
      return
    }
    if (!primaryToken?.slot_id && primaryToken?.slot_id !== 0) {
      setError('Local Signer non ha restituito un token utilizzabile.')
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
      const signResponse = await fetch(localSignerEndpoint('/firma'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          documento: arrayBufferToBase64(sourceBuffer),
          pin,
          slot_id: primaryToken.slot_id,
          visible_signature_mode: visibleSignatureMode,
          visible_signature_place: visibleSignaturePlace,
          visible_signature_datetime_mode: visibleSignatureDatetimeMode,
        }),
      })
      const signedPayload = await signResponse.json()
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
    return (
      <main className="iu-content iu-fascicoli-page">
        <EmptyState icon={<ShieldCheck size={34}/>} title="Fascicolo non disponibile" action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>
          Il fascicolo non e' disponibile o non hai i permessi per aprire la firma del documento.
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
            { label: 'Hash', value: doc?.hash || 'n.d.', mono: true },
            { label: 'Fonte', value: doc?.source || 'Studio' },
          ]}/>
        </Panel>

        <Panel title="Firma con Local Signer" subtitle="Controllo e firma sul PC dell'avvocato" icon={<ShieldCheck size={17}/>} action={<button className="iu-fas-mini-action" type="button" onClick={() => checkLocalSigner(false)} disabled={checkingSigner}><RefreshCw size={14}/> Riverifica</button>}>
          <div className="iu-fas-signature-box">
            <div className={`iu-fas-signer-status ${localSignerCanSign ? 'is-ok' : 'is-warn'}`}>
              <strong>{localSignerStatusTitle}</strong>
              <span>{localSignerStatusMessage}</span>
              {displayToken && signerRestartRequired ? <small>{localSignerTokenLabel(displayToken)} - slot {displayToken.slot_id}</small> : null}
              {localSignerVersion ? <small>Versione {localSignerVersion}</small> : null}
            </div>
            {restartSuggested || !localSignerReachable ? (
              <div className="iu-fas-signer-actions">
                <a className="iu-fas-mini-action iu-fas-mini-action--restart" href={LOCAL_SIGNER_RESTART_URI} onClick={scheduleLocalSignerRestartCheck}>
                  <RefreshCw size={14}/> Riavvia Local Signer
                </a>
                <button className="iu-fas-mini-action" type="button" onClick={() => checkLocalSigner(false)} disabled={checkingSigner}>
                  <RefreshCw size={14}/> Riverifica
                </button>
                {localSignerReachable ? <a className="iu-fas-mini-action" href={localSignerEndpoint('/diagnosi')} target="_blank" rel="noreferrer">Diagnosi locale</a> : null}
              </div>
            ) : null}
            {localSignerCanSign ? (
              <>
                <div className="iu-fas-visible-signature">
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
            <label className="iu-fas-field">
              <span>PIN token <b>*</b></span>
              <input type="password" value={pin} onChange={(event) => setPin(event.target.value)} autoComplete="off" placeholder="Il PIN non viene salvato"/>
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
            <p className="iu-fas-signature-help">La firma integrata usa il servizio locale installato su questo PC. IUSENTRA non salva PIN, password o credenziali del token.</p>
              </>
            ) : (
              <div className="iu-fas-signer-next-step">
                <strong>{signerRestartRequired ? 'Prima riavvia e riverifica Local Signer.' : 'Token non pronto per la firma.'}</strong>
                <span>{signerRestartRequired ? 'Il PIN comparira solo quando il token sara allineato e pronto.' : 'Inserisci il token, avvia Local Signer e premi Riverifica.'}</span>
              </div>
            )}
          </div>
        </Panel>

        <Panel title="Firma esterna" subtitle="ArubaSign, Dike o altro software di firma" icon={<UploadCloud size={17}/>}>
          <JsonPostForm className="iu-fas-signature-form" action={firmaUrl} encType="multipart/form-data">
            <p>Scarica il documento, firmalo in CAdES/PAdES secondo la policy del canale, poi carica qui il file firmato.</p>
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
      <FloatingLex context="firma-documento" title="Lex AI firma" body="Posso spiegare differenze tra CAdES, PAdES, firma locale e controlli predeposito, senza sostituire la verifica tecnica." primaryHref="#lex" primaryLabel="Apri Lex firma" secondaryHref={detailUrl} secondaryLabel="Torna ai documenti" />
    </main>
  )
}

function ActivityRow({ activity }:{activity:FascicoloActivity}) {
  return (
    <article className="iu-fas-activity-row">
      <div><Badge tone={activity.tone}>{activity.result || activity.type}</Badge><time>{activity.date || 'n.d.'}</time></div>
      <div><strong>{activity.title}</strong><span>{activity.type}{activity.place ? ` · ${activity.place}` : ''}{activity.lawyer ? ` · ${activity.lawyer}` : ''}</span>{activity.description ? <p>{activity.description}</p> : null}{activity.notes ? <em>{activity.notes}</em> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {activity.updateAction ? <JsonPostForm action={activity.updateAction} className="iu-fas-mini-form"><select name="esito" defaultValue={activity.result || 'IN_ATTESA'}><option value="IN_ATTESA">In attesa</option><option value="FAVOREVOLE">Favorevole</option><option value="PARZIALE">Parziale</option><option value="SFAVOREVOLE">Sfavorevole</option><option value="RINVIATO">Rinviato</option><option value="ANNULLATO">Annullato</option></select><button type="submit">Aggiorna</button></JsonPostForm> : null}
        {activity.deleteAction ? <PostAction action={activity.deleteAction} tone="danger" confirm="Eliminare questa attività?"><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

function DeadlineRow({ deadline }:{deadline:FascicoloDeadline}) {
  return <a className="iu-fas-deadline-row" href={deadline.href}><Badge tone={deadline.tone}>{deadline.priority || deadline.type || 'termine'}</Badge><strong>{deadline.title}</strong><span>{deadline.date}{deadline.peremptory ? ' · perentorio' : ''}</span></a>
}

function DetailPage({ id }:{id:string}) {
  const [data, setData] = useState<FascicoloDetailData>(emptyFascicoloDetail)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [previewDoc, setPreviewDoc] = useState<PreviewDocument | null>(null)
  const [lazyStatus, setLazyStatus] = useState<Record<FascicoloDetailSection, LazySectionStatus>>(emptyLazySections)
  useEffect(() => {
    let active = true
    setLoading(true)
    setLazyStatus(emptyLazySections)
    getFascicoloDetail(id).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])
  const f = data.fascicolo
  const encodedId = encodeURIComponent(f.id || id)
  const operationalHref = f.operationalHref || `/fascicoli/${encodedId}`
  const quadroHref = `/fascicoli/${encodedId}/quadro`
  const compilerHref = `/template-atti/catalogo?id_fascicolo=${encodedId}`
  const editorWorkspaceHref = `${operationalHref}#editor-professionale`
  const detailReturnHref = `/fascicoli/${encodeURIComponent(f.id || id)}#conformita`
  const signedDocuments = data.documents.filter((doc) => doc.signed).length
  const documentsCount = data.quickCounts.documenti || data.documents.length
  const unsignedDocuments = Math.max(0, documentsCount - signedDocuments)
  const editableDocuments = data.documents.filter((doc) => doc.actions.edit)
  const qualityIssues = data.quality.filter((item) => !item.ok).length + (Number(f.alerts) || 0)
  const nextDeadline = data.deadlines[0]
  const nextAppointment = data.appointments[0]
  const preventivo = data.workflow.find((item) => /preventiv/i.test(item.label))
  const conferimento = data.workflow.find((item) => /conferiment|incaric/i.test(item.label))
  const prossimaAzione = nextDeadline?.title || nextAppointment?.title || (qualityIssues ? 'Controlli qualità da verificare' : 'Nessuna urgenza critica rilevata')
  const loadLazySection = (section: FascicoloDetailSection) => {
    if (lazyStatus[section] === 'loaded' || lazyStatus[section] === 'loading') return
    setLazyStatus((current) => ({ ...current, [section]: 'loading' }))
    getFascicoloDetailSection(id, section)
      .then((payload) => {
        setData((current) => ({
          ...current,
          documents: section === 'documenti' ? payload.documents : current.documents,
          activities: section === 'attivita' ? payload.activities : current.activities,
          requests: section === 'attivita' ? payload.requests : current.requests,
          deadlines: section === 'scadenze' ? payload.deadlines : current.deadlines,
          appointments: section === 'scadenze' ? payload.appointments : current.appointments,
          deposits: section === 'depositi' ? payload.deposits : current.deposits,
          regia: section === 'regia' ? payload.regia : current.regia,
        }))
        setLazyStatus((current) => ({ ...current, [section]: 'loaded' }))
      })
      .catch((err) => {
        setLazyStatus((current) => ({ ...current, [section]: 'error' }))
        setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Caricamento sezione non riuscito.' })
      })
  }
  const refreshDetail = (message?: string) => {
    if (message) setToast({ tone: 'success', message })
    getFascicoloDetail(id, { include: 'all' }).then((payload) => {
      setData(payload)
      setLazyStatus({ documenti: 'loaded', attivita: 'loaded', scadenze: 'loaded', depositi: 'loaded', regia: 'loaded' })
    }).catch((err) => setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Aggiornamento fascicolo non riuscito.' }))
  }
  const failDetail = (message: string) => setToast({ tone: 'danger', message })
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<FolderOpen size={34}/>} title="Fascicolo non trovato" action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>Il fascicolo non è disponibile o non hai i permessi per aprirlo.</EmptyState></main>
  return (
    <main id="fascicolo-top" className="iu-content iu-fascicoli-page iu-fascicolo-detail-page">
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div><span className="iu-fas-eyebrow"><FolderOpen size={16}/> Fascicolo</span><h1>{f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge>{f.archiveReady ? <Badge tone="warning">Pronto per archivio</Badge> : null}<span>{f.object || f.subtitle}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><ArrowLeft size={15}/> Fascicoli</Button><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={quadroHref}><Gauge size={15}/> Quadro AI</Button><Button href={compilerHref}><ClipboardCheck size={15}/> Compilatore</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button variant="primary" href={data.actions.exportPdf || f.exportPdfHref}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-case-strip"><strong>{f.ref}</strong><span>Rif. interno {f.internalRef}</span><span>{f.client}</span><span>{f.court}</span><span>{loading ? 'Caricamento...' : 'Dati aggiornati'}</span></section>
      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}
      <nav className="iu-fas-section-nav" aria-label="Sezioni fascicolo"><a href="#profilo">Profilo <b>{data.quickCounts.profilo || 0}</b></a><a href="#regia-operativa">Regia Operativa <b>{data.regia.documentSlots.length}</b></a><a href="#documenti">Documenti <b>{data.quickCounts.documenti || 0}</b></a><a href="#editor-professionale">Editor / compilatore</a><a href="#attivita">Attività <b>{data.quickCounts.attivita || 0}</b></a><a href="#udienze">Udienze / scadenze <b>{data.quickCounts.udienze_scadenze || 0}</b></a><a href="#cancelleria">Cancelleria <b>{data.quickCounts.comunicazioni || 0}</b></a><a href="#istanze">Istanze <b>{data.quickCounts.istanze || 0}</b></a><a href="#gestione">Gestione</a><a href="#economia">Economia</a><a href="#conformita">Conformità</a><a href="#soggetti">Soggetti <b>{data.parties.length}</b></a></nav>
      <section className="iu-fas-ai-board" aria-label="Quadro intelligente AI del fascicolo">
        <div><span><Sparkles size={16}/> Quadro intelligente AI</span><strong>{prossimaAzione}</strong><p>Analisi del fascicolo, documenti, scadenze, attività e prossime azioni usando i dati reali della pratica.</p></div>
        <div>
          <a href={quadroHref}><Gauge size={15}/> Quadro completo</a>
        </div>
      </section>
      <section className="iu-fas-command-bar" aria-label="Strumenti rapidi del fascicolo">
        <a href={editorWorkspaceHref}><PencilLine size={15}/><span>Editor professionale</span></a>
        <a href={compilerHref}><ClipboardCheck size={15}/><span>Compilatore atti</span></a>
        <a href="#documenti"><BrainCircuit size={15}/><span>Indice Lex</span></a>
        <PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina fascicolo</PostAction>
      </section>
      <section className="iu-fas-smart-board" aria-label="Quadro intelligente del fascicolo">
        <header>
          <div><span><Gauge size={16}/> Quadro intelligente</span><strong>{prossimaAzione}</strong></div>
          <a href={quadroHref}>Apri quadro completo</a>
        </header>
        <div>
          <a href="#documenti"><Badge tone={unsignedDocuments ? 'warning' : 'success'}>Documenti</Badge><strong>{unsignedDocuments ? `${unsignedDocuments} da firmare/verificare` : `${signedDocuments} firmati o verificati`}</strong><span>Controlla atti, allegati e file importati dal portale.</span></a>
          <a href="#udienze"><Badge tone={nextDeadline || nextAppointment ? 'warning' : 'neutral'}>Scadenze</Badge><strong>{nextDeadline?.date || nextAppointment?.date || 'Nessuna data critica'}</strong><span>{nextDeadline?.title || nextAppointment?.title || 'Apri lo scadenziario per programmare il presidio.'}</span></a>
          <a href="#workflow"><Badge tone={conferimento?.tone || preventivo?.tone || 'neutral'}>Incarico</Badge><strong>{conferimento?.value || preventivo?.value || 'Da verificare'}</strong><span>{conferimento?.note || preventivo?.note || 'Verifica preventivo, conferimento e collegamenti economici.'}</span></a>
          <a href="#conformita"><Badge tone={qualityIssues ? 'warning' : 'success'}>Conformità</Badge><strong>{qualityIssues ? `${qualityIssues} verifiche aperte` : 'Presidio OK'}</strong><span>Controlli qualità, parti, sync portale e dati principali.</span></a>
        </div>
      </section>
      <section className="iu-fas-detail-grid">
        <div className="iu-fas-detail-main">
          <section className="iu-fas-cockpit"><StatCard icon={<ClipboardCheck size={19}/>} label="Regia" value={`${data.regia.header.completion}%`} note={data.regia.header.operationalState || 'da verificare'} tone={data.regia.validation.ready ? 'success' : data.regia.validation.blockers.length ? 'danger' : 'warning'} href="#regia-operativa"/><StatCard icon={<FileText size={19}/>} label="Documenti" value={data.quickCounts.documenti || 0} note="acquisiti o da portale" tone="primary" href="#documenti"/><StatCard icon={<CalendarDays size={19}/>} label="Scadenze" value={data.quickCounts.udienze_scadenze || 0} note="aperte e concluse" tone="warning" href="#udienze"/><StatCard icon={<ListChecks size={19}/>} label="Attività" value={data.quickCounts.attivita || 0} note="timeline processuale" tone="success" href="#attivita"/><StatCard icon={<WalletCards size={19}/>} label="Economia" value={data.economics.length} note="preventivi, parcelle, tempo" tone="purple" href="#economia"/></section>
          <DetailSection id="profilo" title="Profilo fascicolo" icon={<BadgeCheck size={17}/>}><KvGrid items={data.profile}/>{f.notes ? <div className="iu-fas-note"><strong>Note</strong><p>{f.notes}</p></div> : null}</DetailSection>
          <RegiaOperativaSection data={data} onDone={refreshDetail} onError={failDetail} onOpen={() => loadLazySection('regia')} loading={lazyStatus.regia === 'loading'}/>
          <DetailSection id="documenti" title="Documenti fascicolo" icon={<FileText size={17}/>} count={data.quickCounts.documenti || 0} onOpen={() => loadLazySection('documenti')}>
            <UploadDocumentForm action={data.actions.uploadDocument} documentTypes={data.options.documentTypes} onDone={refreshDetail} onError={failDetail}/>
            <PortalImportForm action={data.actions.importPortal} onDone={refreshDetail} onError={failDetail}/>
            <LexIndexingPanel summary={data.lexIndexing} refreshAction={data.actions.refreshLexIndex} retryAction={data.actions.retryLexIndexErrors} onDone={refreshDetail} onError={failDetail}/>
            <div className="iu-fas-doc-list">{lazyStatus.documenti === 'loading' ? <p className="iu-empty">Caricamento documenti...</p> : null}{data.documents.map((doc) => <DocumentRow doc={doc} key={doc.id} onPreview={setPreviewDoc} onDone={refreshDetail} onError={failDetail}/>)}{lazyStatus.documenti === 'loaded' && !data.documents.length ? <p className="iu-empty">Nessun documento caricato.</p> : null}{lazyStatus.documenti === 'idle' ? <p className="iu-empty">Apri la sezione per caricare i documenti del fascicolo.</p> : null}</div>
          </DetailSection>
          <DetailSection id="editor-professionale" title="Editor professionale e compilatore atti" icon={<PencilLine size={17}/>} count={data.quickCounts.documenti || 0} onOpen={() => loadLazySection('documenti')}>
            <div className="iu-fas-editor-board">
              <a href={compilerHref}><ClipboardCheck size={16}/><strong>Compilatore atti</strong><span>Catalogo modelli collegato a questo fascicolo.</span></a>
              <a href={`/template-atti/nuovo?id_fascicolo=${encodedId}`}><Plus size={16}/><strong>Nuovo modello</strong><span>Crea un template di studio partendo dalla pratica.</span></a>
              <a href={quadroHref}><Gauge size={16}/><strong>Quadro intelligente</strong><span>Sintesi e controlli sul fascicolo prima della redazione.</span></a>
            </div>
            <div className="iu-fas-editor-list">
              {editableDocuments.map((doc) => <a href={doc.actions.edit} key={`editor-${doc.id}`}><PencilLine size={15}/><strong>{doc.name}</strong><span>Apri editor professionale</span></a>)}
              {lazyStatus.documenti === 'loading' ? <p className="iu-empty">Caricamento documenti modificabili...</p> : null}
              {lazyStatus.documenti === 'loaded' && !editableDocuments.length ? <p className="iu-empty">Carica un documento o apri il compilatore atti per iniziare la redazione.</p> : null}
              {lazyStatus.documenti === 'idle' ? <p className="iu-empty">Apri la sezione per caricare i documenti modificabili.</p> : null}
            </div>
          </DetailSection>
          <DetailSection id="attivita" title="Attività processuali" icon={<ListChecks size={17}/>} count={data.quickCounts.attivita || 0} onOpen={() => loadLazySection('attivita')}>
            <JsonPostForm className="iu-fas-add-activity" action={data.actions.addActivity}><select name="tipo" defaultValue="ALTRO">{data.options.activityTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input type="date" name="data" required/><input name="titolo" placeholder="Titolo attività" required/><input name="luogo" placeholder="Luogo"/><select name="esito" defaultValue="IN_ATTESA">{data.options.activityResults.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input name="avvocato" placeholder="Avvocato"/><textarea name="descrizione" placeholder="Descrizione"/><button type="submit"><Plus size={15}/> Aggiungi</button></JsonPostForm>
            <div className="iu-fas-activity-list">{lazyStatus.attivita === 'loading' ? <p className="iu-empty">Caricamento attività...</p> : null}{data.activities.map((activity) => <ActivityRow activity={activity} key={activity.id}/>)}{lazyStatus.attivita === 'loaded' && !data.activities.length ? <p className="iu-empty">Nessuna attività processuale registrata.</p> : null}{lazyStatus.attivita === 'idle' ? <p className="iu-empty">Apri la sezione per caricare la timeline processuale.</p> : null}</div>
          </DetailSection>
          <DetailSection id="udienze" title="Udienze e scadenze" icon={<CalendarDays size={17}/>} count={data.quickCounts.udienze_scadenze || 0} onOpen={() => loadLazySection('scadenze')}>
            {lazyStatus.scadenze === 'loading' ? <p className="iu-empty">Caricamento udienze e scadenze...</p> : null}
            {lazyStatus.scadenze === 'idle' ? <p className="iu-empty">Apri la sezione per caricare udienze e scadenze collegate.</p> : null}
            <div className="iu-fas-two-cols"><div><h3>Scadenze</h3>{data.deadlines.map((deadline) => <DeadlineRow deadline={deadline} key={deadline.id}/>)}{lazyStatus.scadenze === 'loaded' && !data.deadlines.length ? <p className="iu-empty">Nessuna scadenza collegata.</p> : null}<a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuova scadenza</a></div><div><h3>Agenda</h3>{data.appointments.map((app) => <a className="iu-fas-deadline-row" href={app.href} key={app.id}><Badge tone={app.tone}>{app.type || 'agenda'}</Badge><strong>{app.title}</strong><span>{app.date} {app.time} {app.place}</span></a>)}{lazyStatus.scadenze === 'loaded' && !data.appointments.length ? <p className="iu-empty">Nessun appuntamento trovato.</p> : null}<a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo appuntamento</a></div></div>
          </DetailSection>
          <DetailSection id="cancelleria" title="Comunicazioni, depositi e catalogo portale" icon={<Mail size={17}/>} count={data.quickCounts.comunicazioni || 0} onOpen={() => loadLazySection('depositi')}>
            <div className="iu-fas-deposit-list">{lazyStatus.depositi === 'loading' ? <p className="iu-empty">Caricamento depositi...</p> : null}{data.deposits.map((dep) => <article className="iu-fas-deposit" key={dep.id}><header><Badge tone={dep.tone}>{dep.status}</Badge><strong>{dep.actType || 'Deposito'}</strong><span>{dep.timestamp}</span></header><p>{dep.message || dep.pec}</p><div><span>Controlli: {dep.checks || 'n.d.'}</span><span>Fonte: {dep.source || 'locale'}</span><span>Documenti: {dep.documentsCount}</span></div>{dep.portalDocuments.length ? <ul>{dep.portalDocuments.map((doc) => <li key={`${dep.id}-${doc.name}`}>{doc.name} · {doc.type} · {doc.imported ? 'acquisito' : 'da acquisire'}</li>)}</ul> : null}</article>)}{lazyStatus.depositi === 'loaded' && !data.deposits.length ? <p className="iu-empty">Nessun deposito o documento portale censito.</p> : null}{lazyStatus.depositi === 'idle' ? <p className="iu-empty">Apri la sezione per caricare comunicazioni e depositi.</p> : null}</div>
          </DetailSection>
          <DetailSection id="istanze" title="Istanze e atti collegati" icon={<ClipboardCheck size={17}/>} count={data.quickCounts.istanze || 0} onOpen={() => loadLazySection('attivita')}>{lazyStatus.attivita === 'loading' ? <p className="iu-empty">Caricamento istanze...</p> : null}{data.requests.map((activity) => <ActivityRow activity={activity} key={activity.id}/>)}{lazyStatus.attivita === 'loaded' && !data.requests.length ? <p className="iu-empty">Nessuna istanza separata rilevata.</p> : null}{lazyStatus.attivita === 'idle' ? <p className="iu-empty">Apri la sezione per caricare istanze e attività collegate.</p> : null}</DetailSection>
          <DetailSection id="avanzamento" title="Avanzamento pratica" icon={<Clock3 size={17}/>} count={data.history.length}><div className="iu-fas-timeline">{data.history.map((item) => <article key={`${item.date}-${item.description}`}><time>{item.date}</time><strong>{item.description}</strong><span>{item.from} → {item.to}</span><p>{item.notes}</p></article>)}{!data.history.length ? <p className="iu-empty">Nessun avanzamento registrato.</p> : null}</div></DetailSection>
        </div>
        <aside className="iu-fas-detail-side">
          <DetailSection id="gestione" title="Gestione fascicolo" icon={<Gauge size={17}/>}>
            <JsonPostForm className="iu-fas-side-form" action={data.actions.changeState}><label><span>Cambia stato</span><select name="stato" defaultValue={f.status.toUpperCase()}>{data.options.states.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note cambio stato"/><button type="submit"><RefreshCw size={15}/> Aggiorna stato</button></JsonPostForm>
            <div className="iu-fas-action-stack"><JsonPostForm action={data.actions.define}><input name="esito_finale" placeholder="Esito finale"/><input name="motivo" placeholder="Motivo"/><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note definizione"/><button type="submit"><CheckCircle2 size={15}/> Definisci</button></JsonPostForm><PostAction action={data.actions.archive} tone="primary" confirm="Archiviare il fascicolo?" confirmTitle="Archivia fascicolo"><Archive size={15}/> Archivia con ZIP</PostAction><PostAction action={data.actions.restore} tone="secondary" confirm="Ripristinare il fascicolo?" confirmTitle="Ripristina fascicolo"><RotateCcw size={15}/> Ripristina</PostAction><a className="iu-fas-side-link" href={data.actions.exportPdf || f.exportPdfHref}><FileDown size={15}/> PDF fascicolo</a>{data.actions.archiveZip ? <a className="iu-fas-side-link" href={data.actions.archiveZip}><FileArchive size={15}/> Scarica ZIP</a> : null}<PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina</PostAction></div>
          </DetailSection>
          <DetailSection id="economia" title="Controllo economico" icon={<WalletCards size={17}/>} count={data.economics.length}><div className="iu-fas-side-cards">{data.economics.map((item) => <a href={item.href} key={item.id}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}{!data.economics.length ? <p className="iu-empty">Nessun dato economico collegato.</p> : null}</div></DetailSection>
          <DetailSection id="workflow" title="Percorso cliente-incasso" icon={<Sparkles size={17}/>} count={data.workflow.length}><div className="iu-fas-side-cards">{data.workflow.map((item) => item.href ? <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a> : <article key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></article>)}</div></DetailSection>
          <DetailSection id="conformita" title="Conformità e qualità" icon={<ShieldCheck size={17}/>} count={data.quality.length}><div className="iu-fas-quality-list">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}</div><JsonPostForm className={`iu-fas-compliance-toggle ${f.complianceControlsEnabled ? 'is-on' : 'is-off'}`} action={f.complianceControlsEnabled ? data.actions.complianceOff : data.actions.complianceOn} redirectTo={detailReturnHref}><input type="hidden" name="enabled" value={f.complianceControlsEnabled ? '0' : '1'}/><input type="hidden" name="next" value={detailReturnHref}/><button type="submit" aria-pressed={f.complianceControlsEnabled}><span className="iu-fas-compliance-toggle__switch" aria-hidden="true"><i/></span><span><strong>{f.complianceControlsEnabled ? 'Controlli automatici attivi' : 'Controlli automatici disattivati'}</strong><small>{f.complianceControlsEnabled ? 'Disattiva i controlli qualità sul fascicolo' : 'Riattiva i controlli qualità sul fascicolo'}</small></span></button></JsonPostForm></DetailSection>
          <DetailSection id="telematico" title="Servizi telematici" icon={<Send size={17}/>} count={data.telematic.length}><div className="iu-fas-side-cards">{data.telematic.map((item) => <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}</div></DetailSection>
          <DetailSection id="cliente" title="Cliente" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}>{data.client ? <KvGrid items={[{ label: 'Nome', value: data.client.name, href: data.client.href }, { label: 'Codice fiscale', value: data.client.taxCode, mono: true }, { label: 'P. IVA', value: data.client.vat, mono: true }, { label: 'Email', value: data.client.email }, { label: 'PEC', value: data.client.pec }, { label: 'Telefono', value: data.client.phone }, { label: 'Indirizzo', value: data.client.address }]}/> : <p className="iu-empty">Cliente non collegato.</p>}</DetailSection>
          <DetailSection id="soggetti" title="Soggetti e parti" icon={<UsersRound size={17}/>} count={data.parties.length}><div className="iu-fas-party-list">{data.parties.map((party) => <a href={party.href} key={party.id}><strong>{party.name}</strong><span>{party.role || 'Soggetto'} · {party.taxCode || 'C.F. n.d.'}</span><small>{party.email || party.pec || party.phone}</small></a>)}{!data.parties.length ? <p className="iu-empty">Nessun soggetto collegato.</p> : null}</div><a className="iu-fas-inline-link" href={`/soggetti/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo soggetto</a></DetailSection>
        </aside>
      </section>
      <PdfPreviewModal preview={previewDoc} onClose={() => setPreviewDoc(null)}/>
      <a className="iu-fas-back-top" href="#fascicolo-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex context="fascicolo-dettaglio" title="Lex AI fascicolo" body="Posso sintetizzare profilo, documenti, attività, scadenze, depositi, parti e prossime azioni del fascicolo aperto." primaryHref="#lex" primaryLabel="Apri Lex fascicolo" secondaryHref={quadroHref} secondaryLabel="Quadro fascicolo" />
    </main>
  )
}

function moneyFrom(data: FascicoloDetailData, id: string, fallback = 'EUR 0,00') {
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
  const encodedId = encodeURIComponent(f.id || id)
  const operationalHref = f.operationalHref || `/fascicoli/${encodedId}`
  const detailHref = f.href || `/fascicoli/${encodedId}`
  const preventivo = workflowFrom(data, /preventiv/i, 'Preventivo')
  const conferimento = workflowFrom(data, /conferiment|incaric/i, 'Conferimento')
  const signedDocuments = data.documents.filter((doc) => doc.signed).length
  const unsignedDocuments = Math.max(0, data.documents.length - signedDocuments)
  const qualityOk = data.quality.filter((item) => item.ok).length
  const qualityIssues = Math.max(0, data.quality.length - qualityOk + (Number(f.alerts) || 0))
  const qualityStatus = qualityIssues ? `${qualityIssues} verifiche` : 'OK'
  const nextDeadline = data.deadlines[0]
  const nextAppointment = data.appointments[0]
  const valore = moneyFrom(data, 'valore', f.value || 'EUR 0,00')
  const compenso = moneyFrom(data, 'compenso', f.agreedFee || f.quotedValue || 'EUR 0,00')
  const parcelle = moneyFrom(data, 'parcelle')
  const tempo = moneyFrom(data, 'tempo', '0 h')
  const fatturaPa = data.economics.find((item) => item.id === 'fatturapa')
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<Gauge size={34}/>} title="Quadro non disponibile" action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>Il fascicolo non è disponibile o non hai i permessi per aprire il quadro.</EmptyState></main>
  return (
    <main id="fascicolo-quadro-top" className="iu-content iu-fascicoli-page iu-fascicolo-quadro-page">
      <section className="iu-fas-hero iu-fas-quadro-hero">
        <div><span className="iu-fas-eyebrow"><Gauge size={16}/> Quadro fascicolo</span><h1>{f.ref} - {f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge><span>{f.object || f.subtitle || 'Vista sinottica della pratica'}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href={detailHref}><FolderOpen size={15}/> Dettaglio</Button><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button variant="primary" href={data.actions.exportPdf || f.exportPdfHref}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-quadro-strip"><strong>{f.rg}</strong><span>{f.court}</span><span>{f.client}</span><span>{loading ? 'Caricamento quadro...' : 'Dati aggiornati'}</span></section>
      <section className="iu-fas-quadro-kpis" aria-label="Indicatori quadro fascicolo">
        <StatCard icon={<FileText size={19}/>} label="Documenti" value={data.documents.length} note={`${signedDocuments} firmati`} tone="primary"/>
        <StatCard icon={<FileCheck2 size={19}/>} label="Da firmare" value={unsignedDocuments} note="firma / verifica" tone={unsignedDocuments ? 'warning' : 'success'}/>
        <StatCard icon={<Send size={19}/>} label="Depositi PCT" value={data.deposits.length} note={data.deposits[0]?.status || 'nessun deposito'} tone="purple"/>
        <StatCard icon={<Clock3 size={19}/>} label="Scadenze aperte" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.date || nextAppointment?.date || 'nessuna data'} tone="info"/>
        <StatCard icon={<WalletCards size={19}/>} label="Parcelle" value={parcelle} note={`valore ${valore}`} tone="orange"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Conformità" value={qualityStatus} note={qualityIssues ? 'da verificare' : 'nessun blocco critico'} tone={qualityIssues ? 'warning' : 'success'} href="#conformita"/>
      </section>
      <section className="iu-fas-quadro-client">
        <Panel title="Cliente e dati processuali" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}><KvGrid items={[{ label: 'Cliente', value: f.client, href: data.client?.href }, { label: 'Tribunale', value: f.court }, { label: 'RG', value: f.rg, mono: true }, { label: 'Giudice', value: f.judge || 'n.d.' }, { label: 'Sezione', value: f.section || 'n.d.' }, { label: 'Valore', value: valore }]}/></Panel>
      </section>
      <section className="iu-fas-quadro-grid">
        <QuadroAxis id="commerciale" title="Commerciale" icon={<BriefcaseBusiness size={18}/>} status={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'Conferito' : preventivo.value !== 'Non collegato' && preventivo.value !== '0' ? 'Da conferire' : 'Da creare'} tone={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Preventivo" value={preventivo.value} note={preventivo.note} tone={preventivo.tone} href={preventivo.href}/><QuadroMiniCard label="Conferimento" value={conferimento.value} note={conferimento.note} tone={conferimento.tone} href={conferimento.href}/><QuadroMiniCard label="Compenso" value={compenso} note="dato contrattuale del fascicolo" tone="purple" href="/preventivi/"/></div><a className="iu-fas-inline-link" href="/preventivi/"><Plus size={14}/> Gestisci preventivi e incarichi</a></QuadroAxis>
        <QuadroAxis id="operativo" title="Operativo" icon={<ClipboardCheck size={18}/>} status={formatFascicoloStatus(f.status)} tone={f.tone}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Stato" value={formatFascicoloStatus(f.status)} note={f.nextDeadline || 'nessuna prossima scadenza'} tone={f.tone} href={detailHref}/><QuadroMiniCard label="Udienze / scadenze" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.title || nextAppointment?.title || 'nessun evento aperto'} tone="info" href={`${detailHref}#udienze`}/><QuadroMiniCard label="Depositi" value={data.deposits.length} note={data.deposits[0]?.status || 'nessun deposito registrato'} tone="purple" href={`${detailHref}#cancelleria`}/></div></QuadroAxis>
        <QuadroAxis id="conformita" title="Conformità" icon={<ShieldCheck size={18}/>} status={qualityStatus} tone={qualityIssues ? 'warning' : 'success'}><div className="iu-fas-quadro-quality">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}{!data.quality.length ? <p className="iu-empty">Nessuna verifica registrata.</p> : null}</div><a className="iu-fas-inline-link" href={`${detailHref}#conformita`}><ShieldCheck size={14}/> Apri controlli qualità</a></QuadroAxis>
        <QuadroAxis id="economico" title="Economico" icon={<WalletCards size={18}/>} status={parcelle === 'EUR 0,00' ? 'Da valorizzare' : 'Valorizzato'} tone={parcelle === 'EUR 0,00' ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Valore causa" value={valore} note="profilo fascicolo" tone="primary" href={`${detailHref}#profilo`}/><QuadroMiniCard label="Parcelle" value={parcelle} note="documenti economici collegati" tone="success" href="/fatturazione/"/>{fatturaPa ? <QuadroMiniCard label={fatturaPa.label} value={fatturaPa.value} note={fatturaPa.note} tone={fatturaPa.tone} href={fatturaPa.href}/> : null}<QuadroMiniCard label="Tempo" value={tempo} note="voci timesheet valorizzabili" tone="info" href="/timesheet"/></div></QuadroAxis>
        <QuadroAxis id="documenti" title="Documenti" icon={<FileText size={18}/>} status={unsignedDocuments ? `${unsignedDocuments} da firmare` : 'Completi'} tone={unsignedDocuments ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.documents.length} note="documenti fascicolo" tone="primary" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Firmati" value={signedDocuments} note="depositabili / verificati" tone="success" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Da firmare" value={unsignedDocuments} note="controllo operativo" tone={unsignedDocuments ? 'warning' : 'success'} href={`${detailHref}#documenti`}/></div></QuadroAxis>
        <QuadroAxis id="soggetti" title="Soggetti e parti" icon={<UsersRound size={18}/>} status={data.parties.length ? `${data.parties.length} collegati` : 'Da verificare'} tone={data.parties.length ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.parties.length} note="assistiti, controparti e ruoli" tone={data.parties.length ? 'success' : 'warning'} href={`${detailHref}#soggetti`}/><QuadroMiniCard label="Cliente" value={data.client?.name || f.client || 'n.d.'} note="assistito principale" tone="primary" href={data.client?.href || `${detailHref}#profilo`}/><QuadroMiniCard label="Controparte" value={f.counterparty || 'n.d.'} note="dato fascicolo o parte strutturata" tone={f.counterparty ? 'orange' : 'neutral'} href={`${detailHref}#soggetti`}/></div></QuadroAxis>
        <QuadroAxis id="cancelleria" title="Cancelleria e istanze" icon={<Gavel size={18}/>} status={data.deposits.length ? `${data.deposits.length} depositi` : 'Nessun deposito'} tone={data.deposits.length ? 'purple' : 'neutral'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Depositi" value={data.deposits.length} note={data.deposits[0]?.status || 'nessun deposito registrato'} tone="purple" href={`${detailHref}#cancelleria`}/><QuadroMiniCard label="Istanze" value={data.requests.length} note="atti e richieste operative" tone={data.requests.length ? 'primary' : 'neutral'} href={`${detailHref}#istanze`}/><QuadroMiniCard label="Storico" value={data.history.length} note="transizioni e stati fascicolo" tone="info" href={`${detailHref}#gestione`}/></div></QuadroAxis>
        <QuadroAxis id="telematico" title="Servizi telematici" icon={<Send size={18}/>} status={data.telematic.length ? 'Presidiati' : 'Da configurare'} tone={data.telematic.length ? 'primary' : 'warning'}><div className="iu-fas-quadro-flow">{data.telematic.slice(0, 3).map((item) => <QuadroMiniCard key={item.label} label={item.label} value={item.value} note={item.note} tone={item.tone} href={item.href}/>)}</div><a className="iu-fas-inline-link" href="/telematico"><Send size={14}/> Apri servizi telematici</a></QuadroAxis>
      </section>
      <a className="iu-fas-back-top" href="#fascicolo-quadro-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex context="fascicolo-quadro" title="Lex AI quadro" body="Posso leggere il quadro della pratica, riassumere commerciale, operativo, conformità, economico e documenti, e suggerire la prossima azione utile." primaryHref="#lex" primaryLabel="Apri Lex quadro" secondaryHref={detailHref} secondaryLabel="Apri dettaglio" />
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

export function FascicoliPage() {
  const route = parseRoute()
  if (route.kind === 'archive') return <ArchivePage/>
  if (route.kind === 'new') return <FascicoloFormPage mode="new"/>
  if (route.kind === 'export') return <ExportPage/>
  if (route.kind === 'quadro') return <QuadroPage id={route.id}/>
  if (route.kind === 'signature') return <SignaturePage id={route.id} documentId={route.documentId}/>
  if (route.kind === 'edit') return <FascicoloFormPage mode="edit" id={route.id}/>
  if (route.kind === 'detail') return <DetailPage id={route.id}/>
  return <FascicoliListPage/>
}
