import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  ChevronRight,
  Eye,
  Filter,
  Mail,
  PencilLine,
  Phone,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserPlus,
  UserRound,
  UsersRound,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { SyncedTopScrollbar } from './SyncedTopScrollbar'
import {
  deleteSoggetti,
  deleteSoggetto,
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
  fascicoli: 'Più fascicoli',
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
    item.matterRefs.join(' '),
  ].join(' ')).includes(needle)
}

function initialMatterFilter(): string {
  if (typeof window === 'undefined') return ''
  const params = new URLSearchParams(window.location.search)
  return params.get('fascicolo') || params.get('id_fascicolo') || ''
}

function initialSubjectQuery(): string {
  if (typeof window === 'undefined') return ''
  const params = new URLSearchParams(window.location.search)
  return params.get('q') || params.get('search') || ''
}

function sortRows(rows: SoggettoRow[], sort: SortKey): SoggettoRow[] {
  const copy = [...rows]
  if (sort === 'fascicoli') return copy.sort((a, b) => b.matters - a.matters || a.name.localeCompare(b.name, 'it'))
  if (sort === 'completezza') return copy.sort((a, b) => b.missingFields.length - a.missingFields.length || Number(hasNoContacts(b)) - Number(hasNoContacts(a)))
  return copy.sort((a, b) => a.name.localeCompare(b.name, 'it'))
}

function routeSubjectId(): string {
  const match = window.location.pathname.match(/^\/soggetti\/([^/]+)/)
  if (!match || match[1] === 'nuovo') return ''
  return decodeURIComponent(match[1])
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

function RowActions({
  item,
  deleting,
  onDelete,
}:{
  item: SoggettoRow
  deleting: boolean
  onDelete: (item: SoggettoRow) => void
}) {
  return (
    <div className="iu-sogg-actions" aria-label={`Azioni soggetto ${item.name}`}>
      <a href={item.href} aria-label="Apri soggetto"><Eye size={15}/></a>
      <a href={item.editHref} aria-label="Modifica soggetto"><PencilLine size={15}/></a>
      <button type="button" onClick={() => onDelete(item)} disabled={deleting} aria-label={`Elimina soggetto ${item.name}`}>
        <Trash2 size={15}/>
      </button>
    </div>
  )
}

function SoggettiTable({
  items,
  selected,
  onToggle,
  onToggleAll,
  deletingIds,
  onDelete,
}:{
  items: SoggettoRow[]
  selected: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
  deletingIds: Set<string>
  onDelete: (item: SoggettoRow) => void
}) {
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id))
  return (
    <section className="iu-sogg-table-card" aria-label="Elenco soggetti e parti">
      <div className="iu-sogg-table-head">
        <strong>{items.length} soggetti</strong>
        <span>Dettaglio e modifica aprono la scheda aggiornata, con operazioni tracciate</span>
      </div>
      <SyncedTopScrollbar className="iu-sogg-table-wrap">
        <table className="iu-sogg-table">
          <thead>
            <tr>
              <th><input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Seleziona tutti i soggetti visibili"/></th>
              <th>Soggetto</th>
              <th>Tipo</th>
              <th>Ruolo / qualifica</th>
              <th>Identificativo</th>
              <th>Contatti</th>
              <th>Fascicoli</th>
              <th>Qualità</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td><input type="checkbox" checked={selected.has(item.id)} onChange={() => onToggle(item.id)} aria-label={`Seleziona ${item.name}`}/></td>
                <td className="iu-sogg-title-cell">
                  <div className="iu-sogg-title-line">
                    <a href={item.href}>{item.name}</a>
                    <RowActions item={item} deleting={deletingIds.has(item.id)} onDelete={onDelete}/>
                  </div>
                  <span>{item.city ? `${item.city} ${item.province ? `(${item.province})` : ''}` : 'Anagrafica soggetto'}</span>
                </td>
                <td><Badge tone={item.tone}>{item.typeLabel}</Badge></td>
                <td>{item.role.replaceAll('_', ' ')}</td>
                <td>{item.identifier || '-'}</td>
                <td><ContactBlock item={item}/></td>
                <td>{item.matters}</td>
                <td><Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </SyncedTopScrollbar>
    </section>
  )
}

function SoggettoMobileCard({
  item,
  checked,
  onToggle,
  deleting,
  onDelete,
}:{
  item: SoggettoRow
  checked: boolean
  onToggle: () => void
  deleting: boolean
  onDelete: (item: SoggettoRow) => void
}) {
  return (
    <article className="iu-sogg-mobile-card">
      <header>
        <label className="iu-sogg-mobile-card__select">
          <input type="checkbox" checked={checked} onChange={onToggle}/>
          <a href={item.href}>{item.name}</a>
        </label>
        <Badge tone={item.tone}>{item.typeLabel}</Badge>
      </header>
      <p>{item.role.replaceAll('_', ' ')} - {item.identifier || 'Identificativo assente'}</p>
      <dl>
        <div><dt>Fascicoli</dt><dd>{item.matters}</dd></div>
        <div><dt>Sede</dt><dd>{item.city || '-'}</dd></div>
      </dl>
      <ContactBlock item={item}/>
      <footer>
        <Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge>
        <RowActions item={item} deleting={deleting} onDelete={onDelete}/>
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

function SelectedSubjectPanel({ item }:{item:SoggettoRow}) {
  return (
    <section className="iu-sogg-focus">
      <div>
        <a className="iu-sogg-back" href="/soggetti"><ArrowLeft size={15}/>Torna a Soggetti e Parti</a>
        <span className="iu-sogg-focus__eyebrow">Scheda soggetto selezionato</span>
        <h2>{item.name}</h2>
        <p>{item.role.replaceAll('_', ' ')} - {item.identifier || 'Identificativo non presente'}</p>
      </div>
      <dl>
        <div><dt>Tipo</dt><dd>{item.typeLabel}</dd></div>
        <div><dt>Fascicoli</dt><dd>{item.matters}</dd></div>
        <div><dt>Qualità</dt><dd><Badge tone={qualityTone(item)}>{qualityLabel(item)}</Badge></dd></div>
      </dl>
      <div className="iu-sogg-focus__actions">
        <a href={item.editHref}><PencilLine size={16}/>Modifica dati</a>
        <a href={`/messaggi/nuovo?destinatario=${encodeURIComponent(item.email || item.phone || item.pec || '')}`}><Mail size={16}/>Scrivi comunicazione</a>
        <a href={`/fascicoli/nuovo?id_soggetto=${encodeURIComponent(item.id)}`}><BriefcaseBusiness size={16}/>Nuovo fascicolo</a>
      </div>
      <small><ChevronRight size={14}/>Le operazioni restano tracciate e la scheda usa la nuova grafica.</small>
    </section>
  )
}

export function SoggettiPage() {
  const [data, setData] = useState<SoggettiPageData>(emptySoggettiPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState(initialSubjectQuery)
  const [typeFilter, setTypeFilter] = useState<SoggettoTipo>('tutti')
  const [roleFilter, setRoleFilter] = useState('tutti')
  const [qualityOnly, setQualityOnly] = useState(false)
  const [sort, setSort] = useState<SortKey>('nome')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [error, setError] = useState('')
  const selectedId = routeSubjectId()
  const matterFilter = initialMatterFilter()

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
    if (matterFilter && !item.matterIds.includes(matterFilter)) return false
    if (typeFilter !== 'tutti' && item.type !== typeFilter) return false
    if (roleFilter !== 'tutti' && item.role !== roleFilter) return false
    if (qualityOnly && !item.missingFields.length && !hasNoContacts(item)) return false
    return true
  }), sort), [data.items, query, matterFilter, typeFilter, roleFilter, qualityOnly, sort])
  const selectedSubject = selectedId ? data.items.find((item) => item.id === selectedId) : undefined
  const selectedVisibleIds = useMemo(
    () => filtered.filter((item) => selected.has(item.id)).map((item) => item.id),
    [filtered, selected],
  )
  const selectedVisible = selectedVisibleIds.length

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
      const allSelected = filtered.length > 0 && filtered.every((item) => current.has(item.id))
      if (allSelected) return new Set([...current].filter((id) => !filtered.some((item) => item.id === id)))
      return new Set([...current, ...filtered.map((item) => item.id)])
    })
  }

  const refresh = () => {
    setLoading(true)
    getSoggettiPage().then(setData).finally(() => setLoading(false))
  }

  const handleDelete = async (item: SoggettoRow) => {
    if (!window.confirm(`Eliminare il soggetto "${item.name}"?`)) return
    setError('')
    setFeedback('')
    setDeletingIds((current) => new Set(current).add(item.id))
    try {
      const result = await deleteSoggetto(item.id)
      setFeedback(result.message)
      setSelected((current) => {
        const next = new Set(current)
        next.delete(item.id)
        return next
      })
      refresh()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Eliminazione soggetto non riuscita.')
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current)
        next.delete(item.id)
        return next
      })
    }
  }

  const handleBulkDelete = async () => {
    if (!selectedVisibleIds.length) return
    const label = selectedVisibleIds.length === 1 ? '1 soggetto selezionato' : `${selectedVisibleIds.length} soggetti selezionati`
    if (!window.confirm(`Eliminare ${label}?`)) return
    setError('')
    setFeedback('')
    setBulkDeleting(true)
    try {
      const result = await deleteSoggetti(selectedVisibleIds)
      setFeedback(result.message)
      setSelected((current) => new Set([...current].filter((id) => !selectedVisibleIds.includes(id))))
      refresh()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Eliminazione multipla soggetti non riuscita.')
    } finally {
      setBulkDeleting(false)
    }
  }

  return (
    <main className="iu-content iu-soggetti-page">
      <section className="iu-sogg-hero">
        <div>
          <span><UsersRound size={15}/>Soggetti e Parti</span>
          <h1>Anagrafica soggetti</h1>
          <p>Persone, enti, controparti, difensori, testimoni e soggetti collegati ai fascicoli in una vista anagrafica unica.</p>
        </div>
        <div className="iu-sogg-hero__actions">
          <a href="/soggetti/nuovo"><UserPlus size={16}/>Nuovo Soggetto</a>
          <a href="/clienti">Clienti e anagrafiche</a>
        </div>
      </section>

      <section className="iu-sogg-stats" aria-label="Indicatori soggetti">
        <StatCard icon={<UsersRound size={20}/>} label="Soggetti" value={data.summary.total} note={`${data.summary.withMatters} con fascicoli`}/>
        <StatCard icon={<UserRound size={20}/>} label="Persone fisiche" value={data.summary.physical} note="incluse parti e testimoni"/>
        <StatCard icon={<Building2 size={20}/>} label="Enti e società" value={data.summary.legal} note="PG, PA, enti e condomini"/>
        <StatCard icon={<AlertTriangle size={20}/>} label="Da completare" value={data.summary.incomplete + data.summary.withoutContacts} note="qualità anagrafica"/>
      </section>

      <section className="iu-sogg-toolbar">
        <label className="iu-sogg-search"><Search size={17}/><input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Cerca soggetto, ruolo, CF, PEC o fascicolo..."/></label>
        <label><Filter size={15}/><select value={typeFilter} onChange={(event) => setTypeFilter(event.currentTarget.value as SoggettoTipo)}>{data.facets.types.map((item) => <option value={item.value} key={item.value}>{item.label} ({item.count})</option>)}</select></label>
        <label><BriefcaseBusiness size={15}/><select value={roleFilter} onChange={(event) => setRoleFilter(event.currentTarget.value)}>{data.facets.roles.map((item) => <option value={item.value} key={item.value}>{item.label} ({item.count})</option>)}</select></label>
        <label><BadgeCheck size={15}/><select value={sort} onChange={(event) => setSort(event.currentTarget.value as SortKey)}>{Object.entries(sortLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <button className={qualityOnly ? 'is-active' : ''} type="button" onClick={() => setQualityOnly((value) => !value)}>Solo da completare</button>
      </section>

      <section className="iu-sogg-status">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Caricamento soggetti...' : 'Dati aggiornati'}</span>
        <small><ShieldCheck size={14}/> Le operazioni di dettaglio, modifica ed eliminazione restano allineate con i dati di studio.</small>
        {matterFilter ? <small className="iu-sogg-status__selected">Filtro fascicolo attivo</small> : null}
        {selectedVisible ? <small className="iu-sogg-status__selected">{selectedVisible} selezionati</small> : null}
        {feedback ? <small className="iu-sogg-status__feedback">{feedback}</small> : null}
        {error ? <small className="iu-sogg-status__error">{error}</small> : null}
      </section>

      {selectedSubject ? <SelectedSubjectPanel item={selectedSubject}/> : null}

      <section className="iu-sogg-layout">
        <div>
          {selectedVisible ? (
            <div className="iu-sogg-bulkbar">
              <strong>{selectedVisible} soggetti selezionati</strong>
              <button type="button" onClick={handleBulkDelete} disabled={bulkDeleting}>
                <Trash2 size={14}/> {bulkDeleting ? 'Eliminazione...' : 'Elimina selezione'}
              </button>
              <button type="button" onClick={() => setSelected(new Set())}>Annulla</button>
            </div>
          ) : null}
          {filtered.length ? (
            <SoggettiTable
              items={filtered}
              selected={selected}
              onToggle={toggle}
              onToggleAll={toggleAll}
              deletingIds={deletingIds}
              onDelete={handleDelete}
            />
          ) : <EmptyState/>}
          <div className="iu-sogg-mobile-list">
            {filtered.map((item) => (
              <SoggettoMobileCard
                item={item}
                checked={selected.has(item.id)}
                onToggle={() => toggle(item.id)}
                deleting={deletingIds.has(item.id)}
                onDelete={handleDelete}
                key={item.id}
              />
            ))}
          </div>
        </div>
        <aside className="iu-sogg-rail">
          <Panel title="Qualità dati" icon={<ShieldCheck size={17}/>} count={data.summary.incomplete}>
            <div className="iu-sogg-insights">
              <span><AlertTriangle size={14}/>{data.summary.withoutContacts} soggetti senza recapiti</span>
              <span><BadgeCheck size={14}/>{data.summary.clientsExcluded} clienti esclusi dalla rubrica parti</span>
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

      <span className={`iu-sogg-sync ${loading ? '' : 'ok'}`}>{loading ? 'Caricamento soggetti...' : 'dati dello studio aggiornati'}</span>

      <FloatingLex
        context="soggetti"
        title="Lex AI soggetti"
        body="Posso aiutarti a individuare duplicati, ruoli processuali incoerenti, soggetti senza recapiti e dati fiscali mancanti."
        primaryHref="#lex"
        primaryLabel="Apri Lex soggetti"
        secondaryHref="/soggetti/nuovo"
        secondaryLabel="Nuovo soggetto"
      />
    </main>
  )
}
