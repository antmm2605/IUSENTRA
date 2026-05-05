import { useEffect, useMemo, useState } from 'react'
import { fetchGlobalSearch } from '../services/topbarApi'
import type { GlobalSearchResult, TopbarEntityType } from '../types/topbar'

type SearchState = {
  results: GlobalSearchResult[]
  loading: boolean
  error: string
  empty: boolean
}

export function useGlobalSearch(query: string, open: boolean) {
  const [state, setState] = useState<SearchState>({ results: [], loading: false, error: '', empty: false })
  const normalizedQuery = query.trim()

  useEffect(() => {
    if (!open || normalizedQuery.length < 2) {
      setState({ results: [], loading: false, error: '', empty: false })
      return
    }
    let active = true
    setState((current) => ({ ...current, loading: true, error: '', empty: false }))
    const timer = window.setTimeout(() => {
      fetchGlobalSearch(normalizedQuery, 24)
        .then((payload) => {
          if (!active) return
          const results = payload.results ?? []
          setState({ results, loading: false, error: '', empty: results.length === 0 })
        })
        .catch((error: unknown) => {
          if (!active) return
          const message = error instanceof Error ? error.message : 'Ricerca non disponibile.'
          setState({ results: [], loading: false, error: message, empty: false })
        })
    }, 260)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [normalizedQuery, open])

  const grouped = useMemo(() => {
    const groups = new Map<TopbarEntityType, GlobalSearchResult[]>()
    for (const result of state.results) {
      const current = groups.get(result.type) ?? []
      current.push(result)
      groups.set(result.type, current)
    }
    return Array.from(groups.entries()).map(([type, items]) => ({ type, items }))
  }, [state.results])

  return { ...state, grouped }
}
