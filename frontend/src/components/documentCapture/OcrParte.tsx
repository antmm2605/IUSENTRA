import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Rows3 } from 'lucide-react'
import { CLASSI_ALLINEAMENTO, type OcrBlock, type OcrBlockKind } from './ocrBlocks'
import { ATTRIBUTO_BLOCCO, ripristinaSelezione, selezioneDentro } from './ocrSelezione'
import type { OcrTratto } from './ocrTratti'
import { aCapoValidi, nodiDelTesto } from './ocrACapo'

export const ETICHETTE: Record<OcrBlockKind, string> = {
  titolo: 'Titolo',
  paragrafo: 'Capoverso',
  elenco: 'Voce di elenco',
  tabella: 'Tabella',
  numero_pagina: 'Numero di pagina',
}

/**
 * Sotto questa confidenza il riconoscimento non e' sicuro di quello che ha
 * letto, e chi rilegge deve saperlo. Il testo del documento arriva sempre a
 * uno — li' non c'e' niente da controllare — quindi il segno compare solo
 * dove e' passato l'occhio ottico.
 */
export const CONFIDENZA_DA_CONTROLLARE = 0.9

export function daControllare(block: OcrBlock): boolean {
  return block.confidence > 0 && block.confidence < CONFIDENZA_DA_CONTROLLARE
}

function stileDelBlocco(block: OcrBlock, disposizione?: CSSProperties) {
  const stile: Record<string, string> = { '--iu-ocr-scala': String(block.format.scala || 1) }
  // il nero non si dichiara: senza colore il testo prende quello del foglio;
  // con i tratti il colore e' loro, parola per parola
  if (block.format.colore && !block.tratti?.length) stile.color = block.format.colore
  // carattere e corpo solo se il documento li dichiara: si vede come sarà
  if (block.format.famiglia) stile.fontFamily = `'${block.format.famiglia}', serif`
  // il corpo passa da una variabile: la dimensione la scrive il campo, non la parte
  if (block.format.corpo) stile['--iu-ocr-corpo'] = `${block.format.corpo}pt`
  // dove sta sulla pagina (vedi ocrPagina): spazi, rientri, interlinea;
  // quello che si sceglie in revisione vale sopra quello misurato
  const posto: Record<string, unknown> = { ...stile, ...disposizione }
  if (block.format.interlinea) posto['--iu-ocr-interlinea'] = String(block.format.interlinea)
  if (block.format.rientro) posto.marginLeft = `calc(${String(posto.marginLeft || '0mm')} + ${block.format.rientro}mm)`
  return posto as CSSProperties
}

/** Un tratto nel foglio: come sarà nel documento, con le classi del foglio di stile. */
function nodoDelTratto(tratto: OcrTratto): HTMLSpanElement {
  const nodo = document.createElement('span')
  nodo.className = [
    'iu-ocr-tratto',
    tratto.grassetto ? 'is-g' : '',
    tratto.corsivo ? 'is-c' : '',
    tratto.sottolineato ? 'is-s' : '',
    tratto.barrato ? 'is-b' : '',
  ].filter(Boolean).join(' ')
  if (tratto.colore) nodo.style.color = tratto.colore
  nodo.textContent = tratto.testo
  return nodo
}

/**
 * Un blocco che si corregge scrivendo dentro, come nel documento.
 *
 * Non si riscrive il nodo mentre ci si sta scrivendo dentro: il cursore
 * salterebbe in testa a ogni lettera battuta. Il testo che arriva da fuori —
 * un blocco unito, un cambio di pagina — entra solo quando il campo non ha il
 * fuoco. Fa eccezione un cambio di formato dalla barra (`ridisegno`): li' il
 * testo non cambia, si ridisegnano i tratti e la selezione torna dov'era.
 */
function BloccoScrivibile({ block, disabled, ridisegno, onText, onSelect }: {
  block: OcrBlock
  disabled: boolean
  ridisegno: number
  onText: (testo: string) => void
  onSelect: () => void
}) {
  const nodo = useRef<HTMLDivElement | null>(null)
  const ultimoRidisegno = useRef(ridisegno)
  // Lasciando il campo si ridisegna: le righe del documento tornano (o, se il
  // testo e' stato corretto, il blocco torna a capo da solo).
  const [uscite, setUscite] = useState(0)
  useEffect(() => {
    const elemento = nodo.current
    if (!elemento) return
    const perIlFormato = ultimoRidisegno.current !== ridisegno
    ultimoRidisegno.current = ridisegno
    // Il testo si legge sempre come testo semplice (onInput): i tratti sono
    // solo come lo si vede, e si riallineano da soli quando il testo cambia.
    const disegna = () => {
      elemento.replaceChildren(...nodiDelTesto(block, nodoDelTratto))
      elemento.classList.toggle('con-a-capo', aCapoValidi(block).length > 0)
    }
    if (document.activeElement !== elemento) return disegna()
    if (!perIlFormato) return
    const selezione = selezioneDentro(elemento)
    disegna()
    if (selezione) ripristinaSelezione(elemento, selezione.inizio, selezione.fine)
  }, [block, ridisegno, uscite])
  return (
    <div
      ref={nodo}
      {...{ [ATTRIBUTO_BLOCCO]: block.id }}
      className="iu-ocr-foglio__testo"
      contentEditable={!disabled}
      suppressContentEditableWarning
      role="textbox"
      aria-multiline="true"
      aria-label={`${ETICHETTE[block.kind]}: testo da rileggere`}
      tabIndex={0}
      onFocus={onSelect}
      onBlur={() => setUscite((valore) => valore + 1)}
      onInput={() => {
        // correggendo, le righe non sono piu' quelle del documento: si torna a capo
        nodo.current?.classList.remove('con-a-capo')
        onText(nodo.current?.textContent ?? '')
      }}
    />
  )
}

/**
 * Una parte del foglio riconosciuto, con addosso la forma che aveva sul
 * documento: livello, allineamento, corpo, colore, e il segno che il
 * riconoscimento non era sicuro di averla letta bene.
 */
export function ParteDelFoglio({ block, disabled, scelto, ridisegno, onText, onCell, onSelect, disposizione }: {
  block: OcrBlock
  /** Dove sta sulla pagina: distanza dalla parte sopra, rientri, interlinea. */
  disposizione?: CSSProperties
  disabled: boolean
  scelto: boolean
  /** Cresce a ogni comando della barra: il pezzo si ridisegna anche col cursore dentro. */
  ridisegno: number
  onText: (testo: string) => void
  onCell: (riga: number, colonna: number, valore: string) => void
  onSelect: () => void
}) {
  const incerto = daControllare(block)
  // con i tratti lo stile sta nelle parole: sul blocco resterebbe su tutte
  const formato = block.tratti?.length ? null : block.format
  return (
    <div
      className={[
        'iu-ocr-foglio__parte',
        `iu-ocr-foglio__parte--${block.kind}`,
        `iu-ocr-foglio__parte--h${block.format.livello}`,
        CLASSI_ALLINEAMENTO[block.format.allineamento],
        formato?.grassetto ? 'is-grassetto' : '',
        formato?.corsivo ? 'is-corsivo' : '',
        formato?.sottolineato ? 'is-sottolineato' : '',
        formato?.barrato ? 'is-barrato' : '',
        block.format.corpo ? 'has-corpo' : '',
        incerto ? 'is-incerto' : '',
        scelto ? 'is-scelto' : '',
      ].filter(Boolean).join(' ')}
      style={stileDelBlocco(block, disposizione)}
      title={incerto ? `Riconosciuto al ${Math.round(block.confidence * 100)}%: da rileggere` : undefined}
    >
      {block.kind === 'tabella' ? (
        <div className="iu-ocr-foglio__tabella" onFocusCapture={onSelect}>
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
                        onChange={(event) => onCell(rowIndex, columnIndex, event.target.value)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <BloccoScrivibile block={block} disabled={disabled} ridisegno={ridisegno} onText={onText} onSelect={onSelect} />
      )}
    </div>
  )
}
