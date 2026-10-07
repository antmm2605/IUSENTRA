import { createPortal } from 'react-dom'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { WindowResizeHandles } from './WindowResizeHandles'
import { windowPlacementStyle, workWindowBottom } from './windowPlacement'
import { useManagedWindow, WindowControls } from './ManagedWindowState'

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
  draggable = true,
  fullscreen,
  focusToken,
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
  focusToken?: string | number
}) {
  const managed = useManagedWindow(open, title || ariaLabel, onClose)
  useEffect(() => { if (open && focusToken !== undefined) managed.activate() }, [open,focusToken])
  const maximized = !managed.placement && (Boolean(fullscreen) || managed.expanded)
  const boxRef = useRef<HTMLElement>(null)
  const dragRef = useRef<{ x: number; y: number; dx: number; dy: number } | null>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const freeBounds = useRef<{ left: number; top: number; width: number; height: number } | null>(null)
  const tokenRef = useRef(Symbol('operational-modal'))
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    setPosition({ x: 0, y: 0 })
    dragRef.current = null
  }, [open, maximized])

  useEffect(() => {
    const reset = () => {
      if (freeBounds.current) {
        const bounds = freeBounds.current
        const width = Math.min(bounds.width, document.documentElement.clientWidth - 16)
        const height = Math.min(bounds.height, workWindowBottom() - 16)
        freeBounds.current = { width, height, left: Math.max(8, Math.min(bounds.left, document.documentElement.clientWidth - width - 8)), top: Math.max(8, Math.min(bounds.top, workWindowBottom() - height - 8)) }
      }
      setPosition({ x: 0, y: 0 })
    }
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
      y: Math.max(4 - baseY, Math.min(workWindowBottom() - box.height - baseY, y)),
    })
  }

  useEffect(() => {
    if (!open || managed.minimized) return undefined
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
      if (previouslyFocused?.isConnected && document.contains(previouslyFocused) && !boxRef.current?.contains(previouslyFocused)) {
        window.requestAnimationFrame(() => {
          if (!previouslyFocused.getBoundingClientRect().width) return
          try {
            previouslyFocused.focus({ preventScroll: true })
          } catch {
            previouslyFocused.focus()
          }
        })
      }
    }
  }, [open, managed.minimized])

  if (!open) return null
  return <><WindowResizeHandles pane={boxRef.current} title={ariaLabel} disabled={managed.minimized || maximized} zIndex={managed.zIndex} onResize={bounds => { freeBounds.current = bounds; setPosition({ x: 0, y: 0 }); managed.setPlacement(null) }}/>{createPortal(
    <div
      className={`iu-ag-source-modal iu-managed-window ${managed.minimized ? 'is-minimized' : ''} ${maximized ? 'is-expanded' : ''} ${managed.placement ? 'is-positioned' : ''}`}
      style={{ zIndex: managed.zIndex }}
      onFocusCapture={() => { if (!managed.minimized) managed.activate() }}
      onPointerDownCapture={() => { managed.activate(); const token = tokenRef.current; const index = modalStack.indexOf(token); if (index >= 0) modalStack.splice(index, 1); modalStack.push(token) }}
      data-managed-window-id={managed.id}
      role="dialog"
      aria-modal="false"
      aria-label={ariaLabel}
      onMouseDown={(mouseEvent) => {
        if (mouseEvent.target === mouseEvent.currentTarget && modalStack.at(-1) === tokenRef.current) onClose()
      }}
    >
      <section ref={boxRef} className={`iu-ag-source-modal__box ${boxClassName}`.trim()} style={{ maxWidth: Math.max(0, document.documentElement.clientWidth - 12), maxHeight: workWindowBottom() - 24, ...(maximized ? { height: workWindowBottom() - 24 } : {}), ...(windowPlacementStyle(managed.placement) || ((draggable || freeBounds.current) && !maximized ? { ...(freeBounds.current ? { position: 'fixed' as const, right: 'auto', left: freeBounds.current.left, top: freeBounds.current.top, width: freeBounds.current.width, height: freeBounds.current.height } : {}), transform: `translate(${position.x}px, ${position.y}px)` } : undefined)) }}>
        <header
          onDoubleClick={(event) => { if (!(event.target as Element).closest('button,a,input,select,textarea')) managed.toggleExpanded() }}
          aria-label={`Sposta finestra ${ariaLabel}`}
          tabIndex={draggable && !maximized ? 0 : undefined}
          title={draggable && !maximized ? 'Trascina questa barra per spostare il lettore. Usa le frecce quando la barra ha il focus.' : undefined}
          style={draggable && !maximized ? { cursor: 'move', touchAction: 'none' } : undefined}
          onPointerDown={(event) => {
            if (!draggable || maximized || event.button !== 0 || (event.target as HTMLElement).closest('button,a,input,select,textarea')) return
            const wasPositioned = Boolean(managed.placement)
            if (wasPositioned && boxRef.current) { const rect = boxRef.current.getBoundingClientRect(); freeBounds.current = { left: rect.left, top: rect.top, width: rect.width, height: rect.height }; managed.setPlacement(null); setPosition({ x: 0, y: 0 }) }
            dragRef.current = { x: event.clientX, y: event.clientY, dx: wasPositioned ? 0 : position.x, dy: wasPositioned ? 0 : position.y }
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
            if (!draggable || maximized || event.target !== event.currentTarget || !event.key.startsWith('Arrow')) return
            event.preventDefault()
            move(position.x + (event.key === 'ArrowRight' ? 12 : event.key === 'ArrowLeft' ? -12 : 0), position.y + (event.key === 'ArrowDown' ? 12 : event.key === 'ArrowUp' ? -12 : 0))
          }}
        >
          <div>
            <span>{eyebrow}</span>
            <strong title={title}>{title}</strong>
            {subtitle ? <small>{subtitle}</small> : null}
          </div>
          <nav>
            {actions}
            <span className="iu-window-title-controls">
            <WindowControls title={ariaLabel} expanded={maximized} canExpand={fullscreen === undefined} minimize={managed.minimize} toggleExpanded={managed.toggleExpanded} onPosition={slot => { setPosition({ x: 0, y: 0 }); managed.setPlacement(slot) }}/>
            <button ref={closeRef} type="button" onClick={onClose} aria-label={`Chiudi ${ariaLabel}`} title="Chiudi"><X size={16}/></button>
            </span>
          </nav>
        </header>
        <div className={`iu-ag-source-modal__body ${bodyClassName}`.trim()}>{children}</div>
      </section>
    </div>, document.body
  )}</>
}
