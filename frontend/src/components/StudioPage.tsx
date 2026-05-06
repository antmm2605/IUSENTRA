import { useEffect, useState } from 'react'
import { Building2, ExternalLink, Settings2 } from 'lucide-react'
import { emptyStudioPage, getStudioPage, type StudioPageData } from '../studioData'
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
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: StudioPageData }) {
  return (
    <Panel title="Contratto dati" subtitle="GET React con scritture conservate sui percorsi legacy.">
      <div className="iu-studio-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
}

export function StudioPage() {
  const [data, setData] = useState<StudioPageData>(emptyStudioPage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getStudioPage()
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
      title={data.studio.name || 'Studio'}
      subtitle="Quadro direzionale dello studio con soli dati sicuri e collegamenti operativi."
      actions={
        <ButtonLink href="/impostazioni?_legacy=1" tone="warning">
          <Settings2 size={16} />
          Impostazioni legacy
        </ButtonLink>
      }
    >
      {loading ? <LoadingState title="Caricamento studio" message="Lettura dei repository reali in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun dato studio disponibile"
          message="Lo hub non ha ricevuto dati visualizzabili dai repository."
          action={<ButtonLink href="/impostazioni?_legacy=1" tone="warning">Apri impostazioni legacy</ButtonLink>}
        />
      ) : null}
      {!loading && hasData ? (
        <>
          <section className="iu-studio-banner" aria-label="Impostazioni sensibili ancora legacy">
            <strong>Impostazioni sensibili ancora legacy</strong>
            <span>Configurazioni riservate, calendari e pagamenti restano sui template Flask auditati.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-studio-kpis" aria-label="KPI studio">
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
          <Panel title="Moduli operativi" subtitle={`${data.records.length} collegamenti governati`}>
            <div className="iu-studio-modules">
              {data.records.map((record) => (
                <article className="iu-studio-module" key={record.id}>
                  <div>
                    <Building2 size={18} />
                    <strong>{record.label}</strong>
                    <span>{record.note}</span>
                  </div>
                  <Badge tone={record.tone}>{record.status}</Badge>
                  <ButtonLink href={record.href} tone={record.tone === 'warning' ? 'warning' : 'neutral'}>
                    <ExternalLink size={15} />
                    Apri
                  </ButtonLink>
                </article>
              ))}
            </div>
          </Panel>
          <section className="iu-studio-grid" aria-label="Sezioni studio">
            {data.sections.map((section) => (
              <Panel title={section.title} subtitle={section.kind} key={section.id}>
                {section.items.length ? (
                  <div className="iu-studio-list">
                    {section.items.map((item) => (
                      <div className="iu-studio-list__item" key={item.id}>
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
            <div className="iu-studio-actions">
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
