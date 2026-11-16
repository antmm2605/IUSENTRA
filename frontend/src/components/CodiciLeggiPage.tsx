import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { useBusyActivity } from '../ui/useBusyActivity'
import { useEffect, useMemo, useRef, useState } from 'react'
import { NormativeArticleLink } from './NormativeArticleLink'
import { BookOpen, Search, ExternalLink, X } from 'lucide-react'
import { ensureJson } from '../api/client'
import { Page } from '../ui/Page'
import { Button, ButtonLink } from '../ui/Button'
import { Badge } from '../ui/Badge'
import './LegalIntelligencePage.css'
import { matchesCatalogueAct } from './codiciLeggiSearch'
import { applyCatalogueResponse } from './codiciLeggiResults'
import { CodiciLeggiMaterie } from './CodiciLeggiMaterie'

type Act = { key?: string; id: number; title: string; label: string; category: string; articles: number; updated_at: string; materia?: string; tipo?: string; numero?: string | number | null; data_atto?: string | null }
type Article = { id: number; number: string; title: string; act_title: string }
type FullArticle = Article & { text: string; act_label: string; updated_at: string; source_url: string; source_label?: string; only_heading?: boolean; consolidated_at?: string; text_quality?: string; source_requested_at?: string; version_date_scope?: string; verified_as_of?: string; temporal_evidence?: { data: string; nota: string } }
type Riscontro = { data: string; atti_richiesti: number; atti_esaminati?: number; atti_con_testo_verificato: number }
type Vista = 'vigenti' | 'storico'
type Results = { items: Article[]; total: number; act_id?: number }
const base = '/api/v1/ui/ricerca-legale/normativa'
const pageSize = 30
function dateIt(value: string) { return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('/') : 'Data non indicata' }

export function CodiciLeggiPage() {
  const initial = new URLSearchParams(window.location.search)
  const explicitAct = Number(initial.get('act') || 0)
  const initialView = initial.get('vista')
  const [vista, setVista] = useState<Vista>(initialView === 'storico' || (!initialView && explicitAct > 0 && (explicitAct < 3e12 || explicitAct >= 4e12)) ? 'storico' : 'vigenti')
  const [riscontro, setRiscontro] = useState<Riscontro | null>(null)
  const [acts, setActs] = useState<Act[]>([])
  const [catalogueBusy, setCatalogueBusy] = useState(true)
  const [catalogQuery, setCatalogQuery] = useState('')
  const [category, setCategory] = useState(initial.get('category') || '')
  const [act, setAct] = useState(initial.get('act') || '')
  const [query, setQuery] = useState(initial.get('q') || '')
  const [article, setArticle] = useState(initial.get('article') || '')
  const [filters, setFilters] = useState({ act, query, article, category, offset: 0 })
  const [results, setResults] = useState<Results>({ items: [], total: 0 })
  const [selected, setSelected] = useState<FullArticle | null>(null)
  const [selectedId, setSelectedId] = useState(0)
  const [busy, setBusy] = useState(true)
  useBusyActivity(busy, 'Ricerca nelle fonti locali…')
  const [readerBusy, setReaderBusy] = useState(false)
  useBusyActivity(readerBusy, 'Apertura del testo normativo…')
  const [error, setError] = useState('')
  const [readerError, setReaderError] = useState('')
  const [retry, setRetry] = useState(0)
  const visibleActs = useMemo(() => acts.filter(a => ((!category || a.category === category) && matchesCatalogueAct(a, catalogQuery)) || String(a.id) === act), [acts, catalogQuery, act, category])
  const actOptions = visibleActs.slice(0, 100)
  const selection = act && visibleActs.find(item => String(item.id) === act)
  if (selection && !actOptions.some(item => item.id === selection.id)) actOptions.push(selection)
  const currentAct = acts.find(a => String(a.id) === String(results.act_id || filters.act))

  useEffect(() => {
    const controller = new AbortController()
    setCatalogueBusy(true)
    ensureJson<{ ok: boolean; items: Act[]; riscontro?: Riscontro }>(`${base}/atti?vista=${vista}`, { signal: controller.signal }).then(data => { setActs(data.items); setRiscontro(data.riscontro ?? null) }).catch(e => { if (!controller.signal.aborted) setError(e.status === 403 ? 'Non hai il permesso per consultare le fonti.' : e.message === 'Il catalogo delle fonti si sta aggiornando.' ? e.message : 'Archivio non disponibile. Riprova fra poco.') }).finally(() => { if (!controller.signal.aborted) setCatalogueBusy(false) })
    return () => controller.abort()
  }, [retry, vista])
  useEffect(() => {
    const controller = new AbortController()
    setBusy(true); setError(''); setSelected(null); setSelectedId(0)
    const params = new URLSearchParams({ act: filters.act, q: filters.query, article: filters.article, category: filters.category, offset: String(filters.offset), vista })
    window.history.replaceState({}, '', `${window.location.pathname}?${params}`)
    ensureJson<Results>(`${base}/articoli?${params}`, { signal: controller.signal }).then(data => applyCatalogueResponse(controller.signal, filters.act, data, setResults, resolvedAct => {
      setAct(resolvedAct); setFilters(previous => ({ ...previous, act: resolvedAct }))
    })).catch(e => { if (!controller.signal.aborted) { setResults({ items: [], total: 0 }); setError(e.status === 403 ? 'Non hai il permesso per consultare le fonti.' : 'Ricerca non disponibile. Controlla il numero di articolo e riprova.') } }).finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => controller.abort()
  }, [filters, retry, vista])
  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    setReaderBusy(true); setSelected(null); setReaderError('')
    ensureJson<{ item: FullArticle }>(`${base}/articoli/${selectedId}`, { signal: controller.signal }).then(data => setSelected(data.item)).catch(() => { if (!controller.signal.aborted) setReaderError('Il testo non è disponibile. Riprova ad aprire l’articolo.') }).finally(() => { if (!controller.signal.aborted) setReaderBusy(false) })
    return () => controller.abort()
  }, [selectedId])
  const liveSelection = useRef('')
  liveSelection.current = JSON.stringify([filters, selectedId, vista])
  useOperationalRefresh(['normativa'], async () => {
    const selection = liveSelection.current
    const params = new URLSearchParams({ act: filters.act, q: filters.query, article: filters.article, category: filters.category, offset: String(filters.offset), vista })
    const [catalogue, result, article] = await Promise.all([
      ensureJson<{ ok: boolean; items: Act[]; riscontro?: Riscontro }>(`${base}/atti?vista=${vista}`),
      ensureJson<Results>(`${base}/articoli?${params}`),
      selectedId ? ensureJson<{ item: FullArticle }>(`${base}/articoli/${selectedId}`) : Promise.resolve(null),
    ])
    if (selection !== liveSelection.current) return
    setActs(catalogue.items)
    setRiscontro(catalogue.riscontro ?? null)
    setResults(result)
    if (article) setSelected(article.item)
  })
  function chooseAct(value: string) { setCategory(''); setAct(value); setArticle(''); setQuery(''); setFilters({ act: value, query: '', article: '', category: '', offset: 0 }) }
  function reset() { setAct(''); setQuery(''); setArticle(''); setCatalogQuery(''); setCategory(''); setFilters({ act: '', query: '', article: '', category: '', offset: 0 }) }
  function cambiaVista(value: Vista) {
    if (value === vista) return
    setVista(value)
    setActs([])
    setRiscontro(null)
    reset()
  }
  return <Page title="Codici e leggi" subtitle="Codici, leggi e decreti per materia, con testo integrale e ricerca per articolo." actions={<><ButtonLink href="/ricerca-legale/schede-atti" tone="neutral">Norme dei modelli d’atto</ButtonLink><ButtonLink href="/ricerca-legale" tone="neutral">Ricerca legale</ButtonLink></>}>
    <div className="iu-li-page iu-li-normativa">
      <section className="iu-od-source-card iu-li-normativa-filters" aria-label="Ricerca nei codici e nelle leggi">
        <header className="iu-li-section-head"><BookOpen size={20} aria-hidden="true"/><div><h2>Biblioteca normativa</h2><p role={catalogueBusy ? 'status' : undefined}>{catalogueBusy ? 'Caricamento del catalogo normativo…' : `${acts.length.toLocaleString('it-IT')} atti · ${acts.reduce((n, a) => n + a.articles, 0).toLocaleString('it-IT')} articoli consultabili`}</p></div></header>
        <div className="iu-li-normativa-actions" role="group" aria-label="Edizione da consultare">
          <Button tone="neutral" type="button" aria-pressed={vista === 'vigenti'} onClick={() => cambiaVista('vigenti')}>Testi vigenti</Button>
          <Button tone="neutral" type="button" aria-pressed={vista === 'storico'} onClick={() => cambiaVista('storico')}>Archivio storico</Button>
        </div>
        {vista === 'vigenti' && riscontro ? <p role="status">Verifica al {dateIt(riscontro.data)} · {(riscontro.atti_esaminati ?? riscontro.atti_con_testo_verificato).toLocaleString('it-IT')} edizioni esaminate · {riscontro.atti_con_testo_verificato.toLocaleString('it-IT')} atti con testo vigente{(riscontro.atti_esaminati ?? 0) < riscontro.atti_richiesti ? ` · ${(riscontro.atti_richiesti - (riscontro.atti_esaminati ?? 0)).toLocaleString('it-IT')} da verificare nel lotto` : ''}</p> : null}
        {!catalogueBusy ? <CodiciLeggiMaterie acts={acts} selected={act} onChoose={chooseAct} /> : null}
        <form onSubmit={e => { e.preventDefault(); setFilters({ act, query, article, category, offset: 0 }) }}>
          <label>Raccolta<select value={category} onChange={e => { const value = e.target.value; setCategory(value); setAct(''); setQuery(''); setArticle(''); setFilters({ act: '', query: '', article: '', category: value, offset: 0 }) }}><option value="">Tutte le raccolte</option>{Array.from(new Set(acts.map(a => a.category))).map(c => <option key={c}>{c}</option>)}</select></label>
          <label>Trova un codice o una legge<input value={catalogQuery} onChange={e => setCatalogQuery(e.target.value)} placeholder="Codice civile, privacy, lavoro…" /></label>
          <label>Codice o legge<select value={act} onChange={e => { chooseAct(e.target.value) }}><option value="">Tutti gli atti</option>{actOptions.map(a => <option key={a.id} value={a.id}>{a.label}</option>)}{visibleActs.length > 100 ? <option disabled>Usa «Trova un codice o una legge» per affinare l’elenco.</option> : null}</select></label>
          <label>Numero dell’articolo<input value={article} onChange={e => setArticle(e.target.value)} placeholder="2043, 416-bis, 473-bis.12" /></label>
          <label>Parole nel testo<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Risarcimento, responsabilità, termini…" /></label>
          <div className="iu-li-normativa-actions"><Button type="submit" disabled={busy}><Search size={16} aria-hidden="true"/>Cerca</Button><Button tone="neutral" type="button" onClick={reset}>Azzera</Button></div>
        </form>
      </section>
      {error ? <div role="alert" className="iu-li-warning">{error} <Button tone="neutral" onClick={() => setRetry(n => n + 1)}>Riprova</Button></div> : null}
      <div className="iu-li-normativa-workbench">
        <section className="iu-od-source-card iu-li-normativa-results" aria-label="Articoli trovati" aria-busy={busy}>
          <h2>{currentAct ? currentAct.label : filters.category || 'Tutti gli atti'}</h2>
          <p role="status">{busy ? 'Ricerca in corso…' : `${results.total.toLocaleString('it-IT')} ${results.total === 1 ? 'articolo trovato' : 'articoli trovati'}`}</p>
          {!busy && !results.items.length && !error ? <p>Nessun articolo corrisponde ai filtri. Modifica il codice, il numero o le parole cercate.</p> : null}
          {!busy ? <ul>{results.items.map(a => <li key={a.id}><button type="button" aria-pressed={selectedId === a.id} onClick={() => setSelectedId(a.id)}><span>Art. {a.number}</span><strong>{a.title || 'Senza rubrica'}</strong><small>{a.act_title.split(' — ')[0]}</small></button></li>)}</ul> : null}
          <nav aria-label="Pagine degli articoli" className="iu-li-normativa-actions"><Button tone="neutral" disabled={busy || !filters.offset} onClick={() => setFilters({ ...filters, offset: Math.max(0, filters.offset - pageSize) })}>Precedente</Button><span>{results.total ? `${filters.offset + 1}–${Math.min(filters.offset + pageSize, results.total)}` : '0'}</span><Button tone="neutral" disabled={busy || filters.offset + pageSize >= results.total} onClick={() => setFilters({ ...filters, offset: filters.offset + pageSize })}>Successiva</Button></nav>
        </section>
        <section className="iu-od-source-card iu-li-normativa-reader" aria-label="Testo integrale dell’articolo" aria-busy={readerBusy}>
          {readerBusy ? <p role="status">Apertura dell’articolo…</p> : readerError ? <p role="alert">{readerError}</p> : selected ? <>
            <header><div><p>{selected.act_label || selected.act_title}</p><h2>Art. {selected.number}{selected.title ? ` — ${selected.title}` : ''}</h2></div><Button tone="neutral" aria-label="Chiudi articolo" onClick={() => { setSelected(null); setSelectedId(0) }}><X size={16}/></Button></header>
            <div className="iu-li-normativa-actions"><Badge tone="neutral">{selected.text_quality === 'avviso_abrogazione' ? 'Avviso di abrogazione nella fonte' : selected.only_heading ? 'Solo intestazione nella fonte' : /parte di provvedimento in formato grafico/i.test(selected.text) ? 'Testo con parti grafiche' : 'Testo dell’articolo'}</Badge>{selected.source_requested_at ? <span>Testo richiesto alla fonte per il {dateIt(selected.source_requested_at)}</span> : null}{selected.consolidated_at ? <span>{selected.version_date_scope === 'contenitore_akn' ? 'Data dichiarata nel contenitore XML' : 'Data della versione archiviata'}: {dateIt(selected.consolidated_at)}</span> : null}{selected.verified_as_of ? <span>Testo verificato al {dateIt(selected.verified_as_of)}</span> : null}<NormativeArticleLink url={selected.source_url} article={selected.number} articleId={selected.id} label="Articolo e provenienza">Articolo e provenienza <ExternalLink size={14} aria-hidden="true"/></NormativeArticleLink></div>
            {selected.version_date_scope === 'contenitore_akn' ? <p className="iu-li-normativa-date-note">La data del contenitore XML non indica la data dell’ultima modifica di ogni articolo. La data richiesta alla fonte è indicata separatamente.</p> : null}{selected.temporal_evidence ? <aside aria-label="Riscontro sugli effetti nel tempo">
              <strong>Effetti nel tempo · {dateIt(selected.temporal_evidence.data)}</strong>
              <p>{selected.temporal_evidence.nota}</p>
            </aside> : null}
            <div className="iu-li-normativa-text">{selected.text}</div>{selected.text_quality === 'avviso_abrogazione' ? <p>Questa edizione contiene un avviso sostitutivo, non il testo storico dell’articolo.</p> : selected.only_heading ? <p>La fonte ufficiale acquisita contiene soltanto l’intestazione per questo numero. Verifica il collegamento ufficiale; qui non viene ricostruito un testo mancante.</p> : null}
          </> : <div className="iu-li-normativa-empty"><BookOpen size={32} aria-hidden="true"/><h2>Leggi l’articolo qui</h2><p>Scegli un codice o una legge e apri un risultato per consultarne il testo completo.</p></div>}
        </section>
      </div>
    </div>
  </Page>
}
