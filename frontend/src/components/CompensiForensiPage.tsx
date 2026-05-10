import { useEffect, useMemo, useState } from 'react'
import { Banknote, Calculator, ExternalLink, RefreshCw, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import { displaySourceLabel } from '../displayText'
import {
  calculateCompensiForensi,
  emptyCompensiForensiPage,
  getCompensiForensiPage,
  type CompensiForensiCalculationResult,
  type CompensiForensiPageData,
} from '../compensiForensiData'
import './CompensiForensiPage.css'

function ContractStrip({ data }: { data: CompensiForensiPageData }) {
  return (
    <aside className="iu-comp-contract iu-od-surface">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {displaySourceLabel(data.source)} - calcolo governato
        </span>
      </div>
    </aside>
  )
}

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

function Metrics({ data }: { data: CompensiForensiPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-comp-metrics" aria-label="Indicatori compensi forensi">
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

function Sections({ data }: { data: CompensiForensiPageData }) {
  if (!data.sections.length) return null
  return (
    <section className="iu-comp-section-grid" aria-label="Aree compensi forensi">
      {data.sections.map((section) => (
        <Panel title={section.title} subtitle={displaySourceLabel(section.kind)} key={section.id}>
          {section.items.length ? (
            <div className="iu-comp-list">
              {section.items.map((item) => (
                <div className="iu-comp-row" key={item.id}>
                  <div>
                    <strong>{item.label}</strong>
                    {item.note ? <span>{item.note}</span> : null}
                  </div>
                  <Badge tone={item.tone}>{item.value || 'Dato'}</Badge>
                </div>
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
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState<CompensiForensiCalculationResult | null>(null)
  const [area, setArea] = useState('')
  const [proceeding, setProceeding] = useState('')
  const [phase, setPhase] = useState('')
  const [value, setValue] = useState('0')
  const [complexity, setComplexity] = useState('media')

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
    return <LoadingState title="Caricamento compensi forensi" message="Recupero i dati reali." />
  }

  return (
    <Page
      title="Compensi forensi"
      subtitle="Calcolo operativo con parametri e risultati governati dallo studio."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>
          <ButtonLink href="/tariffario" tone="primary">
            <Banknote size={16} aria-hidden="true" />
            Tariffario
          </ButtonLink>
        </>
      }
    >
      <div className="iu-comp-page iu-od-stack">
        {calculating ? <LoadingState title="Calcolo compensi" message="Elaborazione del risultato in corso." /> : null}
        {saving ? <div className="iu-comp-state" role="status">Salvataggio richiesta in corso.</div> : null}
        {success ? <div className="iu-comp-state iu-comp-state--success" role="status">{success}</div> : null}
        {error ? <div className="iu-comp-state iu-comp-state--error" role="alert">{error}</div> : null}
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics data={data} />
        <section className="iu-comp-hero iu-od-surface">
          <div>
            <h2>Parametri di calcolo</h2>
            <p>
              Inserisci i parametri e ottieni un risultato tracciabile, pronto per verifica e salvataggio.
            </p>
          </div>
          <div className="iu-comp-actions">
            {data.actions.links.map((action) => (
              <ButtonLink key={action.id} href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'}>
                <ExternalLink size={16} aria-hidden="true" />
                {action.label}
              </ButtonLink>
            ))}
          </div>
        </section>
        <Panel title="Calcolo compensi" subtitle="Nessuna formula viene eseguita nel browser.">
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
                <span>Complessita</span>
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
        <Sections data={data} />
      </div>
    </Page>
  )
}
