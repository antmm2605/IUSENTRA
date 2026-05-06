import { useEffect, useState } from 'react'
import { ExternalLink, ShieldCheck } from 'lucide-react'
import {
  emptyAmministrazionePage,
  getAmministrazionePage,
  type AmministrazionePageData,
} from '../amministrazioneData'
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

function ContractPanel({ data }: { data: AmministrazionePageData }) {
  return (
    <Panel title="Contratto dati" subtitle="GET React con operazioni conservate sui percorsi legacy.">
      <div className="iu-adminhub-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
}

export function AmministrazionePage() {
  const [data, setData] = useState<AmministrazionePageData>(emptyAmministrazionePage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getAmministrazionePage()
      .then((payload) => {
        if (active) setData(payload)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const hasData = data.metrics.length > 0 || data.records.length > 0 || data.sections.some((section) => section.items.length > 0)

  return (
    <Page
      title="Amministrazione"
      subtitle="Quadro amministrativo con metriche utenti, profili, audit, permessi e sicurezza aggregata."
      actions={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>}
    >
      {loading ? <LoadingState title="Caricamento amministrazione" message="Lettura dei repository amministrativi in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun dato amministrativo disponibile"
          message="Lo hub non ha ricevuto dati visualizzabili dai repository."
          action={<ButtonLink href="/utenti" tone="primary">Apri utenti</ButtonLink>}
        />
      ) : null}
      {!loading && hasData ? (
        <>
          <section className="iu-adminhub-banner" aria-label="Quadro amministrativo sicuro">
            <strong>Quadro amministrativo sicuro</strong>
            <span>Le modifiche restano sui percorsi legacy auditati; qui sono esposti solo aggregati e collegamenti.</span>
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
          <Panel title="Superfici amministrative" subtitle={`${data.records.length} collegamenti governati`}>
            <div className="iu-adminhub-modules">
              {data.records.map((record) => (
                <article className="iu-adminhub-module" key={record.id}>
                  <div>
                    <ShieldCheck size={18} />
                    <strong>{record.label}</strong>
                    <span>{record.note}</span>
                  </div>
                  <Badge tone={record.tone}>{record.status}</Badge>
                  <ButtonLink href={record.href} tone="neutral">
                    <ExternalLink size={15} />
                    Apri
                  </ButtonLink>
                </article>
              ))}
            </div>
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
          <Panel title="Collegamenti rapidi">
            <div className="iu-adminhub-actions">
              {data.actions.map((action) => (
                <ButtonLink href={action.href} tone={action.tone === 'info' ? 'neutral' : action.tone} key={action.id}>
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
