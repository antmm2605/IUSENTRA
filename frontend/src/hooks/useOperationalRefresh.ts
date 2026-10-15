import { useCallback, useEffect, useId, useRef } from 'react'
import { OPERATIONAL_REFRESH_EVENT, type OperationalDomain } from '../operationalRefresh'
import { createOperationalRefreshQueue } from '../operationalRefreshQueue'
import type { OperationalRevisions } from '../operationalRevisionProof'

export const OPERATIONAL_REFRESH_STATUS = 'iusentra:operational-refresh-status'
export const OPERATIONAL_REFRESH_RETRY = 'iusentra:operational-refresh-retry'

export function useOperationalRefresh(domains: OperationalDomain[], refresh: (intent: { live: boolean; revisions?: OperationalRevisions; revisionContext?: string }) => void | boolean | Promise<unknown>, options: { relayedOnly?: boolean } = {}) {
  const latest = useRef(refresh)
  const queueRef = useRef<ReturnType<typeof createOperationalRefreshQueue> | null>(null)
  const requestedBeforeSubscription = useRef(false)
  const scheduleRefresh = useCallback(() => {
    if (queueRef.current) queueRef.current.schedule()
    else requestedBeforeSubscription.current = true
  }, [])
  const subscriptionId = useId()
  latest.current = refresh
  const signature = domains.join(',')
  const relayedOnly = options.relayedOnly === true
  useEffect(() => {
    const subscribed = signature.split(',')
    let failed = false
    const report = (value: boolean) => {
      failed = value
      window.dispatchEvent(new CustomEvent(OPERATIONAL_REFRESH_STATUS, { detail: { id: subscriptionId, failed: value } }))
    }
    const queue = createOperationalRefreshQueue(intent => latest.current(intent), report)
    queueRef.current = queue
    if (requestedBeforeSubscription.current) {
      requestedBeforeSubscription.current = false
      queue.schedule()
    }
    const updated = (event: Event) => {
      const detail = (event as CustomEvent<{ domains?: string[]; relayed?: boolean; remote?: boolean; revisions?: OperationalRevisions; revisionContext?: string }>).detail
      if (relayedOnly && !detail?.relayed && !detail?.remote) return
      if (!detail?.domains?.some(domain => subscribed.includes(domain))) return
      queue.schedule({ live: true, revisions: detail.revisions, revisionContext: detail.revisionContext })
    }
    const retry = () => { if (failed) queue.schedule() }
    window.addEventListener(OPERATIONAL_REFRESH_EVENT, updated)
    window.addEventListener(OPERATIONAL_REFRESH_RETRY, retry)
    return () => {
      queue.dispose()
      if (queueRef.current === queue) queueRef.current = null
      report(false)
      window.removeEventListener(OPERATIONAL_REFRESH_EVENT, updated)
      window.removeEventListener(OPERATIONAL_REFRESH_RETRY, retry)
    }
  }, [signature, relayedOnly, subscriptionId])
  return scheduleRefresh
}
