import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BookOpen, CheckCircle2, ExternalLink, Filter, RefreshCw, Search, ShieldCheck, Tags } from 'lucide-react'
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
import { displaySourceLabel } from '../displayText'
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
        <span>Catalogo atti collegato ai dati dello studio</span>
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
    <section className="iu-doc-metrics" aria-label="Indicatori template atti">
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
    <section className="iu-doc-section-grid" aria-label="Informazioni template atti">
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

function StudioStampPreview({ data }: { data: TemplateAttiPageData }) {
  if (!data.studioStamp.lines.length) return null
  return (
    <section className="iu-template-stamp iu-od-surface" aria-label="Anteprima timbro studio">
      <div className="iu-template-stamp__preview">
        {data.studioStamp.lines.map((line, index) => (
          <span
            key={`${line.text}-${index}`}
            className={[
              'iu-template-stamp__line',
              line.bold ? 'iu-template-stamp__line--bold' : '',
              line.size >= 12 ? 'iu-template-stamp__line--large' : line.size >= 10 ? 'iu-template-stamp__line--medium' : 'iu-template-stamp__line--small',
            ].filter(Boolean).join(' ')}
          >
            {line.text}
          </span>
        ))}
      </div>
      <div>
        <p className="iu-template-eyebrow">Timbro studio</p>
        <h3>Intestazione applicata automaticamente</h3>
        <p>Il modello usa i dati configurati dello studio e li inserisce prima del titolo dell'atto.</p>
      </div>
    </section>
  )
}

function TemplateCard({ record, onOpen }: { record: TemplateAttiRecord; onOpen: (record: TemplateAttiRecord) => void }) {
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
      <div className="iu-template-badges">
        {record.cartabiaState ? <Badge tone={record.requiresLawyerReview ? 'warning' : 'success'}>{record.cartabiaState.replaceAll('_', ' ')}</Badge> : null}
        {record.prefillStatus === 'precompilabile' ? <Badge tone="success">Precompilabile</Badge> : null}
        {record.requiresLawyerReview ? <Badge tone="warning">Richiede verifica avvocato</Badge> : null}
      </div>
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
        <Button type="button" tone="primary" onClick={() => onOpen(record)}>
          <ExternalLink size={16} aria-hidden="true" />
          Apri scheda
        </Button>
        <ButtonLink href={record.href} tone="neutral">Usa in redazione</ButtonLink>
      </footer>
    </article>
  )
}

function TemplateDetail({ record }: { record?: TemplateAttiRecord }) {
  if (!record) return null
  return (
    <section className="iu-template-detail iu-od-card" aria-label="Scheda template">
      <div>
        <span className="iu-template-card__kind">{record.kind}</span>
        <h2>{record.title}</h2>
        <p>{record.description || record.subtitle || 'Scheda operativa del modello selezionato.'}</p>
      </div>
      <dl className="iu-template-meta">
        <div><dt>Categoria</dt><dd>{record.category || 'Non indicata'}</dd></div>
        <div><dt>Materia</dt><dd>{record.matter || record.area || 'Non indicata'}</dd></div>
        <div><dt>Canale</dt><dd>{record.channel || 'Non indicato'}</dd></div>
        <div><dt>Variabili</dt><dd>{record.requiredVariables.length}</dd></div>
        <div><dt>Cartabia</dt><dd>{record.cartabiaState ? record.cartabiaState.replaceAll('_', ' ') : 'Da verificare'}</dd></div>
        <div><dt>Dati disponibili</dt><dd>{record.prefillAvailable}</dd></div>
      </dl>
      <div className="iu-template-checks">
        <div>
          <strong><CheckCircle2 size={15} aria-hidden="true" /> Fonti dati</strong>
          <p>{record.dataSources.length ? record.dataSources.join(', ') : 'Da selezionare in redazione.'}</p>
        </div>
        <div>
          <strong><AlertTriangle size={15} aria-hidden="true" /> Controlli</strong>
          <p>{record.blockingChecks[0] || record.recommendedChecks[0] || 'Verifica conformita disponibile dalla scheda.'}</p>
        </div>
      </div>
      {record.requiredVariables.length ? (
        <div className="iu-template-vars__list">
          {record.requiredVariables.map((variable) => <span className="iu-template-var" key={`${record.id}-${variable.name}`}>{variable.label || variable.name}</span>)}
        </div>
      ) : null}
      <div className="iu-od-action-row">
        <ButtonLink href={record.href} tone="primary">Usa in Redazione Atti</ButtonLink>
      </div>
    </section>
  )
}

function CatalogFilters({
  query,
  category,
  channel,
  cartabia,
  prefill,
  categories,
  channels,
  cartabiaStates,
  prefillStates,
  onQuery,
  onCategory,
  onChannel,
  onCartabia,
  onPrefill,
}: {
  query: string
  category: string
  channel: string
  cartabia: string
  prefill: string
  categories: string[]
  channels: string[]
  cartabiaStates: string[]
  prefillStates: string[]
  onQuery: (value: string) => void
  onCategory: (value: string) => void
  onChannel: (value: string) => void
  onCartabia: (value: string) => void
  onPrefill: (value: string) => void
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
      <div className="iu-template-filter">
        <label htmlFor="template-cartabia">
          <ShieldCheck size={15} aria-hidden="true" />
          Stato Cartabia
        </label>
        <select id="template-cartabia" value={cartabia} onChange={(event) => onCartabia(event.target.value)}>
          <option value="">Tutti</option>
          {cartabiaStates.map((item) => (
            <option value={item} key={item}>{item.replaceAll('_', ' ')}</option>
          ))}
        </select>
      </div>
      <div className="iu-template-filter">
        <label htmlFor="template-prefill">
          <Tags size={15} aria-hidden="true" />
          Dati
        </label>
        <select id="template-prefill" value={prefill} onChange={(event) => onPrefill(event.target.value)}>
          <option value="">Tutti</option>
          {prefillStates.map((item) => (
            <option value={item} key={item}>{item}</option>
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
  const [cartabia, setCartabia] = useState('')
  const [prefill, setPrefill] = useState('')
  const [selectedId, setSelectedId] = useState(new URLSearchParams(window.location.search).get('scheda') || '')

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
  const cartabiaStates = useMemo(
    () => [...new Set(data.records.map((record) => record.cartabiaState).filter(Boolean))].sort(),
    [data.records],
  )
  const prefillStates = useMemo(
    () => [...new Set(data.records.map((record) => record.prefillStatus).filter(Boolean))].sort(),
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
      const matchesCartabia = !cartabia || record.cartabiaState === cartabia
      const matchesPrefill = !prefill || record.prefillStatus === prefill
      return matchesSearch && matchesCategory && matchesChannel && matchesCartabia && matchesPrefill
    })
  }, [cartabia, category, channel, data.records, prefill, query])
  const selectedRecord = data.records.find((record) => record.id === selectedId) || filteredRecords[0]

  const openRecord = (record: TemplateAttiRecord) => {
    setSelectedId(record.id)
    window.history.replaceState({}, '', `${window.location.pathname}?scheda=${encodeURIComponent(record.id)}`)
    window.requestAnimationFrame(() => document.querySelector('.iu-template-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  if (loading) {
    return <LoadingState title="Caricamento template atti" message="Recupero catalogo e informazioni reali." />
  }

  return (
    <Page
      title={catalogo ? 'Catalogo template atti' : 'Template atti'}
      subtitle="Catalogo operativo con scheda in pagina e avvio diretto della produzione atti."
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
            <h2>{catalogo ? 'Catalogo consultabile e pronto alla redazione' : 'Ingresso operativo ai template dello studio'}</h2>
            <p>
              La pagina mostra catalogo, categorie, materie, canali e variabili, apre la scheda senza uscire e porta
              il modello selezionato nella produzione atti.
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
        <StudioStampPreview data={data} />
        {!catalogo ? <Sections data={data} /> : null}
        {catalogo ? (
          <CatalogFilters
            query={query}
            category={category}
            channel={channel}
            cartabia={cartabia}
            prefill={prefill}
            categories={categories}
            channels={channels}
            cartabiaStates={cartabiaStates}
            prefillStates={prefillStates}
            onQuery={setQuery}
            onCategory={setCategory}
            onChannel={setChannel}
            onCartabia={setCartabia}
            onPrefill={setPrefill}
          />
        ) : null}
        <TemplateDetail record={selectedRecord} />
        <Panel
          title={catalogo ? 'Template del catalogo' : 'Template principali'}
          subtitle={catalogo ? 'Filtri applicati agli atti disponibili.' : 'Informazioni reali e collegamenti sicuri.'}
        >
          {filteredRecords.length ? (
            <div className="iu-template-grid">
              {filteredRecords.map((record) => (
                <TemplateCard record={record} onOpen={openRecord} key={record.id} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Nessun template disponibile"
              message="La schermata resta neutra finche' non sono disponibili template consultabili."
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
