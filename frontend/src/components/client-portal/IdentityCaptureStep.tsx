import { useEffect, useRef, useState } from 'react'
import { Camera, FileUp, IdCard, RefreshCcw, Send, Webcam } from 'lucide-react'
import { clientPortalPost } from '../../clientPortalData'
import { uploadIdentityDocument, type IdentityState, type SigningConsentsPayload } from '../../clientPortalSigning'
import { WebcamCapture } from './WebcamCapture'

type IdentityCaptureStepProps = {
  identity: IdentityState
  consents: SigningConsentsPayload
  onResult: (ok: boolean, message: string, overview?: unknown) => void
  onReload: () => void
}

type PendingFile = { blob: Blob; name: string; previewUrl: string; isPdf: boolean }

const STATUS_LABEL: Record<string, string> = {
  in_revisione: 'In revisione presso lo studio',
  approvato: 'Approvato dallo studio',
  respinto: 'Respinto: carica un nuovo documento',
  caricato: 'Ricevuto',
}

export function IdentityCaptureStep({ identity, consents, onResult, onReload }: IdentityCaptureStepProps) {
  const [source, setSource] = useState<'file' | 'camera' | 'webcam'>('file')
  const [pending, setPending] = useState<PendingFile | null>(null)
  const [consentBusy, setConsentBusy] = useState(false)
  const [sending, setSending] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const cameraInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => () => {
    if (pending) URL.revokeObjectURL(pending.previewUrl)
  }, [pending])

  const acceptConsent = async () => {
    setConsentBusy(true)
    const response = await clientPortalPost('/api/v1/ui/client-portal/public/consents', {
      key: consents.identity.key,
      version: consents.version,
      accepted: true,
    })
    setConsentBusy(false)
    if (response.ok) onReload()
    else onResult(false, response.message || 'Consenso non registrato.')
  }

  const setPendingFile = (blob: Blob, name: string) => {
    if (pending) URL.revokeObjectURL(pending.previewUrl)
    setPending({
      blob,
      name,
      previewUrl: URL.createObjectURL(blob),
      isPdf: blob.type === 'application/pdf' || name.toLowerCase().endsWith('.pdf'),
    })
  }

  const onFileChosen = (files: FileList | null) => {
    const file = files?.[0]
    if (file) setPendingFile(file, file.name)
  }

  const send = async () => {
    if (!pending) return
    setSending(true)
    const response = await uploadIdentityDocument(
      pending.blob instanceof File ? pending.blob : pending.blob,
      pending.name,
    )
    setSending(false)
    if (response.ok) {
      URL.revokeObjectURL(pending.previewUrl)
      setPending(null)
    }
    onResult(response.ok, response.message || 'Operazione non completata.', response.overview)
  }

  const document = identity.document
  const documentStatus = document ? String(document.status || '') : ''

  if (!identity.consentAccepted) {
    return (
      <div className="iu-signing-identity">
        <p className="iu-signing-consent-intro">
          <IdCard size={18} aria-hidden="true" /> Prima di acquisire il documento d’identità serve la tua autorizzazione esplicita.
        </p>
        <label className="iu-signing-consent">
          <input type="checkbox" checked={false} readOnly onClick={() => void acceptConsent()} disabled={consentBusy} />
          <span>{consents.identity.text}</span>
        </label>
        <button className="iu-client-portal-button" type="button" disabled={consentBusy} onClick={() => void acceptConsent()}>
          {consentBusy ? 'Registrazione…' : 'Autorizzo l’acquisizione'}
        </button>
      </div>
    )
  }

  return (
    <div className="iu-signing-identity">
      {document ? (
        <p className={`iu-signing-badge is-${documentStatus}`}>
          {STATUS_LABEL[documentStatus] || 'Ricevuto'} — {String(document.filename || 'documento')}
        </p>
      ) : null}
      {!pending ? (
        <>
          <div className="iu-signing-tabs" role="tablist" aria-label="Sorgente documento">
            <button role="tab" aria-selected={source === 'file'} className={source === 'file' ? 'is-active' : ''} type="button" onClick={() => setSource('file')}>
              <FileUp size={15} aria-hidden="true" />Carica file
            </button>
            <button role="tab" aria-selected={source === 'camera'} className={source === 'camera' ? 'is-active' : ''} type="button" onClick={() => setSource('camera')}>
              <Camera size={15} aria-hidden="true" />Fotocamera
            </button>
            <button role="tab" aria-selected={source === 'webcam'} className={source === 'webcam' ? 'is-active' : ''} type="button" onClick={() => setSource('webcam')}>
              <Webcam size={15} aria-hidden="true" />Webcam
            </button>
          </div>
          {source === 'file' ? (
            <div className="iu-signing-source">
              <p className="iu-client-portal-muted">Formati accettati: PDF, JPG, PNG (max 20 MB).</p>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,application/pdf"
                onChange={(event) => onFileChosen(event.target.files)}
              />
            </div>
          ) : null}
          {source === 'camera' ? (
            <div className="iu-signing-source">
              <p className="iu-client-portal-muted">
                Sul cellulare o tablet si aprirà direttamente la fotocamera posteriore.
              </p>
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(event) => onFileChosen(event.target.files)}
              />
            </div>
          ) : null}
          {source === 'webcam' ? (
            <WebcamCapture
              onCapture={(blob) => setPendingFile(blob, 'documento-identita.jpg')}
              onCancel={() => setSource('file')}
            />
          ) : null}
        </>
      ) : (
        <div className="iu-signing-preview">
          <p><strong>Anteprima</strong> — controlla che il documento sia leggibile prima di inviarlo.</p>
          {pending.isPdf ? (
            <iframe className="iu-signing-preview__frame" src={pending.previewUrl} title="Anteprima documento PDF" />
          ) : (
            <img className="iu-signing-preview__image" src={pending.previewUrl} alt="Anteprima del documento acquisito" />
          )}
          <div className="iu-signing-actions">
            <button className="iu-client-portal-button" type="button" disabled={sending} onClick={() => void send()}>
              <Send size={15} aria-hidden="true" />{sending ? 'Invio in corso…' : 'Invia allo studio'}
            </button>
            <button
              className="iu-client-portal-button secondary"
              type="button"
              disabled={sending}
              onClick={() => {
                URL.revokeObjectURL(pending.previewUrl)
                setPending(null)
              }}
            >
              <RefreshCcw size={15} aria-hidden="true" />Sostituisci
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
