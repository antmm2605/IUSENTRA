import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, FileText, Filter, Landmark, Search, ShieldCheck } from 'lucide-react'
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
} from '../giurisprudenzaData'
import './GiurisprudenzaPage.css'

function ContractStrip({ data }: { data: GiurisprudenzaPageData }) {
  return (
    <aside className="iu-legal-contract iu-od-evidence-panel">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {data.source || 'Archivio'} - sorgente governata
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
    <section className="iu-legal-metrics" aria-label="KPI archivio giurisprudenza">
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

function RecordCard({ record }: { record: GiurisprudenzaRecord }) {
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
        <ButtonLink href={record.legacyHref} tone="primary">
          <FileText size={16} aria-hidden="true" />
          Apri scheda metadati
        </ButtonLink>
      </footer>
    </article>
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

  if (loading) {
    return <LoadingState title="Caricamento archivio giurisprudenza" message="Recupero dei metadati reali." />
  }

  return (
    <Page
      title="Archivio Giurisprudenza"
      subtitle="Banca dati interna di sentenze e provvedimenti, esposta in React solo come consultazione di metadati."
      actions={<ButtonLink href="/legal-intelligence" tone="primary">Legal Intelligence</ButtonLink>}
    >
      <div className="iu-legal-page">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics metrics={data.metrics} />
        <SourcesPanel data={data} />
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
          subtitle={`${visibleRecords.length} elementi visibili su ${data.records.length} metadati disponibili.`}
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
                <RecordCard record={record} key={record.id} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="Nessun provvedimento da mostrare"
              message="L'archivio non contiene metadati compatibili con i filtri applicati."
              action={<ButtonLink href="/legal-intelligence" tone="neutral">Apri Legal Intelligence</ButtonLink>}
            />
          )}
        </Panel>
      </div>
    </Page>
  )
}
