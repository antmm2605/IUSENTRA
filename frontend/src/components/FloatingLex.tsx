import { useEffect, useRef, useState } from 'react'
import { Grip, MessageCircle, Sparkles, X } from 'lucide-react'

type Position = { x: number; y: number }

const STORAGE_KEY = 'iusentra.lex.floating.position'

function defaultPosition(): Position {
  if (typeof window === 'undefined') return { x: 24, y: 24 }
  return {
    x: Math.max(16, window.innerWidth - 96),
    y: Math.max(16, window.innerHeight - 116),
  }
}

function readPosition(): Position {
  if (typeof window === 'undefined') return defaultPosition()
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultPosition()
    const parsed = JSON.parse(raw) as Partial<Position>
    if (typeof parsed.x === 'number' && typeof parsed.y === 'number') {
      return {
        x: Math.max(12, Math.min(window.innerWidth - 72, parsed.x)),
        y: Math.max(12, Math.min(window.innerHeight - 72, parsed.y)),
      }
    }
  } catch {
    return defaultPosition()
  }
  return defaultPosition()
}

export function FloatingLex() {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<Position>(() => readPosition())
  const drag = useRef({ active: false, moved: false, dx: 0, dy: 0, latest: position })

  useEffect(() => {
    drag.current.latest = position
  }, [position])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const handleMove = (event: PointerEvent) => {
      if (!drag.current.active) return
      const next = {
        x: Math.max(12, Math.min(window.innerWidth - 72, event.clientX - drag.current.dx)),
        y: Math.max(12, Math.min(window.innerHeight - 72, event.clientY - drag.current.dy)),
      }
      drag.current.moved = true
      drag.current.latest = next
      setPosition(next)
    }
    const handleUp = () => {
      if (!drag.current.active) return
      drag.current.active = false
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(drag.current.latest))
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
    window.addEventListener('pointercancel', handleUp)
    return () => {
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      window.removeEventListener('pointercancel', handleUp)
    }
  }, [])

  const startDrag = (event: React.PointerEvent<HTMLButtonElement>) => {
    drag.current = {
      active: true,
      moved: false,
      dx: event.clientX - position.x,
      dy: event.clientY - position.y,
      latest: position,
    }
  }

  const toggle = () => {
    if (drag.current.moved) {
      drag.current.moved = false
      return
    }
    setOpen((value) => !value)
  }

  return (
    <div className="iu-lex-float" style={{ left: position.x, top: position.y }}>
      {open ? (
        <section className="iu-lex-float__panel" aria-label="Lex AI agenda">
          <header>
            <span><Sparkles size={16}/> Lex AI</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Chiudi Lex"><X size={16}/></button>
          </header>
          <p>Posso preparare il briefing della giornata, controllare scadenze collegate e suggerire il prossimo passo operativo.</p>
          <div>
            <a href="/lex?context=agenda">Apri Lex completo</a>
            <a href="/workspace-intelligente">Regia operativa</a>
          </div>
        </section>
      ) : null}
      <button
        className="iu-lex-float__button"
        type="button"
        onPointerDown={startDrag}
        onClick={toggle}
        aria-label="Apri Lex AI, icona trascinabile"
        title="Lex AI - trascina per spostare"
      >
        <Grip className="iu-lex-float__grip" size={12}/>
        <MessageCircle size={23}/>
        <Sparkles className="iu-lex-float__spark" size={14}/>
      </button>
    </div>
  )
}
