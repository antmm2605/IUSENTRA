import { AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, Hash, Italic, Rows3, Trash2, Type } from 'lucide-react'
import { Button } from '../../ui/Button'
import {
  changeBlockKind,
  markerOf,
  removeBlock,
  updateBlockCell,
  updateBlockFormat,
  updateBlockText,
  type OcrAlignment,
  type OcrBlock,
  type OcrBlockKind,
  type OcrFigure,
} from './ocrBlocks'

type Props = {
  blocks: OcrBlock[]
  figures: OcrFigure[]
  disabled: boolean
  onChange: (blocks: OcrBlock[]) => void
  /** Blocco evidenziato sull'immagine della pagina, quando la vista è affiancata. */
  selectedId?: string
  onSelect?: (id: string) => void
}

const LIVELLI: { value: number; label: string }[] = [
  { value: 0, label: 'Testo del documento' },
  { value: 1, label: 'Titolo principale' },
  { value: 2, label: 'Titolo' },
  { value: 3, label: 'Sottotitolo' },
  { value: 4, label: 'Rubrica' },
]

const ALLINEAMENTI: { value: OcrAlignment; label: string; Icona: typeof AlignLeft }[] = [
  { value: 'sinistra', label: 'Allinea a sinistra', Icona: AlignLeft },
  { value: 'centro', label: 'Centra', Icona: AlignCenter },
  { value: 'destra', label: 'Allinea a destra', Icona: AlignRight },
  { value: 'giustificato', label: 'Giustifica', Icona: AlignJustify },
]

const ETICHETTE: Record<OcrBlockKind, string> = {
  titolo: 'Titolo',
  paragrafo: 'Capoverso',
  elenco: 'Voce di elenco',
  tabella: 'Tabella',
  numero_pagina: 'Numero di pagina',
}

const ETICHETTE_MARCATORE: Record<string, string> = {
  puntato: 'elenco puntato',
  numerato: 'elenco numerato',
  lettera: 'elenco per lettere',
  romano: 'elenco in numeri romani',
  decimale: 'elenco a livelli',
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
export function OcrReview({ blocks, figures, disabled, onChange, selectedId, onSelect }: Props) {
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
          <li
            key={block.id}
            className={`iu-ocr-block iu-ocr-block--${block.kind}${selectedId === block.id ? ' is-selected' : ''}`}
            onFocusCapture={() => onSelect?.(block.id)}
          >
            <div className="iu-ocr-block__bar">
              <label className="iu-ocr-block__kind">
                <span className="iu-sr-only">Tipo di blocco</span>
                {block.kind === 'tabella' ? <Rows3 size={14} aria-hidden="true" /> : block.kind === 'numero_pagina' ? <Hash size={14} aria-hidden="true" /> : <Type size={14} aria-hidden="true" />}
                <select
                  value={block.kind}
                  disabled={disabled || block.kind === 'tabella'}
                  onChange={(event) => onChange(changeBlockKind(blocks, block.id, event.target.value as OcrBlockKind))}
                >
                  {(['titolo', 'paragrafo', 'elenco', 'numero_pagina'] as OcrBlockKind[]).map((kind) => (
                    <option key={kind} value={kind}>{ETICHETTE[kind]}</option>
                  ))}
                  {block.kind === 'tabella' ? <option value="tabella">{ETICHETTE.tabella}</option> : null}
                </select>
              </label>
              <span className="iu-ocr-block__meta">
                {block.kind === 'elenco' && markerOf(block) ? `${ETICHETTE_MARCATORE[markerOf(block)!.tipo]} · ` : ''}
                {block.kind === 'numero_pagina' ? 'escluso dal documento · ' : ''}
                {fiducia(block.confidence)}
              </span>
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
            {block.kind === 'tabella' ? null : (
              <div className="iu-ocr-block__formato">
                <label>
                  <span className="iu-sr-only">Livello del testo</span>
                  <select
                    value={block.format.livello}
                    disabled={disabled}
                    onChange={(event) => onChange(updateBlockFormat(blocks, block.id, { livello: Number(event.target.value) }))}
                  >
                    {LIVELLI.map((voce) => <option key={voce.value} value={voce.value}>{voce.label}</option>)}
                  </select>
                </label>
                <Button
                  type="button"
                  tone="neutral"
                  disabled={disabled}
                  aria-pressed={block.format.grassetto}
                  aria-label="Grassetto"
                  onClick={() => onChange(updateBlockFormat(blocks, block.id, { grassetto: !block.format.grassetto }))}
                >
                  <Bold size={14} aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  tone="neutral"
                  disabled={disabled}
                  aria-pressed={block.format.corsivo}
                  aria-label="Corsivo"
                  onClick={() => onChange(updateBlockFormat(blocks, block.id, { corsivo: !block.format.corsivo }))}
                >
                  <Italic size={14} aria-hidden="true" />
                </Button>
                {ALLINEAMENTI.map(({ value, label, Icona }) => (
                  <Button
                    key={value}
                    type="button"
                    tone="neutral"
                    disabled={disabled}
                    aria-pressed={block.format.allineamento === value}
                    aria-label={label}
                    onClick={() => onChange(updateBlockFormat(blocks, block.id, { allineamento: value }))}
                  >
                    <Icona size={14} aria-hidden="true" />
                  </Button>
                ))}
              </div>
            )}
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
