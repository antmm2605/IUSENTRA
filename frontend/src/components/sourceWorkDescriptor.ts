import type { SourceDocument } from './SourceDocumentModal'

/** Accetta soltanto fonti di lettura native, senza inoltrare comandi operativi. */
export function sourceWorkDescriptor(value: unknown, origin: string): SourceDocument | null {
  if (!value || typeof value !== 'object') return null
  const input = value as Record<string, unknown>
  if (typeof input.href !== 'string' || typeof input.label !== 'string' || typeof input.context !== 'string') return null
  if (!input.label.trim() || input.label.length > 240 || input.context.length > 2000 || input.href.length > 8000) return null
  try {
    const url = new URL(input.href, origin)
    if (url.origin !== origin || url.username || url.password) return null
    const path = url.pathname.replace(/\/+$/, '')
    const native = /^\/fascicoli\/[A-Za-z0-9_-]+(?:\/documenti\/[A-Za-z0-9_-]+\/visualizza)?$/.test(path)
      || /^\/email(?:-ordinaria)?(?:\/messaggio\/[^/]+(?:\/allegato\/[^/]+)?)?$/.test(path)
      || /^\/api\/v1\/ui\/email\/source\/[^/]+$/.test(path)
      || /^\/api\/v1\/ui\/fonti-procedurali\//.test(path)
      || path === '/api/v1/ui/document-reader/web'
      || /^\/api\/v1\/ui\/controllo-studio\/conoscenza-notifiche\/fonti\/[a-z0-9_]+$/.test(path)
    if (!native || /\/(?:firma|invio|deposito|elimina|scarica)(?:\/|$)/.test(path)) return null
    return { href: `${url.pathname}${url.search}${url.hash}`, label: input.label.trim(), context: input.context,
      ...(typeof input.kind === 'string' ? { kind: input.kind.slice(0, 80) } : {}) }
  } catch { return null }
}
