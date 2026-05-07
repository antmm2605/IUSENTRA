import { useEffect, useState } from 'react'
import { ExternalLink, Link2, ReceiptText, RefreshCw, WalletCards } from 'lucide-react'
import {
  createOrGetPaymentLink,
  emptyIncassiPagamentiPage,
  getIncassiPagamentiPage,
  registerIncasso,
  updatePagamentoStatus,
  type IncassiPagamentiPageData,
  type IncassoPagamentoRecord,
} from '../incassiPagamentiData'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
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

function PaymentRow({
  record,
  canUpdateStatus,
  canGeneratePaymentLink,
  onMarkPaid,
  onMarkFailed,
  onPaymentLink,
}: {
  record: IncassoPagamentoRecord
  canUpdateStatus: boolean
  canGeneratePaymentLink: boolean
  onMarkPaid: (record: IncassoPagamentoRecord) => void
  onMarkFailed: (record: IncassoPagamentoRecord) => void
  onPaymentLink: (record: IncassoPagamentoRecord) => void
}) {
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
        {canUpdateStatus && record.state !== 'PAGATO' ? (
          <Button type="button" tone="success" onClick={() => onMarkPaid(record)}>
            <ReceiptText size={15} />
            Segna pagato
          </Button>
        ) : null}
        {canUpdateStatus && record.state === 'ATTESO' ? (
          <Button type="button" tone="warning" onClick={() => onMarkFailed(record)}>
            <RefreshCw size={15} />
            Fallito
          </Button>
        ) : null}
        {canGeneratePaymentLink && record.invoiceId ? (
          <Button type="button" tone="neutral" onClick={() => onPaymentLink(record)}>
            <Link2 size={15} />
            Link pagamento
          </Button>
        ) : null}
        {record.paymentHref ? (
          <ButtonLink href={record.paymentHref} tone="neutral">
            <ExternalLink size={15} />
            Apri link
          </ButtonLink>
        ) : null}
        {record.invoiceHref ? (
          <ButtonLink href={record.invoiceHref} tone="neutral">
            <ExternalLink size={15} />
            Parcella
          </ButtonLink>
        ) : null}
      </div>
    </article>
  )
}

export function IncassiPagamentiPage() {
  const [data, setData] = useState<IncassiPagamentiPageData>(emptyIncassiPagamentiPage)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')
  const [invoiceId, setInvoiceId] = useState('')
  const [method, setMethod] = useState('manuale')
  const [paidAt, setPaidAt] = useState(new Date().toISOString().slice(0, 10))

  function load() {
    setLoading(true)
    getIncassiPagamentiPage()
      .then((payload) => {
        setData(payload)
        if (!invoiceId && payload.records[0]?.invoiceId) setInvoiceId(payload.records[0].invoiceId)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    let active = true
    getIncassiPagamentiPage()
      .then((payload) => {
        if (active) {
          setData(payload)
          if (!invoiceId && payload.records[0]?.invoiceId) setInvoiceId(payload.records[0].invoiceId)
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  async function submitManualReceipt() {
    setSaving(true)
    setSuccess('')
    setError('')
    const response = await registerIncasso({
      id_parcella: invoiceId,
      metodo_pagamento: method,
      data_pagamento: paidAt,
    })
    setSaving(false)
    if (!response.ok) {
      setError(response.message)
      return
    }
    setSuccess(response.message)
    load()
  }

  async function mark(record: IncassoPagamentoRecord, stato: string) {
    setSaving(true)
    setSuccess('')
    setError('')
    const response = await updatePagamentoStatus(record.id, { stato, metodo_pagamento: method })
    setSaving(false)
    if (!response.ok) {
      setError(response.message)
      return
    }
    setSuccess(response.message)
    load()
  }

  async function paymentLink(record: IncassoPagamentoRecord) {
    setSaving(true)
    setSuccess('')
    setError('')
    const response = await createOrGetPaymentLink(record.id, { id_parcella: record.invoiceId })
    setSaving(false)
    if (!response.ok) {
      setError(response.message)
      return
    }
    setSuccess(response.message)
    load()
  }

  const hasData = data.metrics.length > 0 || data.records.length > 0 || data.sections.some((section) => section.items.length > 0)

  return (
    <Page
      title="Incassi e pagamenti"
      subtitle="Dashboard operativa su incassi, collegamenti pagamento e stato provider sicuro."
      actions={
        <>
          <ButtonLink href="/fatturazione" tone="primary">
            <ReceiptText size={16} />
            Fatturazione
          </ButtonLink>
        </>
      }
    >
      {loading ? <LoadingState title="Caricamento incassi" message="Lettura dei repository economici reali in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun incasso disponibile"
          message="La dashboard non ha ricevuto importi o collegamenti visualizzabili."
        />
      ) : null}
      {!loading && hasData ? (
        <>
          {saving ? <LoadingState title="Salvataggio incasso" message="Invio sicuro al backend JSON in corso." /> : null}
          {success ? <div className="iu-pay-alert iu-pay-alert--success" role="status">{success}</div> : null}
          {error ? <div className="iu-pay-alert iu-pay-alert--error" role="alert">{error}</div> : null}
          <section className="iu-pay-banner" aria-label="Provider legacy">
            <strong>Configurazione provider ancora legacy</strong>
            <span>React mostra solo stato e importi sicuri; configurazioni riservate e webhook restano nel pannello Flask.</span>
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
          <Panel title="Registra incasso manuale" subtitle="Scrittura JSON backend con permessi e CSRF della sessione.">
            {data.actions.canRegisterPayment ? (
              <div className="iu-pay-form">
                <label>
                  <span>Parcella</span>
                  <select value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)}>
                    <option value="">Seleziona parcella</option>
                    {data.records.map((record) => (
                      <option value={record.invoiceId} key={`${record.id}-${record.invoiceId}`}>
                        {record.invoiceNumber || record.invoiceId} - {record.customerName}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Metodo</span>
                  <input value={method} onChange={(event) => setMethod(event.target.value)} />
                </label>
                <label>
                  <span>Data incasso</span>
                  <input type="date" value={paidAt} onChange={(event) => setPaidAt(event.target.value)} />
                </label>
                <Button type="button" tone="primary" onClick={submitManualReceipt} disabled={saving || !invoiceId}>
                  <ReceiptText size={16} />
                  Registra incasso
                </Button>
              </div>
            ) : (
              <EmptyState title="Permesso non disponibile" message="Il backend non consente registrazioni incasso per questa sessione." />
            )}
          </Panel>
          <Panel title="Collegamenti pagamento" subtitle={`${data.records.length} record visibili dal repository pagamenti`}>
            {data.records.length ? (
              <div className="iu-pay-records">
                {data.records.map((record) => (
                  <PaymentRow
                    record={record}
                    canUpdateStatus={data.actions.canUpdateStatus}
                    canGeneratePaymentLink={data.actions.canGeneratePaymentLink}
                    onMarkPaid={(item) => mark(item, 'PAGATO')}
                    onMarkFailed={(item) => mark(item, 'FALLITO')}
                    onPaymentLink={paymentLink}
                    key={record.id || record.invoiceId}
                  />
                ))}
              </div>
            ) : (
              <EmptyState title="Nessun collegamento pagamento visibile" />
            )}
          </Panel>
          <Panel title="Collegamenti rapidi">
            <div className="iu-pay-actions">
              {data.actions.links.map((action) => (
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
