import { useCallback, useEffect, useMemo, useRef, useState, type FocusEvent } from 'react'

/**
 * Bozza automatica delle anagrafiche (Nuovo cliente / Nuovo soggetto e modifiche).
 *
 * Ogni volta che l'avvocato lascia un campo compilato (passa al successivo) la scheda viene salvata
 * come bozza in questo browser, per utente e per scheda. Riaprendo "Nuovo cliente" la bozza viene
 * ripristinata; in modifica viene solo proposta, per non sovrascrivere dati più recenti del server.
 * La bozza si cancella quando la scheda viene salvata davvero o con "Scarta bozza", e scade dopo 7 giorni.
 */

export type DraftValues = Record<string, string | boolean>

export type AnagraficaDraftStatus = {
  tone: 'neutral' | 'success' | 'warning'
  message: string
  savedAt: string
  pendingRestore: boolean
}

type StoredDraft = {
  version: 1
  savedAt: string
  values: DraftValues
  protectedFields?: string[]
}

export const ANAGRAFICA_DRAFT_TTL_MS = 7 * 24 * 60 * 60 * 1000
const STORAGE_PREFIX = 'iusentra:bozza-anagrafica:v1'
const SKIPPED_INPUT_TYPES = new Set(['file', 'hidden', 'password', 'submit', 'button', 'search'])

function currentUsername(): string {
  try {
    const element = document.getElementById('iusentra-react-bootstrap')
    const parsed = element?.textContent ? JSON.parse(element.textContent) as { user?: { username?: string } } : {}
    return String(parsed.user?.username || 'utente').trim() || 'utente'
  } catch {
    return 'utente'
  }
}

export function anagraficaDraftKey(kind: 'cliente' | 'soggetto', recordId = '', contextId = ''): string {
  const parts = [currentUsername(), kind, recordId || 'nuovo', contextId || 'libero'].map((part) => encodeURIComponent(part))
  return [STORAGE_PREFIX, ...parts].join(':')
}

export function readAnagraficaDraft(key: string, now = Date.now()): StoredDraft | null {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredDraft>
    const savedAt = Date.parse(String(parsed.savedAt || ''))
    if (parsed.version !== 1 || !parsed.values || typeof parsed.values !== 'object' || Number.isNaN(savedAt)) return null
    if (now - savedAt > ANAGRAFICA_DRAFT_TTL_MS) {
      window.localStorage.removeItem(key)
      return null
    }
    const protectedFields = Array.isArray(parsed.protectedFields)
      ? parsed.protectedFields.filter((key): key is string => typeof key === 'string' && Object.hasOwn(parsed.values!, key))
      : undefined
    return { version: 1, savedAt: String(parsed.savedAt), values: parsed.values as DraftValues, protectedFields }
  } catch {
    return null
  }
}

function writeDraft(key: string, values: DraftValues, protectedFields: string[]): string {
  const savedAt = new Date().toISOString()
  try {
    window.localStorage.setItem(key, JSON.stringify({ version: 1, savedAt, values, protectedFields } satisfies StoredDraft))
    return savedAt
  } catch {
    return ''
  }
}

function removeDraft(key: string) {
  try {
    window.localStorage.removeItem(key)
  } catch {
    // Il browser può bloccare lo storage: la scheda resta comunque compilabile e salvabile.
  }
}

export function draftDiffers(values: DraftValues, initial: DraftValues, excluded: string[] = []): boolean {
  const skip = new Set(excluded)
  const keys = new Set([...Object.keys(values), ...Object.keys(initial)])
  for (const key of keys) {
    if (skip.has(key)) continue
    const current = values[key]
    const base = initial[key]
    const normalizedCurrent = typeof current === 'boolean' ? current : String(current ?? '').trim()
    const normalizedBase = typeof base === 'boolean' ? base : String(base ?? '').trim()
    if (normalizedCurrent !== normalizedBase) return true
  }
  return false
}

function pickDraftValues(values: DraftValues, excluded: string[]): DraftValues {
  const skip = new Set(excluded)
  return Object.fromEntries(Object.entries(values).filter(([key]) => !skip.has(key)))
}

export function restoredProtectedFields(stored: StoredDraft, initial: DraftValues, excluded: string[] = []): string[] {
  const values = pickDraftValues(stored.values, excluded)
  // Le bozze storiche non distinguono i campi manuali: proteggere i soli
  // valori diversi dalla base, comprese cancellazioni di valori preesistenti.
  return stored.protectedFields === undefined
    ? Object.keys(values).filter((key) => draftDiffers({ [key]: values[key] }, { [key]: initial[key] }))
    : stored.protectedFields.filter((key) => Object.hasOwn(values, key))
}

function formatSavedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const sameDay = date.toDateString() === new Date().toDateString()
  const time = date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  return sameDay ? `alle ${time}` : `il ${date.toLocaleDateString('it-IT')} alle ${time}`
}

function fieldLabel(target: HTMLElement): string {
  const label = target.closest('label')
  const text = label?.querySelector('span')?.textContent || target.getAttribute('aria-label') || target.getAttribute('name') || ''
  return text.replace(/\*/g, '').trim()
}

export function useAnagraficaDraft<T extends DraftValues>({
  storageKey,
  ready,
  autoRestore,
  values,
  initialValues,
  onRestore,
  protectedFields = new Set<string>(),
  excludedFields = [],
}: {
  storageKey: string
  ready: boolean
  autoRestore: boolean
  values: T
  initialValues: T
  onRestore: (draft: Partial<T>, protectedFields: string[]) => void
  protectedFields?: ReadonlySet<string>
  excludedFields?: string[]
}) {
  const [status, setStatus] = useState<AnagraficaDraftStatus>({ tone: 'neutral', message: '', savedAt: '', pendingRestore: false })
  const valuesRef = useRef(values)
  const protectedFieldsRef = useRef(protectedFields)
  const lastSavedRef = useRef('')
  const restoredKeyRef = useRef('')
  const pendingRestoreRef = useRef(false)
  const onRestoreRef = useRef(onRestore)
  const excludedKey = excludedFields.join('|')
  const excluded = useMemo(() => excludedKey ? excludedKey.split('|') : [], [excludedKey])

  valuesRef.current = values
  protectedFieldsRef.current = protectedFields
  onRestoreRef.current = onRestore

  useEffect(() => {
    if (!ready || restoredKeyRef.current === storageKey) return
    restoredKeyRef.current = storageKey
    pendingRestoreRef.current = false
    const stored = readAnagraficaDraft(storageKey)
    if (!stored) return
    const restoredFields = restoredProtectedFields(stored, initialValues, excluded)
    if (!draftDiffers(stored.values, initialValues, excluded) && !restoredFields.length) return
    lastSavedRef.current = JSON.stringify({ values: pickDraftValues(stored.values, excluded), protectedFields: restoredFields.sort() })
    if (autoRestore) {
      onRestoreRef.current(pickDraftValues(stored.values, excluded) as Partial<T>, restoredFields)
      setStatus({ tone: 'success', message: `Bozza ripristinata: dati salvati automaticamente ${formatSavedAt(stored.savedAt)}.`, savedAt: stored.savedAt, pendingRestore: false })
    } else {
      pendingRestoreRef.current = true
      setStatus({ tone: 'warning', message: `C'è una bozza non salvata di questa scheda (${formatSavedAt(stored.savedAt)}).`, savedAt: stored.savedAt, pendingRestore: true })
    }
  }, [autoRestore, excluded, initialValues, ready, storageKey])

  const saveNow = useCallback((label = '') => {
    // Focus/blur e pagehide non possono eliminare o sostituire la bozza
    // precedente mentre l'avvocato deve ancora scegliere se ripristinarla.
    if (pendingRestoreRef.current) return
    const snapshot = pickDraftValues(valuesRef.current, excluded)
    const manualFields = [...protectedFieldsRef.current].filter((key) => Object.hasOwn(snapshot, key)).sort()
    const serialized = JSON.stringify({ values: snapshot, protectedFields: manualFields })
    if (serialized === lastSavedRef.current) return
    if (!draftDiffers(snapshot, initialValues, excluded) && !manualFields.length) {
      removeDraft(storageKey)
      lastSavedRef.current = serialized
      return
    }
    const savedAt = writeDraft(storageKey, snapshot, manualFields)
    lastSavedRef.current = serialized
    if (!savedAt) {
      setStatus({ tone: 'warning', message: 'Il browser non consente il salvataggio automatico della bozza: ricorda di salvare la scheda.', savedAt: '', pendingRestore: false })
      return
    }
    setStatus((current) => ({
      tone: 'success',
      message: `${label ? `«${label}» salvato` : 'Bozza salvata'} automaticamente ${formatSavedAt(savedAt)}.`,
      savedAt,
      pendingRestore: current.pendingRestore,
    }))
  }, [excluded, initialValues, storageKey])

  const handleBlur = useCallback((event: FocusEvent<HTMLFormElement>) => {
    const target = event.target as HTMLElement
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement)) return
    if (target instanceof HTMLInputElement && SKIPPED_INPUT_TYPES.has(target.type)) return
    if (!target.name) return
    // Il valore aggiornato arriva con l'ultimo onChange: si salva al passaggio al campo successivo.
    window.setTimeout(() => saveNow(fieldLabel(target)), 0)
  }, [saveNow])

  useEffect(() => {
    const flush = () => saveNow()
    window.addEventListener('pagehide', flush)
    return () => window.removeEventListener('pagehide', flush)
  }, [saveNow])

  const restore = useCallback(() => {
    const stored = readAnagraficaDraft(storageKey)
    if (!stored) {
      pendingRestoreRef.current = false
      setStatus({ tone: 'neutral', message: 'La bozza non è più disponibile.', savedAt: '', pendingRestore: false })
      return
    }
    const restoredFields = restoredProtectedFields(stored, initialValues, excluded)
    onRestoreRef.current(pickDraftValues(stored.values, excluded) as Partial<T>, restoredFields)
    pendingRestoreRef.current = false
    lastSavedRef.current = JSON.stringify({ values: pickDraftValues(stored.values, excluded), protectedFields: restoredFields.sort() })
    setStatus({ tone: 'success', message: `Bozza ripristinata (${formatSavedAt(stored.savedAt)}): verifica i dati e salva.`, savedAt: stored.savedAt, pendingRestore: false })
  }, [excluded, initialValues, storageKey])

  const discard = useCallback((resetValues = true) => {
    pendingRestoreRef.current = false
    removeDraft(storageKey)
    lastSavedRef.current = JSON.stringify(pickDraftValues(resetValues ? initialValues : valuesRef.current, excluded))
    if (resetValues) onRestoreRef.current(pickDraftValues(initialValues, excluded) as Partial<T>, [])
    setStatus({ tone: 'neutral', message: resetValues ? 'Bozza scartata.' : '', savedAt: '', pendingRestore: false })
  }, [excluded, initialValues, storageKey])

  const clearAfterSave = useCallback(() => {
    pendingRestoreRef.current = false
    removeDraft(storageKey)
    lastSavedRef.current = JSON.stringify(pickDraftValues(valuesRef.current, excluded))
    setStatus({ tone: 'neutral', message: '', savedAt: '', pendingRestore: false })
  }, [excluded, storageKey])

  return { status, handleBlur, restore, discard, clearAfterSave }
}
