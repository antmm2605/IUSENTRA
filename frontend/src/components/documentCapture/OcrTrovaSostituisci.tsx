import { useMemo, useState } from 'react'
import { ArrowDown, ReplaceAll, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { OcrBlock } from './ocrBlocks'
import { occorrenze, sostituisciTutto, type OpzioniRicerca } from './ocrTrova'

type Props = {
  blocks: OcrBlock[]
  disabled: boolean
  onCambia: (blocks: OcrBlock[]) => void
  /** Porta in vista il pezzo che contiene l'occorrenza. */
  onVai: (blockId: string) => void
  onChiudi: () => void
}

/** Trova e sostituisci in tutto il documento riconosciuto, tabelle comprese. */
export function OcrTrovaSostituisci({ blocks, disabled, onCambia, onVai, onChiudi }: Props) {
  const [cerca, setCerca] = useState('')
  const [sostituto, setSostituto] = useState('')
  const [opzioni, setOpzioni] = useState<OpzioniRicerca>({ maiuscole: false, paroleIntere: false })
  const [posizione, setPosizione] = useState(-1)
  const [esito, setEsito] = useState('')
  const trovate = useMemo(() => occorrenze(blocks, cerca, opzioni), [blocks, cerca, opzioni])

  const successiva = () => {
    if (!trovate.length) return
    const prossima = (posizione + 1) % trovate.length
    setPosizione(prossima)
    onVai(trovate[prossima].blockId)
  }
  const sostituisci = () => {
    const { blocks: nuovi, quante } = sostituisciTutto(blocks, cerca, sostituto, opzioni)
    if (quante) onCambia(nuovi)
    setEsito(quante ? `${quante} ${quante === 1 ? 'sostituzione fatta' : 'sostituzioni fatte'}.` : 'Nessuna occorrenza da sostituire.')
    setPosizione(-1)
  }

  return (
    <div className="iu-ocr-trova" role="search" aria-label="Trova e sostituisci nel testo">
      <label>
        <span>Trova</span>
        <input
          autoFocus
          value={cerca}
          onChange={(evento) => { setCerca(evento.target.value); setPosizione(-1); setEsito('') }}
          onKeyDown={(evento) => { if (evento.key === 'Enter') { evento.preventDefault(); successiva() } }}
        />
      </label>
      <label>
        <span>Sostituisci con</span>
        <input value={sostituto} onChange={(evento) => setSostituto(evento.target.value)} />
      </label>
      <label className="iu-ocr-trova__opzione">
        <input type="checkbox" checked={opzioni.maiuscole} onChange={(evento) => setOpzioni({ ...opzioni, maiuscole: evento.target.checked })} />
        Maiuscole/minuscole
      </label>
      <label className="iu-ocr-trova__opzione">
        <input type="checkbox" checked={opzioni.paroleIntere} onChange={(evento) => setOpzioni({ ...opzioni, paroleIntere: evento.target.checked })} />
        Parole intere
      </label>
      <span className="iu-ocr-trova__conteggio" role="status" aria-live="polite">
        {cerca ? (trovate.length ? `${posizione >= 0 ? `${posizione + 1} di ` : ''}${trovate.length} ${trovate.length === 1 ? 'occorrenza' : 'occorrenze'}` : 'Nessuna occorrenza') : ''}
        {esito ? ` ${esito}` : ''}
      </span>
      <Button type="button" tone="neutral" disabled={!trovate.length} onClick={successiva}>
        <ArrowDown size={14} aria-hidden="true" />Successiva
      </Button>
      <Button type="button" tone="neutral" disabled={disabled || !trovate.length} onClick={sostituisci}>
        <ReplaceAll size={14} aria-hidden="true" />Sostituisci tutto
      </Button>
      <Button type="button" tone="neutral" aria-label="Chiudi la ricerca" onClick={onChiudi}>
        <X size={14} aria-hidden="true" />
      </Button>
    </div>
  )
}
