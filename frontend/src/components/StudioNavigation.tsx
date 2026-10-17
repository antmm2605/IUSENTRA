import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, Search, X } from 'lucide-react'
import { filterStudioNavigation, STUDIO_NAV_GROUPS, type StudioNavEntry } from '../studioNavigation'

export function StudioNavigation<T extends StudioNavEntry>({ items, compact, activeGroup, renderItem, showSearch = true }: {
  items: T[]; compact: boolean; activeGroup?: string; showSearch?: boolean; renderItem: (item: T) => ReactNode
}) {
  const [query, setQuery] = useState('')
  const [openGroup, setOpenGroup] = useState(activeGroup || '')
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => { if (activeGroup) setOpenGroup(activeGroup) }, [activeGroup])
  if (compact) return <>{items.map(renderItem)}</>
  const matches = filterStudioNavigation(items, query)
  const searching = query.trim().length > 0
  return <div className="iu-studio-nav">
    {showSearch ? <div className="iu-studio-nav__search">
      <Search size={15} aria-hidden="true" />
      <input ref={input} type="search" aria-label="Cerca funzioni Studio" placeholder="Trova una funzione…" maxLength={80} value={query}
        onChange={event => setQuery(event.target.value)} onKeyDown={event => {
          if (event.key === 'Escape' && query) { event.stopPropagation(); setQuery('') }
        }} />
      {query ? <button type="button" aria-label="Azzera ricerca Studio" onClick={() => { setQuery(''); input.current?.focus() }}><X size={15} /></button> : null}
    </div> : null}
    {searching ? <p className="iu-studio-nav__count" role="status">{matches.length === 1 ? '1 funzione trovata' : `${matches.length} funzioni trovate`}</p> : null}
    {STUDIO_NAV_GROUPS.map(group => {
      const grouped = matches.filter(item => item.group === group.key)
      if (!grouped.length) return null
      const open = searching || openGroup === group.key
      const controls = `${id}-${group.key}`
      return <section className="iu-studio-nav__group" key={group.key} aria-label={group.label}>
        {searching ? <div className="iu-studio-nav__label">{group.label}</div> :
          <button className="iu-studio-nav__toggle" type="button" aria-expanded={open} aria-controls={open ? controls : undefined}
            onClick={() => setOpenGroup(current => current === group.key ? '' : group.key)}>
            <span>{group.label}</span><ChevronDown size={13} aria-hidden="true" />
          </button>}
        {open ? <div className="iu-studio-nav__links" id={controls}>{grouped.map(renderItem)}</div> : null}
      </section>
    })}
    {searching && !matches.length ? <p className="iu-studio-nav__empty">Prova con «fatture», «atti», «norme» o «Lex».</p> : null}
  </div>
}
