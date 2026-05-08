import { useEffect, useMemo, useState } from 'react'
import { ExternalLink, ShieldAlert, ShieldCheck } from 'lucide-react'
import {
  emptyAmministrazionePage,
  getAmministrazionePage,
  type AmministrazionePageData,
} from '../amministrazioneData'
import { buttonTone, type LegacyModule, type OperationalModule } from '../studioData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
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
  if (!modules.length) return <EmptyState title={legacy ? 'Nessuna area legacy protetta' : 'Nessun modulo operativo disponibile'} />
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
          <span>Audit</span>
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
    <Panel title="Contratto dati" subtitle="GET JSON read-only con impostazioni sensibili protette.">
      <div className="iu-adminhub-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Operativo: {data.contracts.operational ? 'si' : 'no'}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
}

export function AmministrazionePage() {
  const [data, setData] = useState<AmministrazionePageData>(emptyAmministrazionePage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    getAmministrazionePage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setError(payload.ok ? '' : payload.warnings[0]?.message || 'Dashboard amministrazione non disponibile.')
      })
      .catch(() => {
        if (active) setError('Dashboard amministrazione non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const hasData = useMemo(
    () => data.metrics.length > 0 || data.operational_routes.length > 0 || data.sections.some((section) => section.items.length > 0),
    [data],
  )

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
      {loading ? <LoadingState title="Caricamento amministrazione" message="Lettura dei repository amministrativi in corso." /> : null}
      {!loading && error ? (
        <EmptyState title="Amministrazione non disponibile" message={error} action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>} />
      ) : null}
      {!loading && !error && !hasData ? (
        <EmptyState
          title="Nessun dato amministrativo disponibile"
          message="Lo hub non ha ricevuto dati visualizzabili dai repository."
          action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>}
        />
      ) : null}
      {!loading && !error && hasData ? (
        <>
          <section className="iu-adminhub-banner" aria-label="Quadro amministrativo operativo">
            <strong>Regia amministrativa React</strong>
            <span>Utenti, profili, audit e backup sono collegamenti operativi; impostazioni sensibili restano legacy protette.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-adminhub-kpis" aria-label="KPI amministrazione">
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
          <Panel title="Moduli amministrativi React" subtitle={`${data.operational_routes.length} route operative full`}>
            <ModuleList modules={data.operational_routes} />
          </Panel>
          <Panel title="Impostazioni legacy protette" subtitle="Percorsi non sbloccati da questa tranche">
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
