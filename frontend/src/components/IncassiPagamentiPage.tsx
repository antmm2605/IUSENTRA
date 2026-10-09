import { useEffect, useRef, useState } from 'react'
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
import { IncassiCardCatalog } from './IncassiCardCatalog'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { formatDateIt } from '../formatting'
import { LoadingState } from '../ui/LoadingState'
import { Page } from '../ui/Page'
import { Panel } from '../ui/Panel'
import './IncassiPagamentiPage.css'

function displayValue(value: string | number): string {
  if (typeof value === 'number') return new Intl.NumberFormat('it-IT').format(value)
  return value
}

function selectedInvoiceFromLocation(): string {
  const params = new URLSearchParams(window.location.search)
  return params.get('id_parcella') || ''
}

function WarningPanel({ data }: { data: IncassiPagamentiPageData }) {
  if (!data.warnings.length) return null
  return (
    <Panel title="Da verificare">
      <div className="iu-pay-warnings">
        {data.warnings.map((warning) => (
          <div className="iu-pay-warning" key={`${warning.code}-${warning.message}`}>
            <span>{warning.message}</span>
          </div>
        ))}
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
  onRegisterReceipt,
}: {
  record: IncassoPagamentoRecord
  canUpdateStatus: boolean
  canGeneratePaymentLink: boolean
  onMarkPaid: (record: IncassoPagamentoRecord) => void
  onMarkFailed: (record: IncassoPagamentoRecord) => void
  onPaymentLink: (record: IncassoPagamentoRecord) => void
  onRegisterReceipt: (record: IncassoPagamentoRecord) => void
}) {
  return (
    <article className="iu-pay-record">
      <div className="iu-pay-record__main">
        <span>{record.invoiceNumber || record.invoiceId}</span>
        <strong>{record.customerName}</strong>
        <small>Canale: {record.providerLabel}</small>
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
        {canUpdateStatus && record.id && record.state !== 'PAGATO' ? (
          <Button type="button" tone="success" onClick={() => onMarkPaid(record)}>
            <ReceiptText size={15} />
            Segna pagato
          </Button>
        ) : null}
        {canUpdateStatus && !record.id && record.invoiceId && record.state !== 'PAGATO' ? (
          <Button type="button" tone="success" onClick={() => onRegisterReceipt(record)}>
            <ReceiptText size={15} />
            Registra incasso
          </Button>
        ) : null}
        {canUpdateStatus && record.id && record.state === 'ATTESO' ? (
          <Button type="button" tone="warning" onClick={() => onMarkFailed(record)}>
            <RefreshCw size={15} />
            Fallito
          </Button>
        ) : null}
        {canGeneratePaymentLink && record.id && record.invoiceId ? (
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
  const [paidAt, setPaidAt] = useState(() => formatDateIt(new Date()).split('/').reverse().join('-'))
  const [metricFilter, setMetricFilter] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('riepilogo') || ''
    return ['incassato', 'da_incassare', 'scaduto', 'crediti', 'link_totali', 'link_pagati', 'link_attesi', 'link_falliti'].includes(requested) ? requested : ''
  })
  const [refreshing, setRefreshing] = useState(false)
  const refreshFlight = useRef<Promise<boolean> | null>(null)
  const [refreshError, setRefreshError] = useState('')
  const [filteredRecordIds, setFilteredRecordIds] = useState<string[] | null>(null)
  const [recordsPage, setRecordsPage] = useState(1)
  const recordIds = filteredRecordIds === null ? null : new Set(filteredRecordIds)
  const filteredRecords = data.records.filter((record) => recordIds === null || recordIds.has(record.id ? `pagamento:${record.id}` : `parcella:${record.invoiceId}`))
  const recordsPages = Math.max(1, Math.ceil(filteredRecords.length / 30))
  const currentRecordsPage = Math.min(recordsPage, recordsPages)
  useEffect(() => { setRecordsPage(1) }, [filteredRecordIds])
  const requestedInvoiceId = selectedInvoiceFromLocation()

  function load() {
    if (refreshFlight.current) return refreshFlight.current
    setRefreshing(true)
    refreshFlight.current = getIncassiPagamentiPage()
      .then((payload) => {
        setData(payload)
        setRefreshError('')
        setInvoiceId((current) => payload.records.some((record) => record.invoiceId === current) ? current : '')
        return true
      })
      .catch((cause) => { setRefreshError(cause instanceof Error ? cause.message : 'Impossibile aggiornare gli incassi.'); return false })
      .finally(() => { setLoading(false); setRefreshing(false); refreshFlight.current = null })
    return refreshFlight.current
  }
  useOperationalRefresh(['incassi', 'fatturazione'], load)

  useEffect(() => {
    let active = true
    getIncassiPagamentiPage()
      .then((payload) => {
        if (active) {
          setData(payload)
          const requested = requestedInvoiceId && payload.records.some((record) => record.invoiceId === requestedInvoiceId) ? requestedInvoiceId : ''
          if (requested) setInvoiceId(requested)
          else if (!invoiceId && payload.records[0]?.invoiceId) setInvoiceId(payload.records[0].invoiceId)
        }
      })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : 'Impossibile caricare gli incassi.') })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [requestedInvoiceId])

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

  function selectManualReceipt(record: IncassoPagamentoRecord) {
    setInvoiceId(record.invoiceId)
    setSuccess('Parcella selezionata per la registrazione incasso.')
    window.requestAnimationFrame(() => document.getElementById('registra-incasso')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  const hasData = data.metrics.length > 0 || data.records.length > 0 || data.sections.some((section) => section.items.length > 0)

  return (
    <Page
      className="iu-pay-page"
      title="Incassi e pagamenti"
      subtitle="Controllo operativo su incassi, link parcella e stato dei canali."
      actions={
        <>
          <ButtonLink href="/fatturazione" tone="primary">
            <ReceiptText size={16} />
            Fatturazione
          </ButtonLink>
        </>
      }
    >
      {error && !data.metrics.length ? <div className="iu-pay-alert iu-pay-alert--error" role="alert">{error}<Button tone="neutral" onClick={load}>Riprova</Button></div> : null}
      {refreshError ? <div className="iu-pay-alert iu-pay-alert--error" role="alert">{refreshError}<Button tone="neutral" disabled={refreshing} onClick={load}>Riprova aggiornamento</Button></div> : null}
      {loading ? <LoadingState title="Caricamento incassi" message="Lettura incassi in corso." /> : null}
      {!loading && !hasData ? (
        <EmptyState
          title="Nessun incasso disponibile"
          message="La dashboard non ha ricevuto importi o collegamenti visualizzabili."
        />
      ) : null}
      {!loading && hasData ? (
        <>
          {saving ? <LoadingState title="Salvataggio incasso" message="Salvataggio in corso." /> : null}
          {success ? <div className="iu-pay-alert iu-pay-alert--success" role="status">{success}</div> : null}
          {error ? <div className="iu-pay-alert iu-pay-alert--error" role="alert">{error}</div> : null}
          <section className="iu-pay-banner" aria-label="Impostazioni pagamenti">
            <strong>Impostazioni nella scheda Pagamenti</strong>
            <span>Canali e chiavi riservate si gestiscono da un unico pannello in Impostazioni.</span>
          </section>
          <WarningPanel data={data} />
          <section className="iu-pay-kpis" aria-label="Indicatori incassi">
            {data.metrics.map((metric) => (
              <button type="button" className="iu-pay-kpi" aria-pressed={metricFilter === metric.id} onClick={() => setMetricFilter((current) => current === metric.id ? '' : metric.id)} key={metric.id} disabled={loading || data.warnings.some((warning) => /fatturazione_non_disponibile|pagamenti_non_disponibili/.test(warning.code))}>
                <span>{metric.label}</span><strong>{data.warnings.some((warning) => metric.id === 'link_attesi' ? warning.code === 'pagamenti_non_disponibili' : warning.code === 'fatturazione_non_disponibile') ? 'Non disponibile' : displayValue(metric.value)}</strong><small>Apri elenco</small>
              </button>
            ))}
          </section>
          {refreshing ? <p className="iu-pay-refresh" role="status">Aggiornamento degli incassi in corso…</p> : null}
          <IncassiCardCatalog rows={data.cardRecords} metric={metricFilter} title={data.metrics.find((metric) => metric.id === metricFilter)?.label || ({crediti:'Crediti aperti, scaduti compresi',link_totali:'Tutti i collegamenti di pagamento',link_pagati:'Collegamenti pagati',link_falliti:'Collegamenti falliti'} as Record<string,string>)[metricFilter] || 'Ricerca parcelle e pagamenti'} onClear={() => setMetricFilter('')} unavailable={data.warnings.some((warning) => /non_disponibil/.test(warning.code))} onFilterChange={setFilteredRecordIds}/>
          <section className="iu-pay-grid" aria-label="Sezioni incassi">
            {data.sections.map((section) => (
              <Panel title={section.title} key={section.id}>
                {section.items.length ? (
                  <div className="iu-pay-list">
                    {section.items.map((item) => {
                      const content = <><WalletCards size={17}/><span>{item.label}</span><strong>{displayValue(item.value)}</strong>{item.note ? <small>{item.note}</small> : null}</>
                      if (section.id === 'link') {
                        const filter = ({totale:'link_totali',pagati:'link_pagati',attesi:'link_attesi',falliti:'link_falliti'} as Record<string,string>)[item.id]
                        return <button className="iu-pay-list__item iu-pay-summary-action" key={item.id} type="button" aria-pressed={metricFilter === filter} onClick={() => { setMetricFilter(filter); document.querySelector('.iu-pay-catalog')?.scrollIntoView({block:'start'}) }}>{content}</button>
                      }
                      return data.actions.canOpenProviderSettings ? <a className="iu-pay-list__item iu-pay-summary-action" href="/impostazioni?tab=pagamenti" key={item.id} aria-label={`Configura ${item.label}`}>{content}</a> : <div className="iu-pay-list__item" key={item.id}>{content}</div>
                    })}
                  </div>
                ) : (
                  <EmptyState title={section.emptyMessage} />
                )}
              </Panel>
            ))}
          </section>
          <Panel title="Registra incasso manuale" subtitle="Salvataggio con permessi della sessione.">
            {data.actions.canRegisterPayment ? (
              <div className="iu-pay-form" id="registra-incasso">
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
              <EmptyState title="Permesso non disponibile" message="Questa sessione non consente registrazioni incasso." />
            )}
          </Panel>
          <Panel title="Operazioni sui risultati filtrati" subtitle={`${filteredRecords.length} ${filteredRecords.length === 1 ? 'voce operativa disponibile' : 'voci operative disponibili'} con i filtri correnti`}>
            {filteredRecords.length ? (
              <div className="iu-pay-records">
                {filteredRecords.slice((currentRecordsPage - 1) * 30, currentRecordsPage * 30).map((record) => (
                  <PaymentRow
                    record={record}
                    canUpdateStatus={data.actions.canUpdateStatus}
                    canGeneratePaymentLink={data.actions.canGeneratePaymentLink}
                    onMarkPaid={(item) => mark(item, 'PAGATO')}
                    onMarkFailed={(item) => mark(item, 'FALLITO')}
                    onPaymentLink={paymentLink}
                    onRegisterReceipt={selectManualReceipt}
                    key={record.id || record.invoiceId}
                  />
                ))}
              </div>
            ) : (
              <EmptyState title="Nessuna operazione disponibile per i filtri correnti" />
            )}
            {recordsPages > 1 ? <nav className="iu-pay-pagination" aria-label="Pagine operazioni incassi"><span>Pagina {currentRecordsPage} di {recordsPages}</span><Button tone="neutral" disabled={currentRecordsPage <= 1} onClick={() => setRecordsPage(currentRecordsPage - 1)}>Operazioni precedenti</Button><Button tone="neutral" disabled={currentRecordsPage >= recordsPages} onClick={() => setRecordsPage(currentRecordsPage + 1)}>Operazioni successive</Button></nav> : null}
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
        </>
      ) : null}
    </Page>
  )
}
