/**
 * Affinamento degli angoli: per ogni lato cerca il bordo più forte in direzione
 * perpendicolare, adatta una retta ai punti trovati e ricava gli angoli come
 * intersezioni dei lati adiacenti. Riduce l'errore dei contorni arrotondati o rumorosi.
 */
import type { Point, Quad } from './documentQuad'

type Line = { point: Point; direction: Point }

const SEARCH_PX = 8
const SAMPLES = 28

function fitLine(points: Point[]): Line | null {
  if (points.length < 6) return null
  const center = points.reduce((sum, point) => ({ x: sum.x + (point.x / points.length), y: sum.y + (point.y / points.length) }), { x: 0, y: 0 })
  let xx = 0
  let xy = 0
  let yy = 0
  for (const point of points) {
    const dx = point.x - center.x
    const dy = point.y - center.y
    xx += dx * dx
    xy += dx * dy
    yy += dy * dy
  }
  const angle = 0.5 * Math.atan2(2 * xy, xx - yy)
  return { point: center, direction: { x: Math.cos(angle), y: Math.sin(angle) } }
}

function intersect(first: Line, second: Line): Point | null {
  const determinant = (first.direction.x * second.direction.y) - (first.direction.y * second.direction.x)
  if (Math.abs(determinant) < 1e-6) return null
  const dx = second.point.x - first.point.x
  const dy = second.point.y - first.point.y
  const t = ((dx * second.direction.y) - (dy * second.direction.x)) / determinant
  return { x: first.point.x + (first.direction.x * t), y: first.point.y + (first.direction.y * t) }
}

function sideEdgePoints(from: Point, to: Point, magnitude: Float32Array, width: number, height: number, threshold: number): Point[] {
  const length = Math.hypot(to.x - from.x, to.y - from.y) || 1
  const normal = { x: -(to.y - from.y) / length, y: (to.x - from.x) / length }
  const found: Point[] = []
  for (let step = 2; step < SAMPLES - 1; step += 1) {
    const base = { x: from.x + ((to.x - from.x) * step / SAMPLES), y: from.y + ((to.y - from.y) * step / SAMPLES) }
    let best = threshold
    let bestPoint: Point | null = null
    for (let offset = -SEARCH_PX; offset <= SEARCH_PX; offset += 1) {
      const x = Math.round(base.x + (normal.x * offset))
      const y = Math.round(base.y + (normal.y * offset))
      if (x < 1 || y < 1 || x >= width - 1 || y >= height - 1) continue
      const value = magnitude[(y * width) + x]
      if (value > best) { best = value; bestPoint = { x, y } }
    }
    if (bestPoint) found.push(bestPoint)
  }
  return found
}

export function refineQuad(quad: Quad, magnitude: Float32Array, width: number, height: number, threshold: number): Quad {
  const lines = quad.map((point, index) => {
    const next = quad[(index + 1) % 4]
    return fitLine(sideEdgePoints(point, next, magnitude, width, height, threshold))
      || { point, direction: { x: next.x - point.x, y: next.y - point.y } }
  })
  const refined = quad.map((original, index) => {
    const corner = intersect(lines[(index + 3) % 4], lines[index])
    if (!corner || Math.hypot(corner.x - original.x, corner.y - original.y) > SEARCH_PX * 2) return original
    return { x: Math.min(width, Math.max(0, corner.x)), y: Math.min(height, Math.max(0, corner.y)) }
  })
  return refined as Quad
}
