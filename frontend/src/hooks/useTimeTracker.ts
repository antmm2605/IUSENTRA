import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchActiveTimer,
  pauseTimer,
  resumeTimer,
  startTimer,
  stopTimer,
  type StartTimerInput,
} from '../services/topbarApi'
import type { TimeTrackingTimer } from '../types/topbar'

function currentElapsed(timer: TimeTrackingTimer | null, tick: number) {
  if (!timer) return 0
  if (timer.status !== 'running') return timer.elapsedSeconds
  const started = Date.parse(timer.startedAt)
  if (!Number.isFinite(started)) return timer.elapsedSeconds
  return Math.max(0, timer.elapsedSeconds + Math.floor((tick - started) / 1000))
}

export function useTimeTracker() {
  const [timer, setTimer] = useState<TimeTrackingTimer | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(Date.now())

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    fetchActiveTimer()
      .then((payload) => setTimer(payload.timer))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Timer non disponibile.'))
      .finally(() => setLoading(false))
  }, [])

  const start = useCallback((input: StartTimerInput) => {
    setLoading(true)
    setError('')
    return startTimer(input)
      .then((payload) => setTimer(payload.timer))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Avvio non riuscito.'))
      .finally(() => setLoading(false))
  }, [])

  const pause = useCallback(() => {
    if (!timer) return Promise.resolve()
    setError('')
    return pauseTimer(timer.id)
      .then((payload) => setTimer(payload.timer))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Pausa non riuscita.'))
  }, [timer])

  const resume = useCallback(() => {
    if (!timer) return Promise.resolve()
    setError('')
    return resumeTimer(timer.id)
      .then((payload) => setTimer(payload.timer))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Ripresa non riuscita.'))
  }, [timer])

  const stop = useCallback(() => {
    if (!timer) return Promise.resolve()
    setError('')
    return stopTimer(timer.id)
      .then(() => setTimer(null))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Stop non riuscito.'))
  }, [timer])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!timer || timer.status !== 'running') return
    const handle = window.setInterval(() => setTick(Date.now()), 1000)
    return () => window.clearInterval(handle)
  }, [timer])

  const elapsedSeconds = useMemo(() => currentElapsed(timer, tick), [tick, timer])

  return { timer, elapsedSeconds, loading, error, reload: load, start, pause, resume, stop }
}
