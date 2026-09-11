/**
 * Raddrizzamento prospettico del foglio: omografia tra i quattro angoli scelti e il
 * rettangolo di destinazione, campionamento bilineare. Tutto avviene nel browser.
 */
import type { Point, Quad } from './documentQuad'

export type Size = { width: number; height: number }
export type Homography = [number, number, number, number, number, number, number, number]

export const A4_RATIO = 297 / 210
/** A4 a 300 dpi: lato lungo massimo per pagine di qualità documento. */
export const MAX_LONG_SIDE = 3508

/** Risolve il sistema lineare 8×8 con eliminazione di Gauss e pivot parziale. */
function solve(matrix: number[][], vector: number[]): number[] | null {
  const size = vector.length
  const rows = matrix.map((row, index) => [...row, vector[index]])
  for (let column = 0; column < size; column += 1) {
    let pivot = column
    for (let row = column + 1; row < size; row += 1) if (Math.abs(rows[row][column]) > Math.abs(rows[pivot][column])) pivot = row
    if (Math.abs(rows[pivot][column]) < 1e-10) return null
    ;[rows[column], rows[pivot]] = [rows[pivot], rows[column]]
    for (let row = 0; row < size; row += 1) {
      if (row === column) continue
      const factor = rows[row][column] / rows[column][column]
      for (let cell = column; cell <= size; cell += 1) rows[row][cell] -= factor * rows[column][cell]
    }
  }
  return rows.map((row, index) => row[size] / row[index])
}

/** Omografia che porta ciascun punto `from[i]` in `to[i]`. */
export function computeHomography(from: Quad, to: Quad): Homography | null {
  const matrix: number[][] = []
  const vector: number[] = []
  for (let index = 0; index < 4; index += 1) {
    const { x, y } = from[index]
    const { x: u, y: v } = to[index]
    matrix.push([x, y, 1, 0, 0, 0, -u * x, -u * y])
    vector.push(u)
    matrix.push([0, 0, 0, x, y, 1, -v * x, -v * y])
    vector.push(v)
  }
  const solution = solve(matrix, vector)
  return solution ? solution as Homography : null
}

export function projectPoint(h: Homography, point: Point): Point {
  const denominator = (h[6] * point.x) + (h[7] * point.y) + 1
  return { x: ((h[0] * point.x) + (h[1] * point.y) + h[2]) / denominator, y: ((h[3] * point.x) + (h[4] * point.y) + h[5]) / denominator }
}

const distance = (a: Point, b: Point) => Math.hypot(b.x - a.x, b.y - a.y)

/**
 * Dimensioni del foglio raddrizzato: media dei lati opposti, proporzione A4 se vicina
 * (tolleranza 10%), nessun ingrandimento oltre la risoluzione acquisita.
 */
export function outputSizeForQuad(quad: Quad, fixed?: Size): Size {
  if (fixed) return fixed
  let width = Math.max(distance(quad[0], quad[1]), distance(quad[3], quad[2]))
  let height = Math.max(distance(quad[0], quad[3]), distance(quad[1], quad[2]))
  const ratio = height / Math.max(1, width)
  if (Math.abs(ratio - A4_RATIO) / A4_RATIO < 0.1) height = width * A4_RATIO
  else if (Math.abs((1 / ratio) - A4_RATIO) / A4_RATIO < 0.1) width = height * A4_RATIO
  const scale = Math.min(1, MAX_LONG_SIDE / Math.max(width, height))
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) }
}

/** Esegue il raddrizzamento su pixel RGBA; restituisce i pixel del foglio. */
export function warpPerspective(source: Uint8ClampedArray, sourceSize: Size, quad: Quad, output: Size): Uint8ClampedArray<ArrayBuffer> {
  const target: Quad = [{ x: 0, y: 0 }, { x: output.width, y: 0 }, { x: output.width, y: output.height }, { x: 0, y: output.height }]
  const inverse = computeHomography(target, quad)
  if (!inverse) throw new Error('Angoli del foglio non validi. Riposizionali e riprova.')
  const pixels = new Uint8ClampedArray(output.width * output.height * 4)
  const maxX = sourceSize.width - 1
  const maxY = sourceSize.height - 1
  const [h0, h1, h2, h3, h4, h5, h6, h7] = inverse
  for (let y = 0; y < output.height; y += 1) {
    const cy = y + 0.5
    for (let x = 0; x < output.width; x += 1) {
      const cx = x + 0.5
      const denominator = (h6 * cx) + (h7 * cy) + 1
      const sx = Math.min(maxX, Math.max(0, (((h0 * cx) + (h1 * cy) + h2) / denominator) - 0.5))
      const sy = Math.min(maxY, Math.max(0, (((h3 * cx) + (h4 * cy) + h5) / denominator) - 0.5))
      const x0 = Math.floor(sx)
      const y0 = Math.floor(sy)
      const x1 = Math.min(maxX, x0 + 1)
      const y1 = Math.min(maxY, y0 + 1)
      const fx = sx - x0
      const fy = sy - y0
      const i00 = ((y0 * sourceSize.width) + x0) * 4
      const i10 = ((y0 * sourceSize.width) + x1) * 4
      const i01 = ((y1 * sourceSize.width) + x0) * 4
      const i11 = ((y1 * sourceSize.width) + x1) * 4
      const offset = ((y * output.width) + x) * 4
      for (let channel = 0; channel < 3; channel += 1) {
        const top = (source[i00 + channel] * (1 - fx)) + (source[i10 + channel] * fx)
        const bottom = (source[i01 + channel] * (1 - fx)) + (source[i11 + channel] * fx)
        pixels[offset + channel] = (top * (1 - fy)) + (bottom * fy)
      }
      pixels[offset + 3] = 255
    }
  }
  return pixels
}

/** Quadrilatero che copre l'intera immagine (nessun ritaglio). */
export function fullFrameQuad(size: Size): Quad {
  return [{ x: 0, y: 0 }, { x: size.width, y: 0 }, { x: size.width, y: size.height }, { x: 0, y: size.height }]
}

/** Converte coordinate normalizzate (0–1) in pixel dell'immagine. */
export function scaleQuad(quad: Quad, size: Size): Quad {
  return quad.map((point) => ({ x: point.x * size.width, y: point.y * size.height })) as Quad
}
