import { useEffect, useState } from 'react'
import { BookOpen, BriefcaseBusiness, FileText, RefreshCw, Sparkles } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { RedazioneGuidataWizard } from '../features/documenti/RedazioneGuidataWizard'
import {
  emptyRedazioneAttiPage,
  getRedazioneAttiPage,
  type RedazioneAttiPageData,
} from '../redazioneAttiData'
import './RedazioneAttiPage.css'

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
  const count = (id: string) => data.metrics.find(metric => metric.id === id)?.value ?? '—'
  function focusWizard() {
    const wizard = document.getElementById('redazione-guidata')
    wizard?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    wizard?.focus({ preventScroll: true })
  }
  return (
    <section className="iu-redazione-metrics" aria-label="Azioni della redazione">
      <KpiCard label="Modelli dello studio" value={count('template')} note="Scegli un modello da compilare" href="/template-atti/catalogo?scope=studio" icon={BookOpen} actionLabel="Mostra modelli" />
      <KpiCard label="Redazione guidata" value="Compila" note="Cliente, fascicolo e tipo di atto" onClick={focusWizard} icon={Sparkles} actionLabel="Vai al percorso" />
      <KpiCard label="Fascicoli" value={count('fascicoli')} note="Fascicoli non archiviati" href="/fascicoli?vista=operativa&status=tutti" icon={BriefcaseBusiness} actionLabel="Apri fascicoli" />
      <KpiCard label="Preventivi" value={count('preventivi')} note="Preventivi registrati nello studio" href="/preventivi?metric=preventivi_totali" icon={FileText} actionLabel="Apri preventivi" />
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

  function load() {
    setLoading(true)
    setLoadError('')
    getRedazioneAttiPage()
      .then((payload) => {
        setData(payload)
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
      className="iu-redazione-compact-page"
      title="Redazione atti"
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
          {data.actions.filter((action, index, actions) =>
            !['/template-atti/catalogo', '/documenti', '/redazione-atti', '/fascicoli', '/preventivi'].includes(action.href)
            && actions.findIndex(candidate => candidate.href === action.href) === index,
          ).map(action => <ButtonLink key={action.id} href={action.href} tone="neutral">{action.label}</ButtonLink>)}
        </>
      }
    >
      <div className="iu-redazione-page iu-od-stack">
        {loadError ? (
          <p className="iu-redazione-warning iu-od-warning" role="alert">
            {loadError}
          </p>
        ) : null}
        <WarningList data={data} />
        <Metrics data={data} />
        <div id="redazione-guidata" tabIndex={-1}><RedazioneGuidataWizard /></div>
        <Records data={data} />
        <aside className="iu-redazione-source iu-od-meta">
          Stato collegamenti governato - aggiornato {data.generated_at || 'non indicato'}
        </aside>
      </div>
    </Page>
  )
}
