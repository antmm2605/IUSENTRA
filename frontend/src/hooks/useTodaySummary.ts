import { useCallback, useEffect, useRef, useState } from 'react'
import { useOperationalRefresh } from './useOperationalRefresh'
import { useStudioToday } from './useStudioToday'
import { fetchTodaySummary } from '../services/topbarApi'
import type { TopbarTodayPayload } from '../types/topbar'

export function useTodaySummary(open: boolean) {
  const { date: today } = useStudioToday()
  const [data, setData] = useState<TopbarTodayPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const generation = useRef(0)

  const load = useCallback(() => {
    const ticket = ++generation.current
    setLoading(true)
    setError('')
    fetchTodaySummary(today)
      .then(result => { if (ticket === generation.current) setData(result) })
      .catch((reason: unknown) => { if (ticket === generation.current) setError(reason instanceof Error ? reason.message : 'Riepilogo non disponibile.') })
      .finally(() => { if (ticket === generation.current) setLoading(false) })
  }, [today])

  useEffect(() => {
    if (open) load()
    return () => { ++generation.current }
  }, [load, open])

  useOperationalRefresh(['agenda', 'scadenze', 'comunicazioni', 'timesheet', 'fascicoli'], () => { if (open) load() })

  return { data, loading, error, reload: load }
}
