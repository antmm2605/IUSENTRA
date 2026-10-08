import { useId, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import './FascicoloSearchSelect.css'

export type FascicoloOption = { value: string; label: string }
const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it').trim()

/** Ricerca locale sul catalogo autorizzato, senza cambiare la scelta dell'avvocato. */
export function FascicoloSearchSelect({ options, value, onChange, disabled = false }: {
  options: FascicoloOption[]; value: string; onChange: (value: string) => void; disabled?: boolean
}) {
  const id = useId()
  const [query, setQuery] = useState('')
  const matches = useMemo(() => {
    const terms = normalize(query).split(/\s+/).filter(Boolean)
    return options.filter(option => terms.every(term => normalize(option.label).includes(term)))
  }, [options, query])
  const selected = options.find(option => option.value === value)
  const visible = selected && !matches.some(option => option.value === value) ? [selected, ...matches] : matches
  return <div className="iu-fascicolo-search">
    <label htmlFor={`${id}-query`}>Cerca il fascicolo per cliente o R.G.</label>
    <div className="iu-fascicolo-search__controls">
      <div className="iu-fascicolo-search__query"><Search size={15} aria-hidden="true"/>
        <input id={`${id}-query`} type="search" autoComplete="off" placeholder="Nome e cognome, R.G. o numero fascicolo"
          value={query} onChange={event => setQuery(event.target.value)} disabled={disabled} aria-describedby={`${id}-results`}/>
      </div>
      <select aria-label="Fascicolo dell’udienza" value={value} onChange={event => onChange(event.target.value)} disabled={disabled}>
        <option value="">Scegli il fascicolo</option>
        {visible.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </div>
    <span id={`${id}-results`} role="status" className="iu-fascicolo-search__status">
      {query.trim() ? matches.length ? matches.length === 1 ? '1 fascicolo corrispondente' : `${matches.length} fascicoli corrispondenti` : 'Nessun fascicolo corrispondente. Prova con il cognome o il numero di ruolo.' : 'La ricerca filtra l’elenco; scegli il procedimento da preparare.'}
    </span>
  </div>
}
