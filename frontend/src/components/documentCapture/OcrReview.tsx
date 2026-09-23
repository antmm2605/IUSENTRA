import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, Italic, Rows3, Trash2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import {
  CLASSI_ALLINEAMENTO,
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

/**
 * Sotto questa confidenza il riconoscimento non e' sicuro di quello che ha
 * letto, e chi rilegge deve saperlo. Il testo del documento arriva sempre a
 * uno — li' non c'e' niente da controllare — quindi il segno compare solo
 * dove e' passato l'occhio ottico.
 */
const CONFIDENZA_DA_CONTROLLARE = 0.9

function fiducia(valore: number): string {
  if (!valore) return ''
  return `${Math.round(valore * 100)}% di confidenza`
}

function stileDelBlocco(block: OcrBlock) {
  return { '--iu-ocr-scala': String(block.format.scala || 1) } as CSSProperties
}

/**
 * Un blocco che si corregge scrivendo dentro, come nel documento.
 *
 * Non si riscrive il nodo mentre ci si sta scrivendo dentro: il cursore
 * salterebbe in testa a ogni lettera battuta. Il testo che arriva da fuori —
 * un blocco unito, un cambio di pagina — entra solo quando il campo non ha il
 * fuoco.
 */
function BloccoScrivibile({ block, disabled, onText, onSelect }: {
  block: OcrBlock
  disabled: boolean
  onText: (testo: string) => void
  onSelect: () => void
}) {
  const nodo = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const elemento = nodo.current
    if (!elemento || document.activeElement === elemento) return
    if (elemento.textContent !== block.text) elemento.textContent = block.text
  }, [block.text])
  return (
    <div
      ref={nodo}
      className="iu-ocr-foglio__testo"
      contentEditable={!disabled}
      suppressContentEditableWarning
      role="textbox"
      aria-multiline="true"
      aria-label={`${ETICHETTE[block.kind]}: testo da rileggere`}
      tabIndex={0}
      onFocus={onSelect}
      onInput={() => onText(nodo.current?.textContent ?? '')}
    />
  )
}

/**
 * Revisione del testo riconosciuto prima di portarlo nel documento.
 *
 * Il riconoscimento automatico sbaglia, e su un atto un errore non corretto
 * diventa un errore depositato. Qui il testo si legge di seguito, come sara'
 * nel documento — non come un elenco di schede — e si corregge scrivendoci
 * dentro. I comandi in alto agiscono sul pezzo in cui si sta scrivendo, e
 * quello che il riconoscimento ha letto con poca sicurezza resta segnato:
 * e' cosi' che si sa dove guardare, invece di rileggere tutto.
 */
export function OcrReview({ blocks, figures, disabled, onChange, selectedId, onSelect }: Props) {
  const [attivo, setAttivo] = useState('')
  const corrente = blocks.find((block) => block.id === (selectedId || attivo)) || null
  const incerti = blocks.filter(
    (block) => block.confidence > 0 && block.confidence < CONFIDENZA_DA_CONTROLLARE,
  ).length

  const scegli = (id: string) => {
    setAttivo(id)
    onSelect?.(id)
  }

  if (!blocks.length) {
    return <p className="iu-acq-hint">Nessun testo riconosciuto in questa acquisizione.</p>
  }

  const formato = corrente && corrente.kind !== 'tabella' ? corrente.format : null
  return (
    <div className="iu-ocr-review">
      <p className="iu-acq-hint">
        Rileggi e correggi scrivendo qui sotto: quello che vedi è esattamente ciò che verrà inserito
        nel documento.{incerti ? ` ${incerti} ${incerti === 1 ? 'parte è segnata' : 'parti sono segnate'} perché il riconoscimento non ne è sicuro.` : ''}
      </p>

      <div className="iu-ocr-barra" role="toolbar" aria-label="Formato del testo selezionato">
        <label className="iu-ocr-barra__livello">
          <span className="iu-sr-only">Livello del testo</span>
          <select
            value={formato ? formato.livello : 0}
            disabled={disabled || !formato}
            onChange={(event) => corrente && onChange(updateBlockFormat(blocks, corrente.id, { livello: Number(event.target.value) }))}
          >
            {LIVELLI.map((voce) => <option key={voce.value} value={voce.value}>{voce.label}</option>)}
          </select>
        </label>
        <Button
          type="button"
          tone="neutral"
          disabled={disabled || !formato}
          aria-pressed={Boolean(formato?.grassetto)}
          aria-label="Grassetto"
          onClick={() => corrente && formato && onChange(updateBlockFormat(blocks, corrente.id, { grassetto: !formato.grassetto }))}
        >
          <Bold size={14} aria-hidden="true" />
        </Button>
        <Button
          type="button"
          tone="neutral"
          disabled={disabled || !formato}
          aria-pressed={Boolean(formato?.corsivo)}
          aria-label="Corsivo"
          onClick={() => corrente && formato && onChange(updateBlockFormat(blocks, corrente.id, { corsivo: !formato.corsivo }))}
        >
          <Italic size={14} aria-hidden="true" />
        </Button>
        {ALLINEAMENTI.map(({ value, label, Icona }) => (
          <Button
            key={value}
            type="button"
            tone="neutral"
            disabled={disabled || !formato}
            aria-pressed={formato?.allineamento === value}
            aria-label={label}
            onClick={() => corrente && onChange(updateBlockFormat(blocks, corrente.id, { allineamento: value }))}
          >
            <Icona size={14} aria-hidden="true" />
          </Button>
        ))}
        <label className="iu-ocr-barra__tipo">
          <span className="iu-sr-only">Tipo di parte</span>
          <select
            value={corrente ? corrente.kind : 'paragrafo'}
            disabled={disabled || !corrente || corrente.kind === 'tabella'}
            onChange={(event) => corrente && onChange(changeBlockKind(blocks, corrente.id, event.target.value as OcrBlockKind))}
          >
            {(['titolo', 'paragrafo', 'elenco', 'numero_pagina'] as OcrBlockKind[]).map((kind) => (
              <option key={kind} value={kind}>{ETICHETTE[kind]}</option>
            ))}
            {corrente?.kind === 'tabella' ? <option value="tabella">{ETICHETTE.tabella}</option> : null}
          </select>
        </label>
        <Button
          type="button"
          tone="neutral"
          disabled={disabled || !corrente}
          aria-label="Togli questa parte dal documento"
          onClick={() => corrente && onChange(removeBlock(blocks, corrente.id))}
        >
          <Trash2 size={14} aria-hidden="true" />
        </Button>
        <span className="iu-ocr-barra__stato">
          {corrente
            ? `${ETICHETTE[corrente.kind]}${corrente.kind === 'elenco' && markerOf(corrente) ? ` · ${ETICHETTE_MARCATORE[markerOf(corrente)!.tipo]}` : ''}${corrente.kind === 'numero_pagina' ? ' · escluso dal documento' : ''}${corrente.confidence ? ` · ${fiducia(corrente.confidence)}` : ''}`
            : 'Clicca nel testo per scegliere su cosa agire'}
        </span>
      </div>

      <div className="iu-ocr-foglio">
        {blocks.map((block) => {
          const daControllare = block.confidence > 0 && block.confidence < CONFIDENZA_DA_CONTROLLARE
          return (
            <div
              key={block.id}
              className={[
                'iu-ocr-foglio__parte',
                `iu-ocr-foglio__parte--${block.kind}`,
                `iu-ocr-foglio__parte--h${block.format.livello}`,
                CLASSI_ALLINEAMENTO[block.format.allineamento],
                block.format.grassetto ? 'is-grassetto' : '',
                block.format.corsivo ? 'is-corsivo' : '',
                daControllare ? 'is-incerto' : '',
                corrente?.id === block.id ? 'is-scelto' : '',
              ].filter(Boolean).join(' ')}
              style={stileDelBlocco(block)}
              title={daControllare ? `Riconosciuto al ${Math.round(block.confidence * 100)}%: da rileggere` : undefined}
            >
              {block.kind === 'tabella' ? (
                <div className="iu-ocr-foglio__tabella" onFocusCapture={() => scegli(block.id)}>
                  <span className="iu-ocr-foglio__etichetta"><Rows3 size={13} aria-hidden="true" /> Tabella</span>
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
                <BloccoScrivibile
                  block={block}
                  disabled={disabled}
                  onText={(testo) => onChange(updateBlockText(blocks, block.id, testo))}
                  onSelect={() => scegli(block.id)}
                />
              )}
            </div>
          )
        })}
      </div>

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
