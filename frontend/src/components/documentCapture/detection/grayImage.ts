/** Operazioni elementari su immagini in scala di grigi, senza librerie esterne. */
export type GrayImage = { width: number; height: number; data: Uint8ClampedArray }

/** Luminanza ITU-R BT.601 da RGBA, con riduzione per media dei pixel del blocco. */
export function rgbaToGray(rgba: Uint8ClampedArray, width: number, height: number, targetWidth = width): GrayImage {
  const scale = Math.max(1, width / Math.max(1, targetWidth))
  const outWidth = Math.max(1, Math.round(width / scale))
  const outHeight = Math.max(1, Math.round(height / scale))
  const data = new Uint8ClampedArray(outWidth * outHeight)
  for (let y = 0; y < outHeight; y += 1) {
    const sourceY = Math.min(height - 1, Math.floor(y * scale))
    for (let x = 0; x < outWidth; x += 1) {
      const sourceX = Math.min(width - 1, Math.floor(x * scale))
      const offset = ((sourceY * width) + sourceX) * 4
      data[(y * outWidth) + x] = (rgba[offset] * 0.299) + (rgba[offset + 1] * 0.587) + (rgba[offset + 2] * 0.114)
    }
  }
  return { width: outWidth, height: outHeight, data }
}

/** Sfocatura a box separabile (raggio configurabile), bordi replicati. */
export function boxBlur(image: GrayImage, radius = 2): GrayImage {
  const { width, height, data } = image
  const size = (radius * 2) + 1
  const horizontal = new Float32Array(width * height)
  for (let y = 0; y < height; y += 1) {
    let sum = 0
    for (let dx = -radius; dx <= radius; dx += 1) sum += data[(y * width) + Math.min(width - 1, Math.max(0, dx))]
    for (let x = 0; x < width; x += 1) {
      horizontal[(y * width) + x] = sum / size
      const outgoing = data[(y * width) + Math.max(0, x - radius)]
      const incoming = data[(y * width) + Math.min(width - 1, x + radius + 1)]
      sum += incoming - outgoing
    }
  }
  const output = new Uint8ClampedArray(width * height)
  for (let x = 0; x < width; x += 1) {
    let sum = 0
    for (let dy = -radius; dy <= radius; dy += 1) sum += horizontal[(Math.min(height - 1, Math.max(0, dy)) * width) + x]
    for (let y = 0; y < height; y += 1) {
      output[(y * width) + x] = sum / size
      const outgoing = horizontal[(Math.max(0, y - radius) * width) + x]
      const incoming = horizontal[(Math.min(height - 1, y + radius + 1) * width) + x]
      sum += incoming - outgoing
    }
  }
  return { width, height, data: output }
}

/** Modulo del gradiente di Sobel; i bordi dell'immagine restano a zero. */
export function gradientMagnitude(image: GrayImage): Float32Array {
  const { width, height, data } = image
  const output = new Float32Array(width * height)
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const i = (y * width) + x
      const gx = (data[i - width + 1] + (2 * data[i + 1]) + data[i + width + 1]) - (data[i - width - 1] + (2 * data[i - 1]) + data[i + width - 1])
      const gy = (data[i + width - 1] + (2 * data[i + width]) + data[i + width + 1]) - (data[i - width - 1] + (2 * data[i - width]) + data[i - width + 1])
      output[i] = Math.hypot(gx, gy) / 4
    }
  }
  return output
}

/** Soglia di Otsu su valori 0–255. */
export function otsuThreshold(values: ArrayLike<number>): number {
  const histogram = new Float64Array(256)
  for (let index = 0; index < values.length; index += 1) histogram[Math.max(0, Math.min(255, Math.round(values[index])))] += 1
  const total = values.length || 1
  let sumAll = 0
  for (let level = 0; level < 256; level += 1) sumAll += level * histogram[level]
  let sumBackground = 0
  let weightBackground = 0
  let best = 0
  let threshold = 127
  for (let level = 0; level < 256; level += 1) {
    weightBackground += histogram[level]
    if (!weightBackground) continue
    const weightForeground = total - weightBackground
    if (!weightForeground) break
    sumBackground += level * histogram[level]
    const meanBackground = sumBackground / weightBackground
    const meanForeground = (sumAll - sumBackground) / weightForeground
    const between = weightBackground * weightForeground * ((meanBackground - meanForeground) ** 2)
    if (between > best) { best = between; threshold = level }
  }
  return threshold
}

/**
 * Toglie il gradiente di luce dalla pagina: ogni pixel viene confrontato con lo
 * sfondo locale invece che con una soglia unica. È la differenza fra riconoscere
 * un foglio illuminato di lato e non riconoscerlo affatto: con una sola soglia
 * globale la metà in ombra finisce fuori dal foglio.
 */
export function flattenIllumination(image: GrayImage): GrayImage {
  // Il raggio deve essere piu' grande del foglio, non piu' piccolo: la luce
  // varia sulla scala dell'inquadratura, la pagina no. Con un raggio corto lo
  // sfondo stimato coincide con la pagina stessa e la pagina sparisce, restando
  // solo le righe di testo. La sfocatura a box e' a somma scorrevole, quindi un
  // raggio grande non costa piu' di uno piccolo.
  const radius = Math.max(6, Math.round(Math.min(image.width, image.height) / 2))
  const background = boxBlur(boxBlur(image, radius), radius)
  const data = new Uint8ClampedArray(image.width * image.height)
  for (let index = 0; index < data.length; index += 1) {
    data[index] = 128 + image.data[index] - background.data[index]
  }
  return { width: image.width, height: image.height, data }
}

/** Erosione seguita da dilatazione: stacca il foglio dai ponti sottili con lo sfondo. */
export function morphOpen(mask: Uint8Array, width: number, height: number, radius = 1): Uint8Array {
  const eroded = new Uint8Array(width * height)
  const opened = new Uint8Array(width * height)
  const sweep = (source: Uint8Array, target: Uint8Array, keepWhenAnyNeighbourIs: 0 | 1) => {
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        let hit = keepWhenAnyNeighbourIs === 0 ? 1 : 0
        for (let dy = -radius; dy <= radius && hit !== keepWhenAnyNeighbourIs; dy += 1) {
          for (let dx = -radius; dx <= radius && hit !== keepWhenAnyNeighbourIs; dx += 1) {
            const nx = Math.min(width - 1, Math.max(0, x + dx))
            const ny = Math.min(height - 1, Math.max(0, y + dy))
            if (source[(ny * width) + nx] === keepWhenAnyNeighbourIs) hit = keepWhenAnyNeighbourIs
          }
        }
        target[(y * width) + x] = hit
      }
    }
  }
  sweep(mask, eroded, 0)
  sweep(eroded, opened, 1)
  return opened
}
