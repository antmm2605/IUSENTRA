import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import type { FascicoloDocument } from '../../fascicoliData'
import {
  DEFAULT_DOCUMENT_SORT,
  buildDocumentHaystack,
  compareDocuments,
  isDocumentSortKey,
  matchesSearchTerms,
  searchTerms,
  type DocumentSortKey,
} from './documentListOrdering'

export type DocumentStatusFilter = 'tutti' | 'da_firmare' | 'da_verificare'

export type DocumentListEntry<T> = {
  id: string
  document: FascicoloDocument
  sectionId: string
  pendingReview: boolean
  searchExtra: string[]
  value: T
}

const SORT_STORAGE_KEY = 'iusentra.fascicolo.documenti.ordinamento'

function readStoredSort(): DocumentSortKey {
  try {
    const stored = window.localStorage.getItem(SORT_STORAGE_KEY)
    return isDocumentSortKey(stored) ? stored : DEFAULT_DOCUMENT_SORT
  } catch {
    return DEFAULT_DOCUMENT_SORT
  }
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

function matchesStatus<T>(entry: DocumentListEntry<T>, status: DocumentStatusFilter): boolean {
  if (status === 'da_firmare') return !entry.document.signed
  if (status === 'da_verificare') return entry.pendingReview
  return true
}

export function useDocumentListControls<T>(entries: DocumentListEntry<T>[]) {
  const [query, setQuery] = useState('')
  const [sort, setSortState] = useState<DocumentSortKey>(readStoredSort)
  const [section, setSection] = useState('tutte')
  const [status, setStatus] = useState<DocumentStatusFilter>('tutti')
  const searchRef = useRef<HTMLInputElement>(null)
  const deferredQuery = useDeferredValue(query)

  const setSort = useCallback((next: DocumentSortKey) => {
    setSortState(next)
    try {
      window.localStorage.setItem(SORT_STORAGE_KEY, next)
    } catch {
      // Preferenza non persistibile (navigazione privata): l'ordinamento resta valido nella sessione.
    }
  }, [])

  const indexed = useMemo(
    () => entries.map((entry) => ({ entry, haystack: buildDocumentHaystack(entry.document, entry.searchExtra) })),
    [entries],
  )

  const terms = useMemo(() => searchTerms(deferredQuery), [deferredQuery])

  const matchingQuery = useMemo(
    () => (terms.length ? indexed.filter((item) => matchesSearchTerms(item.haystack, terms)) : indexed).map((item) => item.entry),
    [indexed, terms],
  )

  const sectionCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const entry of matchingQuery) {
      if (!matchesStatus(entry, status)) continue
      counts.set(entry.sectionId, (counts.get(entry.sectionId) || 0) + 1)
    }
    return counts
  }, [matchingQuery, status])

  const statusCounts = useMemo(() => {
    const inSection = matchingQuery.filter((entry) => section === 'tutte' || entry.sectionId === section)
    return {
      tutti: inSection.length,
      da_firmare: inSection.filter((entry) => matchesStatus(entry, 'da_firmare')).length,
      da_verificare: inSection.filter((entry) => matchesStatus(entry, 'da_verificare')).length,
    } satisfies Record<DocumentStatusFilter, number>
  }, [matchingQuery, section])

  const visible = useMemo(
    () => matchingQuery
      .filter((entry) => (section === 'tutte' || entry.sectionId === section) && matchesStatus(entry, status))
      .sort((a, b) => compareDocuments(sort, a.document, b.document)),
    [matchingQuery, section, status, sort],
  )

  const filtersActive = Boolean(query.trim()) || section !== 'tutte' || status !== 'tutti'

  const resetFilters = useCallback(() => {
    setQuery('')
    setSection('tutte')
    setStatus('tutti')
    searchRef.current?.focus()
  }, [])

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) return
      const input = searchRef.current
      if (!input || !input.isConnected) return
      event.preventDefault()
      input.focus()
      input.select()
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  return {
    query,
    setQuery,
    sort,
    setSort,
    section,
    setSection,
    status,
    setStatus,
    searchRef,
    visible,
    total: entries.length,
    sectionCounts,
    statusCounts,
    filtersActive,
    resetFilters,
  }
}

export type DocumentListControls<T> = ReturnType<typeof useDocumentListControls<T>>
