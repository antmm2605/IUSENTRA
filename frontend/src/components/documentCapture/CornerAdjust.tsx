import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { Check, Maximize, RefreshCcw, Undo2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { CapturePage } from './captureImages'
import { orderQuad, type Quad } from './detection/documentQuad'
import { PAGE_FILTERS, type PageFilter } from './detection/enhance'
import { detectQuadOnSource, renderCapturePage, type CaptureProfile, type CapturedImage } from './detection/pageProcessing'

type Props = {
  image: CapturedImage
  profile: CaptureProfile
  pageNumber: number
  onConfirm: (page: CapturePage) => void
  onCancel: () => void
}

const FULL: Quad = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }]
const CORNER_LABELS = ['in alto a sinistra', 'in alto a destra', 'in basso a destra', 'in basso a sinistra']
const clamp = (value: number) => Math.min(1, Math.max(0, value))

/** Verifica del ritaglio: angoli trascinabili (mouse, dito o frecce della tastiera) e resa della pagina. */
export function CornerAdjust({ image, profile, pageNumber, onConfirm, onCancel }: Props) {
  const svg = useRef<SVGSVGElement>(null)
  const [quad, setQuad] = useState<Quad>(image.quad || FULL)
  const [dragging, setDragging] = useState(-1)
  const [filter, setFilter] = useState<PageFilter>(image.source === 'scanner' ? 'colore' : 'documento')
  const [preview, setPreview] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [pixelScale, setPixelScale] = useState(1)
  const penal = profile === 'penale-200'

  // Maniglie di dimensione costante sullo schermo (bersaglio tattile di almeno 44 px).
  useLayoutEffect(() => {
    const element = svg.current
    if (!element) return undefined
    const measure = () => {
      const box = element.getBoundingClientRect()
      if (box.width && box.height) setPixelScale(Math.max(image.width / box.width, image.height / box.height))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [image])

  useEffect(() => {
    let url = ''
    let alive = true
    image.canvas.toBlob((blob) => {
      if (!blob || !alive) return
      url = URL.createObjectURL(blob)
      setPreview(url)
    }, 'image/jpeg', 0.8)
    return () => { alive = false; if (url) URL.revokeObjectURL(url) }
  }, [image])

  const toImagePoint = (event: PointerEvent<SVGSVGElement>) => {
    const matrix = svg.current?.getScreenCTM()
    if (!svg.current || !matrix) return null
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse())
    return { x: clamp(point.x / image.width), y: clamp(point.y / image.height) }
  }
  const move = (index: number, point: { x: number; y: number }) => setQuad((current) => current.map((item, position) => (position === index ? point : item)) as Quad)
  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (dragging < 0) return
    const point = toImagePoint(event)
    if (point) move(dragging, point)
  }
  const onKey = (index: number) => (event: KeyboardEvent<SVGCircleElement>) => {
    const step = event.shiftKey ? 0.02 : 0.004
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[event.key]
    if (!delta) return
    event.preventDefault()
    move(index, { x: clamp(quad[index].x + delta[0]), y: clamp(quad[index].y + delta[1]) })
  }
  const confirm = async () => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const ordered = orderQuad(quad)
      const isFull = ordered.every((point, index) => Math.abs(point.x - FULL[index].x) < 0.002 && Math.abs(point.y - FULL[index].y) < 0.002)
      onConfirm(await renderCapturePage(image, isFull ? null : ordered, filter, profile, pageNumber))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Pagina non elaborata. Riprova.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="iu-acq-adjust" aria-label={`Verifica del ritaglio della pagina ${pageNumber}`}>
      <p className="iu-acq-hint">Trascina i quattro angoli sui bordi del foglio. Con la tastiera: seleziona un angolo e usa le frecce.</p>
      <div className="iu-acq-adjust__stage">
        {preview ? <img src={preview} alt={`Immagine acquisita per la pagina ${pageNumber}`} /> : null}
        <svg
          ref={svg}
          viewBox={`0 0 ${image.width} ${image.height}`}
          preserveAspectRatio="xMidYMid meet"
          onPointerMove={onPointerMove}
          onPointerUp={() => setDragging(-1)}
          onPointerCancel={() => setDragging(-1)}
          role="group"
          aria-label="Angoli del foglio"
        >
          <polygon points={quad.map((point) => `${point.x * image.width},${point.y * image.height}`).join(' ')} />
          {quad.map((point, index) => (
            <g key={CORNER_LABELS[index]} onPointerDown={(event) => { event.currentTarget.ownerSVGElement?.setPointerCapture(event.pointerId); setDragging(index) }}>
              <circle className="iu-acq-handle-hit" cx={point.x * image.width} cy={point.y * image.height} r={24 * pixelScale} />
              <circle
                cx={point.x * image.width}
                cy={point.y * image.height}
                r={11 * pixelScale}
                tabIndex={0}
                aria-label={`Angolo ${CORNER_LABELS[index]}`}
                className={dragging === index ? 'is-dragging' : ''}
                onKeyDown={onKey(index)}
              />
            </g>
          ))}
        </svg>
      </div>
      <div className="iu-acq-adjust__tools">
        <Button type="button" tone="neutral" disabled={busy} onClick={() => setQuad(detectQuadOnSource(image.canvas, image.width, image.height) || FULL)}>
          <RefreshCcw size={16} aria-hidden="true" />Rileva di nuovo
        </Button>
        <Button type="button" tone="neutral" disabled={busy} onClick={() => setQuad(FULL)}>
          <Maximize size={16} aria-hidden="true" />Tutta l’immagine
        </Button>
        <label className="iu-acq-field">
          <span>Resa della pagina</span>
          <select value={penal ? 'bianco-nero' : filter} disabled={busy || penal} onChange={(event) => setFilter(event.target.value as PageFilter)}>
            {PAGE_FILTERS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
      </div>
      {penal ? <p className="iu-acq-hint">Profilo atto penale di parte: pagina A4 in bianco e nero a 200 dpi.</p> : null}
      {error ? <p className="iu-acq-alert" role="alert">{error}</p> : null}
      <div className="iu-acq-adjust__actions">
        <Button type="button" disabled={busy} onClick={() => void confirm()}>
          <Check size={16} aria-hidden="true" />{busy ? 'Elaborazione della pagina…' : 'Conferma pagina'}
        </Button>
        <Button type="button" tone="neutral" disabled={busy} onClick={onCancel}>
          <Undo2 size={16} aria-hidden="true" />Scarta e rifai
        </Button>
      </div>
    </section>
  )
}
