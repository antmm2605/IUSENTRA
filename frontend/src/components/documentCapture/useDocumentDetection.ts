import { useEffect, useRef, useState, type RefObject } from 'react'
import type { Quad } from './detection/documentQuad'
import { detectQuadOnSource } from './detection/pageProcessing'

export type DetectionState = { quad: Quad | null; stable: boolean }

const INTERVAL_MS = 125
const STABLE_FRAMES = 6
const LOST_FRAMES = 4
const MOVEMENT_LIMIT = 0.012

/** Spostamento medio degli angoli, in frazione del lato dell'inquadratura. */
export function quadMovement(previous: Quad, next: Quad): number {
  return previous.reduce((sum, point, index) => sum + Math.hypot(point.x - next[index].x, point.y - next[index].y), 0) / 4
}

/** Media mobile degli angoli: il riquadro segue il foglio senza tremolare. */
export function smoothQuad(previous: Quad | null, next: Quad, weight = 0.4): Quad {
  if (!previous || quadMovement(previous, next) > 0.08) return next
  return previous.map((point, index) => ({
    x: point.x + ((next[index].x - point.x) * weight),
    y: point.y + ((next[index].y - point.y) * weight),
  })) as Quad
}

/** Analizza l'inquadratura circa 8 volte al secondo finché la fotocamera è attiva. */
export function useDocumentDetection(videoRef: RefObject<HTMLVideoElement | null>, active: boolean): DetectionState {
  const [state, setState] = useState<DetectionState>({ quad: null, stable: false })
  const memory = useRef({ quad: null as Quad | null, steady: 0, lost: 0 })

  useEffect(() => {
    if (!active) {
      memory.current = { quad: null, steady: 0, lost: 0 }
      setState({ quad: null, stable: false })
      return undefined
    }
    const scratch = document.createElement('canvas')
    let timer = 0
    let cancelled = false
    const tick = () => {
      if (cancelled) return
      const video = videoRef.current
      if (video && video.readyState >= 2 && video.videoWidth && !document.hidden) {
        let detected: Quad | null = null
        try { detected = detectQuadOnSource(video, video.videoWidth, video.videoHeight, scratch) } catch { detected = null }
        const current = memory.current
        if (detected) {
          const smoothed = smoothQuad(current.quad, detected)
          current.steady = current.quad && quadMovement(current.quad, detected) < MOVEMENT_LIMIT ? current.steady + 1 : 0
          current.quad = smoothed
          current.lost = 0
        } else if (current.quad && current.lost < LOST_FRAMES) {
          current.lost += 1
          current.steady = 0
        } else {
          current.quad = null
          current.steady = 0
        }
        setState({ quad: current.quad, stable: Boolean(current.quad) && current.steady >= STABLE_FRAMES })
      }
      timer = window.setTimeout(tick, INTERVAL_MS)
    }
    timer = window.setTimeout(tick, INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
      scratch.width = 0
      scratch.height = 0
    }
  }, [active, videoRef])

  return state
}
