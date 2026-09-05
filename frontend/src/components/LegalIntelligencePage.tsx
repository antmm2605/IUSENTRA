import { Fragment, useEffect, useMemo, useState } from 'react'
import { mediazioneWebsite } from '../lib/mediazioneWebsite'
import { MediazioneOrganismoDetail } from './MediazioneOrganismoDetail'
import {
  AlertTriangle,
  ArrowRight,
  Archive,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock3,
  Download,
  ExternalLink,
  Files,
  FileSearch,
  Filter,
  Globe2,
  Landmark,
  ListChecks,
  Mail,
  MessageCircle,
  Maximize2,
  Minimize2,
  Newspaper,
  Search,
  SearchCheck,
} from 'lucide-react'
import { Badge, type BadgeTone } from '../ui/Badge'
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
  type LegalAutofetchSource,
  type LegalIntelligencePageData,
  type LegalIntelligenceRecord,
} from '../legalIntelligenceData'
import './LegalIntelligencePage.css'
import './MediazioneRegistryResponsive.css'
type LegalIntelligenceView = 'dashboard' | 'news' | 'mediazione' | 'ricerca-legale'
const INTERNAL_FULLSCREEN_BODY_CLASS = 'iusentra-ui-fullscreen-open'
const LEGAL_INTELLIGENCE_FULLSCREEN_CLASS = 'iu-li-fullscreen-mode'

function togglePageFullscreen(selector: string, className: string) {
  const target = document.querySelector<HTMLElement>(selector) || document.documentElement
  const nextActive = !target.classList.contains(className)
  target.classList.toggle(className, nextActive)
  document.body.classList.toggle(INTERNAL_FULLSCREEN_BODY_CLASS, nextActive)
  return nextActive
}

function clearPageFullscreen(className: string) {
  document.querySelector<HTMLElement>(`main.iu-content.${className}`)?.classList.remove(className)
  document.body.classList.remove(INTERNAL_FULLSCREEN_BODY_CLASS)
}
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
  if (view === 'news') return 'Aggiornamenti legali'
  if (view === 'mediazione') return 'Registro Mediazione'
  if (view === 'ricerca-legale') return 'Ricerca Legale'
  return 'Osservatorio Legale'
}
function pageSubtitle(view: LegalIntelligenceView) {
  if (view === 'news') return 'Aggiornamenti giuridici con fonte, contesto e uso operativo in studio.'
  if (view === 'mediazione') return 'Registri ministeriali e dati di mediazione letti dentro una scheda professionale.'
  if (view === 'ricerca-legale') return 'Ricerca su archivio giuridico, fonti ufficiali e schede contestualizzate.'
  return 'Archivio fonti, aggiornamenti e registri con contesto leggibile prima di aprire la fonte originale.'
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
  return parsed.toLocaleDateString('it-IT', { timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: 'numeric' })
}
function isOfficial(record: LegalIntelligenceRecord) {
  return [record.sourceKind, record.approvalLabel, record.evidenceType].join(' ').toLocaleLowerCase('it-IT').includes('ufficiale')
}
function normalizedContextText(value: string) {
  return value
    .replace(/^(contesto operativo|contenuto):\s*/i, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .toLocaleLowerCase('it-IT')
}
function sameContextText(left: string, right: string) {
  const a = normalizedContextText(left)
  const b = normalizedContextText(right)
  if (!a || !b) return false
  if (a === b) return true
  if (Math.min(a.length, b.length) < 80) return false
  return a.startsWith(b) || b.startsWith(a)
}
function cleanContextItems(items: string[]) {
  const cleaned: string[] = []
  items.forEach((item) => {
    const current = item.trim()
    if (!current) return
    if (cleaned.some((existing) => sameContextText(existing, current))) return
    cleaned.push(current)
  })
  return cleaned
}
function contextItems(record: LegalIntelligenceRecord) {
  if (record.sourceContext.length) return cleanContextItems(record.sourceContext)
  return cleanContextItems([
    record.contextSummary ? `Contesto operativo: ${record.contextSummary}` : '',
    record.sourceExcerpt ? `Contenuto: ${record.sourceExcerpt}` : '',
    record.area || record.branch ? `Ambito: ${[record.area, record.branch].filter(Boolean).join(' / ')}` : '',
    record.date ? `Aggiornamento: ${formatDate(record.date)}` : '',
    record.sourceLabel ? `Provenienza: ${record.sourceLabel}` : '',
  ].filter(Boolean))
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
function cleanVisibleLabel(value?: string) {
  return (value || '')
    .replace(/^db\s+/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\bnews\b/gi, 'aggiornamenti')
    .replace(/\s+/g, ' ')
    .trim()
}
function recordKindLabel(record: LegalIntelligenceRecord) {
  const kind = record.kind.toLocaleLowerCase('it-IT')
  if (kind.includes('mediazione')) return 'Mediazione'
  if (kind.includes('normativa')) return 'Normativa'
  if (kind.includes('giurisprudenza') || kind.includes('sentenza')) return 'Giurisprudenza'
  if (kind.includes('news') || kind.includes('notizia') || kind.includes('aggiornamento')) return 'Aggiornamento'
  return cleanVisibleLabel(record.kind) || 'Scheda'
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
  const items: Array<{ view: LegalIntelligenceView; label: string; href: string; icon: React.ReactNode }> = [
    { view: 'ricerca-legale', label: 'Ricerca', href: '/ricerca-legale', icon: <Search size={18} aria-hidden="true" /> },
    { view: 'news', label: 'Aggiornamenti', href: '/ricerca-legale/news', icon: <Newspaper size={18} aria-hidden="true" /> },
    { view: 'mediazione', label: 'Mediazione', href: '/ricerca-legale/mediazione', icon: <Landmark size={18} aria-hidden="true" /> },
  ]
  return (
    <nav className="iu-li-tabs" aria-label="Sezioni ricerca legale">
      {items.map((item) => (
        <a
          key={item.view}
          href={item.href}
          className={view === item.view ? 'iu-li-tab-card iu-li-tab-card--active' : 'iu-li-tab-card'}
          aria-current={view === item.view ? 'page' : undefined}
        >
          <span className="iu-li-tab-card__icon">{item.icon}</span>
          <strong>{item.label}</strong>
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
function sourceStatusTone(status: string): BadgeTone {
  const value = status.toLocaleLowerCase('it-IT').replace(/_/g, ' ')
  if (value === 'pronta' || value === 'pronto') return 'success'
  if (value === 'da verificare' || value === 'non pronta' || value === 'controllo sistema') return 'warning'
  if (value === 'failed' || value === 'timeout' || value === 'errore') return 'danger'
  if (value === 'non monitorata') return 'neutral'
  return 'info'
}
function readableStatus(status: string) {
  const value = status.replace(/_/g, ' ').trim()
  if (!value) return 'controllo sistema'
  return value.slice(0, 1).toLocaleUpperCase('it-IT') + value.slice(1)
}
function sourceProgress(source: LegalAutofetchSource) {
  const parts = [
    source.rawDocuments ? `${source.rawDocuments.toLocaleString('it-IT')} letti` : '',
    source.normalizedDocuments ? `${source.normalizedDocuments.toLocaleString('it-IT')} con testo` : '',
    source.reviewPublished ? `${source.reviewPublished.toLocaleString('it-IT')} pubblicati` : '',
    source.reviewPending ? `${source.reviewPending.toLocaleString('it-IT')} in revisione sistema` : '',
  ].filter(Boolean)
  return parts.length
    ? parts.join(' · ')
    : source.systemAction || source.reason || 'Fonte non coperta: completare acquisizione ufficiale prima della pubblicazione.'
}
function sourceLegalPreview(source: LegalAutofetchSource) {
  return [
    source.articlesAndCodes[0],
    source.decreesAndRules[0],
    source.caseLawAndHearings[0],
    source.legalMaterials[0],
  ].filter(Boolean).slice(0, 3)
}
function AcquisitionReadinessPanel({
  data,
  onArchiveSearch,
}: {
  data: LegalIntelligencePageData
  onArchiveSearch: (query: string, scope?: string, source?: string) => void
}) {
  const monitor = data.autofetchMonitor
  const hasMonitor = monitor.sourcesTotal > 0 || monitor.sources.length > 0
  if (!hasMonitor) return null
  const queueOpen = monitor.queue.queued + monitor.queue.running
  const failedJobs = monitor.queue.failed + monitor.queue.timeout
  const lawyerReadiness = monitor.lawyerReadiness
  const sourcePreview = [...monitor.sources]
    .sort((first, second) => {
      const order: Record<string, number> = { completamento_fonti_ufficiali: 0, da_verificare: 1, 'da verificare': 1, non_pronta: 2, pronta: 3, non_monitorata: 4 }
      return (order[first.status] ?? 4) - (order[second.status] ?? 4) || first.sourceName.localeCompare(second.sourceName, 'it-IT')
    })
    .slice(0, 12)
  const cards = [
    {
      id: 'ready',
      label: 'Fonti pronte',
      value: monitor.sourcesReady,
      note: 'Con documenti letti, testo o schede pubblicate.',
      icon: <CheckCircle2 size={18} aria-hidden="true" />,
      tone: 'success' as BadgeTone,
    },
    {
      id: 'blocked',
      label: 'Fonti da completare',
      value: monitor.sourcesNotReady,
      note: 'Manca acquisizione, testo, OCR o ultimo controllo automatico.',
      icon: <AlertTriangle size={18} aria-hidden="true" />,
      tone: monitor.sourcesNotReady ? 'warning' as BadgeTone : 'success' as BadgeTone,
    },
    {
      id: 'lex',
      label: 'Domande Lex',
      value: lawyerReadiness.lexTestableSources,
      note: 'Fonti con domanda di prova collegata al lavoro dell’avvocato.',
      icon: <MessageCircle size={18} aria-hidden="true" />,
      tone: lawyerReadiness.lexTestableSources ? 'success' as BadgeTone : 'warning' as BadgeTone,
    },
    {
      id: 'queue',
      label: 'Coda',
      value: queueOpen,
      note: 'Controlli in attesa o in corso.',
      icon: <Clock3 size={18} aria-hidden="true" />,
      tone: 'info' as BadgeTone,
    },
    {
      id: 'failed',
      label: 'Errori',
      value: failedJobs,
      note: 'Controlli falliti o scaduti da riprendere.',
      icon: <Files size={18} aria-hidden="true" />,
      tone: failedJobs ? 'danger' as BadgeTone : 'neutral' as BadgeTone,
    },
  ]
  return (
    <div className="iu-li-acquisition" aria-label="Stato reale acquisizione fonti">
      <div className="iu-li-acquisition__cards">
        {cards.map((card) => (
          <article className="iu-li-acquisition__card" key={card.id}>
            <span className="iu-li-acquisition__icon">{card.icon}</span>
            <div>
              <span>{card.label}</span>
              <strong>{card.value.toLocaleString('it-IT')}</strong>
              <small>{card.note}</small>
            </div>
            <Badge tone={card.tone}>Stato</Badge>
          </article>
        ))}
      </div>
      {sourcePreview.length ? (
        <div className="iu-li-acquisition__sources">
          <div className="iu-li-source-preview__head">
            <strong>Fonti sincronizzate e fonti da completare</strong>
            <ButtonLink href="/admin/aggiornamenti-legali/fonti" tone="neutral">Gestisci fonti</ButtonLink>
          </div>
          <div className="iu-li-acquisition__source-grid">
            {sourcePreview.map((source) => {
              const legalPreview = sourceLegalPreview(source)
              const testQuery = source.lexTestQuestion || source.sourceName
              return (
                <button
                  className="iu-li-acquisition__source"
                  key={source.sourceCode}
                  onClick={() => onArchiveSearch(testQuery, source.practicePhase, source.sourceName)}
                  type="button"
                >
                  <span className="iu-li-acquisition__source-title">
                    <strong>{source.sourceName}</strong>
                    <Badge tone={source.deliveryStatusLabel ? source.deliveryTone : sourceStatusTone(source.status)}>
                      {source.deliveryStatusLabel || readableStatus(source.status)}
                    </Badge>
                  </span>
                  {source.lawyerUse ? <small><b>Serve per:</b> {source.lawyerUse}</small> : null}
                  {source.practicePhase ? <small><b>Fase:</b> {source.practicePhase}</small> : null}
                  <small><b>Acquisizione:</b> {sourceProgress(source)}</small>
                  {source.systemAction || source.lawyerAction ? <small><b>Azione sistema:</b> {source.systemAction || source.lawyerAction}</small> : null}
                  {legalPreview.length ? (
                    <ul className="iu-li-acquisition__source-points" aria-label={`Materiali collegati a ${source.sourceName}`}>
                      {legalPreview.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  ) : null}
                  {source.lexTestQuestion ? <em>Domanda Lex: {source.lexTestQuestion}</em> : null}
                  {source.lastFinishedAt ? <em>Ultimo controllo {formatDate(source.lastFinishedAt)}</em> : null}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}
      {monitor.qualityQuestions.length ? (
        <div className="iu-li-acquisition__checks" aria-label="Domande qualità fonte">
          <strong>Domande obbligatorie</strong>
          <ul>
            {monitor.qualityQuestions.slice(0, 6).map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
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
      label: 'Aggiornamenti disponibili',
      value: formatMetricValue(news.value),
      note: 'Elenco consultabile con schede e fonte',
      href: '/ricerca-legale/news',
      action: 'Vedi aggiornamenti',
    } : null,
    review ? {
      id: 'review',
      label: 'Da controllare',
      value: formatMetricValue(review.value),
      note: "Documenti acquisiti da completare prima dell'uso",
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
          <h2>Fonti e acquisizioni</h2>
          <p>Stato reale delle fonti: documenti letti, testo disponibile, coda, errori e stati pronti, acquisizioni in corso e fonti da completare.</p>
        </div>
      </header>
      <AcquisitionReadinessPanel data={data} onArchiveSearch={onArchiveSearch} />
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
    ['Tipo fonte', cleanVisibleLabel(record.sourceKind)],
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
          <span className="iu-od-source-badge">{recordIcon(record)}{recordKindLabel(record)}</span>
          <h3>{record.title}</h3>
          {record.sourceExcerpt ? <p>{record.sourceExcerpt}</p> : null}
        </div>
        {stateLabel ? <Badge tone={stateTone}>{stateLabel}</Badge> : null}
      </header>
      {summaryItems.length ? (
        <p className="iu-li-record__summary">{summaryItems[0]}</p>
      ) : null}
      <dl className="iu-li-meta iu-li-meta--compact">
        {metaItems.slice(0, 3).map(([label, value]) => (
          <div key={`${record.id}-${label}`}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="iu-li-evidence-row">
        <span className="iu-od-source-badge">{record.evidenceType || 'informazione'}</span>
        {record.contextCompleted ? <span className="iu-od-source-badge">letto in IUSENTRA</span> : null}
      </div>
      <footer className="iu-od-action-row iu-li-record__actions">
        <Button type="button" tone="primary" onClick={() => onOpen(record)}>
          <BookOpen size={16} aria-hidden="true" />
          Leggi scheda
        </Button>
        <ButtonLink href={`/legal-intelligence/fonte/${encodeURIComponent(record.id)}/scarica`} tone="neutral" download>
          <Download size={16} aria-hidden="true" />
          Scarica
        </ButtonLink>
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer" className="iu-li-official-link">
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
  const isMediazioneRecord = record.kind.toLocaleLowerCase('it-IT').includes('mediazione')
  const sourceMeta = [
    ['Fonte', record.sourceLabel || 'Non indicata'],
    ['Tipo', cleanVisibleLabel(record.sourceKind) || 'Non indicato'],
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
        <span className="iu-od-source-badge">{recordIcon(record)}{recordKindLabel(record)}</span>
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
        <ButtonLink href={`/legal-intelligence/fonte/${encodeURIComponent(record.id)}/scarica`} tone="primary" download>
          <Download size={16} aria-hidden="true" />
          Scarica scheda
        </ButtonLink>
        {view !== 'mediazione' ? (
          <Button type="button" tone="neutral" onClick={() => onSearchRelated(relatedQuery(record))}>
            <Search size={16} aria-hidden="true" />
            Cerca collegati
          </Button>
        ) : null}
        {record.sourceHref ? (
          <ButtonLink href={record.sourceHref} tone="neutral" target="_blank" rel="noreferrer" className="iu-li-official-link">
            <ExternalLink size={16} aria-hidden="true" />
            Fonte originale
          </ButtonLink>
        ) : null}
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
  const hasSelectFilters = Boolean(kind || source || area || state || scope || quality)
  const hasActiveFilters = Boolean(hasSelectFilters || (isSearch ? submittedQuery : query))
  return (
    <section className="iu-li-filters iu-od-source-card" aria-label={isSearch ? 'Ricerca fonti legali' : 'Filtro schede'}>
      <form
        className={hasActiveFilters ? 'iu-li-search-form iu-li-search-form--with-reset' : 'iu-li-search-form'}
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
        <details className="iu-li-advanced-filters" open={hasSelectFilters || undefined}>
          <summary>
            <Filter size={14} aria-hidden="true" />
            Filtri avanzati
          </summary>
          <div className="iu-li-filter-grid" aria-label="Filtri schede">
            <label>
              <span>Ambito</span>
              <select value={scope} onChange={(event) => onScope(event.target.value)}>
                <option value="">Tutti</option>
                <option value="giurisprudenza">Giurisprudenza e Cassazione</option>
                <option value="normativa">Normativa</option>
                <option value="news">Aggiornamenti</option>
                <option value="mediazione">Mediazione</option>
              </select>
            </label>
            <label>
              <span>Fonte</span>
              <select value={source} onChange={(event) => onSource(event.target.value)}>
                <option value="">Tutte</option>
                {sources.map((option) => <option value={option} key={option}>{cleanVisibleLabel(option) || option}</option>)}
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
                {kinds.map((option) => <option value={option} key={option}>{cleanVisibleLabel(option) || option}</option>)}
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
        </details>
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
  selectedId,
  onClose,
  records,
  allRecords,
  query,
  section,
  status,
  type,
  territory,
  region,
  contact,
  onQuery,
  onSubmit,
  onSection,
  onStatus,
  onType,
  onTerritory,
  onRegion,
  onContact,
  onReset,
  onOpen,
}: {
  selectedId: string
  onClose: () => void
  records: LegalIntelligenceRecord[]
  allRecords: LegalIntelligenceRecord[]
  query: string
  section: string
  status: string
  type: string
  territory: string
  region: string
  contact: string
  onQuery: (value: string) => void
  onSubmit: () => void
  onSection: (value: string) => void
  onStatus: (value: string) => void
  onType: (value: string) => void
  onTerritory: (value: string) => void
  onRegion: (value: string) => void
  onContact: (value: string) => void
  onReset: () => void
  onOpen: (record: LegalIntelligenceRecord) => void
}) {
  const sectionOptions = uniqueOptions(allRecords, 'registrySection')
  const statusOptions = uniqueOptions(allRecords, 'stateLabel')
  const typeOptions = uniqueOptions(allRecords, 'organismoType')
  const locations = allRecords.flatMap((record) => record.locations || [])
  const regionOptions = [...new Set(locations.map((l) => l.region).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  const territoryOptions = [...new Set(locations.filter((l) => !region || l.region === region).map((l) => l.province).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  const scope = JSON.stringify([query, section, status, type, region, territory, contact])
  const [pagination, setPagination] = useState({ scope, page: 1 })
  const pageSize = 25
  useEffect(() => {
    const selectedIndex = records.findIndex((record) => record.id === selectedId)
    if (selectedIndex >= 0) setPagination({ scope, page: Math.floor(selectedIndex / pageSize) + 1 })
  }, [records, selectedId, scope])
  const closeDetail = (recordId: string) => {
    onClose()
    requestAnimationFrame(() => document.getElementById(`apri-${recordId}`)?.focus())
  }
  const pageCount = Math.max(1, Math.ceil(records.length / pageSize))
  const page = Math.min(pagination.scope === scope ? pagination.page : 1, pageCount)
  const firstRow = (page - 1) * pageSize
  const visibleRows = records.slice(firstRow, firstRow + pageSize)
  const organisms = allRecords.filter((record) => record.registryKind === 'organismo')
  const activeOrganisms = organisms.filter((record) => record.isActive)
  return (
    <section id="registro-mediazione" className="iu-li-registry iu-od-source-card" aria-label="Elenco organismi di mediazione">
      <header className="iu-li-section-head">
        <Landmark size={18} aria-hidden="true" />
        <div>
          <h2>Registro degli organismi di mediazione</h2>
          <p>{organisms.length.toLocaleString('it-IT')} organismi, di cui {activeOrganisms.length.toLocaleString('it-IT')} attivi nell'ultimo elenco acquisito.</p>
          <p>Il registro comprende anche enti di formazione e formatori: {allRecords.length.toLocaleString('it-IT')} voci complessive. Puoi consultarli dal filtro Sezione.</p>
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
          <span>Regione</span>
          <select value={region} onChange={(event) => onRegion(event.target.value)}>
            <option value="">Tutte le regioni</option>
            {regionOptions.map((option) => <option value={option} key={option}>{option}</option>)}
          </select>
        </label>
        <label>
          <span>Provincia</span>
          <select value={territory} disabled={!region} onChange={(event) => onTerritory(event.target.value)}>
            <option value="">{region ? 'Tutte le province' : 'Scegli prima la regione'}</option>
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
        {(query || section || status || type || region || territory || contact) ? (
          <Button type="button" tone="neutral" onClick={onReset}>Azzera filtri</Button>
        ) : null}
      </div>
      {visibleRows.length ? (
        <div className="iu-li-registry-table-wrap" role="region" aria-label="Risultati del registro, tabella scorrevole" tabIndex={0}>
          <table className="iu-li-registry-table">
            <thead>
              <tr>
                <th>Sezione</th>
                <th>N. registro</th>
                <th>Denominazione / nominativo</th>
                <th>Natura</th>
                <th>Stato</th>
                <th>Identificativi</th>
                <th>Contatti</th>
                <th>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((record) => (
                <Fragment key={record.id}><tr>
                  <td data-label="Sezione">{record.registrySection || 'Registro mediazione'}</td>
                  <td data-label="N. registro"><strong>{record.registryNumber || record.taxCode || '-'}</strong></td>
                  <td data-label="Denominazione / nominativo">
                    <span className="iu-li-registry-table__title">{record.title}</span>
                    {record.territory ? <small>{record.territory}</small> : null}
                  </td>
                  <td data-label="Natura">{record.organismoType || record.subtitle || '-'}</td>
                  <td data-label="Stato"><Badge tone={record.stateTone}>{record.stateLabel || 'Fonte da completare'}</Badge></td>
                  <td data-label="Identificativi">
                    <span>{record.taxCode ? `CF ${record.taxCode}` : 'CF non indicato'}</span>
                    <small>{record.vatNumber ? `P. IVA ${record.vatNumber}` : 'P. IVA non indicata'}</small>
                  </td>
                  <td data-label="Contatti">
                    {record.email ? <span><Mail size={14} aria-hidden="true" /> {record.email}</span> : <span>Email non indicata</span>}
                    {mediazioneWebsite(record.website) ? <a className="iu-li-registry-website" href={mediazioneWebsite(record.website)} target="_blank" rel="noopener noreferrer" aria-label={`Apri sito web: ${record.title} (nuova scheda)`}><Globe2 size={14} aria-hidden="true" /> {record.website}</a> : record.website ? <small>{record.website}</small> : null}
                  </td>
                  <td data-label="Azioni">
                    <Button id={`apri-${record.id}`} type="button" tone="neutral" aria-label={`${selectedId === record.id ? 'Chiudi' : 'Apri'} scheda: ${record.title}`} aria-expanded={selectedId === record.id} aria-controls={`dettaglio-${record.id}`} onClick={() => selectedId === record.id ? closeDetail(record.id) : onOpen(record)}>
                      <BookOpen size={15} aria-hidden="true" />
                      {selectedId === record.id ? 'Chiudi' : 'Scheda'}
                    </Button>
                  </td>
                </tr>
                {selectedId === record.id ? <tr className="iu-li-registry-detail-row"><td colSpan={8}>
                  <div id={`dettaglio-${record.id}`}><MediazioneOrganismoDetail record={record} region={region} province={territory} onClose={() => closeDetail(record.id)} /></div>
                </td></tr> : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="Nessuna voce con questi filtri"
          message="Modifica ricerca, stato, natura o territorio per restringere il registro acquisito."
        />
      )}
      <nav className="iu-li-registry-pagination" aria-label="Pagine del registro mediazione">
        <p className="iu-li-registry-note" role="status">
          {records.length ? `${firstRow + 1}–${firstRow + visibleRows.length} di ${records.length.toLocaleString('it-IT')} risultati. Pagina ${page} di ${pageCount}.` : '0 risultati.'}
        </p>
        <Button type="button" tone="neutral" disabled={page === 1} onClick={() => setPagination({ scope, page: page - 1 })}>Precedente</Button>
        <Button type="button" tone="neutral" disabled={page === pageCount} onClick={() => setPagination({ scope, page: page + 1 })}>Successiva</Button>
      </nav>
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
  const [mediazioneSection, setMediazioneSection] = useState('Organismi di mediazione')
  const [mediazioneStatus, setMediazioneStatus] = useState('attivo')
  const [mediazioneType, setMediazioneType] = useState('')
  const [mediazioneTerritory, setMediazioneTerritory] = useState('')
  const [mediazioneRegion, setMediazioneRegion] = useState('')
  const [mediazioneContact, setMediazioneContact] = useState('')
  const [fullscreenOpen, setFullscreenOpen] = useState(false)
  useEffect(() => {
    let active = true
    setLoading(true)
    loadPage(view, '')
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
  useEffect(() => () => clearPageFullscreen(LEGAL_INTELLIGENCE_FULLSCREEN_CLASS), [])
  const localFilter = view === 'ricerca-legale' ? submittedQuery : query
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
    (record.locations || []).map((l) => `${l.region} ${l.province} ${l.city}`).join(' '),
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
      if ((mediazioneRegion || mediazioneTerritory) && !(record.locations || []).some((l) =>
        (!mediazioneRegion || l.region === mediazioneRegion) && (!mediazioneTerritory || l.province === mediazioneTerritory))) return false
      if (mediazioneContact === 'email' && !record.email) return false
      if (mediazioneContact === 'website' && !record.website) return false
      return true
    })
  }, [mediazioneRegistryRecords, mediazioneContact, mediazioneSection, mediazioneStatus, mediazioneRegion, mediazioneTerritory, mediazioneType, view])
  // Rete di sicurezza lato client: oltre questa soglia il rendering integrale
  // dell'inventario (950+ schede) fa cadere la pagina; il totale resta visibile
  // nell'intestazione e la ricerca filtra comunque l'intero archivio caricato.
  const visibleRecords = (view === 'mediazione'
    ? [...mediazioneOfficialRecords, ...filteredMediazioneRegistryRecords]
    : filteredLegalRecords
  ).slice(0, 120)
  const selectedRecord = (view === 'mediazione' ? data.records : visibleRecords).find((record) => record.id === selectedId) || visibleRecords[0]
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
    const shouldScrollToDetail = !isImportedMediazioneRecord(record) && (view === 'mediazione' || window.matchMedia('(max-width: 1179px)').matches)
    if (shouldScrollToDetail) {
      window.requestAnimationFrame(() => document.querySelector('.iu-li-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
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
          <ButtonLink href="/lex-operativo" tone="neutral"><MessageCircle size={16} aria-hidden="true" />Assistente Lex</ButtonLink>
          <ButtonLink href="/giurisprudenza" tone="neutral"><Archive size={16} aria-hidden="true" />Archivio giurisprudenza</ButtonLink>
          <Button
            type="button"
            tone="neutral"
            aria-pressed={fullscreenOpen}
            onClick={() => setFullscreenOpen(togglePageFullscreen('main.iu-content', LEGAL_INTELLIGENCE_FULLSCREEN_CLASS))}
          >
            {fullscreenOpen ? <Minimize2 size={16} aria-hidden="true" /> : <Maximize2 size={16} aria-hidden="true" />}
            {fullscreenOpen ? 'Riduci' : 'Tutto schermo'}
          </Button>
        </>
      )}
    >
      <div className={`iu-li-page iu-li-page--${view}`}>
        <WarningList data={data} />
        <NavigationTabs view={view} />
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
                selectedId={selectedId}
                onClose={() => {
                  setSelectedId('')
                  const params = new URLSearchParams(window.location.search)
                  params.delete('scheda')
                  window.history.replaceState({}, '', `${window.location.pathname}${params.size ? `?${params}` : ''}`)
                }}
                records={filteredMediazioneRegistryRecords}
                allRecords={data.records.filter(isImportedMediazioneRecord)}
                query={query}
                section={mediazioneSection}
                status={mediazioneStatus}
                type={mediazioneType}
                territory={mediazioneTerritory}
                region={mediazioneRegion}
                contact={mediazioneContact}
                onQuery={setQuery}
                onSubmit={submitSearch}
                onSection={setMediazioneSection}
                onStatus={setMediazioneStatus}
                onType={setMediazioneType}
                onTerritory={setMediazioneTerritory}
                onRegion={(value) => { setMediazioneRegion(value); setMediazioneTerritory('') }}
                onContact={setMediazioneContact}
                onReset={() => {
                  setMediazioneStatus('')
                  setMediazioneSection('')
                  setMediazioneType('')
                  setMediazioneTerritory('')
                  setMediazioneRegion('')
                  setMediazioneContact('')
                  resetSearch()
                }}
                onOpen={openRecord}
              />
            ) : null}
            <section id="schede" className="iu-li-results" aria-label="Schede ricerca legale">
              <ResultHeader
                view={view}
                visibleCount={view === 'mediazione' ? mediazioneOfficialRecords.length : visibleRecords.length}
                totalCount={view === 'mediazione' ? mediazioneOfficialRecords.length : data.records.length}
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
          {view !== 'mediazione' || !selectedRecord || !isImportedMediazioneRecord(selectedRecord) ? <RecordDetail record={selectedRecord} view={view} onSearchRelated={runSearch} /> : null}
        </div>
        {view === 'ricerca-legale' ? <CollapsibleSourceDashboard data={data} onArchiveSearch={runArchiveSearch} /> : null}
      </div>
    </Page>
  )
}
function CollapsibleSourceDashboard({
  data,
  onArchiveSearch,
}: {
  data: LegalIntelligencePageData
  onArchiveSearch: (query: string, scope?: string, source?: string) => void
}) {
  const [open, setOpen] = useState(false)
  const hasMonitor = data.autofetchMonitor.sourcesTotal > 0 || data.autofetchMonitor.sources.length > 0
  if (!hasMonitor && !data.metrics.length) return null
  return (
    <section className="iu-li-collapsible-sources iu-od-source-card" aria-label="Stato fonti e acquisizioni">
      <button
        className="iu-li-collapsible-sources__toggle"
        onClick={() => setOpen(!open)}
        type="button"
        aria-expanded={open}
      >
        <SearchCheck size={18} aria-hidden="true" />
        <div>
          <strong>Stato fonti e acquisizioni</strong>
          <span>{data.autofetchMonitor.sourcesReady} fonti pronte · {data.autofetchMonitor.sourcesNotReady} da completare</span>
        </div>
        {open ? <ChevronUp size={18} aria-hidden="true" /> : <ChevronDown size={18} aria-hidden="true" />}
      </button>
      {open ? <DataAccessPanel data={data} onArchiveSearch={onArchiveSearch} /> : null}
    </section>
  )
}
