import { Search } from 'lucide-react'
import './shell.css'

export function CommandPalette({ query = '' }: { query?: string }) {
  return (
    <form className="iu-command-palette" role="search" action="/global-search" method="get">
      <label className="iu-sr-only" htmlFor="iu-command-search">Ricerca nello studio</label>
      <Search size={17} aria-hidden="true" />
      <input id="iu-command-search" name="q" defaultValue={query} placeholder="Cerca fascicoli, clienti, scadenze, documenti" />
    </form>
  )
}
