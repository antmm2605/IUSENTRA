import { useEffect, useState } from 'react'
import { ExternalLink, ReceiptText, Settings2, WalletCards } from 'lucide-react'
import {
  emptyIncassiPagamentiPage,
  getIncassiPagamentiPage,
  type IncassiPagamentiPageData,
  type IncassoPagamentoRecord,
} from '../incassiPagamentiData'
import { Badge } from '../ui/Badge'
import { ButtonLink } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { KpiCard } from '../ui/KpiCard'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './IncassiPagamentiPage.css'

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function WarningPanel({ data }: { data: IncassiPagamentiPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Avvisi pagamenti">
      <div className="iu-pay-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-pay-warning" key={`${warning.code}-${warning.message}`}>
            <Badge tone="warning">{warning.code}</Badge>
            <span>{warning.message}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ContractPanel({ data }: { data: IncassiPagamentiPageData }) {
  return (
    <Panel title="Contratto dati" subtitle="Dashboard GET senza configurazioni provider nel payload React.">
      <div className="iu-pay-contract">
        <span>Fonte: {data.source || 'non indicata'}</span>
        <span>Generato: {data.generated_at || 'non disponibile'}</span>
        <span>Scritture: {data.contracts.writes}</span>
        <span>Owner route: {data.contracts.route_owner}</span>
        <span>Mock fallback: {data.contracts.mock_fallback ? 'si' : 'no'}</span>
      </div>
    </Panel>
  )
}

function PaymentRow({ record }: { record: IncassoPagamentoRecord }) {
  return (
    <article className="iu-pay-record">
      <div className="iu-pay-record__main">
        <span>{record.invoiceNumber || record.invoiceId}</span>
        <strong>{record.customerName}</strong>
        <small>Provider: {record.providerLabel}</small>
      </div>
      <div className="iu-pay-record__dates">
        <span>Creato {record.createdAt || 'non indicato'}</span>
        <span>Scadenza {record.dueAt || 'non indicata'}</span>
        {record.paidAt ? <span>Incasso {record.paidAt}</span> : null}
      </div>
      <div className="iu-pay-record__amount">
        <strong>{record.amountDisplay || 'Importo non indicato'}</strong>
        <Badge tone={record.stateTone}>{record.stateLabel}</Badge>
      </div>
      <div className="iu-pay-record__actions">
        {record.invoiceHref ? (
          <ButtonLink href={record.invoiceHref} tone="neutral">
            <ExternalLink size={15} />
            Parcella legacy
          </ButtonLink>
        ) : null}
      </div>
    </article>
  )
}

export function IncassiPagamentiPage() {
  const [data, setData] = useState<IncassiPagamentiPageData>(emptyIncassiPagamentiPage)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getIncassiPagamentiPage()
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
      title="Incassi e pagamenti"
      subtitle="Dashboard sicura su incassi, collegamenti pagamento e stato provider senza scritture React."
      actions={
        <>
          <ButtonLink href="/fatturazione" tone="primary">
            <ReceiptText size={16} />
            Fatturazione
          </ButtonLink>
          <ButtonLink href="/impostazioni/pagamenti?_legacy=1" tone="warning">
            <Settings2 size={16} />
            Provider legacy
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento incassi" message="Lettura dei repository economici reali in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun incasso disponibile"
          message="La dashboard non ha ricevuto importi o collegamenti visualizzabili."
          action={<ButtonLink href="/impostazioni/pagamenti?_legacy=1" tone="warning">Apri provider legacy</ButtonLink>}
        />
      ) : null}
      {!loading && hasData ? (
        <>
          <section className="iu-pay-banner" aria-label="Provider legacy">
            <strong>Configurazione provider ancora legacy</strong>
            <span>React mostra solo stato e importi sicuri; credenziali, webhook e avvio incassi restano nel pannello Flask.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-pay-kpis" aria-label="KPI incassi">
            {data.metrics.map((metric) => (
              <KpiCard
                label={metric.label}
                value={displayValue(metric.value)}
                note={metric.note}
                badge={<Badge tone={metric.tone}>{metric.tone}</Badge>}
                key={metric.id}
              />
            ))}
          </section>
          <section className="iu-pay-grid" aria-label="Sezioni incassi">
            {data.sections.map((section) => (
              <Panel title={section.title} subtitle={section.kind} key={section.id}>
                {section.items.length ? (
                  <div className="iu-pay-list">
                    {section.items.map((item) => (
                      <div className="iu-pay-list__item" key={item.id}>
                        <WalletCards size={17} />
                        <span>{item.label}</span>
                        <strong>{displayValue(item.value)}</strong>
                        {item.note ? <small>{item.note}</small> : null}
                        <Badge tone={item.tone}>{item.tone}</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title={section.emptyMessage} />
                )}
              </Panel>
            ))}
          </section>
          <Panel title="Collegamenti pagamento" subtitle={`${data.records.length} record visibili dal repository pagamenti`}>
            {data.records.length ? (
              <div className="iu-pay-records">
                {data.records.map((record) => <PaymentRow record={record} key={record.id || record.invoiceId} />)}
              </div>
            ) : (
              <EmptyState title="Nessun collegamento pagamento visibile" />
            )}
          </Panel>
          <Panel title="Collegamenti rapidi">
            <div className="iu-pay-actions">
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
