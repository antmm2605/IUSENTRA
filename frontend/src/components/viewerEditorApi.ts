export function editorEndpoint(href: string): string | null {
  const url = new URL(href, window.location.origin)
  if (url.origin !== window.location.origin) return null
  const match = /^\/fascicoli\/([^/]+)\/documenti\/([^/]+)\/visualizza\/?$/.exec(url.pathname)
  return match ? `/api/v1/ui/fascicoli/${match[1]}/documenti/${match[2]}/editor-visualizzatore` : null
}

export async function requestJson(url: string, init?: RequestInit) {
  const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...init })
  const payload = await response.json()
  if (!response.ok || payload.ok === false) throw new Error(payload.message || payload.errore || 'Operazione non disponibile.')
  return payload
}
