import { createContext, useRef, useState } from 'react'
import type { PointerEvent } from 'react'
type Receiver = (color: string) => void
export const ViewerColorSampling = createContext<{ active: boolean; start: (receiver: Receiver) => void } | null>(null)
export function rgbaToHex(r: number, g: number, b: number, alpha = 255) {
  const opacity = alpha / 255
  return '#' + [r, g, b].map(channel => Math.round(channel * opacity + 255 * (1 - opacity)).toString(16).padStart(2, '0')).join('')
}
export function useViewerColorSampler(onStatus: (text: string) => void, onError: (text: string) => void) {
  const [active, setActive] = useState(false)
  const receiver = useRef<Receiver | null>(null)
  const cancel = () => { receiver.current = null; setActive(false) }
  const start = (callback: Receiver) => { receiver.current = callback; setActive(true); onError(''); onStatus('') }
  const capture = (event: PointerEvent<HTMLDivElement>) => {
    if (!active || event.button !== 0) return
    event.preventDefault(); event.stopPropagation()
    try {
      const image = event.currentTarget.querySelector('img')
      if (!image?.complete || !image.naturalWidth) throw new Error('Attendi il caricamento della pagina prima di prelevare il colore.')
      const rect = image.getBoundingClientRect()
      const x = Math.max(0, Math.min(image.naturalWidth - 1, Math.floor((event.clientX - rect.left) / rect.width * image.naturalWidth)))
      const y = Math.max(0, Math.min(image.naturalHeight - 1, Math.floor((event.clientY - rect.top) / rect.height * image.naturalHeight)))
      const canvas = document.createElement('canvas'); canvas.width = 1; canvas.height = 1
      const context = canvas.getContext('2d', { willReadFrequently: true })
      if (!context) throw new Error('Il colore non può essere letto in questo browser.')
      context.drawImage(image, x, y, 1, 1, 0, 0, 1, 1)
      const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data
      const color = rgbaToHex(r, g, b, a)
      receiver.current?.(color); cancel()
      onStatus(`Colore rilevato sulla pagina: ${color.toUpperCase()} · RGB ${[1,3,5].map(offset=>parseInt(color.slice(offset,offset+2),16)).join(', ')}.`)
    } catch (error) { onError(error instanceof Error ? error.message : 'Colore non disponibile. Nessun oggetto è stato inserito.') }
  }
  return { active, start, cancel, capture }
}
