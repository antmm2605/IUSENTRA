import { useEffect, useMemo, useRef, useState } from 'react'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { operationalDomains } from '../operationalRefresh'
import { formatDateTimeIt, formatEuroIt } from '../formatting'
import { ArrowRight, Download, RefreshCw } from 'lucide-react'
import {
  emptyStatistichePage,
  getStatistichePage,
  type StatisticheAction,
  type StatisticheItem,
  type StatisticheMetric,
  type StatistichePageData,
} from '../statisticheData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { displaySourceLabel, displayWritesLabel } from '../displayText'
import './StatistichePage.css'

function displayValue(value: string | number | undefined): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return String(value || '')
}

function actionTone(action: StatisticheAction) {
  return action.tone === 'danger' || action.tone === 'success' || action.tone === 'warning'
    ? action.tone
    : action.id === 'refresh'
      ? 'primary'
      : 'neutral'
}

function MetricCard({ metric, selected, onSelect }: { metric: StatisticheMetric; selected: boolean; onSelect: () => void }) {
  const href = metric.id === 'clienti' ? '/clienti' : metric.id === 'incassi' ? '/incassi-pagamenti?riepilogo=crediti' : ''
  const content = <><span className="iu-stat-metric__label">{metric.label}</span><strong>{metric.id === 'incassi' ? formatEuroIt(metric.value) : displayValue(metric.value)}</strong><small>{metric.note}</small><span className="iu-stat-metric__action">{href ? 'Apri elenco' : 'Filtra riepiloghi'}<ArrowRight size={12} aria-hidden="true"/></span></>
  return href ? <ButtonLink className="iu-stat-metric" tone="neutral" href={href}>{content}</ButtonLink> : <Button className="iu-stat-metric" tone="neutral" type="button" aria-pressed={selected} onClick={onSelect}>{content}</Button>
}

function ProgressRow({ item, max, money = false, selected, onSelect }: { item: StatisticheItem; max: number; money?: boolean; selected: boolean; onSelect: () => void }) {
  const numeric = typeof item.value === 'number' ? item.value : Number(item.value) || 0
  const width = max > 0 && numeric > 0 ? Math.min(100, (numeric / max) * 100) : 0
  return (
    <button type="button" className="iu-stat-row" aria-pressed={selected} aria-label={`Filtra i riepiloghi per ${item.label}`} onClick={onSelect}>
      <span className="iu-stat-row__head">
        <strong>{item.label}</strong>
        <span>{money ? formatEuroIt(item.value) : displayValue(item.value)}</span>
        <ArrowRight size={14} aria-hidden="true" />
      </span>
      <span className="iu-stat-row__bar" aria-hidden="true">
        <i style={{ width: `${width}%` }} />
      </span>
      {item.secondaryValue !== undefined || item.note ? (
        <small>{item.secondaryValue !== undefined ? `${item.secondaryLabel || (money ? 'Incassato' : 'Esiti')}: ${money ? formatEuroIt(item.secondaryValue) : displayValue(item.secondaryValue)}` : item.note}</small>
      ) : null}
    </button>
  )
}

function Warnings({ data }: { data: StatistichePageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi operativi">
      <div className="iu-stat-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-stat-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function SectionRows({ items, max, money = false, query, onSelect }: { items: StatisticheItem[]; max: number; money?: boolean; query: string; onSelect: (label: string) => void }) {
  return (
    <div className="iu-stat-rows">
      {items.map((item) => <ProgressRow item={item} max={max} money={money} selected={query === item.label.toLocaleLowerCase('it-IT')} onSelect={() => onSelect(item.label)} key={item.id} />)}
    </div>
  )
}

const sectionActions: Record<string, { href: string; label: string }> = {
  fascicoli_tipo: { href: '/fascicoli', label: 'Apri fascicoli' },
  fascicoli_stato: { href: '/fascicoli', label: 'Apri fascicoli' },
  scadenze_priorita: { href: '/scadenziario?vista=tutte', label: 'Apri scadenze' },
  chiusure_registrate: { href: '/scadenziario?vista=completate', label: 'Apri chiusure' },
  agenda_tipo: { href: '/agenda', label: 'Apri agenda' },
  fatturato_mensile: { href: '/fatturazione', label: 'Apri fatturazione' },
  depositi_trend: { href: '/fascicoli', label: 'Apri fascicoli' },
  preventivi_stato: { href: '/preventivi', label: 'Apri preventivi' },
  incarichi_stato: { href: '/preventivi', label: 'Apri incarichi' },
  timesheet_stato: { href: '/timesheet', label: 'Apri timesheet' },
}

export function StatistichePage() {
  const [data, setData] = useState<StatistichePageData>(emptyStatistichePage)
  const [loading, setLoading] = useState(true)
  const [metricFilter, setMetricFilter] = useState('')
  const [query, setQuery] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const refreshFlight = useRef<Promise<void> | null>(null)
  const [refreshError, setRefreshError] = useState('')
  const relatedSections: Record<string, string[]> = {
    fascicoli: ['fascicoli_tipo', 'fascicoli_stato', 'depositi_trend'],
    scadenze: ['scadenze_priorita'], agenda: ['agenda_tipo'],
    produttivita: ['chiusure_registrate'],
  }
  const relatedRecords: Record<string, string[]> = {
    fascicoli: ['fascicoli_attivi', 'fascicoli_aperti', 'fascicoli_sospesi'], scadenze: ['scadenze_aperte'],
    agenda: [], produttivita: ['scadenze_completate'],
  }
  const lowered = query.trim().toLocaleLowerCase('it-IT')
  const sectionSource = data.metricSections[metricFilter] || data.sections
  const sections = sectionSource.filter(section => data.metricSections[metricFilter] || !metricFilter || relatedSections[metricFilter]?.includes(section.id)).map(section => ({...section,maxValue:Math.max(0,...section.items.map(item => Number(item.value) || 0)),items:section.items.filter(item => `${section.title} ${item.label} ${item.note}`.toLocaleLowerCase('it-IT').includes(lowered))})).filter(section => !lowered || section.items.length > 0)
  const visibleItemCount = sections.reduce((count, section) => count + section.items.length, 0)
  const records = data.records.filter(record => (!metricFilter || relatedRecords[metricFilter]?.includes(record.id)) && `${record.label} ${record.note}`.toLocaleLowerCase('it-IT').includes(lowered))
  function refresh(): Promise<void> {
    if (refreshFlight.current) return refreshFlight.current
    setRefreshing(true)
    const flight = (async () => {
      try {
        const payload = await getStatistichePage()
        if (payload.source === 'errore_controllato') throw new Error('Dati non disponibili')
        setData(payload)
        setRefreshError('')
      } catch { setRefreshError('Aggiornamento non riuscito. I dati e i filtri restano conservati: riprova.') }
      finally { setRefreshing(false); refreshFlight.current = null }
    })()
    refreshFlight.current = flight
    return flight
  }
  useOperationalRefresh(operationalDomains, refresh)

  useEffect(() => {
    let active = true
    getStatistichePage()
      .then((payload) => {
        if (active) setData(payload)
      })
      .catch(() => { if (active) setRefreshError('Impossibile leggere le statistiche: riprova.') })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.records.length > 0 || data.sections.some((section) => section.items.length > 0),
    [data],
  )
  const safeActions = data.actions.filter((action) => action.method === 'GET' && action.href)

  return (
    <Page
      title="Statistiche"
      subtitle="Indicatori reali letti dagli archivi operativi dello studio."
      actions={
        <>
          <Button type="button" onClick={refresh} disabled={loading || refreshing} tone="primary">
            <RefreshCw size={16} />
            {refreshing ? 'Aggiornamento…' : 'Aggiorna'}
          </Button>
          {safeActions.filter((action) => action.id !== 'refresh').slice(0, 2).map((action) => (
            <ButtonLink href={action.href} tone={actionTone(action)} key={action.id}>
              <Download size={16} />
              {action.label}
            </ButtonLink>
          ))}
        </>
      }
    >
      {refreshing ? <p role="status">Aggiornamento dei dati in corso. I filtri restano conservati.</p> : null}
      {loading ? <LoadingState title="Caricamento statistiche" message="Lettura degli archivi reali in corso." /> : null}
      {refreshError ? <div role="alert">{refreshError}<Button type="button" tone="neutral" onClick={refresh}>Riprova aggiornamento</Button></div> : null}
      {!loading && !refreshError && !hasData ? (
        <EmptyState
          title="Nessun dato statistico disponibile"
          message="Gli archivi non contengono ancora elementi sufficienti per alimentare questa pagina."
        />
      ) : null}
      {!loading && hasData ? (
        <>
          <Warnings data={data} />
          <section className="iu-stat-kpis" aria-label="Indicatori statistiche">
            {data.metrics.map((metric) => (
              <MetricCard
                metric={metric}
                key={metric.id}
                onSelect={() => setMetricFilter(current => current === metric.id ? '' : metric.id)}
                selected={metricFilter === metric.id}
              />
            ))}
          </section>
          <div className="iu-stat-filters"><label>Cerca nei riepiloghi<input type="search" value={query} onChange={event => setQuery(event.currentTarget.value)} placeholder="Tipo, stato, attività o indicatore…" /></label><Button type="button" tone="neutral" disabled={!query && !metricFilter} onClick={() => { setQuery(''); setMetricFilter('') }}>Azzera filtri</Button>{metricFilter === 'agenda' ? <ButtonLink href={`/agenda?vista=day&data=${data.metrics.find(metric => metric.id === 'agenda')?.note.split('/').reverse().join('-') || ''}`} tone="neutral">Apri gli appuntamenti di oggi</ButtonLink> : null}</div>
          <p className="iu-stat-result-count" role="status">{sections.length} {sections.length === 1 ? 'riepilogo' : 'riepiloghi'} · {visibleItemCount} {visibleItemCount === 1 ? 'voce' : 'voci'}. Seleziona una voce per filtrare i riepiloghi.</p>
          {!sections.length ? <EmptyState title="Nessun riepilogo con questi filtri" message="Modifica la ricerca o azzera i filtri per tornare ai dati dello studio." /> : null}
          <section className={`iu-stat-grid${sections.length === 1 ? ' iu-stat-grid--single' : ''}`} aria-label="Sezioni statistiche">
            {sections.map((section) => (
              <Panel title={section.title} subtitle={metricFilter && data.metricSections[metricFilter] ? 'Solo il contesto selezionato' : section.kind === 'monthly' ? 'Andamento mensile' : 'Distribuzione archivio'} key={section.id} actions={section.id === 'comunicazioni' ? <><ButtonLink tone="neutral" href="/email/">PEC</ButtonLink><ButtonLink tone="neutral" href="/email-ordinaria/">Email ordinarie</ButtonLink><ButtonLink tone="neutral" href="/messaggi">Messaggi</ButtonLink></> : sectionActions[section.id] ? <ButtonLink tone="neutral" href={section.id === 'scadenze_priorita' && metricFilter === 'scadenze' ? '/scadenziario?vista=aperte' : section.id === 'agenda_tipo' && metricFilter === 'agenda' ? `/agenda?vista=day&data=${data.metrics.find(metric => metric.id === 'agenda')?.note.split('/').reverse().join('-') || ''}` : sectionActions[section.id].href} aria-label={`${sectionActions[section.id].label}: ${section.title}`}>{sectionActions[section.id].label}<ArrowRight size={14} aria-hidden="true" /></ButtonLink> : undefined}>
                {section.items.length ? <SectionRows items={section.items} max={section.maxValue} money={section.id === 'fatturato_mensile'} query={lowered} onSelect={label => setQuery(current => current.trim().toLocaleLowerCase('it-IT') === label.toLocaleLowerCase('it-IT') ? '' : label)} /> : (
                  <p className="iu-stat-section-empty">{section.emptyMessage}</p>
                )}
              </Panel>
            ))}
          </section>
          {metricFilter === 'produttivita' ? <p className="iu-stat-explanation">Il confronto usa la data di chiusura registrata e il termine salvato. Una chiusura registrata dopo il termine non dimostra, da sola, che l’adempimento sia stato eseguito in ritardo. Le date mancanti restano escluse dalla percentuale e visibili nel riepilogo.</p> : null}
          {records.length || (!lowered && !metricFilter) ? <Panel title="Indicatori principali" subtitle="Collegamenti verso i moduli operativi collegati.">
            {records.length ? (
              <div className="iu-stat-records">
                {records.map((record) => (
                  <a className="iu-stat-record" href={record.href} aria-label={record.label} key={record.id}>
                    <span>{record.label}</span>
                    <strong>{displayValue(record.value)}</strong>
                    {record.note ? <small>{record.note}</small> : null}
                  </a>
                ))}
              </div>
            ) : (
              <EmptyState title="Nessun indicatore riepilogativo" />
            )}
          </Panel>
          : null}
          <Panel title="Presidio dati" subtitle="Origine e azioni governate per questa vista.">
            <div className="iu-stat-contract">
              <span>Origine: {displaySourceLabel(data.source)}</span>
              <span>Generato: {formatDateTimeIt(data.generated_at, 'Non disponibile')}</span>
              <span>Azioni: {displayWritesLabel(data.contracts.writes)}</span>
              <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'sì'}</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
