import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
/** Panels live beside all work windows, outside the sticky navigation stacking context. */
export function WorkPanelPortal({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose); closeRef.current = onClose
  useEffect(() => {
    const node = ref.current
    const close = () => closeRef.current()
    node?.addEventListener('iusentra:close-work-panel', close)
    return () => node?.removeEventListener('iusentra:close-work-panel', close)
  }, [])
  return createPortal(<div ref={ref} className="iu-work-panel-host">{children}</div>, document.body)
}