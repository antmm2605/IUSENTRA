/**
 * Acquisizione di documenti analogici dall'editor: scanner (IUSENTRA Local Signer) o
 * webcam sul PC, fotocamera sul telefono. Il risultato è sempre un PDF; l'OCR è facoltativo.
 * Base normativa: copia informatica per immagine di documento analogico (D.Lgs. 82/2005,
 * art. 22); formati dell'atto e degli allegati (Specifiche tecniche DGSIA D.M. 44/2011,
 * artt. 15 e 16).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Dialog } from 'radix-ui'
import { ScanLine, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { acquireFromLocalScanner } from '../../services/localScanner'
import { AcquisitionPages } from './AcquisitionPages'
import { AcquisitionResult, type MatterOption } from './AcquisitionResult'
import { AcquisitionSources, type AcquisitionSource } from './AcquisitionSources'
import { CornerAdjust } from './CornerAdjust'
import { capturedImageFromFile, type CaptureProfile, type CapturedImage } from './detection/pageProcessing'
import { SmartCamera } from './SmartCamera'
import { useAcquisitionSession } from './useAcquisitionSession'
import './acquisition.css'

type Props = {
  /** Il componente resta montato da chiuso: pagine e PDF non salvati restano disponibili alla riapertura. */
  open: boolean
  matters: MatterOption[]
  defaultMatterId: string
  onClose: () => void
  /** Il genitore chiude la finestra e inserisce il testo nel punto del cursore. */
  onInsertText: (paragraphs: string[]) => void
  onSaved: (message: string) => void
}

function isTouchDevice() {
  return typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse) and (hover: none)').matches
}

export default function DocumentAcquisitionDialog({ open, matters, defaultMatterId, onClose, onInsertText, onSaved }: Props) {
  const session = useAcquisitionSession()
  const mobile = useMemo(isTouchDevice, [])
  const [camera, setCamera] = useState(false)
  const [captured, setCaptured] = useState<CapturedImage | null>(null)
  const [profile, setProfile] = useState<CaptureProfile>('allegato')
  const [name, setName] = useState('Acquisizione documento')
  const [discard, setDiscard] = useState(false)
  const [scanning, setScanning] = useState(false)
  const closeCamera = useCallback(() => setCamera(false), [])
  const hasWork = session.pages.length > 0 || Boolean(captured)

  const busy = Boolean(session.busy) || scanning

  useEffect(() => {
    if (!hasWork && !busy) return undefined
    const protect = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [hasWork, busy])

  const requestClose = () => {
    if (busy) return
    if (hasWork) { setCamera(false); setDiscard(true); return }
    setCamera(false)
    onClose()
  }
  const confirmDiscard = () => {
    session.reset()
    setCaptured(null)
    setDiscard(false)
    onClose()
  }
  const loadFile = (file: File, source: CapturedImage['source']) => {
    void (async () => {
      try { setCaptured(await capturedImageFromFile(file, source)) } catch (cause) {
        session.setError(cause instanceof Error ? cause.message : 'Immagine non acquisita.')
      }
    })()
  }
  const chooseSource = (source: AcquisitionSource) => {
    session.setError('')
    if (source === 'scanner') {
      if (scanning) return
      setScanning(true)
      void (async () => {
        try { loadFile(await acquireFromLocalScanner(), 'scanner') } catch (cause) {
          session.setError(cause instanceof Error ? cause.message : 'Acquisizione dallo scanner non completata.')
        } finally { setScanning(false) }
      })()
      return
    }
    setCamera(true)
  }
  const onCapture = useCallback((image: CapturedImage) => { setCamera(false); setCaptured(image) }, [])
  const stage = captured ? 'ritaglio' : camera ? 'fotocamera' : 'fonti'

  return (
    <Dialog.Root open={open} onOpenChange={(next) => { if (!next) requestClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="iu-acq-overlay" />
        <Dialog.Content className="iu-acq-dialog" onEscapeKeyDown={(event) => { event.preventDefault(); requestClose() }} onPointerDownOutside={(event) => event.preventDefault()}>
          <header className="iu-acq-dialog__header">
            <ScanLine size={20} aria-hidden="true" />
            <div>
              <Dialog.Title>Acquisisci documento in PDF</Dialog.Title>
              <Dialog.Description>
                {mobile ? 'Fotocamera del dispositivo' : 'Scanner o webcam del PC'} · {session.pages.length} {session.pages.length === 1 ? 'pagina' : 'pagine'}
              </Dialog.Description>
            </div>
            <Button type="button" tone="neutral" className="iu-acq-dialog__close" aria-label="Chiudi acquisizione" disabled={busy} onClick={requestClose}><X size={18} aria-hidden="true" /></Button>
          </header>
          {discard ? (
            <div className="iu-acq-confirm" role="alertdialog" aria-label="Pagine non salvate">
              <p>Le pagine acquisite non sono state salvate. Vuoi scartarle?</p>
              <Button type="button" tone="danger" onClick={confirmDiscard}>Scarta e chiudi</Button>
              <Button type="button" tone="neutral" onClick={() => setDiscard(false)}>Continua</Button>
            </div>
          ) : null}
          <div className="iu-acq-dialog__body">
            <div className="iu-acq-dialog__capture" data-stage={stage}>
              {stage === 'fonti' ? (
                <AcquisitionSources mobile={mobile} disabled={busy} profile={profile} onProfile={setProfile} onSource={chooseSource} onPhoto={(file) => loadFile(file, 'foto')} />
              ) : null}
              {stage === 'fotocamera' ? (
                <SmartCamera facingMode={mobile ? 'environment' : 'user'} label={mobile ? 'Fotocamera del dispositivo' : 'Webcam del PC'} onCapture={onCapture} onClose={closeCamera} />
              ) : null}
              {captured ? (
                <CornerAdjust
                  key={`${captured.width}x${captured.height}-${session.pages.length}`}
                  image={captured}
                  profile={profile}
                  pageNumber={session.pages.length + 1}
                  onConfirm={(page) => { session.addPage(page); setCaptured(null); if (captured.source === 'fotocamera') setCamera(true) }}
                  onCancel={() => { const again = captured.source === 'fotocamera'; setCaptured(null); setCamera(again) }}
                />
              ) : null}
              {busy ? <p className="iu-acq-status" role="status" aria-live="polite">{scanning ? 'Acquisizione dallo scanner: completa la finestra dello scanner sul PC…' : session.busy}</p> : null}
              {session.error ? <p className="iu-acq-alert" role="alert">{session.error}</p> : null}
              {session.notice && !busy ? <p className="iu-acq-status" role="status">{session.notice}</p> : null}
            </div>
            <aside className="iu-acq-dialog__side">
              <AcquisitionPages pages={session.pages} name={name} busy={busy} onName={setName} onRotate={session.rotate} onMove={session.move} onRemove={session.remove} onBuild={() => void session.buildPdf(name)} />
              {session.result ? (
                <AcquisitionResult
                  key={session.result.objectUrl}
                  result={session.result}
                  ocr={session.ocr}
                  busy={busy}
                  matters={matters}
                  defaultMatterId={defaultMatterId}
                  onOcr={() => void session.runOcr(name)}
                  onInsertText={onInsertText}
                  onSave={(matterId) => void session.save(matterId, onSaved)}
                />
              ) : null}
            </aside>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
