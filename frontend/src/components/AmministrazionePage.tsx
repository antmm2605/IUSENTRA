import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, CircleAlert, ClipboardCheck, Database, ExternalLink, FlaskConical, MonitorCheck, ShieldAlert, ShieldCheck } from 'lucide-react'
import {
  emptyAmministrazionePage,
  getAmministrazionePage,
  type AmministrazionePageData,
} from '../amministrazioneData'
import {
  emptyProductReadinessPage,
  getProductReadinessPage,
  type ProductReadinessCapability,
  type ProductReadinessPageData,
} from '../productReadinessData'
import { buttonTone, type LegacyModule, type OperationalModule } from '../studioData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import { displaySourceLabel, displayWritesLabel } from '../displayText'
import { formatDateTimeIt } from '../formatting'
import './AmministrazionePage.css'

function formatValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function WarningPanel({ data }: { data: AmministrazionePageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi">
      <div className="iu-adminhub-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-adminhub-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ModuleList({ modules, legacy = false }: { modules: Array<OperationalModule | LegacyModule>; legacy?: boolean }) {
  if (!modules.length) return <EmptyState title={legacy ? 'Nessuna area protetta' : 'Nessun modulo operativo disponibile'} />
  return (
    <div className="iu-adminhub-modules">
      {modules.map((record) => (
        <article className="iu-adminhub-module" key={record.id}>
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

function SecurityPanel({ data }: { data: AmministrazionePageData }) {
  const security = data.security
  return (
    <Panel title="Sicurezza e permessi" subtitle="Indicatori aggregati senza credenziali o dati riservati">
      <div className="iu-adminhub-security">
        <article>
          <span>Stato</span>
          <strong>{security.status || 'non indicato'}</strong>
          <Badge tone={security.tone || 'neutral'}>{security.tone || 'neutral'}</Badge>
        </article>
        <article>
          <span>Registro</span>
          <strong>{security.canReadAudit ? 'visibile' : 'permesso richiesto'}</strong>
          <Badge tone={security.canReadAudit ? 'success' : 'warning'}>audit</Badge>
        </article>
        <article>
          <span>Override permessi</span>
          <strong>{formatValue(security.permissionOverrides || 0)}</strong>
          <Badge tone={security.permissionOverrides ? 'warning' : 'success'}>RBAC</Badge>
        </article>
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: AmministrazionePageData }) {
  return (
    <Panel title="Qualita dati" subtitle="Informazioni operative, impostazioni sensibili protette.">
      <div className="iu-adminhub-contract">
        <span>Origine: {displaySourceLabel(data.source || '')}</span>
        <span>Generato: {formatDateTimeIt(data.generated_at, 'Non disponibile')}</span>
        <span>Azioni: {displayWritesLabel(data.contracts.writes || '')}</span>
        <span>Operativo: {data.contracts.operational ? 'si' : 'no'}</span>
        <span>Dati reali: {data.contracts.mock_fallback ? 'da verificare' : 'si'}</span>
      </div>
    </Panel>
  )
}

function EvidenceIcon({ kind }: { kind: string }) {
  if (kind === 'ci') return <FlaskConical size={15} aria-hidden="true" />
  if (kind === 'browser') return <MonitorCheck size={15} aria-hidden="true" />
  return <ShieldCheck size={15} aria-hidden="true" />
}

function CapabilityDetail({ capability }: { capability: ProductReadinessCapability }) {
  return (
    <details className="iu-readiness-capability">
      <summary>
        <span className="iu-readiness-capability__main">
          <strong>{capability.module}</strong>
          <small>{capability.owner} · {capability.lastSmoke.label}</small>
        </span>
        <Badge tone={capability.statusTone}>{capability.statusLabel}</Badge>
      </summary>
      <div className="iu-readiness-capability__body">
        <p className="iu-readiness-capability__note">{capability.statusNote}</p>
        <dl className="iu-readiness-capability__facts">
          <div><dt>Versione regole</dt><dd>{capability.version || 'Non disponibile'}</dd></div>
          <div><dt>Feature flag</dt><dd>{capability.featureFlag || 'Nessun flag dedicato censito'}</dd></div>
          <div><dt>Route</dt><dd><code>{capability.route || 'Da definire'}</code></dd></div>
          <div><dt>API</dt><dd><code>{capability.api || 'Da definire'}</code></dd></div>
          <div><dt>Backend</dt><dd>{capability.backend || 'Da verificare'}</dd></div>
          <div><dt>Storage</dt><dd>{capability.storage || 'Da verificare'}</dd></div>
          <div><dt>Permessi</dt><dd>{capability.permissions.join(', ') || 'Da definire'}</dd></div>
          <div><dt>Operazioni</dt><dd>{capability.operations.join(', ') || 'Da definire'}</dd></div>
          <div><dt>Locale</dt><dd>{capability.environment.local}</dd></div>
          <div><dt>Produzione</dt><dd>{capability.environment.production}</dd></div>
          <div><dt>Dipendenze</dt><dd>{capability.dependencies.join(', ') || 'Nessuna'}</dd></div>
          <div><dt>Incidenti</dt><dd>{capability.incidents.label}</dd></div>
        </dl>
        <section className="iu-readiness-evidence" aria-label={`Prove ${capability.module}`}>
          {capability.evidence.map((evidence) => (
            <article key={`${capability.id}-${evidence.kind}`}>
              <EvidenceIcon kind={evidence.kind} />
              <div>
                <span>{evidence.label}</span>
                <strong>{evidence.status}</strong>
                {evidence.reference ? <small>{evidence.reference}</small> : null}
                {evidence.lastVerified ? <small>Verificata: {formatDateTimeIt(evidence.lastVerified, 'Non disponibile')}</small> : null}
                {evidence.note ? <small>{evidence.note}</small> : null}
              </div>
            </article>
          ))}
        </section>
        <div className="iu-readiness-capability__closing">
          <p><strong>Limitazione:</strong> {capability.limitations}</p>
          <p><strong>Rollback:</strong> {capability.rollback}</p>
          <p><strong>Prossima azione:</strong> {capability.nextAction}</p>
          <p><strong>Test associati:</strong> {capability.tests.join(', ') || 'Da censire'}</p>
        </div>
      </div>
    </details>
  )
}

function ProductReadinessView({ data, loading, error }: { data: ProductReadinessPageData; loading: boolean; error: string }) {
  const hasData = data.capabilities.length > 0
  return (
    <Page
      title="Prontezza prodotto"
      subtitle="Registro P0 generato: mostra prove reali, prove mancanti e prossime azioni senza dichiarazioni promozionali."
      actions={<ButtonLink href="/amministrazione" tone="neutral"><ArrowLeft size={15} />Torna ad amministrazione</ButtonLink>}
    >
      {loading ? <LoadingState title="Caricamento prontezza prodotto" message="Lettura del catalogo di rilascio in corso." /> : null}
      {!loading && error ? <EmptyState title="Registro di prontezza non disponibile" message={error} action={<ButtonLink href="/amministrazione" tone="primary">Torna ad amministrazione</ButtonLink>} /> : null}
      {!loading && !error && !hasData ? <EmptyState title="Nessuna capability P0 disponibile" message="Il catalogo non ha restituito superfici verificabili." action={<ButtonLink href="/amministrazione" tone="primary">Torna ad amministrazione</ButtonLink>} /> : null}
      {!loading && !error && hasData ? (
        <>
          <section className="iu-readiness-banner" aria-label="Regola di verità del registro">
            <CircleAlert size={20} aria-hidden="true" />
            <div>
              <strong>{data.scope}</strong>
              <span>Una prova assente resta “da verificare”: il registro non converte il codice o un test esistente in una certificazione operativa.</span>
            </div>
          </section>
          {data.warnings.length ? (
            <Panel title="Avvisi di verità" subtitle="Condizioni che impediscono una dichiarazione di completezza">
              <div className="iu-adminhub-warnings">
                {data.warnings.map((warning) => <div className="iu-adminhub-warning" key={`${warning.code}-${warning.message}`}><Badge tone="warning">{warning.code}</Badge><span>{warning.message}</span></div>)}
              </div>
            </Panel>
          ) : null}
          <section className="iu-readiness-kpis" aria-label="Riepilogo capability P0">
            <KpiCard label="Flussi P0" value={formatValue(data.summary.total)} note="Superfici censite" badge={<Badge tone="primary">P0</Badge>} />
            <KpiCard label="Verificate" value={formatValue(data.summary.verified)} note="Con prova corrente registrata" badge={<Badge tone="success">prove</Badge>} />
            <KpiCard label="Da verificare" value={formatValue(data.summary.pending)} note="Da provare nelle golden journeys" badge={<Badge tone="warning">aperte</Badge>} />
            <KpiCard label="Bloccate" value={formatValue(data.summary.blocked)} note="Requisiti che impediscono il flusso" badge={<Badge tone="danger">blocchi</Badge>} />
          </section>
          <Panel title="Contratto del registro" subtitle={`Registro ${data.registryVersion || 'non disponibile'} · applicazione ${data.applicationVersion || 'non disponibile'}`}>
            <div className="iu-readiness-contract">
              <span><Database size={15} aria-hidden="true" />Fonte: {data.contracts.sourceOfTruth || 'Non disponibile'}</span>
              <span><ClipboardCheck size={15} aria-hidden="true" />Scritture: {data.contracts.writes || 'none'}</span>
              <span><ShieldCheck size={15} aria-hidden="true" />Provider: {data.contracts.providerCalls ? 'contattati' : 'non contattati'}</span>
              <span>Generato: {formatDateTimeIt(data.generatedAt, 'Non disponibile')}</span>
            </div>
          </Panel>
          <Panel title="Capability P0" subtitle="Apri una riga per route, API, dati, prove, limiti e rollback.">
            <div className="iu-readiness-capabilities">
              {data.capabilities.map((capability) => <CapabilityDetail capability={capability} key={capability.id} />)}
            </div>
          </Panel>
        </>
      ) : null}
    </Page>
  )
}

export function AmministrazionePage() {
  const [data, setData] = useState<AmministrazionePageData>(emptyAmministrazionePage)
  const [readiness, setReadiness] = useState<ProductReadinessPageData>(emptyProductReadinessPage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const readinessSelected = new URLSearchParams(window.location.search).get('tab') === 'prontezza-prodotto'

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    const request = readinessSelected ? getProductReadinessPage() : getAmministrazionePage()
    request
      .then((payload) => {
        if (!active) return
        if (readinessSelected) {
          const readinessPayload = payload as ProductReadinessPageData
          setReadiness(readinessPayload)
          setError(readinessPayload.ok ? '' : readinessPayload.warnings[0]?.message || 'Registro di prontezza non disponibile.')
          return
        }
        const administrationPayload = payload as AmministrazionePageData
        setData(administrationPayload)
        setError(administrationPayload.ok ? '' : administrationPayload.warnings[0]?.message || 'Pagina amministrazione non disponibile.')
      })
      .catch(() => {
        if (active) setError(readinessSelected ? 'Registro di prontezza non disponibile.' : 'Pagina amministrazione non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [readinessSelected])

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.operational_routes.length > 0 || data.sections.some((section) => section.items.length > 0),
    [data],
  )

  if (readinessSelected) return <ProductReadinessView data={readiness} loading={loading} error={error} />

  return (
    <Page
      title="Amministrazione"
      subtitle="Quadro amministrativo reale per utenti, profili, audit, sicurezza e moduli protetti."
      actions={
        <>
          <ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>
          <ButtonLink href="/profili" tone="primary">Apri profili</ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento amministrazione" message="Lettura degli archivi amministrativi in corso." /> : null}
      {!loading && error ? (
        <EmptyState title="Amministrazione non disponibile" message={error} action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>} />
      ) : null}
      {!loading && !error && !hasData ? (
        <EmptyState
          title="Nessun dato amministrativo disponibile"
          message="Il centro amministrativo non ha ricevuto dati visualizzabili dagli archivi."
          action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>}
        />
      ) : null}
      {!loading && !error && hasData ? (
        <>
          <section className="iu-adminhub-banner" aria-label="Quadro amministrativo operativo">
            <strong>Regia amministrativa operativa</strong>
            <span>Utenti, profili, audit e backup sono collegamenti operativi; le impostazioni sensibili restano presidiate.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-adminhub-kpis" aria-label="Indicatori amministrazione">
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
          <SecurityPanel data={data} />
          <Panel title="Moduli amministrativi" subtitle={`${data.operational_routes.length} funzioni operative`}>
            <ModuleList modules={data.operational_routes} />
          </Panel>
          <Panel title="Impostazioni presidiate" subtitle="Percorsi mantenuti sotto controllo amministrativo">
            <ModuleList modules={data.legacy_routes} legacy />
          </Panel>
          <section className="iu-adminhub-grid" aria-label="Sezioni amministrazione">
            {data.sections.map((section) => (
              <Panel title={section.title} subtitle={section.kind} key={section.id}>
                {section.items.length ? (
                  <div className="iu-adminhub-list">
                    {section.items.map((item) => (
                      <div className="iu-adminhub-list__item" key={item.id}>
                        <span>{item.label}</span>
                        <strong>{formatValue(item.value)}</strong>
                        {item.note ? <small>{item.note}</small> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title={section.emptyMessage} />
                )}
              </Panel>
            ))}
          </section>
          <Panel title="Collegamenti operativi">
            <div className="iu-adminhub-actions">
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
