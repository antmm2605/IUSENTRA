import { useCallback, useEffect, useState } from 'react'
import { fetchTodaySummary } from '../services/topbarApi'
import type { TopbarTodayPayload } from '../types/topbar'

export function useTodaySummary(open: boolean) {
  const [data, setData] = useState<TopbarTodayPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    const today = new Date().toISOString().slice(0, 10)
    fetchTodaySummary(today)
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Riepilogo non disponibile.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (open && data === null && !loading && !error) load()
  }, [data, error, load, loading, open])

  return { data, loading, error, reload: load }
}
