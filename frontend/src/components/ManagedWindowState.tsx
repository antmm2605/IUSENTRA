import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react'
import { createPortal } from 'react-dom'
import { Maximize2, Minimize2, Minus, X } from 'lucide-react'
import './ManagedWindows.css'
import { WindowSnapMenu } from './WindowSnapMenu'
import { arrangeWindowPlacements, workWindowBottom, type WindowArrangement, type WindowPlacement } from './windowPlacement'
import { WindowArrangeMenu } from './WindowArrangeMenu'

type WindowEntry = { id: string; title: string; minimized: boolean; zIndex: number; restore: () => void; close: () => void; position: (slot: WindowPlacement) => void; minimize: () => void }
let windows: WindowEntry[] = []
const listeners = new Set<() => void>()
let layer = 30000
let activeArrangement: WindowArrangement | null = null
function applyArrangement(mode: WindowArrangement, includeMinimized = true) {
  const entries = windows.filter(entry => includeMinimized || !entry.minimized).sort((left, right) => right.zIndex - left.zIndex)
  const arrangement = arrangeWindowPlacements(entries.length, mode, document.documentElement.clientWidth, workWindowBottom())
  entries.map((entry, index) => ({ entry, slot: arrangement.slots[index] })).reverse().forEach(({ entry, slot }) => entry.position(slot))
  return arrangement.cascaded && mode !== 'cascade' ? 'Finestre disposte a cascata per mantenere leggibili i contenuti nello spazio disponibile.' : 'Disposizione applicata a tutte le finestre aperte.'
}
function publish() { listeners.forEach((listener) => listener()) }
function subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } }
export function activateManagedWindowForNode(node: HTMLElement, includeMinimized = false) {
  const owner = node.closest<HTMLElement>('[data-managed-window-id]')
  if (!owner || (!includeMinimized && !owner.getBoundingClientRect().width)) return
  const entry = windows.find(item => item.id === owner.dataset.managedWindowId && (includeMinimized || !item.minimized))
  entry?.restore()
}
export function useManagedWindow(open: boolean, title: string, close: () => void) {
  const id = useId()
  const closeRef = useRef(close); closeRef.current = close
  const [minimized, setMinimized] = useState(false)
  const [placement, setPlacement] = useState<WindowPlacement | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [zIndex, setZIndex] = useState(() => ++layer)
  const activate = () => {
    setMinimized(false)
    const front = windows.filter(entry => !entry.minimized).sort((a, b) => b.zIndex - a.zIndex)[0]
    if (front?.id !== id) setZIndex(++layer)
  }
  useEffect(() => { if (open) setZIndex(++layer) }, [open])
  useEffect(() => {
    if (!open) { setMinimized(false); setExpanded(false); return }
    windows = [...windows.filter((entry) => entry.id !== id), { id, title, minimized, zIndex, restore: activate, close: () => closeRef.current(), position: (slot) => { setPlacement(slot); setExpanded(false); activate() }, minimize: () => setMinimized(true) }]
    publish()
    return () => { windows = windows.filter((entry) => entry.id !== id); publish() }
  }, [id, open, title, minimized, zIndex])
  return { id, minimized, expanded, placement, setPlacement: (slot: WindowPlacement | null) => { activeArrangement = null; setPlacement(slot); setExpanded(false); activate() }, zIndex, activate, minimize: () => setMinimized(true), toggleExpanded: () => { setPlacement(null); setExpanded((value) => !value) } }
}
export function WindowControls({ title, expanded, canExpand = true, minimize, toggleExpanded, onPosition }: {
  title: string; expanded: boolean; canExpand?: boolean; minimize: () => void; toggleExpanded: () => void; onPosition: (slot: WindowPlacement | null) => void
}) {
  return <><WindowSnapMenu title={title} onPosition={onPosition}/><button type="button" onClick={minimize} aria-label={`Riduci a icona ${title}`} title="Riduci a icona"><Minus size={16}/></button>
    {canExpand ? <button type="button" onClick={toggleExpanded} aria-label={`${expanded ? 'Ripristina' : 'Ingrandisci'} ${title}`} title={expanded ? 'Ripristina dimensione' : 'Ingrandisci'}>{expanded ? <Minimize2 size={16}/> : <Maximize2 size={16}/>}</button> : null}</>
}
export function ManagedWindowDock() {
  const items = useSyncExternalStore(subscribe, () => windows)
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || !event.isTrusted || document.querySelector('[data-window-snap-menu]')) return
      const active = windows.filter((entry) => !entry.minimized).sort((a, b) => b.zIndex - a.zIndex)[0]
      if (!active) return
      event.preventDefault(); event.stopImmediatePropagation(); active.close()
    }
    const iframeFocus = () => window.setTimeout(() => {
      if (document.hasFocus() && document.activeElement instanceof HTMLIFrameElement) activateManagedWindowForNode(document.activeElement)
    }, 0)
    let resizeFrame = 0
    const resizeArrangement = () => {
      window.cancelAnimationFrame(resizeFrame)
      resizeFrame = window.requestAnimationFrame(() => { if (activeArrangement) applyArrangement(activeArrangement, false) })
    }
    window.addEventListener('resize', resizeArrangement)
    window.addEventListener('blur', iframeFocus)
    document.addEventListener('keydown', escape, true)
    return () => { document.removeEventListener('keydown', escape, true); window.removeEventListener('blur', iframeFocus); window.removeEventListener('resize', resizeArrangement); window.cancelAnimationFrame(resizeFrame) }
  }, [])
  const active = items.filter(entry => !entry.minimized).sort((a, b) => b.zIndex - a.zIndex)[0]
  if (!items.length) return null
  return createPortal(<nav className="iu-window-dock" aria-label="Finestre di lavoro aperte"><WindowArrangeMenu count={items.length} onMinimize={() => { [...windows].forEach(entry => entry.minimize()) }} onArrange={(mode: WindowArrangement) => {
    activeArrangement = mode
    return applyArrangement(mode)
  }}/>

    {items.map((entry) => <div key={entry.id} className={entry.minimized ? 'is-minimized' : entry.id === active?.id ? 'is-active' : ''}><button type="button" onClick={entry.restore} aria-pressed={entry.id === active?.id} title={entry.title} aria-label={`Richiama ${entry.title}`}><span>{entry.title}</span></button><button type="button" onClick={entry.close} aria-label={`Chiudi finestra ${entry.title}`}><X size={14}/></button></div>)}
  </nav>, document.body)
}
