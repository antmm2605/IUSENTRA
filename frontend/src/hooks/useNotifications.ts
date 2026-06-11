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

  // Le notifiche si caricano solo quando il pannello viene aperto.
  useEffect(() => {
    if (!open) return
    load()
  }, [load, open])

  // Il refresh periodico resta attivo solo mentre l'avvocato consulta il pannello.
  useEffect(() => {
    if (!open) return
    const timer = window.setInterval(load, 30000)
    return () => window.clearInterval(timer)
  }, [load, open])

  useEffect(() => {
    const handleNotificationsUpdated = () => {
      if (open) load()
    }
    window.addEventListener('iusentra:notifications-updated', handleNotificationsUpdated)
    return () => window.removeEventListener('iusentra:notifications-updated', handleNotificationsUpdated)
  }, [load, open])

  return { data, loading, error, reload: load, markRead, markAllRead }
}
