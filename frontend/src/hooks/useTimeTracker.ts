import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchActiveTimer,
  pauseTimer,
  resumeTimer,
  startTimer,
  stopTimer,
  updateTimer,
  type StartTimerInput,
} from '../services/topbarApi'
import type { TimeTrackingLink, TimeTrackingPayload, TimeTrackingSaved, TimeTrackingTimer, TimeTrackingToday } from '../types/topbar'

/** Il server restituisce il tempo già trascorso al momento della risposta: si aggiunge solo quanto passato da allora. */
function currentElapsed(timer: TimeTrackingTimer | null, receivedAt: number, tick: number) {
  if (!timer) return 0
  if (timer.status !== 'running') return timer.elapsedSeconds
  return Math.max(0, timer.elapsedSeconds + Math.floor(Math.max(0, tick - receivedAt) / 1000))
}

const messaggio = (reason: unknown, fallback: string) => (reason instanceof Error && reason.message ? reason.message : fallback)

/** Timer attività della top bar: stato, ore di oggi, ultimi fascicoli e registrazione nel timesheet. */
export function useTimeTracker() {
  const [timer, setTimer] = useState<TimeTrackingTimer | null>(null)
  const [today, setToday] = useState<TimeTrackingToday | null>(null)
  const [recent, setRecent] = useState<TimeTrackingLink[]>([])
  const [saved, setSaved] = useState<TimeTrackingSaved | null>(null)
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(Date.now())
  const [receivedAt, setReceivedAt] = useState(Date.now())

  const applica = useCallback((payload: TimeTrackingPayload) => {
    setTimer(payload.timer && payload.timer.status !== 'stopped' ? payload.timer : null)
    if (payload.today) setToday(payload.today)
    if (payload.recent) setRecent(payload.recent)
    const adesso = Date.now()
    setReceivedAt(adesso)
    setTick(adesso)
  }, [])

  const load = useCallback(() => {
    setError('')
    return fetchActiveTimer().then(applica).catch((reason: unknown) => setError(messaggio(reason, 'Timer non disponibile.')))
  }, [applica])

  const start = useCallback((input: StartTimerInput) => {
    setLoading(true)
    setError('')
    setSaved(null)
    setNotice('')
    return startTimer(input)
      .then(applica)
      .catch((reason: unknown) => setError(messaggio(reason, 'Avvio non riuscito.')))
      .finally(() => setLoading(false))
  }, [applica])

  const pause = useCallback(() => {
    if (!timer) return Promise.resolve()
    setError('')
    return pauseTimer(timer.id).then(applica).catch((reason: unknown) => setError(messaggio(reason, 'Pausa non riuscita.')))
  }, [applica, timer])

  const resume = useCallback(() => {
    if (!timer) return Promise.resolve()
    setError('')
    return resumeTimer(timer.id).then(applica).catch((reason: unknown) => setError(messaggio(reason, 'Ripresa non riuscita.')))
  }, [applica, timer])

  const update = useCallback((changes: Partial<StartTimerInput>) => {
    if (!timer) return Promise.resolve()
    setError('')
    return updateTimer(timer.id, changes).then(applica).catch((reason: unknown) => setError(messaggio(reason, 'Modifica non salvata.')))
  }, [applica, timer])

  const stop = useCallback((options: { description?: string; discard?: boolean } = {}) => {
    if (!timer) return Promise.resolve()
    setLoading(true)
    setError('')
    return stopTimer(timer.id, options)
      .then((payload) => {
        applica(payload)
        setSaved(payload.saved ?? null)
        setNotice(payload.message ?? '')
      })
      .catch((reason: unknown) => setError(messaggio(reason, 'Non riesco a fermare il timer.')))
      .finally(() => setLoading(false))
  }, [applica, timer])

  const dismiss = useCallback(() => {
    setSaved(null)
    setNotice('')
  }, [])

  useEffect(() => {
    const handle = window.setTimeout(() => void load(), 1200)
    return () => window.clearTimeout(handle)
  }, [load])

  useEffect(() => {
    if (!timer || timer.status !== 'running') return
    const handle = window.setInterval(() => setTick(Date.now()), 1000)
    return () => window.clearInterval(handle)
  }, [timer])

  const elapsedSeconds = useMemo(() => currentElapsed(timer, receivedAt, tick), [receivedAt, tick, timer])

  return { timer, elapsedSeconds, today, recent, saved, notice, loading, error, reload: load, start, pause, resume, update, stop, dismiss }
}
