import { useEffect, type RefObject } from 'react'
import { flushSync } from 'react-dom'
import { clampZoom } from './pageGeometry'

type Options = {
  viewportRef: RefObject<HTMLDivElement | null>
  frameRef: RefObject<HTMLDivElement | null>
  zoomRef: RefObject<number>
  onZoom: (value: number) => void
}

type Anchor = { contentX: number; contentY: number }

type Point = { clientX: number; clientY: number }

export function touchDistance(first: Point, second: Point): number {
  return Math.hypot(second.clientX - first.clientX, second.clientY - first.clientY)
}

export function touchMidpoint(first: Point, second: Point): Point {
  return { clientX: (first.clientX + second.clientX) / 2, clientY: (first.clientY + second.clientY) / 2 }
}

/** Zoom proporzionale alla distanza tra le dita, limitato ai valori ammessi dal foglio. */
export function pinchZoomValue(startZoom: number, startDistance: number, currentDistance: number): number {
  if (!(startDistance > 0) || !(currentDistance > 0)) return clampZoom(startZoom)
  return clampZoom(startZoom * (currentDistance / startDistance))
}

/**
 * Pizzico a due dita (telefono/tablet) e Ctrl + rotella o pizzico del trackpad (desktop):
 * ingrandisce o riduce solo il foglio, mantenendo fermo il punto del testo sotto le dita.
 */
export function usePinchZoom({ viewportRef, frameRef, zoomRef, onZoom }: Options) {
  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) return undefined
    let startDistance = 0
    let startZoom = 1
    let anchor: Anchor | null = null
    let frame = 0
    let pending: { zoom: number; point: Point } | null = null

    const anchorAt = (point: Point): Anchor | null => {
      const rect = frameRef.current?.getBoundingClientRect()
      const zoom = zoomRef.current || 1
      if (!rect) return null
      return { contentX: (point.clientX - rect.left) / zoom, contentY: (point.clientY - rect.top) / zoom }
    }

    const apply = () => {
      frame = 0
      const next = pending
      pending = null
      if (!next || !anchor) return
      flushSync(() => onZoom(next.zoom))
      const rect = frameRef.current?.getBoundingClientRect()
      if (!rect) return
      viewport.scrollLeft += rect.left + (anchor.contentX * next.zoom) - next.point.clientX
      viewport.scrollTop += rect.top + (anchor.contentY * next.zoom) - next.point.clientY
    }

    const schedule = (zoom: number, point: Point) => {
      pending = { zoom, point }
      if (!frame) frame = window.requestAnimationFrame(apply)
    }

    const end = () => {
      startDistance = 0
      anchor = null
      viewport.classList.remove('is-pinching')
    }

    const onTouchStart = (event: TouchEvent) => {
      if (event.touches.length !== 2) return
      const [first, second] = [event.touches[0], event.touches[1]]
      startDistance = touchDistance(first, second)
      startZoom = zoomRef.current || 1
      anchor = anchorAt(touchMidpoint(first, second))
      viewport.classList.add('is-pinching')
    }

    const onTouchMove = (event: TouchEvent) => {
      if (!startDistance || event.touches.length !== 2) return
      event.preventDefault()
      const [first, second] = [event.touches[0], event.touches[1]]
      schedule(pinchZoomValue(startZoom, startDistance, touchDistance(first, second)), touchMidpoint(first, second))
    }

    const onTouchEnd = (event: TouchEvent) => {
      if (event.touches.length < 2) end()
    }

    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return
      event.preventDefault()
      const point = { clientX: event.clientX, clientY: event.clientY }
      if (!pending) anchor = anchorAt(point)
      const base = pending?.zoom ?? (zoomRef.current || 1)
      schedule(clampZoom(base * Math.exp(-event.deltaY * 0.0025)), point)
    }

    // Safari iOS: evita lo zoom dell'intera pagina durante il pizzico sul foglio.
    const onGesture = (event: Event) => event.preventDefault()

    viewport.addEventListener('touchstart', onTouchStart, { passive: true })
    viewport.addEventListener('touchmove', onTouchMove, { passive: false })
    viewport.addEventListener('touchend', onTouchEnd, { passive: true })
    viewport.addEventListener('touchcancel', end, { passive: true })
    viewport.addEventListener('wheel', onWheel, { passive: false })
    viewport.addEventListener('gesturestart', onGesture)
    viewport.addEventListener('gesturechange', onGesture)
    return () => {
      window.cancelAnimationFrame(frame)
      viewport.removeEventListener('touchstart', onTouchStart)
      viewport.removeEventListener('touchmove', onTouchMove)
      viewport.removeEventListener('touchend', onTouchEnd)
      viewport.removeEventListener('touchcancel', end)
      viewport.removeEventListener('wheel', onWheel)
      viewport.removeEventListener('gesturestart', onGesture)
      viewport.removeEventListener('gesturechange', onGesture)
    }
  }, [viewportRef, frameRef, zoomRef, onZoom])
}
