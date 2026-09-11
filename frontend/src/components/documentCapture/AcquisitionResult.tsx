import { useState } from 'react'
import { Check, FileText, ScanText, TextCursorInput } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { GeneratedDocument } from '../../documentToolsData'
import type { OcrState } from './useAcquisitionSession'

export type MatterOption = { value: string; label: string }

type Props = {
  result: GeneratedDocument
  ocr: OcrState | null
  busy: boolean
  matters: MatterOption[]
  defaultMatterId: string
  onOcr: () => void
  onInsertText: (paragraphs: string[]) => void
  onSave: (matterId: string) => void
}

/** Verifica del PDF, OCR facoltativo, inserimento del testo e salvataggio confermato nel fascicolo. */
export function AcquisitionResult({ result, ocr, busy, matters, defaultMatterId, onOcr, onInsertText, onSave }: Props) {
  const [matterId, setMatterId] = useState(defaultMatterId)
  const [reviewed, setReviewed] = useState(false)
  const preview = ocr?.paragraphs.join('\n\n') || ''
  return (
    <section className="iu-acq-result" aria-label="Verifica del PDF acquisito">
      <header>
        <FileText size={18} aria-hidden="true" />
        <div>
          <strong>{result.filename}</strong>
          <span>{result.pages} {result.pages === 1 ? 'pagina' : 'pagine'}{ocr ? ' · testo ricercabile' : ' · immagine'}</span>
        </div>
      </header>
      <iframe src={result.objectUrl} title="Anteprima del PDF acquisito" />
      <div className="iu-acq-result__ocr">
        {!ocr ? (
          <>
            <p className="iu-acq-hint">Facoltativo: riconosci il testo per rendere il PDF ricercabile e copiare il contenuto nel documento.</p>
            <Button type="button" tone="neutral" disabled={busy} onClick={onOcr}>
              <ScanText size={16} aria-hidden="true" />Riconosci testo (OCR)
            </Button>
          </>
        ) : (
          <>
            <p className="iu-acq-hint">
              {ocr.characters ? `${ocr.characters.toLocaleString('it-IT')} caratteri riconosciuti.` : 'Nessun testo riconosciuto.'}
              {ocr.emptyPages ? ` Pagine senza testo: ${ocr.emptyPages}.` : ''} Il riconoscimento automatico può contenere errori: rileggi prima di usarlo.
            </p>
            {preview ? <textarea className="iu-acq-result__text" readOnly value={preview} aria-label="Testo riconosciuto" /> : null}
            <Button type="button" tone="neutral" disabled={busy || !ocr.paragraphs.length} onClick={() => onInsertText(ocr.paragraphs)}>
              <TextCursorInput size={16} aria-hidden="true" />Inserisci il testo nel documento
            </Button>
          </>
        )}
      </div>
      <div className="iu-acq-result__save">
        <label className="iu-acq-field iu-acq-field--wide">
          <span>Fascicolo di destinazione</span>
          <select value={matterId} disabled={busy} onChange={(event) => { setMatterId(event.target.value); setReviewed(false) }}>
            <option value="">Seleziona il fascicolo</option>
            {matters.map((matter) => <option key={matter.value} value={matter.value}>{matter.label}</option>)}
          </select>
        </label>
        <label className="iu-acq-check">
          <input type="checkbox" checked={reviewed} disabled={busy || !matterId} onChange={(event) => setReviewed(event.target.checked)} />
          Ho controllato tutte le pagine e confermo il salvataggio in questo fascicolo.
        </label>
        <Button type="button" disabled={busy || !matterId || !reviewed} onClick={() => onSave(matterId)}>
          <Check size={16} aria-hidden="true" />Salva PDF nel fascicolo
        </Button>
        <p className="iu-acq-hint">Il PDF non viene firmato né inviato. Le immagini non conservano dati di posizione.</p>
      </div>
    </section>
  )
}
