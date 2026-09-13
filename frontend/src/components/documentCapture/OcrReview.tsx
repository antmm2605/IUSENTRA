import { Rows3, Trash2, Type } from 'lucide-react'
import { Button } from '../../ui/Button'
import {
  changeBlockKind,
  removeBlock,
  updateBlockCell,
  updateBlockText,
  type OcrBlock,
  type OcrBlockKind,
  type OcrFigure,
} from './ocrBlocks'

type Props = {
  blocks: OcrBlock[]
  figures: OcrFigure[]
  disabled: boolean
  onChange: (blocks: OcrBlock[]) => void
}

const ETICHETTE: Record<OcrBlockKind, string> = {
  titolo: 'Titolo',
  paragrafo: 'Capoverso',
  elenco: 'Voce di elenco',
  tabella: 'Tabella',
}

function fiducia(valore: number): string {
  if (!valore) return ''
  return `${Math.round(valore * 100)}% di confidenza`
}

/**
 * Revisione del testo riconosciuto prima di portarlo nel documento.
 *
 * Il riconoscimento automatico sbaglia, e su un atto un errore non corretto
 * diventa un errore depositato: l'avvocato deve poter rileggere e correggere
 * ogni blocco, cambiarne la natura quando il motore l'ha classificato male e
 * togliere quello che non serve, prima che il contenuto entri nell'editor.
 */
export function OcrReview({ blocks, figures, disabled, onChange }: Props) {
  if (!blocks.length) {
    return <p className="iu-acq-hint">Nessun testo riconosciuto in questa acquisizione.</p>
  }
  return (
    <div className="iu-ocr-review">
      <p className="iu-acq-hint">
        Rileggi e correggi: quello che vedi qui è esattamente ciò che verrà inserito nel documento.
      </p>
      <ol className="iu-ocr-review__list">
        {blocks.map((block) => (
          <li key={block.id} className={`iu-ocr-block iu-ocr-block--${block.kind}`}>
            <div className="iu-ocr-block__bar">
              <label className="iu-ocr-block__kind">
                <span className="iu-sr-only">Tipo di blocco</span>
                {block.kind === 'tabella' ? <Rows3 size={14} aria-hidden="true" /> : <Type size={14} aria-hidden="true" />}
                <select
                  value={block.kind}
                  disabled={disabled || block.kind === 'tabella'}
                  onChange={(event) => onChange(changeBlockKind(blocks, block.id, event.target.value as OcrBlockKind))}
                >
                  {(['titolo', 'paragrafo', 'elenco'] as OcrBlockKind[]).map((kind) => (
                    <option key={kind} value={kind}>{ETICHETTE[kind]}</option>
                  ))}
                  {block.kind === 'tabella' ? <option value="tabella">{ETICHETTE.tabella}</option> : null}
                </select>
              </label>
              <span className="iu-ocr-block__meta">{fiducia(block.confidence)}</span>
              <Button
                type="button"
                tone="neutral"
                disabled={disabled}
                aria-label={`Togli il blocco ${ETICHETTE[block.kind].toLowerCase()}`}
                onClick={() => onChange(removeBlock(blocks, block.id))}
              >
                <Trash2 size={14} aria-hidden="true" />
              </Button>
            </div>
            {block.kind === 'tabella' ? (
              <div className="iu-ocr-block__grid">
                <table>
                  <tbody>
                    {block.rows.map((row, rowIndex) => (
                      <tr key={`${block.id}-r${rowIndex}`}>
                        {row.map((cell, columnIndex) => (
                          <td key={`${block.id}-r${rowIndex}-c${columnIndex}`}>
                            <input
                              value={cell}
                              disabled={disabled}
                              aria-label={`Riga ${rowIndex + 1}, colonna ${columnIndex + 1}`}
                              onChange={(event) => onChange(updateBlockCell(blocks, block.id, rowIndex, columnIndex, event.target.value))}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <textarea
                value={block.text}
                disabled={disabled}
                aria-label={`Testo del blocco ${ETICHETTE[block.kind].toLowerCase()}`}
                onChange={(event) => onChange(updateBlockText(blocks, block.id, event.target.value))}
              />
            )}
          </li>
        ))}
      </ol>
      {figures.length ? (
        <p className="iu-acq-alert" role="status">
          {figures.length === 1
            ? 'Nella pagina c’è una zona grafica (firma, timbro, immagine o grafico) che il riconoscimento non può trascrivere: resta nel PDF acquisito.'
            : `Nella pagina ci sono ${figures.length} zone grafiche (firme, timbri, immagini o grafici) che il riconoscimento non può trascrivere: restano nel PDF acquisito.`}
        </p>
      ) : null}
    </div>
  )
}
