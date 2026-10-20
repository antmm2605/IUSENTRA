import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw, RotateCcw } from 'lucide-react'
import { getInvoiceReceipts, type InvoiceReceiptsSummary } from '../invoiceReceiptsData'
import { useInvoiceReceiptCommand } from '../hooks/useInvoiceReceiptCommand'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { formatDateIt, formatDecimalIt, formatEuroIt } from '../formatting'
import { Button } from '../ui/Button'
import { LoadingState } from '../ui/LoadingState'
import './InvoiceReceiptsPanel.css'

const labels = { OPEN: 'Da incassare', PARTIAL: 'Incasso parziale', PAID: 'Saldo incassato', REVIEW: 'Da riscontrare', CANCELLED: 'Documento annullato', DRAFT: 'Bozza non emessa' }
const money = (cents: number | null) => cents === null ? 'Da riscontrare' : formatEuroIt(cents / 100)

export function InvoiceReceiptsPanel({ invoiceId, onConfirmed, reverseMovementId = '' }: {
  invoiceId: string; onConfirmed: (summary: InvoiceReceiptsSummary) => Promise<void>; reverseMovementId?: string;
}) {
  const [data, setData] = useState<InvoiceReceiptsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const load = useCallback(async () => {
    const run = ++sequence.current
    controller.current?.abort()
    const request = new AbortController()
    controller.current = request
    setLoading(true)
    try {
      const result = await getInvoiceReceipts(invoiceId, request.signal)
      if (!request.signal.aborted && run === sequence.current) { setData(result); setError('') }
    } catch (failure) {
      if (!request.signal.aborted && run === sequence.current) setError(failure instanceof Error ? failure.message : 'Incassi non disponibili.')
    } finally {
      if (!request.signal.aborted && run === sequence.current) setLoading(false)
    }
  }, [invoiceId])
  useEffect(() => {
    setData(null); void load()
    return () => { ++sequence.current; controller.current?.abort() }
  }, [load])
  useOperationalRefresh(['fatturazione', 'incassi'], load)
  const command = useInvoiceReceiptCommand(data, setData, onConfirmed, load)
  const selectedReversal = useRef('')
  useEffect(() => {
    if (!reverseMovementId || !data || !command.ready || command.hasDraft || command.pending
      || selectedReversal.current === `${invoiceId}:${reverseMovementId}`) return
    const original = data.receipts.find(row => row.movement_id === reverseMovementId)
    if (!original || original.direction !== 1 || original.reversed || !data.can_write) return
    selectedReversal.current = `${invoiceId}:${reverseMovementId}`
    command.startReversal(original)
  }, [data, invoiceId, reverseMovementId, command.ready, command.hasDraft, command.pending, command.startReversal])
  const pending = Boolean(command.pending)
  const reversing = Boolean(command.form.movementId)
  const canRegister = Boolean(data?.can_write && ['BOZZA', 'EMESSA', 'SCADUTA', 'PAGATA'].includes(data.invoice_state)
    && ['DRAFT', 'OPEN', 'PARTIAL'].includes(data.status) && data.residual_cents && data.residual_cents > 0)
  const locked = pending || command.busy || Boolean(command.storageError) || !command.ready || Boolean(error)
  const original = data?.receipts.find(row => row.movement_id === command.form.movementId)
  if (!data && loading) return <LoadingState title="Caricamento incassi" message="Lettura dei movimenti del documento." />
  return <section className="iu-invoice-receipts" aria-label="Incassi del documento">
    <header><h3>Incassi {data ? <small>{labels[data.status]}</small> : null}</h3>
      <Button type="button" tone="neutral" disabled={loading || command.busy} onClick={() => void load()}><RefreshCw size={14} /> {loading ? 'Aggiornamento…' : 'Aggiorna'}</Button>
    </header>
    {error ? <p role="alert">{error} La bozza è conservata.</p> : null}
    {data ? <>
      <dl className="iu-invoice-receipts__totals">
        <div><dt>Netto di riferimento</dt><dd>{money(data.due_cents)}</dd></div>
        <div><dt>Incassato</dt><dd>{money(data.paid_cents)}</dd></div>
        <div><dt>Residuo</dt><dd>{money(data.residual_cents)}</dd></div>
      </dl>
      {data.reason ? <p role="status">{data.reason}</p> : null}
      {data.fiscal_document_required && (data.paid_cents ?? 0) > 0 ? <p role="status">Incasso registrato. Documento fiscale da predisporre nel percorso di emissione.</p> : null}
      {data.provider_confirmations?.length ? <>
        <h4>Conferme dei gestori</h4>
        <ul className="iu-invoice-receipts__list">{data.provider_confirmations.map(source => <li key={source.source_key}>
          <div>
            <strong>{{ stripe: 'Stripe', paypal: 'PayPal', satispay: 'Satispay', sumup: 'SumUp' }[source.provider]} · {source.currency === 'EUR' ? money(source.amount_cents) : `${source.currency} ${formatDecimalIt(source.amount_cents / 100)}`}</strong>
            <span>{{ RECORDED: 'Registrato in Prima nota', PENDING: 'Registrazione in attesa', DATE_REQUIRED: 'Data da riscontrare', REVIEW: 'Da riconciliare' }[source.status]}</span>
            <small>Riferimento del gestore: {source.transaction_id}</small>
            {source.paid_on ? <small>Data del pagamento: {formatDateIt(source.paid_on)}</small> : null}
            {source.evidence_count > 1 ? <small>{source.evidence_count} conferme collegate allo stesso pagamento</small> : null}
            {source.reason ? <p role={source.status === 'REVIEW' || source.status === 'DATE_REQUIRED' ? 'alert' : 'status'}>{source.reason}</p> : null}
          </div>
        </li>)}</ul>
      </> : null}
      {reverseMovementId && reversing && reverseMovementId !== command.form.movementId ? <p role="status">È stata recuperata una bozza relativa a un altro incasso. Verificala o annullala prima di iniziare questo storno.</p> : null}
      {command.conflict && !pending ? <div role="alert"><p>Il documento o gli incassi sono cambiati. La tua bozza è conservata: confronta il nuovo riepilogo prima di confermare.</p>
        <Button type="button" tone="neutral" disabled={command.busy || Boolean(error)} onClick={command.review}>Usa il riepilogo aggiornato</Button></div> : null}
      {canRegister || reversing || pending ? <div className="iu-invoice-receipts__entry">
        <h4>{reversing ? `Storno incasso${original ? ` di ${money(original.amount_cents)}` : ''}` : 'Registra incasso'}</h4>
        <fieldset disabled={locked || command.conflict}>
          <div className="iu-invoice-receipts__fields">
            {!reversing ? <label>Importo ricevuto (€)<input inputMode="decimal" maxLength={64} value={command.form.amount} onChange={event => command.change('amount', event.currentTarget.value)} placeholder="€ 0,00" /></label> : null}
            <label>Data effettiva<input value={command.form.date} onChange={event => command.change('date', event.currentTarget.value)} placeholder="gg/mm/aaaa" maxLength={10} /></label>
            {!reversing ? <label>Metodo<select value={command.form.method} onChange={event => command.change('method', event.currentTarget.value)}>{data.methods.map(method => <option key={method.value} value={method.value}>{method.label}</option>)}</select></label> : null}
            <label className="iu-invoice-receipts__note">{reversing ? 'Motivo dello storno' : 'Riferimento o annotazione'}<input maxLength={2000} value={reversing ? command.form.reason : command.form.note} onChange={event => command.change(reversing ? 'reason' : 'note', event.currentTarget.value)} /></label>
          </div>
        </fieldset>
        {pending ? <p role="status">Comando conservato: verifica l’esito prima di registrare un altro movimento.</p> : null}
        <div className="iu-invoice-receipts__actions">
          <Button type="button" tone="primary" disabled={command.busy || Boolean(command.storageError) || !command.ready || (!pending && (command.conflict || Boolean(error) || (reversing ? !command.form.reason.trim() : !command.form.amount.trim())))} onClick={() => void command.submit()}>
            {command.busy ? 'Verifica in corso…' : pending ? 'Verifica salvataggio' : reversing ? 'Conferma storno' : 'Registra incasso'}
          </Button>
          {!pending && command.hasDraft ? <Button type="button" tone="neutral" disabled={command.busy} onClick={command.cancel}>Annulla bozza</Button> : null}
        </div>
      </div> : null}
      {command.storageError ? <div role="alert"><p>{command.storageError}</p><Button type="button" tone="neutral" disabled={command.busy} onClick={command.recoverStorage}>Riprova recupero</Button></div> : null}
      {command.message ? <p role="status">{command.message}</p> : null}
      <h4>Movimenti in Prima nota</h4>
      {data.receipts.length ? <ul className="iu-invoice-receipts__list">{data.receipts.map(receipt => <li key={receipt.movement_id}>
        <div><strong>{receipt.direction === -1 ? 'Storno' : receipt.reversed ? 'Incasso stornato' : 'Incasso'} · {money(receipt.amount_cents)}</strong>
          <span>{formatDateIt(receipt.paid_on)} · {data.methods.find(method => method.value === receipt.method)?.label}</span>
          {receipt.note ? <small>{receipt.note}</small> : null}
          {receipt.provider_confirmed ? <small>Confermato dal gestore: un eventuale rimborso richiede il relativo riscontro.</small> : null}</div>
        {data.can_write && receipt.direction === 1 && !receipt.reversed && !receipt.provider_confirmed ? <Button type="button" tone="neutral" disabled={locked || Boolean(command.form.movementId)} onClick={() => command.startReversal(receipt)}><RotateCcw size={14} /> Storna</Button> : null}
      </li>)}</ul> : <p>{data.status === 'REVIEW' ? 'Nessun movimento verificato collegato a questo documento.' : 'Nessun incasso registrato.'}</p>}
    </> : null}
  </section>
}

export default InvoiceReceiptsPanel
