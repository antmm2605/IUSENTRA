/** Operazioni su canvas del browser: fotogramma, rilevamento su immagine, pagina finale JPEG. */
import type { CapturePage } from '../captureImages'
import { detectDocumentQuad, type Quad } from './documentQuad'
import { applyPageFilter, type PageFilter } from './enhance'
import { rgbaToGray } from './grayImage'
import { fullFrameQuad, outputSizeForQuad, scaleQuad, warpPerspective, type Size } from './perspective'

export type CaptureProfile = 'allegato' | 'penale-200'

export type CapturedImage = { canvas: HTMLCanvasElement; width: number; height: number; quad: Quad | null; source: 'fotocamera' | 'scanner' | 'foto' }

/** A4 a 200 dpi (Specifiche tecniche DGSIA, art. 15, comma 1, lett. g). */
export const PENAL_200_DPI: Size = { width: 1654, height: 2339 }
const DETECTION_WIDTH = 320
const MAX_PIXELS = 50_000_000

function context2d(canvas: HTMLCanvasElement) {
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('Elaborazione immagine non disponibile in questo browser.')
  return context
}

export function canvasFromSource(source: CanvasImageSource, width: number, height: number): HTMLCanvasElement {
  if (!width || !height) throw new Error('Attendi che l’inquadratura sia visibile.')
  if (width * height > MAX_PIXELS) throw new Error('L’immagine supera 50 megapixel. Riduci la risoluzione e riprova.')
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = context2d(canvas)
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, width, height)
  context.drawImage(source, 0, 0, width, height)
  return canvas
}

/** Rilevamento su una copia ridotta: restituisce angoli normalizzati (0–1) o null. */
export function detectQuadOnSource(source: CanvasImageSource, width: number, height: number, scratch?: HTMLCanvasElement): Quad | null {
  if (!width || !height) return null
  const scale = Math.min(1, DETECTION_WIDTH / width)
  const canvas = scratch || document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(width * scale))
  canvas.height = Math.max(1, Math.round(height * scale))
  const context = context2d(canvas)
  context.drawImage(source, 0, 0, canvas.width, canvas.height)
  const pixels = context.getImageData(0, 0, canvas.width, canvas.height)
  const gray = rgbaToGray(pixels.data, canvas.width, canvas.height)
  const found = detectDocumentQuad(gray)
  if (!found) return null
  // Rientro di un pixel e mezzo della copia ridotta: il bordo del tavolo non entra nella pagina.
  const center = found.quad.reduce((sum, point) => ({ x: sum.x + (point.x / 4), y: sum.y + (point.y / 4) }), { x: 0, y: 0 })
  return found.quad.map((point) => {
    const distance = Math.hypot(point.x - center.x, point.y - center.y) || 1
    const inset = Math.min(1, 1.5 / distance)
    return { x: (point.x + ((center.x - point.x) * inset)) / gray.width, y: (point.y + ((center.y - point.y) * inset)) / gray.height }
  }) as Quad
}

/** Foto o scansione caricata come file: orientamento EXIF applicato, metadati non copiati. */
export async function capturedImageFromFile(file: File, source: CapturedImage['source']): Promise<CapturedImage> {
  if (!file.size || file.size > 60 * 1024 * 1024) throw new Error('L’immagine è vuota o supera 60 MB.')
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) throw new Error('Usa una foto JPEG, PNG o WebP.')
  let bitmap: ImageBitmap
  try { bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' }) }
  catch { throw new Error('L’immagine non è leggibile. Ripeti l’acquisizione.') }
  try {
    const canvas = canvasFromSource(bitmap, bitmap.width, bitmap.height)
    const quad = source === 'scanner' ? null : detectQuadOnSource(canvas, canvas.width, canvas.height)
    return { canvas, width: canvas.width, height: canvas.height, quad, source }
  } finally { bitmap.close() }
}

const nextFrame = () => new Promise<void>((resolve) => window.setTimeout(resolve, 16))

/** Raddrizza, applica la resa e codifica la pagina in JPEG pronta per il PDF. */
export async function renderCapturePage(image: CapturedImage, quad: Quad | null, filter: PageFilter, profile: CaptureProfile, index: number): Promise<CapturePage> {
  await nextFrame()
  const size = { width: image.width, height: image.height }
  const corners = quad ? scaleQuad(quad, size) : fullFrameQuad(size)
  const natural = outputSizeForQuad(corners)
  const fixed = profile === 'penale-200'
    ? (natural.width > natural.height ? { width: PENAL_200_DPI.height, height: PENAL_200_DPI.width } : PENAL_200_DPI)
    : undefined
  const output = outputSizeForQuad(corners, fixed)
  const source = context2d(image.canvas).getImageData(0, 0, image.width, image.height)
  const pixels = quad || fixed ? warpPerspective(source.data, size, corners, output) : source.data
  const target = quad || fixed ? output : size
  applyPageFilter(pixels, target.width, target.height, profile === 'penale-200' ? 'bianco-nero' : filter)
  const canvas = document.createElement('canvas')
  canvas.width = target.width
  canvas.height = target.height
  context2d(canvas).putImageData(new ImageData(pixels, target.width, target.height), 0, 0)
  try {
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => (value ? resolve(value) : reject(new Error('Pagina non elaborata. Riprova.'))), 'image/jpeg', 0.92))
    const file = new File([blob], `pagina-${String(index).padStart(3, '0')}.jpg`, { type: 'image/jpeg' })
    return { id: crypto.randomUUID(), file, url: URL.createObjectURL(blob), rotation: 0 }
  } finally {
    canvas.width = 0
    canvas.height = 0
  }
}
