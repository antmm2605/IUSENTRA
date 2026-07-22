import { useEffect, useRef, type ReactNode } from 'react'
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
}) {
  const tokenRef = useRef(Symbol('operational-modal'))
  const closeRef = useRef<HTMLButtonElement>(null)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

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
      <section className={`iu-ag-source-modal__box ${boxClassName}`.trim()}>
        <header>
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
