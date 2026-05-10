import { useEffect, useMemo, useState } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import {
  emptyStatistichePage,
  getStatistichePage,
  type StatisticheAction,
  type StatisticheItem,
  type StatistichePageData,
} from '../statisticheData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
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

function ProgressRow({ item, max }: { item: StatisticheItem; max: number }) {
  const numeric = typeof item.value === 'number' ? item.value : Number(item.value) || 0
  const width = max > 0 ? Math.max(4, Math.round((numeric / max) * 100)) : 0
  return (
    <div className="iu-stat-row">
      <div className="iu-stat-row__head">
        <strong>{item.label}</strong>
        <span>{displayValue(item.value)}</span>
      </div>
      <div className="iu-stat-row__bar" aria-hidden="true">
        <i style={{ width: `${width}%` }} />
      </div>
      {item.secondaryValue || item.note ? (
        <small>{item.secondaryValue ? `Secondario: ${displayValue(item.secondaryValue)}` : item.note}</small>
      ) : null}
    </div>
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

function SectionRows({ items }: { items: StatisticheItem[] }) {
  const max = Math.max(0, ...items.map((item) => (typeof item.value === 'number' ? item.value : Number(item.value) || 0)))
  return (
    <div className="iu-stat-rows">
      {items.map((item) => <ProgressRow item={item} max={max} key={item.id} />)}
    </div>
  )
}

export function StatistichePage() {
  const [data, setData] = useState<StatistichePageData>(emptyStatistichePage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getStatistichePage()
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
          <ButtonLink href="/statistiche" tone="primary">
            <RefreshCw size={16} />
            Aggiorna
          </ButtonLink>
          {safeActions.filter((action) => action.id !== 'refresh').slice(0, 2).map((action) => (
            <ButtonLink href={action.href} tone={actionTone(action)} key={action.id}>
              <Download size={16} />
              {action.label}
            </ButtonLink>
          ))}
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento statistiche" message="Lettura degli archivi reali in corso." /> : null}
      {!loading && !hasData ? (
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
              <KpiCard
                label={metric.label}
                value={displayValue(metric.value)}
                note={metric.note}
                badge={<Badge tone={metric.tone}>{metric.tone === 'neutral' ? 'Dato' : 'Stato'}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <section className="iu-stat-grid" aria-label="Sezioni statistiche">
            {data.sections.map((section) => (
              <Panel title={section.title} subtitle={section.kind} key={section.id}>
                {section.items.length ? <SectionRows items={section.items} /> : (
                  <EmptyState title={section.emptyMessage} />
                )}
              </Panel>
            ))}
          </section>
          <Panel title="Indicatori principali" subtitle="Collegamenti verso i moduli operativi collegati.">
            {data.records.length ? (
              <div className="iu-stat-records">
                {data.records.map((record) => (
                  <a className="iu-stat-record" href={record.href} key={record.id}>
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
          <Panel title="Presidio dati" subtitle="Origine e azioni governate per questa vista.">
            <div className="iu-stat-contract">
              <span>Origine: {displaySourceLabel(data.source)}</span>
              <span>Generato: {data.generated_at || 'non disponibile'}</span>
              <span>Azioni: {displayWritesLabel(data.contracts.writes)}</span>
              <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'si'}</span>
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}
