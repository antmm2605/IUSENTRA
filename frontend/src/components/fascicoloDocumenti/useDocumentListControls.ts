import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import type { FascicoloDocument } from '../../fascicoliData'
import {
  DEFAULT_DOCUMENT_SORT,
  compareDocuments,
  isDocumentSortKey,
  type DocumentSortKey,
} from './documentListOrdering'
import { buildDocumentSearchIndex, searchDocumentIndex, type DocumentSearchMode } from './documentSearch'

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
    () => entries.map((entry) => ({ item: entry, index: buildDocumentSearchIndex(entry.document, entry.searchExtra) })),
    [entries],
  )

  // Ricerca per pertinenza: sigle e sinonimi forensi, radici, refusi e date in
  // qualunque formato; se nessun documento contiene tutti i termini propone i più simili.
  const searchResult = useMemo(() => searchDocumentIndex(indexed, deferredQuery), [indexed, deferredQuery])
  const searchMode: DocumentSearchMode = searchResult.mode
  const relevanceActive = searchMode === 'esatta' || searchMode === 'simili'

  const relevanceRank = useMemo(
    () => new Map(searchResult.items.map(({ item }, position) => [item.id, position])),
    [searchResult],
  )

  const matchingQuery = useMemo(() => searchResult.items.map(({ item }) => item), [searchResult])

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
      .sort((a, b) => (relevanceActive ? (relevanceRank.get(a.id) ?? 0) - (relevanceRank.get(b.id) ?? 0) : 0) || compareDocuments(sort, a.document, b.document)),
    [matchingQuery, section, status, sort, relevanceActive, relevanceRank],
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
    searchMode,
    relevanceActive,
    total: entries.length,
    sectionCounts,
    statusCounts,
    filtersActive,
    resetFilters,
  }
}

export type DocumentListControls<T> = ReturnType<typeof useDocumentListControls<T>>
