/** La storia dei blocchi nella revisione: il gancio React sopra ocrStoria. */
import { useCallback, useRef, useState } from 'react'
import type { OcrBlock } from './ocrBlocks'
import { annulla, registra, ripeti, storiaVuota, type Storia } from './ocrStoria'

/** La storia dei blocchi di una revisione: `cambia` al posto di onChange. */
export function useStoriaBlocchi(blocks: OcrBlock[], onChange: (blocks: OcrBlock[]) => void) {
  const storia = useRef<Storia>(storiaVuota())
  const [, aggiorna] = useState(0)
  const cambia = useCallback((nuovi: OcrBlock[], chiave = '') => {
    storia.current = registra(storia.current, blocks, chiave)
    aggiorna((valore) => valore + 1)
    onChange(nuovi)
  }, [blocks, onChange])
  const muovi = useCallback((passo: typeof annulla) => {
    const esito = passo(storia.current, blocks)
    if (!esito) return false
    storia.current = esito.storia
    aggiorna((valore) => valore + 1)
    onChange(esito.blocchi)
    return true
  }, [blocks, onChange])
  return {
    cambia,
    annulla: () => muovi(annulla),
    ripeti: () => muovi(ripeti),
    puoAnnullare: storia.current.indietro.length > 0,
    puoRipetere: storia.current.avanti.length > 0,
  }
}
