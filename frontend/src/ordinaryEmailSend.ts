import { csrfToken, submitFormJson, type FormSubmitResult } from './formSubmit'
import { ensureLocalSignerService } from './features/impostazioni/localSigner'

let currentReceiptKey = 'iusentra-ordinary-local-smtp-pending'
type Pending = { confirmation_token: string; ok?: boolean; inviato?: boolean; canale?: string; message_id?: string }
const commands = new WeakMap<HTMLFormElement, string>()

async function confirm(pending: Pending, receiptKey: string): Promise<FormSubmitResult> {
  const response = await fetch('/email-ordinaria/scrivi/conferma-locale', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': csrfToken() },
    body: JSON.stringify(pending),
  })
  const result = await response.json() as FormSubmitResult
  if (!response.ok || result.ok !== true) throw new Error('Il PC ha confermato l’invio, ma la registrazione nello studio non è completata. Premi nuovamente Invia per registrare la conferma senza rispedire.')
  sessionStorage.removeItem(receiptKey)
  return result
}

export async function submitOrdinaryEmailViaTransport(form: HTMLFormElement): Promise<FormSubmitResult> {
  const transportResponse = await fetch('/email-ordinaria/trasporto', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
  if (!transportResponse.ok) throw new Error('Non è stato possibile verificare il canale email dello studio.')
  const transport = await transportResponse.json() as { ok: boolean; local_signer_required: boolean; scope: string }
  if (transport.ok !== true || !transport.scope) throw new Error('Canale email non disponibile.')
  const receiptKey = 'iusentra-ordinary-local-smtp-pending:' + transport.scope
  currentReceiptKey = receiptKey
  const previous = sessionStorage.getItem(receiptKey)
  if (previous) {
    const pending = JSON.parse(previous) as Pending
    if (pending.ok === true && pending.inviato === true && pending.message_id) return confirm(pending, receiptKey)
    throw new Error('Un precedente invio locale non ha un esito confermato. Verifica la casella prima di effettuare un nuovo invio: nessun tentativo automatico è stato eseguito.')
  }
  if (!transport.local_signer_required) return submitFormJson('/email-ordinaria/scrivi', new FormData(form))
  const localError = await ensureLocalSignerService('http://127.0.0.1:27272', 'iusentra-local-signer://restart', true)
  if (localError) throw new Error(localError.message.replace(/PEC/g, 'email ordinaria'))
  const data = new FormData(form)
  const command = commands.get(form) || crypto.randomUUID().replace(/-/g, '')
  commands.set(form, command)
  data.set('local_command_id', command)
  const preparation = await fetch('/email-ordinaria/scrivi', {
    method: 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRF-Token': csrfToken() }, body: data,
  })
  const prepared = await preparation.json() as { ok: boolean; message?: string; local_signer_required?: boolean; local_payload?: unknown; confirmation_token?: string }
  if (!preparation.ok || prepared.ok !== true) throw new Error(prepared.message || 'Preparazione dell’invio non riuscita. Nessuna email spedita dal browser.')
  if (!prepared.local_signer_required || !prepared.local_payload || !prepared.confirmation_token) throw new Error('Canale email modificato durante la preparazione: verifica l’esito prima di riprovare.')
  const pending: Pending = { confirmation_token: prepared.confirmation_token }
  // Persist the attempt before contacting SMTP. A reload must never resend it.
  sessionStorage.setItem(receiptKey, JSON.stringify(pending))
  let response: Response
  try {
    const options: RequestInit & { targetAddressSpace: 'loopback' } = {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      mode: 'cors', targetAddressSpace: 'loopback',
      body: JSON.stringify(prepared.local_payload), signal: AbortSignal.timeout(240000),
    }
    response = await fetch('http://127.0.0.1:27272/email/send', options)
  } catch {
    throw new Error('Il PC non ha restituito l’esito SMTP. L’invio potrebbe essere avvenuto: verifica la casella e non ripetere automaticamente.')
  }
  const result = await response.json() as Pending & { messaggio?: string; submission_started?: boolean }
  if (!response.ok || result.ok !== true || result.inviato !== true || result.canale !== 'locale' || !result.message_id) {
    if (result.submission_started === false) { sessionStorage.removeItem(receiptKey); commands.delete(form) }
    throw new Error((result.messaggio || 'Invio email dal PC non confermato. Verifica la casella prima di riprovare.').replace(/PEC/g, 'email ordinaria'))
  }
  const receipt = { ...pending, ok: true, inviato: true, canale: 'locale', message_id: result.message_id }
  sessionStorage.setItem(receiptKey, JSON.stringify(receipt))
  return confirm(receipt, receiptKey)
}

export function hasUncertainOrdinaryEmail(): boolean {
  const raw = sessionStorage.getItem(currentReceiptKey)
  return Boolean(raw && JSON.parse(raw).ok !== true)
}

export function acknowledgeUnsentOrdinaryEmail(form: HTMLFormElement): void {
  if (!hasUncertainOrdinaryEmail()) return
  sessionStorage.removeItem(currentReceiptKey)
  commands.delete(form)
}
