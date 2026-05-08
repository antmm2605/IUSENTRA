import { useEffect, useState } from 'react'
import { ExternalLink, FilePenLine, RefreshCw, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import { emptyRedazioneAttiPage, getRedazioneAttiPage, type RedazioneAttiPageData } from '../redazioneAttiData'
import './RedazioneAttiPage.css'

function ContractStrip({ data }: { data: RedazioneAttiPageData }) {
  return (
    <aside className="iu-redazione-contract iu-od-surface">
      <ShieldCheck size={18} aria-hidden="true" />
      <div>
        <strong>{openDesignContract.system}</strong>
        <span>
          {data.source || 'Sorgente non indicata'} - scritture {data.contracts.writes || 'none'}
        </span>
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
    <section className="iu-redazione-metrics" aria-label="KPI redazione atti">
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
    <section className="iu-redazione-section-grid" aria-label="Workflow redazione">
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
    <Panel title="Punti operativi" subtitle="Link reali verso superfici React o percorsi Flask dedicati.">
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
          message="La pagina resta neutra finche' il backend non fornisce collegamenti consultabili."
        />
      )}
    </Panel>
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
    return <LoadingState title="Caricamento redazione atti" message="Recupero quadro operativo e metadati dal backend." />
  }

  return (
    <Page
      title="Redazione atti"
      subtitle="Quadro operativo controllato per scegliere template, fascicoli e checklist senza spostare i workflow sensibili."
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
            <p className="iu-redazione-eyebrow">Workflow documentale</p>
            <h2>Ingresso governato alla redazione</h2>
            <p>
              {data.summary || "React coordina metadati e collegamenti operativi. I passaggi completi restano nei percorsi Flask gia' auditati."}
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
        <Sections data={data} />
        <section className="iu-redazione-guard iu-od-card">
          <FilePenLine size={20} aria-hidden="true" />
          <div>
            <h2>Produzione atti non spostata in React</h2>
            <p>
              Questa superficie non apre editor, non compila modelli e non crea file. Le azioni sensibili restano sui
              percorsi Flask con controlli, audit e revisione umana.
            </p>
          </div>
        </section>
        <Records data={data} />
        <aside className="iu-redazione-source iu-od-meta">
          Contratto: {data.contracts.legacy_contract || 'non indicato'} - aggiornato {data.generated_at || 'non indicato'}
        </aside>
      </div>
    </Page>
  )
}
