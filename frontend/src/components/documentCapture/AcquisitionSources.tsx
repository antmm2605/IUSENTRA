import { useRef } from 'react'
import { Camera, ImagePlus, Printer, Video } from 'lucide-react'
import type { CaptureProfile } from './detection/pageProcessing'

export type AcquisitionSource = 'scanner' | 'webcam' | 'fotocamera' | 'foto'

type Props = {
  mobile: boolean
  disabled: boolean
  profile: CaptureProfile
  onProfile: (profile: CaptureProfile) => void
  onSource: (source: AcquisitionSource) => void
  onPhoto: (file: File) => void
}

type SourceCard = { source: AcquisitionSource; title: string; detail: string; icon: typeof Camera }

const DESKTOP: SourceCard[] = [
  { source: 'scanner', title: 'Scanner del PC', detail: 'Tramite IUSENTRA Local Signer e il driver dello scanner.', icon: Printer },
  { source: 'webcam', title: 'Webcam del PC', detail: 'Riquadro del foglio rilevato dal vivo e raddrizzamento automatico.', icon: Video },
]
const MOBILE: SourceCard[] = [
  { source: 'fotocamera', title: 'Fotocamera del dispositivo', detail: 'Riquadro del foglio rilevato dal vivo, luce e scatto automatico.', icon: Camera },
  { source: 'foto', title: 'App fotocamera', detail: 'Scatta con l’app del telefono: il foglio viene ritagliato dopo lo scatto.', icon: ImagePlus },
]

/** Scelta della sorgente in base al dispositivo e del profilo della copia per immagine. */
export function AcquisitionSources({ mobile, disabled, profile, onProfile, onSource, onPhoto }: Props) {
  const photo = useRef<HTMLInputElement>(null)
  const cards = mobile ? MOBILE : DESKTOP
  return (
    <section className="iu-acq-sources" aria-label="Sorgente di acquisizione">
      <div className="iu-acq-sources__grid">
        {cards.map((card) => {
          const Icon = card.icon
          return (
            <button
              type="button"
              key={card.source}
              className="iu-acq-source"
              disabled={disabled}
              onClick={() => (card.source === 'foto' ? photo.current?.click() : onSource(card.source))}
            >
              <Icon size={22} aria-hidden="true" />
              <strong>{card.title}</strong>
              <span>{card.detail}</span>
            </button>
          )
        })}
      </div>
      <input
        ref={photo}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onPhoto(file)
        }}
      />
      <fieldset className="iu-acq-profile">
        <legend>Uso della copia</legend>
        <label>
          <input type="radio" name="iu-acq-profile" checked={profile === 'allegato'} disabled={disabled} onChange={() => onProfile('allegato')} />
          <span><strong>Allegato o procura</strong> Pagina A4 nitida, a colori o in scala di grigi.</span>
        </label>
        <label>
          <input type="radio" name="iu-acq-profile" checked={profile === 'penale-200'} disabled={disabled} onChange={() => onProfile('penale-200')} />
          <span><strong>Atto penale di parte</strong> Bianco e nero a 200 dpi, come previsto per il deposito della scansione.</span>
        </label>
      </fieldset>
      <p className="iu-acq-hint">
        Nel civile l’atto principale non può essere una scansione: usa l’acquisizione per allegati e procure
        (Specifiche tecniche del Ministero della Giustizia, artt. 15 e 16).
      </p>
    </section>
  )
}
