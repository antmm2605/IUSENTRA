import { useEffect, useRef, useState } from 'react'
import { Camera, CameraOff } from 'lucide-react'
import { Button } from '../../ui/Button'

export function CaptureCamera({ onCapture, onClose }: { onCapture: (file: File) => Promise<void>; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const [error, setError] = useState('')
  const [ready, setReady] = useState(false)
  const [taking, setTaking] = useState(false)
  useEffect(() => {
    let current = true
    const stop = () => { stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null }
    const hidden = () => { if (document.hidden) onClose() }
    const details = video.current?.closest('#documenti')
    const collapsed = () => { if (details instanceof HTMLDetailsElement && !details.open) onClose() }
    document.addEventListener('visibilitychange', hidden)
    details?.addEventListener('toggle', collapsed)
    if (!navigator.mediaDevices?.getUserMedia) setError('La fotocamera richiede una connessione HTTPS o la copia locale sul PC. Apri IUSENTRA da un indirizzo sicuro.')
    else void navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: 'environment' }, width: { ideal: 2560 }, height: { ideal: 1920 } } })
      .then(async (media) => {
        if (!current) { media.getTracks().forEach((track) => track.stop()); return }
        stream.current = media
        media.getVideoTracks().forEach((track) => track.addEventListener('ended', () => { if (current) { setReady(false); setError('La fotocamera è stata scollegata. Chiudi e riaprila per riprovare.') } }))
        if (video.current) { video.current.srcObject = media; await video.current.play() }
      }).catch((cause: unknown) => {
        stop()
        if (!current) return
        const name = cause instanceof DOMException ? cause.name : ''
        setError(name === 'NotAllowedError' ? 'Accesso alla fotocamera non autorizzato. Consenti la fotocamera nelle autorizzazioni del sito e nelle impostazioni privacy del dispositivo, poi riaprila.' : name === 'NotFoundError' ? 'Nessuna fotocamera rilevata. Collega la webcam oppure apri questo fascicolo dal telefono.' : 'Fotocamera non disponibile. Chiudi le altre applicazioni che la usano e riprova.')
      })
    return () => { current = false; stop(); document.removeEventListener('visibilitychange', hidden); details?.removeEventListener('toggle', collapsed) }
  }, [onClose])
  const snap = async () => {
    if (!video.current || !ready || taking) return
    setTaking(true)
    try {
      const canvas = document.createElement('canvas')
      canvas.width = video.current.videoWidth; canvas.height = video.current.videoHeight
      const context = canvas.getContext('2d')
      if (!context || !canvas.width || !canvas.height) throw new Error('Attendi che l’inquadratura sia visibile.')
      context.drawImage(video.current, 0, 0)
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Scatto non riuscito. Riprova.')), 'image/jpeg', 0.96))
      await onCapture(new File([blob], 'pagina-fotocamera.jpg', { type: 'image/jpeg' }))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Scatto non riuscito.') }
    finally { setTaking(false) }
  }
  return <section className="iu-capture-camera" aria-label="Inquadratura della fotocamera">
    <p>Inquadra il foglio per intero, con testo nitido e luce uniforme. Non viene registrato audio o video.</p>
    {error ? <p role="alert">{error}</p> : !ready ? <p role="status">Consenti la fotocamera nel browser e attendi l’inquadratura.</p> : null}
    <video ref={video} autoPlay playsInline muted onLoadedData={() => setReady(true)} aria-label="Anteprima dal vivo della fotocamera" />
    <div className="iu-capture-actions">
      <Button type="button" onClick={snap} disabled={!ready || taking || Boolean(error)}><Camera size={16}/>{taking ? 'Acquisizione…' : 'Scatta pagina'}</Button>
      <Button type="button" tone="neutral" onClick={onClose}><CameraOff size={16}/>Spegni fotocamera</Button>
    </div>
  </section>
}
