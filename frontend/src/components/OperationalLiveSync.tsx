import { useEffect, useState } from 'react'
import { operationalDomains, publishOperationalRefresh, type OperationalDomain } from '../operationalRefresh'
import { OPERATIONAL_REFRESH_RETRY, OPERATIONAL_REFRESH_STATUS } from '../hooks/useOperationalRefresh'
import { changedRevisionDomains, normalizeRevisionContext, sharedRevisionProof } from '../operationalRevisionProof'
import './OperationalLiveSync.css'

/** Share SQL revision polling between tabs of the same tenant/user. */
export function OperationalLiveSync({ enabled, sessionKey }: { enabled: boolean; sessionKey: string }) {
  const [status, setStatus] = useState<'ready' | 'delayed' | 'session-expired'>('ready')
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
    let unauthorized = 0
    let firstFailureAt = 0
    let polling = false
    let controller: AbortController | undefined
    let receivedAt = 0
    let previousContext: string | undefined
    setStatus('ready')
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
      unauthorized = 0
      firstFailureAt = 0
      setStatus('ready')
      if (changed.length) publishOperationalRefresh(changed, { remote: true, revisions: next, revisionContext: context })
    }
    const fail = () => {
      if (!active) return
      const now = Date.now()
      if (!failures) firstFailureAt = now
      failures += 1
      if (failures >= 3 && now - firstFailureAt >= 12000) {
        setStatus(current => current === 'session-expired' ? current : 'delayed')
      }
    }
    if (channel) channel.onmessage = event => {
      const message = event.data as { revisions?: Record<string, number>; revisionContext?: string }
      // An older window cannot certify the current SQL owner. Its unscoped
      // counters never postpone this window's authoritative server polling.
      const proof = sharedRevisionProof(message.revisions, message.revisionContext)
      if (proof) accept(proof.revisions, proof.context)
    }
    const request = async () => {
      if (!active || Date.now() - receivedAt < 1800) return
      controller = new AbortController()
      const requestController = controller
      const timeout = setTimeout(() => requestController.abort(), 10000)
      try {
        const response = await fetch('/api/v1/ui/sync/revisions', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal, headers: { Accept: 'application/json' } })
        if (!active) return
        if (response.status === 401) {
          unauthorized += 1
          if (unauthorized >= 3) {
            failures = Math.max(4, failures)
            setStatus('session-expired')
          }
          return
        }
        unauthorized = 0
        if (!response.ok) {
          fail()
          return
        }
        const payload = await response.json() as { ok?: boolean; revisions?: Record<string, number>; revisionContext?: string }
        if (payload.ok !== true || !payload.revisions) {
          fail()
          return
        }
        if (!active) return
        accept(payload.revisions, payload.revisionContext)
        channel?.postMessage({ revisions: payload.revisions, revisionContext: payload.revisionContext })
      } catch {
        unauthorized = 0
        fail()
      } finally {
        clearTimeout(timeout)
      }
    }
    const poll = async () => {
      if (!active || polling) return
      polling = true
      try {
        if (channel && navigator.locks) {
          await navigator.locks.request(`iusentra-live:${sessionKey}`, { ifAvailable: true }, async lock => { if (lock) await request() })
        } else await request()
      } catch {
        await request()
      } finally {
        polling = false
        // Scheda nascosta: niente controllo ogni 2 secondi per nessuno (verifica del 31/10/2026);
        // al ritorno sulla scheda il controllo riparte subito.
        const nascosta = typeof document !== 'undefined' && document.visibilityState === 'hidden'
        if (active) timer = setTimeout(() => { void poll() }, nascosta ? 60000 : Math.min(2000 * 2 ** failures, 30000))
      }
    }
    const visibile = () => {
      if (!active || document.visibilityState !== 'visible') return
      clearTimeout(timer)
      receivedAt = 0
      void poll()
    }
    document.addEventListener('visibilitychange', visibile)
    window.addEventListener('online', visibile)
    window.addEventListener(OPERATIONAL_REFRESH_RETRY, visibile)
    void poll()
    return () => {
      active = false
      clearTimeout(timer)
      controller?.abort()
      channel?.close()
      document.removeEventListener('visibilitychange', visibile)
      window.removeEventListener('online', visibile)
      window.removeEventListener(OPERATIONAL_REFRESH_RETRY, visibile)
    }
  }, [enabled, sessionKey])
  if (status === 'ready' && !failedViews.length) return null
  return <aside className="iu-operational-live-notices" aria-label="Stato della sincronizzazione">
    {status === 'session-expired'
      ? <div className="iu-operational-live-notice" role="status">Per ricevere gli aggiornamenti, accedi di nuovo. <a className="iu-button" href="/login">Accedi</a></div>
      : <div className="iu-operational-live-notice" role="status">
        Alcuni dati potrebbero non essere aggiornati. <button type="button" className="iu-button" onClick={() => window.dispatchEvent(new Event(OPERATIONAL_REFRESH_RETRY))}>Aggiorna</button>
      </div>}
  </aside>
}
