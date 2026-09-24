import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import type { OcrBlock } from './ocrBlocks'
import { disposizioniDellaPagina, marginiDellaPagina, pagineDelFoglio, type GeometriaPagina, type MarginiPagina } from './ocrPagina'

/** Larghezza di un A4 in pixel CSS: 210 mm a 96 punti per pollice. */
const LARGHEZZA_A4_PX = (210 / 25.4) * 96
/** Aria fra il bordo del pannello e la pagina. */
const RESPIRO_PX = 24

function stileDellaScala(scala: number) {
  return { zoom: scala } as CSSProperties
}

/**
 * Il foglio e' alto quanto la pagina del documento (min-height A4): sotto
 * l'ultima parte non si aggiunge il margine basso, perche' il numero di pagina
 * e' gia' messo al suo posto nel pie' di pagina. Con il margine in piu' il
 * foglio veniva piu' alto dell'immagine e lo scorrimento affiancato perdeva
 * la riga man mano che si scendeva nella pagina.
 */
function stileDellaPagina(margini: MarginiPagina) {
  return { padding: `${margini.alto}mm ${margini.destro}mm 0 ${margini.sinistro}mm` } as CSSProperties
}

/**
 * Le pagine A4 del foglio della revisione.
 *
 * La pagina e' davvero di 210 millimetri, con i margini del PDF: e' per questo
 * che le righe vanno a capo dove andavano sull'originale. Per farla stare nel
 * pannello si rimpicciolisce tutta insieme (zoom), senza stringerla: stringere
 * la pagina vorrebbe dire far andare a capo le righe altrove.
 */
export function OcrFoglio({ blocks, pagine, parte }: {
  blocks: OcrBlock[]
  /** Misure delle pagine lette; senza, margini di un atto qualunque. */
  pagine?: GeometriaPagina[]
  parte: (block: OcrBlock, disposizione?: CSSProperties) => ReactNode
}) {
  const contenitore = useRef<HTMLDivElement | null>(null)
  const [scala, setScala] = useState(1)
  useEffect(() => {
    const elemento = contenitore.current
    if (!elemento || typeof ResizeObserver === 'undefined') return
    const misura = () => setScala(Math.min(1, Math.max(0.3, (elemento.clientWidth - RESPIRO_PX) / LARGHEZZA_A4_PX)))
    misura()
    const osservatore = new ResizeObserver(misura)
    osservatore.observe(elemento)
    return () => osservatore.disconnect()
  }, [])
  return (
    <div ref={contenitore} className="iu-ocr-foglio">
      <div className="iu-ocr-foglio__a4" style={stileDellaScala(scala)}>
        {pagineDelFoglio(blocks).map(({ numero, blocchi }) => {
          const geometria = pagine?.find((voce) => voce.numero === numero)
          const disposizioni = disposizioniDellaPagina(blocchi, geometria)
          return (
            <div
              key={numero}
              className="iu-ocr-pagina"
              data-pagina={numero}
              style={stileDellaPagina(marginiDellaPagina(blocchi, geometria))}
              aria-label={`Pagina ${numero}`}
            >
              {blocchi.map((blocco, indice) => parte(blocco, disposizioni[indice]))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
