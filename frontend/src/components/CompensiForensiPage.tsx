import { useEffect, useState } from 'react'
import { Banknote, ExternalLink, RefreshCw, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LegacyPostForm } from '../ui/LegacyPostForm'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import { emptyCompensiForensiPage, getCompensiForensiPage, type CompensiForensiPageData } from '../compensiForensiData'
import './CompensiForensiPage.css'

function ContractStrip({ data }: { data: CompensiForensiPageData }) {
  return (
    <aside className="iu-comp-contract iu-od-surface">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {data.source || 'Sorgente non indicata'} · scritture {data.contracts.writes || 'legacy_routes'}
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
    <section className="iu-comp-metrics" aria-label="KPI compensi forensi">
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
        <Panel title={section.title} subtitle={section.kind} key={section.id}>
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

function Records({ data }: { data: CompensiForensiPageData }) {
  return (
    <Panel title="Profili e regole disponibili" subtitle="Solo dati gia' esposti dal backend.">
      {data.records.length ? (
        <div className="iu-comp-records">
          {data.records.map((record) => (
            <a className="iu-comp-record iu-od-focus-ring" href={record.href} key={record.id}>
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
          title="Nessun profilo tariffario esposto"
          message="La pagina resta neutra finche' il backend non fornisce elementi consultabili."
        />
      )}
    </Panel>
  )
}

function Forms({ data }: { data: CompensiForensiPageData }) {
  if (!data.forms.length) return null
  return (
    <Panel title="Form operativi" subtitle="Submit HTML standard verso Flask.">
      <div className="iu-comp-forms">
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

export function CompensiForensiPage() {
  const [data, setData] = useState<CompensiForensiPageData>(emptyCompensiForensiPage)
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    getCompensiForensiPage()
      .then(setData)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return <LoadingState title="Caricamento compensi forensi" message="Recupero i dati reali dal backend." />
  }

  return (
    <Page
      title="Compensi forensi"
      subtitle="Dashboard operativa di accesso al motore economico dello studio."
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
        <ContractStrip data={data} />
        <WarningList data={data} />
        <Metrics data={data} />
        <section className="iu-comp-hero iu-od-surface">
          <div>
            <p className="iu-comp-eyebrow">Mandato e parametri forensi</p>
            <h2>Accesso controllato alle funzioni economiche</h2>
            <p>
              React mostra archivio, aree disponibili e link operativi. Il motore economico rimane nella route Flask
              gia' auditata.
            </p>
          </div>
          <div className="iu-comp-actions">
            {data.actions.map((action) => (
              <ButtonLink key={action.id} href={action.href} tone={action.tone === 'primary' ? 'primary' : 'neutral'}>
                <ExternalLink size={16} aria-hidden="true" />
                {action.label}
              </ButtonLink>
            ))}
          </div>
        </section>
        <Sections data={data} />
        <Records data={data} />
        <Forms data={data} />
      </div>
    </Page>
  )
}
