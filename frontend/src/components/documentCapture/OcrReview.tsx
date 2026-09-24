import { useState, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import { AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, Italic, PaintBucket, Strikethrough, Trash2, Underline } from 'lucide-react'
import { Button } from '../../ui/Button'
import { OcrFoglio } from './OcrFoglio'
import { ETICHETTE, ParteDelFoglio, daControllare } from './OcrParte'
import type { GeometriaPagina } from './ocrPagina'
import { CARATTERI_COMUNI, CORPI, ETICHETTE_MARCATORE, LIVELLI, fiducia } from './ocrBarraVoci'
import { useSelezioneOcr } from './ocrSelezione'
import { stileTra, trattiDelBlocco } from './ocrTratti'
import {
  changeBlockKind,
  markerOf,
  removeBlock,
  updateBlockCell,
  updateBlockFormat,
  updateBlockText,
  updateSelectionFormat,
  type OcrAlignment,
  type OcrBlock,
  type OcrBlockKind,
  type OcrFigure,
  type OcrFormat,
} from './ocrBlocks'

type Props = {
  blocks: OcrBlock[]
  figures: OcrFigure[]
  disabled: boolean
  onChange: (blocks: OcrBlock[]) => void
  /** Blocco evidenziato sull'immagine della pagina, quando la vista è affiancata. */
  selectedId?: string
  onSelect?: (id: string) => void
  /** Misure delle pagine lette: il foglio prende i margini del PDF. */
  pagine?: GeometriaPagina[]
  /** Dove mettere indicazioni e barra: nella vista affiancata stanno sopra entrambi i pannelli. */
  barraIn?: HTMLElement | null
}

/** Gli stili che si accendono e si spengono: sulla parte selezionata, o sul pezzo intero se non se ne seleziona una. */
const STILI: { chiave: 'grassetto' | 'corsivo' | 'sottolineato' | 'barrato'; label: string; Icona: typeof Bold }[] = [
  { chiave: 'grassetto', label: 'Grassetto', Icona: Bold },
  { chiave: 'corsivo', label: 'Corsivo', Icona: Italic },
  { chiave: 'sottolineato', label: 'Sottolineato', Icona: Underline },
  { chiave: 'barrato', label: 'Barrato', Icona: Strikethrough },
]

const ALLINEAMENTI: { value: OcrAlignment; label: string; Icona: typeof AlignLeft }[] = [
  { value: 'sinistra', label: 'Allinea a sinistra', Icona: AlignLeft },
  { value: 'centro', label: 'Centra', Icona: AlignCenter },
  { value: 'destra', label: 'Allinea a destra', Icona: AlignRight },
  { value: 'giustificato', label: 'Giustifica', Icona: AlignJustify },
]

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
export function OcrReview({ blocks, figures, disabled, onChange, selectedId, onSelect, pagine, barraIn }: Props) {
  const [attivo, setAttivo] = useState('')
  const [ridisegno, setRidisegno] = useState(0)
  const selezione = useSelezioneOcr('.iu-ocr-barra')
  const corrente = blocks.find((block) => block.id === (selectedId || attivo)) || null
  const incerti = blocks.filter(daControllare).length
  // Con una parte del testo selezionata, neretto, corsivo, sottolineato,
  // barrato e colore valgono per quella; senza, per tutto il pezzo.
  const parziale = corrente && selezione?.blockId === corrente.id && selezione.fine > selezione.inizio ? selezione : null
  const applica = (patch: Partial<OcrFormat>, soloPezzo = false) => {
    if (!corrente) return
    onChange(parziale && !soloPezzo
      ? updateSelectionFormat(blocks, corrente.id, parziale.inizio, parziale.fine, patch)
      : updateBlockFormat(blocks, corrente.id, patch))
    setRidisegno((valore) => valore + 1)
  }
  // la barra non si prende il fuoco: la selezione nel testo resta dov'e'
  const tieniLaSelezione = (event: MouseEvent) => event.preventDefault()

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
  const premuto = (chiave: (typeof STILI)[number]['chiave']) => (corrente && parziale
    ? stileTra(trattiDelBlocco(corrente.tratti, corrente.text, corrente.format), parziale.inizio, parziale.fine, chiave)
    : Boolean(formato?.[chiave]))
  const intestazione = (
    <>
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
            onChange={(event) => applica({ livello: Number(event.target.value) }, true)}
          >
            {LIVELLI.map((voce) => <option key={voce.value} value={voce.value}>{voce.label}</option>)}
          </select>
        </label>
        <label className="iu-ocr-barra__carattere">
          <span className="iu-sr-only">Carattere</span>
          <select
            value={formato?.famiglia || ''}
            disabled={disabled || !formato}
            onChange={(event) => applica({ famiglia: event.target.value }, true)}
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
            onChange={(event) => applica({ corpo: Number(event.target.value) }, true)}
          >
            <option value={0}>Corpo del documento</option>
            {corpi.map((corpo) => <option key={corpo} value={corpo}>{`${String(corpo).replace('.', ',')} pt`}</option>)}
          </select>
        </label>
        {STILI.map(({ chiave, label, Icona }) => (
          <Button
            key={chiave}
            type="button"
            tone="neutral"
            disabled={disabled || !formato}
            aria-pressed={premuto(chiave)}
            aria-label={label}
            onMouseDown={tieniLaSelezione}
            onClick={() => applica({ [chiave]: !premuto(chiave) })}
          >
            <Icona size={14} aria-hidden="true" />
          </Button>
        ))}
        {ALLINEAMENTI.map(({ value, label, Icona }) => (
          <Button
            key={value}
            type="button"
            tone="neutral"
            disabled={disabled || !formato}
            aria-pressed={formato?.allineamento === value}
            aria-label={label}
            onMouseDown={tieniLaSelezione}
            onClick={() => applica({ allineamento: value }, true)}
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
            onChange={(event) => applica({ colore: event.target.value.toLowerCase() })}
          />
        </label>
        <Button
          type="button"
          tone="neutral"
          disabled={disabled || !formato}
          aria-label="Togli il colore e lascia quello del documento"
          onMouseDown={tieniLaSelezione}
          onClick={() => applica({ colore: '' })}
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
            ? `${ETICHETTE[corrente.kind]}${corrente.kind === 'elenco' && markerOf(corrente) ? ` · ${ETICHETTE_MARCATORE[markerOf(corrente)!.tipo]}` : ''}${corrente.kind === 'numero_pagina' ? ' · escluso dal documento' : ''}${corrente.confidence ? ` · ${fiducia(corrente.confidence)}` : ''}${parziale ? ` · ${parziale.fine - parziale.inizio} caratteri selezionati` : ''}`
            : 'Clicca nel testo per scegliere su cosa agire'}
        </span>
      </div>
    </>
  )
  return (
    <div className={`iu-ocr-review${barraIn === undefined ? '' : ' iu-ocr-review--senza-barra'}`}>
      {barraIn === undefined ? intestazione : barraIn ? createPortal(intestazione, barraIn) : null}

      <OcrFoglio
        blocks={blocks}
        pagine={pagine}
        parte={(block) => (
          <ParteDelFoglio
            key={block.id}
            block={block}
            disabled={disabled}
            scelto={corrente?.id === block.id}
            ridisegno={ridisegno}
            onText={(testo) => onChange(updateBlockText(blocks, block.id, testo))}
            onCell={(riga, colonna, valore) => onChange(updateBlockCell(blocks, block.id, riga, colonna, valore))}
            onSelect={() => scegli(block.id)}
          />
        )}
      />

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
