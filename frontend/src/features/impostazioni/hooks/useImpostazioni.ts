import { useCallback, useEffect, useMemo, useState } from 'react'
import { SETTINGS_SECTIONS } from '../constants'
import {
  bootstrapAi,
  emptySettingsPayload,
  getAiStatus,
  getSettings,
  runSettingsTest,
  saveSettingsSection,
} from '../api'
import type { AiRuntimePayload, SettingsPayload, SettingsSection, TestResult } from '../types'

export function sectionFromUrl(): SettingsSection {
  const path = window.location.pathname.replace(/\/+$/, '').toLowerCase()
  if (path === '/impostazioni/pagamenti') return 'pagamenti'
  if (path === '/impostazioni/sdi' || path === '/impostazioni/canali-sdi') return 'sdi'
  if (path === '/notifiche' || path === '/notifiche-whatsapp') return 'notifiche'
  if (path === '/backup') return 'backup'
  if (path === '/impostazioni/calendario' || path === '/sincronizzazione-calendari') return 'calendari'
  const raw = new URLSearchParams(window.location.search).get('tab') || window.location.hash.replace('#', '')
  const normalized = raw.trim().toLowerCase()
  if (normalized === 'canali-sdi') return 'sdi'
  if (normalized === 'calendario' || normalized === 'sincronizzazione-calendari') return 'calendari'
  return SETTINGS_SECTIONS.some((section) => section.id === normalized) ? normalized as SettingsSection : 'studio'
}

export function payloadForSection(data: SettingsPayload, section: SettingsSection): Record<string, unknown> {
  const raw = data[section]
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  return Object.fromEntries(
    Object.entries(raw as Record<string, unknown>).map(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value) && 'present' in value) return [key, '']
      return [key, value]
    }),
  )
}

export function rawPayloadForSection(data: SettingsPayload, section: SettingsSection): Record<string, unknown> {
  const raw = data[section]
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {}
}

export function useImpostazioni() {
  const [data, setData] = useState<SettingsPayload>(emptySettingsPayload)
  const [activeSection, setActiveSection] = useState<SettingsSection>(() => sectionFromUrl())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<SettingsSection | ''>('')
  const [message, setMessage] = useState('')
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [aiStatus, setAiStatus] = useState<AiRuntimePayload | null>(null)

  const load = useCallback(() => {
    const controller = new AbortController()
    setLoading(true)
    getSettings(controller.signal)
      .then((payload) => {
        setData(payload)
        setMessage(payload.ok ? '' : payload.warnings[0]?.message || 'Impostazioni non disponibili.')
      })
      .catch((error) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setMessage('Impostazioni non disponibili.')
        }
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  useEffect(() => load(), [load])

  const openSection = useCallback((section: SettingsSection) => {
    setActiveSection(section)
    const url = new URL(window.location.href)
    url.searchParams.set('tab', section)
    window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}`)
  }, [])

  const values = useMemo(() => payloadForSection(data, activeSection), [activeSection, data])

  const save = useCallback(async (
    section: SettingsSection,
    valuesToSave: Record<string, unknown>,
    files: Record<string, File | null> = {},
  ) => {
    setSaving(section)
    setMessage('')
    const payload = await saveSettingsSection(section, valuesToSave, files)
    setSaving('')
    setData(payload.ok ? payload : data)
    setMessage(payload.message || (payload.ok ? 'Impostazioni salvate.' : 'Salvataggio non completato.'))
    return payload.ok
  }, [data])

  const test = useCallback(async (testId: string, valuesToTest: Record<string, unknown>) => {
    setTestResult({ ok: false, message: 'Test in corso...' })
    const result = await runSettingsTest(testId, valuesToTest)
    setTestResult(result)
    return result
  }, [])

  const refreshAi = useCallback(async () => {
    const result = await getAiStatus()
    setAiStatus(result)
    return result
  }, [])

  useEffect(() => {
    if (activeSection !== 'ai' || aiStatus) return
    void refreshAi().catch(() => undefined)
  }, [activeSection, aiStatus, refreshAi])

  const prepareAi = useCallback(async (force = false) => {
    const result = await bootstrapAi(force)
    setAiStatus(result)
    return result
  }, [])

  return {
    data,
    activeSection,
    loading,
    saving,
    message,
    testResult,
    aiStatus,
    values,
    load,
    openSection,
    save,
    test,
    refreshAi,
    prepareAi,
  }
}
