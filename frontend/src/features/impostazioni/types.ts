export type SettingsSection =
  | 'studio'
  | 'pec'
  | 'firma'
  | 'smtp'
  | 'whatsapp'
  | 'scheduler'
  | 'ai'
  | 'sdi'
  | 'pagamenti'
  | 'notifiche'
  | 'backup'
  | 'calendari'

export type SettingTone = 'primary' | 'success' | 'warning' | 'danger' | 'neutral' | 'info'

export type SecretState = {
  present: boolean
  label: string
  placeholder: string
}

export type SectionStatus = {
  label: string
  status: string
  tone: SettingTone
  note: string
}

export type SettingsContracts = {
  mock_fallback: boolean
  writes: string
  route_owner: string
  operational: boolean
  secrets_exposed: boolean
  sensitive_settings: string
  can_update: boolean
  legacy_contract?: string
}

export type SettingsPayload = {
  ok: boolean
  source: string
  generated_at: string
  contracts: SettingsContracts
  permissions: {
    can_read: boolean
    can_update: boolean
    can_test_connections: boolean
    can_configure_ai: boolean
    can_send_notifications?: boolean
    can_manage_backup?: boolean
    can_manage_calendar?: boolean
  }
  sections: SectionStatus[]
  local_signer: {
    version: string
    base_url: string
    restart_protocol: string
    download_page: string
    downloads: { windows: string; macos: string; linux: string }
    windows_filename: string
    windows_tipo: string
    macos_filename: string
    linux_filename: string
  }
  studio: Record<string, string | number | boolean>
  pec: Record<string, string | number | boolean | SecretState>
  firma: Record<string, string | number | boolean | SecretState>
  smtp: Record<string, string | number | boolean | SecretState>
  whatsapp: Record<string, string | number | boolean | SecretState>
  scheduler: Record<string, string | number | boolean>
  ai: Record<string, string | number | boolean>
  sdi: Record<string, string | number | boolean | SecretState | unknown>
  pagamenti: Record<string, unknown>
  notifiche: Record<string, unknown>
  backup: Record<string, unknown>
  calendari: Record<string, unknown>
  warnings: Array<{ code: string; message: string }>
  message?: string
  updated_section?: SettingsSection
}

export type SettingsField = {
  name: string
  label: string
  type?: 'text' | 'email' | 'url' | 'password' | 'number' | 'time' | 'checkbox' | 'select' | 'file'
  placeholder?: string
  help?: string
  helpLink?: { label: string; href: string }
  required?: boolean
  width?: 'full' | 'half' | 'third'
  options?: Array<{ value: string; label: string }>
  accept?: string
  min?: number
  max?: number
}

export type TestResult = {
  ok: boolean
  message: string
}

export type AiRuntimePayload = {
  ok: boolean
  message?: string
  status_payload: Record<string, unknown>
  result?: Record<string, unknown>
}

export type NotificationActionPayload = {
  ok: boolean
  message: string
  link?: string
  payload?: Record<string, unknown>
  results?: unknown[]
}

export type CalendarActionPayload = {
  ok: boolean
  message: string
  errors?: Record<string, string>
  profile?: Record<string, unknown>
  report?: Record<string, unknown>
}
