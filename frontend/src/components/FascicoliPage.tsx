import { useEffect, useMemo, useState, type FormEvent, type MouseEvent, type ReactNode } from 'react'
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
  ChevronRight,
  ChevronUp,
  ClipboardCheck,
  Clock3,
  Copy,
  Download,
  Edit3,
  Eye,
  FileArchive,
  FileCheck2,
  FileDown,
  FileSignature,
  FileText,
  Fingerprint,
  Filter,
  FolderOpen,
  FolderPlus,
  Gauge,
  Gavel,
  Landmark,
  ListChecks,
  Mail,
  MapPin,
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
  Trash2,
  UploadCloud,
  UserRound,
  UsersRound,
  WalletCards,
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
  getFascicoloDetail,
  getFascicoloDetailSection,
  getFascicoloForm,
  type FascicoliPageData,
  type FascicoliExportData,
  type FascicoloActivity,
  type FascicoloAuditTrail,
  type FascicoloDeadline,
  type FascicoloDetailData,
  type FascicoloDeposit,
  type FascicoloDocument,
  type FascicoloDetailSection,
  type FascicoloFull,
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
  STATI_PRATICA,
  codiceOggettoPstSource,
  findPraticaCollegata,
} from '../data/praticheCollegateCatalog'
import { csrfToken, redirectAfterSuccess, submitFormJson } from '../formSubmit'
import { normaliseStudioRuntimeResult, type StudioRuntimeOffice, type StudioRuntimeResult } from '../studioModuleRuntime'
import { CodiceOggettoPstSearch } from './CodiceOggettoPstSearch'
import { GuidaPraticaSidebar } from './GuidaPraticaSidebar'
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
    office.codice ? `codice ufficio ${office.codice}` : '',
    office.codiceMinistero ? `codice PST ${office.codiceMinistero}` : '',
    office.codiceGiustiziaLocale ? `GL ${office.codiceGiustiziaLocale}` : '',
    office.istatCode ? `ISTAT sede ${office.istatCode}` : '',
  ])
}

const sortLabels: Record<SortKey, string> = {
  recenti: 'Aggiornati di recente',
  rg: 'Anno e numero RG',
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

function openDetailSectionById(id: string) {
  const element = document.getElementById(id)
  if (element instanceof HTMLDetailsElement && !element.open) element.open = true
  if (element) window.requestAnimationFrame(() => element.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  if (window.location.hash !== `#${id}`) window.history.replaceState(null, '', `#${id}`)
}

function relataListHref(item: FascicoloRow): string {
  return item.relataHref || `${item.href}#relata-notifica`
}

function StatCard({ icon, label, value, note, tone = 'primary', href, onClick }:{icon:ReactNode; label:string; value:number|string; note:string; tone?:FascicoloRow['tone']; href?:string; onClick?:(event:MouseEvent<HTMLAnchorElement>)=>void}) {
  const body = (
    <>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </>
  )
  return href ? <a className={`iu-fas-stat iu-fas-stat--${tone}`} href={href} onClick={onClick} title={`Apri ${label}`}>{body}</a> : <article className={`iu-fas-stat iu-fas-stat--${tone}`}>{body}</article>
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
  const tone = summary.status === 'ready' ? 'success' : summary.status === 'error' ? 'danger' : summary.status === 'stale' ? 'warning' : 'info'
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
      {warnings.length ? (
        <div className="iu-fas-lex-indexing__warnings" aria-label="Documenti da verificare per Lex">
          <strong>Documenti da verificare</strong>
          <ul>
            {warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      ) : null}
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
      {item.relataStatusLabel ? <a href={relataListHref(item)} aria-label={`Apri Relata notifica ${item.ref}`} title="Relata notifica"><FileSignature size={15}/></a> : null}
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

function FascicoliTable({ items, selected, onToggle, onToggleAll, archive = false, filtered = false, onDeleted, onError, pagination, pageSize, onPageSizeChange, onPageChange }:{items:FascicoloRow[]; selected:Set<string>; onToggle:(id:string)=>void; onToggleAll:()=>void; archive?:boolean; filtered?:boolean; onDeleted?:(id:string, message?:string)=>void; onError?:(message:string)=>void; pagination?:FascicoliPagination; pageSize?:number; onPageSizeChange?:(value:number)=>void; onPageChange?:(value:number)=>void}) {
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  const total = pagination?.total ?? items.length
  const totalLabel = filtered ? 'fascicoli filtrati' : 'fascicoli'
  const currentPage = pagination?.page ?? 1
  const totalPages = pagination?.pages ?? (items.length ? 1 : 0)
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
      <button type="button" onClick={() => onPageChange(1)} disabled={currentPage <= 1}>Prima</button>
      <button type="button" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1}>Precedente</button>
      <span>Pagina {currentPage} di {Math.max(1, totalPages)} - {total} {totalLabel}</span>
      <div className="iu-fas-page-jump" aria-label="Vai a pagina">
        {pageNumbers.map((value, index) => (
          <button
            type="button"
            className={value === currentPage ? 'is-current' : ''}
            onClick={() => onPageChange(value)}
            disabled={value === currentPage}
            aria-current={value === currentPage ? 'page' : undefined}
            key={value}
          >
            {index > 0 && value - pageNumbers[index - 1] > 1 ? `... ${value}` : value}
          </button>
        ))}
      </div>
      <button type="button" onClick={() => onPageChange(currentPage + 1)} disabled={totalPages === 0 || currentPage >= totalPages}>Successiva</button>
      <button type="button" onClick={() => onPageChange(Math.max(1, totalPages))} disabled={totalPages === 0 || currentPage >= totalPages}>Ultima</button>
    </>
  ) : null
  return (
    <IusentraDataSurface
      title={`${total} ${totalLabel}`}
      subtitle={archive ? 'Archivio pratiche chiuse' : 'Elenco operativo dello studio'}
      toolbar={pageSizeControl}
      footer={paginationControls}
      fill
      className="iu-fas-table-card"
      ariaLabel={archive ? 'Archivio fascicoli' : 'Elenco fascicoli'}
      empty={!items.length ? <p className="iu-empty">Nessun fascicolo corrisponde ai filtri impostati.</p> : null}
    >
      <SyncedTopScrollbar className="iu-fas-table-wrap iusentra-data-surface__scroll">
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
                <td className="iu-fas-title-cell">
                  <a href={item.href}>{item.title}</a>
                  <span>{item.subtitle || item.court}</span>
                  {item.relataStatusLabel ? (
                    <a className={`iu-fas-relata-list-link iu-fas-relata-list-link--${item.relataTone}`} href={relataListHref(item)}>
                      <FileSignature size={14}/>
                      <span>Relata notifica</span>
                      <strong>{item.relataStatusLabel}</strong>
                    </a>
                  ) : null}
                </td>
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
      </SyncedTopScrollbar>
      <div className="iu-fas-mobile-list">
        {items.map((item) => <DossierMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} archive={archive} onDeleted={onDeleted} onError={onError} key={item.id}/>) }
      </div>
    </IusentraDataSurface>
  )
}

function ListFilters({ data, query, setQuery, type, setType, status, setStatus, sort, setSort, advancedOpen, setAdvancedOpen, refresh }:{data:FascicoliPageData; query:string; setQuery:(value:string)=>void; type:FascicoloTipo; setType:(value:FascicoloTipo)=>void; status:FascicoloStato; setStatus:(value:FascicoloStato)=>void; sort:SortKey; setSort:(value:SortKey)=>void; advancedOpen:boolean; setAdvancedOpen:(value:boolean)=>void; refresh:()=>void}) {
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
      <button className="iu-fas-filter-btn" type="button" onClick={() => setAdvancedOpen(!advancedOpen)} aria-expanded={advancedOpen}><Filter size={16}/> Filtri</button>
      <button className="iu-fas-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna fascicoli"><RefreshCw size={17}/></button>
    </IusentraFiltersBar>
  )
}

function InsightPanel({ data, visible }:{data:FascicoliPageData; visible:FascicoloRow[]}) {
  const urgent = visible.filter((item) => item.alerts > 0 || item.unreadCommunications > 0).slice(0, 4)
  const withoutDeadline = visible.filter((item) => item.status !== 'archiviato' && !item.nextDeadlineIso && item.nextDeadline === 'n.d.').length
  return (
    <IusentraSupportRail className="iu-fas-insights">
      <IusentraPanelCard title="Cabina fascicoli" subtitle="Controlli che conviene avere subito" icon={Gauge}>
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
  const [type, setType] = useState<FascicoloTipo>('tutti')
  const [status, setStatus] = useState<FascicoloStato>('tutti')
  const [sort, setSort] = useState<SortKey>('rg')
  const [court, setCourt] = useState('')
  const [debouncedCourt, setDebouncedCourt] = useState('')
  const [alertsOnly, setAlertsOnly] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [toast, setToast] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(5)

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
  const filtersActive = Boolean(query.trim() || type !== 'tutti' || status !== 'tutti' || court.trim() || alertsOnly)
  const updateType = (value: FascicoloTipo) => { setPage(1); setType(value) }
  const updateStatus = (value: FascicoloStato) => { setPage(1); setStatus(value) }
  const updateSort = (value: SortKey) => { setPage(1); setSort(value) }
  const updateAlertsOnly = (value: boolean) => { setPage(1); setAlertsOnly(value) }
  const updatePageSize = (value: number) => { setPage(1); setPageSize(value) }
  const updatePage = (value: number) => setPage(Math.max(1, Math.min(Math.max(1, data.pagination.pages || 1), value)))

  const selectedVisible = visible.filter((item) => selected.has(item.id)).length
  const selectedItems = visible.filter((item) => selected.has(item.id))
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const toggleAll = () => setSelected((current) => {
    const allSelected = visible.length > 0 && visible.every((item) => current.has(item.id))
    if (allSelected) return new Set([...current].filter((id) => !visible.some((item) => item.id === id)))
    return new Set([...current, ...visible.map((item) => item.id)])
  })
  const handleBulkDelete = async () => {
    if (!selectedItems.length) return
    const refs = selectedItems.map((item) => item.ref).join(', ')
    const message = selectedItems.length === 1
      ? `Eliminare definitivamente il fascicolo ${selectedItems[0].ref}?`
      : `Eliminare definitivamente ${selectedItems.length} fascicoli selezionati? ${refs}`
    if (!window.confirm(message)) return
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

  return (
    <main className="iu-content iu-fascicoli-page">
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

      <IusentraMainArea className="iu-fas-layout">
        <IusentraMainSurface className="iu-fas-main-list">
          <ListFilters data={data} query={query} setQuery={setQuery} type={type} setType={updateType} status={status} setStatus={updateStatus} sort={sort} setSort={updateSort} advancedOpen={advancedOpen} setAdvancedOpen={setAdvancedOpen} refresh={refresh}/>

      {advancedOpen ? (
      <IusentraContextFilters className="iu-fas-advanced is-open">
        <div className="iu-fas-context-summary">
          <strong>{sortLabels[sort]}</strong>
          <small>{court ? `Ufficio: ${court}` : 'Tutti gli uffici'}{alertsOnly ? ' · solo alert' : ''}</small>
        </div>
        {advancedOpen ? (
          <>
            <label><span>Ufficio giudiziario</span><input value={court} onChange={(event) => setCourt(event.target.value)} placeholder="Tribunale, TAR, GDP..."/></label>
            <label><span>Ordinamento</span><select value={sort} onChange={(event) => updateSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
            <label className="iu-fas-check"><input type="checkbox" checked={alertsOnly} onChange={(event) => updateAlertsOnly(event.target.checked)}/><span>Solo fascicoli con alert o comunicazioni</span></label>
          </>
        ) : null}
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
              <button className="is-danger" type="button" onClick={() => { void handleBulkDelete() }}><Trash2 size={14}/> Elimina selezionati</button>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll} onDeleted={handleFascicoloDeleted} onError={handleListError} filtered={filtersActive} pagination={data.pagination} pageSize={pageSize} onPageSizeChange={updatePageSize} onPageChange={updatePage}/>
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

function CounterpartyFields({ data, required }:{data:FascicoloFormData; required:boolean}) {
  const initialName = getValue(data, 'counterparty')
  const initialCode = getValue(data, 'counterpartyTaxCode') || getValue(data, 'cf_controparte')
  const [selectedId, setSelectedId] = useState('')
  const [counterpartyName, setCounterpartyName] = useState(initialName)
  const [counterpartyCode, setCounterpartyCode] = useState(initialCode)
  const [createSubject, setCreateSubject] = useState(false)
  const [subjectType, setSubjectType] = useState('PERSONA_GIURIDICA')
  useEffect(() => {
    setCounterpartyName(initialName)
    setCounterpartyCode(initialCode)
  }, [initialName, initialCode])
  const selected = data.subjects.find((subject) => subject.id === selectedId)
  const handleSubjectChange = (value: string) => {
    setSelectedId(value)
    const subject = data.subjects.find((item) => item.id === value)
    if (subject) {
      setCounterpartyName(subject.label)
      setCounterpartyCode(subject.taxCode || subject.vat)
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
            {selected.href ? <a href={selected.href}>Apri soggetto</a> : null}
          </div>
        ) : <small className="iu-fas-field-help">Se il soggetto esiste già, selezionalo: nome e identificativo vengono riportati nel fascicolo.</small>}
      </div>
      <Field label="Controparte" name="controparte" required={required}>
        <input name="controparte" value={counterpartyName} onChange={(event) => setCounterpartyName(event.currentTarget.value)} required={required} placeholder="Nome o ragione sociale della controparte"/>
      </Field>
      <Field label="Codice fiscale / P. IVA controparte" name="cf_controparte" required={required}>
        <input name="cf_controparte" value={counterpartyCode} onChange={(event) => setCounterpartyCode(event.currentTarget.value)} required={required} placeholder="Dato necessario per la scheda soggetto"/>
      </Field>
      <Field label={NUOVO_FASCICOLO_LABELS.fields.attorePrincipale} name="attore_principale" defaultValue={getValue(data, 'attorePrincipale')}/>
      <label className="iu-fas-check-field iu-fas-check-field--wide">
        <input type="checkbox" name="crea_soggetto_controparte" value="1" checked={createSubject} onChange={(event) => setCreateSubject(event.currentTarget.checked)}/>
        <span>Crea anche la scheda soggetto della controparte</span>
        <small>Utile quando la controparte non è ancora in anagrafica. Nome e identificativo restano obbligatori.</small>
      </label>
      {createSubject ? (
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
        selectedOfficeCode ? `codice ufficio ${selectedOfficeCode}` : '',
        selectedPstCode ? `codice PST ${selectedPstCode}` : '',
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
              <em>Fonte territoriale verificata; il codice ministeriale depositabile non è esposto per questo ufficio. Prima del deposito conferma il canale sul portale ufficiale.</em>
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
        help="Scegli dal catalogo ministeriale PST. Il codice resta modificabile finché non viene generata o inviata la busta."
        onChange={(codice) => setSelectedCode(codice)}
      />
      <input type="hidden" name="tipo_procedimento" value={currentProcedure}/>
      <input type="hidden" name="area_pratica" value={currentArea}/>
      <input type="hidden" name="fonte_codice_oggetto" value={selectedCode ? source.fonteCodiceOggetto : ''}/>
      <input type="hidden" name="file_fonte_codice_oggetto" value={selectedCode ? source.fileFonteCodiceOggetto : ''}/>
      <small id="pratiche-collegate-help" className="iu-fas-field-help">
        Il codice scelto viene conservato nel fascicolo e sarà usato nei passaggi di deposito quando il flusso lo richiede.
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
        <JsonPostForm className="iu-fas-form" action={data.action || (mode === 'edit' && id ? `/fascicoli/${encodeURIComponent(id)}/modifica` : '/fascicoli/nuovo')} redirectTo={data.detailHref || data.backHref} encType="multipart/form-data">
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
              <CounterpartyFields data={data} required={fascicoloVeloce}/>
              <a className="iu-fas-inline-link" href="/soggetti/nuovo" target="_blank" rel="noreferrer"><Plus size={14}/> Nuovo soggetto</a>
            </div>
          </CollapsibleFormPanel>
          <CollapsibleFormPanel title={labels.sections.identificazioneGiudiziale} subtitle="Autorità, numero di ruolo e riferimenti dell'ufficio" icon={<Landmark size={17}/>}>
            <div className="iu-fas-form-grid">
              <JudicialOfficeField data={data} required={fascicoloVeloce}/>
              <Field label={labels.fields.numeroRuolo} name="numero_rg" defaultValue={getValue(data, 'numeroRg')}/>
              <Field label="Anno iscrizione" name="anno_rg" type="number" defaultValue={getValue(data, 'annoRg') || new Date().getFullYear()}/>
              <Field label="Sezione" name="sezione" defaultValue={getValue(data, 'section')}/>
              <Field label={labels.fields.istruttorePmGip} name="istruttore_pm_gip" defaultValue={getValue(data, 'istruttorePmGip') || getValue(data, 'judge')}/>
              <Field label={labels.fields.cancelliere} name="cancelliere" defaultValue={getValue(data, 'cancelliere')}/>
              <Field label={labels.fields.ctu} name="ctu" defaultValue={getValue(data, 'ctu')}/>
              <Field label={labels.fields.ctp} name="ctp" defaultValue={getValue(data, 'ctp')}/>
              <Field label="Valore causa (EUR)" name="valore_causa" type="number" defaultValue={getValue(data, 'valueRaw') || getValue(data, 'value')} placeholder="0.00"/>
              <Field label="Compenso pattuito (EUR)" name="compenso_pattuito" type="number" defaultValue={getValue(data, 'agreedFeeRaw') || getValue(data, 'agreedFee')} readOnly={Boolean(getValue(data, 'agreedFee'))}/>
              <Field label="Valore preventivato (EUR)" name="valore_preventivato" type="number" defaultValue={getValue(data, 'quotedValueRaw') || getValue(data, 'quotedValue')} readOnly={Boolean(getValue(data, 'quotedValue'))}/>
              <input type="hidden" name="id_pratica" value={getValue(data, 'practiceId')}/>
              <input type="hidden" name="procedura_operativa_codice" value={getValue(data, 'proceduraOperativaCodice')}/>
              <Field label="Data prima udienza / comparizione" name="data_prima_udienza" type="date" defaultValue={getValue(data, 'firstHearingIso') || getValue(data, 'firstHearing')}/>
              <Field label="Data notificazione citazione" name="data_notifica_citazione" type="date" defaultValue={getValue(data, 'citationNotificationIso') || getValue(data, 'citationNotification')}/>
            </div>
          </CollapsibleFormPanel>
          <CollapsibleFormPanel title={labels.sections.annotazioni} subtitle="Referente, dominus e note operative" icon={<BriefcaseBusiness size={17}/>}>
            <div className="iu-fas-form-grid"><Field label="Avvocato referente" name="avvocato_referente" defaultValue={getValue(data, 'leadLawyer')}/><Field label="Avvocato dominus" name="avvocato_dominus" defaultValue={getValue(data, 'dominus')}/><TextAreaField label={labels.fields.annotazioni} name="note" defaultValue={getValue(data, 'notes')} rows={4}/></div>
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
      </section>
      <FloatingLex context="fascicolo-form" title="Lex AI fascicolo" body="Posso aiutarti a completare oggetto, tipo procedimento, checklist iniziale, scadenze e dati mancanti prima della creazione o modifica." primaryHref="#lex" primaryLabel="Apri Lex fascicolo" secondaryHref="/fascicoli" secondaryLabel="Torna ai fascicoli" />
    </main>
  )
}

function KvGrid({ items }:{items:KeyValue[]}) {
  return <div className="iu-fas-kv-grid">{items.map((item) => <div key={`${item.label}-${item.value}`}><span>{item.label}</span>{item.href ? <a href={item.href} className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</a> : <strong className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</strong>}</div>)}</div>
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

type PreviewDocument = { name: string; url: string; downloadUrl: string }
type LazySectionStatus = 'idle' | 'loading' | 'loaded' | 'error'

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

function recordHref(row: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = recordText(row, key, fallback)
  return value.startsWith('/') || value.startsWith('#') ? value : fallback
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
    ['Percorso', h.workflow],
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
        {metaItems.length ? (
          <div className="iu-fas-regia__meta">
            {metaItems.map(([label, value]) => <span key={label}><strong>{label}</strong>{value}</span>)}
          </div>
        ) : null}
        <div className="iu-fas-regia__grid">
          <article>
            <h4>Contesto economico e incarico</h4>
            <div className="iu-fas-regia-action-list">
              <RegiaActionCard label="Preventivo accettato" value={recordBool(economics, 'preventivoAccepted') ? 'Si' : 'No'} note={recordBool(economics, 'preventivoAccepted') ? 'Apri preventivo' : 'Apri per accettare o creare'} href={preventivoHref} tone={recordBool(economics, 'preventivoAccepted') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Conferimento firmato" value={recordBool(economics, 'conferimentoSigned') ? 'Si' : 'No'} note={recordBool(economics, 'conferimentoSigned') ? 'Apri conferimento' : 'Apri il conferimento'} href={conferimentoHref} tone={recordBool(economics, 'conferimentoSigned') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Avviso / parcella" value={recordBool(economics, 'proformaIssued') ? 'Emesso' : 'Non emesso'} note={recordBool(economics, 'proformaIssued') ? 'Apri documento economico' : 'Crea la parcella'} href={proformaHref} tone={recordBool(economics, 'proformaIssued') ? 'success' : 'warning'}/>
              <RegiaActionCard label="Pagamento" value={recordBool(economics, 'paymentRegistered') ? 'Registrato' : 'Da registrare'} note={recordBool(economics, 'paymentRegistered') ? 'Apri incassi' : 'Registra incasso'} href={paymentHref} tone={recordBool(economics, 'paymentRegistered') ? 'success' : 'warning'}/>
            </div>
            <ul className="iu-fas-regia__facts">
              <li><span>Compenso pattuito</span><strong>{recordText(economics, 'agreedFee', 'EUR 0,00')}</strong></li>
              <li><span>Spese vive / anticipazioni</span><strong>{recordText(economics, 'expenses', 'EUR 0,00')}</strong></li>
            </ul>
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
              {regia.checklist.map((item) => <article key={recordText(item, 'id') || recordText(item, 'key')}><Badge tone={recordText(item, 'status') === 'BLOCCATO' ? 'danger' : recordText(item, 'status') === 'COMPLETATO' ? 'success' : 'warning'}>{recordText(item, 'status', 'Da completare')}</Badge><strong>{recordText(item, 'label')}</strong><span>{recordText(item, 'message')}</span><small>{recordText(item, 'suggestedAction')}</small></article>)}
              {!regia.checklist.length ? <div className="iu-fas-regia-empty-card"><strong>Checklist da creare</strong><span>La Regia genera i controlli dopo il profilo operativo del fascicolo.</span>{recalculateAction ? <PostAction action={recalculateAction} tone="secondary" onDone={onDone} onError={onError}><RefreshCw size={15}/> Aggiorna Regia</PostAction> : null}</div> : null}
            </div>
          </section>
          <section>
            <h4>Slot documentali</h4>
            <div className="iu-fas-regia-list">
              {regia.documentSlots.map((slot) => <article key={recordText(slot, 'slotKey')}><Badge tone={recordText(slot, 'status') === 'VALIDO' ? 'success' : recordText(slot, 'status') === 'WARNING' ? 'warning' : recordText(slot, 'status') === 'NON_APPLICABILE' ? 'neutral' : 'danger'}>{recordText(slot, 'status')}</Badge><strong>{recordText(slot, 'label')}</strong><span>{recordText(slot, 'documentId') ? `Documento ${recordText(slot, 'documentId')}` : recordText(slot, 'message', 'Documento non collegato')}</span><small>{recordText(slot, 'suggestedAction')}</small></article>)}
              {!regia.documentSlots.length ? <div className="iu-fas-regia-empty-card"><strong>Slot da impostare</strong><span>Carica o classifica i documenti, poi aggiorna la Regia per creare gli slot richiesti.</span><a href="#documenti"><FileText size={15}/> Vai ai documenti</a></div> : null}
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

function NotificationRelataMonitor({ data }:{data:FascicoloDetailData}) {
  const monitor = data.notificationRelata
  const actions = [
    { label: monitor.primaryLabel || 'Apri presidio', href: monitor.primaryHref, icon: monitor.status === 'da_acquisire' ? <FileDown size={15}/> : <FileSignature size={15}/> },
    { label: 'Acquisisci dal portale', href: monitor.acquisitionHref, icon: <FileDown size={15}/> },
    { label: 'Prepara relata', href: monitor.prepareHref, icon: <FileSignature size={15}/> },
    { label: 'Deposita prova', href: monitor.depositHref, icon: <Send size={15}/> },
  ].filter((item, index, rows) => item.href && rows.findIndex((row) => row.href === item.href) === index)
  const total = Math.max(monitor.pendingPortalDocuments, monitor.relataDocuments, monitor.signedRelataDocuments, monitor.proofDocuments)
  return (
    <div className={`iu-fas-relata-monitor iu-fas-relata-monitor--${monitor.tone}`}>
      <header>
        <div>
          <Badge tone={monitor.tone}>{monitor.statusLabel}</Badge>
          <h3>Relata notifica</h3>
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
            <em>{step.status.replace(/_/g, ' ')}</em>
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
                <span>{[doc.fontePortale || 'Portale Servizi', doc.ufficio, doc.numeroRg && doc.annoRg ? `R.G. ${doc.numeroRg}/${doc.annoRg}` : '', doc.dataDeposito].filter(Boolean).join(' · ')}</span>
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
                <span>{[doc.kind.replace(/_/g, ' '), doc.status.replace(/_/g, ' ')].filter(Boolean).join(' · ')}</span>
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

const documentAutoSectionOrder: Array<Omit<DocumentAutoSection, 'documents'>> = [
  { id: 'atti', title: 'Atti e memorie', note: 'Atto principale, difese e bozze redazionali.', tone: 'primary' },
  { id: 'provvedimenti', title: 'Provvedimenti', note: 'Sentenze, ordinanze, decreti e verbali.', tone: 'purple' },
  { id: 'comunicazioni', title: 'Comunicazioni', note: 'PEC, cancelleria, notifiche e messaggi collegati.', tone: 'info' },
  { id: 'allegati', title: 'Allegati e supporti', note: 'Procure, contratti, parcelle e allegati di fascicolo.', tone: 'neutral' },
  { id: 'da-verificare', title: 'Da verificare', note: 'Documenti senza sezione certa da controllare.', tone: 'warning' },
]

function documentSearchText(doc: FascicoloDocument): string {
  return normaliseText([doc.type, doc.name, doc.source, doc.portalClass, doc.portalName, doc.portalSender, doc.statusLabel, ...doc.tags].join(' '))
}

function documentAutoSectionId(doc: FascicoloDocument): string {
  const text = documentSearchText(doc)
  if (/(pec|cancelleria|comunicazion|notifica|relata|busta|rdac|rac|esito|ricevut|accettazion)/.test(text)) return 'comunicazioni'
  if (/(sentenza|ordinanza|decreto|provvediment|verbale)/.test(text)) return 'provvedimenti'
  if (/(atto giudiziario|ricorso|citazione|comparsa|memoria|conclusionale|replica)/.test(text)) return 'atti'
  if (/(procura|contratto|parcella|fattura|allegato|documento ufficiale)/.test(text)) return 'allegati'
  return 'da-verificare'
}

function depositCommunicationText(dep: FascicoloDeposit): string {
  return normaliseText([dep.status, dep.actType, dep.message, dep.pec, dep.source, dep.timestamp].join(' '))
}

function depositMetaLine(dep: FascicoloDeposit): string {
  const docs = dep.documentsCount === 1 ? '1 documento' : dep.documentsCount > 1 ? `${dep.documentsCount} documenti` : ''
  return [dep.timestamp || 'Data non indicata', dep.pec, docs, dep.source].filter(Boolean).join(' - ')
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
  return (
    <div className={`iu-fas-deposit-state iu-fas-deposit-state--${summary.tone}`}>
      <Badge tone={summary.tone}>{summary.label}</Badge>
      <span>{summary.body}</span>
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
          <small className="iu-fas-field-help">Puoi selezionare più file. IUSENTRA li classifica dal nome, oppure puoi scegliere il tipo per ogni documento.</small>
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

function DocumentRow({ doc, onPreview, onDone, onError }:{doc:FascicoloDocument; onPreview:(preview:PreviewDocument)=>void; onDone:(message?:string)=>void; onError:(message:string)=>void}) {
  const [renaming, setRenaming] = useState(false)
  const [draftName, setDraftName] = useState(doc.name)
  const [renameBusy, setRenameBusy] = useState(false)
  const [renameMessage, setRenameMessage] = useState('')

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
      <div><strong>{doc.name}</strong><span>{doc.type} · {doc.size || 'dimensione n.d.'} · {doc.documentDate || doc.uploadedAt || 'data n.d.'}</span>{doc.notes ? <p>{doc.notes}</p> : null}{doc.tags.length ? <em>{doc.tags.join(', ')}</em> : null}</div>
      {renaming ? (
        <form className="iu-fas-doc-rename-form" onSubmit={submitRename}>
          <input value={draftName} onChange={(event) => setDraftName(event.currentTarget.value)} aria-label={`Nuovo nome file ${doc.name}`} />
          <button type="submit" disabled={renameBusy}>{renameBusy ? 'Salvo...' : 'Salva nome'}</button>
          <button type="button" onClick={() => setRenaming(false)} disabled={renameBusy}>Annulla</button>
          {renameMessage ? <small>{renameMessage}</small> : null}
        </form>
      ) : null}
      <div className="iu-fas-doc-badges"><Badge tone={doc.statusTone}>{doc.statusLabel || (doc.signed ? 'Firmato' : 'Da firmare')}</Badge>{doc.source ? <Badge tone="neutral">{doc.source}</Badge> : null}{doc.portalClass ? <Badge tone="info">{doc.portalClass}</Badge> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {doc.actions.preview ? <button type="button" title="Anteprima interna" onClick={() => onPreview({ name: doc.name, url: doc.actions.preview, downloadUrl: doc.actions.download })}><Eye size={15}/></button> : null}
        {doc.actions.download ? <a href={doc.actions.download} title="Scarica"><Download size={15}/></a> : null}
        {doc.actions.edit ? <a href={doc.actions.edit} title="Modifica documento" aria-label={`Modifica documento ${doc.name}`}><PencilLine size={15}/></a> : null}
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
  const resultText = normaliseText(activity.result)
  const badgeText = !resultText || /non applicabile/.test(resultText)
    ? (activity.type || 'Evento')
    : depositStatusLabel(activity.result)
  const metaLine = [activity.type, activity.place, activity.lawyer].filter(Boolean).join(' - ')
  return (
    <article className="iu-fas-activity-row">
      <div className="iu-fas-activity-date"><Badge tone={activity.tone}>{badgeText}</Badge><time>{activity.date || 'n.d.'}</time></div>
      <div className="iu-fas-activity-main"><strong>{activity.title}</strong>{metaLine ? <span>{metaLine}</span> : null}{activity.description ? <p>{activity.description}</p> : null}{activity.notes ? <em>{activity.notes}</em> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap iu-fas-activity-actions">
        {activity.updateAction ? <JsonPostForm action={activity.updateAction} className="iu-fas-mini-form iu-fas-mini-form--activity"><select name="esito" defaultValue={activity.result || 'IN_ATTESA'} aria-label="Esito attivita"><option value="IN_ATTESA">In attesa</option><option value="FAVOREVOLE">Favorevole</option><option value="PARZIALE">Parziale</option><option value="SFAVOREVOLE">Sfavorevole</option><option value="RINVIATO">Rinviato</option><option value="ANNULLATO">Annullato</option></select><button type="submit"><CheckCircle2 size={13}/> Salva</button></JsonPostForm> : null}
        {activity.deleteAction ? <PostAction action={activity.deleteAction} tone="danger" confirm="Eliminare questa attività?"><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

function DeadlineRow({ deadline }:{deadline:FascicoloDeadline}) {
  return <a className="iu-fas-deadline-row" href={deadline.href}><Badge tone={deadline.tone}>{deadline.priority || deadline.type || 'termine'}</Badge><strong>{deadline.title}</strong><span>{deadline.date}{deadline.peremptory ? ' · perentorio' : ''}</span></a>
}

function formatAuditDate(value: string) {
  if (!value) return 'n.d.'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('it-IT', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'UTC' }).format(parsed)
}

function copyAuditHash(value: string) {
  if (!value || typeof navigator === 'undefined' || !navigator.clipboard) return
  void navigator.clipboard.writeText(value)
}

function AuditTrailSection({ audit, bundleHref, onOpen, loading = false }:{audit:FascicoloAuditTrail; bundleHref:string; onOpen?:()=>void; loading?:boolean}) {
  const effectiveBundleHref = audit.enabled ? (audit.actions.bundle || bundleHref) : ''
  return (
    <DetailSection id="audit" title="Audit" icon={<Fingerprint size={17}/>} count={audit.summary.total} onOpen={onOpen}>
      {loading ? <p className="iu-empty">Caricamento audit...</p> : null}
      <div className="iu-fas-audit-summary">
        <span><Badge tone={audit.summary.signed === audit.summary.total && audit.summary.total ? 'success' : 'warning'}>{audit.summary.signed}</Badge><strong>Firmati</strong></span>
        <span><Badge tone={audit.summary.worm === audit.summary.total && audit.summary.total ? 'success' : 'warning'}>{audit.summary.worm}</Badge><strong>WORM</strong></span>
        <span><Badge tone={audit.summary.snapshotted ? 'success' : 'neutral'}>{audit.summary.snapshotted}</Badge><strong>In snapshot</strong></span>
        <span><Badge tone={audit.summary.tsaVerified ? 'success' : 'neutral'}>{audit.summary.tsaVerified}</Badge><strong>TSA verificata</strong></span>
      </div>
      <div className="iu-fas-audit-actions">
        {effectiveBundleHref ? <a href={effectiveBundleHref}><PackageCheck size={15}/> Scarica bundle fascicolo</a> : null}
      </div>
      {!audit.enabled ? <p className="iu-empty">Presidio probatorio non attivo per questo studio.</p> : null}
      {audit.enabled && !audit.events.length ? <p className="iu-empty">Nessuna evidenza audit registrata per questo fascicolo.</p> : null}
      <div className="iu-fas-audit-list">
        {audit.events.map((event) => (
          <article className="iu-fas-audit-row" key={event.eventId}>
            <div>
              <Badge tone={event.tone}>{event.kindLabel}</Badge>
              <time>{formatAuditDate(event.eventTsUtc)} UTC</time>
            </div>
            <div>
              <strong>{event.eventHashShort || event.eventHash || 'hash non disponibile'}</strong>
              <span>{event.prevEventHash ? 'Concatenato al precedente evento' : 'Primo evento del fascicolo'}</span>
            </div>
            <div className="iu-fas-audit-badges">
              {event.signed ? <Badge tone="success">Firmato</Badge> : <Badge tone="warning">Firma da verificare</Badge>}
              {event.worm ? <Badge tone="success">WORM</Badge> : <Badge tone="warning">Conservazione da verificare</Badge>}
              {event.inSnapshot ? <Badge tone="success">In snapshot</Badge> : <Badge tone="neutral">Snapshot in attesa</Badge>}
              {event.tsaVerified ? <Badge tone="success">TSA verificata</Badge> : null}
            </div>
            <div className="iu-fas-actions iu-fas-actions--wrap">
              {event.eventHash ? <button type="button" title="Copia hash completo" onClick={() => copyAuditHash(event.eventHash)}><Copy size={15}/></button> : null}
              {event.proofHref ? <a href={event.proofHref} title="Scarica prova"><Download size={15}/></a> : null}
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
  const [lazyStatus, setLazyStatus] = useState<Record<FascicoloDetailSection, LazySectionStatus>>(emptyLazySections)
  useEffect(() => {
    let active = true
    setLoading(true)
    setLazyStatus(emptyLazySections)
    getFascicoloDetail(id).then((payload) => {
      if (active) {
        setData(payload)
      }
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])
  useEffect(() => {
    if (loading) return
    const sectionId = decodeURIComponent(window.location.hash.replace(/^#/, ''))
    if (!sectionId) return
    window.setTimeout(() => openDetailSectionById(sectionId), 80)
  }, [loading, data.fascicolo.id])
  const f = data.fascicolo
  const encodedId = encodeURIComponent(f.id || id)
  const operationalHref = f.operationalHref || `/fascicoli/${encodedId}`
  const quadroHref = `/fascicoli/${encodedId}/quadro`
  const compilerHref = `/template-atti/catalogo?id_fascicolo=${encodedId}`
  const detailReturnHref = `/fascicoli/${encodeURIComponent(f.id || id)}#conformita`
  const exportPdfHref = data.actions.exportPdf || f.exportPdfHref
  const depositTelematicHref = data.telematic.find((item) => /deposito telematico/i.test(item.label))?.href || `/fascicoli/${encodedId}/deposito/prepara`
  const clientId = data.client?.id || f.clientId
  const clientRecordHref = clientId ? `/clienti/${encodeURIComponent(clientId)}/modifica` : '/clienti'
  const partiesRecordHref = `/soggetti?fascicolo=${encodedId}`
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
  const comunicazioniRows = data.deposits.filter((dep) => !isCancelleriaCommunication(dep))
  const cancelleriaRows = data.deposits.filter(isCancelleriaCommunication)
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
          notificationRelata: section === 'relata' ? payload.notificationRelata : current.notificationRelata,
          auditTrail: section === 'audit' ? payload.auditTrail : current.auditTrail,
          lexIndexing: section === 'lex' ? payload.lexIndexing : current.lexIndexing,
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
      setLazyStatus({ documenti: 'loaded', attivita: 'loaded', scadenze: 'loaded', depositi: 'loaded', regia: 'loaded', relata: 'loaded', audit: 'loaded', lex: 'loaded' })
    }).catch((err) => setToast({ tone: 'danger', message: err instanceof Error ? err.message : 'Aggiornamento fascicolo non riuscito.' }))
  }
  const failDetail = (message: string) => setToast({ tone: 'danger', message })
  const openSection = (sectionId: string, lazySection?: FascicoloDetailSection) => (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    if (lazySection) loadLazySection(lazySection)
    openDetailSectionById(sectionId)
  }
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<FolderOpen size={34}/>} title="Fascicolo non trovato" action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>Il fascicolo non è disponibile o non hai i permessi per aprirlo.</EmptyState></main>
  return (
    <main id="fascicolo-top" className="iu-content iu-fascicoli-page iu-fascicolo-detail-page">
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div><span className="iu-fas-eyebrow"><FolderOpen size={16}/> Fascicolo</span><h1>{f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge>{f.archiveReady ? <Badge tone="warning">Pronto per archivio</Badge> : null}<span>{f.object || f.subtitle}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><ArrowLeft size={15}/> Fascicoli</Button><Button variant="primary" href={depositTelematicHref}><Send size={15}/> Deposito telematico</Button><a className="iu-button iu-button--secondary iu-fas-record-link" href={clientRecordHref} target="_blank" rel="noopener noreferrer" aria-label="Apri anagrafica cliente in una nuova finestra" title="Apri anagrafica cliente in una nuova finestra"><UserRound size={15}/> Cliente</a><a className="iu-button iu-button--secondary iu-fas-record-link" href={partiesRecordHref} target="_blank" rel="noopener noreferrer" aria-label="Apri soggetti e parti in una nuova finestra" title="Apri soggetti e parti in una nuova finestra"><UsersRound size={15}/> Soggetti</a><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={quadroHref}><Gauge size={15}/> Quadro AI</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button href={exportPdfHref} disabled={!exportPdfHref} title={!exportPdfHref ? 'PDF fascicolo non disponibile' : undefined}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-case-strip"><strong>{f.ref}</strong><span>Rif. interno {f.internalRef}</span><span>{f.client}</span><span>{f.court}</span><span>{loading ? 'Caricamento...' : 'Dati aggiornati'}</span></section>
      {toast ? <section className={`iu-fas-toast iu-fas-toast--${toast.tone}`}><span>{toast.message}</span><button type="button" onClick={() => setToast(null)}>Chiudi</button></section> : null}
      <nav className="iu-fas-section-nav" aria-label="Sezioni fascicolo"><a href="#profilo">Profilo <b>{data.quickCounts.profilo || 0}</b></a><a href="#guida-pratica">Guida pratica</a><a href="#uffici-competenti">Uffici</a><a href="#regia-operativa">Regia Operativa <b>{data.regia.documentSlots.length}</b></a><a href="#documenti">Documenti e atti <b>{data.quickCounts.documenti || 0}</b></a><a href="#relata-notifica">Relata notifica <b>{notificationRelataCount}</b></a><a href="#attivita">Attività <b>{data.quickCounts.attivita || 0}</b></a><a href="#udienze">Udienze / scadenze <b>{data.quickCounts.udienze_scadenze || 0}</b></a><a href="#cancelleria">Comunicazioni / Cancelleria <b>{data.quickCounts.comunicazioni || 0}</b></a><a href="#audit">Audit <b>{data.auditTrail.summary.total}</b></a><a href="#gestione">Gestione</a><a href="#economia">Contesto economico</a><a href="#conformita">Conformità</a><a href="#soggetti">Soggetti <b>{data.parties.length}</b></a></nav>
      <section className="iu-fas-detail-grid iu-fas-detail-grid--with-guide">
        <aside className="iu-fas-guide-column" aria-label="Guida pratica facoltativa del fascicolo">
          <GuidaPraticaSidebar fascicoloId={f.id || id} codice={f.codiceOggettoPst} fascicoloTitle={f.title}/>
        </aside>
        <div className="iu-fas-detail-content-column">
        <div className="iu-fas-detail-main">
      <section className="iu-fas-ai-board" aria-label="Quadro intelligente AI del fascicolo">
        <div><span><Sparkles size={16}/> Quadro intelligente AI</span><strong>{prossimaAzione}</strong><p>Analisi del fascicolo, documenti, scadenze, attività e prossime azioni usando i dati reali della pratica.</p></div>
        <div className="iu-fas-ai-actions">
          <a href={quadroHref}><Gauge size={15}/> Quadro completo</a>
          <a href="#documenti"><FileText size={15}/> Documenti e atti</a>
          <a href={compilerHref}><ClipboardCheck size={15}/> Compilatore atti</a>
          <a href="#documenti"><BrainCircuit size={15}/> Indice Lex</a>
          <PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina fascicolo</PostAction>
        </div>
      </section>
      <section className="iu-fas-smart-board" aria-label="Quadro intelligente del fascicolo">
        <header>
          <div><span><Gauge size={16}/> Quadro intelligente</span><strong>{prossimaAzione}</strong></div>
          <a href={quadroHref}>Apri quadro completo</a>
        </header>
        <div>
          <a href="#documenti"><Badge tone={unsignedDocuments ? 'warning' : 'success'}>Documenti</Badge><strong>{unsignedDocuments ? `${unsignedDocuments} da firmare/verificare` : `${signedDocuments} firmati o verificati`}</strong><span>Controlla atti, allegati e file acquisiti nel fascicolo.</span></a>
          <a href="#relata-notifica"><Badge tone={notificationRelata.tone}>Relata</Badge><strong>{notificationRelata.statusLabel}</strong><span>{notificationRelata.systemNotification || 'Presidio sempre visibile per notifica e prova.'}</span></a>
          <a href="#udienze"><Badge tone={nextDeadline || nextAppointment ? 'warning' : 'neutral'}>Scadenze</Badge><strong>{nextDeadline?.date || nextAppointment?.date || 'Nessuna data critica'}</strong><span>{nextDeadline?.title || nextAppointment?.title || 'Apri lo scadenziario per programmare il presidio.'}</span></a>
          <a href="#workflow"><Badge tone={conferimento?.tone || preventivo?.tone || 'neutral'}>Incarico</Badge><strong>{conferimento?.value || preventivo?.value || 'Da verificare'}</strong><span>{conferimento?.note || preventivo?.note || 'Verifica preventivo, conferimento e collegamenti economici.'}</span></a>
          <a href="#conformita"><Badge tone={qualityIssues ? 'warning' : 'success'}>Conformità</Badge><strong>{qualityIssues ? `${qualityIssues} verifiche aperte` : 'Presidio OK'}</strong><span>Controlli qualità, parti, sync portale e dati principali.</span></a>
        </div>
      </section>
          <section className="iu-fas-cockpit"><StatCard icon={<ClipboardCheck size={19}/>} label="Regia" value={`${data.regia.header.completion}%`} note={data.regia.header.operationalState || 'da verificare'} tone={data.regia.validation.ready ? 'success' : data.regia.validation.blockers.length ? 'danger' : 'warning'} href="#regia-operativa" onClick={openSection('regia-operativa', 'regia')}/><StatCard icon={<MapPin size={19}/>} label="Uffici" value="Cerca" note="competenza per Comune" tone="success" href="#uffici-competenti" onClick={openSection('uffici-competenti')}/><StatCard icon={<FileText size={19}/>} label="Documenti" value={data.quickCounts.documenti || 0} note="carica e classifica" tone="primary" href="#documenti" onClick={openSection('documenti', 'documenti')}/><StatCard icon={<FileSignature size={19}/>} label="Relata" value={notificationRelataCount} note={notificationRelata.statusLabel} tone={notificationRelata.tone} href="#relata-notifica" onClick={openSection('relata-notifica', 'relata')}/><StatCard icon={<CalendarDays size={19}/>} label="Scadenze" value={data.quickCounts.udienze_scadenze || 0} note="gestisci agenda" tone="warning" href="#udienze" onClick={openSection('udienze', 'scadenze')}/><StatCard icon={<ListChecks size={19}/>} label="Attività" value={data.quickCounts.attivita || 0} note="aggiorna timeline" tone="success" href="#attivita" onClick={openSection('attivita', 'attivita')}/><StatCard icon={<Fingerprint size={19}/>} label="Audit" value={data.auditTrail.summary.total} note={data.auditTrail.summary.snapshotted ? 'prove in snapshot' : 'prove disponibili'} tone={data.auditTrail.summary.total ? 'success' : 'neutral'} href="#audit" onClick={openSection('audit', 'audit')}/><StatCard icon={<WalletCards size={19}/>} label="Contesto economico" value={data.economics.length} note="incarico e incassi" tone="purple" href="#economia" onClick={openSection('economia')}/></section>
          <DetailSection id="profilo" title="Profilo fascicolo" icon={<BadgeCheck size={17}/>}><KvGrid items={data.profile}/><SourceSnapshotPanel fascicolo={f}/>{f.notes ? <div className="iu-fas-note"><strong>Note</strong><p>{f.notes}</p></div> : null}</DetailSection>
          <DetailSection id="uffici-competenti" title="Uffici giudiziari per Comune" icon={<MapPin size={17}/>} defaultOpen>
            <FascicoloUfficiCompetentiPanel fascicolo={f}/>
          </DetailSection>
          <RegiaOperativaSection data={data} onDone={refreshDetail} onError={failDetail} onOpen={() => loadLazySection('regia')} loading={lazyStatus.regia === 'loading'}/>
          <DetailSection id="relata-notifica" title="Relata notifica" icon={<FileSignature size={17}/>} count={notificationRelataCount} defaultOpen={notificationRelata.releaseDetected || notificationRelata.status !== 'monitoraggio'} onOpen={() => loadLazySection('relata')}>
            <NotificationRelataMonitor data={data}/>
          </DetailSection>
          <DetailSection id="documenti" title="Documenti e atti" icon={<FileText size={17}/>} count={data.quickCounts.documenti || 0} onOpen={() => { loadLazySection('documenti'); loadLazySection('lex') }}>
            <DocumentUploadWorkspace data={data} onDone={refreshDetail} onError={failDetail}/>
            <LexIndexingPanel summary={data.lexIndexing} refreshAction={data.actions.refreshLexIndex} retryAction={data.actions.retryLexIndexErrors} onDone={refreshDetail} onError={failDetail}/>
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
          <DetailSection id="attivita" title="Attività processuali" icon={<ListChecks size={17}/>} count={data.quickCounts.attivita || 0} onOpen={() => loadLazySection('attivita')}>
            <JsonPostForm className="iu-fas-add-activity" action={data.actions.addActivity}><select name="tipo" defaultValue="ALTRO">{data.options.activityTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input type="date" name="data" required/><input name="titolo" placeholder="Titolo attività" required/><input name="luogo" placeholder="Luogo"/><select name="esito" defaultValue="IN_ATTESA">{data.options.activityResults.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input name="avvocato" placeholder="Avvocato"/><textarea name="descrizione" placeholder="Descrizione"/><button type="submit"><Plus size={15}/> Aggiungi</button></JsonPostForm>
            <div className="iu-fas-activity-list">{lazyStatus.attivita === 'loading' ? <p className="iu-empty">Caricamento attività...</p> : null}{data.activities.map((activity) => <ActivityRow activity={activity} key={activity.id}/>)}{lazyStatus.attivita === 'loaded' && !data.activities.length ? <p className="iu-empty">Nessuna attività processuale registrata.</p> : null}{lazyStatus.attivita === 'idle' ? <p className="iu-empty">Apri la sezione per caricare la timeline processuale.</p> : null}</div>
          </DetailSection>
          <DetailSection id="udienze" title="Udienze e scadenze" icon={<CalendarDays size={17}/>} count={data.quickCounts.udienze_scadenze || 0} onOpen={() => loadLazySection('scadenze')}>
            {lazyStatus.scadenze === 'loading' ? <p className="iu-empty">Caricamento udienze e scadenze...</p> : null}
            {lazyStatus.scadenze === 'idle' ? <p className="iu-empty">Apri la sezione per caricare udienze e scadenze collegate.</p> : null}
            <div className="iu-fas-two-cols"><div><h3>Scadenze</h3>{data.deadlines.map((deadline) => <DeadlineRow deadline={deadline} key={deadline.id}/>)}{lazyStatus.scadenze === 'loaded' && !data.deadlines.length ? <p className="iu-empty">Nessuna scadenza collegata.</p> : null}<a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuova scadenza</a></div><div><h3>Agenda</h3>{data.appointments.map((app) => <a className="iu-fas-deadline-row" href={app.href} key={app.id}><Badge tone={app.tone}>{app.type || 'agenda'}</Badge><strong>{app.title}</strong><span>{app.date} {app.time} {app.place}</span></a>)}{lazyStatus.scadenze === 'loaded' && !data.appointments.length ? <p className="iu-empty">Nessun appuntamento trovato.</p> : null}<a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo appuntamento</a></div></div>
          </DetailSection>
          <DetailSection id="cancelleria" title="Comunicazioni / Cancelleria" icon={<Mail size={17}/>} count={(comunicazioniRows.length + cancelleriaRows.length) || data.quickCounts.comunicazioni || 0} onOpen={() => loadLazySection('depositi')}>
            <div className="iu-fas-comm-dep-grid">
              <div className="iu-fas-comm-column">
                <Panel title="Comunicazioni" icon={<Mail size={17}/>} count={comunicazioniRows.length}>
                  <div className="iu-fas-comm-list">
                    {lazyStatus.depositi === 'loading' ? <p className="iu-empty">Caricamento comunicazioni...</p> : null}
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
                    {lazyStatus.depositi === 'loaded' && !comunicazioniRows.length ? <p className="iu-empty">Nessuna comunicazione PEC collegata al fascicolo.</p> : null}
                    {lazyStatus.depositi === 'idle' ? <p className="iu-empty">Apri la sezione per caricare le comunicazioni PEC del fascicolo.</p> : null}
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
          <DetailSection id="avanzamento" title="Avanzamento pratica" icon={<Clock3 size={17}/>} count={data.history.length}><div className="iu-fas-timeline">{data.history.map((item) => <article key={`${item.date}-${item.description}`}><time>{item.date}</time><strong>{item.description}</strong><span>{item.from} → {item.to}</span><p>{item.notes}</p></article>)}{!data.history.length ? <p className="iu-empty">Nessun avanzamento registrato.</p> : null}</div></DetailSection>
          <AuditTrailSection audit={data.auditTrail} bundleHref={data.actions.auditBundle} onOpen={() => loadLazySection('audit')} loading={lazyStatus.audit === 'loading'}/>
        </div>
        <aside className="iu-fas-detail-side">
          <DetailSection id="gestione" title="Gestione fascicolo" icon={<Gauge size={17}/>}>
            <JsonPostForm className="iu-fas-side-form" action={data.actions.changeState}><label><span>Cambia stato</span><select name="stato" defaultValue={f.status.toUpperCase()}>{data.options.states.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note cambio stato"/><button type="submit"><RefreshCw size={15}/> Aggiorna stato</button></JsonPostForm>
            <div className="iu-fas-action-stack"><JsonPostForm action={data.actions.define}><input name="esito_finale" placeholder="Esito finale"/><input name="motivo" placeholder="Motivo"/><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note definizione"/><button type="submit"><CheckCircle2 size={15}/> Definisci</button></JsonPostForm><PostAction action={data.actions.archive} tone="primary" confirm="Archiviare il fascicolo?" confirmTitle="Archivia fascicolo"><Archive size={15}/> Archivia con ZIP</PostAction><PostAction action={data.actions.restore} tone="secondary" confirm="Ripristinare il fascicolo?" confirmTitle="Ripristina fascicolo"><RotateCcw size={15}/> Ripristina</PostAction>{exportPdfHref ? <a className="iu-fas-side-link" href={exportPdfHref}><FileDown size={15}/> PDF fascicolo</a> : <button className="iu-fas-side-link is-disabled" type="button" disabled title="PDF fascicolo non disponibile"><FileDown size={15}/> PDF fascicolo</button>}{data.actions.archiveZip ? <a className="iu-fas-side-link" href={data.actions.archiveZip}><FileArchive size={15}/> Scarica ZIP</a> : null}<PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?" confirmTitle="Elimina fascicolo" redirectTo="/fascicoli"><Trash2 size={15}/> Elimina</PostAction></div>
          </DetailSection>
          <DetailSection id="economia" title="Contesto economico" icon={<WalletCards size={17}/>} count={data.economics.length}><div className="iu-fas-side-cards">{data.economics.map((item) => <a href={item.href} onClick={item.href.startsWith('#') ? openSection(item.href.slice(1)) : undefined} key={item.id}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}{!data.economics.length ? <p className="iu-empty">Nessun dato economico collegato.</p> : null}</div></DetailSection>
          <DetailSection id="workflow" title="Percorso cliente-incasso" icon={<Sparkles size={17}/>} count={data.workflow.length}><div className="iu-fas-side-cards">{data.workflow.map((item) => item.href ? <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a> : <article key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></article>)}</div></DetailSection>
          <DetailSection id="conformita" title="Conformità e qualità" icon={<ShieldCheck size={17}/>} count={data.quality.length}><div className="iu-fas-quality-list">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}</div><JsonPostForm className={`iu-fas-compliance-toggle ${f.complianceControlsEnabled ? 'is-on' : 'is-off'}`} action={f.complianceControlsEnabled ? data.actions.complianceOff : data.actions.complianceOn} redirectTo={detailReturnHref}><input type="hidden" name="enabled" value={f.complianceControlsEnabled ? '0' : '1'}/><input type="hidden" name="next" value={detailReturnHref}/><button type="submit" aria-pressed={f.complianceControlsEnabled}><span className="iu-fas-compliance-toggle__switch" aria-hidden="true"><i/></span><span><strong>{f.complianceControlsEnabled ? 'Controlli automatici attivi' : 'Controlli automatici disattivati'}</strong><small>{f.complianceControlsEnabled ? 'Disattiva i controlli qualità sul fascicolo' : 'Riattiva i controlli qualità sul fascicolo'}</small></span></button></JsonPostForm></DetailSection>
          <DetailSection id="telematico" title="Servizi telematici" icon={<Send size={17}/>} count={data.telematic.length}><div className="iu-fas-side-cards">{data.telematic.map((item) => <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}</div></DetailSection>
          <DetailSection id="cliente" title="Cliente" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}>{data.client ? <KvGrid items={[{ label: 'Nome', value: data.client.name, href: data.client.href }, { label: 'Codice fiscale', value: data.client.taxCode, mono: true }, { label: 'P. IVA', value: data.client.vat, mono: true }, { label: 'Email', value: data.client.email }, { label: 'PEC', value: data.client.pec }, { label: 'Telefono', value: data.client.phone }, { label: 'Indirizzo', value: data.client.address }]}/> : <p className="iu-empty">Cliente non collegato.</p>}</DetailSection>
          <DetailSection id="soggetti" title="Soggetti e parti" icon={<UsersRound size={17}/>} count={data.parties.length}><div className="iu-fas-party-list">{data.parties.map((party) => <a href={party.href} key={party.id}><strong>{party.name}</strong><span>{party.role || 'Soggetto'} · {party.taxCode || 'C.F. n.d.'}</span><small>{party.email || party.pec || party.phone}</small></a>)}{!data.parties.length ? <p className="iu-empty">Nessun soggetto collegato.</p> : null}</div><a className="iu-fas-inline-link" href={`/soggetti/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo soggetto</a></DetailSection>
        </aside>
        </div>
      </section>
      <PdfPreviewModal preview={previewDoc} onClose={() => setPreviewDoc(null)}/>
      <a className="iu-fas-back-top" href="#fascicolo-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex context="fascicolo-dettaglio" title="Lex AI fascicolo" body="Posso sintetizzare profilo, documenti, attività, scadenze, cancelleria, parti e prossime azioni del fascicolo aperto." primaryHref="#lex" primaryLabel="Apri Lex fascicolo" secondaryHref={quadroHref} secondaryLabel="Quadro fascicolo" />
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
  const exportPdfHref = data.actions.exportPdf || f.exportPdfHref
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
        <div className="iu-fas-hero__actions"><Button href={detailHref}><FolderOpen size={15}/> Dettaglio</Button><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button variant="primary" href={exportPdfHref} disabled={!exportPdfHref} title={!exportPdfHref ? 'PDF fascicolo non disponibile' : undefined}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-quadro-strip"><strong>{f.rg}</strong><span>{f.court}</span><span>{f.client}</span><span>{loading ? 'Caricamento quadro...' : 'Dati aggiornati'}</span></section>
      <section className="iu-fas-quadro-kpis" aria-label="Indicatori quadro fascicolo">
        <StatCard icon={<FileText size={19}/>} label="Documenti" value={data.documents.length} note={`${signedDocuments} firmati`} tone="primary"/>
        <StatCard icon={<FileCheck2 size={19}/>} label="Da firmare" value={unsignedDocuments} note="firma / verifica" tone={unsignedDocuments ? 'warning' : 'success'}/>
        <StatCard icon={<Send size={19}/>} label="Cancelleria" value={data.deposits.length} note={data.deposits[0]?.status || 'nessuna PEC'} tone="purple"/>
        <StatCard icon={<Clock3 size={19}/>} label="Scadenze aperte" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.date || nextAppointment?.date || 'nessuna data'} tone="info"/>
        <StatCard icon={<WalletCards size={19}/>} label="Parcelle" value={parcelle} note={`valore ${valore}`} tone="orange"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Conformità" value={qualityStatus} note={qualityIssues ? 'da verificare' : 'nessun blocco critico'} tone={qualityIssues ? 'warning' : 'success'} href="#conformita"/>
      </section>
      <section className="iu-fas-quadro-client">
        <Panel title="Cliente e dati processuali" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}><KvGrid items={[{ label: 'Cliente', value: f.client, href: data.client?.href }, { label: 'Tribunale', value: f.court }, { label: 'RG', value: f.rg, mono: true }, { label: 'Giudice', value: f.judge || 'n.d.' }, { label: 'Sezione', value: f.section || 'n.d.' }, { label: 'Valore', value: valore }]}/></Panel>
      </section>
      <section className="iu-fas-quadro-grid">
        <QuadroAxis id="commerciale" title="Commerciale" icon={<BriefcaseBusiness size={18}/>} status={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'Conferito' : preventivo.value !== 'Non collegato' && preventivo.value !== '0' ? 'Da conferire' : 'Da creare'} tone={conferimento.value !== 'Non collegato' && conferimento.value !== '0' ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Preventivo" value={preventivo.value} note={preventivo.note} tone={preventivo.tone} href={preventivo.href}/><QuadroMiniCard label="Conferimento" value={conferimento.value} note={conferimento.note} tone={conferimento.tone} href={conferimento.href}/><QuadroMiniCard label="Compenso" value={compenso} note="dato contrattuale del fascicolo" tone="purple" href="/preventivi/"/></div><a className="iu-fas-inline-link" href="/preventivi/"><Plus size={14}/> Gestisci preventivi e incarichi</a></QuadroAxis>
        <QuadroAxis id="operativo" title="Operativo" icon={<ClipboardCheck size={18}/>} status={formatFascicoloStatus(f.status)} tone={f.tone}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Stato" value={formatFascicoloStatus(f.status)} note={f.nextDeadline || 'nessuna prossima scadenza'} tone={f.tone} href={detailHref}/><QuadroMiniCard label="Udienze / scadenze" value={data.deadlines.length + data.appointments.length} note={nextDeadline?.title || nextAppointment?.title || 'nessun evento aperto'} tone="info" href={`${detailHref}#udienze`}/><QuadroMiniCard label="Cancelleria" value={data.deposits.length} note={data.deposits[0]?.status || 'nessuna PEC collegata'} tone="purple" href={`${detailHref}#cancelleria`}/></div></QuadroAxis>
        <QuadroAxis id="conformita" title="Conformità" icon={<ShieldCheck size={18}/>} status={qualityStatus} tone={qualityIssues ? 'warning' : 'success'}><div className="iu-fas-quadro-quality">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}{!data.quality.length ? <p className="iu-empty">Nessuna verifica registrata.</p> : null}</div><a className="iu-fas-inline-link" href={`${detailHref}#conformita`}><ShieldCheck size={14}/> Apri controlli qualità</a></QuadroAxis>
        <QuadroAxis id="economico" title="Contesto economico" icon={<WalletCards size={18}/>} status={parcelle === 'EUR 0,00' ? 'Da valorizzare' : 'Valorizzato'} tone={parcelle === 'EUR 0,00' ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Valore causa" value={valore} note="profilo fascicolo" tone="primary" href={`${detailHref}#profilo`}/><QuadroMiniCard label="Parcelle" value={parcelle} note="documenti economici collegati" tone="success" href="/fatturazione/"/>{fatturaPa ? <QuadroMiniCard label={fatturaPa.label} value={fatturaPa.value} note={fatturaPa.note} tone={fatturaPa.tone} href={fatturaPa.href}/> : null}<QuadroMiniCard label="Tempo" value={tempo} note="voci timesheet valorizzabili" tone="info" href="/timesheet"/></div></QuadroAxis>
        <QuadroAxis id="documenti" title="Documenti" icon={<FileText size={18}/>} status={unsignedDocuments ? `${unsignedDocuments} da firmare` : 'Completi'} tone={unsignedDocuments ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.documents.length} note="documenti fascicolo" tone="primary" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Firmati" value={signedDocuments} note="depositabili / verificati" tone="success" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Da firmare" value={unsignedDocuments} note="controllo operativo" tone={unsignedDocuments ? 'warning' : 'success'} href={`${detailHref}#documenti`}/></div></QuadroAxis>
        <QuadroAxis id="soggetti" title="Soggetti e parti" icon={<UsersRound size={18}/>} status={data.parties.length ? `${data.parties.length} collegati` : 'Da verificare'} tone={data.parties.length ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.parties.length} note="assistiti, controparti e ruoli" tone={data.parties.length ? 'success' : 'warning'} href={`${detailHref}#soggetti`}/><QuadroMiniCard label="Cliente" value={data.client?.name || f.client || 'n.d.'} note="assistito principale" tone="primary" href={data.client?.href || `${detailHref}#profilo`}/><QuadroMiniCard label="Controparte" value={f.counterparty || 'n.d.'} note="dato fascicolo o parte strutturata" tone={f.counterparty ? 'orange' : 'neutral'} href={`${detailHref}#soggetti`}/></div></QuadroAxis>
        <QuadroAxis id="cancelleria" title="Comunicazioni e cancelleria" icon={<Gavel size={18}/>} status={data.deposits.length ? `${data.deposits.length} PEC` : 'Nessuna PEC'} tone={data.deposits.length ? 'purple' : 'neutral'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Comunicazioni" value={data.deposits.length} note={data.deposits[0]?.message || 'nessuna PEC collegata'} tone="purple" href={`${detailHref}#cancelleria`}/><QuadroMiniCard label="Storico" value={data.history.length} note="transizioni e stati fascicolo" tone="info" href={`${detailHref}#gestione`}/></div></QuadroAxis>
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
