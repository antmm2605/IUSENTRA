import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'

export type CameraDevice = { deviceId: string; label: string }

type TorchCapabilities = MediaTrackCapabilities & { torch?: boolean }
type TorchConstraint = MediaTrackConstraintSet & { torch?: boolean }

function cameraError(cause: unknown): string {
  const name = cause instanceof DOMException ? cause.name : ''
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'Accesso alla fotocamera non autorizzato. Consenti la fotocamera nelle autorizzazioni del sito e nelle impostazioni privacy del dispositivo, poi riprova.'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'Nessuna fotocamera rilevata. Collega una webcam al PC oppure apri IUSENTRA dal telefono.'
  if (name === 'NotReadableError') return 'La fotocamera è già usata da un’altra applicazione. Chiudila e riprova.'
  return 'Fotocamera non disponibile. Riprova tra qualche secondo.'
}

/**
 * Flusso video della fotocamera senza audio né registrazione. Le tracce vengono
 * fermate alla chiusura, al cambio di dispositivo e quando la scheda va in secondo piano.
 */
export function useCameraStream(videoRef: RefObject<HTMLVideoElement | null>, facingMode: 'environment' | 'user', onHidden: () => void) {
  const stream = useRef<MediaStream | null>(null)
  const [deviceId, setDeviceId] = useState('')
  const [devices, setDevices] = useState<CameraDevice[]>([])
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [torchAvailable, setTorchAvailable] = useState(false)
  const [torchOn, setTorchOn] = useState(false)

  const stop = useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    setReady(false)
  }, [])

  useEffect(() => {
    let current = true
    const hidden = () => { if (document.hidden) onHidden() }
    document.addEventListener('visibilitychange', hidden)
    setError('')
    setReady(false)
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setError('La fotocamera richiede un collegamento sicuro (HTTPS). Apri IUSENTRA dall’indirizzo ufficiale dello studio.')
    } else {
      const video: MediaTrackConstraints = deviceId
        ? { deviceId: { exact: deviceId }, width: { ideal: 3840 }, height: { ideal: 2160 } }
        : { facingMode: { ideal: facingMode }, width: { ideal: 3840 }, height: { ideal: 2160 } }
      void navigator.mediaDevices.getUserMedia({ audio: false, video })
        .then(async (media) => {
          if (!current) { media.getTracks().forEach((track) => track.stop()); return }
          stream.current = media
          const [track] = media.getVideoTracks()
          track?.addEventListener('ended', () => { if (current) { setReady(false); setError('La fotocamera è stata scollegata. Ricollegala e riprova.') } })
          const capabilities = (track?.getCapabilities?.() || {}) as TorchCapabilities
          setTorchAvailable(Boolean(capabilities.torch))
          setTorchOn(false)
          if (videoRef.current) {
            videoRef.current.srcObject = media
            await videoRef.current.play().catch(() => undefined)
          }
          const list = await navigator.mediaDevices.enumerateDevices().catch(() => [])
          if (current) {
            setDevices(list.filter((item) => item.kind === 'videoinput').map((item, index) => ({ deviceId: item.deviceId, label: item.label || `Fotocamera ${index + 1}` })))
          }
        })
        .catch((cause: unknown) => { if (current) setError(cameraError(cause)) })
    }
    return () => {
      current = false
      document.removeEventListener('visibilitychange', hidden)
      stream.current?.getTracks().forEach((track) => track.stop())
      stream.current = null
    }
  }, [deviceId, facingMode, onHidden, videoRef])

  const toggleTorch = useCallback(async () => {
    const [track] = stream.current?.getVideoTracks() || []
    if (!track) return
    const next = !torchOn
    try {
      await track.applyConstraints({ advanced: [{ torch: next } as TorchConstraint] })
      setTorchOn(next)
    } catch {
      setTorchAvailable(false)
    }
  }, [torchOn])

  return { devices, deviceId, setDeviceId, ready, setReady, error, stop, torchAvailable, torchOn, toggleTorch }
}
