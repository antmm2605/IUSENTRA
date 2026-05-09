import { useEffect, useMemo, useState } from 'react'
import { BookOpen, ExternalLink, FileText, Filter, RefreshCw, Search, ShieldCheck, Tags } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import {
  emptyTemplateAttiPage,
  getTemplateAttiCatalogoPage,
  getTemplateAttiPage,
  type TemplateAttiPageData,
  type TemplateAttiRecord,
} from '../templateAttiData'
import { displaySourceLabel, displayWritesLabel } from '../displayText'
import './TemplateAttiPage.css'

function isCatalogoRoute() {
  return (window.location.pathname.replace(/\/+$/, '') || '/').toLowerCase() === '/template-atti/catalogo'
}

function ContractStrip({ data }: { data: TemplateAttiPageData }) {
  return (
    <aside className="iu-doc-contract iu-od-surface">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {displaySourceLabel(data.source)} - {displayWritesLabel(data.contracts.writes)}
        </span>
      </div>
    </aside>
  )
}

function WarningList({ data }: { data: TemplateAttiPageData }) {
  if (!data.warnings.length) return null
  return (
    <div className="iu-doc-warnings" role="status">
      {data.warnings.map((warning) => (
        <p className="iu-doc-warning iu-od-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </div>
  )
}

function Metrics({ data }: { data: TemplateAttiPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-doc-metrics" aria-label="KPI template atti">
      {data.metrics.map((metric) => (
        <KpiCard
          key={metric.id}
          label={metric.label}
          value={metric.value || 0}
          note={metric.note}
          badge={<Badge tone={metric.tone}>{metric.tone === 'neutral' ? 'Dato' : 'Attivo'}</Badge>}
        />
      ))}
    </section>
  )
}

function Sections({ data }: { data: TemplateAttiPageData }) {
  if (!data.sections.length) return null
  return (
    <section className="iu-doc-section-grid" aria-label="Metadati template atti">
      {data.sections.map((section) => (
        <Panel title={section.title} subtitle={section.kind} key={section.id}>
          {section.items.length ? (
            <div className="iu-doc-chip-list">
              {section.items.map((item) => (
                <span className="iu-doc-chip" key={item.id}>
                  <strong>{item.label}</strong>
                  <span>{item.value || 'Dato'}</span>
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

function TemplateCard({ record }: { record: TemplateAttiRecord }) {
  return (
    <article className="iu-template-card iu-od-card">
      <header className="iu-template-card__header">
        <div>
          <span className="iu-template-card__kind">{record.kind}</span>
          <h3>{record.title}</h3>
          {record.subtitle ? <p>{record.subtitle}</p> : null}
        </div>
        {record.stateLabel ? <Badge tone={record.stateTone}>{record.stateLabel}</Badge> : null}
      </header>
      {record.description ? <p className="iu-template-card__description">{record.description}</p> : null}
      <dl className="iu-template-meta">
        {record.category ? (
          <div>
            <dt>Categoria</dt>
            <dd>{record.category}</dd>
          </div>
        ) : null}
        {record.matter || record.area ? (
          <div>
            <dt>Materia</dt>
            <dd>{record.matter || record.area}</dd>
          </div>
        ) : null}
        {record.channel ? (
          <div>
            <dt>Canale</dt>
            <dd>{record.channel}</dd>
          </div>
        ) : null}
        {record.updatedAt ? (
          <div>
            <dt>Aggiornato</dt>
            <dd>{record.updatedAt}</dd>
          </div>
        ) : null}
      </dl>
      {record.complianceLabel ? (
        <div className="iu-template-badges">
          <Badge tone="info">{record.complianceLabel}</Badge>
          {record.portal ? <Badge tone="neutral">{record.portal}</Badge> : null}
        </div>
      ) : null}
      {record.requiredVariables.length ? (
        <div className="iu-template-vars">
          <span className="iu-template-vars__label">
            <Tags size={15} aria-hidden="true" />
            Variabili richieste
          </span>
          <div className="iu-template-vars__list">
            {record.requiredVariables.map((variable) => (
              <span className="iu-template-var" key={`${record.id}-${variable.name}`}>
                {variable.label || variable.name}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <footer className="iu-od-action-row iu-template-card__actions">
        <ButtonLink href={record.href} tone="primary">
          <ExternalLink size={16} aria-hidden="true" />
          Apri scheda
        </ButtonLink>
        {record.detailHref ? (
          <ButtonLink href={record.detailHref} tone="neutral">
            Metadati
          </ButtonLink>
        ) : null}
      </footer>
    </article>
  )
}

function CatalogFilters({
  query,
  category,
  channel,
  categories,
  channels,
  onQuery,
  onCategory,
  onChannel,
}: {
  query: string
  category: string
  channel: string
  categories: string[]
  channels: string[]
  onQuery: (value: string) => void
  onCategory: (value: string) => void
  onChannel: (value: string) => void
}) {
  return (
    <section className="iu-template-filters iu-od-card" aria-label="Filtri catalogo template">
      <div className="iu-template-filter">
        <label htmlFor="template-search">
          <Search size={15} aria-hidden="true" />
          Cerca
        </label>
        <input id="template-search" value={query} onChange={(event) => onQuery(event.target.value)} />
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-category">
          <Filter size={15} aria-hidden="true" />
          Categoria
        </label>
        <select id="template-category" value={category} onChange={(event) => onCategory(event.target.value)}>
          <option value="">Tutte</option>
          {categories.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-channel">
          <BookOpen size={15} aria-hidden="true" />
          Canale
        </label>
        <select id="template-channel" value={channel} onChange={(event) => onChannel(event.target.value)}>
          <option value="">Tutti</option>
          {channels.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
    </section>
  )
}

export function TemplateAttiPage() {
  const catalogo = isCatalogoRoute()
  const [data, setData] = useState<TemplateAttiPageData>(emptyTemplateAttiPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [channel, setChannel] = useState('')

  function load() {
    setLoading(true)
    const loader = catalogo ? getTemplateAttiCatalogoPage : getTemplateAttiPage
    loader()
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [catalogo])

  const categories = useMemo(
    () => [...new Set(data.records.map((record) => record.category).filter(Boolean))].sort(),
    [data.records],
  )
  const channels = useMemo(
    () => [...new Set(data.records.map((record) => record.channel).filter(Boolean))].sort(),
    [data.records],
  )
  const filteredRecords = useMemo(() => {
    const search = query.trim().toLowerCase()
    return data.records.filter((record) => {
      const matchesSearch = !search || [record.title, record.subtitle, record.description, record.category, record.matter, record.area]
        .join(' ')
        .toLowerCase()
        .includes(search)
      const matchesCategory = !category || record.category === category
      const matchesChannel = !channel || record.channel === channel
      return matchesSearch && matchesCategory && matchesChannel
    })
  }, [category, channel, data.records, query])

  if (loading) {
    return <LoadingState title="Caricamento template atti" message="Recupero catalogo e metadati reali." />
  }

  return (
    <Page
      title={catalogo ? 'Catalogo template atti' : 'Template atti'}
      subtitle="Superficie documentale di ingresso con soli metadati e azioni controllate."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>
          <ButtonLink href="/redazione-atti" tone="primary">
            Redazione atti
          </ButtonLink>
        </>
      }
    >
      <div className="iu-template-page iu-od-stack">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics data={data} />
        <section className="iu-template-hero iu-od-surface">
          <div>
            <p className="iu-template-eyebrow">Documenti e modelli</p>
            <h2>{catalogo ? 'Catalogo consultabile senza contenuti integrali' : 'Ingresso operativo ai template dello studio'}</h2>
            <p>
              La pagina mostra catalogo, categorie, materie, canali e variabili come metadati. Editor, compilazione,
              produzione file ed esportazioni restano nei percorsi dedicati e auditati.
            </p>
          </div>
          <div className="iu-od-action-row iu-template-hero__actions">
            {data.actions.map((action) => (
              <ButtonLink key={action.id} href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'}>
                <ExternalLink size={16} aria-hidden="true" />
                {action.label}
              </ButtonLink>
            ))}
          </div>
        </section>
        {!catalogo ? <Sections data={data} /> : null}
        {catalogo ? (
          <CatalogFilters
            query={query}
            category={category}
            channel={channel}
            categories={categories}
            channels={channels}
            onQuery={setQuery}
            onCategory={setCategory}
            onChannel={setChannel}
          />
        ) : null}
        <Panel
          title={catalogo ? 'Template del catalogo' : 'Template principali'}
          subtitle={catalogo ? 'Filtri applicati solo sui dati ricevuti.' : 'Metadati reali e collegamenti sicuri.'}
        >
          {filteredRecords.length ? (
            <div className="iu-template-grid">
              {filteredRecords.map((record) => (
                <TemplateCard record={record} key={record.id} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Nessun template disponibile"
              message="La schermata resta neutra finche' non sono disponibili metadati consultabili."
              action={
                <ButtonLink href="/documenti" tone="neutral">
                  Apri documenti
                </ButtonLink>
              }
            />
          )}
        </Panel>
        <aside className="iu-template-source iu-od-meta">
          Presidio dati: {displaySourceLabel(data.source)} - aggiornato {data.generated_at || 'non indicato'}
        </aside>
      </div>
    </Page>
  )
}
