/** Adattatore del protocollo di dominio: intento immutabile e ricevuta concordante. */
export type PreparationProtocol = { persistentCommands: boolean; scope?: string }
export type PreparationCommand = {
  scope: string; target: string; sessionId: string; commandKey: string; expectedRevision: number;
  href: string; body: Record<string, unknown>
}
type StoragePort = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
type Sender = (href: string, body: Record<string, unknown>) => Promise<Record<string, unknown>>
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const id = /^[A-Za-z0-9_-]{1,150}$/
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/
function jsonValue(value: unknown, depth = 0): boolean {
  if (depth > 12) return false
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true
  if (typeof value === 'number') return Number.isFinite(value)
  if (Array.isArray(value)) return value.every(item => jsonValue(item, depth + 1))
  return object(value) && Object.getPrototypeOf(value) === Object.prototype && Object.entries(value).every(([key, item]) =>
    !['__proto__', 'constructor', 'prototype'].includes(key) && jsonValue(item, depth + 1))
}
function storageKey(scope: string, target: string) {
  if (!/^[a-f0-9]{64}$/.test(scope) || !id.test(target)) throw new Error('Contesto della preparazione incompleto.')
  return `iusentra.preparazione.pending.v1.${scope}.${target}`
}
function validate(value: unknown, scope: string, target: string): PreparationCommand {
  if (!object(value) || Object.keys(value).sort().join() !== ['scope', 'target', 'sessionId', 'commandKey', 'expectedRevision', 'href', 'body'].sort().join()
      || value.scope !== scope || value.target !== target || typeof value.sessionId !== 'string'
      || (value.sessionId && !id.test(value.sessionId)) || typeof value.commandKey !== 'string' || !uuid.test(value.commandKey)
      || !Number.isSafeInteger(value.expectedRevision) || Number(value.expectedRevision) < 0 || !object(value.body) || !jsonValue(value.body)
      || 'commandKey' in value.body || 'expectedRevision' in value.body || JSON.stringify(value).length > 131072) {
    throw new Error('Comando conservato non valido: salvataggio sospeso, contenuto preservato.')
  }
  const base = '/api/v1/ui/preparazione-udienza/'
  if (value.sessionId ? !['passo', 'documento', 'documento-extra', 'verifica', 'esito'].some(action => value.href === `${base}${value.sessionId}/${action}`)
    : value.href !== `${base}avvia` || value.expectedRevision !== 0) throw new Error('Destinazione del comando non valida.')
  return value as PreparationCommand
}
export function loadPreparationCommand(storage: Pick<Storage, 'getItem'>, scope: string, target: string): PreparationCommand | null {
  const raw = storage.getItem(storageKey(scope, target))
  if (raw === null) return null
  if (raw.length > 131072) throw new Error('Comando conservato troppo grande: recupero necessario.')
  return validate(JSON.parse(raw), scope, target)
}
const sending = new Set<string>()
export async function preparationCommand(storage: StoragePort, send: Sender, context: { scope: string; target: string; sessionId: string },
  revision: number, href: string, body: Record<string, unknown>, recover = false): Promise<Record<string, unknown>> {
  let key = ''
  let claimed = false
  try {
    key = storageKey(context.scope, context.target)
    if (sending.has(key)) return { ok: false, code: 'in_progress', message: 'Salvataggio già in corso.' }
    let command = loadPreparationCommand(storage, context.scope, context.target)
    if (!recover && command) return { ok: false, code: 'pending', message: 'Recupera il comando ancora in attesa prima di salvare altre modifiche.' }
    if (!recover) {
      command = validate({ ...context, commandKey: crypto.randomUUID(), expectedRevision: revision, href, body }, context.scope, context.target)
      storage.setItem(key, JSON.stringify(command))
      command = loadPreparationCommand(storage, context.scope, context.target)
    }
    if (!command) return { ok: false, message: 'Nessun comando da recuperare in questa preparazione.' }
    sending.add(key)
    claimed = true
    const result = await send(command.href, { ...command.body, commandKey: command.commandKey, expectedRevision: command.expectedRevision })
    const receipt = result.ok === true ? result.confirmedCommand : result.rejectedCommand
    const confirmed = object(receipt) && receipt.scope === command.scope && receipt.commandKey === command.commandKey
      && typeof receipt.sessionId === 'string' && (command.sessionId ? receipt.sessionId === command.sessionId : id.test(receipt.sessionId))
      && Number.isSafeInteger(receipt.committedRevision) && (command.sessionId
        ? receipt.committedRevision === command.expectedRevision + 1 : Number(receipt.committedRevision) >= 1)
    const rejected = result.ok === false && object(receipt) && receipt.status === 'rejected'
      && receipt.scope === command.scope && receipt.commandKey === command.commandKey && receipt.sessionId === command.sessionId
      && receipt.expectedRevision === command.expectedRevision && Number.isSafeInteger(receipt.revision)
      && ['validation', 'conflict'].includes(String(result.code))
    if (!confirmed && !rejected) return { ...result, ok: false, code: 'outcome_not_confirmed',
      message: result.ok ? 'Ricevuta non concordante: conserva la bozza e recupera lo stesso comando.' : result.message }
    if (JSON.stringify(loadPreparationCommand(storage, context.scope, context.target)) !== JSON.stringify(command)) {
      return { ok: false, message: 'Il comando conservato è cambiato durante il salvataggio: nessuna bozza sostituita.' }
    }
    storage.removeItem(key)
    return rejected ? { ...result, terminalRejected: true } : result
  } catch { return { ok: false, code: 'outcome_not_confirmed', message: 'Salvataggio non confermato: bozza preservata. Recupera il comando prima di riprovare.' } }
  finally { if (claimed) sending.delete(key) }
}
