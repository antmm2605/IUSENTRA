import { useOperationalRefresh } from './useOperationalRefresh'
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

  // Le scadenze rapide si caricano solo quando il pannello viene aperto.
  useEffect(() => {
    if (!open) return
    load()
  }, [load, open])

  useEffect(() => {
    if (!open) return
    window.addEventListener('iusentra:scadenze-lette', load)
    return () => window.removeEventListener('iusentra:scadenze-lette', load)
  }, [open, load])

  // Il refresh periodico resta attivo solo durante la consultazione del pannello.
  useEffect(() => {
    if (!open) return
    const timer = window.setInterval(load, 120000)
    return () => window.clearInterval(timer)
  }, [load, open])

  useOperationalRefresh(['agenda', 'scadenze'], () => { if (open) load() })

  return { data, loading, error, reload: load }
}
