import { Download, FileText, FolderOpen, Laptop, PenLine } from 'lucide-react'
import { Button } from '../../ui/Button'

export type DestinazioneOcr =
  | 'editor'
  | 'fascicolo-documento'
  | 'fascicolo-pdf'
  | 'computer-documento'
  | 'computer-pdf'
  | 'computer-testo'

type Props = {
  disabled: boolean
  copiaRicercabileDisponibile: boolean
  onScegli: (destinazione: DestinazioneOcr) => void
}

/**
 * Dove finisce il testo riconosciuto: lo decide l'avvocato, non il programma.
 *
 * Le due domande sono separate e dichiarate: «in quale forma» (documento
 * modificabile, copia della pagina con il testo sotto, testo semplice) e «dove»
 * (nel fascicolo del cliente oppure sul proprio computer). Ogni voce dice cosa
 * produce, perché salvare nel fascicolo di un cliente non è un gesto neutro e
 * non deve capitare per sbaglio.
 */
export function OcrSaveChoices({ disabled, copiaRicercabileDisponibile, onScegli }: Props) {
  return (
    <section className="iu-ocr-destinazioni" aria-label="Dove salvare il testo riconosciuto">
      <h4>Dove vuoi salvare</h4>

      <div className="iu-ocr-destinazioni__gruppo">
        <h5><FolderOpen size={15} aria-hidden="true" />Nel fascicolo</h5>
        <div className="iu-ocr-destinazioni__voci">
          <Button type="button" disabled={disabled} onClick={() => onScegli('editor')}>
            <PenLine size={15} aria-hidden="true" />Apri subito nell’editor
          </Button>
          <Button type="button" tone="neutral" disabled={disabled} onClick={() => onScegli('fascicolo-documento')}>
            <FileText size={15} aria-hidden="true" />Salva il documento modificabile
          </Button>
          {copiaRicercabileDisponibile ? (
            <Button type="button" tone="neutral" disabled={disabled} onClick={() => onScegli('fascicolo-pdf')}>
              <FileText size={15} aria-hidden="true" />Salva la copia PDF con testo ricercabile
            </Button>
          ) : null}
        </div>
        <p className="iu-acq-hint">
          Il documento entra fra i documenti del fascicolo come atto nuovo: l’originale resta dov’è e non viene modificato.
        </p>
      </div>

      <div className="iu-ocr-destinazioni__gruppo">
        <h5><Laptop size={15} aria-hidden="true" />Sul computer</h5>
        <div className="iu-ocr-destinazioni__voci">
          <Button type="button" tone="neutral" disabled={disabled} onClick={() => onScegli('computer-documento')}>
            <Download size={15} aria-hidden="true" />Scarica il documento Word
          </Button>
          {copiaRicercabileDisponibile ? (
            <Button type="button" tone="neutral" disabled={disabled} onClick={() => onScegli('computer-pdf')}>
              <Download size={15} aria-hidden="true" />Scarica il PDF con testo ricercabile
            </Button>
          ) : null}
          <Button type="button" tone="neutral" disabled={disabled} onClick={() => onScegli('computer-testo')}>
            <Download size={15} aria-hidden="true" />Scarica il testo semplice
          </Button>
        </div>
        <p className="iu-acq-hint">
          Il file viene scaricato sul tuo dispositivo e non lascia traccia nel fascicolo.
        </p>
      </div>

      <p className="iu-acq-hint">
        Il documento Word riporta il testo con la formattazione che hai davanti, correzioni comprese. La copia PDF conserva la
        pagina com’è e vi aggiunge sotto il testo letto dalla macchina, quindi senza le tue correzioni.
      </p>
    </section>
  )
}
