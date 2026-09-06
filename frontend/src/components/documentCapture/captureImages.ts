export type CapturePage = { id: string; file: File; url: string; rotation: number }
export const MAX_CAPTURE_FILES = 80
export const MAX_CAPTURE_BYTES = 180 * 1024 * 1024

/** Orientamento EXIF applicato, metadati di posizione esclusi dalla copia. */
export async function prepareCaptureImage(file: File): Promise<CapturePage> {
  if (!file.size || file.size > 60 * 1024 * 1024) throw new Error('La pagina è vuota o supera 60 MB.')
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) throw new Error('Usa una foto JPEG, PNG o WebP. Imposta la fotocamera su un formato compatibile.')
  let bitmap: ImageBitmap
  try { bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' }) }
  catch { throw new Error('La foto non è leggibile. Ripeti lo scatto.') }
  try {
    if (!bitmap.width || bitmap.width * bitmap.height > 50_000_000) throw new Error('La foto supera 50 megapixel. Riduci la risoluzione della fotocamera e riprova.')
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width; canvas.height = bitmap.height
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Anteprima non disponibile in questo browser.')
    context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height)
    context.drawImage(bitmap, 0, 0)
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Foto non acquisita. Ripeti lo scatto.')), 'image/jpeg', 0.96))
    const normalized = new File([blob], `${file.name.replace(/\.[^.]+$/, '')}.jpg`, { type: 'image/jpeg' })
    return { id: crypto.randomUUID(), file: normalized, url: URL.createObjectURL(blob), rotation: 0 }
  } finally { bitmap.close() }
}
