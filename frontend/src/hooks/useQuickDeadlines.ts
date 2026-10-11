import { useOperationalRefresh } from './useOperationalRefresh'
import { beginActivity } from '../ui/activity'
import { useCallback, useEffect, useState } from 'react'
import { fetchQuickDeadlines } from '../services/topbarApi'
import type { TopbarDeadlinesPayload } from '../types/topbar'

export function useQuickDeadlines(open: boolean) {
  const [data, setData] = useState<TopbarDeadlinesPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback((options: { silent?: boolean } = {}) => {
    const finish = options.silent ? () => {} : beginActivity('Caricamento delle scadenze…')
    setLoading(true)
    setError('')
    fetchQuickDeadlines()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Scadenze non disponibili.'))
      .finally(() => { setLoading(false); finish() })
  }, [])

  // Le scadenze rapide si caricano solo quando il pannello viene aperto.
  useEffect(() => {
    if (!open) return
    load()
  }, [load, open])

  useEffect(() => {
    if (!open) return
    const updated = () => load({ silent: true })
    window.addEventListener('iusentra:scadenze-lette', updated)
    return () => window.removeEventListener('iusentra:scadenze-lette', updated)
  }, [open, load])

  // Il refresh periodico resta attivo solo durante la consultazione del pannello.
  useEffect(() => {
    if (!open) return
    const timer = window.setInterval(() => load({ silent: true }), 120000)
    return () => window.clearInterval(timer)
  }, [load, open])

  useOperationalRefresh(['agenda', 'scadenze'], () => { if (open) load({ silent: true }) })

  return { data, loading, error, reload: load }
}
