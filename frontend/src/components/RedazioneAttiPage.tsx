import { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { openDesignContract } from '../ui/openDesign'
import { RedazioneGuidataWizard } from '../features/documenti/RedazioneGuidataWizard'
import {
  emptyRedazioneAttiPage,
  getRedazioneAttiPage,
  type RedazioneAttiPageData,
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


export function RedazioneAttiPage() {
  const [data, setData] = useState<RedazioneAttiPageData>(emptyRedazioneAttiPage)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [loadSuccess, setLoadSuccess] = useState(false)

  function load() {
    setLoading(true)
    setLoadError('')
    setLoadSuccess(false)
    getRedazioneAttiPage()
      .then((payload) => {
        setData(payload)
        setLoadSuccess(true)
      })
      .catch(() => {
        setData(emptyRedazioneAttiPage)
        setLoadError('Redazione atti non disponibile: aggiorna la pagina o riprova tra poco.')
      })
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
        {loadError ? (
          <p className="iu-redazione-warning iu-od-warning" role="alert">
            {loadError}
          </p>
        ) : null}
        {loadSuccess ? (
          <p className="iu-redazione-warning iu-od-success" role="status">
            Aggiornamento riuscito: dati della redazione caricati dal tenant corrente.
          </p>
        ) : null}
        <WarningList data={data} />
        <RedazioneGuidataWizard />
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
        <Sections data={data} />
        <Records data={data} />
        <aside className="iu-redazione-source iu-od-meta">
          Stato collegamenti governato - aggiornato {data.generated_at || 'non indicato'}
        </aside>
      </div>
    </Page>
  )
}
