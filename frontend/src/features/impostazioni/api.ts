import { apiJson, apiPostJson } from '@/lib/apiClient'
import type { AiRuntimePayload, CalendarActionPayload, NotificationActionPayload, SettingsPayload, SettingsSection, TestResult } from './types'

export const emptySettingsPayload: SettingsPayload = {
  ok: false,
  source: '',
  generated_at: '',
  contracts: {
    mock_fallback: false,
    writes: 'json_api',
    route_owner: 'react_shell',
    operational: true,
    secrets_exposed: false,
    sensitive_settings: 'redacted_secret_values',
    can_update: false,
  },
  permissions: {
    can_read: false,
    can_update: false,
    can_test_connections: false,
    can_configure_ai: false,
    can_send_notifications: false,
    can_manage_backup: false,
    can_manage_calendar: false,
  },
  sections: [],
  local_signer: {
    version: '',
    base_url: 'http://127.0.0.1:27272',
    restart_protocol: 'iusentra-local-signer://restart',
    download_page: '/impostazioni?tab=firma',
    downloads: { windows: '/polisWeb/local-signer/setup/windows', macos: '/polisWeb/local-signer/setup/macos', linux: '/polisWeb/local-signer/setup/linux' },
    windows_filename: '',
    windows_tipo: '',
    macos_filename: '',
    linux_filename: '',
  },
  studio: {},
  pec: {},
  firma: {},
  smtp: {},
  whatsapp: {},
  scheduler: {},
  ai: {},
  pagamenti: {},
  notifiche: {},
  backup: {},
  calendari: {},
  warnings: [],
}

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function hasFile(files: Record<string, File | null>): boolean {
  return Object.values(files).some(Boolean)
}

function appendValue(formData: FormData, key: string, value: unknown) {
  if (value === undefined || value === null) return
  formData.append(key, typeof value === 'boolean' ? (value ? '1' : '') : String(value))
}

export function getSettings(signal?: AbortSignal): Promise<SettingsPayload> {
  return apiJson<SettingsPayload>('/api/v1/ui/impostazioni', emptySettingsPayload, { signal })
}

export async function saveSettingsSection(
  section: SettingsSection,
  values: Record<string, unknown>,
  files: Record<string, File | null> = {},
): Promise<SettingsPayload> {
  if (!hasFile(files)) {
    return apiPostJson<SettingsPayload>(`/api/v1/ui/impostazioni/${section}`, values, emptySettingsPayload)
  }
  const formData = new FormData()
  Object.entries(values).forEach(([key, value]) => appendValue(formData, key, value))
  Object.entries(files).forEach(([key, file]) => {
    if (file) formData.append(key, file)
  })
  try {
    const response = await fetch(`/api/v1/ui/impostazioni/${section}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken() },
      body: formData,
    })
    if (!response.ok) return emptySettingsPayload
    return await response.json() as SettingsPayload
  } catch {
    return emptySettingsPayload
  }
}

export function runSettingsTest(testId: string, values: Record<string, unknown>): Promise<TestResult> {
  return apiPostJson<TestResult>(`/api/v1/ui/impostazioni/test/${testId}`, values, {
    ok: false,
    message: 'Test non completato.',
  })
}

export function getAiStatus(): Promise<AiRuntimePayload> {
  return apiJson<AiRuntimePayload>('/api/v1/ui/impostazioni/ai/status', {
    ok: false,
    message: 'Stato AI locale non disponibile.',
    status_payload: {},
  })
}

export function bootstrapAi(force = false): Promise<AiRuntimePayload> {
  return apiPostJson<AiRuntimePayload>('/api/v1/ui/impostazioni/ai/bootstrap', { force }, {
    ok: false,
    message: 'Preparazione AI locale non completata.',
    status_payload: {},
  })
}

const emptyNotificationAction: NotificationActionPayload = {
  ok: false,
  message: 'Operazione non completata.',
}

export function prepareNotificationLink(values: Record<string, unknown>): Promise<NotificationActionPayload> {
  return apiPostJson<NotificationActionPayload>('/api/v1/ui/impostazioni/notifiche/link', values, emptyNotificationAction)
}

export function sendNotification(values: Record<string, unknown>): Promise<NotificationActionPayload> {
  return apiPostJson<NotificationActionPayload>('/api/v1/ui/impostazioni/notifiche/invia', values, emptyNotificationAction)
}

export function sendTomorrowReminders(): Promise<NotificationActionPayload> {
  return apiPostJson<NotificationActionPayload>('/api/v1/ui/impostazioni/notifiche/promemoria-domani', {}, emptyNotificationAction)
}

const emptyCalendarAction: CalendarActionPayload = {
  ok: false,
  message: 'Operazione non completata.',
  errors: {},
}

export function createCalendarProfile(values: Record<string, unknown>): Promise<CalendarActionPayload> {
  return apiPostJson<CalendarActionPayload>('/api/v1/ui/impostazioni/calendari/profili', values, emptyCalendarAction)
}

export function syncCalendarProfile(id: string): Promise<CalendarActionPayload> {
  return apiPostJson<CalendarActionPayload>(`/api/v1/ui/impostazioni/calendari/profili/${encodeURIComponent(id)}/sincronizza`, {}, emptyCalendarAction)
}

export function toggleCalendarProfile(id: string): Promise<CalendarActionPayload> {
  return apiPostJson<CalendarActionPayload>(`/api/v1/ui/impostazioni/calendari/profili/${encodeURIComponent(id)}/stato`, {}, emptyCalendarAction)
}

export function deleteCalendarProfile(id: string): Promise<CalendarActionPayload> {
  return apiPostJson<CalendarActionPayload>(`/api/v1/ui/impostazioni/calendari/profili/${encodeURIComponent(id)}/elimina`, {}, emptyCalendarAction)
}

export function regenerateCalendarLinks(): Promise<CalendarActionPayload> {
  return apiPostJson<CalendarActionPayload>('/api/v1/ui/impostazioni/calendari/rigenera-link', {}, emptyCalendarAction)
}
