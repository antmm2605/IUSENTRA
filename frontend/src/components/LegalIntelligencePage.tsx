import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  Landmark,
  ListChecks,
  Newspaper,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { openDesignContract, openDesignLegalKnowledgeSurface } from '../ui/openDesign'
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
  mediazione: ['registro organismi mediazione', 'elenco enti mediazione', 'formatori mediazione'],
  'ricerca-legale': ['mediazione obbligatoria', 'Cassazione prescrizione', 'credito imposta investimenti', 'usura bancaria tasso soglia'],
}

function currentView(): LegalIntelligenceView {
  const route = (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase()
  // path canonici (v2.242.0+): /ricerca-legale/* è la home; /legal-intelligence/*
  // viene ridiretto lato server con HTTP 301.
  if (route === '/ricerca-legale/news' || route === '/legal-intelligence/news') return 'news'
  if (route === '/ricerca-legale/mediazione' || route === '/legal-intelligence/mediazione') return 'mediazione'
  if (route === '/ricerca-legale/ricerca') return 'ricerca-legale'
  if (route === '/ricerca-legale') return 'dashboard'
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
  return 'Cruscotto fonti, news e registri con contesto leggibile prima di aprire la fonte originale.'
}

function viewBrief(view: LegalIntelligenceView) {
  if (view === 'news') {
    return {
      eyebrow: 'Aggiornamenti',
      title: 'Prima leggi cosa cambia, poi apri la fonte quando serve.',
      body: 'Ogni notizia diventa una scheda con estratto, materia, provenienza e controllo professionale, così il contenuto è utile anche senza uscire dalla pagina.',
      steps: ['Contesto sintetico', 'Materia e data', 'Controllo fonte'],
    }
  }
  if (view === 'mediazione') {
    return {
      eyebrow: 'Mediazione',
      title: 'Registri consultabili con il perché operativo già in pagina.',
      body: 'Organismi, enti e formatori non sono semplici accessi esterni: la scheda indica cosa verificare, quando e con quale attendibilità.',
      steps: ['Registro corretto', 'Ambito della verifica', 'Fonte ministeriale'],
    }
  }
  if (view === 'ricerca-legale') {
    return {
      eyebrow: 'Ricerca assistita',
      title: 'Trova la fonte e valuta subito se serve al fascicolo.',
      body: 'La ricerca costruisce una scheda interna con estratto, provenienza, data, utilità pratica e avvertenza di affidabilità, lasciando la fonte originale come verifica finale.',
      steps: ['Cerca', 'Leggi il contesto', "Valuta l'uso"],
    }
  }
  return {
    eyebrow: 'Cruscotto fonti',
    title: 'La conoscenza legale entra nel lavoro, non resta fuori dalla pagina.',
    body: 'IUSENTRA raccoglie aggiornamenti, registri e fonti censite in schede operative: contenuto, provenienza e prossima verifica sono leggibili nello stesso spazio.',
    steps: ['Fonti governate', 'Schede interne', 'Azioni reali'],
  }
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

function isOfficial(record: LegalIntelligenceRecord) {
  return [record.sourceKind, record.approvalLabel, record.evidenceType].join(' ').toLocaleLowerCase('it-IT').includes('ufficiale')
}

function contextItems(record: LegalIntelligenceRecord) {
  if (record.sourceContext.length) return record.sourceContext
  return [
    record.sourceExcerpt ? `Contenuto: ${record.sourceExcerpt}` : '',
    record.area || record.branch ? `Ambito: ${[record.area, record.branch].filter(Boolean).join(' / ')}` : '',
    record.date ? `Aggiornamento: ${record.date}` : '',
    record.sourceLabel ? `Provenienza: ${record.sourceLabel}` : '',
  ].filter(Boolean)
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

function ContractStrip({ data }: { data: LegalIntelligencePageData }) {
  const officialRecords = data.records.filter(isOfficial).length
  return (
    <aside className="iu-li-contract iu-od-evidence-panel">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>{officialRecords} fonti ufficiali o istituzionali con contesto leggibile in IUSENTRA</span>
      </div>
    </aside>
  )
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

function Metrics({ data }: { data: LegalIntelligencePageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-li-metrics" aria-label="Indicatori ricerca legale">
      {data.metrics.map((metric) => (
        <KpiCard
          key={metric.id}
          label={metric.label}
          value={metric.value || 0}
          note={metric.note}
          badge={<Badge tone={metric.tone}>{metric.tone === 'neutral' ? 'Dato' : 'Stato'}</Badge>}
        />
      ))}
    </section>
  )
}

function NavigationTabs({ view }: { view: LegalIntelligenceView }) {
  // Path canonici sotto /ricerca-legale (v2.242.0+). Il vecchio /legal-intelligence/*
  // resta accessibile e viene ridiretto 301 lato server.
  const items: Array<[LegalIntelligenceView, string, string]> = [
    ['dashboard', 'Cruscotto', '/ricerca-legale'],
    ['news', 'News', '/ricerca-legale/news'],
    ['mediazione', 'Mediazione', '/ricerca-legale/mediazione'],
    ['ricerca-legale', 'Ricerca legale', '/ricerca-legale/ricerca'],
  ]
  return (
    <nav className="iu-li-tabs iu-od-source-card" aria-label="Sezioni ricerca legale">
      {items.map(([itemView, label, href]) => (
        <ButtonLink
          key={itemView}
          href={href}
          tone={view === itemView ? 'primary' : 'neutral'}
          className={view === itemView ? 'iu-li-tab--active' : 'iu-li-tab'}
          aria-current={view === itemView ? 'page' : undefined}
        >
          {label}
        </ButtonLink>
      ))}
    </nav>
  )
}

function WorkbenchBrief({ view }: { view: LegalIntelligenceView }) {
  const brief = viewBrief(view)
  return (
    <section className="iu-li-brief iu-od-evidence-panel" aria-label="Metodo di ricerca">
      <div className="iu-li-brief__copy">
        <span className="iu-li-eyebrow">{brief.eyebrow}</span>
        <h2>{brief.title}</h2>
        <p>{brief.body}</p>
      </div>
      <div className="iu-li-brief__steps" aria-label="Percorso operativo">
        {brief.steps.map((step, index) => (
          <span className="iu-li-step" key={step}>
            <CheckCircle2 size={16} aria-hidden="true" />
            {index + 1}. {step}
          </span>
        ))}
      </div>
    </section>
  )
}

function SourceMap({ data, view }: { data: LegalIntelligencePageData; view: LegalIntelligenceView }) {
  const visible = view === 'news'
    ? data.sections.filter((section) => ['news', 'materie', 'distinzione'].includes(section.id))
    : view === 'mediazione'
      ? data.sections.filter((section) => ['mediazione', 'distinzione'].includes(section.id))
      : view === 'ricerca-legale'
        ? data.sections.filter((section) => ['ricerca', 'fonti', 'distinzione'].includes(section.id))
        : data.sections.filter((section) => ['fonti', 'news', 'mediazione', 'distinzione'].includes(section.id))

  if (!visible.length) return null
  return (
    <section className="iu-li-source-map" aria-label="Mappa fonti e controlli">
      <header className="iu-li-section-head">
        <ListChecks size={18} aria-hidden="true" />
        <div>
          <h2>Mappa del contesto</h2>
          <p>Da dove arrivano le informazioni e come leggerle nello studio.</p>
        </div>
      </header>
      <div className="iu-li-source-map__grid">
        {visible.map((section) => (
          <article className="iu-li-source-map__card iu-od-source-card" key={section.id}>
            <span className="iu-od-source-badge">{section.kind}</span>
            <h3>{section.title}</h3>
            {section.items.length ? (
              <div className="iu-li-chip-list">
                {section.items.slice(0, 4).map((item) => (
                  <span className="iu-li-chip" key={`${section.id}-${item.id}`}>
                    <strong>{item.label}</strong>
                    <span>{item.value || 'Disponibile'}</span>
                    {item.note ? <small>{item.note}</small> : null}
                  </span>
                ))}
              </div>
            ) : (
              <EmptyState title={section.emptyMessage} />
            )}
          </article>
        ))}
      </div>
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
    ['Data', record.date],
    ['Area', record.area],
    ['Materia', record.branch],
    ['Territorio', record.territory],
    ['Registro', record.registryNumber],
  ].filter((item) => item[1])
  const stateLabel = record.approvalLabel || record.stateLabel
  const stateTone = record.approvalLabel ? record.approvalTone : record.stateTone
  const summaryItems = contextItems(record).slice(0, 3)

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
      {summaryItems.length ? (
        <ul className="iu-li-context-list" aria-label="Contesto disponibile">
          {summaryItems.map((item) => (
            <li key={`${record.id}-${item}`}>{item}</li>
          ))}
        </ul>
      ) : null}
      <dl className="iu-li-meta">
        {metaItems.map(([label, value]) => (
          <div key={`${record.id}-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-li-evidence-row">
        <span className="iu-od-source-badge">{record.evidenceType || 'informazione'}</span>
        {record.sourceKind ? <span className="iu-od-source-badge">{record.sourceKind}</span> : null}
      </div>
      <footer className="iu-od-action-row iu-li-record__actions">
        <Button type="button" tone="primary" onClick={() => onOpen(record)}>
          <BookOpen size={16} aria-hidden="true" />
          Leggi contesto
        </Button>
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer">
            <ExternalLink size={16} aria-hidden="true" />
            Fonte originale
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
  const sourceMeta = [
    ['Fonte', record.sourceLabel || 'Non indicata'],
    ['Tipo', record.sourceKind || 'Non indicato'],
    ['Data', record.date || 'Non indicata'],
    ['Area', record.area || record.branch || 'Non indicata'],
  ]
  return (
    <aside className="iu-li-detail iu-od-source-card" aria-label="Contesto fonte">
      <div className="iu-li-detail__intro">
        <span className="iu-od-source-badge">{recordIcon(record)}{record.kind}</span>
        <h2>{record.title}</h2>
        <p>{record.sourceExcerpt || record.subtitle || 'Scheda disponibile con metadati e fonte collegata.'}</p>
      </div>
      <div className="iu-li-detail__reading">
        <h3>Contesto in IUSENTRA</h3>
        <ul className="iu-li-context-list">
          {items.map((item) => (
            <li key={`${record.id}-detail-${item}`}>{item}</li>
          ))}
        </ul>
      </div>
      <div className="iu-li-detail__grid">
        <section className="iu-li-detail__box">
          <h3>Uso pratico</h3>
          <p>{practicalUse(record)}</p>
        </section>
        <section className="iu-li-detail__box">
          <h3>Attendibilità</h3>
          <p>{reliabilityNote(record)}</p>
        </section>
      </div>
      <dl className="iu-li-meta iu-li-detail__meta">
        {sourceMeta.map(([label, value]) => (
          <div key={`${record.id}-detail-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-od-action-row iu-li-detail__actions">
        <Button type="button" tone="primary" onClick={() => onSearchRelated(relatedQuery(record))}>
          <Search size={16} aria-hidden="true" />
          Cerca collegati
        </Button>
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer">
            <ExternalLink size={16} aria-hidden="true" />
            Apri fonte originale
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
  onQuery,
  onSubmit,
  onReset,
  onQuickSearch,
}: {
  view: LegalIntelligenceView
  query: string
  submittedQuery: string
  loading: boolean
  onQuery: (value: string) => void
  onSubmit: () => void
  onReset: () => void
  onQuickSearch: (value: string) => void
}) {
  const isSearch = view === 'ricerca-legale'
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
            placeholder={isSearch ? 'Es. mediazione, Cassazione, prescrizione, decreto' : 'Filtra per materia, fonte o data'}
          />
        </label>
        {isSearch ? (
          <Button type="submit" tone="primary" disabled={loading || !query.trim()}>
            <Search size={16} aria-hidden="true" />
            Costruisci scheda
          </Button>
        ) : null}
        {(isSearch ? submittedQuery : query) ? (
          <Button type="button" tone="neutral" onClick={onReset}>
            Azzera
          </Button>
        ) : null}
      </form>
      <div className="iu-li-quick-row" aria-label="Ricerche guidate">
        {quickQueries[view].map((item) => (
          <Button type="button" tone="neutral" key={item} onClick={() => onQuickSearch(item)}>
            <ArrowRight size={15} aria-hidden="true" />
            {item}
          </Button>
        ))}
      </div>
      {isSearch && submittedQuery ? <p className="iu-li-search-note">Scheda costruita per "{submittedQuery}".</p> : null}
    </section>
  )
}

function MediazioneImportPanel() {
  // Pannello sempre disponibile per mediazione: il portale ministeriale spesso
  // richiede Edge in modalita IE per esportare l'elenco. L'avvocato puo':
  // 1) lanciare la sincronizzazione automatica (se il registro diretto e' raggiungibile),
  // 2) salvare l'HTML completo della pagina ufficiale e caricarlo qui.
  return (
    <section className="iu-li-mediazione-import iu-od-source-card" aria-label="Carica o sincronizza registro mediazione">
      <header className="iu-li-section-head">
        <ListChecks size={18} aria-hidden="true" />
        <div>
          <h2>Carica tutti gli organismi</h2>
          <p>Sincronizza il registro ministeriale o carica uno snapshot HTML per popolare l'elenco completo.</p>
        </div>
      </header>
      <div className="iu-li-mediazione-import__quick">
        <form method="post" action="/ricerca-legale/mediazione/sync" className="iu-li-mediazione-import__sync">
          <Button type="submit" tone="primary">
            <Search size={16} aria-hidden="true" />
            Sincronizza registro ufficiale
          </Button>
          <small>Tenta il fetch diretto da mediazione.giustizia.it.</small>
        </form>
        <a
          className="iu-li-mediazione-import__official"
          href="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX"
          target="_blank"
          rel="noopener noreferrer"
        >
          Apri registro ministeriale
          <ExternalLink size={14} aria-hidden="true" />
        </a>
      </div>
      <div className="iu-li-mediazione-import__divider"><span>oppure carica snapshot HTML</span></div>
      <form
        method="post"
        action="/ricerca-legale/mediazione/import"
        encType="multipart/form-data"
        className="iu-li-mediazione-import__form"
      >
        <label className="iu-li-mediazione-import__field">
          <span>File HTML del registro</span>
          <input type="file" name="snapshot_file" accept=".html,.htm,text/html" />
          <small>Salva la pagina completa (Ctrl+S → "Pagina Web, solo HTML"). Niente MHTML.</small>
        </label>
        <label className="iu-li-mediazione-import__field">
          <span>Sorgente HTML incollato</span>
          <textarea
            name="html_content"
            rows={5}
            placeholder="Incolla qui il sorgente HTML della pagina ufficiale salvata dal browser"
          />
        </label>
        <div className="iu-li-mediazione-import__actions">
          <Button type="submit" tone="neutral">
            <BookOpen size={16} aria-hidden="true" />
            Importa snapshot HTML
          </Button>
        </div>
      </form>
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
      ? 'News con contesto'
      : view === 'ricerca-legale'
        ? 'Fonti contestualizzate'
        : 'Elementi governati'
  const subtitle = view === 'ricerca-legale' && submittedQuery
    ? `${visibleCount} schede costruite per "${submittedQuery}".`
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
  const [view] = useState<LegalIntelligenceView>(() => currentView())
  const [data, setData] = useState<LegalIntelligencePageData>(emptyLegalIntelligencePage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState(() => (currentView() === 'ricerca-legale' ? initialQuery() : ''))
  const [submittedQuery, setSubmittedQuery] = useState(() => (currentView() === 'ricerca-legale' ? initialQuery() : ''))
  const [selectedId, setSelectedId] = useState(new URLSearchParams(window.location.search).get('scheda') || '')

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
  const visibleRecords = useMemo(() => data.records.filter((record) => includesText([
    record.title,
    record.subtitle,
    record.sourceExcerpt,
    record.sourceContext.join(' '),
    record.practicalUse,
    record.reliabilityNote,
    record.sourceLabel,
    record.sourceKind,
    record.area,
    record.branch,
    record.territory,
    record.registryNumber,
  ].join(' '), localFilter)), [data.records, localFilter])
  const selectedRecord = data.records.find((record) => record.id === selectedId) || visibleRecords[0]

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
    if (view === 'ricerca-legale') {
      window.history.replaceState({}, '', window.location.pathname)
      setSubmittedQuery('')
    }
  }

  const openRecord = (record: LegalIntelligenceRecord) => {
    setSelectedId(record.id)
    const params = new URLSearchParams(window.location.search)
    if (view === 'ricerca-legale' && submittedQuery) params.set('q', submittedQuery)
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
          <ButtonLink href="/giurisprudenza" tone="neutral">Archivio giurisprudenza</ButtonLink>
        </>
      )}
    >
      <div className="iu-li-page">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <NavigationTabs view={view} />
        <WorkbenchBrief view={view} />
        <Metrics data={data} />
        <div className="iu-li-workbench">
          <div className="iu-li-workbench__main">
            <RecordFilters
              view={view}
              query={query}
              submittedQuery={submittedQuery}
              loading={loading}
              onQuery={setQuery}
              onSubmit={submitSearch}
              onReset={resetSearch}
              onQuickSearch={runSearch}
            />
            <SourceMap data={data} view={view} />
            {view === 'mediazione' ? <MediazioneImportPanel /> : null}
            <section className="iu-li-results" aria-label="Schede ricerca legale">
              <ResultHeader
                view={view}
                visibleCount={visibleRecords.length}
                totalCount={data.records.length}
                submittedQuery={submittedQuery}
              />
              {visibleRecords.length ? (
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
              ) : (
                <EmptyState
                  title={view === 'ricerca-legale' ? 'Nessuna fonte trovata' : 'Nessuna scheda da mostrare'}
                  message={view === 'ricerca-legale'
                    ? 'Prova con riferimenti normativi, parole chiave più precise o una materia giuridica specifica.'
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
