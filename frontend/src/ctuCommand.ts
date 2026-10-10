/** Comandi CTU pendenti: il retry riusa contesto, revisione e intento originali. */
export type CtuWriteProtocol = { persistentCommands: boolean; revision: number | null; scope: string | null }
export type CtuCommandContext = { scope: string; fascicoloId: string; incaricoId: string }
type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }
export type PendingCtuCommand = CtuCommandContext & {
  commandKey: string; expectedRevision: number; href: string; body: Record<string, JsonValue>
}
const hash = /^[a-f0-9]{64}$/
const identifier = /^[A-Za-z0-9_-]{1,100}$/
const uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)

export function parseCtuWriteProtocol(value: unknown): CtuWriteProtocol {
  if (value === undefined) return { persistentCommands: false, revision: null, scope: null }
  if (!object(value) || typeof value.persistentCommands !== 'boolean') throw new Error('Protocollo CTU non valido.')
  if (value.persistentCommands) {
    if (!Number.isSafeInteger(value.revision) || Number(value.revision) < 0 || typeof value.scope !== 'string' || !hash.test(value.scope)) {
      throw new Error('Contesto del salvataggio CTU incompleto.')
    }
    return { persistentCommands: true, revision: value.revision as number, scope: value.scope }
  }
  if (value.revision !== null || (value.scope !== undefined && value.scope !== null)) throw new Error('Protocollo storico CTU incoerente.')
  return { persistentCommands: false, revision: null, scope: null }
}

export function ctuPendingStorageKey(context: CtuCommandContext): string {
  if (typeof context.scope !== 'string' || !hash.test(context.scope) || typeof context.fascicoloId !== 'string' || !identifier.test(context.fascicoloId)
    || typeof context.incaricoId !== 'string' || (context.incaricoId && !identifier.test(context.incaricoId))) {
    throw new Error('Contesto del comando CTU non valido.')
  }
  return `iusentra.ctu.pending.v1.${context.scope}.${context.fascicoloId}.${context.incaricoId || 'nuovo'}`
}

function jsonValue(value: unknown, depth = 0): boolean {
  if (depth > 12) return false
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true
  if (typeof value === 'number') return Number.isFinite(value)
  if (Array.isArray(value)) return value.every((item) => jsonValue(item, depth + 1))
  return object(value) && Object.getPrototypeOf(value) === Object.prototype && Object.entries(value).every(([key, item]) =>
    !['__proto__', 'constructor', 'prototype'].includes(key) && jsonValue(item, depth + 1))
}

function validateCommand(value: unknown, context: CtuCommandContext): PendingCtuCommand {
  ctuPendingStorageKey(context)
  if (!object(value) || Object.keys(value).sort().join() !== ['scope', 'fascicoloId', 'incaricoId', 'commandKey', 'expectedRevision', 'href', 'body'].sort().join()
    || value.scope !== context.scope || value.fascicoloId !== context.fascicoloId || value.incaricoId !== context.incaricoId
    || typeof value.commandKey !== 'string' || !uuid.test(value.commandKey)
    || !Number.isSafeInteger(value.expectedRevision) || Number(value.expectedRevision) < 0
    || typeof value.href !== 'string' || !object(value.body) || !jsonValue(value.body)
    || 'commandKey' in value.body || 'expectedRevision' in value.body) {
    throw new Error('Comando CTU pendente non valido. Il contenuto resta conservato per il recupero.')
  }
  const base = `/fascicoli/${context.fascicoloId}/ctu/`
  const expected = context.incaricoId ? `${base}${context.incaricoId}/` : `${base}nuovo`
  const allowed = context.incaricoId
    ? ['aggiorna', 'operazioni', 'compenso', 'ctp', 'proponi-scadenze', 'istanza'].some((action) => value.href === `${expected}${action}`)
      || new RegExp(`^${expected}operazioni/[A-Za-z0-9_-]{1,100}/rimuovi$`).test(value.href)
    : value.href === expected
  if (!allowed || JSON.stringify(value).length > 131072) throw new Error('Destinazione o dimensione del comando CTU non valida.')
  return value as PendingCtuCommand
}

export function loadPendingCtuCommand(storage: Pick<Storage, 'getItem'>, context: CtuCommandContext): PendingCtuCommand | null {
  const raw = storage.getItem(ctuPendingStorageKey(context))
  if (raw === null) return null
  if (raw.length > 131072) throw new Error('Comando CTU pendente troppo grande. Il contenuto resta conservato per il recupero.')
  return validateCommand(JSON.parse(raw), context)
}

export function savePendingCtuCommand(storage: Pick<Storage, 'setItem'>, command: PendingCtuCommand): void {
  validateCommand(command, command)
  storage.setItem(ctuPendingStorageKey(command), JSON.stringify(command))
}

export function clearPendingCtuCommand(storage: Pick<Storage, 'removeItem'>, context: CtuCommandContext): void {
  storage.removeItem(ctuPendingStorageKey(context))
}

/** ok da solo non dimostra che il server ha confermato proprio il comando pendente. */
export function isCtuCommandConfirmed(payload: unknown, command: PendingCtuCommand): boolean {
  if (!object(payload) || payload.ok !== true || !object(payload.confirmedCommand)) return false
  const receipt = payload.confirmedCommand
  return receipt.scope === command.scope && receipt.commandKey === command.commandKey
    && receipt.fascicoloId === command.fascicoloId && typeof receipt.incaricoId === 'string' && identifier.test(receipt.incaricoId)
    && (!command.incaricoId || receipt.incaricoId === command.incaricoId)
    && Number.isSafeInteger(receipt.committedRevision) && receipt.committedRevision === command.expectedRevision + 1
}

export function isCtuCommandRejected(payload: unknown, command: PendingCtuCommand): boolean {
  if (!object(payload) || payload.ok !== false || !['validation', 'conflict'].includes(String(payload.code)) || !object(payload.rejectedCommand)) return false
  const receipt = payload.rejectedCommand
  return receipt.status === 'rejected' && receipt.scope === command.scope && receipt.commandKey === command.commandKey
    && receipt.fascicoloId === command.fascicoloId && receipt.incaricoId === command.incaricoId
    && receipt.expectedRevision === command.expectedRevision && Number.isSafeInteger(receipt.rejectedAtRevision)
    && Number(receipt.rejectedAtRevision) >= 0
}

type CommandStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>
type CommandSender = (href: string, body: Record<string, unknown>) => Promise<Record<string, unknown>>

/** Un solo comando in volo; nessun nuovo intento sostituisce un esito ancora incerto. */
export class CtuCommandSession {
  private sending = false
  private storage: CommandStorage
  private send: CommandSender
  private createKey: () => string
  constructor(storage: CommandStorage, send: CommandSender, createKey: () => string) {
    this.storage = storage
    this.send = send
    this.createKey = createKey
  }

  async start(context: CtuCommandContext, revision: number, href: string, body: Record<string, unknown>): Promise<Record<string, unknown>> {
    if (this.sending) return { ok: false, code: 'command_in_progress', message: 'Un comando CTU è già in corso.' }
    if (loadPendingCtuCommand(this.storage, context)) {
      return { ok: false, code: 'pending_command', message: 'Un salvataggio CTU attende il riscontro. Recuperalo prima di inviare altre modifiche.' }
    }
    const command = validateCommand({ ...context, commandKey: this.createKey(), expectedRevision: revision, href, body }, context)
    // Copia serializzata prima dell'invio: modifiche successive al modulo non cambiano il retry.
    savePendingCtuCommand(this.storage, command)
    return this.deliver(context)
  }

  async recover(context: CtuCommandContext): Promise<Record<string, unknown>> {
    if (this.sending) return { ok: false, code: 'command_in_progress', message: 'Un comando CTU è già in corso.' }
    return this.deliver(context)
  }

  private async deliver(context: CtuCommandContext): Promise<Record<string, unknown>> {
    const command = loadPendingCtuCommand(this.storage, context)
    if (!command) return { ok: false, code: 'command_missing', message: 'Nessun comando CTU da recuperare in questo contesto.' }
    this.sending = true
    try {
      const payload = await this.send(command.href, { ...command.body, commandKey: command.commandKey, expectedRevision: command.expectedRevision })
      const rejected = isCtuCommandRejected(payload, command)
      if (!isCtuCommandConfirmed(payload, command) && !rejected) {
        return { ...payload, ok: false, code: 'outcome_not_confirmed',
          message: typeof payload.message === 'string' && payload.ok !== true ? payload.message
            : 'Esito CTU non confermato: comando e bozza conservati per il recupero.' }
      }
      const current = loadPendingCtuCommand(this.storage, context)
      if (!current || JSON.stringify(current) !== JSON.stringify(command)) {
        return { ok: false, code: 'pending_changed', message: 'Il comando conservato è cambiato durante il salvataggio. Il riscontro non lo sostituisce.' }
      }
      clearPendingCtuCommand(this.storage, context)
      return rejected ? { ...payload, terminalRejected: true } : payload
    } catch {
      return { ok: false, code: 'outcome_not_confirmed', message: 'Esito CTU non confermato: comando e bozza conservati. Riprova il recupero dello stesso comando.' }
    } finally { this.sending = false }
  }
}
