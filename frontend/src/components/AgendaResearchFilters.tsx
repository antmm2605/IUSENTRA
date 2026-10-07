import type { AgendaEvent } from '../agendaData'
import { useState } from 'react'
import { Filter } from 'lucide-react'

export type AgendaFilters = { priority: string; status: string; matter: string; owner: string }
export const emptyAgendaFilters: AgendaFilters = { priority: '', status: '', matter: '', owner: '' }
export function matchesAgendaFilters(event: AgendaEvent, filters: AgendaFilters): boolean {
  return (!filters.priority || event.priority === filters.priority)
    && (!filters.status || (filters.status.startsWith('stato:') ? event.status === filters.status.slice(6) : filters.status === 'completati' ? event.completed : !event.completed && !['ANNULLATO', 'RINVIATO'].includes(event.status.toUpperCase())))
    && (!filters.matter || (event.matterId || event.matter) === filters.matter)
    && (!filters.owner || event.owner === filters.owner)
}
export function AgendaResearchFilters({ events, value, onChange, onReset, count }: {
  events: AgendaEvent[]; value: AgendaFilters; onChange: (value: AgendaFilters) => void; onReset: () => void; count: number
}) {
  const [expanded, setExpanded] = useState(false)
  const activeCount = Object.values(value).filter(Boolean).length
  const matters = [...new Map(events.filter((event) => event.matterId || event.matter).map((event) => [event.matterId || event.matter, event.matter || event.client])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'it'))
  const statuses = [...new Set(events.map((event) => event.status).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  const owners = [...new Set(events.map((event) => event.owner).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'it'))
  const change = (key: keyof AgendaFilters, selected: string) => onChange({ ...value, [key]: selected })
  return <section className="iu-ag-research" aria-label="Ricerca e filtri agenda">
    <header>
      <button type="button" aria-expanded={expanded} onClick={() => setExpanded(current => !current)}><Filter size={14}/>Filtri avanzati{activeCount ? ` · ${activeCount} ${activeCount === 1 ? 'attivo' : 'attivi'}` : ''}</button>
      <strong role="status">{count} {count === 1 ? 'attività trovata' : 'attività trovate'}</strong>
      <button type="button" onClick={onReset}>Azzera filtri</button>
    </header>
    {expanded ? <>
    <label>Priorità<select value={value.priority} onChange={(event) => change('priority', event.target.value)}><option value="">Tutte le priorità</option>{['critica','alta','media','bassa'].map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label>
    <label>Stato attività<select value={value.status} onChange={(event) => change('status', event.target.value)}><option value="">Tutti gli stati</option><option value="aperti">Da affrontare</option><option value="completati">Completati</option>{statuses.map((status) => <option key={status} value={`stato:${status}`}>{status.charAt(0).toUpperCase() + status.slice(1).toLocaleLowerCase('it').replaceAll('_', ' ')}</option>)}</select></label>
    <label>Fascicolo<select value={value.matter} onChange={(event) => change('matter', event.target.value)}><option value="">Tutti i fascicoli</option>{matters.map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label>
    <label>Responsabile<select value={value.owner} onChange={(event) => change('owner', event.target.value)}><option value="">Tutti i responsabili</option>{owners.map((owner) => <option key={owner}>{owner}</option>)}</select></label>
    </> : null}
  </section>
}
