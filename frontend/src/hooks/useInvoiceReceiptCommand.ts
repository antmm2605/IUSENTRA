import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { formatDateIt, formatEuroIt } from '../formatting'
import { clearReceiptCommand, loadReceiptCommand, saveReceiptCommand, sendReceiptCommand,
  receiptAmountCents, receiptDateKey, type InvoiceReceipt, type InvoiceReceiptsSummary, type ReceiptCommand } from '../invoiceReceiptsData'
import { clearReceiptDraft, loadReceiptDraft, saveReceiptDraft, type ReceiptFields } from '../invoiceReceiptDraft'

const empty = (): ReceiptFields => ({ amount: '', date: formatDateIt(new Date()), method: 'banca', note: '', reason: '', movementId: '' })

export function useInvoiceReceiptCommand(data: InvoiceReceiptsSummary | null, updateSummary: (data: InvoiceReceiptsSummary) => void,
  onConfirmed: (summary: InvoiceReceiptsSummary) => Promise<void>, refreshSummary: () => Promise<void>) {
  const [form, setForm] = useState(empty)
  const [revision, setRevision] = useState('')
  const [pending, setPending] = useState<ReceiptCommand | null>(null)
  const [storageError, setStorageError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const active = useRef('')
  const mounted = useRef(true)
  const submitting = useRef(false)
  const scope = data?.command_scope || ''
  const invoiceId = data?.invoice_id || ''
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  function recoverStorage() {
    if (!data) return
    try {
      const stored = loadReceiptCommand(sessionStorage, invoiceId, scope)
      const draft = loadReceiptDraft(sessionStorage, invoiceId, scope)
      const command = stored || (pending?.scope === scope && pending.invoice_id === invoiceId ? pending : null)
      if (command && !stored) saveReceiptCommand(sessionStorage, command)
      if (stored && pending) saveReceiptCommand(sessionStorage, pending)
      if (active.current === `${scope}:${invoiceId}` && !command) {
        if (revision) saveReceiptDraft(sessionStorage, invoiceId, scope, { fields: form, revision })
        setStorageError(''); return
      }
      setPending(command)
      if (command) {
        setRevision(command.expected_revision)
        setForm({ ...empty(), date: /^\d{4}-\d{2}-\d{2}$/.test(command.paid_on) ? formatDateIt(command.paid_on) : command.paid_on,
          ...(command.operation === 'receipt' ? { amount: formatEuroIt(command.amount_cents / 100), method: command.method, note: command.note }
            : { movementId: command.movement_id, reason: command.reason }) })
      } else if (draft) { setForm(draft.fields); setRevision(draft.revision) }
      else { setForm(empty()); setRevision('') }
      active.current = `${scope}:${invoiceId}`
      setStorageError('')
    } catch { setStorageError('Impossibile recuperare la bozza. Nessun nuovo movimento viene inviato: riprova il recupero.') }
  }
  useLayoutEffect(() => {
    if (!scope || !invoiceId || active.current === `${scope}:${invoiceId}`) return
    setForm(empty()); setPending(null); setRevision(''); setMessage('')
    recoverStorage()
  }, [scope, invoiceId])

  const conflict = Boolean(data && revision && revision !== data.revision)
  function preserve(next: ReceiptFields, nextRevision = revision || data?.revision || '') {
    if (!data || pending || busy || active.current !== `${scope}:${invoiceId}`) return
    setForm(next); setRevision(nextRevision)
    try { saveReceiptDraft(sessionStorage, invoiceId, scope, { fields: next, revision: nextRevision }); setStorageError('') }
    catch { setStorageError('La bozza resta aperta ma non può essere conservata. Riprova il recupero prima di inviare.') }
  }
  function change(field: keyof ReceiptFields, value: string) { preserve({ ...form, [field]: value }) }
  function startReversal(receipt: InvoiceReceipt) {
    if (!data || pending || busy) return
    if (revision) { setMessage('È aperta una bozza: completala o annullala prima dello storno.'); return }
    preserve({ ...empty(), movementId: receipt.movement_id }, data.revision)
  }
  function cancel() {
    if (!data || pending || busy) return
    try { clearReceiptDraft(sessionStorage, invoiceId, scope); setForm(empty()); setRevision(''); setMessage('') }
    catch { setStorageError('La bozza non è stata rimossa: riprova il recupero prima di proseguire.') }
  }
  async function submit() {
    if (!data || submitting.current || storageError || active.current !== `${scope}:${invoiceId}` || (!pending && (conflict || !data.can_write))) return
    submitting.current = true; setBusy(true); setMessage('')
    let command = pending
    try {
      if (!command) {
        const common = { invoice_id: invoiceId, scope, command_key: crypto.randomUUID(), expected_revision: revision || data.revision, paid_on: receiptDateKey(form.date) }
        if (form.movementId) {
          if (!form.reason.trim()) throw new Error('Indica il motivo dello storno.')
          command = { ...common, operation: 'reversal', movement_id: form.movementId, reason: form.reason }
        } else {
          const cents = receiptAmountCents(form.amount)
          command = { ...common, operation: 'receipt', amount_cents: cents, method: form.method, note: form.note }
        }
        try { saveReceiptCommand(sessionStorage, command) }
        catch { setStorageError('Il comando non può essere conservato: nessun invio eseguito. Riprova il recupero.'); return }
        setPending(command)
      }
      const result = await sendReceiptCommand(command)
      if (!mounted.current || active.current !== `${command.scope}:${command.invoice_id}`) return
      setMessage(result.message)
      if (result.confirmed && result.summary) {
        try { clearReceiptDraft(sessionStorage, invoiceId, scope); clearReceiptCommand(sessionStorage, command) }
        catch { setStorageError('Movimento confermato. Riprova il recupero della bozza prima di una nuova registrazione.'); return }
        setPending(null); setForm(empty()); setRevision(''); updateSummary(result.summary)
        try { await onConfirmed(result.summary) } catch { setMessage('Movimento registrato. Il documento deve essere aggiornato: riprova il caricamento.') }
      } else if (result.rejected) {
        try { clearReceiptCommand(sessionStorage, command); setPending(null) }
        catch { setStorageError('La bozza deve essere recuperata prima di modificare il comando.') }
        if (result.refresh) await refreshSummary()
      }
    } catch (error) {
      if (mounted.current) setMessage(error instanceof Error ? error.message : 'Esito non confermato: conserva la bozza e verifica il salvataggio.')
    } finally { submitting.current = false; if (mounted.current) setBusy(false) }
  }
  return { form, change, cancel, startReversal, submit, pending, storageError, recoverStorage, message, busy, conflict,
    review: () => { if (data) preserve(form, data.revision) },
    ready: active.current === `${scope}:${invoiceId}`, hasDraft: Boolean(revision) }
}
