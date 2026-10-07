import { useEffect, useRef } from 'react'
import { OPERATIONAL_REFRESH_EVENT, type OperationalDomain } from '../operationalRefresh'

export function useOperationalRefresh(domains: OperationalDomain[], refresh: () => void | Promise<unknown>, options: { relayedOnly?: boolean } = {}) {
  const latest = useRef(refresh)
  latest.current = refresh
  const signature = domains.join(',')
  const relayedOnly = options.relayedOnly === true
  useEffect(() => {
    const subscribed = signature.split(',')
    let timer: ReturnType<typeof setTimeout> | undefined
    const updated = (event: Event) => {
      const detail = (event as CustomEvent<{ domains?: string[]; relayed?: boolean }>).detail
      if (relayedOnly && !detail?.relayed) return
      if (!detail?.domains?.some(domain => subscribed.includes(domain))) return
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => { void Promise.resolve().then(() => latest.current()).catch(() => undefined) }, 120)
    }
    window.addEventListener(OPERATIONAL_REFRESH_EVENT, updated)
    return () => {
      if (timer) clearTimeout(timer)
      window.removeEventListener(OPERATIONAL_REFRESH_EVENT, updated)
    }
  }, [signature, relayedOnly])
}