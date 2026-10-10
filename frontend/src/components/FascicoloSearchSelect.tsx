import { useId, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import './FascicoloSearchSelect.css'

export type FascicoloOption = { value: string; label: string; client?: string }
const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it').trim()

/** Ricerca locale sul catalogo autorizzato, senza cambiare la scelta dell'avvocato. */
export function FascicoloSearchSelect({ options, value, onChange, disabled = false, selectionLabel = 'Fascicolo dell’udienza', hint = 'La ricerca filtra l’elenco; scegli il procedimento da preparare.' }: {
  options: FascicoloOption[]; value: string; onChange: (value: string) => void; disabled?: boolean; selectionLabel?: string; hint?: string
}) {
  const id = useId()
  const [query, setQuery] = useState('')
  const [clientFilter, setClientFilter] = useState('')
  const clients = useMemo(() => [...new Set(options.map(option => option.client || '').filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it')), [options])
  const matches = useMemo(() => {
    const terms = normalize(query).split(/\s+/).filter(Boolean)
    return options.filter(option => (!clientFilter || option.client === clientFilter) && terms.every(term => normalize(option.label).includes(term)))
  }, [options, query, clientFilter])
  const selected = options.find(option => option.value === value)
  const visible = selected && !matches.some(option => option.value === value) ? [selected, ...matches] : matches
  return <div className="iu-fascicolo-search">
    <label htmlFor={`${id}-query`}>Cerca il fascicolo per cliente o R.G.</label>
    {clients.length > 0 && <label>Cliente<select aria-label="Filtra fascicoli per cliente" value={clientFilter} onChange={event => setClientFilter(event.target.value)} disabled={disabled}>
      <option value="">Tutti i clienti</option>{clients.map(client => <option key={client} value={client}>{client}</option>)}
    </select></label>}
    <div className="iu-fascicolo-search__controls">
      <div className="iu-fascicolo-search__query"><Search size={15} aria-hidden="true"/>
        <input id={`${id}-query`} type="search" autoComplete="off" placeholder="Nome e cognome, R.G. o numero fascicolo"
          value={query} onChange={event => setQuery(event.target.value)} disabled={disabled} aria-describedby={`${id}-results`}/>
      </div>
      <select aria-label={selectionLabel} value={value} onChange={event => onChange(event.target.value)} disabled={disabled}>
        <option value="">Scegli il fascicolo</option>
        {visible.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </div>
    <span id={`${id}-results`} role="status" className="iu-fascicolo-search__status">
      {query.trim() || clientFilter ? matches.length ? matches.length === 1 ? '1 fascicolo corrispondente' : `${matches.length} fascicoli corrispondenti` : 'Nessun fascicolo corrispondente. Prova con il cognome o il numero di ruolo.' : hint}
    </span>
  </div>
}
