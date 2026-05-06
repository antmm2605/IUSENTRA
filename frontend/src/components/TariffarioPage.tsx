import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, Scale, Search } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import { emptyTariffarioPage, getTariffarioPage, type TariffarioPageData } from '../tariffarioData'
import './TariffarioPage.css'

function ContractStrip({ data }: { data: TariffarioPageData }) {
  return (
    <aside className="iu-tar-contract iu-od-surface">
      <Scale size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {data.source || 'Sorgente non indicata'} · scritture {data.contracts.writes || 'legacy_routes'}
        </span>
      </div>
    </aside>
  )
}

function WarningList({ data }: { data: TariffarioPageData }) {
  if (!data.warnings.length) return null
  return (
    <div className="iu-tar-warnings" role="status">
      {data.warnings.map((warning) => (
        <p className="iu-tar-warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </div>
  )
}

function Metrics({ data }: { data: TariffarioPageData }) {
  if (!data.metrics.length) return null
  return (
    <section className="iu-tar-metrics" aria-label="KPI tariffario">
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

function Sections({ data }: { data: TariffarioPageData }) {
  if (!data.sections.length) return null
  return (
    <section className="iu-tar-section-grid" aria-label="Aree tariffario">
      {data.sections.map((section) => (
        <Panel title={section.title} subtitle={section.kind} key={section.id}>
          {section.items.length ? (
            <div className="iu-tar-list">
              {section.items.map((item) => (
                <div className="iu-tar-row" key={item.id}>
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

function Records({ data, query }: { data: TariffarioPageData; query: string }) {
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return data.records
    return data.records.filter((record) =>
      [record.title, record.subtitle, record.meta].some((value) => value.toLowerCase().includes(needle)),
    )
  }, [data.records, query])

  return (
    <Panel title="Voci tariffarie" subtitle="Filtro locale su dati gia' ricevuti dal backend.">
      {filtered.length ? (
        <div className="iu-tar-records">
          {filtered.map((record) => (
            <a className="iu-tar-record iu-od-focus-ring" href={record.href} key={record.id}>
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
        <EmptyState title="Nessuna voce tariffaria trovata" message="Modifica il filtro o aggiorna i dati backend." />
      )}
    </Panel>
  )
}

function Forms({ data }: { data: TariffarioPageData }) {
  if (!data.forms.length) return null
  return (
    <Panel title="Submit tariffario" subtitle="Il risultato viene calcolato dalla route Flask.">
      <div className="iu-tar-forms">
        {data.forms.map((form) => (
          <LegacyPostForm
            key={form.id}
            action={form.action}
            method={form.method}
            title={form.title}
            description={form.description}
            submitLabel={form.submitLabel}
            fields={form.fields}
            disabled={!form.enabled}
          />
        ))}
      </div>
    </Panel>
  )
}

export function TariffarioPage() {
  const [data, setData] = useState<TariffarioPageData>(emptyTariffarioPage)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')

  function load() {
    setLoading(true)
    getTariffarioPage()
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return <LoadingState title="Caricamento tariffario" message="Recupero tabelle e regole dal backend." />
  }

  return (
    <Page
      title="Tariffario"
      subtitle="Consultazione operativa delle voci e submit verso il motore backend."
      actions={
        <>
          <Button type="button" tone="neutral" onClick={load}>
            <RefreshCw size={16} aria-hidden="true" />
            Aggiorna
          </Button>
          <ButtonLink href="/compensi-forensi" tone="primary">
            <Scale size={16} aria-hidden="true" />
            Compensi
          </ButtonLink>
        </>
      }
    >
      <div className="iu-tar-page iu-od-stack">
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics data={data} />
        <section className="iu-tar-toolbar iu-od-surface">
          <label className="iu-tar-search">
            <Search size={17} aria-hidden="true" />
            <span>Cerca voce tariffaria</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Materia, grado o regola" />
          </label>
          <div className="iu-tar-actions">
            {data.actions.map((action) => (
              <ButtonLink key={action.id} href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'}>
                {action.label}
              </ButtonLink>
            ))}
          </div>
        </section>
        <Sections data={data} />
        <Records data={data} query={query} />
        <Forms data={data} />
      </div>
    </Page>
  )
}
