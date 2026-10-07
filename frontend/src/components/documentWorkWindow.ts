export type DocumentWorkPreview = { name: string; url: string; downloadUrl: string; mobileUrl?: string; operational?: boolean }
// Trasporta soltanto documenti persistenti dello stesso fascicolo: nessun file temporaneo o percorso operativo di firma/invio.
export function documentWorkPreview(value: unknown, origin: string): DocumentWorkPreview | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Record<string, unknown>
  if (item.objectUrl || typeof item.name !== 'string' || !item.name.trim() || typeof item.url !== 'string') return null
  try {
    const url = new URL(item.url, origin)
    const match = url.pathname.match(/^\/fascicoli\/([a-zA-Z0-9_-]+)\/documenti\/([a-zA-Z0-9_-]+)\/visualizza$/)
    if (!match || url.origin !== origin || url.username || url.password) return null
    const internal = (raw: unknown, action: string): string | null => {
      if (!raw) return ''
      if (typeof raw !== 'string') return null
      const candidate = new URL(raw, origin)
      if (candidate.origin !== origin || candidate.username || candidate.password || candidate.pathname !== `/fascicoli/${match[1]}/documenti/${match[2]}/${action}`) return null
      return candidate.pathname + candidate.search + candidate.hash
    }
    const downloadUrl = internal(item.downloadUrl, 'scarica')
    const mobileUrl = internal(item.mobileUrl, 'visualizza')
    if (downloadUrl === null || mobileUrl === null) return null
    return { name: item.name.trim().slice(0, 512), url: url.pathname + url.search + url.hash, downloadUrl, ...(mobileUrl ? { mobileUrl } : {}), ...(item.operational === true ? { operational: true } : {}) }
  } catch { return null }
}
