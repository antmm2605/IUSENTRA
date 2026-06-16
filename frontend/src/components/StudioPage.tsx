import { useEffect, useMemo, useState } from 'react'
import {
  BookOpenCheck,
  Building2,
  ExternalLink,
  FileSearch,
  FileText,
  PenLine,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import {
  buttonTone,
  emptyStudioPage,
  getStudioPage,
  type LegacyModule,
  type OperationalModule,
  type StudioPageData,
} from '../studioData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './StudioPage.css'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function WarningPanel({ data }: { data: StudioPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi">
      <div className="iu-studio-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-studio-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">Avviso</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ModuleList({ modules, legacy = false }: { modules: Array<OperationalModule | LegacyModule>; legacy?: boolean }) {
  if (!modules.length) return <EmptyState title={legacy ? 'Nessun modulo protetto' : 'Nessun modulo operativo disponibile'} />
  return (
    <div className="iu-studio-modules">
      {modules.map((record) => (
        <article className="iu-studio-module" key={record.id}>
          <div>
            {legacy ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />}
            <strong>{record.label}</strong>
            <span>{record.note}</span>
          </div>
          <Badge tone={record.tone}>{record.status}</Badge>
          <ButtonLink href={record.href} tone={legacy ? 'warning' : 'neutral'}>
            <ExternalLink size={15} />
            Apri
          </ButtonLink>
        </article>
      ))}
    </div>
  )
}

function ContractPanel({ data }: { data: StudioPageData }) {
  return (
    <Panel title="Presidio dati" subtitle="Consultazione operativa con impostazioni sensibili protette.">
      <div className="iu-studio-contract">
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Consultazione: {data.contracts.operational ? 'attiva' : 'non disponibile'}</span>
        <span>Impostazioni sensibili: protette</span>
      </div>
    </Panel>
  )
}

function ProfessionalEditorPanel() {
  return (
    <Panel title="Editor professionale" subtitle="Redazione, lettura firmati e ricerca documentale sempre raggiungibili dallo Studio.">
      <div className="iu-studio-editor">
        <article className="iu-studio-editor__lead">
          <div className="iu-studio-editor__icon"><PenLine size={20} /></div>
          <div>
            <strong>Scrivi, correggi e controlla gli atti dello studio</strong>
            <span>Apri il workspace di redazione, richiama Lex e visualizza PDF firmati CAdES senza uscire dal lavoro operativo.</span>
          </div>
        </article>
        <div className="iu-studio-editor__actions" aria-label="Azioni editor professionale">
          <ButtonLink href="/editor-professionale" tone="primary"><PenLine size={15} /> Apri editor</ButtonLink>
          <ButtonLink href="/redazione-atti" tone="neutral"><PenLine size={15} /> Redazione atti</ButtonLink>
          <ButtonLink href="/template-atti/catalogo" tone="neutral"><BookOpenCheck size={15} /> Modelli atti</ButtonLink>
          <ButtonLink href="/global-search?tipo=documenti" tone="neutral"><FileSearch size={15} /> Cerca documenti</ButtonLink>
          <ButtonLink href="/fascicoli" tone="neutral"><FileText size={15} /> Documenti fascicolo</ButtonLink>
          <ButtonLink href="#lex" tone="neutral" data-lex-open data-lex-context="editor-professionale"><Sparkles size={15} /> Lex editor</ButtonLink>
        </div>
      </div>
    </Panel>
  )
}

export function StudioPage() {
  const [data, setData] = useState<StudioPageData>(emptyStudioPage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getStudioPage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setError(payload.ok ? '' : payload.warnings[0]?.message || 'Pagina Studio non disponibile.')
      })
      .catch(() => {
        if (active) setError('Pagina Studio non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.operational_routes.length > 0 || data.health.length > 0,
    [data],
  )

  return (
    <Page
      title={data.studio.name || 'Studio'}
      subtitle="Regia operativa dello studio con dati reali aggregati, permessi e presidi di sicurezza."
      actions={
        <>
          <ButtonLink href="/backup" tone="primary">Apri backup</ButtonLink>
          <ButtonLink href="/sito-studio/contatti" tone="primary">Contatti sito</ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento studio" message="Lettura degli archivi reali in corso." /> : null}
      {!loading && error ? (
        <EmptyState title="Studio non disponibile" message={error} action={<ButtonLink href="/backup" tone="primary">Apri backup</ButtonLink>} />
      ) : null}
      {!loading && !error && !hasData ? (
        <EmptyState
          title="Nessun dato studio disponibile"
          message="Il centro studio non ha ricevuto aggregati visualizzabili dagli archivi."
          action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>}
        />
      ) : null}
      {!loading && !error && hasData ? (
        <>
          <section className="iu-studio-banner" aria-label="Impostazioni sensibili presidiate">
            <strong>Impostazioni sensibili presidiate</strong>
            <span>PEC, firma digitale, calendari, pagamenti e telematico restano nei percorsi protetti.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-studio-kpis" aria-label="Indicatori studio">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={formatValue(metric.value)}
                note={metric.note}
                badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <Panel title="Salute sistema" subtitle={`${data.health.length} presidi verificati`}>
            <div className="iu-studio-health">
              {data.health.map((item) => (
                <article className="iu-studio-health__item" key={item.id}>
                  <Building2 size={18} />
                  <div>
                    <span>{item.label}</span>
                    <strong>{item.status}</strong>
                    {item.note ? <small>{item.note}</small> : null}
                  </div>
                  <Badge tone={item.tone}>{formatValue(item.value) || item.tone}</Badge>
                </article>
              ))}
            </div>
          </Panel>
          <ProfessionalEditorPanel />
          <Panel title="Moduli operativi" subtitle={`${data.operational_routes.length} percorsi pronti`}>
            <ModuleList modules={data.operational_routes} />
          </Panel>
          <Panel title="Impostazioni sensibili presidiate" subtitle="Percorsi protetti, non usati come azione primaria">
            <ModuleList modules={data.legacy_routes} legacy />
          </Panel>
          <Panel title="Collegamenti operativi">
            <div className="iu-studio-actions">
              {data.actions.map((action) => (
                <ButtonLink href={action.href} tone={buttonTone(action.tone)} key={action.id}>
                  <ExternalLink size={15} />
                  {action.label}
                </ButtonLink>
              ))}
            </div>
          </Panel>
          <ContractPanel data={data} />
        </>
      ) : null}
    </Page>
  )
}
