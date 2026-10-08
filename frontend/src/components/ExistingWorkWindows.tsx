import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Move, X } from 'lucide-react'
import { WindowResizeHandles } from './WindowResizeHandles'
import { windowPlacementStyle, workWindowBottom } from './windowPlacement'
import { useManagedWindow, WindowControls } from './ManagedWindowState'

type ExistingWindowEntry = { node: HTMLElement; pane: HTMLElement; header: HTMLElement | null; title: string }
function ExistingWindow({ node, pane, header, title }: ExistingWindowEntry) {
  const layerHost = node.closest<HTMLElement>('#pct-ai-widget') || node
  const controlsTarget = header || pane
  const close = () => {
    const buttons = [...node.querySelectorAll<HTMLButtonElement>('button')].filter((button) => !button.closest('.iu-existing-window-controls'))
    const control = buttons.find((button) => /^Chiudi/i.test(button.getAttribute('aria-label') || ''))
      || buttons.find((button) => /^(?:Chiudi|Esci)$/i.test(button.textContent?.trim() || ''))
      || buttons.find((button) => button.closest('header') && /^Annulla$/i.test(button.textContent?.trim() || ''))
    const toggle = node.parentElement?.querySelector<HTMLButtonElement>('button[aria-haspopup="dialog"][aria-expanded="true"]')
    if (control) control.click()
    else if (toggle) toggle.click()
    else if (node.closest('.iu-work-panel-host')) node.dispatchEvent(new CustomEvent('iusentra:close-work-panel', { bubbles: true }))
    else node.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  }
  const managed = useManagedWindow(true, title, close)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [viewportRevision, setViewportRevision] = useState(0)
  const live = useRef({ position, managed }); live.current = { position, managed }
  const freeBounds = useRef<{ left: number; top: number; width: number; height: number } | null>(null)
  const original = useMemo(() => Object.fromEntries(['position','left','right','top','width','height','max-width','max-height','resize'].map(key => [key,pane.style.getPropertyValue(key)])), [pane])
  const drag = useRef<{ x: number; y: number; dx: number; dy: number } | null>(null)
  useEffect(() => {
    const style = pane.style.cssText
    const outerStyle = node.style.cssText
    const hostLayer = layerHost.style.getPropertyValue('z-index')
    const hostLayerPriority = layerHost.style.getPropertyPriority('z-index')
    const ariaModal = node.getAttribute('aria-modal')
    node.dataset.managedExistingWindow = 'true'
    node.dataset.managedWindowId = managed.id
    if (pane !== node) { node.style.setProperty('pointer-events','none','important'); node.style.setProperty('background','transparent','important'); pane.style.setProperty('pointer-events','auto','important'); node.setAttribute('aria-modal','false') }
    const originalCloseButtons = [...pane.querySelectorAll<HTMLButtonElement>(':scope > header button')].filter(button => !button.closest('.iu-existing-window-controls') && (/^Chiudi/i.test(button.getAttribute('aria-label') || button.textContent?.trim() || '') || /^(?:Tutto schermo|Esci da tutto schermo)$/.test(button.getAttribute('aria-label') || ''))).map(button => ({ button, display: button.style.display }))
    originalCloseButtons.forEach(({ button }) => { button.style.display = 'none' })
    const activate = () => managed.activate()
    pane.addEventListener('pointerdown', activate)
    pane.addEventListener('focusin', activate)
    const resize = () => {
      if (freeBounds.current) {
        const bounds = freeBounds.current
        const width = Math.min(bounds.width, document.documentElement.clientWidth - 24)
        const height = Math.min(bounds.height, workWindowBottom() - 24)
        freeBounds.current = {
          width, height,
          left: Math.max(12, Math.min(bounds.left, document.documentElement.clientWidth - width - 12)),
          top: Math.max(12, Math.min(bounds.top, workWindowBottom() - height - 12)),
        }
      }
      setPosition({ x: 0, y: 0 })
      setViewportRevision(value => value + 1)
    }
    window.addEventListener('resize', resize)
    const captureDrag = node.id === 'pct-ai-panel'
    const down = (event: PointerEvent) => {
      if (event.button !== 0 || (event.target as Element).closest('button,a,input,select,textarea')) return
      const rect = pane.getBoundingClientRect()
      const wasPositioned = live.current.managed.expanded || Boolean(live.current.managed.placement)
      if (wasPositioned) { freeBounds.current = { left: rect.left, top: rect.top, width: rect.width, height: rect.height }; setPosition({ x: 0, y: 0 }) }
      live.current.managed.activate()
      if (live.current.managed.expanded) live.current.managed.toggleExpanded()
      if (live.current.managed.placement) live.current.managed.setPlacement(null)
      drag.current = { x: event.clientX, y: event.clientY, dx: wasPositioned ? 0 : live.current.position.x, dy: wasPositioned ? 0 : live.current.position.y }
      header?.setPointerCapture(event.pointerId); event.preventDefault(); event.stopPropagation(); if (captureDrag) event.stopImmediatePropagation()
    }
    const motion = (event: PointerEvent) => { const start = drag.current; if (start) move(start.dx + event.clientX - start.x, start.dy + event.clientY - start.y) }
    const up = () => { drag.current = null }
    header?.addEventListener('pointerdown',down,captureDrag); header?.addEventListener('pointermove',motion); header?.addEventListener('pointerup',up); header?.addEventListener('pointercancel',up)

    return () => { originalCloseButtons.forEach(({ button, display }) => { button.style.display = display }); if (ariaModal === null) node.removeAttribute('aria-modal'); else node.setAttribute('aria-modal',ariaModal); pane.style.cssText = style; node.style.cssText = outerStyle; if (layerHost !== node) layerHost.style.setProperty('z-index', hostLayer, hostLayerPriority); delete node.dataset.managedExistingWindow; delete node.dataset.managedWindowId; delete node.dataset.windowMinimized; pane.removeEventListener('pointerdown', activate); pane.removeEventListener('focusin', activate); window.removeEventListener('resize', resize); header?.removeEventListener('pointerdown',down,captureDrag); header?.removeEventListener('pointermove',motion); header?.removeEventListener('pointerup',up); header?.removeEventListener('pointercancel',up) }
  }, [node, pane, header, title])
  useEffect(() => {
    for (const [key,value] of Object.entries(original)) pane.style.setProperty(key,value)
    node.dataset.windowMinimized = managed.minimized ? 'true' : 'false'
    // Lex vive in un contenitore fisso: anche il suo contesto di sovrapposizione deve seguire la finestra.
    layerHost.style.setProperty('z-index', String(managed.zIndex), 'important')
    node.style.setProperty('z-index', String(managed.zIndex), 'important')
    node.style.setProperty('display', managed.minimized ? 'none' : '', 'important')
    if (pane !== node) {
      node.style.setProperty('height', `${workWindowBottom()}px`, 'important')
      node.style.setProperty('bottom', 'auto', 'important')
    }
    pane.style.setProperty('transform', managed.expanded ? 'none' : `translate(${position.x}px,${position.y}px)`, 'important')
    pane.style.setProperty('width', managed.expanded ? `${document.documentElement.clientWidth - 24}px` : '', 'important')
    pane.style.setProperty('height', managed.expanded ? `${workWindowBottom() - 24}px` : '', 'important')
    pane.style.setProperty('max-width', `${document.documentElement.clientWidth - 24}px`, 'important')
    const paneTop = managed.expanded || managed.placement ? 12 : freeBounds.current?.top ?? (node.id === "pct-ai-panel" ? 12 : pane.getBoundingClientRect().top)
    pane.style.setProperty('max-height', `${Math.max(120, workWindowBottom() - paneTop - 12)}px`, 'important')
    if (pane === node) {
      for (const [name, value] of Object.entries({ left: '12px', right: 'auto', top: '12px', position: 'fixed' })) node.style.setProperty(name, managed.expanded ? value : '', 'important')
    }
    if (freeBounds.current && !managed.expanded && !managed.placement) { const bounds = freeBounds.current; for (const [key,value] of Object.entries({ position: 'fixed', left: bounds.left + 'px', right: 'auto', top: bounds.top + 'px', width: bounds.width + 'px', height: bounds.height + 'px' })) pane.style.setProperty(key,value,'important') }
    const placement = windowPlacementStyle(managed.placement)
    if (placement) for (const [key,value] of Object.entries(placement)) pane.style.setProperty(key.replace(/[A-Z]/g, letter => '-' + letter.toLowerCase()), value, 'important')
    if (managed.expanded) setPosition({ x: 0, y: 0 })
  }, [node, pane, original, header, managed.zIndex, managed.minimized, managed.expanded, managed.placement, position.x, position.y, viewportRevision])
  const move = (x: number, y: number) => {
    const rect = pane.getBoundingClientRect()
    const left = rect.left - live.current.position.x, top = rect.top - live.current.position.y
    setPosition({ x: Math.max(4 - left, Math.min(document.documentElement.clientWidth - rect.width - left - 4, x)), y: Math.max(4 - top, Math.min(workWindowBottom() - rect.height - top, y)) })
  }
  return <><WindowResizeHandles pane={pane} title={title} disabled={managed.minimized || managed.expanded} zIndex={managed.zIndex} onResize={bounds => { freeBounds.current = bounds; setViewportRevision(value => value + 1); setPosition({ x: 0, y: 0 }); managed.setPlacement(null) }}/>{createPortal(<div className="iu-existing-window-controls" tabIndex={0} aria-label={`Sposta finestra ${title}`}
    onPointerDown={(event) => { if ((event.target as Element).closest('button')) return; const rect = pane.getBoundingClientRect(); const wasPositioned = managed.expanded || Boolean(managed.placement); if (wasPositioned) { freeBounds.current = { left: rect.left, top: rect.top, width: rect.width, height: rect.height }; setPosition({ x: 0, y: 0 }) }; managed.activate(); if (managed.expanded) managed.toggleExpanded(); if (managed.placement) managed.setPlacement(null); drag.current = { x: event.clientX, y: event.clientY, dx: wasPositioned ? 0 : position.x, dy: wasPositioned ? 0 : position.y }; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); event.stopPropagation() }}
    onPointerMove={(event) => { const start = drag.current; if (start) move(start.dx + event.clientX - start.x, start.dy + event.clientY - start.y) }}
    onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}
    onKeyDown={(event) => { if (event.target !== event.currentTarget || managed.expanded || !event.key.startsWith('Arrow')) return; event.preventDefault(); move(position.x + (event.key === 'ArrowRight' ? 12 : event.key === 'ArrowLeft' ? -12 : 0), position.y + (event.key === 'ArrowDown' ? 12 : event.key === 'ArrowUp' ? -12 : 0)) }}>
    <span title="Trascina per spostare. Usa le frecce da tastiera."><Move size={15}/></span><nav><WindowControls title={title} expanded={managed.expanded} minimize={managed.minimize} toggleExpanded={managed.toggleExpanded} onPosition={slot => { setPosition({ x: 0, y: 0 }); managed.setPlacement(slot) }}/><button type="button" onClick={close} aria-label={`Chiudi finestra di lavoro ${title}`}><X size={16}/></button></nav>
  </div>, controlsTarget)}</>
}
export function ExistingWorkWindows() {
  const [nodes, setNodes] = useState<ExistingWindowEntry[]>([])
  useEffect(() => {
    const scan = () => {
      const next = [...document.querySelectorAll<HTMLElement>('[role="dialog"]:not(.iu-managed-window)')].filter((node) => node.dataset.windowMinimized === 'true' || (node.getBoundingClientRect().width > 0 && node.getBoundingClientRect().height > 0 && getComputedStyle(node).visibility !== 'hidden' && node.getAttribute('aria-hidden') !== 'true')).map(node => {
        const pane = (node.querySelector(':scope > [class*="__box"], :scope > [class*="-box"], :scope > [class*="__panel"], :scope > section') as HTMLElement | null) || node
        return { node, pane, header: pane.querySelector<HTMLElement>(':scope > header'), title: node.getAttribute('aria-label') || node.querySelector('h1,h2,h3,strong')?.textContent || 'Attività dello studio' }
      })
      setNodes((current) => current.length === next.length && current.every((entry, index) => entry.node === next[index].node && entry.pane === next[index].pane && entry.header === next[index].header && entry.title === next[index].title) ? current : next)
    }
    scan()
    const observer = new MutationObserver(scan)
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden', 'aria-hidden', 'aria-label'] })
    return () => observer.disconnect()
  }, [])
  const ids = useRef(new WeakMap<HTMLElement, number>())
  const sequence = useRef(0)
  return <>{nodes.map((entry) => { if (!ids.current.has(entry.node)) ids.current.set(entry.node, ++sequence.current); return <ExistingWindow {...entry} key={ids.current.get(entry.node)}/> })}</>
}
