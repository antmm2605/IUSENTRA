import { useState } from 'react'
import { AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, Italic, PaintBucket, Trash2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import { ETICHETTE, ParteDelFoglio, daControllare } from './OcrParte'
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

/**
 * I caratteri che si offrono sempre: quelli dell'editor dei documenti, più
 * quelli che il documento stesso usa. Un carattere letto dal PDF deve poter
 * restare, anche se non è fra i soliti.
 */
const CARATTERI_COMUNI = ['Times New Roman', 'Arial', 'Calibri', 'Garamond', 'Georgia', 'Book Antiqua', 'Courier New']
const CORPI = [8, 9, 10, 10.5, 11, 11.5, 12, 13, 14, 16, 18, 20, 24]

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
 * diventa un errore depositato. Qui il testo si legge di seguito, come sara'
 * nel documento — non come un elenco di schede — e si corregge scrivendoci
 * dentro. I comandi in alto agiscono sul pezzo in cui si sta scrivendo, e
 * quello che il riconoscimento ha letto con poca sicurezza resta segnato:
 * e' cosi' che si sa dove guardare, invece di rileggere tutto.
 */
export function OcrReview({ blocks, figures, disabled, onChange, selectedId, onSelect }: Props) {
  const [attivo, setAttivo] = useState('')
  const corrente = blocks.find((block) => block.id === (selectedId || attivo)) || null
  const incerti = blocks.filter(daControllare).length

  const scegli = (id: string) => {
    setAttivo(id)
    onSelect?.(id)
  }

  if (!blocks.length) {
    return <p className="iu-acq-hint">Nessun testo riconosciuto in questa acquisizione.</p>
  }

  const formato = corrente && corrente.kind !== 'tabella' ? corrente.format : null
  const famiglie = Array.from(new Set([...blocks.map((block) => block.format.famiglia).filter(Boolean), ...CARATTERI_COMUNI]))
  const corpi = formato?.corpo && !CORPI.includes(formato.corpo) ? [...CORPI, formato.corpo].sort((a, b) => a - b) : CORPI
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
        <label className="iu-ocr-barra__carattere">
          <span className="iu-sr-only">Carattere</span>
          <select
            value={formato?.famiglia || ''}
            disabled={disabled || !formato}
            onChange={(event) => corrente && onChange(updateBlockFormat(blocks, corrente.id, { famiglia: event.target.value }))}
          >
            <option value="">Carattere del documento</option>
            {famiglie.map((nome) => <option key={nome} value={nome}>{nome}</option>)}
          </select>
        </label>
        <label className="iu-ocr-barra__corpo">
          <span className="iu-sr-only">Dimensione del testo</span>
          <select
            value={formato?.corpo || 0}
            disabled={disabled || !formato}
            onChange={(event) => corrente && onChange(updateBlockFormat(blocks, corrente.id, { corpo: Number(event.target.value) }))}
          >
            <option value={0}>Corpo del documento</option>
            {corpi.map((corpo) => <option key={corpo} value={corpo}>{`${String(corpo).replace('.', ',')} pt`}</option>)}
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
        <label className="iu-ocr-barra__colore" title="Colore del testo">
          <span className="iu-sr-only">Colore del testo</span>
          <input
            type="color"
            value={formato?.colore || '#111827'}
            disabled={disabled || !formato}
            onChange={(event) => corrente && onChange(updateBlockFormat(blocks, corrente.id, { colore: event.target.value.toLowerCase() }))}
          />
        </label>
        <Button
          type="button"
          tone="neutral"
          disabled={disabled || !formato?.colore}
          aria-label="Togli il colore e lascia quello del documento"
          onClick={() => corrente && onChange(updateBlockFormat(blocks, corrente.id, { colore: '' }))}
        >
          <PaintBucket size={14} aria-hidden="true" />
        </Button>
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
        {blocks.map((block) => (
          <ParteDelFoglio
            key={block.id}
            block={block}
            disabled={disabled}
            scelto={corrente?.id === block.id}
            onText={(testo) => onChange(updateBlockText(blocks, block.id, testo))}
            onCell={(riga, colonna, valore) => onChange(updateBlockCell(blocks, block.id, riga, colonna, valore))}
            onSelect={() => scegli(block.id)}
          />
        ))}
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
