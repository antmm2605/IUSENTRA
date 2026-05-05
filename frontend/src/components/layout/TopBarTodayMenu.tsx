import { Loader2 } from 'lucide-react'
import { useCallback, useRef, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useTodaySummary } from '../../hooks/useTodaySummary'

function formatType(type: string) {
  return {
    hearing: 'Udienza',
    deadline: 'Scadenza',
    task: 'Attivita',
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
      {open ? (
        <div className="iu-topbar-panel iu-today-panel" role="dialog" aria-label="Oggi">
          <header>
            <strong>Oggi</strong>
            <small>{data?.date ? new Date(`${data.date}T12:00:00`).toLocaleDateString('it-IT', { weekday: 'long', day: '2-digit', month: 'long' }) : 'Agenda operativa'}</small>
          </header>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento riepilogo...</p> : null}
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          {data ? (
            <>
              <div className="iu-today-summary">
                <span><strong>{data.summary.hearingsToday}</strong> udienze</span>
                <span><strong>{data.summary.deadlinesToday}</strong> scadenze</span>
                <span><strong>{data.summary.tasksToday}</strong> attivita</span>
                <span><strong>{data.summary.urgentItems}</strong> urgenti</span>
              </div>
              <div className="iu-panel-list">
                {data.items.length ? data.items.map((item) => (
                  <a className={`iu-panel-item is-${item.priority}`} href={item.href} key={`${item.type}-${item.id}`} onClick={onClose}>
                    <span>{item.time ?? formatType(item.type).slice(0, 3)}</span>
                    <span>
                      <strong>{item.title}</strong>
                      <small>{formatType(item.type)}{item.clientName ? ` - ${item.clientName}` : ''}</small>
                    </span>
                  </a>
                )) : <p className="iu-panel-state">Nessuna urgenza o attivita per oggi.</p>}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
