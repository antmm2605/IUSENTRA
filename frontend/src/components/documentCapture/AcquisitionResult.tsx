import { useState } from 'react'
import { Check, FileText, ScanText, TextCursorInput } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { GeneratedDocument } from '../../documentToolsData'
import { blocksToHtml, type OcrBlock } from './ocrBlocks'
import { OcrReview } from './OcrReview'
import { MatterPicker, type MatterOption } from './MatterPicker'
import type { OcrState } from './useAcquisitionSession'

export type { MatterOption }

type Props = {
  result: GeneratedDocument
  ocr: OcrState | null
  busy: boolean
  matters: MatterOption[]
  defaultMatterId: string
  onOcr: () => void
  onEditBlocks: (blocks: OcrBlock[]) => void
  onInsertHtml: (html: string) => void
  onSave: (matterId: string) => void
}

/** Verifica del PDF, OCR facoltativo, inserimento del testo e salvataggio confermato nel fascicolo. */
export function AcquisitionResult({ result, ocr, busy, matters, defaultMatterId, onOcr, onEditBlocks, onInsertHtml, onSave }: Props) {
  const [matterId, setMatterId] = useState(defaultMatterId)
  const [reviewed, setReviewed] = useState(false)
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
              {ocr.characters ? `${ocr.characters.toLocaleString('it-IT')} caratteri riconosciuti` : 'Nessun testo riconosciuto'}
              {ocr.blocks.length ? ` in ${ocr.blocks.length} ${ocr.blocks.length === 1 ? 'blocco' : 'blocchi'}` : ''}
              {ocr.confidence ? ` · qualità media ${Math.round(ocr.confidence * 100)}%` : ''}
              {ocr.emptyPages ? ` · pagine senza testo: ${ocr.emptyPages}` : ''}
              {ocr.engine ? ` · ${ocr.engine}` : ''}.
            </p>
            <OcrReview blocks={ocr.blocks} figures={ocr.figures} disabled={busy} onChange={onEditBlocks} />
            <Button type="button" tone="neutral" disabled={busy || !ocr.blocks.length} onClick={() => onInsertHtml(blocksToHtml(ocr.blocks))}>
              <TextCursorInput size={16} aria-hidden="true" />Inserisci il testo rivisto nel documento
            </Button>
          </>
        )}
      </div>
      <div className="iu-acq-result__save">
        <MatterPicker
          matters={matters}
          value={matterId}
          disabled={busy}
          onChange={(scelto) => { setMatterId(scelto); setReviewed(false) }}
        />
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
