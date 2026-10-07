/** Un errore di lettura non dimostra che il messaggio sia stato rimosso. */
const sourceRetryStatuses = new Set([423, 429, 500, 503])
function failureLabel(status?: number): string {
  if (status === 401) return 'La sessione è scaduta. Accedi nuovamente per consultare il messaggio.'
  if (status === 403) return 'Non hai il permesso di consultare questo messaggio.'
  return 'Non è stato possibile caricare il messaggio. Riprova tra poco.'
}
export async function fetchMailboxDetailJson(endpoint: string, sourceRetry = false): Promise<Record<string, unknown> | null> {
  const attempts = sourceRetry ? 3 : 1
  let failure = failureLabel()
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const controller = sourceRetry && typeof AbortController !== 'undefined' ? new AbortController() : null
    const timeout = controller ? setTimeout(() => controller.abort(), 8000) : undefined
    let retry = false
    try {
      const response = await fetch(`${endpoint}?_ts=${Date.now()}`, {
        credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }, signal: controller?.signal,
      })
      if (response.status === 404) return null
      if (response.ok) {
        const payload: unknown = await response.json()
        if (payload && typeof payload === 'object' && !Array.isArray(payload) && (payload as Record<string, unknown>).ok !== false) {
          return payload as Record<string, unknown>
        }
        failure = 'I dati del messaggio non sono disponibili. Riprova tra poco.'
      } else {
        failure = failureLabel(response.status)
        retry = sourceRetryStatuses.has(response.status)
      }
    } catch {
      failure = 'Il caricamento del messaggio si è interrotto. Controlla la connessione e riprova.'
      retry = true
    } finally {
      if (timeout) clearTimeout(timeout)
    }
    if (!retry || attempt === attempts - 1) throw new Error(failure)
    await new Promise<void>(resolve => setTimeout(resolve, 450 + attempt * 550))
  }
  throw new Error(failure)
}
