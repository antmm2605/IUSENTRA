import { useCallback, useEffect, useRef, useState } from 'react'
import { apiPostJson } from '../api/client'
import { CtuCommandSession, loadPendingCtuCommand, type CtuCommandContext, type CtuWriteProtocol, type PendingCtuCommand } from '../ctuCommand'

const send = (href: string, body: Record<string, unknown>) => apiPostJson<Record<string, unknown>>(href, body,
  { ok: false, message: 'Esito non confermato: comando e bozza conservati.' },
  { headers: { 'X-Requested-With': 'XMLHttpRequest' } })

/** Stessa regia per creazione e dettaglio; il recupero non dipende dalla bozza corrente. */
export function useCtuCommand(protocol: CtuWriteProtocol | null, fascicoloId: string, incaricoId: string) {
  const session = useRef<CtuCommandSession | null>(null)
  const [pending, setPending] = useState<PendingCtuCommand | null>(null)
  const [storageError, setStorageError] = useState('')
  const scope = protocol?.scope
  const context = useCallback((): CtuCommandContext => {
    if (!scope) throw new Error('Contesto del salvataggio CTU non disponibile. Riprova la lettura.')
    return { scope, fascicoloId, incaricoId }
  }, [scope, fascicoloId, incaricoId])
  const refreshPending = useCallback(() => {
    if (!scope) { setPending(null); setStorageError(''); return }
    try { setPending(loadPendingCtuCommand(window.sessionStorage, context())); setStorageError('') }
    catch { setPending(null); setStorageError('Il comando conservato non è recuperabile in questa finestra. La bozza resta disponibile; il salvataggio è sospeso.') }
  }, [scope, context])
  useEffect(() => {
    refreshPending()
    window.addEventListener('iusentra:ctu-command-change', refreshPending)
    return () => window.removeEventListener('iusentra:ctu-command-change', refreshPending)
  }, [refreshPending, protocol?.revision])
  const execute = async (href: string, body: Record<string, unknown>, recover = false): Promise<Record<string, unknown>> => {
    if (!protocol) return { ok: false, message: 'Prima del salvataggio occorre rileggere gli incarichi CTU.' }
    if (!protocol.persistentCommands) return recover
      ? { ok: false, message: 'Questo registro storico non dispone di un comando persistente da recuperare.' }
      : send(href, body)
    try {
      if (!session.current) session.current = new CtuCommandSession(window.sessionStorage, send, () => crypto.randomUUID())
      return await (recover ? session.current.recover(context()) : session.current.start(context(), protocol.revision!, href, body))
    } catch {
      return { ok: false, message: 'Impossibile conservare il comando per il recupero. Nessuna nuova richiesta inviata; la bozza è conservata.' }
    } finally {
      refreshPending()
      window.dispatchEvent(new Event('iusentra:ctu-command-change'))
    }
  }
  return { pending, storageError, blocked: !protocol || Boolean(pending) || Boolean(storageError),
    submit: (href: string, body: Record<string, unknown>) => execute(href, body),
    recover: () => execute('', {}, true) }
}
