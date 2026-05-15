import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, Landmark, Newspaper, Search, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
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

function currentView(): LegalIntelligenceView {
  const route = (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase()
  if (route === '/legal-intelligence/news') return 'news'
  if (route === '/legal-intelligence/mediazione') return 'mediazione'
  if (route === '/ricerca-legale') return 'ricerca-legale'
  return 'dashboard'
}

function pageTitle(view: LegalIntelligenceView) {
  if (view === 'news') return 'News Legali'
  if (view === 'mediazione') return 'Registro Mediazione'
  if (view === 'ricerca-legale') return 'Ricerca Legale'
  return 'Ricerca legale'
}

function pageSubtitle(view: LegalIntelligenceView) {
  if (view === 'news') return 'News giuridiche disponibili, con fonte, materia e stato pubblicazione.'
  if (view === 'mediazione') return 'Registro mediazione disponibile per lo studio.'
  if (view === 'ricerca-legale') return 'Ricerca reale su archivio giuridico, fonti ufficiali e schede collegate.'
  return 'Cruscotto di monitoraggio fonti, news e registri in una vista unica.'
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

function ContractStrip({ data }: { data: LegalIntelligencePageData }) {
  return (
    <aside className="iu-li-contract iu-od-evidence-panel">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>Fonti e aggiornamenti collegati al lavoro dello studio</span>
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
  return (
    <nav className="iu-li-tabs iu-od-source-card" aria-label="Sezioni ricerca legale">
      <ButtonLink href="/legal-intelligence" tone={view === 'dashboard' ? 'primary' : 'neutral'} className={view === 'dashboard' ? 'iu-li-tab--active' : 'iu-li-tab'}>
        Cruscotto
      </ButtonLink>
      <ButtonLink href="/legal-intelligence/news" tone={view === 'news' ? 'primary' : 'neutral'} className={view === 'news' ? 'iu-li-tab--active' : 'iu-li-tab'}>
        News
      </ButtonLink>
      <ButtonLink href="/legal-intelligence/mediazione" tone={view === 'mediazione' ? 'primary' : 'neutral'} className={view === 'mediazione' ? 'iu-li-tab--active' : 'iu-li-tab'}>
        Mediazione
      </ButtonLink>
      <ButtonLink href="/ricerca-legale" tone={view === 'ricerca-legale' ? 'primary' : 'neutral'} className={view === 'ricerca-legale' ? 'iu-li-tab--active' : 'iu-li-tab'}>
        Ricerca legale
      </ButtonLink>
    </nav>
  )
}

function Sections({ data, view }: { data: LegalIntelligencePageData; view: LegalIntelligenceView }) {
  const visible = view === 'news'
    ? data.sections.filter((section) => ['news', 'materie', 'distinzione'].includes(section.id))
    : view === 'mediazione'
      ? data.sections.filter((section) => ['mediazione', 'distinzione'].includes(section.id))
      : data.sections
  if (!visible.length) return null
  return (
    <section className="iu-li-section-grid" aria-label="Riepilogo ricerca legale">
      {visible.map((section) => (
        <Panel title={section.title} subtitle={section.kind} key={section.id}>
          {section.items.length ? (
            <div className="iu-li-chip-list">
              {section.items.map((item) => (
                <span className="iu-li-chip" key={`${section.id}-${item.id}`}>
                  <strong>{item.label}</strong>
                  <span>{item.value || 'Dato'}</span>
                  {item.note ? <small>{item.note}</small> : null}
                </span>
              ))}
            </div>
          ) : (
            <EmptyState title={section.emptyMessage} />
          )}
        </Panel>
      ))}
    </section>
  )
}

function RecordCard({ record, onOpen }: { record: LegalIntelligenceRecord; onOpen: (record: LegalIntelligenceRecord) => void }) {
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

  return (
    <article className="iu-li-record iu-od-source-card">
      <header className="iu-li-record__header">
        <div>
          <span className="iu-od-source-badge">{record.kind}</span>
          <h3>{record.title}</h3>
          {record.subtitle ? <p>{record.subtitle}</p> : null}
        </div>
        {stateLabel ? <Badge tone={stateTone}>{stateLabel}</Badge> : null}
      </header>
      <dl className="iu-li-meta">
        {metaItems.map(([label, value]) => (
          <div key={`${record.id}-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-li-evidence-row">
        <span className="iu-od-source-badge">{record.evidenceType || 'metadato'}</span>
        {record.sourceKind ? <span className="iu-od-source-badge">{record.sourceKind}</span> : null}
      </div>
      <footer className="iu-od-action-row iu-li-record__actions">
        {record.legacyHref ? (
          <Button type="button" tone="primary" onClick={() => onOpen(record)}>
            {record.kind === 'mediazione' ? <Landmark size={16} aria-hidden="true" /> : <Newspaper size={16} aria-hidden="true" />}
            Apri scheda
          </Button>
        ) : null}
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer">
            <ExternalLink size={16} aria-hidden="true" />
            Fonte
          </ButtonLink>
        ) : null}
      </footer>
    </article>
  )
}

function RecordDetail({ record }: { record?: LegalIntelligenceRecord }) {
  if (!record) return null
  return (
    <section className="iu-li-detail iu-od-source-card" aria-label="Scheda selezionata">
      <div>
        <span className="iu-od-source-badge">{record.kind}</span>
        <h2>{record.title}</h2>
        <p>{record.subtitle || 'Scheda operativa disponibile nella stessa pagina.'}</p>
      </div>
      <dl className="iu-li-meta">
        <div><dt>Fonte</dt><dd>{record.sourceLabel || 'Non indicata'}</dd></div>
        <div><dt>Area</dt><dd>{record.area || 'Non indicata'}</dd></div>
        <div><dt>Materia</dt><dd>{record.branch || 'Non indicata'}</dd></div>
        <div><dt>Data</dt><dd>{record.date || 'Non indicata'}</dd></div>
      </dl>
      <div className="iu-od-action-row">
        {record.sourceHref ? <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer">Apri fonte</ButtonLink> : null}
        <ButtonLink href="/giurisprudenza" tone="neutral">Archivio giurisprudenza</ButtonLink>
      </div>
    </section>
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
}: {
  view: LegalIntelligenceView
  query: string
  submittedQuery: string
  loading: boolean
  onQuery: (value: string) => void
  onSubmit: () => void
  onReset: () => void
}) {
  const isSearch = view === 'ricerca-legale'
  return (
    <section className="iu-li-filters iu-od-source-card" aria-label={isSearch ? 'Ricerca fonti legali' : 'Filtro risultati ricerca legale'}>
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
            {isSearch ? 'Cerca fonti, norme e giurisprudenza' : 'Cerca'}
          </span>
          <input
            id="legal-intelligence-search"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder={isSearch ? 'Es. mediazione, Cassazione, prescrizione, decreto' : undefined}
          />
        </label>
        {isSearch ? (
          <Button type="submit" tone="primary" disabled={loading || !query.trim()}>
            <Search size={16} aria-hidden="true" />
            Cerca
          </Button>
        ) : null}
        {(isSearch ? submittedQuery : query) ? (
          <Button type="button" tone="neutral" onClick={onReset}>
            Azzera
          </Button>
        ) : null}
      </form>
      {isSearch && submittedQuery ? <p className="iu-li-search-note">Risultati per "{submittedQuery}".</p> : null}
    </section>
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
    record.sourceLabel,
    record.sourceKind,
    record.area,
    record.branch,
    record.territory,
    record.registryNumber,
  ].join(' '), localFilter)), [data.records, localFilter])
  const selectedRecord = data.records.find((record) => record.id === selectedId) || visibleRecords[0]
  const submitSearch = () => {
    const trimmed = query.trim()
    setSelectedId('')
    if (view === 'ricerca-legale') {
      const params = new URLSearchParams(window.location.search)
      if (trimmed) params.set('q', trimmed)
      else params.delete('q')
      params.delete('scheda')
      const suffix = params.toString() ? `?${params.toString()}` : ''
      window.history.replaceState({}, '', `${window.location.pathname}${suffix}`)
      setSubmittedQuery(trimmed)
    }
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
      actions={<ButtonLink href="/giurisprudenza" tone="neutral">Archivio giurisprudenza</ButtonLink>}
    >
      <div className="iu-li-page">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <NavigationTabs view={view} />
        <Metrics data={data} />
        <Sections data={data} view={view} />
        <RecordFilters
          view={view}
          query={query}
          submittedQuery={submittedQuery}
          loading={loading}
          onQuery={setQuery}
          onSubmit={submitSearch}
          onReset={resetSearch}
        />
        <RecordDetail record={selectedRecord} />
        <Panel
          title={view === 'mediazione' ? 'Registro mediazione' : view === 'news' ? 'News disponibili' : view === 'ricerca-legale' ? 'Risultati ricerca' : 'Elementi di monitoraggio'}
          subtitle={view === 'ricerca-legale' && submittedQuery
            ? `${visibleRecords.length} risultati per "${submittedQuery}".`
            : `${visibleRecords.length} elementi visibili su ${data.records.length} schede disponibili.`}
        >
          {visibleRecords.length ? (
            <div className={openDesignLegalKnowledgeSurface.legalList}>
              {visibleRecords.map((record) => (
                <RecordCard record={record} onOpen={openRecord} key={`${record.kind}-${record.id}`} />
              ))}
            </div>
          ) : (
            <EmptyState
              title={view === 'ricerca-legale' ? 'Nessuna fonte trovata' : 'Nessun elemento da mostrare'}
              message={view === 'ricerca-legale'
                ? 'Prova con riferimenti normativi, parole chiave piu precise o una materia giuridica specifica.'
                : 'Non sono disponibili schede compatibili con questa vista o con il filtro applicato.'}
              action={<ButtonLink href="/giurisprudenza" tone="neutral">Apri giurisprudenza</ButtonLink>}
            />
          )}
        </Panel>
      </div>
    </Page>
  )
}
