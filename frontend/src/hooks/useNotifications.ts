import { useCallback, useEffect, useState } from 'react'
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from '../services/topbarApi'
import type { TopbarNotificationsPayload } from '../types/topbar'

export function useNotifications(open: boolean) {
  const [data, setData] = useState<TopbarNotificationsPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    fetchNotifications()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Notifiche non disponibili.'))
      .finally(() => setLoading(false))
  }, [])

  const markRead = useCallback((id: string) => {
    setError('')
    return markNotificationRead(id)
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Aggiornamento non riuscito.'))
  }, [])

  const markAllRead = useCallback(() => {
    setError('')
    return markAllNotificationsRead()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Aggiornamento non riuscito.'))
  }, [])

  useEffect(() => {
    if (open && data === null && !loading) load()
  }, [data, load, loading, open])

  return { data, loading, error, reload: load, markRead, markAllRead }
}
