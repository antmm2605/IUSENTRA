import { useEffect, useMemo, useState } from 'react'
import {
  BellRing,
  BookOpen,
  CalendarPlus,
  Check,
  ChevronLeft,
  ExternalLink,
  FolderPlus,
  Landmark,
  Maximize2,
  Minimize2,
  Newspaper,
  RefreshCw,
  Search,
  Star,
  X,
} from 'lucide-react'
import { sanitizeDisplayText } from '../displayText'
import { formatDateIt } from '../formatting'
import {
  loadNotiziario,
  loadNotiziarioSource,
  notiziarioEmptyPayload,
  updateNotiziarioInteraction,
  type NotiziarioItem,
  type NotiziarioQuickSource,
  type NotiziarioSourceReader,
} from '../notiziarioData'
import './NotiziarioPanel.css'

type StatusFilter = 'all' | 'unread' | 'favorite'

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
  params.set('note', `Aggiornamento dal Notiziario IUSENTRA (${item.sourceName}).`)
  if (item.linkedCaseId) params.set('id_fascicolo', item.linkedCaseId)
  return `/scadenziario/nuova?${params.toString()}`
}

export function NotiziarioPanel() {
  const [payload, setPayload] = useState(notiziarioEmptyPayload)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [selectedId, setSelectedId] = useState('')
  const [busyId, setBusyId] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [linking, setLinking] = useState(false)
  const [caseId, setCaseId] = useState('')
  const [webSource, setWebSource] = useState<NotiziarioQuickSource | null>(null)
  const [sourceReader, setSourceReader] = useState<NotiziarioSourceReader | null>(null)
  const [sourceLoading, setSourceLoading] = useState(false)

  const refresh = () => {
    setLoading(true)
    setError('')
    loadNotiziario()
      .then((next) => {
        setPayload(next)
        setSelectedId((current) => current && next.items.some((item) => item.id === current) ? current : next.items[0]?.id || '')
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Notiziario momentaneamente non disponibile.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    refresh()
  }, [])

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

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('it-IT')
    return payload.items.filter((item) => {
      if (sourceFilter !== 'all' && item.sourceGroup !== sourceFilter) return false
      if (statusFilter === 'unread' && item.read) return false
      if (statusFilter === 'favorite' && !item.favorite) return false
      if (!needle) return true
      return [item.title, item.summary, item.sourceName, item.matterName, item.submatterName]
        .join(' ')
        .toLocaleLowerCase('it-IT')
        .includes(needle)
    })
  }, [payload.items, query, sourceFilter, statusFilter])

  const selected = payload.items.find((item) => item.id === selectedId) || filteredItems[0] || payload.items[0]
  const unreadCount = payload.items.filter((item) => !item.read).length

  const replaceItem = (next: NotiziarioItem) => {
    setPayload((current) => ({
      ...current,
      items: current.items.map((item) => item.id === next.id ? next : item),
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

  const openCaseLink = () => {
    if (!selected) return
    setCaseId(selected.linkedCaseId)
    setLinking(true)
  }

  const openQuickSource = (source: NotiziarioQuickSource) => {
    setWebSource(source)
    setSourceReader(null)
    setSourceLoading(true)
    setExpanded(true)
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

  return (
    <section className={`iu-notiziario ${expanded ? 'is-expanded' : ''}`} aria-labelledby="iu-notiziario-title">
      <header className="iu-notiziario__header">
        <div>
          <span className="iu-notiziario__eyebrow"><Newspaper size={15} /> Informazione professionale</span>
          <h2 id="iu-notiziario-title">Notiziario</h2>
          <p>Aggiornamenti pubblicati dalle fonti istituzionali, pronti da leggere e collegare al lavoro dello studio.</p>
        </div>
        <div className="iu-notiziario__summary" aria-label="Stato del Notiziario">
          <span><BellRing size={15} /><strong>{unreadCount}</strong> da leggere</span>
          <button type="button" onClick={refresh} disabled={loading} title="Aggiorna il Notiziario">
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
          <span className="sr-only">Cerca nel Notiziario</span>
          <input value={query} onChange={(event) => setQuery(event.currentTarget.value)} placeholder="Cerca titolo, materia o fonte" />
          {query ? <button type="button" onClick={() => setQuery('')} title="Cancella ricerca"><X size={14} /></button> : null}
        </label>
        <div className="iu-notiziario__filters" aria-label="Filtra per fonte">
          {payload.filters.map((filter) => (
            <button
              type="button"
              key={filter.id}
              className={sourceFilter === filter.id ? 'is-active' : ''}
              aria-pressed={sourceFilter === filter.id}
              onClick={() => setSourceFilter(filter.id)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="iu-notiziario__status-filters" aria-label="Filtra per stato">
          <button type="button" className={statusFilter === 'all' ? 'is-active' : ''} onClick={() => setStatusFilter('all')}>Tutte</button>
          <button type="button" className={statusFilter === 'unread' ? 'is-active' : ''} onClick={() => setStatusFilter('unread')}>Da leggere</button>
          <button type="button" className={statusFilter === 'favorite' ? 'is-active' : ''} onClick={() => setStatusFilter('favorite')}>Preferite</button>
        </div>
      </div>

      {error ? <div className="iu-notiziario__message is-error" role="alert">{visibleText(error)}</div> : null}

      <div className="iu-notiziario__workspace">
        <div className="iu-notiziario__feed" aria-label="Elenco aggiornamenti">
          <div className="iu-notiziario__feed-heading">
            <strong>{filteredItems.length} {filteredItems.length === 1 ? 'aggiornamento' : 'aggiornamenti'}</strong>
            <span>{unreadCount} da leggere</span>
          </div>
          {loading ? (
            <div className="iu-notiziario__loading" role="status">
              <span /><span /><span /><span />
            </div>
          ) : filteredItems.length ? filteredItems.map((item) => (
            <div className={`iu-notiziario-row ${selected?.id === item.id && !webSource ? 'is-selected' : ''} ${item.read ? 'is-read' : 'is-unread'}`} key={item.id}>
              <button type="button" className="iu-notiziario-row__main" onClick={() => selectItem(item)}>
                <span className="iu-notiziario-row__source" aria-hidden="true">{sourceInitials(item.sourceName)}</span>
                <span className="iu-notiziario-row__copy">
                  <span className="iu-notiziario-row__meta">
                    <b>{visibleText(item.sourceName)}</b>
                    <time dateTime={item.publishedAt}>{formatDateIt(item.publishedAt, 'Data non disponibile')}</time>
                  </span>
                  <strong>{visibleText(item.title)}</strong>
                  <small>{visibleText(item.summary, 'Apri per leggere il dettaglio pubblicato.')}</small>
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
          )) : (
            <div className="iu-notiziario__empty">
              <Newspaper size={24} />
              <strong>Nessun aggiornamento in questa vista</strong>
              <span>Modifica ricerca o filtri per tornare all’elenco pubblicato.</span>
            </div>
          )}
        </div>

        <article className="iu-notiziario__reader" aria-live="polite">
          {webSource ? (
            <>
              <div className="iu-notiziario__reader-head">
                <button type="button" onClick={() => setWebSource(null)}><ChevronLeft size={16} /> Torna al Notiziario</button>
                <span>Fonte istituzionale</span>
              </div>
              <div className="iu-notiziario__reader-title">
                <span className="iu-notiziario__source-mark"><Landmark size={19} /></span>
                <div><small>Consultazione nel lettore IUSENTRA</small><h3>{webSource.label}</h3></div>
              </div>
              <div className="iu-notiziario__web-reader" aria-live="polite">
                {sourceLoading ? (
                  <div className="iu-notiziario__source-state" role="status"><RefreshCw className="is-spinning" size={20} /><strong>Apertura della fonte in corso...</strong><span>Sto preparando una lettura interna del sito istituzionale.</span></div>
                ) : sourceReader?.ok && sourceReader.blocks.length ? (
                  <div className="iu-notiziario__source-copy">
                    <h4>{visibleText(sourceReader.title, webSource.label)}</h4>
                    {sourceReader.blocks.map((block, index) => <p key={`${webSource.id}-${index}`}>{visibleText(block)}</p>)}
                  </div>
                ) : (
                  <div className="iu-notiziario__source-state is-warning" role="alert"><ExternalLink size={20} /><strong>Fonte non leggibile nel pannello</strong><span>{visibleText(sourceReader?.message || '', 'Usa il collegamento al sito ufficiale per consultare il contenuto.')}</span></div>
                )}
              </div>
              <a className="iu-notiziario__original" href={webSource.url} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Apri il sito ufficiale</a>
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
                  <small>{[selected.matterName, selected.submatterName].filter(Boolean).map((value) => visibleText(value)).join(' · ') || 'Aggiornamento istituzionale'}</small>
                  <h3>{visibleText(selected.title)}</h3>
                </div>
              </div>
              <p className="iu-notiziario__lead">{visibleText(selected.summary, 'Sintesi non disponibile. Consulta il testo e la fonte ufficiale.')}</p>
              <div className="iu-notiziario__article-copy">
                {(selected.content || selected.summary).split(/\n+/).filter(Boolean).map((paragraph, index) => <p key={`${selected.id}-${index}`}>{visibleText(paragraph)}</p>)}
              </div>
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
                <button type="button" onClick={openCaseLink}><FolderPlus size={16} /> Collega a fascicolo</button>
                <a href={deadlineHref(selected)}><CalendarPlus size={16} /> Crea scadenza</a>
                <button type="button" onClick={() => void updateItem(selected, { read: !selected.read })} disabled={busyId === selected.id}>
                  <Check size={16} /> {selected.read ? 'Segna da leggere' : 'Segna come letta'}
                </button>
              </div>
              {selected.sourceUrl ? <a className="iu-notiziario__original" href={selected.sourceUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Apri la fonte ufficiale</a> : null}
            </>
          ) : (
            <div className="iu-notiziario__empty is-reader"><BookOpen size={28} /><strong>Seleziona un aggiornamento</strong><span>Il testo pubblicato si apre qui, senza perdere la Panoramica.</span></div>
          )}
        </article>
      </div>

      <footer className="iu-notiziario__quick-sources">
        <strong>Fonti rapide</strong>
        <div>
          {payload.quickSources.map((source) => (
            <button type="button" key={source.id} onClick={() => openQuickSource(source)}>
              <Landmark size={15} /> {visibleText(source.label)}
            </button>
          ))}
        </div>
      </footer>
    </section>
  )
}
