import { useEffect } from 'react'
import { beginActivity } from './activity'

/** Adopt an existing UI state, without changing requests or domain commands. */
export function useBusyActivity(busy: boolean, label: string) {
  useEffect(() => {
    if (busy) return beginActivity(label)
    return undefined
  }, [busy, label])
}
