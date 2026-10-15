import { useEffect, useState } from 'react'
import { operationalDomains, publishOperationalRefresh, type OperationalDomain } from '../operationalRefresh'
import { OPERATIONAL_REFRESH_RETRY, OPERATIONAL_REFRESH_STATUS } from '../hooks/useOperationalRefresh'
import { changedRevisionDomains, normalizeRevisionContext, sharedRevisionProof } from '../operationalRevisionProof'
import './OperationalLiveSync.css'

/** Share SQL revision polling between tabs of the same tenant/user. */
export function OperationalLiveSync({ enabled, sessionKey }: { enabled: boolean; sessionKey: string }) {
  const [error, setError] = useState('')
  const [failedViews, setFailedViews] = useState<string[]>([])
  useEffect(() => {
    const changed = (event: Event) => {
      const detail = (event as CustomEvent<{ id: string; failed: boolean }>).detail
      if (!detail || typeof detail.id !== 'string') return
      setFailedViews(current => detail.failed ? [...new Set([...current, detail.id])] : current.filter(id => id !== detail.id))
    }
    window.addEventListener(OPERATIONAL_REFRESH_STATUS, changed)
    return () => window.removeEventListener(OPERATIONAL_REFRESH_STATUS, changed)
  }, [])
  useEffect(() => {
    if (!enabled || window.parent !== window) return
    let active = true
    let previous: Record<string, number> | undefined
    let timer: ReturnType<typeof setTimeout>
    let failures = 0
    let controller: AbortController | undefined
    let receivedAt = 0
    let previousContext: string | undefined
    const channel = typeof BroadcastChannel === 'undefined' ? undefined : new BroadcastChannel(`iusentra-live:${sessionKey}`)
    const accept = (next: Record<string, number>, revisionContext?: string) => {
      if (!active) return
      const prior = previous
      const context = normalizeRevisionContext(revisionContext)
      const changed = changedRevisionDomains(prior, next, operationalDomains, previousContext, context) as OperationalDomain[]
      previous = next
      if (context) previousContext = context
      receivedAt = Date.now()
      failures = 0
      setError('')
      if (changed.length) publishOperationalRefresh(changed, { remote: true, revisions: next, revisionContext: context })
    }
    const fail = (message: string) => {
      if (!active) return
      failures += 1
      receivedAt = Date.now()
      setError(message)
    }
    if (channel) channel.onmessage = event => {
      const message = event.data as { revisions?: Record<string, number>; error?: string; revisionContext?: string }
      // An older window cannot certify the current SQL owner. Its unscoped
      // counters never postpone this window's authoritative server polling.
      const proof = sharedRevisionProof(message.revisions, message.revisionContext)
      if (proof) accept(proof.revisions, proof.context)
      else if (typeof message.error === 'string') fail(message.error)
    }
    const request = async () => {
      if (!active || Date.now() - receivedAt < 1800) return
      controller = new AbortController()
      const requestController = controller
      const timeout = setTimeout(() => requestController.abort(), 10000)
      try {
        const response = await fetch('/api/v1/ui/sync/revisions', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: { Accept: 'application/json' } })
        if (!response.ok) throw new Error('Sincronizzazione live interrotta. Riprovo automaticamente.')
        const payload = await response.json() as { ok?: boolean; revisions?: Record<string, number>; revisionContext?: string }
        if (payload.ok !== true || !payload.revisions) throw new Error('Il server non ha confermato la sincronizzazione live.')
        if (!active) return
        accept(payload.revisions, payload.revisionContext)
        channel?.postMessage({ revisions: payload.revisions, revisionContext: payload.revisionContext })
      } catch (reason) {
        if (!active) return
        // Le eccezioni del browser (rete, timeout, risposta non JSON) sono
        // tecniche e spesso in inglese. Il problema resta visibile, insieme
        // al recupero automatico; i messaggi governati sopra restano distinti.
        const message = reason instanceof Error && reason.name === 'Error' ? reason.message : 'Sincronizzazione live interrotta. Riprovo automaticamente.'
        fail(message)
        channel?.postMessage({ error: message })
      } finally {
        clearTimeout(timeout)
      }
    }
    const poll = async () => {
      try {
        if (channel && navigator.locks) {
          await navigator.locks.request(`iusentra-live:${sessionKey}`, { ifAvailable: true }, async lock => { if (lock) await request() })
        } else await request()
      } finally {
        if (active) timer = setTimeout(() => { void poll() }, Math.min(2000 * 2 ** failures, 30000))
      }
    }
    void poll()
    return () => { active = false; clearTimeout(timer); controller?.abort(); channel?.close() }
  }, [enabled, sessionKey])
  if (!error && !failedViews.length) return null
  return <aside className="iu-operational-live-notices" aria-label="Stato della sincronizzazione">
    {error ? <div className="iu-operational-live-notice" role="alert">{error}</div> : null}
    {failedViews.length ? <div className="iu-operational-live-notice" role="alert">Alcuni dati della vista non sono aggiornati. Il recupero non è ancora confermato. <button type="button" className="iu-button" onClick={() => window.dispatchEvent(new Event(OPERATIONAL_REFRESH_RETRY))}>Riprova aggiornamento</button></div> : null}
  </aside>
}
