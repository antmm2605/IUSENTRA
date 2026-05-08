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
  return 'Legal Intelligence'
}

function pageSubtitle(view: LegalIntelligenceView) {
  if (view === 'news') return 'News giuridiche gia presenti nel backend, con fonte, materia e stato pubblicazione.'
  if (view === 'mediazione') return 'Consultazione del registro mediazione gia disponibile nel backend.'
  if (view === 'ricerca-legale') return 'Hub di consultazione verso Legal Intelligence, senza nuova pipeline.'
  return 'Dashboard di monitoraggio fonti, news e registri, esposta in React solo come consultazione.'
}

async function loadPage(view: LegalIntelligenceView): Promise<LegalIntelligencePageData> {
  if (view === 'news') return getLegalIntelligenceNewsPage()
  if (view === 'mediazione') return getLegalIntelligenceMediazionePage()
  if (view === 'ricerca-legale') return getRicercaLegalePage()
  return getLegalIntelligencePage()
}

function ContractStrip({ data }: { data: LegalIntelligencePageData }) {
  return (
    <aside className="iu-li-contract iu-od-evidence-panel">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {data.source || 'Repository'} - sorgente canonica {data.contracts.canonical_source || 'backend storico'}
        </span>
      </div>
    </aside>
  )
}

function WarningList({ data }: { data: LegalIntelligencePageData }) {
  if (!data.warnings.length) return null
  return (
    <section className="iu-li-warnings" aria-label="Avvisi Legal Intelligence">
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
    <section className="iu-li-metrics" aria-label="KPI Legal Intelligence">
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
    <nav className="iu-li-tabs iu-od-source-card" aria-label="Sezioni Legal Intelligence">
      <ButtonLink href="/legal-intelligence" tone={view === 'dashboard' ? 'primary' : 'neutral'} className={view === 'dashboard' ? 'iu-li-tab--active' : 'iu-li-tab'}>
        Dashboard
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
    <section className="iu-li-section-grid" aria-label="Snapshot Legal Intelligence">
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

function RecordCard({ record }: { record: LegalIntelligenceRecord }) {
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
          <ButtonLink href={record.legacyHref} tone="primary">
            {record.kind === 'mediazione' ? <Landmark size={16} aria-hidden="true" /> : <Newspaper size={16} aria-hidden="true" />}
            Apri scheda
          </ButtonLink>
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

function RecordFilters({
  query,
  onQuery,
}: {
  query: string
  onQuery: (value: string) => void
}) {
  return (
    <section className="iu-li-filters iu-od-source-card" aria-label="Filtro risultati Legal Intelligence">
      <label htmlFor="legal-intelligence-search">
        <Search size={15} aria-hidden="true" />
        Cerca
      </label>
      <input id="legal-intelligence-search" value={query} onChange={(event) => onQuery(event.target.value)} />
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
  const [query, setQuery] = useState('')

  useEffect(() => {
    let active = true
    loadPage(view)
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [view])

  const visibleRecords = useMemo(() => data.records.filter((record) => includesText([
    record.title,
    record.subtitle,
    record.sourceLabel,
    record.sourceKind,
    record.area,
    record.branch,
    record.territory,
    record.registryNumber,
  ].join(' '), query)), [data.records, query])

  if (loading) {
    return <LoadingState title={`Caricamento ${pageTitle(view)}`} message="Recupero dei metadati reali dal backend." />
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
        <RecordFilters query={query} onQuery={setQuery} />
        <Panel
          title={view === 'mediazione' ? 'Registro mediazione' : view === 'news' ? 'News disponibili' : 'Elementi di monitoraggio'}
          subtitle={`${visibleRecords.length} elementi visibili su ${data.records.length} metadati disponibili.`}
          actions={
            query ? (
              <Button type="button" tone="neutral" onClick={() => setQuery('')}>
                Azzera filtro
              </Button>
            ) : null
          }
        >
          {visibleRecords.length ? (
            <div className={openDesignLegalKnowledgeSurface.legalList}>
              {visibleRecords.map((record) => (
                <RecordCard record={record} key={`${record.kind}-${record.id}`} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Nessun elemento da mostrare"
              message="Il backend non espone metadati compatibili con questa vista o con il filtro applicato."
              action={<ButtonLink href="/giurisprudenza" tone="neutral">Apri giurisprudenza</ButtonLink>}
            />
          )}
        </Panel>
      </div>
    </Page>
  )
}
