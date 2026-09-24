import { useEffect, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { ScanEye } from 'lucide-react'
import { Button } from '../../ui/Button'
import { blocksOfPage, type OcrBlock } from './ocrBlocks'
import { fermaEco } from './ocrScorrimento'
import type { PaginaRiconosciuta } from '../../services/documentoOcr'

type Props = {
  pagine: PaginaRiconosciuta[]
  blocchi: OcrBlock[]
  selezionato: string
  onSeleziona: (id: string) => void
  sovrapposizione: boolean
  onSovrapposizione: (attiva: boolean) => void
  /** Dove mettere i comandi: nella vista affiancata stanno sopra i pannelli. */
  comandiIn?: HTMLElement | null
  /** Dove mettere i dati letti: nella vista affiancata stanno sotto i pannelli, che restano alti uguali. */
  riferimentiIn?: HTMLElement | null
}

/** Valori letti su tutte le pagine, senza ripetizioni e nell'ordine in cui compaiono. */
function unici(pagine: PaginaRiconosciuta[], voce: (pagina: PaginaRiconosciuta) => string[]): string[] {
  return Array.from(new Set(pagine.flatMap(voce)))
}

/** Com'e' stato letto il documento: testo gia' presente, riconoscimento ottico o entrambi. */
function origineDelDocumento(pagine: PaginaRiconosciuta[]): string {
  const ottiche = pagine.filter((pagina) => pagina.origine !== 'testo')
  if (!ottiche.length) return 'Testo già presente nel documento'
  const media = ottiche.reduce((somma, pagina) => somma + pagina.confidence, 0) / ottiche.length
  const ottico = `Riconoscimento ottico · ${Math.round(media * 100)}% di confidenza`
  return ottiche.length === pagine.length ? ottico : `${ottico} su ${ottiche.length} pagine di ${pagine.length}`
}

/**
 * Il documento com'è, accanto a quello che il riconoscimento ne ha letto.
 *
 * Un testo riconosciuto non si controlla leggendolo: si controlla confrontandolo
 * con il foglio. Qui le pagine scorrono una sotto l'altra come nel pannello del
 * testo, e la sovrapposizione mostra dove finisce ogni blocco, così l'avvocato
 * vede subito se un capoverso è stato letto per intero, se una tabella è stata
 * spezzata o se un timbro è stato scambiato per testo.
 */
export function OcrPageViewer({
  pagine,
  blocchi,
  selezionato,
  onSeleziona,
  sovrapposizione,
  onSovrapposizione,
  comandiIn,
  riferimentiIn,
}: Props) {
  const conImmagine = useMemo(() => pagine.filter((pagina) => pagina.anteprima), [pagine])
  const foglio = useRef<HTMLDivElement | null>(null)

  // Il blocco scelto nel testo si porta in vista anche sulle pagine, senza
  // muovere il resto della schermata: scorre solo il riquadro delle immagini.
  useEffect(() => {
    const contenitore = foglio.current
    const scelto = contenitore?.querySelector<SVGRectElement>('.iu-ocr-viewer__riquadro.is-selected')
    if (!contenitore || !scelto) return
    const vista = contenitore.getBoundingClientRect()
    const zona = scelto.getBoundingClientRect()
    if (zona.top >= vista.top && zona.bottom <= vista.bottom) return
    // Spostamento chiesto dalla scelta: il pannello del testo non deve seguirlo.
    fermaEco(contenitore, contenitore.scrollTop + zona.top - vista.top - 24)
  }, [selezionato, sovrapposizione])

  if (!pagine.length) return null
  const numeriDiRuolo = unici(pagine, (pagina) => pagina.riferimenti.numeroRuolo)
  const uffici = unici(pagine, (pagina) => pagina.riferimenti.uffici)
  const date = unici(pagine, (pagina) => pagina.riferimenti.date)

  const riferimenti = numeriDiRuolo.length || uffici.length || date.length ? (
    <dl className="iu-ocr-viewer__riferimenti">
      {numeriDiRuolo.length ? <div><dt>Numero di ruolo letto</dt><dd>{numeriDiRuolo.join(' · ')}</dd></div> : null}
      {uffici.length ? <div><dt>Ufficio giudiziario</dt><dd>{uffici.join(' · ')}</dd></div> : null}
      {date.length ? <div><dt>Date nel testo</dt><dd>{date.slice(0, 3).join(' · ')}</dd></div> : null}
    </dl>
  ) : null

  const comandi = (
    <header className="iu-ocr-viewer__barra">
      <span className="iu-ocr-viewer__origine">
        {pagine.length === 1 ? '1 pagina' : `${pagine.length} pagine`} · {origineDelDocumento(pagine)}
      </span>
      {conImmagine.length ? (
        <Button type="button" tone="neutral" aria-pressed={sovrapposizione} onClick={() => onSovrapposizione(!sovrapposizione)}>
          <ScanEye size={15} aria-hidden="true" />
          {sovrapposizione ? 'Nascondi i riquadri' : 'Mostra i riquadri'}
        </Button>
      ) : null}
    </header>
  )

  return (
    <section className="iu-ocr-viewer" aria-label="Pagine del documento">
      {comandiIn === undefined ? comandi : comandiIn ? createPortal(comandi, comandiIn) : null}

      {conImmagine.length ? (
        <div className="iu-ocr-viewer__foglio" ref={foglio}>
          {conImmagine.map((pagina) => {
            const anteprima = pagina.anteprima!
            return (
              // Immagine e riquadri nello stesso contenitore, alto quanto l'immagine:
              // le pagine scorrono, ma i riquadri restano sopra le righe.
              <div key={pagina.numero} className="iu-ocr-viewer__tavola" data-pagina={pagina.numero}>
                <img
                  src={anteprima.url}
                  alt={`Immagine della pagina ${pagina.numero}`}
                  width={anteprima.larghezza}
                  height={anteprima.altezza}
                  loading="lazy"
                />
                {/* I riquadri ci sono sempre: nascosti, servono a far scorrere
                    insieme pagina e testo blocco per blocco. */}
                <svg
                    className={`iu-ocr-viewer__riquadri${sovrapposizione ? '' : ' is-nascosti'}`}
                    viewBox={`0 0 ${anteprima.larghezza} ${anteprima.altezza}`}
                    preserveAspectRatio="none"
                    aria-hidden="true"
                  >
                    {blocksOfPage(blocchi, pagina.numero).map((blocco) => {
                      if (!blocco.box) return null
                      const [x0, y0, x1, y1] = blocco.box.map((valore) => valore * anteprima.scala)
                      return (
                        <rect
                          key={blocco.id}
                          data-blocco={blocco.id}
                          className={`iu-ocr-viewer__riquadro${selezionato === blocco.id ? ' is-selected' : ''}`}
                          x={x0}
                          y={y0}
                          width={Math.max(1, x1 - x0)}
                          height={Math.max(1, y1 - y0)}
                          onClick={() => onSeleziona(blocco.id)}
                        />
                      )
                    })}
                  </svg>
                <span className="iu-ocr-viewer__numero">Pagina {pagina.numero}</span>
              </div>
            )
          })}
        </div>
      ) : (
        <p className="iu-acq-hint">Anteprima delle pagine non disponibile: il testo riconosciuto resta comunque completo.</p>
      )}

      {riferimenti ? (riferimentiIn === undefined ? riferimenti : riferimentiIn ? createPortal(riferimenti, riferimentiIn) : null) : null}
    </section>
  )
}
