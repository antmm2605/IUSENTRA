import { useEffect, useRef, useState, type CSSProperties, type HTMLAttributes } from 'react'

export function useReaderDrag(enabled: boolean, resetKey?: string) {
  const boxRef = useRef<HTMLDivElement>(null)
  const dragging = useRef<{ x: number; y: number; dx: number; dy: number } | null>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  useEffect(() => { setPosition({ x: 0, y: 0 }); dragging.current = null }, [enabled, resetKey])
  useEffect(() => {
    const reset = () => setPosition({ x: 0, y: 0 })
    window.addEventListener('resize', reset)
    return () => window.removeEventListener('resize', reset)
  }, [])
  const move = (x: number, y: number) => {
    const box = boxRef.current?.getBoundingClientRect()
    if (!box) return
    const baseX = box.left - position.x, baseY = box.top - position.y
    setPosition({ x: Math.max(4 - baseX, Math.min(window.innerWidth - box.width - 4 - baseX, x)), y: Math.max(4 - baseY, Math.min(window.innerHeight - box.height - 4 - baseY, y)) })
  }
  const headerProps: HTMLAttributes<HTMLElement> = enabled ? {
    tabIndex: 0,
    title: 'Trascina la barra per spostare il lettore. Puoi usare anche le frecce della tastiera.',
    style: { cursor: 'move', touchAction: 'none' },
    onPointerDown: (event) => {
      if (event.button !== 0 || (event.target as HTMLElement).closest('button,a,input,select,textarea')) return
      dragging.current = { x: event.clientX, y: event.clientY, dx: position.x, dy: position.y }
      event.currentTarget.setPointerCapture(event.pointerId)
      event.preventDefault()
    },
    onPointerMove: (event) => {
      const drag = dragging.current
      if (drag) move(drag.dx + event.clientX - drag.x, drag.dy + event.clientY - drag.y)
    },
    onPointerUp: (event) => { dragging.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId) },
    onPointerCancel: () => { dragging.current = null },
    onKeyDown: (event) => {
      if (event.target !== event.currentTarget || !event.key.startsWith('Arrow')) return
      event.preventDefault()
      move(position.x + (event.key === 'ArrowLeft' ? -12 : event.key === 'ArrowRight' ? 12 : 0), position.y + (event.key === 'ArrowUp' ? -12 : event.key === 'ArrowDown' ? 12 : 0))
    },
  } : {}
  const boxStyle: CSSProperties | undefined = enabled ? { transform: `translate(${position.x}px, ${position.y}px)` } : undefined
  return { boxRef, boxStyle, headerProps }
}
