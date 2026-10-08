import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import type { OcrBlock } from './ocrBlocks'
import { disposizioniDellaPagina, marginiDellaPagina, pagineDelFoglio, type GeometriaPagina, type MarginiPagina } from './ocrPagina'

/** Larghezza di un A4 in pixel CSS: 210 mm a 96 punti per pollice. */
const LARGHEZZA_A4_PX = (210 / 25.4) * 96
/** Aria fra il bordo del pannello e la pagina. */
const RESPIRO_PX = 24

function stileDellaScala(scala: number) {
  return { zoom: scala, rowGap: `${12 / scala}px` } as CSSProperties
}

/**
 * Il foglio e' alto quanto la pagina del documento (min-height A4): sotto
 * l'ultima parte non si aggiunge il margine basso, perche' il numero di pagina
 * e' gia' messo al suo posto nel pie' di pagina. Con il margine in piu' il
 * foglio veniva piu' alto dell'immagine e lo scorrimento affiancato perdeva
 * la riga man mano che si scendeva nella pagina.
 */
function stileDellaPagina(margini: MarginiPagina, geometria?: GeometriaPagina) {
  return { padding: `${margini.alto}mm ${margini.destro}mm 0 ${margini.sinistro}mm`,
    ...(geometria && geometria.larghezza > 0
      ? { minHeight: `${210 * geometria.altezza / geometria.larghezza}mm` } : {}) } as CSSProperties
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
  const [larghezza, setLarghezza] = useState(LARGHEZZA_A4_PX)
  useEffect(() => {
    const elemento = contenitore.current
    if (!elemento || typeof ResizeObserver === 'undefined') return
    const misura = () => setLarghezza(Math.max(80, elemento.clientWidth - RESPIRO_PX))
    misura()
    const osservatore = new ResizeObserver(misura)
    osservatore.observe(elemento)
    return () => osservatore.disconnect()
  }, [])
  return (
    <div ref={contenitore} className="iu-ocr-foglio">
      <div className="iu-ocr-foglio__a4" style={{ rowGap: '12px' }}>
        {pagineDelFoglio(blocks).map(({ numero, blocchi }) => {
          const geometria = pagine?.find((voce) => voce.numero === numero)
          const larghezzaMm = geometria?.larghezzaMm || 210
          const altezzaMm = geometria?.altezzaMm || (geometria ? 210 * geometria.altezza / geometria.larghezza : 297)
          const scala = larghezza / (larghezzaMm * 96 / 25.4)
          const disposizioni = disposizioniDellaPagina(blocchi, geometria)
          return (
            <div key={numero} style={{ width: larghezza, height: larghezza * altezzaMm / larghezzaMm, position: 'relative' }}>
            <div
              className={`iu-ocr-pagina${geometria?.fondo ? ' iu-ocr-pagina--nativa' : ''}`}
              data-pagina={numero}
              style={{ ...stileDellaPagina(marginiDellaPagina(blocchi, geometria), geometria),
                ...stileDellaScala(scala), width: `${larghezzaMm}mm`, minHeight: `${altezzaMm}mm`,
                ...(geometria?.fondo ? { height: `${altezzaMm}mm`, padding: 0, position: 'relative' } : {}) }}
              aria-label={`Pagina ${numero}`}
            >
              {geometria?.fondo ? <img className="iu-ocr-pagina__grafica" src={geometria.fondo} alt="" aria-hidden="true" /> : null}
              {blocchi.map((blocco, indice) => {
                if (!geometria?.fondo || !blocco.box) return parte(blocco, disposizioni[indice])
                const [x0, y0, x1, y1] = blocco.box
                const rotazione = blocco.rotation || 0
                const verticale = Math.abs(rotazione) === 90
                const sinistra = rotazione === 90 || Math.abs(rotazione) === 180 ? x1 : x0
                const alto = rotazione === -90 || Math.abs(rotazione) === 180 ? y1 : y0
                const larghezzaTesto = verticale
                  ? (y1 - y0) / geometria.altezza * altezzaMm
                  : (x1 - x0) / geometria.larghezza * larghezzaMm
                return parte(blocco, { position: 'absolute', left: `${sinistra / geometria.larghezza * larghezzaMm}mm`,
                  top: `${alto / geometria.altezza * altezzaMm}mm`,
                  width: `${larghezzaTesto + 0.5}mm`,
                  ...(rotazione ? { transform: `rotate(${rotazione}deg)`, transformOrigin: 'top left' } : {}),
                  margin: 0, whiteSpace: geometria.testiOriginali?.[blocco.id] === blocco.text ? 'pre' : 'pre-wrap',
                  '--iu-ocr-interlinea': blocco.righe?.interlinea
                    ? `${blocco.righe.interlinea / geometria.altezza * altezzaMm}mm` : '1.15',
                } as CSSProperties)
              })}
            </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
