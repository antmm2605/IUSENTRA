import { useEffect, useRef, useState } from 'react'
import { Camera, CameraOff, X } from 'lucide-react'

type WebcamCaptureProps = {
  onCapture: (blob: Blob) => void
  onCancel: () => void
}

/**
 * Acquisizione da webcam con consenso esplicito: la camera parte SOLO dopo il
 * click su "Attiva fotocamera", mai al caricamento. Tutti i track vengono
 * fermati all'annullamento o allo smontaggio del componente.
 */
export function WebcamCapture({ onCapture, onCancel }: WebcamCaptureProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [active, setActive] = useState(false)
  const [error, setError] = useState('')

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setActive(false)
  }

  useEffect(() => () => stopStream(), [])

  const start = async () => {
    setError('')
    if (!window.isSecureContext) {
      setError('La fotocamera richiede una connessione sicura (HTTPS).')
      return
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Il browser non supporta l’acquisizione dalla fotocamera.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setActive(true)
    } catch (err) {
      const name = err instanceof DOMException ? err.name : ''
      if (name === 'NotAllowedError') {
        setError('Permesso fotocamera negato. Puoi consentirlo dalle impostazioni del browser oppure caricare un file.')
      } else if (name === 'NotFoundError') {
        setError('Nessuna fotocamera trovata su questo dispositivo: usa il caricamento file.')
      } else {
        setError('Impossibile avviare la fotocamera: usa il caricamento file.')
      }
    }
  }

  const capture = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return
    context.drawImage(video, 0, 0)
    canvas.toBlob(
      (blob) => {
        if (blob) {
          stopStream()
          onCapture(blob)
        }
      },
      'image/jpeg',
      0.9,
    )
  }

  const cancel = () => {
    stopStream()
    onCancel()
  }

  return (
    <div className="iu-signing-webcam">
      {!active ? (
        <div className="iu-signing-webcam__intro">
          <p>
            Per fotografare il documento verrà attivata la fotocamera del dispositivo.
            L’immagine resta sul tuo dispositivo finché non premi «Invia allo studio».
          </p>
          {error ? <p className="iu-signing-error" role="alert">{error}</p> : null}
          <div className="iu-signing-actions">
            <button className="iu-client-portal-button" type="button" onClick={() => void start()}>
              <Camera size={16} aria-hidden="true" />Attiva fotocamera
            </button>
            <button className="iu-client-portal-button secondary" type="button" onClick={cancel}>
              <X size={16} aria-hidden="true" />Annulla
            </button>
          </div>
        </div>
      ) : (
        <div className="iu-signing-webcam__live">
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video ref={videoRef} className="iu-signing-webcam__video" playsInline muted />
          <div className="iu-signing-actions">
            <button className="iu-client-portal-button" type="button" onClick={capture}>
              <Camera size={16} aria-hidden="true" />Scatta
            </button>
            <button className="iu-client-portal-button secondary" type="button" onClick={cancel}>
              <CameraOff size={16} aria-hidden="true" />Spegni fotocamera
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
