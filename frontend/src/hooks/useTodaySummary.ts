import { useCallback, useEffect, useRef, useState } from 'react'
import { useOperationalRefresh } from './useOperationalRefresh'
import { useStudioToday } from './useStudioToday'
import { beginActivity } from '../ui/activity'
import { fetchTodaySummary } from '../services/topbarApi'
import type { TopbarTodayPayload } from '../types/topbar'

export function useTodaySummary(open: boolean) {
  const { date: today } = useStudioToday()
  const [data, setData] = useState<TopbarTodayPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const generation = useRef(0)

  const load = useCallback((silent = false) => {
    const finish = silent ? () => {} : beginActivity('Caricamento del riepilogo di oggi…')
    const ticket = ++generation.current
    setLoading(true)
    setError('')
    fetchTodaySummary(today)
      .then(result => { if (ticket === generation.current) setData(result) })
      .catch((reason: unknown) => { if (ticket === generation.current) setError(reason instanceof Error ? reason.message : 'Riepilogo non disponibile.') })
      .finally(() => { finish(); if (ticket === generation.current) setLoading(false) })
  }, [today])

  useEffect(() => {
    if (open) load()
    return () => { ++generation.current }
  }, [load, open])

  useOperationalRefresh(['agenda', 'scadenze', 'comunicazioni', 'timesheet', 'fascicoli'], () => { if (open) load(true) })

  return { data, loading, error, reload: () => load() }
}
