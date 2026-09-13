/**
 * Rilevamento del foglio nell'inquadratura (webcam del PC o fotocamera del telefono).
 * Lavora su una copia ridotta in scala di grigi: due strategie indipendenti (foglio più
 * chiaro dello sfondo, contorno chiuso dai bordi) propongono un quadrilatero; vince quello
 * con il miglior supporto di bordo reale lungo i quattro lati. Nessun dato lascia il browser.
 */
import { boxBlur, flattenIllumination, gradientMagnitude, morphOpen, otsuThreshold, type GrayImage } from './grayImage'
import { refineQuad } from './quadRefine'

export type Point = { x: number; y: number }
export type Quad = [Point, Point, Point, Point]

const MIN_AREA_RATIO = 0.10
const MIN_EDGE_SUPPORT = 0.42
// Un foglio inquadrato di sbieco può avere angoli lontani dai 90°: la soglia
// serve solo a scartare i quadrilateri degeneri, non a pretendere un rettangolo.
const ANGOLO_MINIMO = 32
const ANGOLO_MASSIMO = 148
// Nessun formato di carta arriva a un lato dieci volte l'altro: oltre questo
// rapporto si tratta di una striscia dello sfondo, non della pagina.
const RAPPORTO_LATI_MASSIMO = 6

function cross(o: Point, a: Point, b: Point) {
  return ((a.x - o.x) * (b.y - o.y)) - ((a.y - o.y) * (b.x - o.x))
}

export function convexHull(points: Point[]): Point[] {
  const sorted = [...points].sort((a, b) => a.x - b.x || a.y - b.y)
  if (sorted.length < 3) return sorted
  const lower: Point[] = []
  for (const point of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) lower.pop()
    lower.push(point)
  }
  const upper: Point[] = []
  for (let index = sorted.length - 1; index >= 0; index -= 1) {
    const point = sorted[index]
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) upper.pop()
    upper.push(point)
  }
  return [...lower.slice(0, -1), ...upper.slice(0, -1)]
}

export function polygonArea(points: Point[]): number {
  let area = 0
  for (let index = 0; index < points.length; index += 1) {
    const next = points[(index + 1) % points.length]
    area += (points[index].x * next.y) - (next.x * points[index].y)
  }
  return Math.abs(area) / 2
}

/** Riduce il poligono convesso a 4 vertici togliendo ogni volta l'angolo meno significativo. */
export function simplifyToQuad(hull: Point[]): Quad | null {
  if (hull.length < 4) return null
  const polygon = [...hull]
  while (polygon.length > 4) {
    let weakest = 0
    let smallest = Number.POSITIVE_INFINITY
    for (let index = 0; index < polygon.length; index += 1) {
      const previous = polygon[(index - 1 + polygon.length) % polygon.length]
      const next = polygon[(index + 1) % polygon.length]
      const area = Math.abs(cross(previous, polygon[index], next))
      if (area < smallest) { smallest = area; weakest = index }
    }
    polygon.splice(weakest, 1)
  }
  return orderQuad(polygon as Quad)
}

/** Ordine fisso: alto-sinistra, alto-destra, basso-destra, basso-sinistra. */
export function orderQuad(points: Point[]): Quad {
  const center = points.reduce((sum, point) => ({ x: sum.x + (point.x / points.length), y: sum.y + (point.y / points.length) }), { x: 0, y: 0 })
  const byAngle = [...points].sort((a, b) => Math.atan2(a.y - center.y, a.x - center.x) - Math.atan2(b.y - center.y, b.x - center.x))
  let start = 0
  byAngle.forEach((point, index) => { if (point.x + point.y < byAngle[start].x + byAngle[start].y) start = index })
  return [0, 1, 2, 3].map((offset) => byAngle[(start + offset) % 4]) as Quad
}

function interiorAnglesValid(quad: Quad) {
  for (let index = 0; index < 4; index += 1) {
    const previous = quad[(index + 3) % 4]
    const current = quad[index]
    const next = quad[(index + 1) % 4]
    const ax = previous.x - current.x
    const ay = previous.y - current.y
    const bx = next.x - current.x
    const by = next.y - current.y
    const cosine = ((ax * bx) + (ay * by)) / ((Math.hypot(ax, ay) * Math.hypot(bx, by)) || 1)
    const degrees = Math.acos(Math.max(-1, Math.min(1, cosine))) * 180 / Math.PI
    if (degrees < ANGOLO_MINIMO || degrees > ANGOLO_MASSIMO) return false
  }
  return true
}

/** Quota di punti lungo i lati con un bordo reale entro 2 pixel. */
export function edgeSupport(quad: Quad, magnitude: Float32Array, width: number, height: number, threshold: number): number {
  let hits = 0
  let samples = 0
  for (let side = 0; side < 4; side += 1) {
    const from = quad[side]
    const to = quad[(side + 1) % 4]
    for (let step = 1; step < 24; step += 1) {
      const x = from.x + ((to.x - from.x) * step / 24)
      const y = from.y + ((to.y - from.y) * step / 24)
      samples += 1
      let found = false
      for (let dy = -2; dy <= 2 && !found; dy += 1) {
        for (let dx = -2; dx <= 2 && !found; dx += 1) {
          const px = Math.round(x + dx)
          const py = Math.round(y + dy)
          if (px >= 0 && py >= 0 && px < width && py < height && magnitude[(py * width) + px] >= threshold) found = true
        }
      }
      if (found) hits += 1
    }
  }
  return samples ? hits / samples : 0
}

/** Componente connessa più estesa; restituisce per ogni riga gli estremi, sufficienti al guscio convesso. */
export function largestComponentOutline(mask: Uint8Array, width: number, height: number): Point[] {
  const labels = new Int32Array(width * height)
  const stack = new Int32Array(width * height)
  let bestLabel = 0
  let bestSize = 0
  let label = 0
  for (let start = 0; start < mask.length; start += 1) {
    if (!mask[start] || labels[start]) continue
    label += 1
    let size = 0
    let top = 0
    stack[top++] = start
    labels[start] = label
    while (top) {
      const index = stack[--top]
      size += 1
      const x = index % width
      if (x > 0 && mask[index - 1] && !labels[index - 1]) { labels[index - 1] = label; stack[top++] = index - 1 }
      if (x < width - 1 && mask[index + 1] && !labels[index + 1]) { labels[index + 1] = label; stack[top++] = index + 1 }
      if (index >= width && mask[index - width] && !labels[index - width]) { labels[index - width] = label; stack[top++] = index - width }
      if (index + width < mask.length && mask[index + width] && !labels[index + width]) { labels[index + width] = label; stack[top++] = index + width }
    }
    if (size > bestSize) { bestSize = size; bestLabel = label }
  }
  const outline: Point[] = []
  if (!bestLabel) return outline
  for (let y = 0; y < height; y += 1) {
    let first = -1
    let last = -1
    for (let x = 0; x < width; x += 1) {
      if (labels[(y * width) + x] === bestLabel) { if (first < 0) first = x; last = x }
    }
    if (first >= 0) outline.push({ x: first, y }, { x: last, y })
  }
  return outline
}

function brightPaperMask(flattened: GrayImage): Uint8Array {
  const threshold = otsuThreshold(flattened.data)
  const mask = Uint8Array.from(flattened.data, (value) => (value > threshold ? 1 : 0))
  return morphOpen(mask, flattened.width, flattened.height)
}

/** Rapporto fra i lati opposti: quanto il quadrilatero somiglia a un foglio. */
function sideRatioValid(quad: Quad): boolean {
  const sides = [0, 1, 2, 3].map((index) => {
    const from = quad[index]
    const to = quad[(index + 1) % 4]
    return Math.hypot(to.x - from.x, to.y - from.y)
  })
  const shortest = Math.min(...sides)
  if (shortest <= 0) return false
  return (Math.max(...sides) / shortest) <= RAPPORTO_LATI_MASSIMO
}

/**
 * Quanto il quadrilatero riempie il proprio rettangolo circoscritto: un foglio
 * lo riempie quasi tutto, una macchia dello sfondo molto meno.
 */
function rectangularity(quad: Quad): number {
  const xs = quad.map((point) => point.x)
  const ys = quad.map((point) => point.y)
  const box = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys))
  return box > 0 ? Math.min(1, polygonArea(quad) / box) : 0
}

/** Regione racchiusa dai bordi: tutto ciò che non si raggiunge dal perimetro senza attraversare un bordo. */
function enclosedByEdgesMask(magnitude: Float32Array, width: number, height: number, threshold: number): Uint8Array {
  const edges = new Uint8Array(width * height)
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const index = (y * width) + x
      if (magnitude[index] >= threshold) for (let dy = -1; dy <= 1; dy += 1) for (let dx = -1; dx <= 1; dx += 1) edges[index + (dy * width) + dx] = 1
    }
  }
  const outside = new Uint8Array(width * height)
  const stack: number[] = []
  for (let x = 0; x < width; x += 1) stack.push(x, ((height - 1) * width) + x)
  for (let y = 0; y < height; y += 1) stack.push(y * width, (y * width) + width - 1)
  while (stack.length) {
    const index = stack.pop() as number
    if (outside[index] || edges[index]) continue
    outside[index] = 1
    const x = index % width
    if (x > 0) stack.push(index - 1)
    if (x < width - 1) stack.push(index + 1)
    if (index >= width) stack.push(index - width)
    if (index < (width * (height - 1))) stack.push(index + width)
  }
  return Uint8Array.from(outside, (value) => (value ? 0 : 1))
}

export function detectDocumentQuad(image: GrayImage): { quad: Quad; support: number } | null {
  const { width, height } = image
  if (width < 32 || height < 32) return null
  const blurred = boxBlur(boxBlur(image))
  const flattened = flattenIllumination(blurred)
  const magnitude = gradientMagnitude(blurred)
  const sorted = Float32Array.from(magnitude).sort()
  const edgeThreshold = Math.max(20, sorted[Math.floor(sorted.length * 0.88)])
  const frameArea = width * height
  let best: { quad: Quad; support: number; score: number } | null = null
  const masks = [
    brightPaperMask(flattened),
    brightPaperMask({ width, height, data: blurred.data }),
    enclosedByEdgesMask(magnitude, width, height, edgeThreshold),
  ]
  for (const mask of masks) {
    const quad = simplifyToQuad(convexHull(largestComponentOutline(mask, width, height)))
    if (!quad || !interiorAnglesValid(quad) || !sideRatioValid(quad)) continue
    const ratio = polygonArea(quad) / frameArea
    if (ratio < MIN_AREA_RATIO || ratio > 0.985) continue
    const support = edgeSupport(quad, magnitude, width, height, edgeThreshold * 0.6)
    if (support < MIN_EDGE_SUPPORT) continue
    // Fra più candidati vince quello che ha insieme bordi reali, forma da foglio
    // e una porzione plausibile dell'inquadratura: il solo supporto di bordo
    // premierebbe anche un rettangolo minuscolo ben contrastato.
    const score = (support * 0.6) + (rectangularity(quad) * 0.3) + (Math.min(ratio / 0.6, 1) * 0.1)
    if (!best || score > best.score) best = { quad, support, score }
  }
  return best ? { quad: refineQuad(best.quad, magnitude, width, height, edgeThreshold * 0.5), support: best.support } : null
}
