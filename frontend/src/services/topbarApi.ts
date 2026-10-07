import type {
  GlobalSearchPayload,
  TimeTrackingActivityType,
  TimeTrackingLink,
  TimeTrackingPayload,
  TopbarDeadlinesPayload,
  TopbarNotificationsPayload,
  TopbarRecentPayload,
  TopbarTodayPayload,
} from '../types/topbar'

type ApiFailure = { ok?: boolean; error?: string }

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return {}
  try {
    return JSON.parse(text) as unknown
  } catch {
    return {}
  }
}

function errorMessage(payload: unknown, fallback: string): string {
  const candidate = payload as ApiFailure
  return typeof candidate.error === 'string' && candidate.error.trim() ? candidate.error : fallback
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  const payload = await readJson(response)
  if (!response.ok) {
    throw new Error(errorMessage(payload, 'Operazione non riuscita.'))
  }
  return payload as T
}

export function fetchGlobalSearch(query: string, limit = 20): Promise<GlobalSearchPayload> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return requestJson<GlobalSearchPayload>(`/api/search/global?${params.toString()}`)
}

export function fetchTodaySummary(date: string): Promise<TopbarTodayPayload> {
  const params = new URLSearchParams({ date })
  return requestJson<TopbarTodayPayload>(`/api/dashboard/today?${params.toString()}`)
}

export function fetchNotifications(options: { page?: number; state?: string; query?: string } = {}): Promise<TopbarNotificationsPayload> {
  const params = new URLSearchParams({ page: String(options.page ?? 1), state: options.state ?? 'all', q: options.query ?? '' })
  return requestJson<TopbarNotificationsPayload>(`/api/notifications?${params.toString()}`)
}

export function markNotificationRead(id: string): Promise<TopbarNotificationsPayload> {
  return requestJson<TopbarNotificationsPayload>(`/api/notifications/${encodeURIComponent(id)}/read`, {
    method: 'PATCH',
  })
}

export function markAllNotificationsRead(): Promise<TopbarNotificationsPayload> {
  return requestJson<TopbarNotificationsPayload>('/api/notifications/read-all', { method: 'PATCH' })
}

export function fetchQuickDeadlines(): Promise<TopbarDeadlinesPayload> {
  return requestJson<TopbarDeadlinesPayload>('/api/deadlines/quick-summary')
}

export function fetchRecentItems(): Promise<TopbarRecentPayload> {
  return requestJson<TopbarRecentPayload>('/api/recent')
}

export function trackRecentItem(entityType: string, entityId: string): Promise<TopbarRecentPayload> {
  return requestJson<TopbarRecentPayload>('/api/recent', {
    method: 'POST',
    body: JSON.stringify({ entityType, entityId }),
  })
}

export function trackRecentSearch(query: string, total = 0): Promise<TopbarRecentPayload> {
  return requestJson<TopbarRecentPayload>('/api/recent/search', {
    method: 'POST',
    body: JSON.stringify({ query, total }),
  })
}

export function fetchActiveTimer(): Promise<TimeTrackingPayload> {
  return requestJson<TimeTrackingPayload>('/api/time-tracking/active')
}

export type StartTimerInput = {
  caseId: string
  clientId: string
  activityType: TimeTrackingActivityType
  description: string
}

export function startTimer(input: StartTimerInput): Promise<TimeTrackingPayload> {
  return requestJson<TimeTrackingPayload>('/api/time-tracking/start', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function pauseTimer(id: string): Promise<TimeTrackingPayload> {
  return requestJson<TimeTrackingPayload>(`/api/time-tracking/${encodeURIComponent(id)}/pause`, { method: 'PATCH' })
}

export function resumeTimer(id: string): Promise<TimeTrackingPayload> {
  return requestJson<TimeTrackingPayload>(`/api/time-tracking/${encodeURIComponent(id)}/resume`, { method: 'PATCH' })
}

export function stopTimer(id: string, options: { description?: string; discard?: boolean } = {}): Promise<TimeTrackingPayload> {
  return requestJson<TimeTrackingPayload>(`/api/time-tracking/${encodeURIComponent(id)}/stop`, {
    method: 'PATCH',
    body: JSON.stringify(options),
  })
}

export function updateTimer(id: string, changes: Partial<StartTimerInput>): Promise<TimeTrackingPayload> {
  return requestJson<TimeTrackingPayload>(`/api/time-tracking/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  })
}

export function searchTimerLinks(query: string, ids: { caseId?: string; clientId?: string } = {}): Promise<{ ok: boolean; items: TimeTrackingLink[] }> {
  const params = new URLSearchParams({ q: query, caseId: ids.caseId || '', clientId: ids.clientId || '' })
  return requestJson<{ ok: boolean; items: TimeTrackingLink[] }>(`/api/time-tracking/links?${params.toString()}`)
}
