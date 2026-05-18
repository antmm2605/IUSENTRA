import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  Archive,
  BookOpen,
  ExternalLink,
  FileSearch,
  Filter,
  Globe2,
  Landmark,
  ListChecks,
  Mail,
  MessageCircle,
  Newspaper,
  Search,
  SearchCheck,
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { openDesignLegalKnowledgeSurface } from '../ui/openDesign'
import {
  emptyLegalIntelligencePage,
  getLegalIntelligenceMediazionePage,
  getLegalIntelligenceNewsPage,
  getLegalIntelligencePage,
  getRicercaLegalePage,
  type LegalIntelligencePageData,
  type LegalIntelligenceRecord,
} from '../legalIntelligenceData'
import './LegalIntelligencePage.css'
type LegalIntelligenceView = 'dashboard' | 'news' | 'mediazione' | 'ricerca-legale'
const quickQueries: Record<LegalIntelligenceView, string[]> = {
  dashboard: ['mediazione obbligatoria', 'Cassazione prescrizione', 'credito imposta', 'usura bancaria'],
  news: ['mediazione', 'processo civile', 'tributario', 'diritto del lavoro'],
  mediazione: ['ADR Center', 'Roma', 'Ente Autonomo', 'attivo'],
  'ricerca-legale': ['mediazione obbligatoria', 'Cassazione prescrizione', 'credito imposta investimenti', 'usura bancaria tasso soglia'],
}
function currentView(): LegalIntelligenceView {
  const route = (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase()
  // Path canonici sotto /ricerca-legale; /legal-intelligence/* viene ridiretto lato server.
  if (route === '/ricerca-legale/news' || route === '/legal-intelligence/news') return 'news'
  if (route === '/ricerca-legale/mediazione' || route === '/legal-intelligence/mediazione') return 'mediazione'
  if (route === '/ricerca-legale/ricerca') return 'ricerca-legale'
  if (route === '/legal-intelligence') return 'ricerca-legale'
  if (route === '/ricerca-legale') return 'ricerca-legale'
  return 'dashboard'
}
function pageTitle(view: LegalIntelligenceView) {
  if (view === 'news') return 'News Legali'
  if (view === 'mediazione') return 'Registro Mediazione'
  if (view === 'ricerca-legale') return 'Ricerca Legale'
  return 'Osservatorio Legale'
}
function pageSubtitle(view: LegalIntelligenceView) {
  if (view === 'news') return 'Aggiornamenti giuridici con fonte, contesto e uso operativo in studio.'
  if (view === 'mediazione') return 'Registri ministeriali e dati di mediazione letti dentro una scheda professionale.'
  if (view === 'ricerca-legale') return 'Ricerca su archivio giuridico, fonti ufficiali e schede contestualizzate.'
  return 'Archivio fonti, news e registri con contesto leggibile prima di aprire la fonte originale.'
}
function initialQuery() {
  return new URLSearchParams(window.location.search).get('q') || ''
}
async function loadPage(view: LegalIntelligenceView, query = ''): Promise<LegalIntelligencePageData> {
  if (view === 'news') return getLegalIntelligenceNewsPage()
  if (view === 'mediazione') return getLegalIntelligenceMediazionePage()
  if (view === 'ricerca-legale') return getRicercaLegalePage({ q: query })
  return getLegalIntelligencePage()
}

function formatDate(value: string) {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function isOfficial(record: LegalIntelligenceRecord) {
  return [record.sourceKind, record.approvalLabel, record.evidenceType].join(' ').toLocaleLowerCase('it-IT').includes('ufficiale')
}
function contextItems(record: LegalIntelligenceRecord) {
  if (record.sourceContext.length) return record.sourceContext
  return [
    record.contextSummary ? `Contesto operativo: ${record.contextSummary}` : '',
    record.sourceExcerpt ? `Contenuto: ${record.sourceExcerpt}` : '',
    record.area || record.branch ? `Ambito: ${[record.area, record.branch].filter(Boolean).join(' / ')}` : '',
    record.date ? `Aggiornamento: ${formatDate(record.date)}` : '',
    record.sourceLabel ? `Provenienza: ${record.sourceLabel}` : '',
  ].filter(Boolean)
}
function contextStatusLabel(record: LegalIntelligenceRecord) {
  if (record.contextCompleted) return 'Scheda interna completa'
  if (record.contextSummary || record.keyPoints.length || record.operationalChecks.length) return 'Scheda interna da completare'
  return 'Contesto essenziale'
}
function practicalUse(record: LegalIntelligenceRecord) {
  if (record.practicalUse) return record.practicalUse
  if (record.kind.toLocaleLowerCase('it-IT').includes('mediazione')) {
    return 'Verifica soggetti e requisiti prima di scegliere organismo, ente o formatore.'
  }
  return 'Valuta pertinenza, fonte e data prima di usare il riferimento nel lavoro di studio.'
}
function reliabilityNote(record: LegalIntelligenceRecord) {
  if (record.reliabilityNote) return record.reliabilityNote
  if (record.contextCompleted) return 'Contesto letto dentro IUSENTRA: la fonte originale resta controllo finale.'
  if (isOfficial(record)) return 'Fonte ufficiale o istituzionale: apri il testo originale per il controllo finale.'
  return "Fonte censita nello studio: richiede controllo professionale prima dell'uso."
}
function relatedQuery(record: LegalIntelligenceRecord) {
  return record.followUpQuery || [record.title, record.area, record.branch, record.sourceLabel].filter(Boolean).join(' ')
}
function recordIcon(record: LegalIntelligenceRecord) {
  const kind = record.kind.toLocaleLowerCase('it-IT')
  if (kind.includes('mediazione')) return <Landmark size={17} aria-hidden="true" />
  if (kind.includes('news')) return <Newspaper size={17} aria-hidden="true" />
  if (kind.includes('normativa')) return <BookOpen size={17} aria-hidden="true" />
  return <FileSearch size={17} aria-hidden="true" />
}
function WarningList({ data }: { data: LegalIntelligencePageData }) {
  if (!data.warnings.length) return null
  return (
    <section className="iu-li-warnings" aria-label="Avvisi ricerca legale">
      {data.warnings.map((warning) => (
        <p className="iu-li-warning iu-od-inference-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </section>
  )
}
function NavigationTabs({ view }: { view: LegalIntelligenceView }) {
  // Path canonici sotto /ricerca-legale; /legal-intelligence/* viene ridiretto lato server.
  // resta accessibile e viene ridiretto 301 lato server.
  const items: Array<[LegalIntelligenceView, string, string, string]> = [
    ['ricerca-legale', 'Ricerca', 'fonti e norme', '/ricerca-legale'],
    ['news', 'News', 'aggiornamenti', '/ricerca-legale/news'],
    ['mediazione', 'Mediazione', 'registro', '/ricerca-legale/mediazione'],
  ]
  return (
    <nav className="iu-li-tabs iu-od-source-card" aria-label="Sezioni ricerca legale">
      {items.map(([itemView, label, description, href]) => (
        <a
          key={itemView}
          href={href}
          className={view === itemView ? 'iu-li-tab-card iu-li-tab-card--active' : 'iu-li-tab-card'}
          aria-current={view === itemView ? 'page' : undefined}
        >
          <strong>{label}</strong>
          <span>{description}</span>
        </a>
      ))}
    </nav>
  )
}
function formatMetricValue(value: string | number) {
  if (typeof value === 'number') return value.toLocaleString('it-IT')
  return value || '0'
}
function metricById(data: LegalIntelligencePageData, id: string) {
  return data.metrics.find((metric) => metric.id === id)
}
function sectionById(data: LegalIntelligencePageData, id: string) {
  return data.sections.find((section) => section.id === id)
}
function DataAccessPanel({
  data,
  onArchiveSearch,
}: {
  data: LegalIntelligencePageData
  onArchiveSearch: (query: string, scope?: string, source?: string) => void
}) {
  const normattiva = metricById(data, 'normattiva')
  const gazzetta = metricById(data, 'gazzetta')
  const monitoredSources = metricById(data, 'fonti_monitorate')
  const news = metricById(data, 'news_pubblicate')
  const review = metricById(data, 'review')
  const mediazione = metricById(data, 'mediazione')
  const monitoredSection = sectionById(data, 'fonti')
  const monitoredItems = monitoredSection?.items ?? []
  const hasCassazione = monitoredItems.some((item) => {
    const text = `${item.id} ${item.label} ${item.note}`.toLocaleLowerCase('it-IT')
    return text.includes('cassazione') || text.includes('cortedicassazione')
  })
  const items = [
    monitoredSources ? {
      id: 'fonti',
      label: 'Fonti monitorate',
      value: formatMetricValue(monitoredSources.value),
      note: monitoredItems.length ? 'Elenco sotto, con stato e famiglia' : 'Elenco fonti configurate e stato dei controlli',
      action: 'Mostra fonti',
      onClick: () => document.getElementById('fonti-monitorate-list')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    } : null,
    hasCassazione ? {
      id: 'cassazione',
      label: 'Corte di Cassazione',
      value: 'attiva',
      note: 'Sentenze, ordinanze e questioni catalogate',
      action: 'Prova Cassazione',
      onClick: () => onArchiveSearch('Cassazione ultime sentenze ordinanze questioni', 'giurisprudenza'),
    } : null,
    normattiva ? {
      id: 'normattiva',
      label: 'Normattiva',
      value: formatMetricValue(normattiva.value),
      note: normattiva.note || 'Archivio normativo locale',
      action: 'Prova normativa',
      onClick: () => onArchiveSearch('mediazione obbligatoria', 'normativa', 'Normattiva'),
    } : null,
    gazzetta ? {
      id: 'gazzetta',
      label: 'Gazzetta Ufficiale',
      value: formatMetricValue(gazzetta.value),
      note: gazzetta.note || 'Estratti ufficiali indicizzati',
      action: 'Prova Gazzetta',
      onClick: () => onArchiveSearch('credito imposta investimenti', 'normativa', 'Gazzetta Ufficiale'),
    } : null,
    news ? {
      id: 'news',
      label: 'News disponibili',
      value: formatMetricValue(news.value),
      note: 'Elenco consultabile con schede e fonte',
      href: '/ricerca-legale/news',
      action: 'Vedi news',
    } : null,
    review ? {
      id: 'review',
      label: 'Da controllare',
      value: formatMetricValue(review.value),
      note: 'Documenti acquisiti da completare prima dell’uso',
      href: '/admin/aggiornamenti-legali/staging',
      action: 'Vedi acquisizioni',
    } : null,
    mediazione ? {
      id: 'mediazione',
      label: 'Registro mediazione',
      value: formatMetricValue(mediazione.value),
      note: 'Organismi, enti e formatori filtrabili',
      href: '/ricerca-legale/mediazione',
      action: 'Vedi registro',
    } : null,
  ].filter(Boolean) as Array<{
    id: string
    label: string
    value: string
    note: string
    action: string
    href?: string
    onClick?: () => void
  }>
  if (!items.length) return null
  return (
    <section className="iu-li-data-access iu-od-source-card" aria-label="Dati disponibili nella ricerca legale">
      <header className="iu-li-section-head">
        <SearchCheck size={18} aria-hidden="true" />
        <div>
          <h2>Dati disponibili</h2>
          <p>Conteggi reali collegati ad archivi consultabili: usa la ricerca e i filtri per vedere le schede, non solo il numero.</p>
        </div>
      </header>
      <div className="iu-li-data-access__grid">
        {items.map((item) => (
          <article className="iu-li-data-access__item" key={item.id}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.note}</small>
            {item.href ? (
              <ButtonLink href={item.href} tone="neutral">{item.action}</ButtonLink>
            ) : (
              <Button type="button" tone="neutral" onClick={item.onClick}>{item.action}</Button>
            )}
          </article>
        ))}
      </div>
      {monitoredItems.length ? (
        <div id="fonti-monitorate-list" className="iu-li-source-preview" aria-label="Fonti monitorate disponibili">
          <div className="iu-li-source-preview__head">
            <strong>Fonti monitorate</strong>
            <ButtonLink href="/admin/aggiornamenti-legali/fonti" tone="neutral">Gestisci fonti</ButtonLink>
          </div>
          <div className="iu-li-source-preview__grid">
            {monitoredItems.map((item) => (
              <button
                className="iu-li-source-preview__item"
                key={item.id}
                onClick={() => onArchiveSearch(item.label, '')}
                type="button"
              >
                <strong>{item.label}</strong>
                <Badge tone={item.tone}>{item.value || 'censita'}</Badge>
                {item.note ? <small>{item.note}</small> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}
function RecordCard({
  record,
  selected,
  onOpen,
}: {
  record: LegalIntelligenceRecord
  selected: boolean
  onOpen: (record: LegalIntelligenceRecord) => void
}) {
  const metaItems = [
    ['Fonte', record.sourceLabel],
    ['Tipo fonte', record.sourceKind],
    ['Data', formatDate(record.date)],
    ['Area', record.area],
    ['Materia', record.branch],
    ['Territorio', record.territory],
    ['Registro', record.registryNumber],
  ].filter((item) => item[1])
  const stateLabel = record.approvalLabel || record.stateLabel
  const stateTone = record.approvalLabel ? record.approvalTone : record.stateTone
  const summaryItems = contextItems(record).slice(0, 2)
  const pointPreview = record.keyPoints.slice(0, 2)
  const checkPreview = record.operationalChecks.slice(0, 1)
  return (
    <article className={selected ? 'iu-li-record iu-li-record--selected iu-od-source-card' : 'iu-li-record iu-od-source-card'}>
      <header className="iu-li-record__header">
        <div className="iu-li-record__title">
          <span className="iu-od-source-badge">{recordIcon(record)}{record.kind}</span>
          <h3>{record.title}</h3>
          {record.sourceExcerpt ? <p>{record.sourceExcerpt}</p> : null}
        </div>
        {stateLabel ? <Badge tone={stateTone}>{stateLabel}</Badge> : null}
      </header>
      <div className="iu-li-internal-strip" aria-label="Stato scheda IUSENTRA">
        <span className="iu-li-internal-strip__label">Scheda IUSENTRA</span>
        <strong>{contextStatusLabel(record)}</strong>
      </div>
      {summaryItems.length ? (
        <ul className="iu-li-context-list" aria-label="Contesto disponibile">
          {summaryItems.map((item) => (
            <li key={`${record.id}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : null}
      {pointPreview.length || checkPreview.length ? (
        <div className="iu-li-card-points" aria-label="Punti e controlli della scheda">
          {pointPreview.map((item) => <span key={`${record.id}-card-point-${item}`}>{item}</span>)}
          {checkPreview.map((item) => <span key={`${record.id}-card-check-${item}`}>{item}</span>)}
        </div>
      ) : null}
      <dl className="iu-li-meta iu-li-meta--compact">
        {metaItems.slice(0, 4).map(([label, value]) => (
          <div key={`${record.id}-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-li-evidence-row">
        <span className="iu-od-source-badge">{record.evidenceType || 'informazione'}</span>
        {record.sourceKind ? <span className="iu-od-source-badge">{record.sourceKind}</span> : null}
        {record.contextCompleted ? <span className="iu-od-source-badge">letto in IUSENTRA</span> : null}
      </div>
      <footer className="iu-od-action-row iu-li-record__actions">
        <Button type="button" tone="primary" onClick={() => onOpen(record)}>
          <BookOpen size={16} aria-hidden="true" />
          Leggi scheda
        </Button>
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer" className="iu-li-official-link">
            <ExternalLink size={16} aria-hidden="true" />
            Controllo ufficiale
          </ButtonLink>
        ) : null}
      </footer>
    </article>
  )
}
function RecordDetail({
  record,
  view,
  onSearchRelated,
}: {
  record?: LegalIntelligenceRecord
  view: LegalIntelligenceView
  onSearchRelated: (query: string) => void
}) {
  if (!record) {
    return (
      <aside className="iu-li-detail iu-od-source-card" aria-label="Contesto fonte">
        <EmptyState
          title="Nessuna scheda selezionata"
          message="Avvia una ricerca o scegli un risultato per leggere contesto, provenienza e uso pratico dentro IUSENTRA."
        />
      </aside>
    )
  }
  const items = contextItems(record)
  const isMediazioneRecord = record.kind.toLocaleLowerCase('it-IT').includes('mediazione')
  const sourceMeta = [
    ['Fonte', record.sourceLabel || 'Non indicata'],
    ['Tipo', record.sourceKind || 'Non indicato'],
    ['Data', formatDate(record.date) || 'Non indicata'],
    ['Area', record.area || record.branch || 'Non indicata'],
    ...(isMediazioneRecord ? [
      ['Sezione', record.registrySection || 'Registro mediazione'],
      ['Registro', record.registryNumber || 'Non indicato'],
      ['Codice fiscale', record.taxCode || 'Non indicato'],
      ['Partita IVA', record.vatNumber || 'Non indicata'],
      ['Contatti', record.email || record.website || 'Non indicati'],
    ] : []),
  ]
  const contextSummary = record.contextSummary || record.sourceExcerpt || record.subtitle
  return (
    <aside className="iu-li-detail iu-od-source-card" aria-label="Contesto fonte">
      <div className="iu-li-detail__intro">
        <span className="iu-od-source-badge">{recordIcon(record)}{record.kind}</span>
        <h2>{record.title}</h2>
        <p>{contextSummary || 'Scheda disponibile con provenienza, controlli e fonte collegata.'}</p>
      </div>
      <section className="iu-li-detail__status" aria-label="Stato della scheda interna">
        <div>
          <span>Scheda interna IUSENTRA</span>
          <strong>{contextStatusLabel(record)}</strong>
        </div>
        <p>Il contenuto utile allo studio è leggibile qui; il collegamento esterno resta un controllo finale sulla fonte originale.</p>
      </section>
      <div className="iu-li-detail__reading">
        <h3>Contesto in IUSENTRA</h3>
        {items.length ? (
          <ul className="iu-li-context-list">
            {items.map((item) => (
              <li key={`${record.id}-detail-${item}`}>{item}</li>
            ))}
          </ul>
        ) : (
          <p>Contesto essenziale disponibile nella scheda.</p>
        )}
      </div>
      {record.keyPoints.length ? (
        <section className="iu-li-detail__box">
          <h3>Punti della scheda</h3>
          <ul className="iu-li-context-list">
            {record.keyPoints.map((item) => (
              <li key={`${record.id}-point-${item}`}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {record.officialContext ? (
        <section className="iu-li-detail__box iu-li-detail__official">
          <h3>Testo letto in IUSENTRA</h3>
          <p>{record.officialContext}</p>
        </section>
      ) : null}
      <div className="iu-li-detail__grid">
        <section className="iu-li-detail__box">
          <h3>Uso pratico</h3>
          <p>{practicalUse(record)}</p>
        </section>
        <section className="iu-li-detail__box">
          <h3>{'Attendibilit\u00e0'}</h3>
          <p>{reliabilityNote(record)}</p>
        </section>
      </div>
      {record.operationalChecks.length ? (
        <section className="iu-li-detail__box">
          <h3>Controlli per lo studio</h3>
          <ul className="iu-li-context-list">
            {record.operationalChecks.map((item) => (
              <li key={`${record.id}-check-${item}`}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <dl className="iu-li-meta iu-li-detail__meta">
        {sourceMeta.map(([label, value]) => (
          <div key={`${record.id}-detail-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-od-action-row iu-li-detail__actions">
        {view !== 'mediazione' ? (
          <Button type="button" tone="primary" onClick={() => onSearchRelated(relatedQuery(record))}>
            <Search size={16} aria-hidden="true" />
            Cerca collegati
          </Button>
        ) : null}
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer" className="iu-li-official-link">
            <ExternalLink size={16} aria-hidden="true" />
            {view === 'mediazione' ? 'Apri fonte originale' : 'Controllo ufficiale'}
          </ButtonLink>
        ) : null}
        {view !== 'mediazione' ? <ButtonLink href="/giurisprudenza" tone="neutral">Archivio giurisprudenza</ButtonLink> : null}
      </div>
    </aside>
  )
}
function RecordFilters({
  view,
  query,
  submittedQuery,
  loading,
  kind,
  source,
  area,
  state,
  scope,
  quality,
  kinds,
  sources,
  areas,
  states,
  onQuery,
  onKind,
  onSource,
  onArea,
  onState,
  onScope,
  onQuality,
  onSubmit,
  onReset,
  onQuickSearch,
}: {
  view: LegalIntelligenceView
  query: string
  submittedQuery: string
  loading: boolean
  kind: string
  source: string
  area: string
  state: string
  scope: string
  quality: string
  kinds: string[]
  sources: string[]
  areas: string[]
  states: string[]
  onQuery: (value: string) => void
  onKind: (value: string) => void
  onSource: (value: string) => void
  onArea: (value: string) => void
  onState: (value: string) => void
  onScope: (value: string) => void
  onQuality: (value: string) => void
  onSubmit: () => void
  onReset: () => void
  onQuickSearch: (value: string) => void
}) {
  const isSearch = view === 'ricerca-legale'
  const showSelectFilters = view !== 'mediazione'
  const hasActiveFilters = Boolean(kind || source || area || state || scope || quality || (isSearch ? submittedQuery : query))
  return (
    <section className="iu-li-filters iu-od-source-card" aria-label={isSearch ? 'Ricerca fonti legali' : 'Filtro schede'}>
      <form
        className="iu-li-search-form"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <label className="iu-li-search-field" htmlFor="legal-intelligence-search">
          <span>
            <Search size={15} aria-hidden="true" />
            {isSearch ? 'Cerca fonti, norme e giurisprudenza' : 'Filtra le schede visibili'}
          </span>
          <input
            id="legal-intelligence-search"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder={view === 'mediazione'
              ? 'Cerca organismo, numero registro, codice fiscale, partita IVA, email o sito'
              : isSearch
                ? 'Es. mediazione, Cassazione, prescrizione, decreto'
                : 'Filtra per materia, fonte o data'}
          />
        </label>
        <Button type="submit" tone="primary" disabled={loading || !query.trim()}>
          <Search size={16} aria-hidden="true" />
          {isSearch ? 'Cerca' : 'Cerca nelle fonti'}
        </Button>
        {hasActiveFilters ? (
          <Button type="button" tone="neutral" onClick={onReset}>
            Azzera
          </Button>
        ) : null}
      </form>
      {showSelectFilters ? (
        <div className="iu-li-filter-grid" aria-label="Filtri schede">
          <label>
            <span><Filter size={14} aria-hidden="true" /> Ambito</span>
            <select value={scope} onChange={(event) => onScope(event.target.value)}>
              <option value="">Tutti</option>
              <option value="giurisprudenza">Giurisprudenza e Cassazione</option>
              <option value="normativa">Normativa</option>
              <option value="news">News e aggiornamenti</option>
              <option value="mediazione">Mediazione</option>
            </select>
          </label>
          <label>
            <span>Fonte</span>
            <select value={source} onChange={(event) => onSource(event.target.value)}>
              <option value="">Tutte</option>
              {sources.map((option) => <option value={option} key={option}>{option}</option>)}
            </select>
          </label>
          <label>
            <span>Materia</span>
            <select value={area} onChange={(event) => onArea(event.target.value)}>
              <option value="">Tutte</option>
              {areas.map((option) => <option value={option} key={option}>{option}</option>)}
            </select>
          </label>
          <label>
            <span>Qualità</span>
            <select value={quality} onChange={(event) => onQuality(event.target.value)}>
              <option value="">Tutte</option>
              <option value="ufficiale">Solo fonti ufficiali</option>
              <option value="letta">Letta in IUSENTRA</option>
              <option value="link">Con fonte apribile</option>
            </select>
          </label>
          <label>
            <span>Tipo documento</span>
            <select value={kind} onChange={(event) => onKind(event.target.value)}>
              <option value="">Tutti</option>
              {kinds.map((option) => <option value={option} key={option}>{option}</option>)}
            </select>
          </label>
          <label>
            <span>Stato</span>
            <select value={state} onChange={(event) => onState(event.target.value)}>
              <option value="">Tutti</option>
              {states.map((option) => <option value={option} key={option}>{option}</option>)}
            </select>
          </label>
        </div>
      ) : null}
      <div className="iu-li-quick-row" aria-label="Ricerche guidate">
        {quickQueries[view].map((item) => (
          <Button type="button" tone="neutral" key={item} onClick={() => onQuickSearch(item)}>
            <ArrowRight size={15} aria-hidden="true" />
            {item}
          </Button>
        ))}
      </div>
      {isSearch && submittedQuery ? <p className="iu-li-search-note">Risultati per "{submittedQuery}".</p> : null}
    </section>
  )
}
function uniqueOptions(records: LegalIntelligenceRecord[], field: keyof LegalIntelligenceRecord) {
  return Array.from(new Set(records.map((record) => String(record[field] || '').trim()).filter(Boolean))).sort((a, b) => a.localeCompare(b, 'it-IT'))
}
function recordMatchesSelect(value: string, filterValue: string) {
  if (!filterValue) return true
  return value.toLocaleLowerCase('it-IT') === filterValue.toLocaleLowerCase('it-IT')
}
function recordMatchesLegalScope(record: LegalIntelligenceRecord, filterValue: string) {
  if (!filterValue) return true
  const haystack = [
    record.kind,
    record.title,
    record.subtitle,
    record.sourceLabel,
    record.sourceKind,
    record.area,
    record.branch,
    record.evidenceType,
  ].join(' ').toLocaleLowerCase('it-IT')
  if (filterValue === 'giurisprudenza') {
    return ['giurisprudenza', 'cassazione', 'sentenza', 'ordinanza', 'questione penale', 'questione civile'].some((term) => haystack.includes(term))
  }
  if (filterValue === 'normativa') {
    return ['norma', 'normativa', 'legge', 'decreto', 'gazzetta', 'normattiva'].some((term) => haystack.includes(term))
  }
  if (filterValue === 'news') {
    return ['news', 'aggiornamento', 'notizia'].some((term) => haystack.includes(term))
  }
  if (filterValue === 'mediazione') {
    return ['mediazione', 'organismo', 'formatore', 'ente'].some((term) => haystack.includes(term))
  }
  return true
}
function recordMatchesQuality(record: LegalIntelligenceRecord, filterValue: string) {
  if (!filterValue) return true
  if (filterValue === 'ufficiale') return isOfficial(record)
  if (filterValue === 'letta') return record.contextCompleted || Boolean(record.officialContext || record.sourceContext.length)
  if (filterValue === 'link') return Boolean(record.sourceHref)
  return true
}
function isImportedMediazioneRecord(record: LegalIntelligenceRecord) {
  return record.id.startsWith('registro-mediazione-') || Boolean(record.registrySection)
}
function MediazioneRegistryExplorer({
  records,
  allRecords,
  query,
  section,
  status,
  type,
  territory,
  contact,
  onQuery,
  onSubmit,
  onSection,
  onStatus,
  onType,
  onTerritory,
  onContact,
  onReset,
  onOpen,
}: {
  records: LegalIntelligenceRecord[]
  allRecords: LegalIntelligenceRecord[]
  query: string
  section: string
  status: string
  type: string
  territory: string
  contact: string
  onQuery: (value: string) => void
  onSubmit: () => void
  onSection: (value: string) => void
  onStatus: (value: string) => void
  onType: (value: string) => void
  onTerritory: (value: string) => void
  onContact: (value: string) => void
  onReset: () => void
  onOpen: (record: LegalIntelligenceRecord) => void
}) {
  const sectionOptions = uniqueOptions(allRecords, 'registrySection')
  const statusOptions = uniqueOptions(allRecords, 'stateLabel')
  const typeOptions = uniqueOptions(allRecords, 'organismoType')
  const territoryOptions = uniqueOptions(allRecords, 'territory').slice(0, 180)
  const visibleRows = records.slice(0, 80)
  return (
    <section id="registro-mediazione" className="iu-li-registry iu-od-source-card" aria-label="Elenco organismi di mediazione">
      <header className="iu-li-section-head">
        <Landmark size={18} aria-hidden="true" />
        <div>
          <h2>Organismi nel registro</h2>
          <p>{records.length} risultati filtrati su {allRecords.length} organismi acquisiti dal registro ministeriale.</p>
        </div>
      </header>
      <div className="iu-li-registry-filters" aria-label="Filtri registro organismi">
        <label className="iu-li-registry-search">
          <span><Search size={14} aria-hidden="true" /> Cerca</span>
          <input
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') onSubmit()
            }}
            placeholder="Organismo, numero registro, codice fiscale, email o sito"
          />
        </label>
        <label>
          <span><Filter size={14} aria-hidden="true" /> Sezione</span>
          <select value={section} onChange={(event) => onSection(event.target.value)}>
            <option value="">Tutte</option>
            {sectionOptions.map((option) => <option value={option} key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          <span>Stato</span>
          <select value={status} onChange={(event) => onStatus(event.target.value)}>
            <option value="">Tutti</option>
            {statusOptions.map((option) => <option value={option} key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          <span>Natura</span>
          <select value={type} onChange={(event) => onType(event.target.value)}>
            <option value="">Tutte</option>
            {typeOptions.map((option) => <option value={option} key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          <span>Territorio</span>
          <select value={territory} onChange={(event) => onTerritory(event.target.value)}>
            <option value="">Tutti</option>
            {territoryOptions.map((option) => <option value={option} key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          <span>Contatti</span>
          <select value={contact} onChange={(event) => onContact(event.target.value)}>
            <option value="">Tutti</option>
            <option value="email">Con email</option>
            <option value="website">Con sito web</option>
          </select>
        </label>
        {(query || section || status || type || territory || contact) ? (
          <Button type="button" tone="neutral" onClick={onReset}>Azzera filtri</Button>
        ) : null}
      </div>
      {visibleRows.length ? (
        <div className="iu-li-registry-table-wrap">
          <table className="iu-li-registry-table">
            <thead>
              <tr>
                <th>Sezione</th>
                <th>Registro</th>
                <th>Organismo</th>
                <th>Natura</th>
                <th>Stato</th>
                <th>Identificativi</th>
                <th>Contatti</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((record) => (
                <tr key={record.id}>
                  <td>{record.registrySection || 'Registro mediazione'}</td>
                  <td><strong>{record.registryNumber || record.taxCode || '-'}</strong></td>
                  <td>
                    <span className="iu-li-registry-table__title">{record.title}</span>
                    {record.territory ? <small>{record.territory}</small> : null}
                  </td>
                  <td>{record.organismoType || record.subtitle || '-'}</td>
                  <td><Badge tone={record.stateTone}>{record.stateLabel || 'Da verificare'}</Badge></td>
                  <td>
                    <span>{record.taxCode ? `CF ${record.taxCode}` : 'CF non indicato'}</span>
                    <small>{record.vatNumber ? `P. IVA ${record.vatNumber}` : 'P. IVA non indicata'}</small>
                  </td>
                  <td>
                    {record.email ? <span><Mail size={14} aria-hidden="true" /> {record.email}</span> : <span>Email non indicata</span>}
                    {record.website ? <small><Globe2 size={14} aria-hidden="true" /> {record.website}</small> : null}
                  </td>
                  <td>
                    <Button type="button" tone="neutral" onClick={() => onOpen(record)}>
                      <BookOpen size={15} aria-hidden="true" />
                      Scheda
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="Nessun organismo con questi filtri"
          message="Modifica ricerca, stato, natura o territorio per restringere il registro acquisito."
        />
      )}
      {records.length > visibleRows.length ? (
        <p className="iu-li-registry-note">Mostro i primi {visibleRows.length} risultati per mantenere la pagina reattiva: la ricerca e i filtri lavorano su tutti gli organismi acquisiti.</p>
      ) : null}
    </section>
  )
}
function MediazioneImportPanel() {
  return (
    <section className="iu-li-mediazione-import iu-od-source-card" aria-label="Aggiornamento registro mediazione">
      <header className="iu-li-section-head">
        <ListChecks size={18} aria-hidden="true" />
        <div>
          <h2>Registro aggiornabile</h2>
          <p>I dati sono acquisiti nel presidio interno IUSENTRA e restano consultabili qui con ricerca e filtri; i collegamenti ministeriali servono solo per verifica finale.</p>
        </div>
      </header>
      <div className="iu-li-mediazione-import__quick">
        <div className="iu-li-mediazione-import__sync">
          <strong>Aggiornamento automatico</strong>
          <small>La scansione periodica legge i tre elenchi ufficiali e aggiorna l'archivio interno senza uscire dalla pagina di lavoro.</small>
        </div>
        <a
          className="iu-li-mediazione-import__official"
          href="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX"
          target="_blank"
          rel="noopener noreferrer"
        >
          Apri registro ministeriale
          <ExternalLink size={14} aria-hidden="true" />
        </a>
        <a
          className="iu-li-mediazione-import__official"
          href="https://mediazione.giustizia.it/ROM/AlboEntiFormazione.aspx"
          target="_blank"
          rel="noopener noreferrer"
        >
          Apri elenco enti
          <ExternalLink size={14} aria-hidden="true" />
        </a>
        <a
          className="iu-li-mediazione-import__official"
          href="https://mediazione.giustizia.it/ROM/AlboFormatori.aspx"
          target="_blank"
          rel="noopener noreferrer"
        >
          Apri elenco formatori
          <ExternalLink size={14} aria-hidden="true" />
        </a>
      </div>
    </section>
  )
}
function ResultHeader({
  view,
  visibleCount,
  totalCount,
  submittedQuery,
}: {
  view: LegalIntelligenceView
  visibleCount: number
  totalCount: number
  submittedQuery: string
}) {
  const title = view === 'mediazione'
    ? 'Schede mediazione'
    : view === 'news'
      ? 'Aggiornamenti consultabili'
      : view === 'ricerca-legale'
        ? submittedQuery ? 'Risultati della ricerca' : 'Fonti disponibili'
        : 'Schede disponibili'
  const subtitle = view === 'ricerca-legale' && submittedQuery
    ? `${visibleCount} schede trovate per "${submittedQuery}".`
    : `${visibleCount} schede visibili su ${totalCount} elementi disponibili.`
  return (
    <header className="iu-li-section-head">
      <FileSearch size={18} aria-hidden="true" />
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </header>
  )
}
function includesText(value: string, query: string) {
  if (!query.trim()) return true
  return value.toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))
}
export function LegalIntelligencePage() {
  const initialParams = new URLSearchParams(window.location.search)
  const [view] = useState<LegalIntelligenceView>(() => currentView())
  const [data, setData] = useState<LegalIntelligencePageData>(emptyLegalIntelligencePage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState(() => (['ricerca-legale', 'mediazione'].includes(currentView()) ? initialQuery() : ''))
  const [submittedQuery, setSubmittedQuery] = useState(() => (currentView() === 'ricerca-legale' ? initialQuery() : ''))
  const [selectedId, setSelectedId] = useState(new URLSearchParams(window.location.search).get('scheda') || '')
  const [recordKind, setRecordKind] = useState(initialParams.get('tipo') || '')
  const [recordSource, setRecordSource] = useState(initialParams.get('fonte') || '')
  const [recordArea, setRecordArea] = useState(initialParams.get('area') || '')
  const [recordState, setRecordState] = useState(initialParams.get('stato') || '')
  const [recordScope, setRecordScope] = useState(initialParams.get('ambito') || '')
  const [recordQuality, setRecordQuality] = useState(initialParams.get('qualita') || '')
  const [mediazioneSection, setMediazioneSection] = useState('')
  const [mediazioneStatus, setMediazioneStatus] = useState('')
  const [mediazioneType, setMediazioneType] = useState('')
  const [mediazioneTerritory, setMediazioneTerritory] = useState('')
  const [mediazioneContact, setMediazioneContact] = useState('')
  useEffect(() => {
    let active = true
    setLoading(true)
    loadPage(view, submittedQuery)
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [view, submittedQuery])
  const localFilter = view === 'ricerca-legale' ? '' : query
  const locallyVisibleRecords = useMemo(() => data.records.filter((record) => includesText([
    record.title,
    record.subtitle,
    record.sourceExcerpt,
    record.sourceContext.join(' '),
    record.officialContext,
    record.contextSummary,
    record.keyPoints.join(' '),
    record.operationalChecks.join(' '),
    record.practicalUse,
    record.reliabilityNote,
    record.sourceLabel,
    record.sourceKind,
    record.area,
    record.branch,
    record.territory,
    record.registryNumber,
    record.taxCode,
    record.vatNumber,
    record.email,
    record.website,
  ].join(' '), localFilter)), [data.records, localFilter])
  const selectableRecords = view === 'mediazione' ? locallyVisibleRecords : data.records
  const kindOptions = useMemo(() => uniqueOptions(selectableRecords, 'kind'), [selectableRecords])
  const sourceOptions = useMemo(() => uniqueOptions(selectableRecords, 'sourceLabel'), [selectableRecords])
  const areaOptions = useMemo(() => uniqueOptions(selectableRecords, 'area'), [selectableRecords])
  const stateOptions = useMemo(() => Array.from(new Set(selectableRecords
    .map((record) => record.approvalLabel || record.stateLabel)
    .filter((value): value is string => Boolean(value))))
    .sort((a, b) => a.localeCompare(b, 'it-IT')), [selectableRecords])
  const filteredLegalRecords = useMemo(() => {
    if (view === 'mediazione') return locallyVisibleRecords
    return locallyVisibleRecords.filter((record) => {
      if (!recordMatchesSelect(record.kind, recordKind)) return false
      if (!recordMatchesSelect(record.sourceLabel, recordSource)) return false
      if (!recordMatchesSelect(record.area, recordArea)) return false
      if (!recordMatchesSelect(record.approvalLabel || record.stateLabel, recordState)) return false
      if (!recordMatchesLegalScope(record, recordScope)) return false
      if (!recordMatchesQuality(record, recordQuality)) return false
      return true
    })
  }, [locallyVisibleRecords, recordArea, recordKind, recordQuality, recordScope, recordSource, recordState, view])
  const mediazioneOfficialRecords = useMemo(() => view === 'mediazione'
    ? locallyVisibleRecords.filter((record) => !isImportedMediazioneRecord(record))
    : [], [locallyVisibleRecords, view])
  const mediazioneRegistryRecords = useMemo(() => view === 'mediazione'
    ? locallyVisibleRecords.filter(isImportedMediazioneRecord)
    : [], [locallyVisibleRecords, view])
  const filteredMediazioneRegistryRecords = useMemo(() => {
    if (view !== 'mediazione') return []
    return mediazioneRegistryRecords.filter((record) => {
      if (!recordMatchesSelect(record.registrySection, mediazioneSection)) return false
      if (!recordMatchesSelect(record.stateLabel, mediazioneStatus)) return false
      if (!recordMatchesSelect(record.organismoType, mediazioneType)) return false
      if (!recordMatchesSelect(record.territory, mediazioneTerritory)) return false
      if (mediazioneContact === 'email' && !record.email) return false
      if (mediazioneContact === 'website' && !record.website) return false
      return true
    })
  }, [mediazioneRegistryRecords, mediazioneContact, mediazioneSection, mediazioneStatus, mediazioneTerritory, mediazioneType, view])
  const visibleRecords = view === 'mediazione'
    ? [...mediazioneOfficialRecords, ...filteredMediazioneRegistryRecords]
    : filteredLegalRecords
  const selectedRecord = visibleRecords.find((record) => record.id === selectedId) || visibleRecords[0]
  const updateSearchUrl = (value: string) => {
    const params = new URLSearchParams(window.location.search)
    if (value) params.set('q', value)
    else params.delete('q')
    params.delete('scheda')
    const suffix = params.toString() ? `?${params.toString()}` : ''
    window.history.replaceState({}, '', `${window.location.pathname}${suffix}`)
  }
  const runSearch = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    if (view === 'mediazione') {
      setQuery(trimmed)
      setSelectedId('')
      const params = new URLSearchParams(window.location.search)
      params.set('q', trimmed)
      params.delete('scheda')
      window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
      return
    }
    if (view !== 'ricerca-legale') {
      window.location.href = `/ricerca-legale?q=${encodeURIComponent(trimmed)}`
      return
    }
    setQuery(trimmed)
    setSelectedId('')
    updateSearchUrl(trimmed)
    setSubmittedQuery(trimmed)
  }
  const submitSearch = () => {
    const trimmed = query.trim()
    if (!trimmed) {
      resetSearch()
      return
    }
    runSearch(trimmed)
  }
  const resetSearch = () => {
    setQuery('')
    setSelectedId('')
    setRecordKind('')
    setRecordSource('')
    setRecordArea('')
    setRecordState('')
    setRecordScope('')
    setRecordQuality('')
    if (view === 'mediazione') {
      setMediazioneStatus('')
      setMediazioneSection('')
      setMediazioneType('')
      setMediazioneTerritory('')
      setMediazioneContact('')
      window.history.replaceState({}, '', window.location.pathname)
    }
    if (view === 'ricerca-legale') {
      window.history.replaceState({}, '', window.location.pathname)
      setSubmittedQuery('')
    }
  }
  const runArchiveSearch = (value: string, scope = '', source = '') => {
    setRecordScope(scope)
    setRecordSource(source)
    setRecordQuality('letta')
    runSearch(value)
    window.requestAnimationFrame(() => document.getElementById('legal-intelligence-search')?.focus())
  }
  const openRecord = (record: LegalIntelligenceRecord) => {
    setSelectedId(record.id)
    const params = new URLSearchParams(window.location.search)
    if (view === 'ricerca-legale' && submittedQuery) params.set('q', submittedQuery)
    if (view === 'mediazione' && query) params.set('q', query)
    if (recordKind) params.set('tipo', recordKind)
    if (recordSource) params.set('fonte', recordSource)
    if (recordArea) params.set('area', recordArea)
    if (recordState) params.set('stato', recordState)
    if (recordScope) params.set('ambito', recordScope)
    if (recordQuality) params.set('qualita', recordQuality)
    params.set('scheda', record.id)
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
    window.requestAnimationFrame(() => document.querySelector('.iu-li-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
  if (loading) {
    return <LoadingState title={`Caricamento ${pageTitle(view)}`} message="Recupero delle informazioni reali." />
  }
  return (
    <Page
      title={pageTitle(view)}
      subtitle={pageSubtitle(view)}
      actions={(
        <>
          {view !== 'ricerca-legale' ? <ButtonLink href="/ricerca-legale" tone="primary">Nuova ricerca</ButtonLink> : null}
          <ButtonLink href="/lex-operativo" tone="neutral"><MessageCircle size={16} aria-hidden="true" />Lex Chat AI</ButtonLink>
          <ButtonLink href="/giurisprudenza" tone="neutral"><Archive size={16} aria-hidden="true" />Archivio giurisprudenza</ButtonLink>
        </>
      )}
    >
      <div className="iu-li-page">
        <WarningList data={data} />
        <NavigationTabs view={view} />
        {view === 'ricerca-legale' ? <DataAccessPanel data={data} onArchiveSearch={runArchiveSearch} /> : null}
        {view !== 'mediazione' ? (
          <RecordFilters
            view={view}
            query={query}
            submittedQuery={submittedQuery}
            loading={loading}
            kind={recordKind}
            source={recordSource}
            area={recordArea}
            state={recordState}
            scope={recordScope}
            quality={recordQuality}
            kinds={kindOptions}
            sources={sourceOptions}
            areas={areaOptions}
            states={stateOptions}
            onQuery={setQuery}
            onKind={setRecordKind}
            onSource={setRecordSource}
            onArea={setRecordArea}
            onState={setRecordState}
            onScope={setRecordScope}
            onQuality={setRecordQuality}
            onSubmit={submitSearch}
            onReset={resetSearch}
            onQuickSearch={runSearch}
          />
        ) : null}
        <div className="iu-li-workbench">
          <div className="iu-li-workbench__main">
            {view === 'mediazione' ? (
              <MediazioneRegistryExplorer
                records={filteredMediazioneRegistryRecords}
                allRecords={mediazioneRegistryRecords}
                query={query}
                section={mediazioneSection}
                status={mediazioneStatus}
                type={mediazioneType}
                territory={mediazioneTerritory}
                contact={mediazioneContact}
                onQuery={setQuery}
                onSubmit={submitSearch}
                onSection={setMediazioneSection}
                onStatus={setMediazioneStatus}
                onType={setMediazioneType}
                onTerritory={setMediazioneTerritory}
                onContact={setMediazioneContact}
                onReset={() => {
                  setMediazioneStatus('')
                  setMediazioneSection('')
                  setMediazioneType('')
                  setMediazioneTerritory('')
                  setMediazioneContact('')
                  resetSearch()
                }}
                onOpen={openRecord}
              />
            ) : null}
            <section id="schede" className="iu-li-results" aria-label="Schede ricerca legale">
              <ResultHeader
                view={view}
                visibleCount={visibleRecords.length}
                totalCount={data.records.length}
                submittedQuery={submittedQuery}
              />
              {visibleRecords.length && view !== 'mediazione' ? (
                <div className={[openDesignLegalKnowledgeSurface.legalList, 'iu-li-results-list'].join(' ')}>
                  {visibleRecords.map((record) => (
                    <RecordCard
                      record={record}
                      selected={selectedRecord?.id === record.id}
                      onOpen={openRecord}
                      key={`${record.kind}-${record.id}`}
                    />
                  ))}
                </div>
              ) : view === 'mediazione' && mediazioneOfficialRecords.length ? (
                <div className={[openDesignLegalKnowledgeSurface.legalList, 'iu-li-results-list'].join(' ')}>
                  {mediazioneOfficialRecords.map((record) => (
                    <RecordCard
                      record={record}
                      selected={selectedRecord?.id === record.id}
                      onOpen={openRecord}
                      key={`${record.kind}-${record.id}`}
                    />
                  ))}
                </div>
              ) : (
                <EmptyState
                  title={view === 'ricerca-legale' ? 'Nessuna fonte trovata' : 'Nessuna scheda da mostrare'}
                  message={view === 'ricerca-legale'
                    ? 'Prova con riferimenti normativi, parole chiave pi\u00f9 precise o una materia giuridica specifica.'
                    : 'Non sono disponibili schede compatibili con questa vista o con il filtro applicato.'}
                  action={<ButtonLink href="/giurisprudenza" tone="neutral">Apri giurisprudenza</ButtonLink>}
                />
              )}
            </section>
          </div>
          <RecordDetail record={selectedRecord} view={view} onSearchRelated={runSearch} />
        </div>
      </div>
    </Page>
  )
}
