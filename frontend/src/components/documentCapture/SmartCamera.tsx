import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, CameraOff, Flashlight, FlashlightOff, ScanLine } from 'lucide-react'
import { Button } from '../../ui/Button'
import { canvasFromSource, type CapturedImage } from './detection/pageProcessing'
import { useCameraStream } from './useCameraStream'
import { useDocumentDetection } from './useDocumentDetection'

type Props = {
  facingMode: 'environment' | 'user'
  label: string
  onCapture: (image: CapturedImage) => void
  onClose: () => void
}

function statusText(ready: boolean, found: boolean, stable: boolean) {
  if (!ready) return 'Consenti la fotocamera e attendi l’inquadratura.'
  if (stable) return 'Foglio rilevato e fermo: puoi scattare.'
  if (found) return 'Foglio rilevato: tieni fermo il dispositivo.'
  return 'Inquadra tutto il foglio su uno sfondo che contrasti.'
}

/** Fotocamera con riquadro del foglio rilevato in tempo reale e scatto automatico opzionale. */
export function SmartCamera({ facingMode, label, onCapture, onClose }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const [autoCapture, setAutoCapture] = useState(false)
  const [flash, setFlash] = useState(false)
  const [captureError, setCaptureError] = useState('')
  const hidden = useCallback(() => onClose(), [onClose])
  const camera = useCameraStream(video, facingMode, hidden)
  const detection = useDocumentDetection(video, camera.ready)
  const lastAuto = useRef(0)
  const width = video.current?.videoWidth || 1600
  const height = video.current?.videoHeight || 1200

  const snap = useCallback(() => {
    const element = video.current
    if (!element || !camera.ready) return
    try {
      const canvas = canvasFromSource(element, element.videoWidth, element.videoHeight)
      setFlash(true)
      window.setTimeout(() => setFlash(false), 180)
      onCapture({ canvas, width: canvas.width, height: canvas.height, quad: detection.quad, source: 'fotocamera' })
    } catch (cause) {
      setCaptureError(cause instanceof Error ? cause.message : 'Scatto non riuscito. Riprova.')
    }
  }, [camera.ready, detection.quad, onCapture])

  useEffect(() => {
    if (!autoCapture || !detection.stable) return
    const now = Date.now()
    if (now - lastAuto.current < 2500) return
    lastAuto.current = now
    snap()
  }, [autoCapture, detection.stable, snap])

  const points = detection.quad?.map((point) => `${Math.round(point.x * width)},${Math.round(point.y * height)}`).join(' ') || ''
  const error = camera.error || captureError
  return (
    <section className="iu-smartcam" aria-label={label}>
      <div className={`iu-smartcam__stage${flash ? ' is-flash' : ''}`}>
        <video ref={video} autoPlay playsInline muted onLoadedData={() => camera.setReady(true)} aria-label="Anteprima dal vivo della fotocamera" />
        <svg className="iu-smartcam__overlay" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          {points ? (
            <polygon className={detection.stable ? 'is-stable' : 'is-found'} points={points} />
          ) : (
            <rect className="iu-smartcam__guide" x={width * 0.2} y={height * 0.08} width={width * 0.6} height={height * 0.84} rx={12} />
          )}
        </svg>
        <p className={`iu-smartcam__status${detection.stable ? ' is-stable' : ''}`} role="status" aria-live="polite">
          {error ? '' : statusText(camera.ready, Boolean(detection.quad), detection.stable)}
        </p>
      </div>
      {error ? <p className="iu-acq-alert" role="alert">{error}</p> : null}
      <div className="iu-smartcam__controls">
        <Button type="button" className="iu-smartcam__shutter" onClick={snap} disabled={!camera.ready || Boolean(camera.error)}>
          <Camera size={18} aria-hidden="true" />Scatta pagina
        </Button>
        <label className="iu-acq-switch">
          <input type="checkbox" checked={autoCapture} onChange={(event) => setAutoCapture(event.target.checked)} />
          <ScanLine size={15} aria-hidden="true" />Scatto automatico quando il foglio è fermo
        </label>
        {camera.devices.length > 1 ? (
          <label className="iu-acq-field">
            <span>Fotocamera</span>
            <select value={camera.deviceId} onChange={(event) => camera.setDeviceId(event.target.value)}>
              <option value="">Predefinita</option>
              {camera.devices.map((device) => <option key={device.deviceId} value={device.deviceId}>{device.label}</option>)}
            </select>
          </label>
        ) : null}
        {camera.torchAvailable ? (
          <Button type="button" tone="neutral" aria-pressed={camera.torchOn} onClick={() => void camera.toggleTorch()}>
            {camera.torchOn ? <FlashlightOff size={16} aria-hidden="true" /> : <Flashlight size={16} aria-hidden="true" />}
            {camera.torchOn ? 'Spegni luce' : 'Accendi luce'}
          </Button>
        ) : null}
        <Button type="button" tone="neutral" onClick={() => { camera.stop(); onClose() }}>
          <CameraOff size={16} aria-hidden="true" />Chiudi fotocamera
        </Button>
      </div>
    </section>
  )
}
