import { useState, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { OcrBarra, type ChiaveStile } from './OcrBarra'
import { OcrFoglio } from './OcrFoglio'
import { ParteDelFoglio, daControllare } from './OcrParte'
import { OcrTrovaSostituisci } from './OcrTrovaSostituisci'
import type { GeometriaPagina } from './ocrPagina'
import { ATTRIBUTO_BLOCCO, useSelezioneOcr } from './ocrSelezione'
import { useStoriaBlocchi } from './useStoriaBlocchi'
import { stileTra, trattiDelBlocco } from './ocrTratti'
import {
  changeBlockKind,
  removeBlock,
  updateBlockCell,
  updateBlockFormat,
  updateBlockText,
  updateSelectionFormat,
  type OcrBlock,
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
  /** Salva e Stampa nella barra degli strumenti. */
  azioni?: ReactNode
}

/**
 * Revisione del testo riconosciuto prima di portarlo nel documento.
 *
 * Il riconoscimento automatico sbaglia, e su un atto un errore non corretto
 * diventa un errore depositato. Qui il testo si legge di seguito, come sara'
 * nel documento — non come un elenco di schede — e si corregge scrivendoci
 * dentro. I comandi in alto agiscono sul pezzo in cui si sta scrivendo, e
 * quello che il riconoscimento ha letto con poca sicurezza resta segnato:
 * e' cosi' che si sa dove guardare, invece di rileggere tutto. Ogni cambio si
 * annulla e si ripete (Ctrl+Z, Ctrl+Y), e un errore ripetuto si corregge in
 * tutto il documento con trova e sostituisci (Ctrl+F).
 */
export function OcrReview({ blocks, figures, disabled, onChange, selectedId, onSelect, pagine, barraIn, azioni }: Props) {
  const [attivo, setAttivo] = useState('')
  const [ridisegno, setRidisegno] = useState(0)
  const [trova, setTrova] = useState(false)
  const storia = useStoriaBlocchi(blocks, onChange)
  const selezione = useSelezioneOcr('.iu-ocr-barra')
  const corrente = blocks.find((block) => block.id === (selectedId || attivo)) || null
  const incerti = blocks.filter(daControllare).length
  const ridisegna = () => setRidisegno((valore) => valore + 1)
  // Con una parte del testo selezionata, neretto, corsivo, sottolineato,
  // barrato e colore valgono per quella; senza, per tutto il pezzo.
  const parziale = corrente && selezione?.blockId === corrente.id && selezione.fine > selezione.inizio ? selezione : null
  const applica = (patch: Partial<OcrFormat>, soloPezzo = false) => {
    if (!corrente) return
    storia.cambia(parziale && !soloPezzo
      ? updateSelectionFormat(blocks, corrente.id, parziale.inizio, parziale.fine, patch)
      : updateBlockFormat(blocks, corrente.id, patch))
    ridisegna()
  }
  const premuto = (chiave: ChiaveStile) => (corrente && parziale
    ? stileTra(trattiDelBlocco(corrente.tratti, corrente.text, corrente.format), parziale.inizio, parziale.fine, chiave)
    : Boolean(corrente && corrente.kind !== 'tabella' && corrente.format[chiave]))
  const annulla = () => { if (storia.annulla()) ridisegna() }
  const ripeti = () => { if (storia.ripeti()) ridisegna() }

  const scegli = (id: string) => {
    setAttivo(id)
    onSelect?.(id)
  }
  const vai = (id: string) => {
    scegli(id)
    document.querySelector(`[${ATTRIBUTO_BLOCCO}="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }
  // Le scorciatoie di un programma di scrittura: la storia e' della revisione, non del campo.
  const scorciatoie = (evento: KeyboardEvent) => {
    if (!(evento.ctrlKey || evento.metaKey) || evento.altKey) return
    const tasto = evento.key.toLowerCase()
    if (tasto === 'z' && !evento.shiftKey) { evento.preventDefault(); annulla() }
    else if (tasto === 'y' || (tasto === 'z' && evento.shiftKey)) { evento.preventDefault(); ripeti() }
    else if (tasto === 'f') { evento.preventDefault(); setTrova(true) }
  }

  if (!blocks.length) {
    return <p className="iu-acq-hint">Nessun testo riconosciuto in questa acquisizione.</p>
  }

  const intestazione = (
    <>
      <p className="iu-acq-hint">
        Rileggi e correggi scrivendo qui sotto: quello che vedi è esattamente ciò che verrà inserito
        nel documento.{incerti ? ` ${incerti} ${incerti === 1 ? 'parte è segnata' : 'parti sono segnate'} perché il riconoscimento non ne è sicuro.` : ''}
      </p>
      <OcrBarra
        blocks={blocks}
        corrente={corrente}
        disabled={disabled}
        selezionati={parziale ? parziale.fine - parziale.inizio : 0}
        applica={applica}
        premuto={premuto}
        onTipo={(kind) => corrente && storia.cambia(changeBlockKind(blocks, corrente.id, kind))}
        onTogli={() => corrente && storia.cambia(removeBlock(blocks, corrente.id))}
        storia={{ annulla, ripeti, puoAnnullare: storia.puoAnnullare, puoRipetere: storia.puoRipetere }}
        trovaAperto={trova}
        onTrova={() => setTrova((aperto) => !aperto)}
        azioni={azioni}
      />
      {trova ? (
        <OcrTrovaSostituisci
          blocks={blocks}
          disabled={disabled}
          onCambia={(nuovi) => { storia.cambia(nuovi); ridisegna() }}
          onVai={vai}
          onChiudi={() => setTrova(false)}
        />
      ) : null}
    </>
  )
  return (
    <div className={`iu-ocr-review${barraIn === undefined ? '' : ' iu-ocr-review--senza-barra'}`} onKeyDownCapture={scorciatoie}>
      {barraIn === undefined ? intestazione : barraIn ? createPortal(intestazione, barraIn) : null}

      <OcrFoglio
        blocks={blocks}
        pagine={pagine}
        parte={(block, disposizione) => (
          <ParteDelFoglio
            key={block.id}
            block={block}
            disposizione={disposizione}
            disabled={disabled}
            scelto={corrente?.id === block.id}
            ridisegno={ridisegno}
            onText={(testo) => storia.cambia(updateBlockText(blocks, block.id, testo), `testo:${block.id}`)}
            onCell={(riga, colonna, valore) => storia.cambia(updateBlockCell(blocks, block.id, riga, colonna, valore), `cella:${block.id}:${riga}:${colonna}`)}
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
