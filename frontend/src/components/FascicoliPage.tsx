import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Archive,
  ArrowLeft,
  BadgeCheck,
  Bell,
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
  getFascicoloForm,
  type FascicoliPageData,
  type FascicoliExportData,
  type FascicoloActivity,
  type FascicoloDeadline,
  type FascicoloDetailData,
  type FascicoloDocument,
  type FascicoloFormData,
  type FascicoloRow,
  type FascicoloStato,
  type FascicoloTipo,
  type KeyValue,
  type SelectOption,
} from '../fascicoliData'
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

function sortRows(rows: FascicoloRow[], sort: SortKey): FascicoloRow[] {
  const copy = [...rows]
  if (sort === 'rg') return copy.sort((a, b) => a.rg.localeCompare(b.rg, 'it'))
  if (sort === 'cliente') return copy.sort((a, b) => a.client.localeCompare(b.client, 'it'))
  if (sort === 'scadenza') return copy.sort((a, b) => (a.nextDeadlineIso || '9999').localeCompare(b.nextDeadlineIso || '9999'))
  if (sort === 'documenti') return copy.sort((a, b) => b.documents - a.documents)
  return copy.sort((a, b) => (b.updatedAt || b.openedAt || '').localeCompare(a.updatedAt || a.openedAt || ''))
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

function PostAction({ action, children, tone = 'secondary', confirm }:{action:string; children:ReactNode; tone?:'primary'|'secondary'|'danger'|'ghost'; confirm?:string}) {
  if (!action) return null
  return (
    <form method="post" action={action} onSubmit={(event) => { if (confirm && !window.confirm(confirm)) event.preventDefault() }}>
      <button className={`iu-fas-post iu-fas-post--${tone}`} type="submit">{children}</button>
    </form>
  )
}

function RowActions({ item, archive = false }:{item:FascicoloRow; archive?:boolean}) {
  return (
    <div className="iu-fas-actions" aria-label={`Azioni fascicolo ${item.ref}`}>
      <a href={item.href} aria-label="Apri fascicolo React" title="Apri"><Eye size={15}/></a>
      {!archive ? <a href={item.editHref} aria-label="Modifica fascicolo React" title="Modifica"><PencilLine size={15}/></a> : null}
      <a href={item.exportPdfHref} aria-label="Esporta PDF fascicolo" title="PDF"><FileDown size={15}/></a>
      {archive && item.archive?.zipAvailable ? <a href={item.archiveZipHref} aria-label="Scarica ZIP archivio" title="ZIP"><FileArchive size={15}/></a> : null}
    </div>
  )
}

function DossierMobileCard({ item, checked, onToggle, archive = false }:{item:FascicoloRow; checked:boolean; onToggle:()=>void; archive?:boolean}) {
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
        <RowActions item={item} archive={archive}/>
      </footer>
    </article>
  )
}

function FascicoliTable({ items, selected, onToggle, onToggleAll, archive = false }:{items:FascicoloRow[]; selected:Set<string>; onToggle:(id:string)=>void; onToggleAll:()=>void; archive?:boolean}) {
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  return (
    <section className="iu-fas-table-card" aria-label={archive ? 'Archivio fascicoli' : 'Elenco fascicoli'}>
      <div className="iu-fas-table-head">
        <strong>{items.length} fascicoli</strong>
        <label>
          <span>25 per pagina</span>
          <ChevronDown size={14}/>
        </label>
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
                <td><RowActions item={item} archive={archive}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="iu-fas-mobile-list">
        {items.map((item) => <DossierMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} archive={archive} key={item.id}/>) }
      </div>
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
          <a href="/lex?context=fascicoli"><Sparkles size={15}/> Chiedi a Lex</a>
        </div>
      </Panel>
    </aside>
  )
}

function FascicoliListPage() {
  const [data, setData] = useState<FascicoliPageData>(emptyFascicoliPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [type, setType] = useState<FascicoloTipo>('tutti')
  const [status, setStatus] = useState<FascicoloStato>('tutti')
  const [sort, setSort] = useState<SortKey>('recenti')
  const [court, setCourt] = useState('')
  const [alertsOnly, setAlertsOnly] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const refresh = () => {
    setLoading(true)
    getFascicoliPage().then(setData).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getFascicoliPage().then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const visible = useMemo(() => {
    const courtNeedle = normaliseText(court)
    const filtered = data.items.filter((item) => {
      if (!isInsideQuery(item, query)) return false
      if (type !== 'tutti' && item.type !== type) return false
      if (status !== 'tutti' && item.status !== status) return false
      if (alertsOnly && item.alerts === 0 && item.unreadCommunications === 0) return false
      if (courtNeedle && !normaliseText(item.court).includes(courtNeedle)) return false
      return true
    })
    return sortRows(filtered, sort)
  }, [alertsOnly, court, data.items, query, sort, status, type])

  const selectedVisible = visible.filter((item) => selected.has(item.id)).length
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const toggleAll = () => setSelected((current) => {
    const allSelected = visible.length > 0 && visible.every((item) => current.has(item.id))
    if (allSelected) return new Set([...current].filter((id) => !visible.some((item) => item.id === id)))
    return new Set([...current, ...visible.map((item) => item.id)])
  })

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

      <ListFilters data={data} query={query} setQuery={setQuery} type={type} setType={setType} status={status} setStatus={setStatus} advancedOpen={advancedOpen} setAdvancedOpen={setAdvancedOpen} refresh={refresh}/>

      {advancedOpen ? (
        <section className="iu-fas-advanced" aria-label="Filtri avanzati fascicoli">
          <label><span>Ufficio giudiziario</span><input value={court} onChange={(event) => setCourt(event.target.value)} placeholder="Tribunale, TAR, GDP..."/></label>
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label className="iu-fas-check"><input type="checkbox" checked={alertsOnly} onChange={(event) => setAlertsOnly(event.target.checked)}/><span>Solo fascicoli con alert o comunicazioni</span></label>
        </section>
      ) : null}

      <section className="iu-fas-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione fascicoli...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> React gestisce la vista; salvataggi e audit restano sui servizi backend già governati.</small>
        {selectedVisible ? <small className="iu-fas-selected">{selectedVisible} selezionati</small> : null}
      </section>

      <section className="iu-fas-layout">
        <div className="iu-fas-main-list">
          {selectedVisible ? (
            <div className="iu-fas-bulkbar">
              <strong>{selectedVisible} fascicoli selezionati</strong>
              <a href="/fascicoli/esporta"><Download size={14}/> Esporta selezione</a>
              <a href="/lex?context=fascicoli"><Sparkles size={14}/> Sintesi Lex</a>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll}/>
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

      <FloatingLex context="fascicoli" title="Lex AI fascicoli" body="Posso sintetizzare un fascicolo, evidenziare scadenze senza prossima azione, preparare una lista documenti e suggerire il percorso prima di deposito, udienza o archiviazione." primaryHref="/lex?context=fascicoli" primaryLabel="Apri Lex sui fascicoli" secondaryHref="/global-search?tipo=fascicoli" secondaryLabel="Cerca nello studio" />
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
  useEffect(() => { let active = true; getFascicoliArchive().then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [])
  const visible = useMemo(() => data.items.filter((item) => isInsideQuery(item, query)), [data.items, query])
  const toggle = (id: string) => setSelected((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const toggleAll = () => setSelected((current) => visible.every((item) => current.has(item.id)) ? new Set<string>() : new Set(visible.map((item) => item.id)))
  return (
    <main className="iu-content iu-fascicoli-page">
      <section className="iu-fas-hero iu-fas-hero--archive">
        <div><span className="iu-fas-eyebrow"><Archive size={16}/> Archivio</span><h1>Archivio Fascicoli</h1><p>Procedimenti definiti, archiviati, ZIP e possibilità di ripristino.</p></div>
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><FolderOpen size={15}/> Fascicoli attivi</Button><Button href="/fascicoli/esporta"><Download size={15}/> Esporta</Button></div>
      </section>
      <section className="iu-fas-stats"><StatCard icon={<Archive size={19}/>} label="Archiviati" value={data.summary.archived || data.items.length} note="in archivio" tone="neutral"/><StatCard icon={<FileArchive size={19}/>} label="ZIP" value={data.items.filter((item) => item.archive?.zipAvailable).length} note="archivi scaricabili" tone="primary"/><StatCard icon={<BadgeCheck size={19}/>} label="Esiti" value={data.items.filter((item) => item.archive?.outcome).length} note="con esito finale" tone="success"/></section>
      <section className="iu-fas-toolbar"><label className="iu-fas-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca per numero, titolo, cliente..."/></label></section>
      <section className="iu-fas-status-line"><span className={loading ? '' : 'is-ok'}>{loading ? 'Caricamento archivio...' : `Archivio aggiornato - ${data.source}`}</span><small><RotateCcw size={14}/> Il ripristino usa il servizio operativo con audit.</small></section>
      <FascicoliTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll} archive/>
      <FloatingLex context="archivio-fascicoli" title="Lex AI archivio" body="Posso aiutarti a controllare fascicoli archiviati, ZIP mancanti, esiti finali e criteri di conservazione." primaryHref="/lex?context=archivio-fascicoli" primaryLabel="Apri Lex archivio" secondaryHref="/fascicoli" secondaryLabel="Fascicoli attivi" />
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
  return (
    <main className="iu-content iu-fascicoli-page iu-fascicolo-form-page">
      <section className="iu-fas-hero">
        <div><span className="iu-fas-eyebrow">{mode === 'edit' ? <Edit3 size={16}/> : <FolderPlus size={16}/>} {mode === 'edit' ? 'Modifica fascicolo' : 'Nuovo fascicolo'}</span><h1>{mode === 'edit' ? getValue(data, 'title') || 'Modifica fascicolo' : 'Nuovo Fascicolo'}</h1><p>Dati processuali, parti, informazioni economiche, workflow e note operative.</p></div>
        <div className="iu-fas-hero__actions"><Button href={data.detailHref || data.backHref}><ArrowLeft size={15}/> {mode === 'edit' ? 'Fascicolo' : 'Fascicoli'}</Button></div>
      </section>
      {loading ? <p className="iu-empty">Caricamento dati fascicolo...</p> : null}
      {data.correction?.active ? <section className="iu-fas-correction"><Badge tone="primary">Correzione</Badge><div><strong>{data.correction.title}</strong><span>{data.correction.help}</span></div></section> : null}
      <section className="iu-fas-form-layout">
        <form className="iu-fas-form" method="post" action={data.action || (mode === 'edit' && id ? `/fascicoli/${encodeURIComponent(id)}/modifica` : '/fascicoli/nuovo')}>
          {mode === 'new' ? <><input type="hidden" name="source_preventivo" value={data.query.source_preventivo || ''}/><input type="hidden" name="source_conferimento" value={data.query.source_conferimento || ''}/><input type="hidden" name="from_page" value={data.query.from_page || ''}/></> : null}
          <Panel title="Dati principali" subtitle="Titolo, tipo e oggetto" icon={<FolderOpen size={17}/>}>
            <div className="iu-fas-form-grid"><Field label="Titolo" name="titolo" defaultValue={getValue(data, 'title')} required placeholder="es. Rossi c/ Bianchi - Inadempimento contrattuale"/><SelectField label="Tipo" name="tipo" options={data.types} defaultValue={getValue(data, 'typeRaw') || getValue(data, 'type').toUpperCase()} required/><TextAreaField label="Oggetto / Descrizione" name="oggetto" defaultValue={getValue(data, 'object') || getValue(data, 'subtitle')} rows={2}/></div>
          </Panel>
          <Panel title="Parti" subtitle="Cliente e controparte" icon={<UsersRound size={17}/>}>
            <div className="iu-fas-form-grid"><SelectField label="Cliente" name="id_cliente" options={[{ value: '', label: 'Seleziona cliente' }, ...data.clients.map((client) => ({ value: client.id, label: client.label }))]} defaultValue={getValue(data, 'clientId') || data.query.id_cliente || ''}/><Field label="Controparte" name="controparte" defaultValue={getValue(data, 'counterparty')} placeholder="Cerca per nome, C.F. o digita"/><a className="iu-fas-inline-link" href="/soggetti/nuovo" target="_blank" rel="noreferrer"><Plus size={14}/> Nuovo soggetto</a></div>
          </Panel>
          <Panel title="Dati del procedimento" subtitle="Ufficio giudiziario, RG, valore, udienze" icon={<Landmark size={17}/>}>
            <div className="iu-fas-form-grid"><Field label="Tribunale / ufficio" name="tribunale" defaultValue={getValue(data, 'court')}/><Field label="N. Registro Generale" name="numero_rg" defaultValue={getValue(data, 'numeroRg')}/><Field label="Anno iscrizione" name="anno_rg" type="number" defaultValue={getValue(data, 'annoRg') || new Date().getFullYear()}/><Field label="Sezione" name="sezione" defaultValue={getValue(data, 'section')}/><Field label="Giudice" name="giudice" defaultValue={getValue(data, 'judge')}/><Field label="Valore causa (EUR)" name="valore_causa" type="number" defaultValue={getValue(data, 'valueRaw') || getValue(data, 'value')} placeholder="0.00"/><Field label="Tipo procedimento" name="tipo_procedimento" defaultValue={getValue(data, 'procedureType')}/><Field label="Compenso pattuito (EUR)" name="compenso_pattuito" type="number" defaultValue={getValue(data, 'agreedFeeRaw') || getValue(data, 'agreedFee')} readOnly={Boolean(getValue(data, 'agreedFee'))}/><Field label="Valore preventivato (EUR)" name="valore_preventivato" type="number" defaultValue={getValue(data, 'quotedValueRaw') || getValue(data, 'quotedValue')} readOnly={Boolean(getValue(data, 'quotedValue'))}/><input type="hidden" name="id_pratica" value={getValue(data, 'practiceId')}/><input type="hidden" name="area_pratica" value={getValue(data, 'practiceArea')}/><Field label="Data prima udienza / comparizione" name="data_prima_udienza" type="date" defaultValue={getValue(data, 'firstHearingIso') || getValue(data, 'firstHearing')}/><Field label="Data notificazione citazione" name="data_notifica_citazione" type="date" defaultValue={getValue(data, 'citationNotificationIso') || getValue(data, 'citationNotification')}/></div>
          </Panel>
          <Panel title="Avvocati responsabili" subtitle="Referente, dominus e note" icon={<BriefcaseBusiness size={17}/>}>
            <div className="iu-fas-form-grid"><Field label="Avvocato referente" name="avvocato_referente" defaultValue={getValue(data, 'leadLawyer')}/><Field label="Avvocato dominus" name="avvocato_dominus" defaultValue={getValue(data, 'dominus')}/><TextAreaField label="Note" name="note" defaultValue={getValue(data, 'notes')} rows={4}/></div>
          </Panel>
          <div className="iu-fas-form-actions"><button className="iu-fas-submit" type="submit"><CheckCircle2 size={16}/> {mode === 'edit' ? 'Salva modifiche' : 'Crea fascicolo'}</button><a href={data.detailHref || data.backHref}>Annulla</a></div>
        </form>
        <aside className="iu-fas-form-side">
          <FascicoloGuardrailsPanel guardrails={data.guardrails} />
          {data.workflow ? <Panel title="Apertura pratica guidata" icon={<Sparkles size={17}/>}><div className="iu-fas-workflow-box"><div>{data.workflow.badges.map((badge) => <Badge tone="primary" key={badge}>{badge}</Badge>)}</div><p>{data.workflow.summary}</p>{data.workflow.values.map((item) => <span key={item.label}><strong>{item.label}</strong>{item.value}</span>)}<ul>{data.workflow.checklist.map((item) => <li key={item}>{item}</li>)}</ul></div></Panel> : null}
          <Panel title="Guida rapida" icon={<BadgeCheck size={17}/>}><div className="iu-fas-help"><p><strong>RG</strong>: numero assegnato dal tribunale all'iscrizione a ruolo.</p><p><strong>Sezione</strong>: sezione competente, utile per filtri e notifiche.</p><p><strong>Valore causa</strong>: alimenta compensi, dashboard economica e controllo incassi.</p></div></Panel>
          <Panel title="Prossimi passi" icon={<ListChecks size={17}/>}><div className="iu-fas-help"><p>Dopo il salvataggio potrai aggiungere documenti, scadenze processuali, attività, depositi telematici e note.</p></div></Panel>
        </aside>
      </section>
      <FloatingLex context="fascicolo-form" title="Lex AI fascicolo" body="Posso aiutarti a completare oggetto, tipo procedimento, checklist iniziale, scadenze e dati mancanti prima della creazione o modifica." primaryHref="/lex?context=fascicolo-form" primaryLabel="Apri Lex" secondaryHref="/fascicoli" secondaryLabel="Torna ai fascicoli" />
    </main>
  )
}

function KvGrid({ items }:{items:KeyValue[]}) {
  return <div className="iu-fas-kv-grid">{items.map((item) => <div key={`${item.label}-${item.value}`}><span>{item.label}</span>{item.href ? <a href={item.href} className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</a> : <strong className={item.mono ? 'mono' : ''}>{item.value || 'n.d.'}</strong>}</div>)}</div>
}

function DetailSection({ id, title, icon, count, children }:{id:string; title:string; icon:ReactNode; count?:number; children:ReactNode}) {
  return (
    <details id={id} className="iu-fas-detail-section">
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

function DocumentRow({ doc }:{doc:FascicoloDocument}) {
  return (
    <article className="iu-fas-doc-row">
      <div><FileText size={18}/></div>
      <div><strong>{doc.name}</strong><span>{doc.type} · {doc.size || 'dimensione n.d.'} · {doc.documentDate || doc.uploadedAt || 'data n.d.'}</span>{doc.notes ? <p>{doc.notes}</p> : null}{doc.tags.length ? <em>{doc.tags.join(', ')}</em> : null}</div>
      <div className="iu-fas-doc-badges"><Badge tone={doc.statusTone}>{doc.statusLabel || (doc.signed ? 'Firmato' : 'Da firmare')}</Badge>{doc.source ? <Badge tone="neutral">{doc.source}</Badge> : null}{doc.portalClass ? <Badge tone="info">{doc.portalClass}</Badge> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {doc.actions.preview ? <a href={doc.actions.preview} title="Anteprima"><Eye size={15}/></a> : null}
        {doc.actions.download ? <a href={doc.actions.download} title="Scarica"><Download size={15}/></a> : null}
        {doc.actions.edit ? <a href={doc.actions.edit} title="Editor"><PencilLine size={15}/></a> : null}
        {doc.actions.sign ? <a href={doc.actions.sign} title="Firma"><Edit3 size={15}/></a> : null}
        {doc.actions.attest ? <PostAction action={doc.actions.attest} tone="secondary"><BadgeCheck size={14}/></PostAction> : null}
        {doc.actions.pdfa ? <PostAction action={doc.actions.pdfa} tone="secondary" confirm="Convertire il documento in PDF/A-2B?"><FileCheck2 size={14}/></PostAction> : null}
        {doc.actions.delete ? <PostAction action={doc.actions.delete} tone="danger" confirm="Eliminare il documento dal fascicolo?"><Trash2 size={14}/></PostAction> : null}
      </div>
    </article>
  )
}

type LocalSignerToken = { slot_id?: number | string; label?: string; manufacturer?: string }
type LocalSignerStatus = { ok?: boolean; token?: LocalSignerToken[]; versione?: string; version?: string; messaggio?: string; error?: string }
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

function SignaturePage({ id, documentId }:{id:string; documentId:string}) {
  const [data, setData] = useState<FascicoloDetailData>(emptyFascicoloDetail)
  const [loading, setLoading] = useState(true)
  const [info, setInfo] = useState<FirmaInfo | null>(null)
  const [localSigner, setLocalSigner] = useState<LocalSignerStatus | null>(null)
  const [checkingSigner, setCheckingSigner] = useState(false)
  const [pin, setPin] = useState('')
  const [confirmResign, setConfirmResign] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const encodedId = encodeURIComponent(id)
  const encodedDocId = encodeURIComponent(documentId)
  const firmaUrl = `/fascicoli/${encodedId}/documenti/${encodedDocId}/firma`
  const infoUrl = `/api/fascicoli/${encodedId}/documenti/${encodedDocId}/info-firma`
  const detailUrl = `/fascicoli/${encodedId}#documenti`
  const doc = data.documents.find((item) => item.id === documentId)
  const token = localSigner?.token?.[0]
  const signatureCount = info?.firme?.length || 0
  const alreadySigned = Boolean(doc?.signed || signatureCount > 0 || doc?.name.toLowerCase().match(/\.(p7m|sig|pkcs7)$/))

  const refreshInfo = () => {
    fetch(infoUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((response) => response.json())
      .then((payload) => setInfo(payload as FirmaInfo))
      .catch(() => setInfo({ errore: 'Stato firma non disponibile.' }))
  }

  const checkLocalSigner = () => {
    setCheckingSigner(true)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 2500)
    fetch('http://127.0.0.1:27272/ping', { signal: controller.signal })
      .then((response) => response.json())
      .then((payload) => setLocalSigner(payload as LocalSignerStatus))
      .catch(() => setLocalSigner({ ok: false, messaggio: 'Local Signer non rilevato su questo PC.' }))
      .finally(() => {
        window.clearTimeout(timeout)
        setCheckingSigner(false)
      })
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getFascicoloDetail(id).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  useEffect(() => {
    refreshInfo()
    checkLocalSigner()
  }, [infoUrl])

  const firmaConLocalSigner = async () => {
    if (!doc) return
    if (!token?.slot_id && token?.slot_id !== 0) {
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
      const signResponse = await fetch('http://127.0.0.1:27272/firma', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          documento: arrayBufferToBase64(sourceBuffer),
          pin,
          slot_id: token.slot_id,
          visible_signature_mode: 'nessuna',
          visible_signature_place: '',
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
      getFascicoloDetail(id).then(setData)
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

        <Panel title="Firma con Local Signer" subtitle="Controllo e firma sul PC dell'avvocato" icon={<ShieldCheck size={17}/>} action={<button className="iu-fas-mini-action" type="button" onClick={checkLocalSigner} disabled={checkingSigner}><RefreshCw size={14}/> Riverifica</button>}>
          <div className="iu-fas-signature-box">
            <div className={`iu-fas-signer-status ${token ? 'is-ok' : 'is-warn'}`}>
              <strong>{token ? 'Local Signer rilevato' : checkingSigner ? 'Verifica Local Signer...' : 'Local Signer non rilevato'}</strong>
              <span>{token ? `${token.label || token.manufacturer || 'Token USB'} - slot ${token.slot_id}` : localSigner?.messaggio || localSigner?.error || 'Avvia Local Signer sul PC e riprova.'}</span>
              {localSigner?.versione || localSigner?.version ? <small>Versione {localSigner.versione || localSigner.version}</small> : null}
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
            <button className="iu-fas-submit" type="button" disabled={busy || !token || (alreadySigned && !confirmResign)} onClick={firmaConLocalSigner}>
              <ShieldCheck size={16}/> {busy ? 'Firma in corso...' : 'Firma tramite Local Signer'}
            </button>
            <p className="iu-fas-signature-help">La firma integrata passa da <code>127.0.0.1:27272</code>. IUSENTRA non salva PIN, password o credenziali del token.</p>
          </div>
        </Panel>

        <Panel title="Firma esterna" subtitle="ArubaSign, Dike o altro software di firma" icon={<UploadCloud size={17}/>}>
          <form className="iu-fas-signature-form" method="post" action={firmaUrl} encType="multipart/form-data">
            <p>Scarica il documento, firmalo in CAdES/PAdES secondo la policy del canale, poi carica qui il file firmato.</p>
            <label className="iu-fas-field">
              <span>File firmato <b>*</b></span>
              <input type="file" name="file" accept=".p7m,.sig,.pkcs7,.pdf" required/>
            </label>
            <label className="iu-fas-field">
              <span>Note operative</span>
              <input type="text" name="note" defaultValue="Versione firmata per deposito"/>
            </label>
            {alreadySigned ? (
              <label className="iu-fas-resign-confirm">
                <input type="checkbox" checked={confirmResign} onChange={(event) => setConfirmResign(event.target.checked)}/>
                <span>Ho verificato che il documento è già firmato e autorizzo una nuova firma/sostituzione del file.</span>
              </label>
            ) : null}
            {alreadySigned && confirmResign ? <input type="hidden" name="confirm_resign" value="1"/> : null}
            <button className="iu-fas-submit" type="submit" disabled={alreadySigned && !confirmResign}><UploadCloud size={16}/> Carica file firmato</button>
          </form>
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
      <FloatingLex context="firma-documento" title="Lex AI firma" body="Posso spiegare differenze tra CAdES, PAdES, firma locale e controlli predeposito, senza sostituire la verifica tecnica." primaryHref={`/lex?context=firma-documento&id_fasc=${encodedId}&id_doc=${encodedDocId}`} primaryLabel="Chiedi a Lex" secondaryHref={detailUrl} secondaryLabel="Torna ai documenti" />
    </main>
  )
}

function ActivityRow({ activity }:{activity:FascicoloActivity}) {
  return (
    <article className="iu-fas-activity-row">
      <div><Badge tone={activity.tone}>{activity.result || activity.type}</Badge><time>{activity.date || 'n.d.'}</time></div>
      <div><strong>{activity.title}</strong><span>{activity.type}{activity.place ? ` · ${activity.place}` : ''}{activity.lawyer ? ` · ${activity.lawyer}` : ''}</span>{activity.description ? <p>{activity.description}</p> : null}{activity.notes ? <em>{activity.notes}</em> : null}</div>
      <div className="iu-fas-actions iu-fas-actions--wrap">
        {activity.updateAction ? <form method="post" action={activity.updateAction} className="iu-fas-mini-form"><select name="esito" defaultValue={activity.result || 'IN_ATTESA'}><option value="IN_ATTESA">In attesa</option><option value="FAVOREVOLE">Favorevole</option><option value="PARZIALE">Parziale</option><option value="SFAVOREVOLE">Sfavorevole</option><option value="RINVIATO">Rinviato</option><option value="ANNULLATO">Annullato</option></select><button type="submit">Aggiorna</button></form> : null}
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
  useEffect(() => { let active = true; getFascicoloDetail(id).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [id])
  const f = data.fascicolo
  const operationalHref = f.operationalHref || `/fascicoli/${encodeURIComponent(f.id || id)}`
  const quadroHref = `/fascicoli/${encodeURIComponent(f.id || id)}/quadro`
  const detailReturnHref = `/fascicoli/${encodeURIComponent(f.id || id)}#conformita`
  const signedDocuments = data.documents.filter((doc) => doc.signed).length
  const unsignedDocuments = Math.max(0, data.documents.length - signedDocuments)
  const qualityIssues = data.quality.filter((item) => !item.ok).length + (Number(f.alerts) || 0)
  const nextDeadline = data.deadlines[0]
  const nextAppointment = data.appointments[0]
  const preventivo = data.workflow.find((item) => /preventiv/i.test(item.label))
  const conferimento = data.workflow.find((item) => /conferiment|incaric/i.test(item.label))
  const prossimaAzione = nextDeadline?.title || nextAppointment?.title || (qualityIssues ? 'Controlli qualità da verificare' : 'Nessuna urgenza critica rilevata')
  if (!loading && data.notFound) return <main className="iu-content iu-fascicoli-page"><EmptyState icon={<FolderOpen size={34}/>} title="Fascicolo non trovato" action={<Button href="/fascicoli">Torna ai fascicoli</Button>}>Il fascicolo non è disponibile o non hai i permessi per aprirlo.</EmptyState></main>
  return (
    <main id="fascicolo-top" className="iu-content iu-fascicoli-page iu-fascicolo-detail-page">
      <section className="iu-fas-hero iu-fas-detail-hero">
        <div><span className="iu-fas-eyebrow"><FolderOpen size={16}/> Fascicolo</span><h1>{f.title}</h1><p><Badge tone={f.tone}>{formatFascicoloStatus(f.status)}</Badge><Badge tone="neutral">{formatFascicoloType(f.type)}</Badge>{f.archiveReady ? <Badge tone="warning">Pronto per archivio</Badge> : null}<span>{f.object || f.subtitle}</span></p></div>
        <div className="iu-fas-hero__actions"><Button href="/fascicoli"><ArrowLeft size={15}/> Fascicoli</Button><Button href={f.editHref}><Edit3 size={15}/> Modifica</Button><Button href={quadroHref}><Gauge size={15}/> Quadro</Button><Button href={`${operationalHref}/copertina`}><FileText size={15}/> Copertina</Button><Button variant="primary" href={data.actions.exportPdf || f.exportPdfHref}><FileDown size={15}/> PDF</Button></div>
      </section>
      <section className="iu-fas-case-strip"><strong>{f.ref}</strong><span>Rif. interno {f.internalRef}</span><span>{f.client}</span><span>{f.court}</span><span>{loading ? 'Caricamento...' : 'Dati aggiornati'}</span></section>
      <nav className="iu-fas-section-nav" aria-label="Sezioni fascicolo"><a href="#profilo">Profilo <b>{data.quickCounts.profilo || 0}</b></a><a href="#documenti">Documenti <b>{data.documents.length}</b></a><a href="#attivita">Attività <b>{data.activities.length}</b></a><a href="#udienze">Udienze / scadenze <b>{data.deadlines.length + data.appointments.length}</b></a><a href="#cancelleria">Cancelleria <b>{data.deposits.length}</b></a><a href="#istanze">Istanze <b>{data.requests.length}</b></a><a href="#gestione">Gestione</a><a href="#economia">Economia</a><a href="#conformita">Conformità</a><a href="#soggetti">Soggetti <b>{data.parties.length}</b></a></nav>
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
          <section className="iu-fas-cockpit"><StatCard icon={<FileText size={19}/>} label="Documenti" value={data.documents.length} note="acquisiti o da portale" tone="primary" href="#documenti"/><StatCard icon={<CalendarDays size={19}/>} label="Scadenze" value={data.deadlines.length} note="aperte e concluse" tone="warning" href="#udienze"/><StatCard icon={<ListChecks size={19}/>} label="Attività" value={data.activities.length} note="timeline processuale" tone="success" href="#attivita"/><StatCard icon={<WalletCards size={19}/>} label="Economia" value={data.economics.length} note="preventivi, parcelle, tempo" tone="purple" href="#economia"/></section>
          <DetailSection id="profilo" title="Profilo fascicolo" icon={<BadgeCheck size={17}/>}><KvGrid items={data.profile}/>{f.notes ? <div className="iu-fas-note"><strong>Note</strong><p>{f.notes}</p></div> : null}</DetailSection>
          <DetailSection id="documenti" title="Documenti fascicolo" icon={<FileText size={17}/>} count={data.documents.length}>
            <form className="iu-fas-upload" method="post" action={data.actions.uploadDocument} encType="multipart/form-data"><input type="file" name="file"/><select name="tipo_doc" defaultValue="ALTRO">{data.options.documentTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input type="date" name="data_documento"/><input name="tags" placeholder="tag separati da virgola"/><input name="note" placeholder="note documento"/><label><input type="checkbox" name="firmato" value="1"/> Firmato</label><button type="submit"><UploadCloud size={15}/> Carica</button></form>
            <form className="iu-fas-upload iu-fas-upload--portal" method="post" action={data.actions.importPortal} encType="multipart/form-data"><input type="file" name="files" multiple/><input name="note_importazione" placeholder="note importazione portale"/><label><input type="checkbox" name="mantieni_albero_originale" value="1"/> Mantieni albero originale</label><label><input type="checkbox" name="scarica_originale_portale" value="1"/> Originale portale</label><button type="submit"><Download size={15}/> Importa portale</button></form>
            <div className="iu-fas-doc-list">{data.documents.map((doc) => <DocumentRow doc={doc} key={doc.id}/>)}{!data.documents.length ? <p className="iu-empty">Nessun documento caricato.</p> : null}</div>
          </DetailSection>
          <DetailSection id="attivita" title="Attività processuali" icon={<ListChecks size={17}/>} count={data.activities.length}>
            <form className="iu-fas-add-activity" method="post" action={data.actions.addActivity}><select name="tipo" defaultValue="ALTRO">{data.options.activityTypes.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input type="date" name="data" required/><input name="titolo" placeholder="Titolo attività" required/><input name="luogo" placeholder="Luogo"/><select name="esito" defaultValue="IN_ATTESA">{data.options.activityResults.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select><input name="avvocato" placeholder="Avvocato"/><textarea name="descrizione" placeholder="Descrizione"/><button type="submit"><Plus size={15}/> Aggiungi</button></form>
            <div className="iu-fas-activity-list">{data.activities.map((activity) => <ActivityRow activity={activity} key={activity.id}/>)}{!data.activities.length ? <p className="iu-empty">Nessuna attività processuale registrata.</p> : null}</div>
          </DetailSection>
          <DetailSection id="udienze" title="Udienze e scadenze" icon={<CalendarDays size={17}/>} count={data.deadlines.length + data.appointments.length}>
            <div className="iu-fas-two-cols"><div><h3>Scadenze</h3>{data.deadlines.map((deadline) => <DeadlineRow deadline={deadline} key={deadline.id}/>)}{!data.deadlines.length ? <p className="iu-empty">Nessuna scadenza collegata.</p> : null}<a className="iu-fas-inline-link" href={`/scadenziario/nuova?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuova scadenza</a></div><div><h3>Agenda</h3>{data.appointments.map((app) => <a className="iu-fas-deadline-row" href={app.href} key={app.id}><Badge tone={app.tone}>{app.type || 'agenda'}</Badge><strong>{app.title}</strong><span>{app.date} {app.time} {app.place}</span></a>)}{!data.appointments.length ? <p className="iu-empty">Nessun appuntamento trovato.</p> : null}<a className="iu-fas-inline-link" href={`/agenda/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo appuntamento</a></div></div>
          </DetailSection>
          <DetailSection id="cancelleria" title="Comunicazioni, depositi e catalogo portale" icon={<Mail size={17}/>} count={data.deposits.length}>
            <div className="iu-fas-deposit-list">{data.deposits.map((dep) => <article className="iu-fas-deposit" key={dep.id}><header><Badge tone={dep.tone}>{dep.status}</Badge><strong>{dep.actType || 'Deposito'}</strong><span>{dep.timestamp}</span></header><p>{dep.message || dep.pec}</p><div><span>Controlli: {dep.checks || 'n.d.'}</span><span>Fonte: {dep.source || 'locale'}</span><span>Documenti: {dep.documentsCount}</span></div>{dep.portalDocuments.length ? <ul>{dep.portalDocuments.map((doc) => <li key={`${dep.id}-${doc.name}`}>{doc.name} · {doc.type} · {doc.imported ? 'acquisito' : 'da acquisire'}</li>)}</ul> : null}</article>)}{!data.deposits.length ? <p className="iu-empty">Nessun deposito o documento portale censito.</p> : null}</div>
          </DetailSection>
          <DetailSection id="istanze" title="Istanze e atti collegati" icon={<ClipboardCheck size={17}/>} count={data.requests.length}>{data.requests.map((activity) => <ActivityRow activity={activity} key={activity.id}/>)}{!data.requests.length ? <p className="iu-empty">Nessuna istanza separata rilevata.</p> : null}</DetailSection>
          <DetailSection id="avanzamento" title="Avanzamento pratica" icon={<Clock3 size={17}/>} count={data.history.length}><div className="iu-fas-timeline">{data.history.map((item) => <article key={`${item.date}-${item.description}`}><time>{item.date}</time><strong>{item.description}</strong><span>{item.from} → {item.to}</span><p>{item.notes}</p></article>)}{!data.history.length ? <p className="iu-empty">Nessun avanzamento registrato.</p> : null}</div></DetailSection>
        </div>
        <aside className="iu-fas-detail-side">
          <DetailSection id="gestione" title="Gestione fascicolo" icon={<Gauge size={17}/>}>
            <form className="iu-fas-side-form" method="post" action={data.actions.changeState}><label><span>Cambia stato</span><select name="stato" defaultValue={f.status.toUpperCase()}>{data.options.states.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note cambio stato"/><button type="submit"><RefreshCw size={15}/> Aggiorna stato</button></form>
            <div className="iu-fas-action-stack"><form method="post" action={data.actions.define}><input name="esito_finale" placeholder="Esito finale"/><input name="motivo" placeholder="Motivo"/><input name="avvocato" placeholder="Avvocato"/><textarea name="note" placeholder="Note definizione"/><button type="submit"><CheckCircle2 size={15}/> Definisci</button></form><PostAction action={data.actions.archive} tone="primary" confirm="Archiviare il fascicolo?"><Archive size={15}/> Archivia con ZIP</PostAction><PostAction action={data.actions.restore} tone="secondary" confirm="Ripristinare il fascicolo?"><RotateCcw size={15}/> Ripristina</PostAction><a className="iu-fas-side-link" href={data.actions.exportPdf || f.exportPdfHref}><FileDown size={15}/> PDF fascicolo</a>{data.actions.archiveZip ? <a className="iu-fas-side-link" href={data.actions.archiveZip}><FileArchive size={15}/> Scarica ZIP</a> : null}<PostAction action={data.actions.delete} tone="danger" confirm="Eliminare definitivamente il fascicolo?"><Trash2 size={15}/> Elimina</PostAction></div>
          </DetailSection>
          <DetailSection id="economia" title="Controllo economico" icon={<WalletCards size={17}/>} count={data.economics.length}><div className="iu-fas-side-cards">{data.economics.map((item) => <a href={item.href} key={item.id}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}{!data.economics.length ? <p className="iu-empty">Nessun dato economico collegato.</p> : null}</div></DetailSection>
          <DetailSection id="workflow" title="Workflow cliente → incasso" icon={<Sparkles size={17}/>} count={data.workflow.length}><div className="iu-fas-side-cards">{data.workflow.map((item) => <a href={item.href || '#'} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}</div></DetailSection>
          <DetailSection id="conformita" title="Conformità e qualità" icon={<ShieldCheck size={17}/>} count={data.quality.length}><div className="iu-fas-quality-list">{data.quality.map((item) => <span key={item.label}><Badge tone={item.tone}>{item.ok ? 'OK' : 'Verifica'}</Badge><strong>{item.label}</strong><small>{item.value}</small></span>)}</div><form className={`iu-fas-compliance-toggle ${f.complianceControlsEnabled ? 'is-on' : 'is-off'}`} method="post" action={f.complianceControlsEnabled ? data.actions.complianceOff : data.actions.complianceOn}><input type="hidden" name="enabled" value={f.complianceControlsEnabled ? '0' : '1'}/><input type="hidden" name="next" value={detailReturnHref}/><button type="submit" aria-pressed={f.complianceControlsEnabled}><span className="iu-fas-compliance-toggle__switch" aria-hidden="true"><i/></span><span><strong>{f.complianceControlsEnabled ? 'Controlli automatici attivi' : 'Controlli automatici disattivati'}</strong><small>{f.complianceControlsEnabled ? 'Disattiva i controlli qualità sul fascicolo' : 'Riattiva i controlli qualità sul fascicolo'}</small></span></button></form></DetailSection>
          <DetailSection id="telematico" title="Servizi telematici" icon={<Send size={17}/>} count={data.telematic.length}><div className="iu-fas-side-cards">{data.telematic.map((item) => <a href={item.href} key={item.label}><Badge tone={item.tone}>{item.label}</Badge><strong>{item.value}</strong><span>{item.note}</span></a>)}</div></DetailSection>
          <DetailSection id="cliente" title="Cliente" icon={<UserRound size={17}/>} count={data.client ? 1 : 0}>{data.client ? <KvGrid items={[{ label: 'Nome', value: data.client.name, href: data.client.href }, { label: 'Codice fiscale', value: data.client.taxCode, mono: true }, { label: 'P. IVA', value: data.client.vat, mono: true }, { label: 'Email', value: data.client.email }, { label: 'PEC', value: data.client.pec }, { label: 'Telefono', value: data.client.phone }, { label: 'Indirizzo', value: data.client.address }]}/> : <p className="iu-empty">Cliente non collegato.</p>}</DetailSection>
          <DetailSection id="soggetti" title="Soggetti e parti" icon={<UsersRound size={17}/>} count={data.parties.length}><div className="iu-fas-party-list">{data.parties.map((party) => <a href={party.href} key={party.id}><strong>{party.name}</strong><span>{party.role || 'Soggetto'} · {party.taxCode || 'C.F. n.d.'}</span><small>{party.email || party.pec || party.phone}</small></a>)}{!data.parties.length ? <p className="iu-empty">Nessun soggetto collegato.</p> : null}</div><a className="iu-fas-inline-link" href={`/soggetti/nuovo?id_fascicolo=${encodeURIComponent(f.id)}`}><Plus size={14}/> Nuovo soggetto</a></DetailSection>
        </aside>
      </section>
      <a className="iu-fas-back-top" href="#fascicolo-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex context="fascicolo-dettaglio" title="Lex AI fascicolo" body="Posso sintetizzare profilo, documenti, attività, scadenze, depositi, parti e prossime azioni del fascicolo aperto." primaryHref={`/lex?context=fascicolo&id_fasc=${encodeURIComponent(f.id)}`} primaryLabel="Apri Lex sul fascicolo" secondaryHref={`/global-search?q=${encodeURIComponent(f.ref)}`} secondaryLabel="Cerca collegati" />
    </main>
  )
}

function moneyFrom(data: FascicoloDetailData, id: string, fallback = 'EUR 0,00') {
  return data.economics.find((item) => item.id === id)?.value || fallback
}

function workflowFrom(data: FascicoloDetailData, matcher: RegExp, fallbackLabel: string) {
  return data.workflow.find((item) => matcher.test(item.label)) || { label: fallbackLabel, value: 'Non collegato', note: 'Collega la fase operativa auditata quando serve.', tone: 'neutral' as const, href: '#' }
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
  useEffect(() => { let active = true; getFascicoloDetail(id).then((payload) => { if (active) setData(payload) }).finally(() => { if (active) setLoading(false) }); return () => { active = false } }, [id])
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
        <QuadroAxis id="economico" title="Economico" icon={<WalletCards size={18}/>} status={parcelle === 'EUR 0,00' ? 'Da valorizzare' : 'Valorizzato'} tone={parcelle === 'EUR 0,00' ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Valore causa" value={valore} note="profilo fascicolo" tone="primary" href={`${detailHref}#profilo`}/><QuadroMiniCard label="Parcelle" value={parcelle} note="documenti economici collegati" tone="success" href="/fatturazione/"/><QuadroMiniCard label="Tempo" value={tempo} note="voci timesheet valorizzabili" tone="info" href="/timesheet"/></div></QuadroAxis>
        <QuadroAxis id="documenti" title="Documenti" icon={<FileText size={18}/>} status={unsignedDocuments ? `${unsignedDocuments} da firmare` : 'Completi'} tone={unsignedDocuments ? 'warning' : 'success'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.documents.length} note="documenti fascicolo" tone="primary" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Firmati" value={signedDocuments} note="depositabili / verificati" tone="success" href={`${detailHref}#documenti`}/><QuadroMiniCard label="Da firmare" value={unsignedDocuments} note="controllo operativo" tone={unsignedDocuments ? 'warning' : 'success'} href={`${detailHref}#documenti`}/></div></QuadroAxis>
        <QuadroAxis id="soggetti" title="Soggetti e parti" icon={<UsersRound size={18}/>} status={data.parties.length ? `${data.parties.length} collegati` : 'Da verificare'} tone={data.parties.length ? 'success' : 'warning'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Totale" value={data.parties.length} note="assistiti, controparti e ruoli" tone={data.parties.length ? 'success' : 'warning'} href={`${detailHref}#soggetti`}/><QuadroMiniCard label="Cliente" value={data.client?.name || f.client || 'n.d.'} note="assistito principale" tone="primary" href={data.client?.href || `${detailHref}#profilo`}/><QuadroMiniCard label="Controparte" value={f.counterparty || 'n.d.'} note="dato fascicolo o parte strutturata" tone={f.counterparty ? 'orange' : 'neutral'} href={`${detailHref}#soggetti`}/></div></QuadroAxis>
        <QuadroAxis id="cancelleria" title="Cancelleria e istanze" icon={<Gavel size={18}/>} status={data.deposits.length ? `${data.deposits.length} depositi` : 'Nessun deposito'} tone={data.deposits.length ? 'purple' : 'neutral'}><div className="iu-fas-quadro-flow"><QuadroMiniCard label="Depositi" value={data.deposits.length} note={data.deposits[0]?.status || 'nessun deposito registrato'} tone="purple" href={`${detailHref}#cancelleria`}/><QuadroMiniCard label="Istanze" value={data.requests.length} note="atti e richieste operative" tone={data.requests.length ? 'primary' : 'neutral'} href={`${detailHref}#istanze`}/><QuadroMiniCard label="Storico" value={data.history.length} note="transizioni e stati fascicolo" tone="info" href={`${detailHref}#gestione`}/></div></QuadroAxis>
        <QuadroAxis id="telematico" title="Servizi telematici" icon={<Send size={18}/>} status={data.telematic.length ? 'Presidiati' : 'Da configurare'} tone={data.telematic.length ? 'primary' : 'warning'}><div className="iu-fas-quadro-flow">{data.telematic.slice(0, 3).map((item) => <QuadroMiniCard key={item.label} label={item.label} value={item.value} note={item.note} tone={item.tone} href={item.href}/>)}</div><a className="iu-fas-inline-link" href="/telematico"><Send size={14}/> Apri servizi telematici</a></QuadroAxis>
      </section>
      <a className="iu-fas-back-top" href="#fascicolo-quadro-top" aria-label="Torna su" title="Torna su"><ChevronUp size={18}/></a>
      <FloatingLex context="fascicolo-quadro" title="Lex AI quadro" body="Posso leggere il quadro della pratica, riassumere commerciale, operativo, conformità, economico e documenti, e suggerire la prossima azione utile." primaryHref={`/lex?context=fascicolo-quadro&id_fasc=${encodedId}`} primaryLabel="Apri Lex sul quadro" secondaryHref={detailHref} secondaryLabel="Apri dettaglio" />
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
      <section className="iu-fas-hero"><div><span className="iu-fas-eyebrow"><Download size={16}/> Esporta</span><h1>Esporta fascicoli</h1><p>PDF lista, CSV operativo, PDF fascicolo singolo e ZIP archivio, usando servizi già auditati.</p></div><div className="iu-fas-hero__actions"><Button href="/fascicoli"><FolderOpen size={15}/> Fascicoli</Button><Button href="/fascicoli/archivio"><Archive size={15}/> Archivio</Button></div></section>
      <section className="iu-fas-stats"><StatCard icon={<FolderOpen size={19}/>} label="Totali" value={data.summary.total} note="nel repository" tone="primary"/><StatCard icon={<Archive size={19}/>} label="Archiviati" value={data.summary.archived} note="da conservare" tone="neutral"/><StatCard icon={<FileText size={19}/>} label="Documenti" value={data.summary.documents} note="conteggio fascicoli" tone="purple"/></section>
      <section className="iu-fas-export-layout"><Panel title="Builder export" subtitle={loading ? 'Caricamento...' : `Sorgente ${data.source}`} icon={<FileDown size={17}/>}><div className="iu-fas-export-builder"><label><span>Formato</span><select value={format} onChange={(event) => setFormat(event.target.value)}><option value="pdf">PDF lista</option><option value="csv">CSV</option></select></label><label><span>Ricerca</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="numero, titolo, cliente..."/></label><label><span>Tipo</span><select value={type} onChange={(event) => setType(event.target.value as FascicoloTipo)}>{data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label}</option>)}</select></label><label><span>Stato</span><select value={status} onChange={(event) => setStatus(event.target.value as FascicoloStato)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label}</option>)}</select></label><a className="iu-fas-download-main" href={href}><Download size={16}/> Scarica export</a></div></Panel><Panel title="Campi inclusi" icon={<ListChecks size={17}/>}><div className="iu-fas-export-fields">{data.fields.map((field) => <label key={field.key}><input type="checkbox" defaultChecked={field.checked} readOnly/> {field.label}</label>)}</div></Panel><Panel title="Preset rapidi" icon={<Sparkles size={17}/>}><div className="iu-fas-side-cards">{data.presets.map((preset) => <a href={preset.href} key={preset.label}><Badge tone={preset.tone}>{preset.label}</Badge><span>{preset.description}</span></a>)}</div></Panel></section>
      <Panel title="Fascicoli recenti esportabili singolarmente" icon={<FolderOpen size={17}/>} count={data.recent.length}><div className="iu-fas-export-recent">{data.recent.map((item) => <a href={item.exportPdfHref} key={item.id}><FileDown size={15}/><strong>{item.ref}</strong><span>{item.title}</span></a>)}</div></Panel>
      <FloatingLex context="export-fascicoli" title="Lex AI export" body="Posso suggerire quali campi esportare, preparare una sintesi per il cliente o controllare se mancano dati prima dell'archiviazione." primaryHref="/lex?context=export-fascicoli" primaryLabel="Apri Lex export" secondaryHref="/fascicoli" secondaryLabel="Torna ai fascicoli" />
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
