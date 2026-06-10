import { useCallback, useEffect, useState } from 'react'
import { fetchQuickDeadlines } from '../services/topbarApi'
import type { TopbarDeadlinesPayload } from '../types/topbar'

export function useQuickDeadlines(open: boolean) {
  const [data, setData] = useState<TopbarDeadlinesPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    fetchQuickDeadlines()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Scadenze non disponibili.'))
      .finally(() => setLoading(false))
  }, [])

  // Pre-fetch al mount per badge contatore + refresh ad ogni apertura.
  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (open) load()
  }, [load, open])

  // Polling soft ogni 2 minuti per scadenze urgenti nuove.
  useEffect(() => {
    const timer = window.setInterval(load, 120000)
    return () => window.clearInterval(timer)
  }, [load])

  return { data, loading, error, reload: load }
}
