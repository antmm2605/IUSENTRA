import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import { ExternalLink, FilePenLine, RefreshCw, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import {
  emptyRedazioneAttiPage,
  getRedazioneAttiPage,
  produceRedazioneAtto,
  type RedazioneAttiPageData,
  type RedazioneField,
  type RedazioneProduceResult,
} from '../redazioneAttiData'
import './RedazioneAttiPage.css'

function ContractStrip({ data }: { data: RedazioneAttiPageData }) {
  return (
    <aside className="iu-redazione-contract iu-od-surface">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>Redazione collegata ai dati dello studio</span>
      </div>
    </aside>
  )
}

function WarningList({ data }: { data: RedazioneAttiPageData }) {
  if (!data.warnings.length) return null
  return (
    <div className="iu-redazione-warnings" role="status">
      {data.warnings.map((warning) => (
        <p className="iu-redazione-warning iu-od-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </div>
  )
}

function Metrics({ data }: { data: RedazioneAttiPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-redazione-metrics" aria-label="Indicatori redazione atti">
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

function Sections({ data }: { data: RedazioneAttiPageData }) {
  if (!data.sections.length) return null
  return (
    <section className="iu-redazione-section-grid" aria-label="Percorso redazione">
      {data.sections.map((section) => (
        <Panel title={section.title} subtitle={section.kind} key={section.id}>
          {section.items.length ? (
            <div className="iu-redazione-list">
              {section.items.map((item) => (
                <div className="iu-redazione-row" key={item.id}>
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

function Records({ data }: { data: RedazioneAttiPageData }) {
  return (
    <Panel title="Punti operativi" subtitle="Collegamenti reali verso funzioni dello studio.">
      {data.records.length ? (
        <div className="iu-redazione-records">
          {data.records.map((record) => (
            <a className="iu-redazione-record iu-od-focus-ring" href={record.href} key={record.id}>
              <div>
                <strong>{record.title}</strong>
                {record.subtitle ? <span>{record.subtitle}</span> : null}
                {record.meta ? <small>{record.meta}</small> : null}
              </div>
              {record.stateLabel ? <Badge tone={record.stateTone}>{record.stateLabel}</Badge> : null}
            </a>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Nessun punto operativo disponibile"
          message="La pagina resta neutra finche' non sono disponibili collegamenti consultabili."
        />
      )}
    </Panel>
  )
}

function FieldInput({
  field,
  value,
  onChange,
  error,
}: {
  field: RedazioneField
  value: string
  onChange: (value: string) => void
  error?: string
}) {
  const common = {
    name: field.name,
    required: field.required,
    value,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onChange(event.target.value),
  }
  return (
    <label className={error ? 'has-error' : ''}>
      <span>{field.label}{field.required ? ' *' : ''}</span>
      {field.options.length ? (
        <select {...common}>
          <option value="">Seleziona</option>
          {field.options.map((option) => <option value={option.value} key={`${field.name}-${option.value}`}>{option.label}</option>)}
        </select>
      ) : field.type === 'textarea' || field.name.includes('facts') || field.name.includes('requests') ? (
        <textarea {...common} rows={4} />
      ) : (
        <input {...common} type={field.type === 'date' || field.type === 'number' || field.type === 'email' ? field.type : 'text'} />
      )}
      {error ? <small>{error}</small> : null}
    </label>
  )
}

function ProductionWorkspace({ data }: { data: RedazioneAttiPageData }) {
  const [modelCode, setModelCode] = useState(data.production.defaultModelCode)
  const selectedModel = useMemo(
    () => data.production.models.find((model) => model.code === modelCode) || data.production.models[0],
    [data.production.models, modelCode],
  )
  const [values, setValues] = useState<Record<string, string>>({})
  const [result, setResult] = useState<RedazioneProduceResult | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const next = selectedModel?.fields.reduce<Record<string, string>>((acc, field) => {
      acc[field.name] = field.value || ''
      return acc
    }, {}) || {}
    setValues(next)
    setResult(null)
  }, [selectedModel?.code])

  if (!selectedModel) {
    return (
      <section className="iu-redazione-production iu-od-card">
        <EmptyState title="Nessun modello produttivo disponibile" message="La pagina resta pronta appena il catalogo compilatore espone modelli utilizzabili." />
      </section>
    )
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    produceRedazioneAtto(data.production.endpoint, selectedModel.code, values)
      .then(setResult)
      .finally(() => setBusy(false))
  }

  return (
    <section className="iu-redazione-production iu-od-card">
      <div className="iu-redazione-production__head">
        <FilePenLine size={20} aria-hidden="true" />
        <div>
          <p className="iu-redazione-eyebrow">Produzione atti</p>
          <h2>Compila e controlla l'atto nella stessa pagina</h2>
          <span>{selectedModel.summary || 'Modello pronto per la compilazione guidata.'}</span>
        </div>
        <select value={selectedModel.code} onChange={(event) => setModelCode(event.target.value)} aria-label="Modello atto">
          {data.production.models.map((model) => <option value={model.code} key={model.code}>{model.title}</option>)}
        </select>
      </div>
      <div className="iu-redazione-production__grid">
        <form className="iu-redazione-production__form" onSubmit={submit}>
          {selectedModel.fields.map((field) => (
            <FieldInput
              key={`${selectedModel.code}-${field.name}`}
              field={field}
              value={values[field.name] ?? ''}
              error={result?.errors?.[field.name]}
              onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
            />
          ))}
          <button type="submit" disabled={busy}>{busy ? 'Produzione in corso...' : 'Produci anteprima'}</button>
        </form>
        <aside className="iu-redazione-production__preview">
          <div>
            <strong>{result?.title || selectedModel.title}</strong>
            <Badge tone={result?.ok ? 'success' : result ? 'warning' : 'neutral'}>
              {result?.ok ? 'Pronta' : result ? 'Da completare' : selectedModel.area || 'Bozza'}
            </Badge>
          </div>
          {result?.warnings?.length ? result.warnings.map((warning) => <p key={warning}>{warning}</p>) : null}
          <pre>{result?.preview || 'Compila i campi essenziali e produci una prima versione verificabile dell atto.'}</pre>
        </aside>
      </div>
    </section>
  )
}

export function RedazioneAttiPage() {
  const [data, setData] = useState<RedazioneAttiPageData>(emptyRedazioneAttiPage)
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    getRedazioneAttiPage()
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return <LoadingState title="Caricamento redazione atti" message="Recupero quadro operativo e template." />
  }

  return (
    <Page
      title="Redazione atti"
      subtitle="Pagina unica per scegliere template, compilare modelli reali e controllare l'anteprima dell'atto."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>
          <ButtonLink href="/template-atti/catalogo" tone="primary">
            Catalogo template
          </ButtonLink>
          <ButtonLink href="/documenti" tone="neutral">
            Documenti
          </ButtonLink>
        </>
      }
    >
      <div className="iu-redazione-page iu-od-stack">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics data={data} />
        <section className="iu-redazione-hero iu-od-surface">
          <div>
            <p className="iu-redazione-eyebrow">Percorso documentale</p>
            <h2>Ingresso governato alla redazione</h2>
            <p>
              {data.summary || 'La pagina coordina template, modelli e controlli operativi.'}
            </p>
          </div>
          <div className="iu-od-action-row iu-redazione-hero__actions">
            {data.actions.map((action) => (
              <ButtonLink key={action.id} href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'}>
                <ExternalLink size={16} aria-hidden="true" />
                {action.label}
              </ButtonLink>
            ))}
          </div>
        </section>
        <ProductionWorkspace data={data} />
        <Sections data={data} />
        <Records data={data} />
        <aside className="iu-redazione-source iu-od-meta">
          Stato collegamenti governato - aggiornato {data.generated_at || 'non indicato'}
        </aside>
      </div>
    </Page>
  )
}
