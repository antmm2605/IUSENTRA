import { lazy, Suspense, useEffect, useId, useMemo, useState } from 'react'
import { CalendarCheck, Gavel, RefreshCw, Scale, Search } from 'lucide-react'
import { getGuidaProcedureCatalog, type GuidaCatalogRow } from '../guidaPraticaData'
import { useBusyActivity } from '../ui/useBusyActivity'

const ProcedureGuide = lazy(() => import('./GuidaPraticaSidebar').then(module => ({ default: module.GuidaPraticaSidebar })))
type Category = 'impugnazione' | 'reclamo'

export default function AgendaProceduralTools({ fascicoloId, fascicoloTitle }: { fascicoloId: string; fascicoloTitle: string }) {
  const [category, setCategory] = useState<Category | null>(null)
  const [catalog, setCatalog] = useState<GuidaCatalogRow[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState('')
  const searchId = useId()
  useBusyActivity(loading, 'Caricamento delle procedure…')
  useEffect(() => {
    if (!category || catalog) return
    let active = true
    setLoading(true)
    setError('')
    getGuidaProcedureCatalog().then(rows => {
      if (active) { setLoading(false); setCatalog(rows) }
    }).catch(() => {
      if (active) { setLoading(false); setError('Catalogo non disponibile. Riprova il caricamento.') }
    })
    return () => { active = false }
  }, [Boolean(category), catalog, retry])
  const choices = useMemo(() => (catalog || []).filter(row => {
    const name = row.denominazione.toLocaleLowerCase('it-IT')
    const matchesCategory = category === 'reclamo' ? /reclam/u.test(name) : /impugnaz|appello|cassazion|revocazion/u.test(name)
    return matchesCategory && `${name} ${row.codice}`.includes(query.trim().toLocaleLowerCase('it-IT'))
  }), [catalog, category, query])
  function chooseCategory(next: Category) {
    setCategory(current => current === next ? null : next)
    setSelected('')
    setQuery('')
  }
  return <section className="iu-ag-procedures" aria-label="Impugnazioni, reclami e scadenze">
    <nav aria-label="Supporto al procedimento">
      <button type="button" aria-expanded={category === 'impugnazione'} onClick={() => chooseCategory('impugnazione')}><Scale size={16}/>Impugnazione</button>
      <button type="button" aria-expanded={category === 'reclamo'} onClick={() => chooseCategory('reclamo')}><Gavel size={16}/>Reclamo</button>
      <a href={`/scadenziario${fascicoloId ? `?id_fascicolo=${encodeURIComponent(fascicoloId)}` : ''}`}><CalendarCheck size={16}/>Scadenziario</a>
    </nav>
    {category ? <div className="iu-ag-procedures__body">
      <p>Scegli la procedura applicabile alla fonte. La data dell’impegno non determina automaticamente la decorrenza del termine.</p>
      <label htmlFor={searchId}><Search size={15}/>Cerca {category === 'reclamo' ? 'reclamo' : 'impugnazione'}</label>
      <input id={searchId} type="search" value={query} onChange={event => { setQuery(event.target.value); setSelected('') }} placeholder="Nome della procedura o codice"/>
      {loading ? <p role="status"><RefreshCw size={16} className="iu-spin"/>Caricamento delle procedure…</p> : error ? <div role="alert"><p>{error}</p><button type="button" onClick={() => setRetry(value => value + 1)}>Riprova</button></div> : <>
        <label htmlFor={`${searchId}-procedure`}>Procedura</label>
        <select id={`${searchId}-procedure`} value={selected} onChange={event => setSelected(event.target.value)}>
          <option value="">Scegli la procedura</option>
          {choices.map(row => <option key={row.codice} value={row.codice}>{row.denominazione} · {row.codice}</option>)}
        </select>
        {!choices.length ? <p role="status">Nessuna procedura corrisponde alla ricerca.</p> : null}
      </>}
      {selected ? <Suspense fallback={<p role="status">Caricamento della guida…</p>}><ProcedureGuide key={`${fascicoloId}:${selected}`} fascicoloId={fascicoloId} codice={selected} fascicoloTitle={fascicoloTitle} explicitProcedure/></Suspense> : null}
    </div> : null}
  </section>
}
