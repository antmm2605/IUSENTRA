import { sourceWorkDescriptor } from './sourceWorkDescriptor'
import { openSourceWindow } from './sourceWindowEvents'
import type { SourceDocument } from './SourceDocumentModal'

export function inAppSourceDestination(href: string, label: string, origin: string, target = '', download = false): SourceDocument | null {
  if (download) return null
  try {
    const url = new URL(href, origin)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null
    const source = { href: url.pathname + url.search + url.hash, label: label.trim().slice(0, 240) || 'Documento', context: 'Consultazione della fonte in IUSENTRA' }
    if (url.origin !== origin) return { ...source, href: `/api/v1/ui/document-reader/web?${new URLSearchParams({ url: url.href })}` }
    if (/^\/giurisprudenza\/sentenzeweb\/\d+(?:\/documenti\/\d+)?\/testo$/.test(url.pathname) || /^\/giurisprudenza\/corpus\/\d+(?:\/testo|\/documenti\/\d+\/pdf)$/.test(url.pathname) || /^\/giurisprudenza\/corpus\/\d+\/traduzioni\/[0-9a-f]{32}$/.test(url.pathname) || target === '_blank') return sourceWorkDescriptor(source, origin)
    return null
  } catch { return null }
}

export function installInAppSourceNavigation() {
  const follow = (event: MouseEvent) => {
    if (event.defaultPrevented || event.button !== 0 || !(event.target instanceof Element)) return
    const link = event.target.closest<HTMLAnchorElement>('a[href]')
    if (!link || link.hasAttribute('download')) return
    const source = inAppSourceDestination(link.href, link.getAttribute('aria-label') || link.textContent || '', window.location.origin, link.target)
    if (source) {
      event.preventDefault()
      openSourceWindow(source, 'navigazione-fonti', () => {})
    } else if (link.target === '_blank' && new URL(link.href, window.location.origin).origin === window.location.origin) {
      link.target = '_self'
    }
  }
  document.addEventListener('click', follow)
  return () => document.removeEventListener('click', follow)
}
