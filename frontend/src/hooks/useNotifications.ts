import { useOperationalRefresh } from './useOperationalRefresh'
import { useBusyActivity } from '../ui/useBusyActivity'
import { beginActivity } from '../ui/activity'
import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from '../services/topbarApi'
import type { TopbarNotificationsPayload } from '../types/topbar'

export function useNotifications(open: boolean) {
  const [data, setData] = useState<TopbarNotificationsPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [mutating, setMutating] = useState(false)
  useBusyActivity(mutating, 'Registrazione della presa visione…')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [page, setPage] = useState(1)
  const [state, setState] = useState('all')
  const [query, setQuery] = useState('')
  const [filterRevision, setFilterRevision] = useState(0)
  const generation = useRef(0)
  const saving = useRef(false)
  const latestOptions = useRef({ page, state, query })
  latestOptions.current = { page, state, query }

  const load = useCallback(async (options: { silent?: boolean } = {}) => {
    const finish = options.silent ? () => {} : beginActivity('Caricamento delle notifiche…')
    const ticket = ++generation.current
    setLoading(true)
    setError('')
    try {
      const result = await fetchNotifications(latestOptions.current)
      if (ticket === generation.current) setData(result)
    } catch (reason) {
      if (ticket === generation.current) setError(reason instanceof Error ? reason.message : 'Notifiche non disponibili.')
    } finally {
      if (ticket === generation.current) setLoading(false)
      finish()
    }
  }, [])

  const save = useCallback(async (id?: string) => {
    if (saving.current) return
    saving.current = true
    ++generation.current
    setLoading(false)
    setMutating(true)
    setError('')
    setNotice('')
    try {
      if (id) await markNotificationRead(id)
      else await markAllNotificationsRead()
      setNotice(id ? 'Presa visione salvata.' : 'Tutte le notifiche sono state segnate come lette.')
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Presa visione non salvata. Riprova.')
    } finally {
      saving.current = false
      setMutating(false)
    }
  }, [load])

  const markRead = useCallback((id: string) => save(id), [save])
  const markAllRead = useCallback(() => save(), [save])
  const filter = useCallback((nextState: string, nextQuery: string) => {
    ++generation.current
    setData(null)
    setNotice('')
    setPage(1)
    setState(nextState)
    setQuery(nextQuery)
    setFilterRevision(current => current + 1)
  }, [])

  useEffect(() => {
    if (open) void load()
    return () => { ++generation.current }
  }, [load, open, page, query, state, filterRevision])

  useEffect(() => {
    if (!open) return
    const timer = window.setInterval(() => { if (!saving.current) void load({ silent: true }) }, 30000)
    return () => window.clearInterval(timer)
  }, [load, open])

  useEffect(() => {
    const updated = () => { if (open && !saving.current) void load({ silent: true }) }
    window.addEventListener('iusentra:notifications-updated', updated)
    return () => window.removeEventListener('iusentra:notifications-updated', updated)
  }, [load, open])

  useOperationalRefresh(['agenda', 'scadenze', 'comunicazioni'], () => { if (open && !saving.current) void load({ silent: true }) })

  return { data, loading, mutating, error, notice, page, state, query, filter, setPage, reload: load, markRead, markAllRead }
}
