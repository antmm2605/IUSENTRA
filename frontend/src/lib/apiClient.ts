export type ApiErrorShape = {
  ok?: false
  message?: string
  errore?: string
  errors?: Record<string, string>
  warnings?: Array<{ code?: string; message?: string }>
  status?: number
}

function csrfToken(): string {
  if (typeof document === 'undefined') return ''
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function parseJsonResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) {
    const text = await response.text()
    return text ? { ok: false, message: text } : {}
  }
  return response.json()
}

function normaliseErrorPayload(payload: unknown, status: number, fallback: unknown): unknown {
  const record = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : {}
  const warnings = Array.isArray(record.warnings) ? record.warnings : []
  const warningMessage = warnings
    .map((item) => {
      if (!item || typeof item !== 'object') return ''
      return String((item as Record<string, unknown>).message || '').trim()
    })
    .filter(Boolean)
    .join(' ')
  const message = String(record.message || record.errore || warningMessage || '').trim()
  if (Object.keys(record).length) {
    return {
      ...record,
      ok: record.ok === true ? true : false,
      message: message || `Richiesta non completata (${status}).`,
      status,
    }
  }
  if (fallback && typeof fallback === 'object' && !Array.isArray(fallback)) {
    return {
      ...(fallback as Record<string, unknown>),
      ok: false,
      message: message || `Richiesta non completata (${status}).`,
      status,
    }
  }
  return fallback
}

export async function apiJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return fallback
    return (await response.json()) as T
  } catch {
    return fallback
  }
}

export async function apiPostJson<T>(url: string, body: unknown, fallback: T): Promise<T> {
  try {
    const token = csrfToken()
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(token ? { 'X-CSRF-Token': token } : {}),
      },
      body: JSON.stringify(body),
    })
    const payload = await parseJsonResponse(response)
    if (!response.ok) return normaliseErrorPayload(payload, response.status, fallback) as T
    return payload as T
  } catch {
    return fallback
  }
}
