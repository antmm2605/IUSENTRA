import { useEffect, useRef, useState, type ReactNode } from 'react'
import { X } from 'lucide-react'

const modalStack: symbol[] = []
let lockedBodyCount = 0

export function OperationalModal({
  open,
  ariaLabel,
  eyebrow,
  title,
  subtitle,
  actions,
  children,
  onClose,
  boxClassName = '',
  bodyClassName = '',
  draggable = false,
  fullscreen = false,
}: {
  open: boolean
  ariaLabel: string
  eyebrow: ReactNode
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  onClose: () => void
  boxClassName?: string
  bodyClassName?: string
  draggable?: boolean
  fullscreen?: boolean
}) {
  const boxRef = useRef<HTMLElement>(null)
  const dragRef = useRef<{ x: number; y: number; dx: number; dy: number } | null>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const tokenRef = useRef(Symbol('operational-modal'))
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    setPosition({ x: 0, y: 0 })
    dragRef.current = null
  }, [open, fullscreen])

  useEffect(() => {
    const reset = () => setPosition({ x: 0, y: 0 })
    window.addEventListener('resize', reset)
    return () => window.removeEventListener('resize', reset)
  }, [])

  const move = (x: number, y: number) => {
    const box = boxRef.current?.getBoundingClientRect()
    if (!box) return
    const baseX = box.left - position.x
    const baseY = box.top - position.y
    setPosition({
      x: Math.max(4 - baseX, Math.min(window.innerWidth - box.width - 4 - baseX, x)),
      y: Math.max(4 - baseY, Math.min(window.innerHeight - box.height - 4 - baseY, y)),
    })
  }

  useEffect(() => {
    if (!open) return undefined
    const token = tokenRef.current
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null
    modalStack.push(token)
    lockedBodyCount += 1
    document.body.classList.add('iu-ag-source-open')

    const closeOnEscape = (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key === 'Escape' && modalStack.at(-1) === token) onCloseRef.current()
    }
    document.addEventListener('keydown', closeOnEscape)
    window.setTimeout(() => closeRef.current?.focus(), 0)

    return () => {
      document.removeEventListener('keydown', closeOnEscape)
      const index = modalStack.lastIndexOf(token)
      if (index >= 0) modalStack.splice(index, 1)
      lockedBodyCount = Math.max(0, lockedBodyCount - 1)
      if (!lockedBodyCount) document.body.classList.remove('iu-ag-source-open')
      if (previouslyFocused?.isConnected && document.contains(previouslyFocused)) {
        window.requestAnimationFrame(() => {
          try {
            previouslyFocused.focus({ preventScroll: true })
          } catch {
            previouslyFocused.focus()
          }
        })
      }
    }
  }, [open])

  if (!open) return null
  return (
    <div
      className="iu-ag-source-modal"
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      onMouseDown={(mouseEvent) => {
        if (mouseEvent.target === mouseEvent.currentTarget && modalStack.at(-1) === tokenRef.current) onClose()
      }}
    >
      <section ref={boxRef} className={`iu-ag-source-modal__box ${boxClassName}`.trim()} style={draggable && !fullscreen ? { transform: `translate(${position.x}px, ${position.y}px)` } : undefined}>
        <header
          tabIndex={draggable && !fullscreen ? 0 : undefined}
          title={draggable && !fullscreen ? 'Trascina questa barra per spostare il lettore. Usa le frecce quando la barra ha il focus.' : undefined}
          style={draggable && !fullscreen ? { cursor: 'move', touchAction: 'none' } : undefined}
          onPointerDown={(event) => {
            if (!draggable || fullscreen || event.button !== 0 || (event.target as HTMLElement).closest('button,a,input,select,textarea')) return
            dragRef.current = { x: event.clientX, y: event.clientY, dx: position.x, dy: position.y }
            event.currentTarget.setPointerCapture(event.pointerId)
            event.preventDefault()
          }}
          onPointerMove={(event) => {
            const drag = dragRef.current
            if (drag) move(drag.dx + event.clientX - drag.x, drag.dy + event.clientY - drag.y)
          }}
          onPointerUp={(event) => {
            dragRef.current = null
            if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
          }}
          onPointerCancel={() => { dragRef.current = null }}
          onKeyDown={(event) => {
            if (!draggable || fullscreen || event.target !== event.currentTarget || !event.key.startsWith('Arrow')) return
            event.preventDefault()
            move(position.x + (event.key === 'ArrowRight' ? 12 : event.key === 'ArrowLeft' ? -12 : 0), position.y + (event.key === 'ArrowDown' ? 12 : event.key === 'ArrowUp' ? -12 : 0))
          }}
        >
          <div>
            <span>{eyebrow}</span>
            <strong>{title}</strong>
            {subtitle ? <small>{subtitle}</small> : null}
          </div>
          <nav>
            {actions}
            <button ref={closeRef} type="button" onClick={onClose} aria-label={`Chiudi ${ariaLabel}`}><X size={16}/> Chiudi</button>
          </nav>
        </header>
        <div className={`iu-ag-source-modal__body ${bodyClassName}`.trim()}>{children}</div>
      </section>
    </div>
  )
}
