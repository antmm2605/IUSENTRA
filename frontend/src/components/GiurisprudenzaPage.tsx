import { useEffect, useMemo, useState } from 'react'
import { Bot, CheckCircle2, Database, ExternalLink, FileText, Filter, Landmark, Search, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract, openDesignLegalKnowledgeSurface } from '../ui/openDesign'
import {
  emptyGiurisprudenzaPage,
  getGiurisprudenzaPage,
  type GiurisprudenzaPageData,
  type GiurisprudenzaRecord,
  type GiurisprudenzaSource,
  type LegalMetric,
  type LegalSection,
} from '../giurisprudenzaData'
import './GiurisprudenzaPage.css'

function ContractStrip({ data }: { data: GiurisprudenzaPageData }) {
  const citations = data.sections
    .find((section) => section.id === 'citazioni_verificate')
    ?.items.find((item) => item.id === 'provvedimenti_citabili')
  return (
    <aside className="iu-legal-contract iu-od-evidence-panel">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {citations ? `${citations.value || 0} schede citabili con presidio fonte attivo` : 'Archivio sentenze collegato al lavoro dello studio'}
        </span>
      </div>
    </aside>
  )
}

function WarningList({ data }: { data: GiurisprudenzaPageData }) {
  if (!data.warnings.length) return null
  return (
    <section className="iu-legal-warnings" aria-label="Avvisi archivio giurisprudenza">
      {data.warnings.map((warning) => (
        <p className="iu-legal-warning iu-od-inference-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </section>
  )
}

function Metrics({ metrics }: { metrics: LegalMetric[] }) {
  if (!metrics.length) return null
  return (
    <section className="iu-legal-metrics" aria-label="Indicatori archivio giurisprudenza">
      {metrics.map((metric) => (
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

function sectionById(data: GiurisprudenzaPageData, id: string) {
  return data.sections.find((section) => section.id === id)
}

function sectionIcon(section: LegalSection) {
  if (section.id === 'citazioni_verificate') return <CheckCircle2 size={18} aria-hidden="true" />
  if (section.id === 'lex_presidio') return <Bot size={18} aria-hidden="true" />
  if (section.id === 'archivi_ufficiali') return <Database size={18} aria-hidden="true" />
  return <ShieldCheck size={18} aria-hidden="true" />
}

function KnowledgeStatusCard({ section }: { section: LegalSection }) {
  return (
    <article className="iu-legal-knowledge-card iu-od-source-card">
      <header className="iu-legal-knowledge-card__header">
        <span className="iu-legal-knowledge-card__icon">{sectionIcon(section)}</span>
        <div>
          <span className="iu-od-source-badge">{section.kind}</span>
          <h3>{section.title}</h3>
        </div>
      </header>
      {section.items.length ? (
        <div className="iu-legal-knowledge-items">
          {section.items.slice(0, 6).map((item) => (
            <span className="iu-legal-knowledge-item" data-tone={item.tone} key={`${section.id}-${item.id}`}>
              <strong>{item.label}</strong>
              <span>{item.value === '' ? 'Disponibile' : item.value}</span>
              {item.note ? <small>{item.note}</small> : null}
            </span>
          ))}
        </div>
      ) : (
        <EmptyState title={section.emptyMessage} />
      )}
    </article>
  )
}

function KnowledgeStatusPanel({ data }: { data: GiurisprudenzaPageData }) {
  const sections = ['citazioni_verificate', 'lex_presidio', 'archivi_ufficiali', 'ai_avanzata']
    .map((id) => sectionById(data, id))
    .filter(Boolean) as LegalSection[]
  if (!sections.length) return null
  return (
    <section className="iu-legal-knowledge-panel" aria-label="Presidio fonti giurisprudenza">
      <header className="iu-legal-section-head">
        <ShieldCheck size={18} aria-hidden="true" />
        <div>
          <h2>Citazioni e fonti verificate</h2>
          <p>Cassazione, fonti ufficiali, allegati e agenti Lex sono visibili prima di usare una massima in atto.</p>
        </div>
      </header>
      <div className="iu-legal-knowledge-grid">
        {sections.map((section) => <KnowledgeStatusCard section={section} key={section.id} />)}
      </div>
    </section>
  )
}

function SourceCard({ source }: { source: GiurisprudenzaSource }) {
  return (
    <article className="iu-legal-source iu-od-source-card">
      <header className="iu-legal-source__header">
        <div>
          <span className="iu-od-source-badge">{source.kind || 'Fonte'}</span>
          <h3>{source.label}</h3>
        </div>
        <Badge tone={source.stateTone}>{source.stateLabel || 'Censita'}</Badge>
      </header>
      <dl className="iu-legal-meta">
        {source.coverage ? (
          <div>
            <dt>Copertura</dt>
            <dd>{source.coverage}</dd>
          </div>
        ) : null}
        {source.accessMode ? (
          <div>
            <dt>Accesso</dt>
            <dd>{source.accessMode}</dd>
          </div>
        ) : null}
        <div>
          <dt>Provvedimenti</dt>
          <dd>{source.count}</dd>
        </div>
      </dl>
      {source.resolutionNote ? (
        <p className="iu-legal-source__resolution">{source.resolutionNote}</p>
      ) : null}
      <footer className="iu-od-action-row iu-legal-source__actions">
        {source.sourceHref ? (
          <ButtonLink href={source.sourceHref} tone="neutral" target="_blank" rel="noreferrer">
            <ExternalLink size={16} aria-hidden="true" />
            Apri fonte
          </ButtonLink>
        ) : null}
        {source.legacyHref ? (
          <ButtonLink href={source.legacyHref} tone="neutral">
            Scheda fonte
          </ButtonLink>
        ) : null}
      </footer>
    </article>
  )
}

function SourcesPanel({ data }: { data: GiurisprudenzaPageData }) {
  if (!data.sources.length) return null
  return (
    <Panel title="Fonti disponibili" subtitle="Banca dati interna, fonti ufficiali e fonti redazionali gia censite.">
      <div className="iu-legal-source-grid">
        {data.sources.map((source) => (
          <SourceCard source={source} key={source.id} />
        ))}
      </div>
    </Panel>
  )
}

function Filters({
  query,
  area,
  grade,
  areas,
  grades,
  onQuery,
  onArea,
  onGrade,
}: {
  query: string
  area: string
  grade: string
  areas: string[]
  grades: string[]
  onQuery: (value: string) => void
  onArea: (value: string) => void
  onGrade: (value: string) => void
}) {
  return (
    <section className="iu-legal-filters iu-od-source-card" aria-label="Filtri archivio giurisprudenza">
      <div className="iu-legal-filter">
        <label htmlFor="giurisprudenza-search">
          <Search size={15} aria-hidden="true" />
          Cerca
        </label>
        <input id="giurisprudenza-search" value={query} onChange={(event) => onQuery(event.target.value)} />
      </div>
      <div className="iu-legal-filter">
        <label htmlFor="giurisprudenza-area">
          <Filter size={15} aria-hidden="true" />
          Area
        </label>
        <select id="giurisprudenza-area" value={area} onChange={(event) => onArea(event.target.value)}>
          <option value="">Tutte</option>
          {areas.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="iu-legal-filter">
        <label htmlFor="giurisprudenza-grade">
          <Landmark size={15} aria-hidden="true" />
          Grado
        </label>
        <select id="giurisprudenza-grade" value={grade} onChange={(event) => onGrade(event.target.value)}>
          <option value="">Tutti</option>
          {grades.map((item) => (
            <option value={item} key={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
    </section>
  )
}

function RecordCard({ record, onOpen }: { record: GiurisprudenzaRecord; onOpen: (record: GiurisprudenzaRecord) => void }) {
  const metaItems = [
    ['Fonte', record.sourceLabel],
    ['Autorita', record.authority || record.office],
    ['Data', record.date],
    ['Area', record.area],
    ['Branca', record.branch || record.subbranch],
    ['Grado', record.grade || record.jurisdiction],
    ['Numero', record.caseNumber || record.ecli],
  ].filter((item) => item[1])

  return (
    <article className="iu-legal-record iu-od-source-card">
      <header className="iu-legal-record__header">
        <div>
          <span className="iu-od-source-badge">{record.sourceKind || 'Fonte'}</span>
          <h3>{record.title}</h3>
          {record.subtitle ? <p>{record.subtitle}</p> : null}
        </div>
        {record.verificationLabel ? <Badge tone={record.verificationTone}>{record.verificationLabel}</Badge> : null}
      </header>
      <dl className="iu-legal-meta">
        {metaItems.map(([label, value]) => (
          <div key={`${record.id}-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-legal-evidence-row">
        <span className="iu-od-source-badge">{record.evidenceType || 'metadato'}</span>
        {record.orientation ? (
          <span className="iu-od-source-badge">
            {record.orientationKind ? 'Analisi' : 'Orientamento'}: {record.orientation}
          </span>
        ) : null}
        {record.citationLabel ? <span className="iu-od-source-badge">{record.citationLabel}</span> : null}
      </div>
      {record.tags.length ? (
        <div className="iu-legal-tags" aria-label="Tag giurisprudenza">
          {record.tags.map((tag) => (
            <span className="iu-legal-tag" key={`${record.id}-${tag}`}>{tag}</span>
          ))}
        </div>
      ) : null}
      {record.practiceLinks.length ? (
        <div className="iu-legal-links">
          <strong>Fascicoli collegati</strong>
          <div className="iu-od-action-row">
            {record.practiceLinks.map((link) => (
              <ButtonLink href={link.href || '/fascicoli'} tone="neutral" key={`${record.id}-${link.id}`}>
                {link.label}
              </ButtonLink>
            ))}
          </div>
        </div>
      ) : null}
      <footer className="iu-od-action-row iu-legal-record__actions">
        <Button type="button" tone="primary" onClick={() => onOpen(record)}>
          <FileText size={16} aria-hidden="true" />
          Apri scheda
        </Button>
      </footer>
    </article>
  )
}

function RecordDetail({ record }: { record?: GiurisprudenzaRecord }) {
  if (!record) return null
  return (
    <section className="iu-legal-detail iu-od-source-card" aria-label="Scheda provvedimento">
      <div>
        <span className="iu-od-source-badge">{record.sourceKind || 'Fonte'}</span>
        <h2>{record.title}</h2>
        <p>{record.subtitle || record.orientation || 'Scheda del provvedimento selezionato.'}</p>
      </div>
      <dl className="iu-legal-meta">
        <div><dt>Autorità</dt><dd>{record.authority || record.office || 'Non indicata'}</dd></div>
        <div><dt>Data</dt><dd>{record.date || 'Non indicata'}</dd></div>
        <div><dt>Area</dt><dd>{record.area || 'Non indicata'}</dd></div>
        <div><dt>Numero</dt><dd>{record.caseNumber || record.ecli || 'Non indicato'}</dd></div>
      </dl>
      {record.tags.length ? (
        <div className="iu-legal-tags">
          {record.tags.map((tag) => <span className="iu-legal-tag" key={`${record.id}-detail-${tag}`}>{tag}</span>)}
        </div>
      ) : null}
    </section>
  )
}

function includesText(value: string, query: string) {
  if (!query.trim()) return true
  return value.toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))
}

export function GiurisprudenzaPage() {
  const [data, setData] = useState<GiurisprudenzaPageData>(emptyGiurisprudenzaPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [area, setArea] = useState('')
  const [grade, setGrade] = useState('')
  const [selectedId, setSelectedId] = useState(new URLSearchParams(window.location.search).get('scheda') || '')

  useEffect(() => {
    let active = true
    getGiurisprudenzaPage()
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const areas = useMemo(() => [...new Set(data.records.map((record) => record.area).filter(Boolean))].sort(), [data.records])
  const grades = useMemo(() => [...new Set(data.records.map((record) => record.grade).filter(Boolean))].sort(), [data.records])
  const visibleRecords = useMemo(() => data.records.filter((record) => {
    const searchable = [
      record.title,
      record.subtitle,
      record.sourceLabel,
      record.authority,
      record.office,
      record.area,
      record.branch,
      record.subbranch,
      record.grade,
      record.orientation,
      record.tags.join(' '),
    ].join(' ')
    return includesText(searchable, query) && (!area || record.area === area) && (!grade || record.grade === grade)
  }), [area, data.records, grade, query])
  const selectedRecord = data.records.find((record) => record.id === selectedId) || visibleRecords[0]
  const openRecord = (record: GiurisprudenzaRecord) => {
    setSelectedId(record.id)
    window.history.replaceState({}, '', `${window.location.pathname}?scheda=${encodeURIComponent(record.id)}`)
    window.requestAnimationFrame(() => document.querySelector('.iu-legal-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  if (loading) {
    return <LoadingState title="Caricamento archivio giurisprudenza" message="Recupero delle informazioni reali." />
  }

  return (
    <Page
      title="Archivio Giurisprudenza"
      subtitle="Banca dati interna di sentenze e provvedimenti in una pagina unica di ricerca e lettura."
      actions={<ButtonLink href="/ricerca-legale" tone="primary">Ricerca legale</ButtonLink>}
    >
      <div className="iu-legal-page">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics metrics={data.metrics} />
        <KnowledgeStatusPanel data={data} />
        <SourcesPanel data={data} />
        <RecordDetail record={selectedRecord} />
        <Filters
          query={query}
          area={area}
          grade={grade}
          areas={areas}
          grades={grades}
          onQuery={setQuery}
          onArea={setArea}
          onGrade={setGrade}
        />
        <Panel
          title="Sentenze e provvedimenti"
          subtitle={`${visibleRecords.length} elementi visibili su ${data.records.length} schede disponibili.`}
          actions={
            query || area || grade ? (
              <Button type="button" tone="neutral" onClick={() => {
                setQuery('')
                setArea('')
                setGrade('')
              }}>
                Azzera filtri
              </Button>
            ) : null
          }
        >
          {visibleRecords.length ? (
            <div className={openDesignLegalKnowledgeSurface.legalList}>
              {visibleRecords.map((record) => (
                <RecordCard record={record} onOpen={openRecord} key={record.id} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Nessun provvedimento da mostrare"
              message="L'archivio non contiene schede compatibili con i filtri applicati."
              action={<ButtonLink href="/ricerca-legale" tone="neutral">Apri ricerca legale</ButtonLink>}
            />
          )}
        </Panel>
      </div>
    </Page>
  )
}
