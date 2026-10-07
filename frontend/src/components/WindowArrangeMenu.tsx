import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { PanelsTopLeft, ChevronUp, Columns2, LayoutGrid, Layers, WandSparkles, Minus } from 'lucide-react'
import type { WindowArrangement } from './windowPlacement'

export function WindowArrangeMenu({ count, onArrange, onMinimize }: { count: number; onArrange: (mode: WindowArrangement) => string; onMinimize: () => void }) {
  const [open, setOpen] = useState(false)
  const [anchor, setAnchor] = useState({ left: 8, bottom: 76 })
  const [status, setStatus] = useState('')
  const trigger = useRef<HTMLButtonElement>(null), menu = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    menu.current?.querySelector<HTMLButtonElement>('button')?.focus()
    const close = (event: PointerEvent) => { if (!menu.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setOpen(false) }
    const reposition = () => { const rect = trigger.current?.getBoundingClientRect(); if (rect) setAnchor({ left: Math.max(8, Math.min(document.documentElement.clientWidth - 288, rect.left)), bottom: window.innerHeight - rect.top + 8 }) }
    window.addEventListener('resize', reposition)
    document.addEventListener('pointerdown', close, true)
    return () => { window.removeEventListener('resize', reposition); document.removeEventListener('pointerdown', close, true) }
  }, [open])
  const finish = () => { setOpen(false); trigger.current?.focus() }
  return <>
    <button ref={trigger} className="iu-window-dock__organize" type="button" aria-label={`Organizza ${count} ${count === 1 ? 'finestra aperta' : 'finestre aperte'}`} title="Organizza le finestre aperte" aria-haspopup="menu" aria-expanded={open} onClick={() => { const rect = trigger.current!.getBoundingClientRect(); setAnchor({ left: Math.max(8, Math.min(document.documentElement.clientWidth - 288, rect.left)), bottom: window.innerHeight - rect.top + 8 }); setOpen(!open) }}><PanelsTopLeft size={17}/><strong>{count}</strong><ChevronUp size={14}/></button>
    <span className="iu-window-dock__status" role="status">{status}</span>
    {open && createPortal(<div ref={menu} className="iu-window-arrange-menu" role="menu" aria-label="Organizza tutte le finestre" data-window-snap-menu style={anchor} onKeyDown={event => {
      if (event.key === 'Escape' || event.key === 'Tab') { if (event.key === 'Escape') event.preventDefault(); event.stopPropagation(); finish() }
      else if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) { event.preventDefault(); const buttons = [...(menu.current?.querySelectorAll<HTMLButtonElement>('button') || [])]; const current = buttons.indexOf(document.activeElement as HTMLButtonElement); const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length; buttons[next]?.focus() }
    }}>
      <strong>Organizza {count} {count === 1 ? 'finestra' : 'finestre'}</strong>
      <p>La disposizione richiama anche le finestre ridotte a icona.</p>
      <button role="menuitem" type="button" onClick={() => { setStatus(onArrange('auto')); finish() }}><WandSparkles size={18}/><span><strong>Automatico</strong><small>Adatta le finestre allo spazio disponibile</small></span></button>
      <button role="menuitem" type="button" onClick={() => { setStatus(onArrange('columns')); finish() }}><Columns2 size={18}/><span><strong>Affianca</strong><small>Colonne, con nuove righe se necessarie</small></span></button>
      <button role="menuitem" type="button" onClick={() => { setStatus(onArrange('grid')); finish() }}><LayoutGrid size={18}/><span><strong>Griglia</strong><small>Riquadri di uguale dimensione</small></span></button>
      <button role="menuitem" type="button" onClick={() => { setStatus(onArrange('cascade')); finish() }}><Layers size={18}/><span><strong>Cascata</strong><small>Finestre sovrapposte con titoli accessibili</small></span></button>
      <button role="menuitem" type="button" onClick={() => { onMinimize(); setStatus('Tutte le finestre sono ridotte a icona. Richiamale dalla barra.'); finish() }}><Minus size={18}/><span><strong>Riduci tutte a icona</strong><small>Lascia libera la pagina di lavoro</small></span></button>
    </div>, document.body)}
  </>
}
