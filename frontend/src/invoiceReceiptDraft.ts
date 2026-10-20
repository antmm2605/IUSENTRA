import { receiptStorageKey } from './invoiceReceiptsData'

export type ReceiptFields = { amount: string; date: string; method: string; note: string; reason: string; movementId: string }
export type ReceiptDraft = { fields: ReceiptFields; revision: string }
const names = ['amount', 'date', 'method', 'note', 'reason', 'movementId']

function validated(value: unknown): ReceiptDraft {
  const draft = value as ReceiptDraft | null
  if (!draft || typeof draft !== 'object' || Object.keys(draft).sort().join() !== 'fields,revision'
    || typeof draft.revision !== 'string' || !/^[a-f0-9]{64}$/.test(draft.revision)
    || !draft.fields || typeof draft.fields !== 'object' || Object.keys(draft.fields).sort().join() !== [...names].sort().join()
    || Object.values(draft.fields).some(field => typeof field !== 'string') || JSON.stringify(draft).length > 32768) {
    throw new Error('Bozza non riscontrata. Il contenuto è conservato per il recupero.')
  }
  return draft
}
export function loadReceiptDraft(storage: Pick<Storage, 'getItem'>, invoiceId: string, scope: string): ReceiptDraft | null {
  const raw = storage.getItem(receiptStorageKey(invoiceId, scope) + '.draft')
  if (raw === null) return null
  if (raw.length > 32768) throw new Error('Bozza troppo grande: contenuto conservato.')
  return validated(JSON.parse(raw))
}
export function saveReceiptDraft(storage: Pick<Storage, 'setItem'>, invoiceId: string, scope: string, draft: ReceiptDraft): void {
  validated(draft)
  storage.setItem(receiptStorageKey(invoiceId, scope) + '.draft', JSON.stringify(draft))
}
export function clearReceiptDraft(storage: Pick<Storage, 'removeItem'>, invoiceId: string, scope: string): void {
  storage.removeItem(receiptStorageKey(invoiceId, scope) + '.draft')
}
