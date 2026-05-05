import { useCallback, useEffect, useState } from 'react'
import { fetchRecentItems } from '../services/topbarApi'
import type { TopbarRecentPayload } from '../types/topbar'

export function useRecentItems(open: boolean) {
  const [data, setData] = useState<TopbarRecentPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    fetchRecentItems()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Recenti non disponibili.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (open && data === null && !loading) load()
  }, [data, load, loading, open])

  return { data, loading, error, reload: load }
}
