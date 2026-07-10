import { useEffect, useRef, useState } from 'react'
import { Eraser } from 'lucide-react'

type SignaturePadProps = {
  onChange: (dataUrl: string) => void
}

const PAD_WIDTH = 600
const PAD_HEIGHT = 200
const MAX_EXPORT_BYTES = 300 * 1024

/**
 * Canvas di firma con Pointer Events (mouse, touch, penna). Esporta un JPEG su
 * sfondo bianco (unico formato applicabile al PDF lato server senza Pillow).
 */
export function SignaturePad({ onChange }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const drawingRef = useRef(false)
  const [hasStrokes, setHasStrokes] = useState(false)

  const withContext = (fn: (context: CanvasRenderingContext2D, canvas: HTMLCanvasElement) => void) => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d')
    if (canvas && context) fn(context, canvas)
  }

  const clear = (notify = true) => {
    withContext((context, canvas) => {
      context.fillStyle = '#ffffff'
      context.fillRect(0, 0, canvas.width, canvas.height)
    })
    setHasStrokes(false)
    if (notify) onChange('')
  }

  useEffect(() => {
    clear(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const pointerPosition = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    return {
      x: ((event.clientX - rect.left) / rect.width) * canvas.width,
      y: ((event.clientY - rect.top) / rect.height) * canvas.height,
    }
  }

  const exportSignature = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    let quality = 0.85
    let dataUrl = canvas.toDataURL('image/jpeg', quality)
    while (dataUrl.length * 0.75 > MAX_EXPORT_BYTES && quality > 0.3) {
      quality -= 0.15
      dataUrl = canvas.toDataURL('image/jpeg', quality)
    }
    onChange(dataUrl)
  }

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    event.preventDefault()
    drawingRef.current = true
    canvasRef.current?.setPointerCapture(event.pointerId)
    const { x, y } = pointerPosition(event)
    withContext((context) => {
      context.strokeStyle = '#1c2b4a'
      context.lineWidth = 2.4
      context.lineCap = 'round'
      context.lineJoin = 'round'
      context.beginPath()
      context.moveTo(x, y)
    })
  }

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return
    event.preventDefault()
    const { x, y } = pointerPosition(event)
    withContext((context) => {
      context.lineTo(x, y)
      context.stroke()
    })
    if (!hasStrokes) setHasStrokes(true)
  }

  const onPointerUp = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return
    drawingRef.current = false
    canvasRef.current?.releasePointerCapture(event.pointerId)
    exportSignature()
  }

  return (
    <div className="iu-signing-pad">
      <canvas
        ref={canvasRef}
        className="iu-signing-pad__canvas"
        width={PAD_WIDTH}
        height={PAD_HEIGHT}
        role="img"
        aria-label="Area di firma: disegna qui la tua firma"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      />
      <div className="iu-signing-pad__footer">
        <span className="iu-client-portal-muted">
          {hasStrokes ? 'Firma acquisita: puoi rifarla con «Cancella».' : 'Disegna la firma con il dito, la penna o il mouse.'}
        </span>
        <button className="iu-client-portal-button secondary" type="button" onClick={() => clear()}>
          <Eraser size={15} aria-hidden="true" />Cancella
        </button>
      </div>
    </div>
  )
}
