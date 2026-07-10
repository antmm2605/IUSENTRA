import { useRef, useState } from 'react'
import { Download, FileSignature, FileUp, PenLine, ShieldAlert, Type, Upload } from 'lucide-react'
import { clientPortalDocumentUrl } from '../../clientPortalData'
import {
  signConferimento,
  startSigningOtp,
  uploadSignedConferimento,
  verifySigningOtp,
  type ConferimentoState,
  type SignatureState,
  type SigningConsentsPayload,
  type SignPosition,
} from '../../clientPortalSigning'
import { SignaturePad } from './SignaturePad'

type ConferimentoSignStepProps = {
  conferimento: ConferimentoState
  signature: SignatureState
  consents: SigningConsentsPayload
  otpStepUp: boolean
  onResult: (ok: boolean, message: string, overview?: unknown) => void
}

const POSITIONS: Array<{ id: string; label: string; position: SignPosition }> = [
  { id: 'basso-destra', label: 'Ultima pagina, in basso a destra', position: { pageIndex: -1, xMm: 110, yMm: 12, widthMm: 85, heightMm: 26 } },
  { id: 'basso-sinistra', label: 'Ultima pagina, in basso a sinistra', position: { pageIndex: -1, xMm: 15, yMm: 12, widthMm: 85, heightMm: 26 } },
  { id: 'prima-basso-destra', label: 'Prima pagina, in basso a destra', position: { pageIndex: 0, xMm: 110, yMm: 12, widthMm: 85, heightMm: 26 } },
]

export function ConferimentoSignStep({ conferimento, signature, consents, otpStepUp, onResult }: ConferimentoSignStepProps) {
  const [mode, setMode] = useState<'canvas' | 'typed' | 'image'>('canvas')
  const [signatureDataUrl, setSignatureDataUrl] = useState('')
  const [typedName, setTypedName] = useState('')
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [positionId, setPositionId] = useState(POSITIONS[0].id)
  const [busy, setBusy] = useState(false)
  const [otpRequested, setOtpRequested] = useState(false)
  const [otpVerified, setOtpVerified] = useState(false)
  const [otpCode, setOtpCode] = useState('')
  const [otpMessage, setOtpMessage] = useState('')
  const [fallbackOpen, setFallbackOpen] = useState(false)
  const [signedFile, setSignedFile] = useState<File | null>(null)
  const imageInputRef = useRef<HTMLInputElement | null>(null)

  if (signature.firmaEseguita) {
    const signedId = String(signature.signedDocument?.id || '')
    const inReview = String(signature.signedDocument?.status || '') === 'in_revisione'
    return (
      <div className="iu-signing-done">
        <p className="iu-signing-badge is-firmato_definitivo">
          <FileSignature size={15} aria-hidden="true" />
          {inReview ? 'Documento firmato ricevuto: in revisione presso lo studio.' : 'Incarico firmato e trasmesso allo studio.'}
        </p>
        {signedId ? (
          <a className="iu-client-portal-button secondary" href={clientPortalDocumentUrl(signedId)}>
            <Download size={15} aria-hidden="true" />Scarica il documento firmato
          </a>
        ) : null}
        <p className="iu-client-portal-muted">
          La firma applicata è una firma elettronica semplice con evidenze conservate dallo studio: non è una firma
          elettronica qualificata.
        </p>
      </div>
    )
  }

  if (!conferimento.available) {
    return (
      <div className="iu-signing-blocked">
        <p><ShieldAlert size={16} aria-hidden="true" /> La firma del conferimento non è ancora disponibile.</p>
        <ul>
          {conferimento.requisiti.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </div>
    )
  }

  const allConsentsChecked = consents.signing.every((item) => checked[item.key])
  const signatureReady = mode === 'typed' ? typedName.trim().length > 1 : signatureDataUrl.length > 0
  const otpSatisfied = !otpStepUp || otpVerified
  const canSign = allConsentsChecked && signatureReady && otpSatisfied && !busy

  const requestOtp = async () => {
    setOtpMessage('')
    const response = await startSigningOtp()
    setOtpRequested(response.ok)
    setOtpMessage(response.message || '')
  }

  const confirmOtp = async () => {
    const response = await verifySigningOtp(otpCode)
    setOtpVerified(response.ok)
    setOtpMessage(response.message || '')
  }

  const onImageChosen = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    if (file.type !== 'image/jpeg') {
      onResult(false, 'L’immagine della firma deve essere un file JPEG.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => setSignatureDataUrl(String(reader.result || ''))
    reader.readAsDataURL(file)
  }

  const sign = async () => {
    setBusy(true)
    const position = POSITIONS.find((item) => item.id === positionId) || POSITIONS[0]
    const response = await signConferimento(conferimento.id, {
      mode,
      signatureImage: mode === 'typed' ? undefined : signatureDataUrl,
      typedName: typedName || undefined,
      consents: Object.fromEntries(consents.signing.map((item) => [item.key, Boolean(checked[item.key])])),
      position: position.position,
      pdfSha256: conferimento.pdfSha256,
    })
    setBusy(false)
    onResult(response.ok, response.message || 'Operazione non completata.', response.overview)
  }

  const uploadSigned = async () => {
    if (!signedFile) return
    setBusy(true)
    const response = await uploadSignedConferimento(
      conferimento.id,
      signedFile,
      Object.fromEntries(consents.signing.map((item) => [item.key, Boolean(checked[item.key])])),
      consents.manualUploadDeclaration,
    )
    setBusy(false)
    onResult(response.ok, response.message || 'Operazione non completata.', response.overview)
  }

  return (
    <div className="iu-signing-conferimento">
      <header className="iu-signing-card__head">
        <div>
          <strong>Conferimento incarico {conferimento.numero}</strong>
          <span>{conferimento.oggetto}</span>
        </div>
        <code title="Impronta SHA-256 del documento">{conferimento.pdfSha256.slice(0, 16)}…</code>
      </header>
      {conferimento.documentId ? (
        <a className="iu-client-portal-button secondary" href={clientPortalDocumentUrl(conferimento.documentId)}>
          <Download size={15} aria-hidden="true" />Leggi e scarica il conferimento (PDF)
        </a>
      ) : null}

      <fieldset className="iu-signing-consents">
        <legend>Dichiarazioni obbligatorie</legend>
        {consents.signing.map((item) => (
          <label className="iu-signing-consent" key={item.key}>
            <input
              type="checkbox"
              checked={Boolean(checked[item.key])}
              onChange={(event) => setChecked((current) => ({ ...current, [item.key]: event.target.checked }))}
            />
            <span>{item.text}</span>
          </label>
        ))}
      </fieldset>

      <div className="iu-signing-tabs" role="tablist" aria-label="Modalità di firma">
        <button role="tab" aria-selected={mode === 'canvas'} className={mode === 'canvas' ? 'is-active' : ''} type="button" onClick={() => { setMode('canvas'); setSignatureDataUrl('') }}>
          <PenLine size={15} aria-hidden="true" />Disegna la firma
        </button>
        <button role="tab" aria-selected={mode === 'typed'} className={mode === 'typed' ? 'is-active' : ''} type="button" onClick={() => { setMode('typed'); setSignatureDataUrl('') }}>
          <Type size={15} aria-hidden="true" />Digita nome e cognome
        </button>
        <button role="tab" aria-selected={mode === 'image'} className={mode === 'image' ? 'is-active' : ''} type="button" onClick={() => { setMode('image'); setSignatureDataUrl('') }}>
          <FileUp size={15} aria-hidden="true" />Carica immagine firma
        </button>
      </div>

      {mode === 'canvas' ? <SignaturePad onChange={setSignatureDataUrl} /> : null}
      {mode === 'typed' ? (
        <div className="iu-signing-source">
          <label htmlFor="typed-signature">Nome e cognome come firma</label>
          <input
            id="typed-signature"
            type="text"
            value={typedName}
            onChange={(event) => setTypedName(event.target.value)}
            placeholder="Es. Mario Rossi"
            autoComplete="name"
          />
        </div>
      ) : null}
      {mode === 'image' ? (
        <div className="iu-signing-source">
          <p className="iu-client-portal-muted">Immagine JPEG della tua firma su sfondo chiaro (max 300 KB).</p>
          <input ref={imageInputRef} type="file" accept="image/jpeg" onChange={(event) => onImageChosen(event.target.files)} />
          {signatureDataUrl ? <img className="iu-signing-preview__signature" src={signatureDataUrl} alt="Anteprima firma caricata" /> : null}
        </div>
      ) : null}

      <div className="iu-signing-source">
        <label htmlFor="signature-position">Posizione della firma sul documento</label>
        <select id="signature-position" value={positionId} onChange={(event) => setPositionId(event.target.value)}>
          {POSITIONS.map((item) => (
            <option value={item.id} key={item.id}>{item.label}</option>
          ))}
        </select>
      </div>

      {otpStepUp ? (
        <div className="iu-signing-otp">
          <p><strong>Verifica aggiuntiva richiesta dallo studio.</strong> Riceverai un codice via email.</p>
          {!otpVerified ? (
            <div className="iu-signing-actions">
              <button className="iu-client-portal-button secondary" type="button" onClick={() => void requestOtp()}>
                {otpRequested ? 'Invia di nuovo il codice' : 'Invia il codice via email'}
              </button>
              {otpRequested ? (
                <>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="Codice a 6 cifre"
                    value={otpCode}
                    onChange={(event) => setOtpCode(event.target.value.replace(/\D/g, ''))}
                    aria-label="Codice di verifica ricevuto via email"
                  />
                  <button className="iu-client-portal-button" type="button" disabled={otpCode.length < 4} onClick={() => void confirmOtp()}>
                    Verifica codice
                  </button>
                </>
              ) : null}
            </div>
          ) : <p className="iu-signing-badge is-approvato">Identità verificata.</p>}
          {otpMessage ? <p className="iu-client-portal-muted" role="status">{otpMessage}</p> : null}
        </div>
      ) : null}

      <div className="iu-signing-final">
        <p className="iu-client-portal-muted">
          Premendo il pulsante verrà generato un nuovo PDF con la tua firma elettronica/grafica e il documento sarà
          trasmesso allo studio. Non è una firma elettronica qualificata.
        </p>
        <button className="iu-client-portal-button iu-signing-final__button" type="button" disabled={!canSign} onClick={() => void sign()}>
          <FileSignature size={17} aria-hidden="true" />
          {busy ? 'Applicazione firma…' : 'Applica firma e invia allo Studio'}
        </button>
      </div>

      <details className="iu-signing-fallback" open={fallbackOpen} onToggle={(event) => setFallbackOpen((event.target as HTMLDetailsElement).open)}>
        <summary>Preferisci firmare a mano? Scarica, firma e ricarica il PDF</summary>
        <ol>
          <li>Scarica il conferimento con il pulsante in alto.</li>
          <li>Stampalo e firmalo, poi scansionalo o fotografalo in PDF.</li>
          <li>Spunta le dichiarazioni obbligatorie qui sopra e ricarica il file firmato.</li>
        </ol>
        <p className="iu-client-portal-muted">{consents.manualUploadDeclaration}</p>
        <input type="file" accept="application/pdf" onChange={(event) => setSignedFile(event.target.files?.[0] || null)} aria-label="PDF firmato da caricare" />
        <button
          className="iu-client-portal-button secondary"
          type="button"
          disabled={!signedFile || !allConsentsChecked || busy}
          onClick={() => void uploadSigned()}
        >
          <Upload size={15} aria-hidden="true" />Invia il documento firmato
        </button>
      </details>
    </div>
  )
}
