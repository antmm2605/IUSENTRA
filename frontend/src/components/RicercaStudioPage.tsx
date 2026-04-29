import {
  BookOpen,
  BriefcaseBusiness,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Command,
  Copy,
  DatabaseZap,
  FileText,
  FolderOpen,
  Grid2X2,
  History,
  Inbox,
  Keyboard,
  Loader2,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Star,
  UsersRound,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from 'react'
import {
  emptyStudioSearchPayload,
  formatLastIndexed,
  loadStudioSearchStats,
  reindexStudioSearch,
  searchStudio,
  type SearchType,
  type StudioSearchFilter,
  type StudioSearchPayload,
  type StudioSearchResult,
  type StudioSearchStats,
} from '../searchData'

const filters: StudioSearchFilter[] = [
  { key: 'all', label: 'Tutto', icon: <Grid2X2 size={15} /> },
  { key: 'fascicoli', label: 'Fascicoli', icon: <FolderOpen size={15} /> },
  { key: 'clienti', label: 'Clienti', icon: <UsersRound size={15} /> },
  { key: 'scadenze', label: 'Scadenze', icon: <Clock3 size={15} /> },
  { key: 'documenti', label: 'Documenti', icon: <FileText size={15} /> },
  { key: 'comunicazioni', label: 'Comunicazioni', icon: <Inbox size={15} /> },
  { key: 'economia', label: 'Economia', icon: <ClipboardCheck size={15} /> },
  { key: 'telematico', label: 'Telematico', icon: <Send size={15} /> },
]

const typeLabels: Record<Exclude<SearchType, 'all'>, string> = {
  fascicoli: 'Fascicolo',
  clienti: 'Cliente',
  scadenze: 'Scadenza',
  documenti: 'Documento',
  comunicazioni: 'Comunicazione',
  economia: 'Economia',
  telematico: 'Telematico',
}

const typeIcons: Record<Exclude<SearchType, 'all'>, ReactNode> = {
  fascicoli: <FolderOpen size={16} />,
  clienti: <UsersRound size={16} />,
  scadenze: <Clock3 size={16} />,
  documenti: <FileText size={16} />,
  comunicazioni: <Inbox size={16} />,
  economia: <ClipboardCheck size={16} />,
  telematico: <Send size={16} />,
}

const suggestions = ['N.RG 139/2023', 'fattura proforma', 'deposito memoria', 'PEC cancelleria']

type RicercaStudioPageProps = {
  initialQuery?: string
}

export function RicercaStudioPage({ initialQuery = '' }: RicercaStudioPageProps) {
  const [query, setQuery] = useState(initialQuery)
  const [activeFilter, setActiveFilter] = useState<SearchType>('all')
  const [payload, setPayload] = useState<StudioSearchPayload>(emptyStudioSearchPayload)
  const [stats, setStats] = useState<StudioSearchStats>(emptyStudioSearchPayload.stats)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [isIndexing, setIsIndexing] = useState(false)
  const [copied, setCopied] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const results = payload.results
  const activeResult = useMemo(() => {
    if (!results.length) return null
    return results.find((item) => item.id === selectedId) ?? results[0]
  }, [results, selectedId])

  useEffect(() => {
    let alive = true
    loadStudioSearchStats().then((nextStats) => {
      if (alive) setStats(nextStats)
    })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    const value = query.trim()
    if (!value) {
      setPayload(emptyStudioSearchPayload)
      setSelectedId(null)
      return
    }

    let alive = true
    const timer = window.setTimeout(() => {
      setLoading(true)
      searchStudio(value, activeFilter)
        .then((nextPayload) => {
          if (!alive) return
          setPayload(nextPayload)
          setStats(nextPayload.stats)
          setSelectedId(nextPayload.results[0]?.id ?? null)
        })
        .finally(() => {
          if (alive) setLoading(false)
        })
    }, 180)

    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [activeFilter, query])

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent) => {
      const isSearchShortcut = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k'
      if (isSearchShortcut) {
        event.preventDefault()
        inputRef.current?.focus()
      }
      if (event.key === 'Escape') setQuery('')
    }

    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  const handleKeyboard = (event: KeyboardEvent<HTMLElement>) => {
    if (!results.length) return
    const currentIndex = Math.max(0, results.findIndex((item) => item.id === activeResult?.id))
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setSelectedId(results[Math.min(results.length - 1, currentIndex + 1)].id)
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setSelectedId(results[Math.max(0, currentIndex - 1)].id)
    }
    if (event.key === 'Enter' && activeResult?.href) {
      window.location.href = activeResult.href
    }
  }

  const handleReindex = async () => {
    setIsIndexing(true)
    try {
      const nextStats = await reindexStudioSearch()
      setStats(nextStats)
      if (query.trim()) setPayload(await searchStudio(query.trim(), activeFilter))
    } finally {
      setIsIndexing(false)
    }
  }

  const handleCopyLink = async () => {
    const href = activeResult?.href
    if (!href) return
    const absolute = new URL(href, window.location.origin).toString()
    await navigator.clipboard?.writeText(absolute)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <main className="iu-search-page" aria-label="Ricerca Studio" onKeyDown={handleKeyboard}>
      <Hero indexedCount={stats.total} ftsEnabled={stats.ftsEnabled} lastIndexedAt={stats.lastIndexedAt} />

      <div className="iu-search-layout">
        <section className="iu-search-card" aria-label="Motore di ricerca dello studio">
          <SearchBox
            refElement={inputRef}
            value={query}
            onChange={setQuery}
            placeholder="Cerca RG, cliente, codice fiscale, documento, scadenza, fattura..."
          />

          <FilterBar active={activeFilter} onChange={setActiveFilter} />

          <SearchMeta
            query={query}
            count={payload.total}
            tookMs={payload.tookMs}
            loading={loading}
            indexing={isIndexing}
            onReindex={handleReindex}
          />

          <ResultsArea
            query={query}
            results={results}
            activeId={activeResult?.id ?? null}
            loading={loading}
            error={payload.error}
            onSelect={setSelectedId}
            onSuggestionClick={setQuery}
          />
        </section>

        <PreviewPanel
          result={activeResult}
          hasQuery={Boolean(query.trim())}
          copied={copied}
          onCopyLink={handleCopyLink}
        />
      </div>
    </main>
  )
}

function Hero({ indexedCount, ftsEnabled, lastIndexedAt }: { indexedCount: number; ftsEnabled: boolean; lastIndexedAt: string }) {
  return (
    <section className="iu-search-hero">
      <div className="iu-search-hero__content">
        <span className="iu-search-hero__eyebrow">
          <Search size={14} />
          Ricerca Studio
        </span>
        <h1>Trova tutto ciò che serve allo studio</h1>
        <p>Fascicoli, clienti, scadenze, documenti, comunicazioni, economia e dati telematici in un unico punto.</p>
      </div>
      <div className="iu-search-hero__badges" aria-label="Stato indicizzazione">
        <StatusBadge icon={<DatabaseZap size={14} />} label={`${indexedCount} elementi indicizzati`} />
        <StatusBadge icon={<ShieldCheck size={14} />} label={ftsEnabled ? 'FTS5 attivo' : 'Ricerca compatibile'} />
        <StatusBadge icon={<CheckCircle2 size={14} />} label={formatLastIndexed(lastIndexedAt)} muted />
      </div>
    </section>
  )
}

function StatusBadge({ icon, label, muted }: { icon: ReactNode; label: string; muted?: boolean }) {
  return (
    <span className={`iu-search-status ${muted ? 'is-muted' : ''}`}>
      {icon}
      {label}
    </span>
  )
}

function SearchBox({
  refElement,
  value,
  onChange,
  placeholder,
}: {
  refElement: RefObject<HTMLInputElement | null>
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <label className="iu-search-box">
      <Search className="iu-search-box__icon" size={23} />
      <input
        ref={refElement}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label="Cerca nello studio"
      />
      {value ? (
        <button type="button" className="iu-search-box__clear" onClick={() => onChange('')} aria-label="Cancella ricerca">
          <X size={16} />
        </button>
      ) : (
        <kbd>Ctrl K</kbd>
      )}
    </label>
  )
}

function FilterBar({ active, onChange }: { active: SearchType; onChange: (filter: SearchType) => void }) {
  return (
    <div className="iu-search-filterbar" role="tablist" aria-label="Filtra risultati">
      {filters.map((filter) => (
        <button
          key={filter.key}
          type="button"
          className={`iu-search-chip ${active === filter.key ? 'is-active' : ''}`}
          onClick={() => onChange(filter.key)}
          role="tab"
          aria-selected={active === filter.key}
        >
          {filter.icon}
          {filter.label}
        </button>
      ))}
    </div>
  )
}

function SearchMeta({
  query,
  count,
  tookMs,
  loading,
  indexing,
  onReindex,
}: {
  query: string
  count: number
  tookMs: number
  loading: boolean
  indexing: boolean
  onReindex: () => void
}) {
  const hasQuery = Boolean(query.trim())
  return (
    <div className="iu-search-meta">
      <div>
        <strong>{hasQuery ? count : 0} risultati</strong>
        <span>{hasQuery ? ` per "${query.trim()}" in ${Math.max(0, Math.round(tookMs))} ms` : ' in 0 ms'}</span>
        {loading ? <Loader2 className="iu-search-spin" size={15} aria-label="Ricerca in corso" /> : null}
      </div>
      <div className="iu-search-meta__actions">
        <button className="iu-search-ghost" type="button">
          <History size={15} />
          Ricerche recenti
        </button>
        <button className="iu-search-ghost" type="button" onClick={onReindex} disabled={indexing}>
          <RefreshCw size={15} className={indexing ? 'iu-search-spin' : ''} />
          {indexing ? 'Indicizzazione...' : 'Reindicizza'}
        </button>
      </div>
    </div>
  )
}

function ResultsArea({
  query,
  results,
  activeId,
  loading,
  error,
  onSelect,
  onSuggestionClick,
}: {
  query: string
  results: StudioSearchResult[]
  activeId: string | null
  loading: boolean
  error?: string
  onSelect: (id: string) => void
  onSuggestionClick: (value: string) => void
}) {
  const hasQuery = Boolean(query.trim())

  if (!hasQuery) {
    return (
      <div className="iu-search-empty">
        <div className="iu-search-empty__icon">
          <Search size={34} />
          <Star size={15} />
        </div>
        <h2>Inizia da una parola chiave</h2>
        <p>Cerca in fascicoli, clienti, documenti, scadenze, agenda, economia, comunicazioni e dati telematici indicizzati.</p>
        <div className="iu-search-suggestions" aria-label="Suggerimenti ricerca">
          {suggestions.map((term) => (
            <button key={term} type="button" onClick={() => onSuggestionClick(term)}>
              {term}
            </button>
          ))}
        </div>
      </div>
    )
  }

  if (loading && !results.length) {
    return (
      <div className="iu-search-empty is-compact">
        <div className="iu-search-empty__icon">
          <Loader2 className="iu-search-spin" size={34} />
        </div>
        <h2>Ricerca in corso</h2>
        <p>Sto interrogando l'indice reale dello studio.</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="iu-search-empty is-compact">
        <div className="iu-search-empty__icon warning">
          <Search size={31} />
        </div>
        <h2>Ricerca non disponibile</h2>
        <p>{error}</p>
      </div>
    )
  }

  if (!results.length) {
    return (
      <div className="iu-search-empty is-compact">
        <div className="iu-search-empty__icon warning">
          <Search size={31} />
        </div>
        <h2>Nessun risultato trovato</h2>
        <p>Prova con RG, codice fiscale, nome cliente, numero fattura, oggetto PEC o parola presente nel documento.</p>
      </div>
    )
  }

  return (
    <div className="iu-search-results" aria-label="Risultati ricerca">
      {results.map((result) => (
        <ResultCard
          key={result.id}
          result={result}
          active={activeId === result.id}
          onClick={() => onSelect(result.id)}
        />
      ))}
    </div>
  )
}

function ResultCard({ result, active, onClick }: { result: StudioSearchResult; active: boolean; onClick: () => void }) {
  return (
    <button className={`iu-search-result ${active ? 'is-active' : ''}`} type="button" onClick={onClick}>
      <span className="iu-search-result__icon">{typeIcons[result.type]}</span>
      <span className="iu-search-result__body">
        <span className="iu-search-result__topline">
          <strong>{result.title}</strong>
          <ResultStatus status={result.status} />
        </span>
        <span className="iu-search-result__subtitle">{result.subtitle}</span>
        <span className="iu-search-result__meta">{result.meta}</span>
        <span className="iu-search-result__tags">
          {result.tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </span>
      </span>
      <span className="iu-search-result__updated">{result.updatedAt}</span>
    </button>
  )
}

function ResultStatus({ status }: { status?: string }) {
  if (!status) return null
  const normalized = status.toLowerCase()
  const tone =
    normalized.includes('urgent') || normalized.includes('alta') ? 'urgente' :
    normalized.includes('complet') || normalized.includes('pagat') ? 'completato' :
    normalized.includes('archiv') ? 'archiviato' :
    'aperto'
  return <span className={`iu-search-result-status ${tone}`}>{status}</span>
}

function PreviewPanel({
  result,
  hasQuery,
  copied,
  onCopyLink,
}: {
  result: StudioSearchResult | null
  hasQuery: boolean
  copied: boolean
  onCopyLink: () => void
}) {
  if (!result) {
    return (
      <aside className="iu-search-preview" aria-label="Anteprima risultato">
        <span className="iu-search-preview__label">Anteprima</span>
        <h2>Seleziona un risultato</h2>
        <p>Da qui puoi aprire subito fascicolo, cliente, documento, scadenza o comunicazione trovata nell'indice.</p>
        <div className="iu-search-preview__actions">
          <a className="iu-search-primary is-disabled" aria-disabled={!hasQuery}>
            Apri
          </a>
          <a className="iu-search-outline" href="/lex">
            <Sparkles size={15} />
            Chiedi a Lex
          </a>
        </div>
        <PreviewEnhancements />
      </aside>
    )
  }

  return (
    <aside className="iu-search-preview has-selection" aria-label="Anteprima risultato selezionato">
      <span className="iu-search-preview__label">Anteprima</span>
      <div className="iu-search-preview__title-row">
        <span className="iu-search-preview__type">{typeIcons[result.type]}</span>
        <div>
          <p>{typeLabels[result.type]}</p>
          <h2>{result.title}</h2>
        </div>
      </div>
      <p>{result.description}</p>

      <dl className="iu-search-facts">
        <div>
          <dt>Stato</dt>
          <dd>{result.status || 'Non indicato'}</dd>
        </div>
        <div>
          <dt>Riferimento</dt>
          <dd>{result.entityId || result.id}</dd>
        </div>
        <div>
          <dt>Ultimo aggiornamento</dt>
          <dd>{result.updatedAt}</dd>
        </div>
      </dl>

      <div className="iu-search-preview__actions">
        <a className="iu-search-primary" href={result.href}>Apri</a>
        <a className="iu-search-outline" href={`/lex?q=${encodeURIComponent(result.title)}`}>
          <Sparkles size={15} />
          Chiedi a Lex
        </a>
      </div>

      <div className="iu-search-preview__secondary-actions">
        <a href={result.fascicoloHref || result.href}>
          <FolderOpen size={14} />
          Vai al fascicolo
        </a>
        <button type="button" onClick={onCopyLink}>
          {copied ? <CheckCircle2 size={14} /> : <Copy size={14} />}
          {copied ? 'Link copiato' : 'Copia link'}
        </button>
      </div>

      <PreviewEnhancements />
    </aside>
  )
}

function PreviewEnhancements() {
  return (
    <div className="iu-search-enhancements" aria-label="Elementi integrati">
      <h3>Integrato in questa vista</h3>
      <ul>
        <li>
          <Command size={14} />
          Shortcut tastiera e focus rapido
        </li>
        <li>
          <ShieldCheck size={14} />
          Stato indice, FTS e ultimo sync
        </li>
        <li>
          <BookOpen size={14} />
          Fonti interne dello studio
        </li>
        <li>
          <BriefcaseBusiness size={14} />
          Azioni contestuali sui risultati
        </li>
        <li>
          <Keyboard size={14} />
          Frecce, Invio ed Esc
        </li>
      </ul>
    </div>
  )
}
