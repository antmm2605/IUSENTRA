import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { PanelsTopLeft } from 'lucide-react'
import type { WindowPlacement } from './windowPlacement'
const options: [WindowPlacement | null, string][] = [['left','Metà sinistra'],['right','Metà destra'],['top-left','Quadrante in alto a sinistra'],['top-right','Quadrante in alto a destra'],['bottom-left','Quadrante in basso a sinistra'],['bottom-right','Quadrante in basso a destra'],[null,'Posizione libera']]
export function WindowSnapMenu({ title, onPosition }: { title: string; onPosition: (slot: WindowPlacement | null) => void }) {
  const [open,setOpen] = useState(false)
  const [anchor,setAnchor] = useState({ left: 0, top: 0 })
  const button = useRef<HTMLButtonElement>(null), menu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    menu.current?.querySelector('button')?.focus()
    const close = (event: PointerEvent) => { if (!menu.current?.contains(event.target as Node) && !button.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown',close,true)
    return () => document.removeEventListener('pointerdown',close,true)
  }, [open])
  return <><button ref={button} type="button" title="Affianca o posiziona" aria-label={`Affianca o posiziona ${title}`} aria-haspopup="menu" aria-expanded={open} onClick={() => { const rect = button.current!.getBoundingClientRect(); setAnchor({ left: Math.max(8, Math.min(window.innerWidth - 256, rect.right - 248)), top: Math.min(window.innerHeight - 350, rect.bottom + 6) }); setOpen(!open) }}><PanelsTopLeft size={16}/></button>
    {open && createPortal(<div ref={menu} className="iu-window-snap-menu" role="menu" aria-label={`Posizionamento ${title}`} data-window-snap-menu style={anchor} onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setOpen(false); button.current?.focus() } else if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) { event.preventDefault(); const items = [...(menu.current?.querySelectorAll<HTMLButtonElement>('button') || [])]; const current = items.indexOf(document.activeElement as HTMLButtonElement); const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length; items[next]?.focus() } }}>
      <strong>Affianca e organizza</strong>{options.map(([slot,label]) => <button key={label} role="menuitem" type="button" onClick={() => { onPosition(slot); setOpen(false); button.current?.focus() }}><span className={`iu-snap-symbol is-${slot || 'free'}`}/>{label}</button>)}
    </div>,document.body)}</>
}
