import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  Eye,
  Filter,
  Mail,
  PencilLine,
  Phone,
  Search,
  ShieldCheck,
  Sparkles,
  UserPlus,
  UserRound,
  UsersRound,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptySoggettiPage,
  getSoggettiPage,
  type SoggettiPageData,
  type SoggettoRow,
  type SoggettoTipo,
} from '../soggettiData'
import './SoggettiPage.css'

type SortKey = 'nome' | 'fascicoli' | 'completezza'

const sortLabels: Record<SortKey, string> = {
  nome: 'Nome',
  fascicoli: 'Piu fascicoli',
  completezza: 'Da completare',
}

function normalizeText(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function hasNoContacts(item: SoggettoRow): boolean {
  return !item.email && !item.phone && !item.pec
}

function qualityTone(item: SoggettoRow): SoggettoRow['tone'] {
  if (item.missingFields.length > 2) return 'danger'
  if (item.missingFields.length || hasNoContacts(item)) return 'warning'
  return 'success'
}

function qualityLabel(item: SoggettoRow): string {
  if (item.missingFields.length) return 'Da completare'
  if (hasNoContacts(item)) return 'Recapiti assenti'
  return 'Completo'
}

function visible(item: SoggettoRow, query: string): boolean {
  const needle = normalizeText(query.trim())
  if (!needle) return true
  return normalizeText([
    item.name,
    item.typeLabel,
    item.role,
    item.identifier,
    item.email,
    item.phone,
    item.pec,
    item.city,
    item.province,
    item.clientName,
  ].join(' ')).includes(needle)
}

function sortRows(rows: SoggettoRow[], sort: SortKey): SoggettoRow[] {
  const copy = [...rows]
  if (sort === 'fascicoli') return copy.sort((a, b) => b.matters - a.matters || a.name.localeCompare(b.name, 'it'))
  if (sort === 'completezza') return copy.sort((a, b) => b.missingFields.length - a.missingFields.length || Number(hasNoContacts(b)) - Number(hasNoContacts(a)))
  return copy.sort((a, b) => a.name.localeCompare(b.name, 'it'))
}

function StatCard({ icon, label, value, note }:{icon: ReactNode; label: string; value: number; note: string}) {
  return (
    <article className="iu-sogg-stat">
      <div>{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  )
}

function ContactBlock({ item }:{item: SoggettoRow}) {
  if (hasNoContacts(item)) return <span className="iu-sogg-muted">-</span>
  return (
    <div className="iu-sogg-contact">
      {item.phone ? <span><Phone size={13}/> {item.phone}</span> : null}
      {item.email ? <span><Mail size={13}/> {item.email}</span> : null}
      {item.pec ? <span><ShieldCheck size={13}/> {item.pec}</span> : null}
    </div>
  )
}

function RowActions({ item }:{item: SoggettoRow}) {
  return (
    <div className="iu-sogg-actions" aria-label={`Azioni soggetto ${item.name}`}>
      <a href={item.href} aria-label="Apri soggetto"><Eye size={15}/></a>
      <a href={item.editHref} aria-label="Modifica soggetto"><PencilLine size={15}/></a>
    </div>
  )
}

function SoggettiTable({ items }:{items: SoggettoRow[]}) {
  return (
    <section className="iu-sogg-table-card" aria-label="Elenco soggetti e parti">
      <div className="iu-sogg-table-head">
        <strong>{items.length} soggetti</strong>
        <span>Dettaglio e modifica restano sul backend storico</span>
      </div>
      <div className="iu-sogg-table-wrap">
        <table className="iu-sogg-table">
          <thead>
            <tr>
              <th>Soggetto</th>
              <th>Tipo</th>
              <th>Ruolo / qualifica</th>
              <th>Identificativo</th>
              <th>Contatti</th>
              <th>Cliente collegato</th>
              <th>Fascicoli</th>
              <th>Qualita</th>
              <th>Azioni</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td className="iu-sogg-title-cell"><a href={item.href}>{item.name}</a><span>{item.city ? `${item.city} ${item.province ? `(${item.province})` : ''}` : 'Anagrafica soggetto'}</span></td>
                <td><Badge tone={item.tone}>{item.typeLabel}</Badge></td>
                <td>{item.role.replaceAll('_', ' ')}</td>
                <td>{item.identifier || '-'}</td>
                <td><ContactBlock item={item}/></td>
                <td>{item.clientName || <span className="iu-sogg-muted">Non collegato</span>}</td>
                <td>{item.matters}</td>
                <td><Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge></td>
                <td><RowActions item={item}/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function SoggettoMobileCard({ item }:{item: SoggettoRow}) {
  return (
    <article className="iu-sogg-mobile-card">
      <header>
        <a href={item.href}>{item.name}</a>
        <Badge tone={item.tone}>{item.typeLabel}</Badge>
      </header>
      <p>{item.role.replaceAll('_', ' ')} - {item.identifier || 'Identificativo assente'}</p>
      <dl>
        <div><dt>Cliente</dt><dd>{item.clientName || '-'}</dd></div>
        <div><dt>Fascicoli</dt><dd>{item.matters}</dd></div>
        <div><dt>Sede</dt><dd>{item.city || '-'}</dd></div>
      </dl>
      <ContactBlock item={item}/>
      <footer>
        <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
        <RowActions item={item}/>
      </footer>
    </article>
  )
}

function EmptyState() {
  return (
    <section className="iu-sogg-empty">
      <UsersRound size={26}/>
      <h2>Nessun soggetto trovato</h2>
      <p>Modifica ricerca e filtri oppure crea un nuovo soggetto processuale.</p>
      <a href="/soggetti/nuovo"><UserPlus size={16}/>Nuovo Soggetto</a>
    </section>
  )
}

export function SoggettiPage() {
  const [data, setData] = useState<SoggettiPageData>(emptySoggettiPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<SoggettoTipo>('tutti')
  const [roleFilter, setRoleFilter] = useState('tutti')
  const [qualityOnly, setQualityOnly] = useState(false)
  const [sort, setSort] = useState<SortKey>('nome')

  useEffect(() => {
    let alive = true
    getSoggettiPage().then((payload) => {
      if (alive) setData(payload)
    }).finally(() => {
      if (alive) setLoading(false)
    })
    return () => {
      alive = false
    }
  }, [])

  const filtered = useMemo(() => sortRows(data.items.filter((item) => {
    if (!visible(item, query)) return false
    if (typeFilter !== 'tutti' && item.type !== typeFilter) return false
    if (roleFilter !== 'tutti' && item.role !== roleFilter) return false
    if (qualityOnly && !item.missingFields.length && !hasNoContacts(item)) return false
    return true
  }), sort), [data.items, query, typeFilter, roleFilter, qualityOnly, sort])

  return (
    <main className="iu-content iu-soggetti-page">
      <section className="iu-sogg-hero">
        <div>
          <span><UsersRound size={15}/>Soggetti e Parti</span>
          <h1>Anagrafica soggetti</h1>
          <p>Persone, enti, controparti, difensori, testimoni e soggetti collegati ai fascicoli nella nuova superficie React ufficiale.</p>
        </div>
        <div className="iu-sogg-hero__actions">
          <a href="/soggetti/nuovo"><UserPlus size={16}/>Nuovo Soggetto</a>
          <a href="/clienti">Clienti e anagrafiche</a>
        </div>
      </section>

      <section className="iu-sogg-stats" aria-label="Indicatori soggetti">
        <StatCard icon={<UsersRound size={20}/>} label="Soggetti" value={data.summary.total} note={`${data.summary.withMatters} con fascicoli`}/>
        <StatCard icon={<UserRound size={20}/>} label="Persone fisiche" value={data.summary.physical} note="incluse parti e testimoni"/>
        <StatCard icon={<Building2 size={20}/>} label="Enti e societa" value={data.summary.legal} note="PG, PA, enti e condomini"/>
        <StatCard icon={<AlertTriangle size={20}/>} label="Da completare" value={data.summary.incomplete + data.summary.withoutContacts} note="qualita anagrafica"/>
      </section>

      <section className="iu-sogg-toolbar">
        <label className="iu-sogg-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Cerca soggetto, ruolo, CF, cliente collegato..."/></label>
        <label><Filter size={15}/><select value={typeFilter} onChange={(event) => setTypeFilter(event.currentTarget.value as SoggettoTipo)}>{data.facets.types.map((item) => <option value={item.value} key={item.value}>{item.label} ({item.count})</option>)}</select></label>
        <label><BriefcaseBusiness size={15}/><select value={roleFilter} onChange={(event) => setRoleFilter(event.currentTarget.value)}>{data.facets.roles.map((item) => <option value={item.value} key={item.value}>{item.label} ({item.count})</option>)}</select></label>
        <label><BadgeCheck size={15}/><select value={sort} onChange={(event) => setSort(event.currentTarget.value as SortKey)}>{Object.entries(sortLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <button className={qualityOnly ? 'is-active' : ''} type="button" onClick={() => setQualityOnly((value) => !value)}>Solo da completare</button>
      </section>

      <section className="iu-sogg-layout">
        <div>
          {filtered.length ? <SoggettiTable items={filtered}/> : <EmptyState/>}
          <div className="iu-sogg-mobile-list">{filtered.map((item) => <SoggettoMobileCard item={item} key={item.id}/>)}</div>
        </div>
        <aside className="iu-sogg-rail">
          <Panel title="Qualita dati" icon={<ShieldCheck size={17}/>} count={data.summary.incomplete}>
            <div className="iu-sogg-insights">
              <span><AlertTriangle size={14}/>{data.summary.withoutContacts} soggetti senza recapiti</span>
              <span><BadgeCheck size={14}/>{data.summary.linkedClients} collegati a clienti</span>
              <span><BriefcaseBusiness size={14}/>{data.summary.withMatters} presenti in fascicoli</span>
            </div>
          </Panel>
          <Panel title="Accessi rapidi" icon={<Sparkles size={17}/>}>
            <div className="iu-sogg-shortcuts">
              <a href="/soggetti/nuovo"><UserPlus size={15}/>Nuovo soggetto</a>
              <a href="/clienti/nuovo?tab=soggetto"><UsersRound size={15}/>Form unificato</a>
              <a href="/clienti"><UserRound size={15}/>Clienti e anagrafiche</a>
            </div>
          </Panel>
        </aside>
      </section>

      <span className={`iu-sogg-sync ${loading ? '' : 'ok'}`}>{loading ? 'Caricamento soggetti...' : `${data.source} - dati reali`}</span>

      <FloatingLex
        context="soggetti"
        title="Lex AI soggetti"
        body="Posso aiutarti a individuare duplicati, ruoli processuali incoerenti, soggetti senza cliente collegato e dati fiscali mancanti."
        primaryHref="/lex?context=soggetti"
        primaryLabel="Apri Lex soggetti"
        secondaryHref="/soggetti/nuovo"
        secondaryLabel="Nuovo soggetto"
      />
    </main>
  )
}
