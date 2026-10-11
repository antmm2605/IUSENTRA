import { publishMutationRefresh } from '../operationalRefresh'
import { csrfHeader } from './csrf'
import { ApiClientError, normaliseErrorPayload } from './errors'
import type { ApiMutationOptions, ApiRequestOptions } from './types'
import { withActivity } from '../ui/activity'

export { ApiClientError } from './errors'

async function parseJsonResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('application/json')) {
    const text = await response.text()
    return text ? { ok: false, message: text } : {}
  }
  return response.json()
}

async function requestJson<T>(url: string, init: RequestInit, fallback: T, activity: string | false): Promise<T> {
  return withActivity(activity, async () => {
  try {
    const response = await fetch(url, init)
    const payload = await parseJsonResponse(response)
    if (!response.ok) {
      return normaliseErrorPayload(payload, response.status, fallback) as T
    }
    if (payload && typeof payload === 'object' && 'ok' in payload && payload.ok === true) publishMutationRefresh(url)
    return payload as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    return fallback
  }
  })
}

export async function apiJson<T>(url: string, fallback: T, options: ApiRequestOptions = {}): Promise<T> {
  return withActivity(options.activity ?? 'Caricamento dati…', async () => {
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      signal: options.signal,
      headers: {
        Accept: 'application/json',
        ...options.headers,
      },
    })
    if (!response.ok) return fallback
    return (await parseJsonResponse(response)) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    return fallback
  }
  })
}

export async function apiPostJson<T>(
  url: string,
  body: unknown,
  fallback: T,
  options: ApiMutationOptions = {},
): Promise<T> {
  return requestJson<T>(url, {
    method: options.method || 'POST',
    credentials: 'same-origin',
    signal: options.signal,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...csrfHeader(),
      ...options.headers,
    },
    body: JSON.stringify(body),
  }, fallback, options.activity ?? 'Operazione in corso…')
}

export async function ensureJson<T>(url: string, options: ApiRequestOptions = {}): Promise<T> {
  return withActivity(options.activity ?? 'Caricamento dati…', async () => {
  const response = await fetch(url, {
    credentials: 'same-origin',
    signal: options.signal,
    headers: {
      Accept: 'application/json',
      ...options.headers,
    },
  })
  const payload = await parseJsonResponse(response)
  if (!response.ok) throw new ApiClientError(response.status, normaliseErrorPayload(payload, response.status, {}))
  return payload as T
  })
}
