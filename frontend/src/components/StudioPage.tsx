import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpenCheck,
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
import { Button, ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { operationalDomains } from '../operationalRefresh'
import './StudioPage.css'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
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

function ProfessionalEditorPanel() {
  return (
    <Panel title="Editor professionale" subtitle="Redazione, lettura firmati e ricerca documentale sempre raggiungibili dallo Studio.">
      <div className="iu-studio-editor">
        <article className="iu-studio-editor__lead">
          <div className="iu-studio-editor__icon"><PenLine size={20} /></div>
          <div>
            <strong>Scrivi, correggi e controlla gli atti dello studio</strong>
            <span>Apri il workspace di redazione, richiama Lex e visualizza PDF firmati senza uscire dal lavoro operativo.</span>
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
  const [context, setContext] = useState('')
  const contextPanelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (context) contextPanelRef.current?.scrollIntoView({ block: 'nearest', behavior: 'auto' })
  }, [context])
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState('')
  const refreshFlight = useRef<Promise<void> | null>(null)
  function refresh(): Promise<void> {
    if (refreshFlight.current) return refreshFlight.current
    setRefreshing(true)
    const flight = (async () => {
      try {
        const payload = await getStudioPage()
        if (!payload.ok) throw new Error('Dati non disponibili')
        setData(payload); setError(''); setRefreshError('')
      } catch { setRefreshError('Aggiornamento non riuscito. Il contesto resta conservato: riprova.') }
      finally { setRefreshing(false); refreshFlight.current = null }
    })()
    refreshFlight.current = flight
    return flight
  }
  useOperationalRefresh(operationalDomains, refresh)
  const destinations: Record<string, string> = { clienti: '/clienti', utenti: '/utenti?stato=attivi', backup: '/backup' }
  const healthDestinations: Record<string, string> = { backup: '/backup', sito: '/sito-studio/contatti', utenti: '/profili', registro: '/audit' }


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
          <Button type="button" tone="neutral" disabled={loading || refreshing} onClick={refresh}>{refreshing ? 'Aggiornamento…' : 'Aggiorna'}</Button>
          <ButtonLink href="/backup" tone="primary">Apri backup</ButtonLink>
          <ButtonLink href="/sito-studio/contatti" tone="primary">Contatti sito</ButtonLink>
        </>
      }
    >
      {refreshing ? <p role="status">Aggiornamento dei dati in corso.</p> : null}
      {refreshError ? <p role="alert">{refreshError}<Button type="button" tone="neutral" onClick={refresh}>Riprova</Button></p> : null}
      {data.warnings.filter(warning => /non_disponibile|assente/.test(warning.code)).map(warning => <p role="alert" key={warning.code}>{warning.message}</p>)}
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
          <section className="iu-studio-kpis" aria-label="Indicatori studio">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={formatValue(metric.value)}
                note={metric.note}
                key={metric.id}
                href={destinations[metric.id]}
                onClick={destinations[metric.id] ? undefined : () => setContext(current => current === metric.id ? '' : metric.id)}
                active={context === metric.id}
                actionLabel={destinations[metric.id] ? 'Apri elenco' : 'Apri riepilogo'}
              />
            ))}
          </section>
          {context ? <div ref={contextPanelRef}><Panel title={data.metrics.find(metric => metric.id === context)?.label || 'Riepilogo'} actions={<Button type="button" tone="neutral" onClick={() => setContext('')}>Azzera filtro</Button>}>
            <div className="iu-studio-context" aria-label="Risultati del riepilogo selezionato">{(data.metricContexts[context] || []).map(metric => <KpiCard key={metric.id} label={metric.label} value={formatValue(metric.value)} note={metric.note} href={metric.href} actionLabel="Apri elenco" />)}</div>
          </Panel></div> : null}
          <Panel title="Salute sistema" subtitle={`${data.health.length} presidi verificati`}>
            <div className="iu-studio-health">
              {data.health.map(item => {
                const content = <><div><span>{item.label}</span><strong>{item.status}</strong>{item.note ? <small>{item.note}</small> : null}</div>{item.value !== '' ? <Badge tone={item.tone}>{formatValue(item.value)}</Badge> : null}<em className="iu-studio-health__action">Verifica presidio →</em></>
                return healthDestinations[item.id]
                  ? <a className="iu-studio-health__item" key={item.id} href={healthDestinations[item.id]} aria-label={`Verifica ${item.label}`}>{content}</a>
                  : <button className="iu-studio-health__item" key={item.id} type="button" onClick={() => setContext(item.id === 'documentale' ? 'scadenze' : 'economico')} aria-label={`Verifica ${item.label}`}>{content}</button>
              })}
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
        </>
      ) : null}
    </Page>
  )
}
