import { useEffect, useMemo, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import './CartellaClientePage.css'
import { OperationalModal } from './OperationalModal'
import { Button, ButtonLink } from '../ui/Button'
import { getCartellaClientePage, type CartellaClienteData, type CartellaClienteItem } from '../clientiCartellaData'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'

export type ClientCatalogArea = 'matters' | 'deadlines' | 'documents' | 'messages' | 'invoices'
const titles: Record<ClientCatalogArea, string> = { matters: 'Fascicoli attivi', deadlines: 'Scadenze aperte', documents: 'Documenti', messages: 'Comunicazioni', invoices: 'Parcelle' }

export default function CartellaClienteCatalog({ clientId, clientName, area, onClose, onOpenDocuments, focusToken }: {
  clientId: string; clientName: string; area: ClientCatalogArea; focusToken?: number; onClose: () => void;
  onOpenDocuments: (items: CartellaClienteItem[]) => void;
}) {
  const contentRef = useRef<HTMLElement>(null)
  const [data, setData] = useState<CartellaClienteData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [query, setQuery] = useState('')
  const [state, setState] = useState('')
  const [selection, setSelection] = useState<Set<string>>(new Set())
  const [onlySelected, setOnlySelected] = useState(false)
  const [page, setPage] = useState(1)
  useOperationalRefresh(['clienti', 'fascicoli', 'scadenze', 'comunicazioni', 'fatturazione'], () => setRevision(value => value + 1))
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    getCartellaClientePage(clientId, true).then(payload => {
      if (active) setData(payload)
    }).catch(() => { if (active) setError('Impossibile caricare il catalogo della cartella cliente. Riprova o controlla i permessi.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [clientId, revision])
  useEffect(() => { setQuery(''); setState(''); setSelection(new Set()); setOnlySelected(false); setPage(1) }, [area])
  const rows: CartellaClienteItem[] = useMemo(() => !data ? [] : ({ matters: data.matters.active, deadlines: data.deadlines, documents: data.documentItems, messages: data.messages, invoices: data.invoices }[area]), [data, area])
  const matching = useMemo(() => rows.filter(row => (!state || row.status === state) && `${row.title} ${row.subtitle} ${row.date || ''} ${row.status || ''}`.toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))), [rows, query, state])
  const filtered = onlySelected ? matching.filter(row => selection.has(row.id)) : matching
  const pages = Math.max(1, Math.ceil(filtered.length / 30))
  const currentPage = Math.min(page, pages)
  const selected = rows.filter(row => selection.has(row.id))
  const allSelected = matching.length > 0 && matching.every(row => selection.has(row.id))
  const states = [...new Set(rows.map(row => row.status || '').filter(Boolean))]
  useEffect(() => { setPage(1) }, [query, state, onlySelected])
  useEffect(() => { const available = new Set(rows.map(row => row.id)); setSelection(current => new Set([...current].filter(id => available.has(id)))) }, [rows])
  useEffect(() => {
    const content = contentRef.current
    content?.closest('.iu-ag-source-modal__body')?.scrollTo({ top: 0 })
    if (content) content.querySelector<HTMLInputElement>('.iu-cart-catalog__rows input[type="checkbox"]')?.focus({ preventScroll: true })
  }, [currentPage])
  function openSelected() {
    if (area === 'documents') onOpenDocuments(selected)
    else for (const item of selected) window.dispatchEvent(new CustomEvent('iusentra:open-work-window', { detail: { href: item.href, title: item.title } }))
  }
  return <OperationalModal open focusToken={focusToken} ariaLabel={`${titles[area]} di ${clientName}`} title={`${titles[area]} · ${clientName}`} eyebrow={null} onClose={onClose} boxClassName="iu-cart-catalog-box">
    <section ref={contentRef} className="iu-cart-catalog" aria-busy={loading}>
      <div className="iu-cart-catalog__filters">
        <label><span>Cerca nell’elenco</span><div><Search size={16} aria-hidden="true"/><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Titolo, fascicolo, data o stato…"/></div></label>
        <label><span>Stato o tipo</span><select value={state} onChange={event => setState(event.target.value)}><option value="">Tutti</option>{states.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      </div>
      {error ? <div role="alert"><p>{error}</p><Button tone="neutral" onClick={() => setRevision(value => value + 1)}>Riprova</Button></div> : null}
      {loading ? <p role="status">Caricamento dell’elenco completo…</p> : !error ? <>
        <div className="iu-cart-catalog__selection">
          <label><input type="checkbox" checked={allSelected} disabled={!matching.length} onChange={() => setSelection(current => { const next = new Set(current); for (const row of matching) { if (allSelected) next.delete(row.id); else next.add(row.id) } return next })}/>Seleziona tutti i risultati filtrati ({matching.length.toLocaleString('it-IT')})</label>
          <span role="status">{selected.length.toLocaleString('it-IT')} {selected.length === 1 ? 'selezionato' : 'selezionati'}</span>
          <Button tone="neutral" disabled={!selected.length} onClick={() => setOnlySelected(value => !value)}>{onlySelected ? 'Mostra tutti' : 'Mostra selezionati'}</Button>
          <Button tone="neutral" disabled={!selected.length || selected.length > 6} onClick={openSelected}>Apri selezionati</Button>
          {selected.length > 6 ? <span>Apri fino a 6 elementi insieme per mantenere leggibile lo spazio di lavoro.</span> : null}
          {selected.length ? <Button tone="neutral" onClick={() => { setSelection(new Set()); setOnlySelected(false) }}>Azzera selezione</Button> : null}
        </div>
        {!filtered.length ? <p role="status">Nessun risultato corrisponde ai filtri.</p> : <div className="iu-cart-catalog__rows">{filtered.slice((currentPage - 1) * 30, currentPage * 30).map(row => <article key={row.id}>
          <input type="checkbox" aria-label={`Seleziona ${row.title}`} checked={selection.has(row.id)} onChange={event => setSelection(current => { const next = new Set(current); if (event.target.checked) next.add(row.id); else next.delete(row.id); return next })}/>
          <div><strong>{row.title}</strong><span>{row.subtitle}</span><small>{[row.status, row.date, row.time, row.amount].filter(Boolean).join(' · ')}</small></div>
          {area === 'documents' ? <Button tone="neutral" onClick={() => onOpenDocuments([row])}>Visualizza</Button> : <ButtonLink href={row.href} tone="neutral">Apri</ButtonLink>}
        </article>)}</div>}
        <footer><span>{filtered.length.toLocaleString('it-IT')} {filtered.length === 1 ? 'risultato' : 'risultati'} · Pagina {currentPage} di {pages}</span><Button tone="neutral" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Precedente</Button><Button tone="neutral" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Successiva</Button></footer>
      </> : null}
    </section>
  </OperationalModal>
}
