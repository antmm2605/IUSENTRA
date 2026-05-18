export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface JsonRequestOptions extends Omit<RequestInit, 'body' | 'method'> {
  body?: unknown
  csrfToken?: string
  fetchImpl?: typeof fetch
  method?: HttpMethod
}

export class ApiClientError extends Error {
  readonly details: unknown
  readonly status: number

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.details = details
  }
}

const ensureRelativeApiPath = (path: string) => {
  if (!path.startsWith('/')) {
    throw new Error('Il percorso API deve iniziare con /.')
  }
  if (/^\/\//.test(path) || /^https?:\/\//i.test(path)) {
    throw new Error('Il client API accetta solo percorsi relativi interni.')
  }
}

export async function requestJson<TResponse>(
  path: string,
  {
    body,
    csrfToken,
    fetchImpl = globalThis.fetch,
    headers,
    method = body === undefined ? 'GET' : 'POST',
    ...request
  }: JsonRequestOptions = {},
): Promise<TResponse> {
  ensureRelativeApiPath(path)

  if (!fetchImpl) {
    throw new Error('Fetch non disponibile: configurare esplicitamente fetchImpl.')
  }

  const response = await fetchImpl(path, {
    ...request,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: {
      Accept: 'application/json',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
      ...headers,
    },
    method,
  })

  const contentType = response.headers.get('content-type') ?? ''
  const details = contentType.includes('application/json') ? await response.json() : await response.text()

  if (!response.ok) {
    throw new ApiClientError('Richiesta non riuscita.', response.status, details)
  }

  return details as TResponse
}
