import { csrfToken } from './formSubmit'
import { publishOperationalRefresh } from './operationalRefresh'

export type InvoiceReceipt = {
  movement_id: string; amount_cents: number; direction: 1 | -1; paid_on: string;
  method: string; note: string; reversed: boolean; reverses_movement_id: string;
  provider_confirmed?: boolean;
}
export type ProviderConfirmation = {
  source_key: string; provider: 'stripe' | 'paypal' | 'satispay' | 'sumup'; transaction_id: string;
  amount_cents: number; currency: string; paid_on: string | null; observed_at: string;
  date_origin: string; source_sha256: string; status: 'RECORDED' | 'PENDING' | 'DATE_REQUIRED' | 'REVIEW';
  reason: string; evidence_count: number; movement_id: string;
}
export type InvoiceReceiptsSummary = {
  invoice_id: string; invoice_state: string; is_proforma: boolean; fiscal_document_required?: boolean;
  paid_cents: number | null; residual_cents: number | null; due_cents: number | null;
  status: 'OPEN' | 'PARTIAL' | 'PAID' | 'REVIEW' | 'CANCELLED' | 'DRAFT'; revision: string;
  command_scope: string; can_write: boolean; reason?: string; receipts: InvoiceReceipt[];
  methods: { value: string; label: string }[];
  provider_confirmations?: ProviderConfirmation[];
}
export type ReceiptCommand = {
  invoice_id: string; scope: string; command_key: string; expected_revision: string; paid_on: string;
} & ({ operation: 'receipt'; amount_cents: number; method: string; note: string }
  | { operation: 'reversal'; movement_id: string; reason: string })

const hash = /^[a-f0-9]{64}$/
const identifier = /^[A-Za-z0-9_-]{1,100}$/
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const cents = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
const methods = new Set(['banca', 'cassa', 'pos', 'altro'])

export function receiptAmountCents(input: string): number {
  const raw = input.trim().replace(/^(?:€|EUR)\s*/i, '').replace(/\s+/g, '')
  if (raw.length > 64 || !/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(raw) && !/^\d+\.\d{1,2}$/.test(raw)) {
    throw new Error('Indica un importo positivo con al massimo due decimali.')
  }
  const decimalDot = !raw.includes(',') && /^\d+\.\d{1,2}$/.test(raw)
  const [integer, fraction = ''] = raw.split(decimalDot ? '.' : ',')
  const value = BigInt(integer.replace(/\./g, '')) * 100n + BigInt(fraction.padEnd(2, '0'))
  if (value <= 0n || value > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Importo fuori dai limiti del registro.')
  return Number(value)
}

export function receiptDateKey(input: string): string {
  const raw = input.trim()
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  const italian = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(raw)
  const [year, month, day] = iso ? iso.slice(1).map(Number) : italian ? [Number(italian[3]), Number(italian[2]), Number(italian[1])] : [0, 0, 0]
  const date = new Date(0)
  date.setUTCFullYear(year, month - 1, day)
  if (year < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new Error('Indica una data valida nel formato gg/mm/aaaa.')
  }
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function parseSummary(value: unknown, invoiceId: string): InvoiceReceiptsSummary {
  if (!object(value) || value.invoice_id !== invoiceId || typeof value.invoice_state !== 'string'
    || !['BOZZA', 'EMESSA', 'SCADUTA', 'PAGATA', 'ANNULLATA'].includes(value.invoice_state)
    || typeof value.is_proforma !== 'boolean' || typeof value.can_write !== 'boolean'
    || (value.fiscal_document_required !== undefined && typeof value.fiscal_document_required !== 'boolean')
    || typeof value.status !== 'string' || !['OPEN', 'PARTIAL', 'PAID', 'REVIEW', 'CANCELLED', 'DRAFT'].includes(value.status)
    || typeof value.revision !== 'string' || !hash.test(value.revision)
    || typeof value.command_scope !== 'string' || !hash.test(value.command_scope)
    || !Array.isArray(value.receipts) || !Array.isArray(value.methods)
    || (value.reason !== undefined && typeof value.reason !== 'string')
    || ['paid_cents', 'residual_cents', 'due_cents'].some(key => value[key] !== null && !cents(value[key]))) {
    throw new Error('Riepilogo degli incassi incompleto. Riprova il caricamento.')
  }
  for (const row of value.receipts) {
    if (!object(row) || typeof row.movement_id !== 'string' || !identifier.test(row.movement_id)
      || !cents(row.amount_cents) || row.amount_cents === 0 || ![1, -1].includes(Number(row.direction))
      || typeof row.direction !== 'number' || typeof row.paid_on !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(row.paid_on)
      || typeof row.method !== 'string' || !methods.has(row.method) || typeof row.note !== 'string'
      || typeof row.reversed !== 'boolean' || typeof row.reverses_movement_id !== 'string'
      || (row.provider_confirmed !== undefined && typeof row.provider_confirmed !== 'boolean')
      || (row.reverses_movement_id && !identifier.test(row.reverses_movement_id))) {
      throw new Error('Movimento non riscontrato. Gli importi non vengono ricostruiti.')
    }
  }
  if (value.provider_confirmations !== undefined) {
    if (!Array.isArray(value.provider_confirmations)) throw new Error('Conferme dei gestori non disponibili.')
    for (const row of value.provider_confirmations) {
      if (!object(row) || typeof row.source_key !== 'string' || !hash.test(row.source_key)
        || typeof row.provider !== 'string' || !['stripe', 'paypal', 'satispay', 'sumup'].includes(row.provider)
        || typeof row.transaction_id !== 'string' || !row.transaction_id || row.transaction_id.length > 200
        || !cents(row.amount_cents) || row.amount_cents === 0 || typeof row.currency !== 'string' || !/^[A-Z]{3}$/.test(row.currency)
        || (row.paid_on !== null && (typeof row.paid_on !== 'string' || receiptDateKey(row.paid_on) !== row.paid_on))
        || typeof row.observed_at !== 'string' || !Number.isFinite(Date.parse(row.observed_at))
        || typeof row.date_origin !== 'string' || typeof row.source_sha256 !== 'string' || !hash.test(row.source_sha256)
        || typeof row.status !== 'string' || !['RECORDED', 'PENDING', 'DATE_REQUIRED', 'REVIEW'].includes(row.status)
        || typeof row.reason !== 'string' || typeof row.evidence_count !== 'number' || !Number.isSafeInteger(row.evidence_count) || row.evidence_count < 1
        || typeof row.movement_id !== 'string' || (row.movement_id !== '' && !identifier.test(row.movement_id))
        || (row.status === 'RECORDED' && !row.movement_id)) {
        throw new Error('Conferma del gestore incompleta: aggiorna i riscontri del documento.')
      }
      if (row.status === 'RECORDED' && !value.receipts.some((receipt: InvoiceReceipt) =>
        receipt.movement_id === row.movement_id && receipt.direction === 1 && receipt.amount_cents === row.amount_cents
        && (row.paid_on === null || receipt.paid_on === row.paid_on))) {
        throw new Error('Conferma del gestore senza il relativo movimento verificato.')
      }
    }
  }
  if (value.methods.length !== methods.size || new Set(value.methods.map(row => object(row) ? row.value : null)).size !== methods.size
    || value.methods.some(row => !object(row) || typeof row.value !== 'string' || !methods.has(row.value) || typeof row.label !== 'string')) {
    throw new Error('Metodi di incasso non disponibili.')
  }
  if (value.status !== 'REVIEW' && (!cents(value.paid_cents) || !cents(value.residual_cents) || !cents(value.due_cents))) {
    throw new Error('Saldo non riscontrato. Ricarica gli incassi.')
  }
  const total = value.receipts.reduce((sum: bigint, row: InvoiceReceipt) => sum + BigInt(row.amount_cents) * BigInt(row.direction), 0n)
  if (value.paid_cents !== null && (!cents(value.paid_cents) || total !== BigInt(value.paid_cents))) throw new Error('Saldo discordante dai movimenti ricevuti.')
  if (['OPEN', 'PARTIAL', 'PAID'].includes(value.status)
    && (!cents(value.paid_cents) || !cents(value.residual_cents) || !cents(value.due_cents)
      || value.paid_cents + value.residual_cents !== value.due_cents
      || (value.status === 'PARTIAL' && !(value.paid_cents > 0 && value.residual_cents > 0))
      || (value.status === 'OPEN' && value.paid_cents !== 0)
      || (value.status === 'PAID' && !(value.residual_cents === 0 && value.due_cents > 0)))) {
    throw new Error('Riepilogo discordante tra importi e stato del pagamento.')
  }
  if ((value.status === 'DRAFT' && (value.paid_cents !== 0 || value.residual_cents !== value.due_cents))
    || (value.status === 'CANCELLED' && (value.paid_cents !== 0 || value.residual_cents !== 0))) {
    throw new Error('Bozza o documento annullato con saldo non riscontrato.')
  }
  return value as InvoiceReceiptsSummary
}

export async function getInvoiceReceipts(invoiceId: string, signal?: AbortSignal): Promise<InvoiceReceiptsSummary> {
  if (!identifier.test(invoiceId)) throw new Error('Documento non valido.')
  const response = await fetch(`/api/fatturazione/${encodeURIComponent(invoiceId)}/incassi`, {
    signal, credentials: 'same-origin', headers: { Accept: 'application/json' },
  })
  const payload: unknown = await response.json()
  if (!response.ok || !object(payload) || payload.ok !== true) {
    throw new Error(object(payload) && typeof payload.message === 'string' ? payload.message : 'Incassi non disponibili.')
  }
  return parseSummary(payload.summary, invoiceId)
}

export function receiptStorageKey(invoiceId: string, scope: string): string {
  if (!identifier.test(invoiceId) || !hash.test(scope)) throw new Error('Contesto del comando non valido.')
  return `iusentra.invoice-receipts.pending.v1.${scope}.${invoiceId}`
}

function validateCommand(value: unknown, invoiceId: string, scope: string): ReceiptCommand {
  const base = ['invoice_id', 'scope', 'command_key', 'expected_revision', 'paid_on', 'operation']
  const extra = object(value) && value.operation === 'receipt' ? ['amount_cents', 'method', 'note'] : ['movement_id', 'reason']
  if (!object(value) || Object.keys(value).sort().join() !== [...base, ...extra].sort().join()
    || value.invoice_id !== invoiceId || value.scope !== scope || !identifier.test(invoiceId) || !hash.test(scope)
    || typeof value.command_key !== 'string' || !uuid.test(value.command_key)
    || typeof value.expected_revision !== 'string' || !hash.test(value.expected_revision)
    || typeof value.paid_on !== 'string' || value.paid_on.length > 10
    || !['receipt', 'reversal'].includes(String(value.operation))
    || (value.operation === 'receipt' ? !cents(value.amount_cents) || value.amount_cents === 0
      || typeof value.method !== 'string' || !methods.has(value.method) || typeof value.note !== 'string'
      : typeof value.movement_id !== 'string' || !identifier.test(value.movement_id) || typeof value.reason !== 'string' || !value.reason.trim())) {
    throw new Error('Comando pendente non valido. Il contenuto è conservato per recuperarne l’esito.')
  }
  if (JSON.stringify(value).length > 32768) throw new Error('Comando troppo grande: nessun invio eseguito.')
  receiptDateKey(value.paid_on)
  return value as ReceiptCommand
}

export function loadReceiptCommand(storage: Pick<Storage, 'getItem'>, invoiceId: string, scope: string): ReceiptCommand | null {
  const raw = storage.getItem(receiptStorageKey(invoiceId, scope))
  if (raw === null) return null
  if (raw.length > 32768) throw new Error('Comando pendente troppo grande. Il contenuto resta conservato.')
  return validateCommand(JSON.parse(raw), invoiceId, scope)
}
function sameCommand(left: ReceiptCommand, right: ReceiptCommand): boolean {
  return Object.keys(left).length === Object.keys(right).length && Object.entries(left).every(([key, value]) =>
    value === (right as unknown as Record<string, unknown>)[key])
}
export function saveReceiptCommand(storage: Pick<Storage, 'setItem' | 'getItem'>, command: ReceiptCommand): void {
  validateCommand(command, command.invoice_id, command.scope)
  const previous = loadReceiptCommand(storage, command.invoice_id, command.scope)
  if (previous && !sameCommand(previous, command)) {
    throw new Error('È presente un comando da verificare. Recuperane l’esito prima di inviarne un altro.')
  }
  storage.setItem(receiptStorageKey(command.invoice_id, command.scope), JSON.stringify(command))
}
export function clearReceiptCommand(storage: Pick<Storage, 'removeItem' | 'getItem'>, command: ReceiptCommand): void {
  const previous = loadReceiptCommand(storage, command.invoice_id, command.scope)
  if (previous && !sameCommand(previous, command)) {
    throw new Error('Il comando conservato è cambiato: nessuna bozza viene eliminata.')
  }
  storage.removeItem(receiptStorageKey(command.invoice_id, command.scope))
}

export async function sendReceiptCommand(command: ReceiptCommand): Promise<{
  confirmed: boolean; rejected: boolean; message: string; summary?: InvoiceReceiptsSummary; refresh?: boolean;
}> {
  validateCommand(command, command.invoice_id, command.scope)
  try {
    const { invoice_id: invoiceId, ...body } = command
    const response = await fetch(`/api/fatturazione/${encodeURIComponent(invoiceId)}/incassi`, {
      method: 'POST', credentials: 'same-origin', headers: {
        Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest',
      }, body: JSON.stringify(body),
    })
    const payload: unknown = await response.json()
    const ack = object(payload) && object(payload.confirmed_command) ? payload.confirmed_command : null
    const confirmed = response.ok && object(payload) && payload.ok === true && ack !== null
      && ack.invoice_id === invoiceId && ack.scope === command.scope && ack.command_key === command.command_key
      && ack.expected_revision === command.expected_revision && typeof payload.movement_id === 'string' && identifier.test(payload.movement_id)
      && typeof payload.already_present === 'boolean'
    if (confirmed) {
      const summary = parseSummary(payload.summary, invoiceId)
      const movement = summary.receipts.find(row => row.movement_id === payload.movement_id)
      const original = command.operation === 'reversal' ? summary.receipts.find(row => row.movement_id === command.movement_id) : null
      if (!movement || movement.paid_on !== receiptDateKey(command.paid_on)
        || (command.operation === 'receipt' ? movement.direction !== 1 || movement.amount_cents !== command.amount_cents
          || movement.method !== command.method || movement.note !== command.note
          : movement.direction !== -1 || movement.reverses_movement_id !== command.movement_id || !original
            || movement.amount_cents !== original.amount_cents || movement.method !== original.method
            || movement.note !== `Storno di ${command.movement_id}: ${command.reason.trim()}`)) {
        throw new Error('Il movimento non conferma il comando originale.')
      }
      if (!payload.already_present) publishOperationalRefresh(['fatturazione', 'incassi', 'fascicoli'])
      return { confirmed: true, rejected: false, message: String(payload.message || 'Movimento registrato.'), summary }
    }
    return { confirmed: false, rejected: !response.ok && object(payload)
      && ((response.status === 400 && payload.code === 'validation') || (response.status === 409 && payload.code === 'revision_conflict')),
      refresh: response.status === 409 && object(payload) && payload.code === 'revision_conflict',
      message: object(payload) && typeof payload.message === 'string' ? payload.message : 'Conferma incompleta. Verifica il salvataggio con lo stesso comando.' }
  } catch {
    return { confirmed: false, rejected: false, message: 'Esito da verificare. La bozza è conservata: verifica il salvataggio prima di registrare un altro movimento.' }
  }
}
