import { useEffect, useState, useSyncExternalStore } from 'react'
import { createPortal } from 'react-dom'
import { getActivities, subscribeActivities } from './activity'
import './activity.css'

export function ActivityStatus() {
  const activities = useSyncExternalStore(subscribeActivities, getActivities, getActivities)
  const first = activities[0]
  const [shownId, setShownId] = useState<number>()
  const [slowId, setSlowId] = useState<number>()
  const [fullscreen, setFullscreen] = useState<Element | null>(() => document.fullscreenElement)
  useEffect(() => {
    const changed = () => setFullscreen(document.fullscreenElement)
    document.addEventListener('fullscreenchange', changed)
    return () => document.removeEventListener('fullscreenchange', changed)
  }, [])
  useEffect(() => {
    if (!first) return
    // Avoid flicker on immediate responses, without delaying the operation.
    const show = window.setTimeout(() => setShownId(first.id), Math.max(0, 180 - (Date.now() - first.startedAt)))
    const slow = window.setTimeout(() => setSlowId(first.id), Math.max(0, 15000 - (Date.now() - first.startedAt)))
    return () => { window.clearTimeout(show); window.clearTimeout(slow) }
  }, [first])
  if (!first || shownId !== first.id) return null
  const status = <div className="iu-activity-status" role="status" aria-live="polite" aria-atomic="true">
    <span className="iu-activity-spinner" aria-hidden="true" />
    <span>{first.label}
      {slowId === first.id ? <small>L’operazione sta richiedendo più tempo. Attendo la risposta.</small> : null}
    </span>
  </div>
  // Fullscreen hides siblings outside its subtree, including the shell status.
  return fullscreen ? createPortal(status, fullscreen) : status
}
