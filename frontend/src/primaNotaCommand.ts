// Conserva soltanto il comando pendente della scheda e dell'operatore correnti.
export type PendingPrimaNotaCommand = {commandKey: string; expectedRevision: number; scope: string; body: Record<string, string>}
const fields = ['data', 'tipo', 'importo', 'categoria', 'controparte', 'causale', 'metodo', 'documento']
export function pendingStorageKey(scope: string): string {
  if (!/^[a-f0-9]{64}$/.test(scope)) throw new Error('Contesto del salvataggio non valido.')
  return `iusentra.prima-nota.pending.v1.${scope}`
}
export function loadPendingCommand(storage: Pick<Storage, 'getItem'>, scope: string): PendingPrimaNotaCommand | null {
  const raw = storage.getItem(pendingStorageKey(scope))
  if (raw === null) return null
  const value = JSON.parse(raw) as PendingPrimaNotaCommand
  if (!value || value.scope !== scope || typeof value.commandKey !== 'string'
    || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value.commandKey)
    || !Number.isSafeInteger(value.expectedRevision) || value.expectedRevision < 0
    || !value.body || typeof value.body !== 'object' || Array.isArray(value.body)
    || Object.keys(value.body).sort().join() !== [...fields].sort().join()
    || Object.values(value.body).some(item => typeof item !== 'string')) {
    throw new Error('Comando pendente non valido. Il contenuto è conservato; occorre recuperarne l’esito.')
  }
  return value
}
export function savePendingCommand(storage: Pick<Storage, 'setItem'>, command: PendingPrimaNotaCommand): void {
  storage.setItem(pendingStorageKey(command.scope), JSON.stringify(command))
}
export function clearPendingCommand(storage: Pick<Storage, 'removeItem'>, scope: string): void {
  storage.removeItem(pendingStorageKey(scope))
}
