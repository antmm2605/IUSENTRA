import { useEffect, useId, useState, useSyncExternalStore } from 'react'
import { beginActivity, getActivities, presentedInlineActivity, subscribeActivities, type Activity } from './activity'

/** Adopt an existing UI state, without changing requests or domain commands. */
export function useBusyActivity(busy: boolean, label: string, presentation: Activity['presentation'] = 'global', owner?: string) {
  useEffect(() => {
    if (busy) return beginActivity(label, presentation, owner)
    return undefined
  }, [busy, label, presentation, owner])
}

/** Page/panel loaders arbitrate one visible card while retaining every owner. */
export function useInlineActivity(label: string): Element | null {
  const owner = useId()
  const activities = useSyncExternalStore(subscribeActivities, getActivities, getActivities)
  const [target, setTarget] = useState<Element | null>(() => typeof document === 'undefined' ? null : document.fullscreenElement || document.body)
  useBusyActivity(true, label, 'inline', owner)
  useEffect(() => {
    const changed = () => setTarget(document.fullscreenElement || document.body)
    document.addEventListener('fullscreenchange', changed)
    return () => document.removeEventListener('fullscreenchange', changed)
  }, [])
  return presentedInlineActivity(activities)?.owner === owner ? target : null
}
