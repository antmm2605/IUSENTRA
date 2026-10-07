import { useEffect } from 'react'
import { OPERATIONAL_REFRESH_EVENT, operationalDomains, type OperationalDomain } from '../operationalRefresh'

type Update = { type: typeof OPERATIONAL_REFRESH_EVENT; domains: OperationalDomain[] }
export function OperationalRefreshBridge() {
  useEffect(() => {
    const frames = () => [...document.querySelectorAll<HTMLIFrameElement>('.iu-context-work-frame, iframe[data-iusentra-operational-frame="true"]')]
    const sendToFrames = (message: Update, except?: MessageEventSource | null) => {
      frames().forEach(frame => {
        if (frame.contentWindow !== except) frame.contentWindow?.postMessage(message, window.location.origin)
      })
    }
    const local = (event: Event) => {
      const detail = (event as CustomEvent<{ domains: OperationalDomain[]; relayed?: boolean }>).detail
      if (!detail || detail.relayed) return
      const message: Update = { type: OPERATIONAL_REFRESH_EVENT, domains: detail.domains }
      if (window.parent !== window) window.parent.postMessage(message, window.location.origin)
      else sendToFrames(message)
    }
    const received = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== OPERATIONAL_REFRESH_EVENT) return
      const embedded = window.parent !== window
      if (embedded ? event.source !== window.parent : !frames().some(frame => frame.contentWindow === event.source)) return
      if (!Array.isArray(event.data.domains) || event.data.domains.length > operationalDomains.length) return
      const domains = event.data.domains.filter((value: unknown): value is OperationalDomain => typeof value === 'string' && operationalDomains.includes(value as OperationalDomain))
      if (!domains.length) return
      window.dispatchEvent(new CustomEvent(OPERATIONAL_REFRESH_EVENT, { detail: { domains, relayed: true } }))
      if (!embedded) sendToFrames({ type: OPERATIONAL_REFRESH_EVENT, domains }, event.source)
    }
    window.addEventListener(OPERATIONAL_REFRESH_EVENT, local)
    window.addEventListener('message', received)
    return () => {
      window.removeEventListener(OPERATIONAL_REFRESH_EVENT, local)
      window.removeEventListener('message', received)
    }
  }, [])
  return null
}