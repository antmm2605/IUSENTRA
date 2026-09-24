import { useEffect, useMemo, useRef } from 'react'
import { ChevronLeft, ChevronRight, ScanEye } from 'lucide-react'
import { Button } from '../../ui/Button'
import { blocksOfPage, type OcrBlock } from './ocrBlocks'
import type { PaginaRiconosciuta } from '../../services/documentoOcr'

type Props = {
  pagine: PaginaRiconosciuta[]
  paginaAttiva: number
  onPagina: (numero: number) => void
  blocchi: OcrBlock[]
  selezionato: string
  onSeleziona: (id: string) => void
  sovrapposizione: boolean
  onSovrapposizione: (attiva: boolean) => void
}

/**
 * La pagina com'è, accanto a quello che il riconoscimento ne ha letto.
 *
 * Un testo riconosciuto non si controlla leggendolo: si controlla confrontandolo
 * con il foglio. Qui l'immagine della pagina resta visibile e la sovrapposizione
 * mostra dove finisce ogni blocco, così l'avvocato vede subito se un capoverso
 * è stato letto per intero, se una tabella è stata spezzata o se un timbro è
 * stato scambiato per testo.
 */
export function OcrPageViewer({
  pagine,
  paginaAttiva,
  onPagina,
  blocchi,
  selezionato,
  onSeleziona,
  sovrapposizione,
  onSovrapposizione,
}: Props) {
  const pagina = useMemo(() => pagine.find((voce) => voce.numero === paginaAttiva) || pagine[0], [pagine, paginaAttiva])
  const dellaPagina = useMemo(() => (pagina ? blocksOfPage(blocchi, pagina.numero) : []), [blocchi, pagina])
  const foglio = useRef<HTMLDivElement | null>(null)

  // Il blocco scelto nel testo si porta in vista anche sul foglio, senza
  // muovere il resto della pagina: scorre solo il riquadro dell'immagine.
  useEffect(() => {
    const contenitore = foglio.current
    const scelto = contenitore?.querySelector<SVGRectElement>('.iu-ocr-viewer__riquadro.is-selected')
    if (!contenitore || !scelto) return
    const vista = contenitore.getBoundingClientRect()
    const zona = scelto.getBoundingClientRect()
    if (zona.top >= vista.top && zona.bottom <= vista.bottom) return
    const margine = 24
    contenitore.scrollTop += zona.top - vista.top - margine
  }, [selezionato, pagina, sovrapposizione])
  if (!pagina) return null
  const anteprima = pagina.anteprima
  const indice = pagine.findIndex((voce) => voce.numero === pagina.numero)

  return (
    <section className="iu-ocr-viewer" aria-label={`Pagina ${pagina.numero} riconosciuta`}>
      <header className="iu-ocr-viewer__barra">
        <div className="iu-ocr-viewer__pagine">
          <Button
            type="button"
            tone="neutral"
            disabled={indice <= 0}
            aria-label="Pagina precedente"
            onClick={() => onPagina(pagine[Math.max(0, indice - 1)].numero)}
          >
            <ChevronLeft size={15} aria-hidden="true" />
          </Button>
          <span>Pagina {pagina.numero} di {pagine.length === 1 ? pagina.numero : pagine[pagine.length - 1].numero}</span>
          <Button
            type="button"
            tone="neutral"
            disabled={indice >= pagine.length - 1}
            aria-label="Pagina successiva"
            onClick={() => onPagina(pagine[Math.min(pagine.length - 1, indice + 1)].numero)}
          >
            <ChevronRight size={15} aria-hidden="true" />
          </Button>
        </div>
        <span className="iu-ocr-viewer__origine">
          {pagina.origine === 'testo' ? 'Testo già presente nel documento' : `Riconoscimento ottico · ${Math.round(pagina.confidence * 100)}% di confidenza`}
        </span>
        {anteprima ? (
          <Button
            type="button"
            tone="neutral"
            aria-pressed={sovrapposizione}
            onClick={() => onSovrapposizione(!sovrapposizione)}
          >
            <ScanEye size={15} aria-hidden="true" />
            {sovrapposizione ? 'Nascondi i riquadri' : 'Mostra i riquadri'}
          </Button>
        ) : null}
      </header>

      {anteprima ? (
        <div className="iu-ocr-viewer__foglio" ref={foglio}>
          {/* Immagine e riquadri stanno nello stesso contenitore, alto quanto
              l'immagine: il foglio scorre, ma i riquadri restano sopra le righe. */}
          <div className="iu-ocr-viewer__tavola">
          <img src={anteprima.url} alt={`Immagine della pagina ${pagina.numero}`} width={anteprima.larghezza} height={anteprima.altezza} />
          {sovrapposizione ? (
            <svg
              className="iu-ocr-viewer__riquadri"
              viewBox={`0 0 ${anteprima.larghezza} ${anteprima.altezza}`}
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              {dellaPagina.map((blocco) => {
                if (!blocco.box) return null
                const [x0, y0, x1, y1] = blocco.box.map((valore) => valore * anteprima.scala)
                return (
                  <rect
                    key={blocco.id}
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
          ) : null}
          </div>
        </div>
      ) : (
        <p className="iu-acq-hint">Anteprima della pagina non disponibile: il testo riconosciuto resta comunque completo.</p>
      )}

      {pagina.correzioni.length || pagina.riferimenti.numeroRuolo.length || pagina.riferimenti.uffici.length ? (
        <dl className="iu-ocr-viewer__riferimenti">
          {pagina.riferimenti.numeroRuolo.length ? (
            <div><dt>Numero di ruolo letto</dt><dd>{pagina.riferimenti.numeroRuolo.join(' · ')}</dd></div>
          ) : null}
          {pagina.riferimenti.uffici.length ? (
            <div><dt>Ufficio giudiziario</dt><dd>{pagina.riferimenti.uffici.join(' · ')}</dd></div>
          ) : null}
          {pagina.riferimenti.date.length ? (
            <div><dt>Date nel testo</dt><dd>{pagina.riferimenti.date.slice(0, 3).join(' · ')}</dd></div>
          ) : null}
        </dl>
      ) : null}
    </section>
  )
}
