import { useEffect, useState } from 'react'

export const COMPACT_EDITOR_QUERY = '(max-width: 820px)'

function matches(query: string) {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches
}

/** True su telefoni e tablet stretti: pannelli laterali a scomparsa invece che affiancati. */
export function useCompactLayout(onChange?: (compact: boolean) => void) {
  const [compact, setCompact] = useState(() => matches(COMPACT_EDITOR_QUERY))
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const media = window.matchMedia(COMPACT_EDITOR_QUERY)
    const listener = () => {
      setCompact(media.matches)
      onChange?.(media.matches)
    }
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [onChange])
  return compact
}

export function isCompactViewport() {
  return matches(COMPACT_EDITOR_QUERY)
}

/** Tablet e desktop stretti: il catalogo parte chiuso per lasciare spazio alla pagina. */
export function isNarrowEditorViewport() {
  return matches('(max-width: 1240px)')
}
