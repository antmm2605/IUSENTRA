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

  useEffect(() => {
    if (open && data === null && !loading) load()
  }, [data, load, loading, open])

  return { data, loading, error, reload: load }
}
