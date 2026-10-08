import { useEffect, useState } from 'react'
import { formatDateIt, ITALIAN_TIME_ZONE } from '../formatting'

export function studioDay(now = new Date()) {
  return {
    date: formatDateIt(now).split('/').reverse().join('-'),
    label: new Intl.DateTimeFormat('it-IT', {
      timeZone: ITALIAN_TIME_ZONE,
      weekday: 'short', day: '2-digit', month: 'short',
    }).format(now),
  }
}

/** Cambia soltanto al nuovo giorno di Roma, anche dopo sospensione del PC. */
export function useStudioToday() {
  const [day, setDay] = useState(studioDay)
  useEffect(() => {
    const refresh = () => {
      const next = studioDay()
      setDay(previous => previous.date === next.date ? previous : next)
    }
    const interval = window.setInterval(refresh, 30_000)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(interval)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [])
  return day
}
