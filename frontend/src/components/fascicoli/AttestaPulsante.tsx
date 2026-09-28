import { Suspense, lazy, useState } from 'react'
import { createPortal } from 'react-dom'
import { BadgeCheck } from 'lucide-react'

// La finestra (lettore, riquadri, caratteri) si carica solo quando l'avvocato preme «Attesta».
const AttestazioneConformitaFinestra = lazy(() => import('./AttestazioneConformita'))

/** Pulsante «Attesta» del documento: apre l'attestazione di conformità da scrivere sul PDF e firmare. */
export function AttestazioneConformitaAzione({ action, documento, onDone, onError }: {
  action: string
  documento: string
  onDone?: (message?: string) => void
  onError?: (message: string) => void
}) {
  const [aperta, setAperta] = useState(false)
  return (
    <>
      <button className="iu-fas-post iu-fas-post--secondary" type="button" onClick={() => setAperta(true)} title="Scrivi l’attestazione di conformità sul PDF e firmalo">
        <BadgeCheck size={14}/><span>Attesta</span>
      </button>
      {/* Fuori dalla riga del documento: la finestra non eredita gli stili delle azioni e non sparisce se la riga si chiude. */}
      {aperta ? createPortal(
        <Suspense fallback={<span role="status">Apro il documento…</span>}>
          <AttestazioneConformitaFinestra action={action} documento={documento} onChiudi={() => setAperta(false)} onDone={onDone} onError={onError}/>
        </Suspense>, document.body,
      ) : null}
    </>
  )
}
