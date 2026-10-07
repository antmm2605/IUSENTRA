import { WorkPanelPortal } from './WorkPanelPortal'
import { Loader2 } from 'lucide-react'
import { useCallback, useRef, useState, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useTodaySummary } from '../../hooks/useTodaySummary'

function formatType(type: string) {
  return {
    hearing: 'Udienza',
    deadline: 'Scadenza',
    task: 'Attività',
    appointment: 'Appuntamento',
    communication: 'Comunicazione',
  }[type] ?? 'Elemento'
}

export function TopBarTodayMenu({
  open,
  onToggle,
  onClose,
  label,
  icon,
}: {
  open: boolean
  onToggle: () => void
  onClose: () => void
  label: string
  icon: ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const { data, loading, error } = useTodaySummary(open)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const filtered = (data?.items || []).filter(item => {
    const inGroup = filter === 'all' || (filter === 'urgent' ? item.priority === 'urgent' : item.type === filter && (filter !== 'deadline' || item.date.slice(0, 10) === data?.date))
    return inGroup && `${item.title} ${item.clientName || ''} ${formatType(item.type)}`.toLocaleLowerCase('it-IT').includes(query.trim().toLocaleLowerCase('it-IT'))
  })
  const pageOffset = Math.min(offset, Math.max(0, Math.ceil(filtered.length / 40) - 1) * 40)
  const selectFilter = (value: string) => { setFilter(value); setOffset(0) }
  const cards = data ? [
    { id: 'all', label: 'Tutto', count: data.items.length },
    { id: 'hearing', label: 'Udienze', count: data.summary.hearingsToday },
    { id: 'deadline', label: 'Scadenze oggi', count: data.summary.deadlinesToday },
    { id: 'appointment', label: 'Appuntamenti', count: data.items.filter(item => item.type === 'appointment').length },
    { id: 'task', label: 'Attività', count: data.summary.tasksToday },
    { id: 'urgent', label: 'Urgenti', count: data.summary.urgentItems },
  ] : []
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-date iu-topbar-op-button" type="button" onClick={onToggle} aria-haspopup="dialog" aria-expanded={open} title="Riepilogo di oggi">
        <span>{label}</span>
        {icon}
      </button>
      {open ? (<WorkPanelPortal onClose={onClose}>
        <div className="iu-topbar-panel iu-today-panel" role="dialog" aria-label="Oggi">
          <header>
            <strong>Oggi</strong>
            <small>{data?.date ? new Date(`${data.date}T12:00:00`).toLocaleDateString('it-IT', { timeZone: 'Europe/Rome', weekday: 'long', day: '2-digit', month: 'long' }) : 'Agenda operativa'}</small>
          </header>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento riepilogo...</p> : null}
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          {data ? (
            <>
              <div className="iu-today-summary">
                {cards.map(card => <button type="button" key={card.id} aria-pressed={filter === card.id} onClick={() => selectFilter(card.id)}><strong>{card.count}</strong>{card.label}</button>)}
              </div>
              <div className="iu-today-filters">
                <input type="search" aria-label="Cerca nel riepilogo di oggi" placeholder="Cerca attività, cliente o numero di ruolo…" value={query} onChange={event => { setQuery(event.target.value); setOffset(0) }} />
                <span role="status">{filtered.length} {filtered.length === 1 ? 'voce' : 'voci'}</span>
                {filter !== 'all' || query ? <button type="button" className="iu-panel-ghost" onClick={() => { selectFilter('all'); setQuery('') }}>Azzera filtri</button> : null}
              </div>
              <div className="iu-panel-list">
                {filtered.length ? filtered.slice(pageOffset, pageOffset + 40).map((item) => (
                  <a className={`iu-panel-item is-${item.priority}`} href={item.href} title={item.title} key={`${item.type}-${item.id}`}>
                    <span>{item.time ?? formatType(item.type).slice(0, 3)}</span>
                    <span>
                      <strong>{item.title}</strong>
                      <small>{formatType(item.type)}{item.clientName ? ` - ${item.clientName}` : ''}</small>
                    </span>
                  </a>
                )) : <p className="iu-panel-state">{filter !== 'all' || query ? 'Nessuna voce corrisponde ai filtri.' : 'Nessuna urgenza o attività per oggi.'}</p>}
              </div>
              {filtered.length > 40 ? <nav className="iu-today-filters" aria-label="Pagine del riepilogo"><button type="button" className="iu-panel-ghost" disabled={!pageOffset} onClick={() => setOffset(pageOffset - 40)}>Precedenti</button><span>{pageOffset + 1}–{Math.min(pageOffset + 40, filtered.length)} di {filtered.length}</span><button type="button" className="iu-panel-ghost" disabled={pageOffset + 40 >= filtered.length} onClick={() => setOffset(pageOffset + 40)}>Successive</button></nav> : null}
            </>
          ) : null}
        </div></WorkPanelPortal>
      ) : null}
    </div>
  )
}
