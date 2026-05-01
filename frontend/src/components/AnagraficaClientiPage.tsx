import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Archive,
  AlertTriangle,
  BadgeCheck,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronDown,
  Download,
  Eye,
  FileText,
  Filter,
  FolderOpen,
  Mail,
  PencilLine,
  Phone,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import { Badge, Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyClientiPage,
  formatClienteStatus,
  formatClienteType,
  getClientiPage,
  type ClienteRow,
  type ClienteStato,
  type ClienteTipo,
  type ClientiPageData,
} from '../clientiData'
import './AnagraficaClientiPage.css'

type SortKey = 'nome' | 'recenti' | 'pratiche' | 'completezza'

const sortLabels: Record<SortKey, string> = {
  nome: 'Nome cliente',
  recenti: 'Aggiornati di recente',
  pratiche: 'Più procedimenti',
  completezza: 'Da completare prima',
}

function StatCard({
  icon,
  label,
  value,
  note,
  tone = 'primary',
}:{
  icon: ReactNode
  label: string
  value: number | string
  note: string
  tone?: ClienteRow['tone']
}) {
  return (
    <article className={`iu-cli-stat iu-cli-stat--${tone}`}>
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

function hasNoContacts(item: ClienteRow): boolean {
  return !item.email && !item.phone && !item.pec
}

function hasQualityIssue(item: ClienteRow): boolean {
  return item.missingFields.length > 0 || !item.privacyOk || item.documentExpired || hasNoContacts(item)
}

function isInsideQuery(item: ClienteRow, query: string): boolean {
  const needle = normaliseText(query.trim())
  if (!needle) return true
  return normaliseText([
    item.name,
    item.subtitle,
    item.fiscalId,
    item.email,
    item.phone,
    item.pec,
    item.attorney,
    item.tags.join(' '),
    formatClienteType(item.type),
    formatClienteStatus(item.status),
  ].join(' ')).includes(needle)
}

function qualityTone(item: ClienteRow): ClienteRow['tone'] {
  if (item.documentExpired) return 'danger'
  if (item.missingFields.length > 2) return 'orange'
  if (item.missingFields.length || !item.privacyOk || hasNoContacts(item)) return 'warning'
  return 'success'
}

function qualityLabel(item: ClienteRow): string {
  if (item.documentExpired) return 'Documento scaduto'
  if (item.missingFields.length) return 'Da completare'
  if (!item.privacyOk) return 'Privacy da verificare'
  if (hasNoContacts(item)) return 'Recapiti assenti'
  return 'Completa'
}

function sortRows(rows: ClienteRow[], sort: SortKey): ClienteRow[] {
  const copy = [...rows]
  if (sort === 'pratiche') return copy.sort((a, b) => b.matters - a.matters || a.name.localeCompare(b.name, 'it'))
  if (sort === 'completezza') {
    return copy.sort((a, b) => Number(hasQualityIssue(b)) - Number(hasQualityIssue(a)) || b.missingFields.length - a.missingFields.length)
  }
  if (sort === 'recenti') return copy.sort((a, b) => (b.lastUpdated || '').localeCompare(a.lastUpdated || ''))
  return copy.sort((a, b) => a.name.localeCompare(b.name, 'it'))
}

function RowActions({ item }:{item: ClienteRow}) {
  return (
    <div className="iu-cli-actions" aria-label={`Azioni cliente ${item.name}`}>
      <a href={item.href} aria-label="Apri scheda cliente"><Eye size={15}/></a>
      <a href={item.editHref} aria-label="Modifica cliente"><PencilLine size={15}/></a>
      <a href={item.folderHref} aria-label="Apri cartella cliente"><FolderOpen size={15}/></a>
    </div>
  )
}

function ContactBlock({ item }:{item: ClienteRow}) {
  if (hasNoContacts(item)) return <span className="iu-cli-muted">-</span>
  return (
    <div className="iu-cli-contact">
      {item.phone ? <span><Phone size={13}/> {item.phone}</span> : null}
      {item.email ? <span><Mail size={13}/> {item.email}</span> : null}
      {item.pec ? <span><ShieldCheck size={13}/> {item.pec}</span> : null}
    </div>
  )
}

function ClienteMobileCard({
  item,
  checked,
  onToggle,
}:{
  item: ClienteRow
  checked: boolean
  onToggle: () => void
}) {
  return (
    <article className="iu-cli-mobile-card">
      <header>
        <label><input type="checkbox" checked={checked} onChange={onToggle}/><span>{item.name}</span></label>
        <Badge tone={item.tone}>{formatClienteStatus(item.status)}</Badge>
      </header>
      <a href={item.href} className="iu-cli-mobile-card__title">{item.name}</a>
      <p>{item.subtitle || item.fiscalId || 'Anagrafica cliente'}</p>
      <dl>
        <div><dt>Tipo</dt><dd>{formatClienteType(item.type)}</dd></div>
        <div><dt>C.F. / P.IVA</dt><dd>{item.fiscalId || '-'}</dd></div>
        <div><dt>Avv. referente</dt><dd>{item.attorney || '-'}</dd></div>
        <div><dt>Pratiche</dt><dd>{item.matters}</dd></div>
      </dl>
      <ContactBlock item={item}/>
      <footer>
        <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
        <span><BriefcaseBusiness size={14}/> {item.activeMatters} attive</span>
        <RowActions item={item}/>
      </footer>
    </article>
  )
}

function ClientiTable({
  items,
  selected,
  onToggle,
  onToggleAll,
}:{
  items: ClienteRow[]
  selected: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
}) {
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  return (
    <section className="iu-cli-table-card" aria-label="Elenco clienti">
      <div className="iu-cli-table-head">
        <strong>{items.length} clienti</strong>
        <label><span>25 per pagina</span><ChevronDown size={14}/></label>
      </div>
      <div className="iu-cli-table-wrap">
        <table className="iu-cli-table">
          <thead>
            <tr>
              <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutti i clienti visibili"/></th>
              <th>Cliente</th>
              <th>Tipo</th>
              <th>C.F. / P.IVA</th>
              <th>Contatti</th>
              <th>Avv. referente</th>
              <th>Pratiche</th>
              <th>Qualità</th>
              <th>Stato</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.name}`}/></td>
                <td className="iu-cli-title-cell"><a href={item.href}>{item.name}</a><span>{item.subtitle || item.tags.join(', ') || 'Anagrafica cliente'}</span></td>
                <td><Badge tone="neutral">{formatClienteType(item.type)}</Badge></td>
                <td>{item.fiscalId || '-'}</td>
                <td><ContactBlock item={item}/></td>
                <td>{item.attorney || '-'}</td>
                <td><span className="iu-cli-matter-count">{item.matters}</span></td>
                <td><Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge></td>
                <td><Badge tone={item.tone}>{formatClienteStatus(item.status)}</Badge></td>
                <td><RowActions item={item}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="iu-cli-mobile-list">
        {items.map((item) => (
          <ClienteMobileCard item={item} checked={selected.has(item.id)} onToggle={() => onToggle(item.id)} key={item.id}/>
        ))}
      </div>
      {!items.length ? <p className="iu-empty">Nessun cliente corrisponde ai filtri impostati.</p> : null}
    </section>
  )
}

function InsightPanel({ data, visible }:{data: ClientiPageData; visible: ClienteRow[]}) {
  const daCompletare = visible.filter(hasQualityIssue).slice(0, 4)
  const withProcedures = visible.filter((item) => item.matters > 0 || item.activeMatters > 0).length
  return (
    <aside className="iu-cli-insights">
      <Panel title="Cabina anagrafiche" subtitle="Controlli utili prima di incarico, deposito e fatturazione" icon={<BadgeCheck size={17}/>}>
        <div className="iu-cli-briefing">
          <article>
            <span>Completezza operativa</span>
            <strong>{data.summary.incomplete} anagrafiche da completare</strong>
            <small>Controllo su recapiti, privacy, documento e dati minimi per conferimento.</small>
          </article>
          <article>
            <span>Clienti collegati</span>
            <strong>{withProcedures} clienti con procedimenti visibili</strong>
            <small>La nuova interfaccia è attiva: salvataggi e audit passano dai servizi backend già governati.</small>
          </article>
        </div>
      </Panel>
      <Panel title="Da verificare" icon={<AlertTriangle size={17}/>} count={daCompletare.length}>
        {daCompletare.length ? (
          <div className="iu-cli-alerts">
            {daCompletare.map((item) => (
              <a href={item.href} key={item.id}>
                <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
                <strong>{item.name}</strong>
                <span>
                  {item.missingFields.length
                    ? `Mancano: ${item.missingFields.slice(0, 3).join(', ')}`
                    : item.documentExpired
                      ? 'Documento di identità scaduto'
                      : 'Consenso privacy o recapiti da verificare'}
                </span>
              </a>
            ))}
          </div>
        ) : <p className="iu-empty">Nessuna criticità sulle anagrafiche visibili.</p>}
      </Panel>
      <Panel title="Azioni rapide" icon={<Sparkles size={17}/>}>
        <div className="iu-cli-quick-actions">
          <a href="/clienti/nuovo"><UserPlus size={15}/> Nuovo cliente</a>
          <a href="/soggetti/nuovo"><UsersRound size={15}/> Nuovo soggetto</a>
          <a href="/preventivi/"><FileText size={15}/> Preventivi e incarichi</a>
          <a href="/lex?context=clienti"><Sparkles size={15}/> Chiedi a Lex</a>
        </div>
      </Panel>
    </aside>
  )
}

export function AnagraficaClientiPage() {
  const [data, setData] = useState<ClientiPageData>(emptyClientiPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [type, setType] = useState<ClienteTipo>('tutti')
  const [status, setStatus] = useState<ClienteStato>('tutti')
  const [sort, setSort] = useState<SortKey>('nome')
  const [attorney, setAttorney] = useState('')
  const [onlyIncomplete, setOnlyIncomplete] = useState(false)
  const [withoutContacts, setWithoutContacts] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const refresh = () => {
    setLoading(true)
    getClientiPage().then(setData).finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    setLoading(true)
    getClientiPage()
      .then((payload) => { if (active) setData(payload) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const visible = useMemo(() => {
    const attorneyNeedle = normaliseText(attorney)
    return sortRows(data.items.filter((item) => {
      if (!isInsideQuery(item, query)) return false
      if (type !== 'tutti' && item.type !== type) return false
      if (status !== 'tutti' && item.status !== status) return false
      if (onlyIncomplete && !hasQualityIssue(item)) return false
      if (withoutContacts && !hasNoContacts(item)) return false
      if (attorneyNeedle && !normaliseText(item.attorney).includes(attorneyNeedle)) return false
      return true
    }), sort)
  }, [attorney, data.items, onlyIncomplete, query, sort, status, type, withoutContacts])

  const selectedVisible = visible.filter((item) => selected.has(item.id)).length
  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const toggleAll = () => {
    setSelected((current) => {
      const allSelected = visible.length > 0 && visible.every((item) => current.has(item.id))
      if (allSelected) return new Set([...current].filter((id) => !visible.some((item) => item.id === id)))
      return new Set([...current, ...visible.map((item) => item.id)])
    })
  }

  return (
    <main className="iu-content iu-clienti-page">
      <section className="iu-cli-hero">
        <div>
          <span className="iu-cli-eyebrow"><UsersRound size={16}/> Clienti e anagrafiche</span>
          <h1>Anagrafica Clienti</h1>
          <p>Persone fisiche e giuridiche assistite dallo studio, con stato, recapiti, procedimenti, qualità dati e privacy sempre leggibili.</p>
        </div>
        <div className="iu-cli-hero__actions">
          <Button href="/clienti/esporta"><Download size={15}/> Esporta</Button>
          <Button href="/clienti?stato=ARCHIVIATO"><Archive size={15}/> Archivio clienti</Button>
          <Button variant="primary" href="/clienti/nuovo"><UserPlus size={16}/> Nuovo cliente</Button>
        </div>
      </section>

      <section className="iu-cli-stats" aria-label="Indicatori anagrafica clienti">
        <StatCard icon={<UsersRound size={19}/>} label="Totali" value={data.summary.total} note="clienti in anagrafica" tone="primary"/>
        <StatCard icon={<CheckCircle2 size={19}/>} label="Attivi" value={data.summary.active} note="assistiti operativi" tone="success"/>
        <StatCard icon={<Sparkles size={19}/>} label="Potenziali" value={data.summary.potential} note="da convertire" tone="warning"/>
        <StatCard icon={<Archive size={19}/>} label="Archiviati" value={data.summary.archived} note="non operativi" tone="neutral"/>
        <StatCard icon={<BriefcaseBusiness size={19}/>} label="Con procedimenti" value={data.summary.withMatters} note="fascicoli o pratiche" tone="info"/>
        <StatCard icon={<AlertTriangle size={19}/>} label="Da completare" value={data.summary.incomplete} note="dati mancanti" tone="orange"/>
        <StatCard icon={<Phone size={19}/>} label="Senza recapiti" value={data.summary.withoutContacts} note="telefono, email o PEC assenti" tone="warning"/>
        <StatCard icon={<ShieldCheck size={19}/>} label="Privacy" value={data.summary.privacyMissing} note="consenso da verificare" tone="purple"/>
        <StatCard icon={<FileText size={19}/>} label="Documenti scaduti" value={data.summary.documentsExpired} note="identità da aggiornare" tone="danger"/>
      </section>

      <section className="iu-cli-toolbar" aria-label="Filtri clienti">
        <label className="iu-cli-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca per nome, CF, P.IVA, email, telefono..."/></label>
        <label><span>Tipo</span><select value={type} onChange={(event) => setType(event.target.value as ClienteTipo)}>{data.facets.types.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
        <label><span>Stato</span><select value={status} onChange={(event) => setStatus(event.target.value as ClienteStato)}>{data.facets.statuses.map((facet) => <option value={facet.value} key={facet.value}>{facet.label} ({facet.count})</option>)}</select></label>
        <button className="iu-cli-filter-btn" type="button" onClick={() => setAdvancedOpen((value) => !value)} aria-expanded={advancedOpen}><Filter size={16}/> Filtri</button>
        <button className="iu-cli-icon-btn" type="button" onClick={refresh} aria-label="Aggiorna clienti"><RefreshCw size={17}/></button>
      </section>

      {advancedOpen ? (
        <section className="iu-cli-advanced" aria-label="Filtri avanzati clienti">
          <label><span>Avvocato referente</span><input value={attorney} onChange={(event) => setAttorney(event.target.value)} placeholder="Nome referente..."/></label>
          <label><span>Ordinamento</span><select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>{(Object.keys(sortLabels) as SortKey[]).map((item) => <option value={item} key={item}>{sortLabels[item]}</option>)}</select></label>
          <label className="iu-cli-check"><input type="checkbox" checked={onlyIncomplete} onChange={(event) => setOnlyIncomplete(event.target.checked)}/><span>Solo incomplete, privacy, recapiti o documenti da verificare</span></label>
          <label className="iu-cli-check"><input type="checkbox" checked={withoutContacts} onChange={(event) => setWithoutContacts(event.target.checked)}/><span>Solo senza recapiti</span></label>
        </section>
      ) : null}

      <section className="iu-cli-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Sincronizzazione anagrafiche...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> Dettaglio, modifica e invii usano il backend storico senza duplicare dati.</small>
        {selectedVisible ? <small className="iu-cli-selected">{selectedVisible} selezionati</small> : null}
      </section>

      <section className="iu-cli-layout">
        <div className="iu-cli-main-list">
          {selectedVisible ? (
            <div className="iu-cli-bulkbar">
              <strong>{selectedVisible} clienti selezionati</strong>
              <a href="/clienti/esporta"><Download size={14}/> Esporta selezione</a>
              <a href="/lex?context=clienti"><Sparkles size={14}/> Chiedi controllo a Lex</a>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          <ClientiTable items={visible} selected={selected} onToggle={toggle} onToggleAll={toggleAll}/>
        </div>
        <InsightPanel data={data} visible={visible}/>
      </section>

      <section className="iu-cli-lower-grid">
        <Panel title="Qualità dati anagrafici" subtitle="Informazioni da tenere pulite prima di incarico, atto e fattura" icon={<BadgeCheck size={17}/>}>
          <div className="iu-cli-checklist">
            <span><CheckCircle2 size={16}/> C.F. / P.IVA e recapiti sempre visibili nella lista</span>
            <span><ShieldCheck size={16}/> Privacy e documenti segnalati senza aprire la scheda</span>
            <span><BriefcaseBusiness size={16}/> Procedimenti collegati separati dal semplice stato cliente</span>
          </div>
        </Panel>
        <Panel title="Collegamenti operativi" subtitle="Azioni tipiche dalla pagina anagrafica" icon={<FolderOpen size={17}/>}>
          <div className="iu-cli-integrations">
            <a href="/clienti/nuovo">Nuovo cliente</a>
            <a href="/soggetti/nuovo">Nuovo soggetto</a>
            <a href="/preventivi/">Preventivo</a>
            <a href="/fascicoli/nuovo">Fascicolo</a>
          </div>
        </Panel>
      </section>

      <FloatingLex
        context="clienti"
        title="Lex AI anagrafiche"
        body="Posso controllare quali clienti bloccano conferimento, privacy, preventivo o fascicolo, e preparare una checklist di completamento senza modificare i dati."
        primaryHref="/lex?context=clienti"
        primaryLabel="Apri Lex sui clienti"
        secondaryHref="/global-search?tipo=clienti"
        secondaryLabel="Cerca nello studio"
      />
    </main>
  )
}
