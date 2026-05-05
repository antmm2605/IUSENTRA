import { useEffect } from 'react'

export function useKeyboardShortcut(
  matcher: (event: KeyboardEvent) => boolean,
  handler: (event: KeyboardEvent) => void,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled) return
    const listener = (event: KeyboardEvent) => {
      if (!matcher(event)) return
      handler(event)
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [enabled, handler, matcher])
}

export function isCommandK(event: KeyboardEvent) {
  return event.key.toLowerCase() === 'k' && (event.ctrlKey || event.metaKey)
}
