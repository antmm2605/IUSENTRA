import { useState } from 'react'
import { BookOpen } from 'lucide-react'
import { Button } from '../ui/Button'

// Sigle come si citano negli atti: il server riconosce gli estremi e apre l'articolo (e il comma) vigente
// dall'archivio Normattiva del software, come primo risultato «Norma citata».
const TIPI_ATTO = [
  { sigla: 'L.', etichetta: 'Legge' },
  { sigla: 'D.Lgs.', etichetta: 'Decreto legislativo' },
  { sigla: 'D.L.', etichetta: 'Decreto-legge' },
  { sigla: 'D.P.R.', etichetta: 'D.P.R.' },
  { sigla: 'D.M.', etichetta: 'Decreto ministeriale' },
  { sigla: 'D.P.C.M.', etichetta: 'D.P.C.M.' },
  { sigla: 'R.D.', etichetta: 'Regio decreto' },
  { sigla: 'L. cost.', etichetta: 'Legge costituzionale' },
]

export function citazioneDaEstremi(estremi: { tipo: string; numero: string; anno: string; articolo: string; comma: string }) {
  const parti = []
  if (estremi.articolo.trim()) parti.push(`art. ${estremi.articolo.trim()}`)
  if (estremi.articolo.trim() && estremi.comma.trim()) parti.push(`comma ${estremi.comma.trim()}`)
  parti.push(`${estremi.tipo} ${estremi.numero.trim()}/${estremi.anno.trim()}`)
  return parti.join(' ')
}

export function RicercaPerEstremi({ loading, onCerca }: { loading: boolean; onCerca: (citazione: string) => void }) {
  const [tipo, setTipo] = useState('L.')
  const [numero, setNumero] = useState('')
  const [anno, setAnno] = useState('')
  const [articolo, setArticolo] = useState('')
  const [comma, setComma] = useState('')
  const completo = /^\d{1,5}$/.test(numero.trim()) && /^\d{4}$/.test(anno.trim())
  return (
    <details className="iu-li-advanced-filters iu-li-estremi">
      <summary>
        <BookOpen size={14} aria-hidden="true" />
        Ricerca per estremi dell'atto
      </summary>
      <form
        className="iu-li-filter-grid"
        aria-label="Ricerca per estremi dell'atto"
        onSubmit={(event) => {
          event.preventDefault()
          if (completo) onCerca(citazioneDaEstremi({ tipo, numero, anno, articolo, comma }))
        }}
      >
        <label>
          <span>Tipo di atto</span>
          <select value={tipo} onChange={(event) => setTipo(event.target.value)}>
            {TIPI_ATTO.map((voce) => <option value={voce.sigla} key={voce.sigla}>{voce.etichetta}</option>)}
          </select>
        </label>
        <label>
          <span>Numero</span>
          <input inputMode="numeric" value={numero} onChange={(event) => setNumero(event.target.value)} placeholder="Es. 107" />
        </label>
        <label>
          <span>Anno</span>
          <input inputMode="numeric" value={anno} onChange={(event) => setAnno(event.target.value)} placeholder="Es. 2015" />
        </label>
        <label>
          <span>Articolo</span>
          <input value={articolo} onChange={(event) => setArticolo(event.target.value)} placeholder="Es. 1 o 2-bis" />
        </label>
        <label>
          <span>Comma</span>
          <input value={comma} onChange={(event) => setComma(event.target.value)} placeholder="Es. 121" disabled={!articolo.trim()} />
        </label>
        <Button type="submit" tone="primary" disabled={loading || !completo}>
          <BookOpen size={16} aria-hidden="true" />
          Apri la norma
        </Button>
      </form>
    </details>
  )
}
