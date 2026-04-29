import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Archive,
  Bell,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Download,
  Eye,
  FileCheck2,
  FileText,
  Filter,
  FolderOpen,
  FolderPlus,
  Gauge,
  Landmark,
  PencilLine,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyFascicoliPage,
  formatFascicoloStatus,
  formatFascicoloType,
  getFascicoliPage,
  type FascicoloRow,
  type FascicoloStato,
  type FascicoloTipo,
  type FascicoliPageData,
} from '../fascicoliData'
import './FascicoliPage.css'

type SortKey = 'recenti' | 'rg' | 'cliente' | 'scadenza' | 'documenti'

const sortLabels: Record<SortKey, string> = {
  recenti: 'Aggiornati di recente',
  rg: 'Numero RG',
  cliente: 'Cliente',
  scadenza: 'Prossima scadenza',
  documenti: 'Documenti',
}

function StatCard({ icon, label, value, note, tone = 'primary' }:{icon:ReactNode; label:string; value:number|string; note:string; tone?:FascicoloRow['tone']}) {
  return (
    <article className={`iu-fas-stat iu-fas-stat--${tone}`}>
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
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
  return copy
}

function RowActions({ item }:{item:FascicoloRow}) {
  return (
    <div className="iu-fas-actions" aria-label={`Azioni fascicolo ${item.ref}`}>
      <a href={item.href} aria-label="Apri fascicolo"><Eye size={15}/></a>
      <a href={item.editHref} aria-label="Modifica fascicolo"><PencilLine size={15}/></a>
    </div>
  )
}

function DossierMobileCard({ item, checked, onToggle }:{item:FascicoloRow; checked:boolean; onToggle:()=>void}) {
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
        <div><dt>Prossima scad.</dt><dd>{item.nextDeadline || 'n.d.'}</dd></div>
      </dl>
      <footer>
        <span><FileText size={14}/> {item.documents}</span>
        {item.unreadCommunications ? <span><Bell size={14}/> {item.unreadCommunications}</span> : null}
        {item.alerts ? <span><ShieldCheck size={14}/> {item.alerts}</span> : null}
        <RowActions item={item}/>
      </footer>
    </article>
  )
}

function FascicoliTable({ items, selected, onToggle, onToggleAll }:{items:FascicoloRow[]; selected:Set<string>; onToggle:(id:string)=>void; onToggleAll:()=>void}) {
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  return (
    <section className="iu-fas-table-card" aria-label="Elenco fascicoli">
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
              <th>Prossima scad.</th>
              <th>Stato</th>
              <th>Doc.</th>
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
                <td>{item.nextDeadline || 'n.d.'}</td>
                <td><Badge tone={item.tone}>{formatFascicoloStatus(item.status)}</Badge></td>
                <td><span className="iu-fas-doc-count">{item.documents}</span></td>
                <td><RowActions item={item}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="iu-fas-mobile-list">
        {items.map((item) => <DossierMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} key={item.id}/>) }
      </div>
      {!items.length ? <p className="iu-empty">Nessun fascicolo corrisponde ai filtri impostati.</p> : null}
    </section>
  )
}

function InsightPanel({ data, visible }:{data:FascicoliPageData; visible:FascicoloRow[]}) {
  const urgent = visible.filter((item) => item.alerts > 0 || item.unreadCommunications > 0).slice(0, 3)
  const withoutDeadline = visible.filter((item) => item.status !== 'archiviato' && !item.nextDeadlineIso && item.nextDeadline === 'n.d.').length
  return (
    <aside className="iu-fas-insights">
      <Panel title="Cabina fascicoli" subtitle="Controlli che conviene avere subito" icon={<Gauge size={17}/>}>
        <div className="iu-fas-briefing">
          <article>
            <span>Da governare ora</span>
            <strong>{data.summary.deadlines30} scadenze nei prossimi 30 giorni</strong>
            <small>Il dato resta in sola lettura e deriva dal bridge backend.</small>
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
          <a href="/scadenziario/nuova"><CalendarDays size={15}/> Nuova scadenza</a>
          <a href="/redazione-atti"><FileCheck2 size={15}/> Redazione atti</a>
          <a href="/fascicoli/archivio"><Archive size={15}/> Vai all'archivio</a>
          <a href="/lex?context=fascicoli"><Sparkles size={15}/> Chiedi a Lex</a>
        </div>
      </Panel>
    </aside>
  )
}

export function FascicoliPage() {
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
    getFascicoliPage().then((payload) => {
      if (active) setData(payload)
    }).finally(() => {
      if (active) setLoading(false)
    })
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
  const toggle = (id: string) => setSelected((current) => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
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
          <p>Procedimenti civili, penali e amministrativi con scadenze, documenti, clienti e prossime azioni in una vista professionale.</p>
        </div>
        <div className="iu-fas-hero__actions">
          <Button href="/fascicoli/esporta"><Download size={15}/> Esporta</Button>
          <Button href="/fascicoli/archivio"><Archive size={15}/> Archivio</Button>
          <Button variant="primary" href="/fascicoli/nuovo"><FolderPlus size={16}/> Nuovo fascicolo</Button>
        </div>
      </section>

      <section className="iu-fas-stats" aria-label="Indicatori fascicoli">
        <StatCard icon={<FolderOpen size={19}/>} label="Attivi" value={data.summary.active} note="fascicoli non archiviati" tone="primary"/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="In corso" value={data.summary.inProgress} note="pratiche da lavorare" tone="success"/>
        <StatCard icon={<Archive size={19}/>} label="Da archiviare" value={data.summary.toArchive} note="definiti o da chiudere" tone="warning"/>
        <StatCard icon={<CalendarDays size={19}/>} label="Scadenze 30g" value={data.summary.deadlines30} note="prossime scadenze" tone="orange"/>
        <StatCard icon={<FileText size={19}/>} label="Da classificare" value={data.summary.documentsToClassify} note="documenti da rivedere" tone="purple"/>
        <StatCard icon={<Bell size={19}/>} label="Comunicazioni" value={data.summary.unreadCommunications} note="non lette o da associare" tone="info"/>
      </section>

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
        <button className="iu-fas-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><Filter size={16}/> Filtri</button>
        <button className="iu-fas-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna fascicoli"><RefreshCw size={17}/></button>
      </section>

      {advancedOpen ? (
        <section className="iu-fas-advanced" aria-label="Filtri avanzati fascicoli">
          <label>
            <span>Ufficio giudiziario</span>
            <input value={court} onChange={(event) => setCourt(event.target.value)} placeholder="Tribunale, TAR, GDP..."/>
          </label>
          <label>
            <span>Ordinamento</span>
            <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
              {(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}
            </select>
          </label>
          <label className="iu-fas-check">
            <input type="checkbox" checked={alertsOnly} onChange={(event) => setAlertsOnly(event.target.checked)}/>
            <span>Mostra solo fascicoli con alert o comunicazioni</span>
          </label>
        </section>
      ) : null}

      <section className="iu-fas-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione fascicoli...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> Vista in sola lettura: scritture ancora sulle route storiche.</small>
        {selectedVisible ? <small className="iu-fas-selected">{selectedVisible} selezionati</small> : null}
      </section>

      <section className="iu-fas-layout">
        <div className="iu-fas-main-list">
          {selectedVisible ? (
            <div className="iu-fas-bulkbar">
              <strong>{selectedVisible} fascicoli selezionati</strong>
              <a href="/fascicoli/esporta"><Download size={14}/> Esporta selezione</a>
              <a href="/lex?context=fascicoli"><Sparkles size={14}/> Chiedi sintesi a Lex</a>
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
            <span><FileText size={16}/> Numero documenti e documenti da classificare sempre separati</span>
          </div>
        </Panel>
        <Panel title="Integrazioni pronte" subtitle="Agganci utili alla pagina fascicoli" icon={<Sparkles size={17}/>}>
          <div className="iu-fas-integrations">
            <a href="/polisWeb">PolisWeb / PST</a>
            <a href="/pdp">PDP Penale</a>
            <a href="/pat">PAT Amministrativo</a>
            <a href="/sigit/ricerca">PTT Tributario</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context="fascicoli"
        title="Lex AI fascicoli"
        body="Posso sintetizzare un fascicolo, evidenziare scadenze senza prossima azione e preparare una lista di controllo prima di deposito, udienza o archiviazione."
        primaryHref="/lex?context=fascicoli"
        primaryLabel="Apri Lex sui fascicoli"
        secondaryHref="/app-v2/ricerca-studio?tipo=fascicoli"
        secondaryLabel="Cerca nello studio"
      />
    </main>
  )
}
