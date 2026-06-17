import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchRecentItems } from '../services/topbarApi'
import type { TopbarRecentPayload } from '../types/topbar'

export function useRecentItems(open: boolean) {
  const [data, setData] = useState<TopbarRecentPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef<Promise<void> | null>(null)
  const loadedAt = useRef(0)

  const load = useCallback((force = false) => {
    if (!force && loadedAt.current && Date.now() - loadedAt.current < 15000) return
    if (inFlight.current) return
    setLoading(true)
    setError('')
    inFlight.current = fetchRecentItems()
      .then(setData)
      .then(() => { loadedAt.current = Date.now() })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Recenti non disponibili.'))
      .finally(() => {
        inFlight.current = null
        setLoading(false)
      })
  }, [])

  // Prefetch leggero dopo il primo rendering: la pagina operativa resta prioritaria.
  useEffect(() => {
    const handle = window.setTimeout(() => load(), 1200)
    return () => window.clearTimeout(handle)
  }, [load])

  useEffect(() => {
    const refresh = () => {
      loadedAt.current = 0
      if (open) load(true)
    }
    window.addEventListener('iusentra:recent-items-updated', refresh)
    return () => window.removeEventListener('iusentra:recent-items-updated', refresh)
  }, [load, open])

  // Refresh ad ogni apertura del pannello (cattura nuove navigazioni avvenute nel frattempo).
  useEffect(() => {
    if (open) load()
  }, [load, open])

  return { data, loading, error, reload: load }
}
