/**
 * Resa della pagina acquisita. «Documento nitido» uniforma lo sfondo (ombre e luce
 * irregolare) e aumenta il contrasto del testo; «Bianco e nero» applica poi una soglia,
 * come richiesto per la scansione dell'atto penale di parte (Specifiche tecniche
 * DGSIA, art. 15, comma 1, lett. g: bianco e nero, 200 dpi).
 */
import { otsuThreshold } from './grayImage'

export type PageFilter = 'colore' | 'grigi' | 'documento' | 'bianco-nero'

export const PAGE_FILTERS: Array<{ value: PageFilter; label: string }> = [
  { value: 'documento', label: 'Documento nitido' },
  { value: 'colore', label: 'Colore originale' },
  { value: 'grigi', label: 'Scala di grigi' },
  { value: 'bianco-nero', label: 'Bianco e nero' },
]

function luminance(pixels: Uint8ClampedArray): Float32Array {
  const output = new Float32Array(pixels.length / 4)
  for (let index = 0; index < output.length; index += 1) {
    const offset = index * 4
    output[index] = (pixels[offset] * 0.299) + (pixels[offset + 1] * 0.587) + (pixels[offset + 2] * 0.114)
  }
  return output
}

/** Stima dello sfondo: massimo per blocchi (il foglio è la parte chiara), poi interpolazione. */
export function estimateBackground(gray: Float32Array, width: number, height: number, block = 24): Float32Array {
  const columns = Math.max(1, Math.ceil(width / block))
  const rows = Math.max(1, Math.ceil(height / block))
  const small = new Float32Array(columns * rows)
  for (let y = 0; y < height; y += 1) {
    const row = Math.floor(y / block) * columns
    for (let x = 0; x < width; x += 1) {
      const cell = row + Math.floor(x / block)
      const value = gray[(y * width) + x]
      if (value > small[cell]) small[cell] = value
    }
  }
  const smooth = new Float32Array(small.length)
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < columns; c += 1) {
      let sum = 0
      let count = 0
      for (let dr = -1; dr <= 1; dr += 1) for (let dc = -1; dc <= 1; dc += 1) {
        const rr = r + dr
        const cc = c + dc
        if (rr >= 0 && cc >= 0 && rr < rows && cc < columns) { sum += small[(rr * columns) + cc]; count += 1 }
      }
      smooth[(r * columns) + c] = sum / count
    }
  }
  const output = new Float32Array(width * height)
  for (let y = 0; y < height; y += 1) {
    const gy = Math.min(rows - 1, Math.max(0, (y / block) - 0.5))
    const r0 = Math.floor(gy)
    const r1 = Math.min(rows - 1, r0 + 1)
    const fy = gy - r0
    for (let x = 0; x < width; x += 1) {
      const gx = Math.min(columns - 1, Math.max(0, (x / block) - 0.5))
      const c0 = Math.floor(gx)
      const c1 = Math.min(columns - 1, c0 + 1)
      const fx = gx - c0
      const top = (smooth[(r0 * columns) + c0] * (1 - fx)) + (smooth[(r0 * columns) + c1] * fx)
      const bottom = (smooth[(r1 * columns) + c0] * (1 - fx)) + (smooth[(r1 * columns) + c1] * fx)
      output[(y * width) + x] = (top * (1 - fy)) + (bottom * fy)
    }
  }
  return output
}

/** Applica la resa scelta in-place sui pixel RGBA. */
export function applyPageFilter(pixels: Uint8ClampedArray, width: number, height: number, filter: PageFilter): Uint8ClampedArray {
  if (filter === 'colore') return pixels
  const gray = luminance(pixels)
  let values = gray
  if (filter === 'documento' || filter === 'bianco-nero') {
    const background = estimateBackground(gray, width, height)
    values = new Float32Array(gray.length)
    for (let index = 0; index < gray.length; index += 1) {
      const normalized = Math.min(255, (gray[index] / Math.max(24, background[index])) * 255)
      values[index] = Math.max(0, Math.min(255, ((normalized - 70) * 255) / 170))
    }
  }
  const threshold = filter === 'bianco-nero' ? Math.min(215, Math.max(120, otsuThreshold(values))) : -1
  for (let index = 0; index < values.length; index += 1) {
    const value = threshold >= 0 ? (values[index] > threshold ? 255 : 0) : values[index]
    const offset = index * 4
    pixels[offset] = value
    pixels[offset + 1] = value
    pixels[offset + 2] = value
    pixels[offset + 3] = 255
  }
  return pixels
}
