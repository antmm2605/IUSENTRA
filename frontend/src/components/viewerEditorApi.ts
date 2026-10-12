export function editorEndpoint(href: string): string | null {
  const url = new URL(href, window.location.origin)
  if (url.origin !== window.location.origin) return null
  const match = /^\/fascicoli\/([^/]+)\/documenti\/([^/]+)\/visualizza\/?$/.exec(url.pathname)
  return match ? `/api/v1/ui/fascicoli/${match[1]}/documenti/${match[2]}/editor-visualizzatore` : null
}

export async function requestJson(url: string, init?: RequestInit) {
  const readOnly = (init?.method || 'GET').toUpperCase() === 'GET'
  for (let attempt = 0; ; attempt += 1) {
    let response: Response
    let raw: string
    try {
      response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', ...init })
      raw = await response.text()
    } catch (error) {
      if (init?.signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw error
      if (readOnly && attempt < 2) { await retryDelay(attempt, init?.signal); continue }
      throw new Error('Connessione al lettore interrotta. Riprova il caricamento; le modifiche restano conservate.')
    }
    let payload
    try { payload = JSON.parse(raw) } catch {
      if (readOnly && attempt < 2 && (response.ok || [502, 503, 504].includes(response.status))) {
        await retryDelay(attempt, init?.signal); continue
      }
      throw new Error('Il lettore non ha ricevuto una risposta valida dal server. Riprova il caricamento.')
    }
    if ([502, 503, 504].includes(response.status) && readOnly && attempt < 2) {
      await retryDelay(attempt, init?.signal); continue
    }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      throw new Error('Risposta del lettore non valida. Riprova il caricamento.')
    }
    if (!response.ok || payload.ok === false) throw new Error(payload.message || payload.errore || 'Operazione non disponibile.')
    return payload
  }
}

function retryDelay(attempt: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); signal?.removeEventListener('abort', abort); reject(new DOMException('Lettura annullata', 'AbortError')) }
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve() }, attempt === 0 ? 1200 : 2500)
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
  })
}
