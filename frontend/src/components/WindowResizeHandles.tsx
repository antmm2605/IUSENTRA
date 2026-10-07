import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { resizeWindowBounds, workWindowBottom, type WindowBounds, type Edge } from './windowPlacement'

const edges: Edge[] = ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw']
const names = { n: 'superiore', e: 'destro', s: 'inferiore', w: 'sinistro', ne: 'superiore destro', nw: 'superiore sinistro', se: 'inferiore destro', sw: 'inferiore sinistro' }

export function WindowResizeHandles({ pane, title, disabled, zIndex, onResize }: {
  pane: HTMLElement | null; title: string; disabled: boolean; zIndex: number; onResize: (bounds: WindowBounds) => void
}) {
  const [bounds, setBounds] = useState<WindowBounds | null>(null)
  const callback = useRef(onResize); callback.current = onResize
  const drag = useRef<{ bounds: WindowBounds; edge: Edge; x: number; y: number } | null>(null)
  useEffect(() => {
    if (!pane || disabled) { setBounds(null); return }
    const measure = () => {
      const rect = pane.getBoundingClientRect()
      const next = { left: rect.left, top: rect.top, width: rect.width, height: rect.height }
      setBounds(old => old && Object.keys(next).every(key => old[key as keyof WindowBounds] === next[key as keyof WindowBounds]) ? old : next)
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(pane)
    const position = new MutationObserver(measure)
    position.observe(pane, { attributes: true, attributeFilter: ['style', 'class'] })
    pane.addEventListener('transitionend', measure)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => { observer.disconnect(); position.disconnect(); pane.removeEventListener('transitionend', measure); window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure, true); drag.current = null }
  }, [pane, disabled])
  if (!bounds || disabled || bounds.width <= 0 || bounds.height <= 0) return null
  return createPortal(<div className="iu-window-resize-frame" style={{ ...bounds, position: 'fixed', zIndex: zIndex + 1 }}>
    {edges.map(edge => <button key={edge} type="button" className={`iu-window-resize-handle is-${edge}`}
      aria-label={`Ridimensiona ${title}: bordo ${names[edge]}`} title="Trascina per ridimensionare. Usa le frecce da tastiera."
      onPointerDown={event => {
        if (event.button !== 0) return
        const rect = pane?.getBoundingClientRect()
        const currentBounds = rect ? { left: rect.left, top: rect.top, width: rect.width, height: rect.height } : bounds
        drag.current = { bounds: currentBounds, edge, x: event.clientX, y: event.clientY }
        event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); event.stopPropagation()
      }}
      onPointerMove={event => {
        const start = drag.current
        if (start) callback.current(resizeWindowBounds(start.bounds, start.edge, event.clientX - start.x, event.clientY - start.y, document.documentElement.clientWidth, workWindowBottom()))
      }}
      onPointerUp={event => { drag.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId) }}
      onPointerCancel={() => { drag.current = null }}
      onKeyDown={event => {
        if (!event.key.startsWith('Arrow')) return
        event.preventDefault(); event.stopPropagation()
        const step = event.shiftKey ? 40 : 12
        const rect = pane?.getBoundingClientRect()
        const currentBounds = rect ? { left: rect.left, top: rect.top, width: rect.width, height: rect.height } : bounds
        callback.current(resizeWindowBounds(currentBounds, edge, event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0, event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0, document.documentElement.clientWidth, workWindowBottom()))
      }}/>) }
  </div>, document.body)
}
