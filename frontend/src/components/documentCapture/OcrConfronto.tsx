import { useMemo, useRef, useState, type ReactNode } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { PaginaRiconosciuta } from '../../services/documentoOcr'
import type { OcrBlock, OcrFigure } from './ocrBlocks'
import { OcrPageViewer } from './OcrPageViewer'
import { OcrReview } from './OcrReview'
import { useScorrimentoAppaiato } from './ocrScorrimento'
import { useSchermoIntero } from './useSchermoIntero'
import './fascicoloOcr.css'

type Props = {
  pagine: PaginaRiconosciuta[]
  blocchi: OcrBlock[]
  figure: OcrFigure[]
  disabled: boolean
  onChange: (blocchi: OcrBlock[]) => void
  azioni?: ReactNode
  esito?: string
  errore?: boolean
}

/** Unico confronto originale/revisione, per fascicoli e strumenti. */
export function OcrConfronto({ pagine, blocchi, figure, disabled, onChange, azioni, esito, errore }: Props) {
  const affiancato = useRef<HTMLDivElement | null>(null)
  const schermoIntero = useSchermoIntero(affiancato)
  const [selezionato, setSelezionato] = useState('')
  const [sovrapposizione, setSovrapposizione] = useState(true)
  const [postoComandi, setPostoComandi] = useState<HTMLDivElement | null>(null)
  const [postoBarra, setPostoBarra] = useState<HTMLDivElement | null>(null)
  const [postoRiferimenti, setPostoRiferimenti] = useState<HTMLDivElement | null>(null)
  useScorrimentoAppaiato(affiancato, blocchi.length > 0)
  const geometrie = useMemo(() => pagine.flatMap((pagina) => (
    pagina.anteprima && pagina.anteprima.scala > 0
      ? [{ numero: pagina.numero, larghezza: pagina.anteprima.larghezza / pagina.anteprima.scala,
          altezza: pagina.anteprima.altezza / pagina.anteprima.scala,
          larghezzaMm: pagina.dimensioniPt ? pagina.dimensioniPt.larghezza * 25.4 / 72 : undefined,
          altezzaMm: pagina.dimensioniPt ? pagina.dimensioniPt.altezza * 25.4 / 72 : undefined,
          fondo: pagina.origine === 'testo' ? pagina.fondo?.url : undefined,
          testiOriginali: Object.fromEntries(pagina.blocks.map(blocco => [blocco.id, blocco.text])) }]
      : []
  )), [pagine])

  return (
    <div ref={affiancato} className={`iu-ocr-affiancato${schermoIntero.ripiego ? ' is-schermo-intero' : ''}`}>
      <div className="iu-ocr-affiancato__comandi">
        <div ref={setPostoComandi} className="iu-ocr-affiancato__pagina" />
        {esito ? <span className={`iu-ocr-affiancato__esito${errore ? ' is-errore' : ''}`} role="status" aria-live="polite">{esito}</span> : null}
        <Button type="button" tone="neutral" aria-pressed={schermoIntero.attivo} onClick={() => void schermoIntero.alterna()}>
          {schermoIntero.attivo ? <Minimize2 size={15} aria-hidden="true" /> : <Maximize2 size={15} aria-hidden="true" />}
          {schermoIntero.attivo ? 'Esci dallo schermo intero' : 'Schermo intero'}
        </Button>
      </div>
      <div ref={setPostoBarra} className="iu-ocr-affiancato__barra" />
      <OcrPageViewer comandiIn={postoComandi} riferimentiIn={postoRiferimenti}
        pagine={pagine} blocchi={blocchi} selezionato={selezionato} onSeleziona={setSelezionato}
        sovrapposizione={sovrapposizione} onSovrapposizione={setSovrapposizione} />
      <div className="iu-ocr-affiancato__testo">
        <OcrReview blocks={blocchi} figures={figure} pagine={geometrie} disabled={disabled}
          onChange={onChange} selectedId={selezionato} onSelect={setSelezionato}
          barraIn={postoBarra} azioni={azioni} />
      </div>
      <div ref={setPostoRiferimenti} className="iu-ocr-affiancato__riferimenti" />
    </div>
  )
}
