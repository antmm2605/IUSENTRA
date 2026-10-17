import { useBusyActivity } from '../ui/useBusyActivity'
import { useEffect, useMemo, useState } from 'react'
import { Calculator, ExternalLink, Maximize2, Minimize2, RefreshCw } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import {
  calculateCompensiForensi,
  emptyCompensiForensiPage,
  getCompensiForensiPage,
  type CompensiForensiCalculationResult,
  type CompensiForensiPageData,
} from '../compensiForensiData'
import './CompensiForensiPage.css'
import { CompensiCatalogWindow } from './CompensiCatalogWindow'

function WarningList({ data }: { data: CompensiForensiPageData }) {
  if (!data.warnings.length) return null
  return (
    <div className="iu-comp-warnings" role="status">
      {data.warnings.map((warning) => (
        <p className="iu-comp-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </div>
  )
}

function Metrics({ data, onCatalog }: { data: CompensiForensiPageData; onCatalog: (kind: 'profili' | 'regole') => void }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-comp-metrics" aria-label="Indicatori compensi forensi">
      {data.metrics.map((metric) => (
        metric.id === 'profili' || metric.id === 'regole'
          ? <Button key={metric.id} type="button" tone="neutral" onClick={() => onCatalog(metric.id as 'profili' | 'regole')}>
              {metric.label}<Badge tone={metric.tone}>{metric.value || 0}</Badge>
            </Button>
          : <ButtonLink key={metric.id} tone="neutral" href={metric.id === 'preventivi' ? '/preventivi?metric=preventivi_totali' : '/preventivi?metric=conferimenti'}>
              {metric.label}<Badge tone={metric.tone}>{metric.value || 0}</Badge>
            </ButtonLink>
      ))}
    </section>
  )
}

function ResultPanel({ result }: { result: CompensiForensiCalculationResult | null }) {
  if (!result) {
    return (
      <Panel title="Risultato calcolo">
        <EmptyState title="Nessun risultato calcolato" message="Inserisci i parametri e avvia il calcolo." />
      </Panel>
    )
  }
  return (
    <Panel title={result.title || 'Risultato calcolo'} subtitle={result.engineLabel}>
      <div className="iu-comp-result">
        <p>{result.engineText}</p>
        <div className="iu-comp-result__badges">
          {result.badges.map((badge) => <Badge tone="info" key={badge}>{badge}</Badge>)}
        </div>
        {result.metadata.length ? (
          <dl className="iu-comp-result__meta">
            {result.metadata.map((item) => (
              <div key={`${item.label}-${item.value}`}>
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {result.economic?.rows.length ? (
          <dl className="iu-comp-result__meta">
            {result.economic.rows.map((row) => (
              <div key={row.id}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {result.note ? <p>{result.note}</p> : null}
      </div>
    </Panel>
  )
}

export function CompensiForensiPage() {
  const [data, setData] = useState<CompensiForensiPageData>(emptyCompensiForensiPage)
  const [loading, setLoading] = useState(true)
  const [calculating, setCalculating] = useState(false)
  const [saving, setSaving] = useState(false)
  useBusyActivity(saving, 'Salvataggio dei compensi…')
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState<CompensiForensiCalculationResult | null>(null)
  const [area, setArea] = useState('')
  const [proceeding, setProceeding] = useState('')
  const [phase, setPhase] = useState('')
  const [value, setValue] = useState('0')
  const [complexity, setComplexity] = useState('media')
  const [fullscreen, setFullscreen] = useState(false)
  const [catalogs, setCatalogs] = useState<Partial<Record<'profili' | 'regole', number>>>({})

  function load() {
    setLoading(true)
    getCompensiForensiPage()
      .then((payload) => {
        setData(payload)
        const firstArea = payload.parameters.areas[0]?.value || ''
        const firstProceeding = payload.parameters.proceedings[0]?.value || ''
        const firstComplexity = payload.parameters.complexities.find((item) => item.value === 'media')?.value
          || payload.parameters.complexities[0]?.value
          || 'media'
        if (!area) setArea(firstArea)
        if (!proceeding) setProceeding(firstProceeding)
        if (!complexity) setComplexity(firstComplexity)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    document.body.classList.toggle('iu-comp-fullscreen', fullscreen)
    return () => document.body.classList.remove('iu-comp-fullscreen')
  }, [fullscreen])

  const filteredProceedings = useMemo(() => {
    if (!area) return data.parameters.proceedings
    const filtered = data.parameters.proceedings.filter((item) => item.area === area)
    return filtered.length ? filtered : data.parameters.proceedings
  }, [area, data.parameters.proceedings])

  async function runCalculation() {
    setCalculating(true)
    setSaving(true)
    setSuccess('')
    setError('')
    const response = await calculateCompensiForensi({
      area,
      procedimento: proceeding,
      fase: phase,
      valore_controversia: Number(value || 0),
      complessita: complexity,
      aumenti: [],
      riduzioni: [],
      opzioni_fiscali: data.parameters.fiscal_options,
    })
    setCalculating(false)
    setSaving(false)
    if (!response.ok || !response.result) {
      setError(response.message)
      return
    }
    setResult(response.result)
    setSuccess(response.message)
  }

  if (loading) {
    return <LoadingState title="Caricamento del Calcolo Tariffario" message="Recupero i dati reali." />
  }

  return (
    <Page
      className="iu-comp-compact-page"
      title="Calcolo Tariffario"
      actions={
        <>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>

            <Button
              type="button"
              tone="neutral"
              onClick={() => setFullscreen((current) => !current)}
              aria-pressed={fullscreen}
              title={fullscreen ? 'Esci da tutto schermo' : 'Apri a tutto schermo'}
            >
              {fullscreen ? <Minimize2 size={16} aria-hidden="true" /> : <Maximize2 size={16} aria-hidden="true" />}
              {fullscreen ? 'Riduci' : 'Tutto schermo'}
            </Button>
            {data.actions.links.filter(action => !/_legacy=1|percorso_recupero/i.test(`${action.href} ${action.id}`)).map((action) => (
              <ButtonLink
                key={action.id}
                href={action.href}
                tone={action.tone === 'primary' ? 'primary' : action.tone === 'warning' ? 'warning' : 'neutral'}
                data-iusentra-secondary-action={/_legacy=1|percorso_recupero/i.test(`${action.href} ${action.id}`) ? 'recovery' : undefined}
              >
                <ExternalLink size={16} aria-hidden="true" />
                {action.label}
              </ButtonLink>
            ))}
        </>
      }
    >
      <div className={`iu-comp-page iu-od-stack${fullscreen ? ' iu-comp-page--fullscreen' : ''}`}>
        {fullscreen ? <Button type="button" tone="neutral" onClick={() => setFullscreen(false)}><Minimize2 size={16} aria-hidden="true" />Riduci</Button> : null}
        {calculating ? <LoadingState title="Calcolo compensi" message="Elaborazione del risultato in corso." /> : null}
        {saving ? <div className="iu-comp-state" role="status">Salvataggio richiesta in corso.</div> : null}
        {success ? <div className="iu-comp-state iu-comp-state--success" role="status">{success}</div> : null}
        {error ? <div className="iu-comp-state iu-comp-state--error" role="alert">{error}</div> : null}
        <WarningList data={data} />
        <Metrics data={data} onCatalog={kind => setCatalogs(current => ({ ...current, [kind]: (current[kind] || 0) + 1 }))} />
        {(['profili', 'regole'] as const).map(kind => catalogs[kind] ? <CompensiCatalogWindow key={kind} kind={kind} records={data.records} focusToken={catalogs[kind] || 0} canOpenTariffario={data.actions.canOpenTariffario}
          onClose={() => setCatalogs(current => { const next = { ...current }; delete next[kind]; return next })}/> : null)}
        <Panel title="Calcolo compensi">
          {data.actions.canCalculate ? (
            <div className="iu-comp-form">
              <label>
                <span>Area</span>
                <select value={area} onChange={(event) => setArea(event.target.value)}>
                  <option value="">Seleziona area</option>
                  {data.parameters.areas.map((item) => (
                    <option value={item.value} key={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Procedimento</span>
                <select value={proceeding} onChange={(event) => setProceeding(event.target.value)}>
                  <option value="">Standard di studio</option>
                  {filteredProceedings.map((item) => (
                    <option value={item.value} key={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Fase</span>
                <input value={phase} onChange={(event) => setPhase(event.target.value)} placeholder="Fase se prevista dal criterio scelto" />
              </label>
              <label>
                <span>Valore controversia</span>
                <input type="number" min="0" value={value} onChange={(event) => setValue(event.target.value)} />
              </label>
              <label>
                <span>Complessità</span>
                <select value={complexity} onChange={(event) => setComplexity(event.target.value)}>
                  {data.parameters.complexities.map((item) => (
                    <option value={item.value} key={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <Button type="button" tone="primary" onClick={runCalculation} disabled={calculating || !area}>
                <Calculator size={16} aria-hidden="true" />
                Calcola
              </Button>
            </div>
          ) : (
            <EmptyState title="Calcolo non autorizzato" message="La sessione corrente non ha permessi per il calcolo." />
          )}
        </Panel>
        <ResultPanel result={result} />
      </div>
    </Page>
  )
}
