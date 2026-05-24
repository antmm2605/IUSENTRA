import { useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Bot,
  CheckCircle2,
  Database,
  ExternalLink,
  FileText,
  Filter,
  Landmark,
  Link2,
  Save,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract, openDesignLegalKnowledgeSurface } from '../ui/openDesign'
import {
  createGiurisprudenzaRecord,
  emptyGiurisprudenzaPage,
  getGiurisprudenzaCreatePage,
  getGiurisprudenzaPage,
  type GiurisprudenzaCreateDefaults,
  type GiurisprudenzaCreateOption,
  type GiurisprudenzaCreatePageData,
  type GiurisprudenzaCreateResponse,
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
          href={giurisprudenzaMetricHref(metric)}
          area="ricerca"
          actionLabel="Apri"
        />
      ))}
    </section>
  )
}

function giurisprudenzaMetricHref(metric: LegalMetric) {
  const label = metric.label.toLocaleLowerCase('it-IT')
  if (label.includes('provvedimenti')) return '#sentenze'
  if (label.includes('fonti')) return '#fonti-disponibili'
  if (label.includes('aree')) return '#filtri-giurisprudenza'
  if (label.includes('verificare')) return '?status=Da%20verificare#sentenze'
  if (label.includes('agenti')) return '#presidio-lex'
  if (label.includes('fascicoli')) return '/fascicoli'
  return '#sentenze'
}

function sectionById(data: GiurisprudenzaPageData, id: string) {
  return data.sections.find((section) => section.id === id)
}

function sectionIcon(section: LegalSection) {
  if (section.id === 'citazioni_verificate') return <CheckCircle2 size={18} aria-hidden="true" />
  if (section.id === 'presidio_dati') return <Database size={18} aria-hidden="true" />
  if (section.id === 'lex_presidio') return <Bot size={18} aria-hidden="true" />
  if (section.id === 'archivi_ufficiali') return <Database size={18} aria-hidden="true" />
  return <ShieldCheck size={18} aria-hidden="true" />
}

function formatDate(value: string) {
  const raw = value.trim()
  if (!raw) return ''
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) return raw
  const isoDay = raw.match(/^(\d{4})-(\d{2})-(\d{2})/)
  const parsed = isoDay ? new Date(`${isoDay[1]}-${isoDay[2]}-${isoDay[3]}T12:00:00`) : new Date(raw)
  if (Number.isNaN(parsed.getTime())) return raw
  return new Intl.DateTimeFormat('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(parsed)
}

function recordSearchText(record: GiurisprudenzaRecord) {
  return [
    record.title,
    record.subtitle,
    record.summary,
    record.principle,
    record.abstract,
    record.practicalUse,
    record.reliabilityNote,
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
  const sections = ['citazioni_verificate', 'presidio_dati', 'lex_presidio', 'archivi_ufficiali', 'ai_avanzata']
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
  source,
  verification,
  areas,
  grades,
  sources,
  verifications,
  onQuery,
  onArea,
  onGrade,
  onSource,
  onVerification,
  onReset,
}: {
  query: string
  area: string
  grade: string
  source: string
  verification: string
  areas: string[]
  grades: string[]
  sources: string[]
  verifications: string[]
  onQuery: (value: string) => void
  onArea: (value: string) => void
  onGrade: (value: string) => void
  onSource: (value: string) => void
  onVerification: (value: string) => void
  onReset: () => void
}) {
  const hasFilters = Boolean(query || area || grade || source || verification)
  return (
    <section className="iu-legal-filters iu-od-source-card" aria-label="Filtri archivio giurisprudenza">
      <header className="iu-legal-filters__header">
        <div>
          <h2>Ricerca e lettura</h2>
          <p>Filtra l'archivio e seleziona una scheda per leggere fonte, massima e uso professionale.</p>
        </div>
        {hasFilters ? <Button type="button" tone="neutral" onClick={onReset}>Azzera filtri</Button> : null}
      </header>
      <div className="iu-legal-filter-grid">
        <div className="iu-legal-filter iu-legal-filter--search">
          <label htmlFor="giurisprudenza-search">
            <Search size={15} aria-hidden="true" />
            Cerca
          </label>
          <input
            id="giurisprudenza-search"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Parole chiave, numero, fonte, materia"
          />
        </div>
        <div className="iu-legal-filter">
          <label htmlFor="giurisprudenza-source">
            <BookOpen size={15} aria-hidden="true" />
            Fonte
          </label>
          <select id="giurisprudenza-source" value={source} onChange={(event) => onSource(event.target.value)}>
            <option value="">Tutte</option>
            {sources.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
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
        <div className="iu-legal-filter">
          <label htmlFor="giurisprudenza-verification">
            <ShieldCheck size={15} aria-hidden="true" />
            Verifica
          </label>
          <select id="giurisprudenza-verification" value={verification} onChange={(event) => onVerification(event.target.value)}>
            <option value="">Tutte</option>
            {verifications.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  )
}

function RecordCard({ record, onOpen }: { record: GiurisprudenzaRecord; onOpen: (record: GiurisprudenzaRecord) => void }) {
  const metaItems = [
    ['Fonte', record.sourceLabel],
    ['Autorit\u00e0', record.authority || record.office],
    ['Data', formatDate(record.date)],
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
          {record.summary || record.subtitle ? <p>{record.summary || record.subtitle}</p> : null}
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
        {record.fullTextAvailable ? <span className="iu-od-source-badge">Testo in archivio</span> : null}
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
          Leggi scheda
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

function RecordDetail({ record }: { record?: GiurisprudenzaRecord }) {
  if (!record) {
    return (
      <aside className="iu-legal-detail iu-od-source-card" aria-label="Scheda provvedimento">
        <EmptyState
          title="Nessuna scheda selezionata"
          message="Cerca o filtra l'archivio per leggere fonte, massima, verifica e uso professionale."
        />
      </aside>
    )
  }
  return (
    <aside className="iu-legal-detail iu-od-source-card" aria-label="Scheda provvedimento">
      <div className="iu-legal-detail__intro">
        <span className="iu-od-source-badge">{record.sourceKind || 'Fonte'}</span>
        <h2>{record.title}</h2>
        <p>{record.summary || record.subtitle || record.orientation || 'Scheda del provvedimento selezionato.'}</p>
      </div>
      <dl className="iu-legal-meta">
        <div><dt>{'Autorit\u00e0'}</dt><dd>{record.authority || record.office || 'Non indicata'}</dd></div>
        <div><dt>Data</dt><dd>{formatDate(record.date) || 'Non indicata'}</dd></div>
        <div><dt>Area</dt><dd>{record.area || 'Non indicata'}</dd></div>
        <div><dt>Numero</dt><dd>{record.caseNumber || record.ecli || 'Non indicato'}</dd></div>
      </dl>
      <div className="iu-legal-detail__grid">
        <section className="iu-legal-detail__box">
          <h3>Uso nel lavoro</h3>
          <p>{record.practicalUse || 'Valuta pertinenza, fonte e data prima di usare il riferimento.'}</p>
        </section>
        <section className="iu-legal-detail__box">
          <h3>Controllo fonte</h3>
          <p>{record.reliabilityNote || "Verifica la fonte originale prima dell'uso professionale."}</p>
        </section>
      </div>
      {record.principle ? (
        <section className="iu-legal-detail__box">
          <h3>Principio</h3>
          <p>{record.principle}</p>
        </section>
      ) : null}
      {record.abstract && record.abstract !== record.summary ? (
        <section className="iu-legal-detail__box">
          <h3>Estratto</h3>
          <p>{record.abstract}</p>
        </section>
      ) : null}
      {record.tags.length ? (
        <div className="iu-legal-tags">
          {record.tags.map((tag) => <span className="iu-legal-tag" key={`${record.id}-detail-${tag}`}>{tag}</span>)}
        </div>
      ) : null}
      <div className="iu-od-action-row iu-legal-detail__actions">
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="primary" target="_blank" rel="noreferrer">
            <ExternalLink size={16} aria-hidden="true" />
            Apri fonte originale
          </ButtonLink>
        ) : null}
        <ButtonLink href={`/ricerca-legale?q=${encodeURIComponent([record.title, record.caseNumber, record.area].filter(Boolean).join(' '))}`} tone="neutral">
          <Search size={16} aria-hidden="true" />
          Cerca collegati
        </ButtonLink>
        {record.practiceLinks.length ? (
          <ButtonLink href={record.practiceLinks[0].href || '/fascicoli'} tone="neutral">
            <Link2 size={16} aria-hidden="true" />
            Fascicolo collegato
          </ButtonLink>
        ) : null}
      </div>
    </aside>
  )
}

type CreateFieldName = keyof GiurisprudenzaCreateDefaults

function CreateTextField({
  id,
  label,
  value,
  onChange,
  type = 'text',
  required = false,
  error = '',
  placeholder = '',
}: {
  id: CreateFieldName
  label: string
  value: string
  onChange: (field: CreateFieldName, value: string) => void
  type?: string
  required?: boolean
  error?: string
  placeholder?: string
}) {
  const inputId = `giurisprudenza-create-${id}`
  return (
    <div className="iu-legal-create-field">
      <label htmlFor={inputId}>{label}</label>
      <input
        id={inputId}
        value={value}
        type={type}
        required={required}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : undefined}
        onChange={(event) => onChange(id, event.target.value)}
      />
      {error ? <small id={`${inputId}-error`}>{error}</small> : null}
    </div>
  )
}

function CreateSelectField({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: CreateFieldName
  label: string
  value: string
  options: GiurisprudenzaCreateOption[]
  onChange: (field: CreateFieldName, value: string) => void
}) {
  const inputId = `giurisprudenza-create-${id}`
  return (
    <div className="iu-legal-create-field">
      <label htmlFor={inputId}>{label}</label>
      <select id={inputId} value={value} onChange={(event) => onChange(id, event.target.value)}>
        <option value="">Seleziona</option>
        {options.map((option) => (
          <option value={option.value} key={`${id}-${option.value}`}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function CreateTextAreaField({
  id,
  label,
  value,
  onChange,
  rows = 4,
  required = false,
  error = '',
  placeholder = '',
}: {
  id: CreateFieldName
  label: string
  value: string
  onChange: (field: CreateFieldName, value: string) => void
  rows?: number
  required?: boolean
  error?: string
  placeholder?: string
}) {
  const inputId = `giurisprudenza-create-${id}`
  return (
    <div className="iu-legal-create-field iu-legal-create-field--wide">
      <label htmlFor={inputId}>{label}</label>
      <textarea
        id={inputId}
        value={value}
        rows={rows}
        required={required}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${inputId}-error` : undefined}
        onChange={(event) => onChange(id, event.target.value)}
      />
      {error ? <small id={`${inputId}-error`}>{error}</small> : null}
    </div>
  )
}

function CreateStatusPanel({ result }: { result: GiurisprudenzaCreateResponse | null }) {
  if (!result) return null
  if (result.ok) {
    return (
      <aside className="iu-legal-create-status iu-legal-create-status--success" aria-live="polite">
        <CheckCircle2 size={18} aria-hidden="true" />
        <div>
          <strong>{result.message}</strong>
          <span>La scheda è disponibile nell'archivio e può essere collegata al lavoro dello studio.</span>
          {result.redirectHref ? (
            <ButtonLink href={result.redirectHref} tone="neutral">
              Leggi scheda salvata
            </ButtonLink>
          ) : null}
        </div>
      </aside>
    )
  }
  return (
    <aside className="iu-legal-create-status iu-legal-create-status--warning" aria-live="polite">
      <AlertTriangle size={18} aria-hidden="true" />
      <div>
        <strong>{result.message}</strong>
        {Object.values(result.errors).length ? <span>{Object.values(result.errors).join(' ')}</span> : null}
      </div>
    </aside>
  )
}

function GiurisprudenzaCreatePage() {
  const [page, setPage] = useState<GiurisprudenzaCreatePageData | null>(null)
  const [form, setForm] = useState<GiurisprudenzaCreateDefaults | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<GiurisprudenzaCreateResponse | null>(null)

  useEffect(() => {
    let active = true
    getGiurisprudenzaCreatePage()
      .then((payload) => {
        if (!active) return
        setPage(payload)
        setForm(payload.defaults)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const updateField = (field: CreateFieldName, value: string) => {
    setResult(null)
    setForm((current) => current ? { ...current, [field]: value } : current)
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!form || saving) return
    setSaving(true)
    try {
      const response = await createGiurisprudenzaRecord(form)
      setResult(response)
      if (response.ok && response.record) {
        setForm((current) => current ? { ...current, titolo: '', massima: '', principio_diritto: '', abstract: '', text_original: '' } : current)
      }
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <LoadingState title="Caricamento nuova scheda" message="Preparo campi, fonti e classificazioni dello studio." />
  }

  if (!page || !form) {
    return (
      <Page title="Nuova scheda giurisprudenza" subtitle="Inserimento governato delle informazioni giurisprudenziali dello studio.">
        <EmptyState
          title="Inserimento non disponibile"
          message="La pagina non ha ricevuto i campi necessari per registrare una scheda."
          action={<ButtonLink href="/giurisprudenza" tone="neutral">Torna all'archivio</ButtonLink>}
        />
      </Page>
    )
  }

  const errors = result?.ok === false ? result.errors : {}
  const options = page.options

  return (
    <Page
      title="Nuova scheda giurisprudenza"
      subtitle="Registra una decisione, una massima o un precedente interno con fonte, classificazione e controllo d'uso."
      actions={(
        <ButtonLink href="/giurisprudenza" tone="neutral">
          <ArrowLeft size={16} aria-hidden="true" />
          Archivio
        </ButtonLink>
      )}
    >
      <div className="iu-legal-page iu-legal-create-page">
        <ContractStrip data={{ ...emptyGiurisprudenzaPage, sources: page.sources, warnings: page.warnings }} />
        <WarningList data={{ ...emptyGiurisprudenzaPage, warnings: page.warnings }} />
        <CreateStatusPanel result={result} />
        <form className="iu-legal-create-form iu-od-source-card" onSubmit={submit}>
          <section className="iu-legal-create-section">
            <header className="iu-legal-section-head">
              <BookOpen size={18} aria-hidden="true" />
              <div>
                <h2>Identificazione</h2>
                <p>Dati essenziali per ritrovare e citare correttamente la scheda.</p>
              </div>
            </header>
            <div className="iu-legal-create-grid">
              <CreateTextField id="titolo" label="Titolo" value={form.titolo} onChange={updateField} required error={errors.titolo} />
              <CreateSelectField id="source_system" label="Fonte" value={form.source_system} options={options.fonti || []} onChange={updateField} />
              <CreateTextField id="organo_giudicante" label="Autorità" value={form.organo_giudicante || form.ufficio} onChange={updateField} placeholder="Corte, TAR, Tribunale" />
              <CreateTextField id="numero_provvedimento" label="Numero" value={form.numero_provvedimento} onChange={updateField} placeholder="1234/2026" />
              <CreateTextField id="data_decisione" label="Data decisione" value={form.data_decisione} type="date" onChange={updateField} />
              <CreateTextField id="data_deposito" label="Data deposito" value={form.data_deposito} type="date" onChange={updateField} />
            </div>
          </section>

          <section className="iu-legal-create-section">
            <header className="iu-legal-section-head">
              <Filter size={18} aria-hidden="true" />
              <div>
                <h2>Classificazione</h2>
                <p>Area, branca e uso pratico aiutano ricerca, Lex e collegamento ai fascicoli.</p>
              </div>
            </header>
            <div className="iu-legal-create-grid">
              <CreateSelectField id="area" label="Area" value={form.area} options={options.aree || []} onChange={updateField} />
              <CreateSelectField id="branca" label="Branca" value={form.branca} options={options.branche || []} onChange={updateField} />
              <CreateSelectField id="sottobranca" label="Sottobranca" value={form.sottobranca} options={options.sottobranche || []} onChange={updateField} />
              <CreateSelectField id="grado" label="Grado" value={form.grado} options={options.gradi || []} onChange={updateField} />
              <CreateSelectField id="tipo_provvedimento" label="Tipo" value={form.tipo_provvedimento} options={options.tipi_provvedimento || []} onChange={updateField} />
              <CreateSelectField id="orientamento" label="Orientamento" value={form.orientamento} options={options.orientamenti || []} onChange={updateField} />
              <CreateTextField id="microtema" label="Microtema" value={form.microtema} onChange={updateField} />
              <CreateTextField id="materia" label="Materia" value={form.materia} onChange={updateField} />
            </div>
          </section>

          <section className="iu-legal-create-section">
            <header className="iu-legal-section-head">
              <FileText size={18} aria-hidden="true" />
              <div>
                <h2>Contenuto</h2>
                <p>Inserisci il nucleo utile alla ricerca e alla valutazione professionale.</p>
              </div>
            </header>
            <div className="iu-legal-create-grid">
              <CreateTextAreaField id="massima" label="Massima" value={form.massima} onChange={updateField} required error={errors.contenuto} rows={5} />
              <CreateTextAreaField id="principio_diritto" label="Principio di diritto" value={form.principio_diritto} onChange={updateField} rows={4} />
              <CreateTextAreaField id="abstract" label="Sintesi" value={form.abstract} onChange={updateField} rows={4} />
              <CreateTextAreaField id="text_original" label="Testo disponibile" value={form.text_original} onChange={updateField} rows={6} />
              <CreateTextField id="norme_citate" label="Norme citate" value={form.norme_citate} onChange={updateField} placeholder="Articoli separati da virgola" />
              <CreateTextField id="parole_chiave" label="Parole chiave" value={form.parole_chiave} onChange={updateField} placeholder="Termini separati da virgola" />
            </div>
          </section>

          <section className="iu-legal-create-section">
            <header className="iu-legal-section-head">
              <ExternalLink size={18} aria-hidden="true" />
              <div>
                <h2>Fonte e uso</h2>
                <p>Collega il riferimento originale e indica come usarlo nel lavoro dello studio.</p>
              </div>
            </header>
            <div className="iu-legal-create-grid">
              <CreateTextField id="url_pagina_ufficiale" label="Pagina fonte" value={form.url_pagina_ufficiale} type="url" onChange={updateField} />
              <CreateTextField id="url_pdf_ufficiale" label="PDF fonte" value={form.url_pdf_ufficiale} type="url" onChange={updateField} />
              <CreateTextField id="ecli" label="ECLI" value={form.ecli} onChange={updateField} />
              <CreateSelectField id="uso_nel_software" label="Uso" value={form.uso_nel_software} options={options.usi || []} onChange={updateField} />
              <CreateTextAreaField id="note_redazionali" label="Note interne" value={form.note_redazionali} onChange={updateField} rows={3} />
            </div>
          </section>

          <footer className="iu-legal-create-actions">
            <ButtonLink href="/giurisprudenza" tone="neutral">Annulla</ButtonLink>
            <Button type="submit" tone="primary" disabled={saving}>
              <Save size={16} aria-hidden="true" />
              {saving ? 'Salvataggio' : 'Salva scheda'}
            </Button>
          </footer>
        </form>
      </div>
    </Page>
  )
}

function includesText(value: string, query: string) {
  if (!query.trim()) return true
  return value.toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))
}

function GiurisprudenzaArchivePage() {
  const initialParams = new URLSearchParams(window.location.search)
  const [data, setData] = useState<GiurisprudenzaPageData>(emptyGiurisprudenzaPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState(initialParams.get('q') || '')
  const [area, setArea] = useState(initialParams.get('area') || '')
  const [grade, setGrade] = useState(initialParams.get('grado') || '')
  const [source, setSource] = useState(initialParams.get('fonte') || '')
  const [verification, setVerification] = useState(initialParams.get('status') || '')
  const [selectedId, setSelectedId] = useState(initialParams.get('scheda') || '')

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
  const sources = useMemo(() => [...new Set(data.records.map((record) => record.sourceLabel).filter(Boolean))].sort(), [data.records])
  const verifications = useMemo(
    () => [...new Set(data.records.map((record) => record.verificationLabel || record.citationLabel).filter(Boolean))].sort(),
    [data.records],
  )
  const visibleRecords = useMemo(() => data.records.filter((record) => {
    const verificationValue = record.verificationLabel || record.citationLabel
    return includesText(recordSearchText(record), query)
      && (!area || record.area === area)
      && (!grade || record.grade === grade)
      && (!source || record.sourceLabel === source)
      && (!verification || verificationValue === verification)
  }), [area, data.records, grade, query, source, verification])
  const selectedRecord = data.records.find((record) => record.id === selectedId) || visibleRecords[0]
  const resetFilters = () => {
    setQuery('')
    setArea('')
    setGrade('')
    setSource('')
    setVerification('')
    window.history.replaceState({}, '', window.location.pathname)
  }
  const openRecord = (record: GiurisprudenzaRecord) => {
    setSelectedId(record.id)
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (area) params.set('area', area)
    if (grade) params.set('grado', grade)
    if (source) params.set('fonte', source)
    if (verification) params.set('status', verification)
    params.set('scheda', record.id)
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`)
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
        <div id="filtri-giurisprudenza" />
        <Filters
          query={query}
          area={area}
          grade={grade}
          source={source}
          verification={verification}
          areas={areas}
          grades={grades}
          sources={sources}
          verifications={verifications}
          onQuery={setQuery}
          onArea={setArea}
          onGrade={setGrade}
          onSource={setSource}
          onVerification={setVerification}
          onReset={resetFilters}
        />
        <div id="sentenze" className="iu-legal-workbench">
          <div className="iu-legal-workbench__main">
        <Panel
          title="Sentenze e provvedimenti"
          subtitle={`${visibleRecords.length} elementi visibili su ${data.records.length} schede disponibili.`}
          actions={
            query || area || grade || source || verification ? (
              <Button type="button" tone="neutral" onClick={resetFilters}>
                Azzera filtri
              </Button>
            ) : null
          }
        >
          {visibleRecords.length ? (
            <div className={[openDesignLegalKnowledgeSurface.legalList, 'iu-legal-record-grid'].join(' ')}>
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
          <RecordDetail record={selectedRecord} />
        </div>
        <Metrics metrics={data.metrics} />
        <div id="presidio-lex">
          <KnowledgeStatusPanel data={data} />
        </div>
        <div id="fonti-disponibili">
          <SourcesPanel data={data} />
        </div>
      </div>
    </Page>
  )
}

export function GiurisprudenzaPage() {
  const routePath = window.location.pathname.replace(/\/+$/, '') || '/'
  return routePath === '/giurisprudenza/nuova' ? <GiurisprudenzaCreatePage /> : <GiurisprudenzaArchivePage />
}
