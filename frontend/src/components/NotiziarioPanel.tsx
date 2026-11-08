import { useBusyActivity } from '../ui/useBusyActivity'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BellRing,
  BookOpen,
  Briefcase,
  CalendarPlus,
  Check,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FolderPlus,
  Landmark,
  Maximize2,
  Minimize2,
  Newspaper,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  X,
} from 'lucide-react'
import { sanitizeDisplayText } from '../displayText'
import { formatDateIt, formatDateTimeIt } from '../formatting'
import {
  NOTIZIARIO_QUERY_INIZIALE,
  loadNotiziario,
  refreshNotiziario,
  loadNotiziarioSource,
  notiziarioEmptyPayload,
  updateNotiziarioInteraction,
  type NotiziarioItem,
  type NotiziarioPayload,
  type NotiziarioQuery,
  type NotiziarioQuickSource,
  type NotiziarioSourceReader,
} from '../notiziarioData'
import './NotiziarioPanel.css'

function visibleText(value: string, fallback = ''): string {
  return sanitizeDisplayText(value || fallback)
}

function sourceInitials(value: string): string {
  const parts = visibleText(value, 'Fonte').split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'FI'
}

function deadlineHref(item: NotiziarioItem): string {
  const params = new URLSearchParams()
  params.set('titolo', `Verifica aggiornamento: ${item.title}`)
  params.set('descrizione', [item.summary, item.sourceUrl ? `Fonte: ${item.sourceUrl}` : ''].filter(Boolean).join('\n\n'))
  params.set('note', `Aggiornamento da Notizie utili IUSENTRA (${item.sourceName}).`)
  if (item.linkedCaseId) params.set('id_fascicolo', item.linkedCaseId)
  return `/scadenziario/nuova?${params.toString()}`
}

/** Il vecchio formato (senza filtri lato server) resta leggibile: si filtra nel browser. */
function filtraNelBrowser(items: NotiziarioItem[], query: NotiziarioQuery): NotiziarioItem[] {
  const needle = query.q.trim().toLocaleLowerCase('it-IT')
  return items.filter((item) => {
    if (query.fonte && item.sourceGroup !== query.fonte) return false
    if (query.stato === 'unread' && item.read) return false
    if (query.stato === 'favorite' && !item.favorite) return false
    if (!needle) return true
    return [item.title, item.summary, item.sourceName, item.matterName].join(' ').toLocaleLowerCase('it-IT').includes(needle)
  })
}

export function NotiziarioPanel() {
  const [payload, setPayload] = useState<NotiziarioPayload>(notiziarioEmptyPayload)
  const [loading, setLoading] = useState(true)
  useBusyActivity(loading, 'Caricamento delle Notizie utili…')
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState<NotiziarioQuery>(NOTIZIARIO_QUERY_INIZIALE)
  const [searchText, setSearchText] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [busyId, setBusyId] = useState('')
  useBusyActivity(Boolean(busyId), 'Aggiornamento della notizia…')
  const [expanded, setExpanded] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [linking, setLinking] = useState(false)
  const [caseId, setCaseId] = useState('')
  const [webSource, setWebSource] = useState<NotiziarioQuickSource | null>(null)
  const [sourceReader, setSourceReader] = useState<NotiziarioSourceReader | null>(null)
  const [sourceLoading, setSourceLoading] = useState(false)
  useBusyActivity(sourceLoading, 'Apertura della fonte ufficiale…')
  const primoCaricamento = useRef(true)

  const serverSide = payload.facets.kinds.length > 0

  const acceptPayload = (next: NotiziarioPayload, append = false) => {
    // Le pagine successive portano solo le notizie: filtri, conteggi e fascicoli restano quelli della prima.
    setPayload((current) => (append
      ? { ...current, items: [...current.items, ...next.items], page: next.page, hasMore: next.hasMore, total: next.total }
      : next))
    if (!append) {
      setSelectedId((current) => (current && next.items.some((item) => item.id === current) ? current : next.items[0]?.id || ''))
    }
  }

  // La ricerca parte dopo una breve pausa di digitazione, non a ogni tasto.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery((current) => (current.q === searchText ? current : { ...current, q: searchText, pagina: 1 }))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [searchText])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    loadNotiziario(query)
      .then(async (next) => {
        if (!active) return
        acceptPayload(next)
        // Solo il vecchio formato chiede l'aggiornamento all'apertura; l'archivio lo tiene aggiornato la pianificazione.
        if (primoCaricamento.current && next.refreshRequired) {
          const refreshed = await refreshNotiziario(query)
          if (active) acceptPayload(refreshed)
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Notizie utili momentaneamente non disponibili.')
      })
      .finally(() => {
        primoCaricamento.current = false
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [query])

  useEffect(() => {
    if (!expanded) return undefined
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setExpanded(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    document.body.classList.add('iu-notiziario-open')
    return () => {
      document.removeEventListener('keydown', closeOnEscape)
      document.body.classList.remove('iu-notiziario-open')
    }
  }, [expanded])

  const refresh = () => {
    setLoading(true)
    setError('')
    refreshNotiziario({ ...query, pagina: 1 })
      .then((next) => acceptPayload(next))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Aggiornamento delle fonti non riuscito.'))
      .finally(() => setLoading(false))
  }

  const loadMore = () => {
    const next = { ...query, pagina: payload.page + 1 }
    setLoadingMore(true)
    loadNotiziario(next)
      .then((page) => acceptPayload(page, true))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Altre notizie non disponibili.'))
      .finally(() => setLoadingMore(false))
  }

  const changeQuery = (patch: Partial<NotiziarioQuery>) => setQuery((current) => ({ ...current, ...patch, pagina: 1 }))

  const items = useMemo(() => (serverSide ? payload.items : filtraNelBrowser(payload.items, query)), [payload.items, query, serverSide])
  const total = serverSide ? payload.total : items.length
  const selected = items.find((item) => item.id === selectedId) || items[0]
  const sourceOptions = serverSide
    ? payload.facets.sources
    : payload.filters.filter((filter) => filter.id !== 'all').map((filter) => ({ ...filter, count: 0 }))
  const failingSources = payload.sourceStates.filter((state) => state.checked && !state.ok)

  const replaceItem = (next: NotiziarioItem) => {
    setPayload((current) => ({
      ...current,
      items: current.items.map((item) => (item.id === next.id
        ? { ...item, read: next.read, readAt: next.readAt, favorite: next.favorite, linkedCaseId: next.linkedCaseId, linkedCaseLabel: next.linkedCaseLabel }
        : item)),
    }))
  }

  const updateItem = async (item: NotiziarioItem, patch: { read?: boolean; favorite?: boolean; linkedCaseId?: string }) => {
    setBusyId(item.id)
    setError('')
    try {
      replaceItem(await updateNotiziarioInteraction(item.id, patch))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Modifica non salvata.')
    } finally {
      setBusyId('')
    }
  }

  const selectItem = (item: NotiziarioItem) => {
    setSelectedId(item.id)
    setWebSource(null)
    setLinking(false)
    setCaseId(item.linkedCaseId)
    if (!item.read) void updateItem(item, { read: true })
  }

  const openQuickSource = (source: NotiziarioQuickSource) => {
    setWebSource(source)
    setSourceReader(null)
    setExpanded(true)
    if (source.requiresAuthentication || source.directOpen) {
      setSourceLoading(false)
      return
    }
    setSourceLoading(true)
    void loadNotiziarioSource(source)
      .then(setSourceReader)
      .catch(() => setSourceReader({
        ok: false,
        id: source.id,
        label: source.label,
        url: source.url,
        title: source.label,
        sourceName: source.label,
        blocks: [],
        message: 'Il sito istituzionale non è leggibile in questo momento. Usa il collegamento al sito ufficiale.',
        fetchedAt: '',
      }))
      .finally(() => setSourceLoading(false))
  }

  const toggleCollapsed = () => {
    if (!collapsed) setExpanded(false)
    setCollapsed((value) => !value)
  }

  return (
    <section className={`iu-notiziario ${expanded ? 'is-expanded' : ''} ${collapsed ? 'is-collapsed' : ''}`} aria-labelledby="iu-notiziario-title">
      <header className="iu-notiziario__header">
        <div>
          <span className="iu-notiziario__eyebrow"><Newspaper size={15} /> Informazione professionale</span>
          <h2 id="iu-notiziario-title">Notizie utili</h2>
          <p>Norme, pronunce, prassi e avvisi del processo telematico pubblicati dalle fonti istituzionali, con i fascicoli dello studio a cui possono servire.</p>
        </div>
        <div className="iu-notiziario__summary" aria-label="Stato delle Notizie utili">
          <span><BellRing size={15} /><strong>{payload.unreadCount}</strong> da leggere</span>
          {serverSide ? <span><Sparkles size={15} /><strong>{payload.newCount}</strong> pubblicate da ieri</span> : null}
          {serverSide ? <span><Briefcase size={15} /><strong>{payload.relevantCount}</strong> per i tuoi fascicoli</span> : null}
          <button type="button" onClick={refresh} disabled={loading} title="Interroga ora le fonti ufficiali">
            <RefreshCw size={16} className={loading ? 'is-spinning' : ''} />
            <span>Aggiorna</span>
          </button>
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            aria-pressed={expanded}
            title={expanded ? 'Chiudi tutto schermo' : 'Apri a tutto schermo'}
          >
            {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            <span>{expanded ? 'Riduci' : 'Tutto schermo'}</span>
          </button>
        </div>
      </header>

      <div className="iu-notiziario__toolbar">
        <label className="iu-notiziario__search">
          <Search size={16} />
          <span className="sr-only">Cerca nelle Notizie utili</span>
          <input value={searchText} onChange={(event) => setSearchText(event.currentTarget.value)} placeholder="Cerca titolo, ente, materia o estremi" />
          {searchText ? <button type="button" onClick={() => setSearchText('')} title="Cancella ricerca"><X size={14} /></button> : null}
        </label>
        {serverSide ? (
          <div className="iu-notiziario__filters" aria-label="Filtra per tipo di notizia">
            <button type="button" className={!query.tipo ? 'is-active' : ''} aria-pressed={!query.tipo} onClick={() => changeQuery({ tipo: '' })}>Tutti i tipi</button>
            {payload.facets.kinds.map((kind) => (
              <button
                type="button"
                key={kind.id}
                className={query.tipo === kind.id ? 'is-active' : ''}
                aria-pressed={query.tipo === kind.id}
                onClick={() => changeQuery({ tipo: query.tipo === kind.id ? '' : kind.id })}
              >
                {visibleText(kind.label)} <span className="iu-notiziario__count">{kind.count}</span>
              </button>
            ))}
          </div>
        ) : <div />}
        <div className="iu-notiziario__status-filters" aria-label="Filtra per stato">
          <button type="button" className={query.stato === 'all' ? 'is-active' : ''} onClick={() => changeQuery({ stato: 'all' })}>Tutte</button>
          <button type="button" className={query.stato === 'unread' ? 'is-active' : ''} onClick={() => changeQuery({ stato: 'unread' })}>Da leggere</button>
          <button type="button" className={query.stato === 'favorite' ? 'is-active' : ''} onClick={() => changeQuery({ stato: 'favorite' })}>Preferite</button>
        </div>
      </div>

      <div className="iu-notiziario__refine">
        <label>
          <span>Fonte</span>
          <select value={query.fonte} onChange={(event) => changeQuery({ fonte: event.currentTarget.value })}>
            <option value="">Tutte le fonti</option>
            {sourceOptions.map((source) => (
              <option value={source.id} key={source.id}>{visibleText(source.label)}{serverSide ? ` (${source.count})` : ''}</option>
            ))}
          </select>
        </label>
        {serverSide ? (
          <label>
            <span>Materia</span>
            <select value={query.materia} onChange={(event) => changeQuery({ materia: event.currentTarget.value })}>
              <option value="">Tutte le materie</option>
              {payload.facets.matters.map((matter) => (
                <option value={matter.id} key={matter.id}>{visibleText(matter.label)} ({matter.count})</option>
              ))}
            </select>
          </label>
        ) : null}
        {serverSide ? (
          <div className="iu-notiziario__toggles" aria-label="Restringi l’elenco">
            <button type="button" className={query.pertinenti ? 'is-active' : ''} aria-pressed={query.pertinenti} onClick={() => changeQuery({ pertinenti: !query.pertinenti })}>
              <Briefcase size={14} /> Per i miei fascicoli
            </button>
            <button type="button" className={query.nuove ? 'is-active' : ''} aria-pressed={query.nuove} onClick={() => changeQuery({ nuove: !query.nuove })}>
              <Sparkles size={14} /> Pubblicate da ieri
            </button>
          </div>
        ) : null}
        {payload.refreshedAt ? <small className="iu-notiziario__refreshed">Ultimo controllo delle fonti: {formatDateTimeIt(payload.refreshedAt)}</small> : null}
      </div>

      {error ? <div className="iu-notiziario__message is-error" role="alert">{visibleText(error)}</div> : null}

      <div className="iu-notiziario__workspace">
        <div className="iu-notiziario__feed" aria-label="Elenco delle notizie">
          <div className="iu-notiziario__feed-heading">
            <strong>{total} {total === 1 ? 'notizia' : 'notizie'}</strong>
            <span>{payload.unreadCount} da leggere</span>
          </div>
          {loading ? (
            <div className="iu-notiziario__loading" role="status">
              <span /><span /><span /><span />
            </div>
          ) : items.length ? (
            <>
              {items.map((item) => (
                <div className={`iu-notiziario-row ${selected?.id === item.id && !webSource ? 'is-selected' : ''} ${item.read ? 'is-read' : 'is-unread'}`} key={item.id}>
                  <button type="button" className="iu-notiziario-row__main" onClick={() => selectItem(item)}>
                    <span className="iu-notiziario-row__source" aria-hidden="true">{sourceInitials(item.sourceName)}</span>
                    <span className="iu-notiziario-row__copy">
                      <span className="iu-notiziario-row__meta">
                        <b>{visibleText(item.sourceName)}</b>
                        <time dateTime={item.publishedAt}>{formatDateIt(item.publishedAt, 'Data non disponibile')}</time>
                      </span>
                      <strong>{visibleText(item.title)}</strong>
                      {item.summary ? <small>{visibleText(item.summary)}</small> : null}
                      <span className="iu-notiziario-row__tags">
                        {item.kindLabel ? <em className={`iu-notiziario-tag is-${item.kind}`}>{visibleText(item.kindLabel)}</em> : null}
                        {item.isNew ? <em className="iu-notiziario-tag is-new">Nuova</em> : null}
                        {item.relatedCases.length ? (
                          <em className="iu-notiziario-tag is-cases">
                            {item.relatedCases.length === 1 ? '1 fascicolo pertinente' : `${item.relatedCases.length} fascicoli pertinenti`}
                          </em>
                        ) : null}
                      </span>
                    </span>
                    {!item.read ? <i aria-label="Da leggere" /> : null}
                  </button>
                  <button
                    type="button"
                    className={`iu-notiziario-row__favorite ${item.favorite ? 'is-active' : ''}`}
                    onClick={() => void updateItem(item, { favorite: !item.favorite })}
                    aria-pressed={item.favorite}
                    disabled={busyId === item.id}
                    title={item.favorite ? 'Rimuovi dai preferiti' : 'Aggiungi ai preferiti'}
                  >
                    <Star size={16} fill={item.favorite ? 'currentColor' : 'none'} />
                  </button>
                </div>
              ))}
              {serverSide && payload.hasMore ? (
                <button type="button" className="iu-notiziario__more" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? 'Caricamento…' : `Mostra altre notizie (${total - items.length} rimanenti)`}
                </button>
              ) : null}
            </>
          ) : (
            <div className="iu-notiziario__empty">
              <Newspaper size={24} />
              <strong>Nessuna notizia con questi filtri</strong>
              <span>Togli un filtro o cambia la ricerca per tornare all’elenco completo.</span>
            </div>
          )}
        </div>

        <article className="iu-notiziario__reader" aria-live="polite">
          {webSource ? (
            <>
              <div className="iu-notiziario__reader-head">
                <button type="button" onClick={() => setWebSource(null)}><ChevronLeft size={16} /> Torna alle Notizie utili</button>
                <span>Fonte ufficiale</span>
              </div>
              <div className="iu-notiziario__reader-title">
                <span className="iu-notiziario__source-mark"><Landmark size={19} /></span>
                <div><small>{webSource.requiresAuthentication ? 'Accesso protetto con credenziali personali' : 'Notizie e comunicazioni ufficiali'}</small><h3>{webSource.label}</h3></div>
              </div>
              <div className="iu-notiziario__web-reader" aria-live="polite">
                {webSource.directOpen ? (
                  <div className="iu-notiziario__source-state">
                    <ExternalLink size={20} />
                    <strong>Consulta la pubblicazione ufficiale</strong>
                    <span>La Gazzetta Ufficiale si apre dalla fonte istituzionale, così visualizzi sempre l’edizione corrente.</span>
                  </div>
                ) : webSource.requiresAuthentication ? (
                  <div className="iu-notiziario__source-state">
                    <Landmark size={20} />
                    <strong>Area riservata dell’Agenzia delle Entrate</strong>
                    <span>Per accedere a Fatture e Corrispettivi sono necessarie le credenziali personali abilitate. IUSENTRA non acquisisce né conserva tali credenziali.</span>
                  </div>
                ) : sourceLoading ? (
                  <div className="iu-notiziario__source-state" role="status"><RefreshCw className="is-spinning" size={20} /><strong>Apertura della fonte in corso…</strong><span>Sto preparando una lettura interna del sito istituzionale.</span></div>
                ) : sourceReader?.ok && sourceReader.blocks.length ? (
                  <div className="iu-notiziario__source-copy">
                    {sourceReader.blocks.map((block, index) => <p key={`${webSource.id}-${index}`}>{visibleText(block)}</p>)}
                  </div>
                ) : (
                  <div className="iu-notiziario__source-state is-warning" role="alert"><ExternalLink size={20} /><strong>Fonte non leggibile nel pannello</strong><span>{visibleText(sourceReader?.message || '', 'Usa il collegamento al sito ufficiale per consultare il contenuto.')}</span></div>
                )}
              </div>
              <a className="iu-notiziario__original" href={webSource.url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> {webSource.requiresAuthentication ? 'Apri l’accesso ufficiale' : webSource.directOpen ? 'Apri la Gazzetta Ufficiale' : 'Apri il sito ufficiale'}</a>
            </>
          ) : selected ? (
            <>
              <div className="iu-notiziario__reader-head">
                <span>{visibleText(selected.sourceName)}</span>
                <time dateTime={selected.publishedAt}>{formatDateIt(selected.publishedAt, 'Data non disponibile')}</time>
              </div>
              <div className="iu-notiziario__reader-title">
                <span className="iu-notiziario__source-mark">{sourceInitials(selected.sourceName)}</span>
                <div>
                  <small>{[selected.kindLabel, selected.matterName].filter(Boolean).map((value) => visibleText(value)).join(' · ') || 'Aggiornamento istituzionale'}</small>
                  <h3>{visibleText(selected.title)}</h3>
                </div>
              </div>
              {selected.authority || selected.officialReference ? (
                <dl className="iu-notiziario__provenance">
                  {selected.authority ? <><dt>Ente</dt><dd>{visibleText(selected.authority)}</dd></> : null}
                  {selected.officialReference ? <><dt>Riferimento</dt><dd>{visibleText(selected.officialReference)}</dd></> : null}
                </dl>
              ) : null}
              <p className="iu-notiziario__lead">{visibleText(selected.summary, 'La fonte non pubblica una descrizione: apri il testo ufficiale.')}</p>
              {selected.content && selected.content !== selected.summary ? (
                <div className="iu-notiziario__article-copy">
                  {selected.content.split(/\n+/).filter(Boolean).map((paragraph, index) => <p key={`${selected.id}-${index}`}>{visibleText(paragraph)}</p>)}
                </div>
              ) : null}
              {selected.relatedCases.length ? (
                <section className="iu-notiziario__related" aria-label="Fascicoli dello studio a cui può servire">
                  <h4><Briefcase size={15} /> Fascicoli dello studio a cui può servire</h4>
                  <ul>
                    {selected.relatedCases.map((related) => (
                      <li key={related.id}>
                        <a href={`/fascicoli/${encodeURIComponent(related.id)}`}>{visibleText(related.label)}</a>
                        <span>{visibleText(related.reason)}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {selected.linkedCaseLabel ? (
                <div className="iu-notiziario__linked"><FolderPlus size={15} /><span>Collegato a</span><strong>{visibleText(selected.linkedCaseLabel)}</strong></div>
              ) : null}
              {linking ? (
                <div className="iu-notiziario__case-linker">
                  <label htmlFor={`notiziario-case-${selected.id}`}>Fascicolo</label>
                  <select id={`notiziario-case-${selected.id}`} value={caseId} onChange={(event) => setCaseId(event.currentTarget.value)}>
                    <option value="">Nessun collegamento</option>
                    {payload.cases.map((item) => <option value={item.id} key={item.id}>{visibleText(item.label)}</option>)}
                  </select>
                  <button type="button" onClick={() => void updateItem(selected, { linkedCaseId: caseId }).then(() => setLinking(false))} disabled={busyId === selected.id}><Check size={15} /> Salva</button>
                  <button type="button" onClick={() => setLinking(false)}>Annulla</button>
                </div>
              ) : null}
              <div className="iu-notiziario__actions">
                {!expanded ? <button type="button" onClick={() => setExpanded(true)}><BookOpen size={16} /> Leggi a tutto schermo</button> : null}
                <button type="button" onClick={() => { setCaseId(selected.relatedCases[0]?.id || selected.linkedCaseId); setLinking(true) }}><FolderPlus size={16} /> Collega a fascicolo</button>
                <a href={deadlineHref(selected)}><CalendarPlus size={16} /> Crea scadenza</a>
                <button type="button" onClick={() => void updateItem(selected, { read: !selected.read })} disabled={busyId === selected.id}>
                  <Check size={16} /> {selected.read ? 'Segna da leggere' : 'Segna come letta'}
                </button>
              </div>
              {selected.sourceUrl ? <a className="iu-notiziario__original" href={selected.sourceUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Apri il testo ufficiale</a> : null}
            </>
          ) : (
            <div className="iu-notiziario__empty is-reader"><BookOpen size={28} /><strong>Seleziona una notizia</strong><span>Il testo pubblicato dall’ente si apre qui, senza lasciare la Panoramica.</span></div>
          )}
        </article>
      </div>

      <footer className="iu-notiziario__quick-sources">
        <strong>Fonti rapide</strong>
        <div>
          {payload.quickSources.map((source) => (
            <button
              type="button"
              key={source.id}
              className={webSource?.id === source.id ? 'is-active' : ''}
              aria-pressed={webSource?.id === source.id}
              title={source.directOpen ? `Apri ${visibleText(source.label)}` : `Consulta ${visibleText(source.label)}`}
              onClick={() => openQuickSource(source)}
            >
              <Landmark size={15} /> {visibleText(source.label)}
            </button>
          ))}
        </div>
      </footer>
      {payload.sourceStates.length ? (
        <details className="iu-notiziario__sources-state">
          <summary>
            Stato delle fonti ufficiali: {payload.sourceStates.filter((state) => state.ok).length} aggiornate
            {failingSources.length ? `, ${failingSources.length} non raggiungibili all’ultimo controllo` : ''}
          </summary>
          <ul>
            {payload.sourceStates.map((state) => (
              <li key={state.id} className={state.checked && !state.ok ? 'is-failing' : ''}>
                <a href={state.url} target="_blank" rel="noreferrer">{visibleText(state.label)}</a>
                <span>{visibleText(state.authority)}</span>
                <span>
                  {!state.checked ? 'Non ancora interrogata' : state.ok ? 'Aggiornata' : visibleText(state.message, 'Non raggiungibile')}
                  {state.latestPublishedAt ? ` · ultima notizia del ${formatDateIt(state.latestPublishedAt)}` : ''}
                  {state.count ? ` · ${state.count} in archivio` : ''}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      <button
        type="button"
        className="iu-notiziario__collapse"
        onClick={toggleCollapsed}
        aria-expanded={!collapsed}
        title={collapsed ? 'Apri Notizie utili' : 'Chiudi Notizie utili'}
      >
        {collapsed ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        <span className="sr-only">{collapsed ? 'Apri Notizie utili' : 'Chiudi Notizie utili'}</span>
      </button>
    </section>
  )
}
