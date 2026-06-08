import { Loader2 } from 'lucide-react'
import { useCallback, useMemo, useRef, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useQuickDeadlines } from '../../hooks/useQuickDeadlines'

function formatDate(value: string) {
  if (!value) return ''
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString('it-IT', { day: '2-digit', month: 'short' })
}

export function TopBarDeadlines({
  open,
  onToggle,
  onClose,
  icon,
}: {
  open: boolean
  onToggle: () => void
  onClose: () => void
  icon: ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const { data, loading, error } = useQuickDeadlines(open)
  const deadlines = useMemo(() => dedupeDeadlines(data?.deadlines ?? []), [data?.deadlines])
  const urgent = (data?.summary.urgent ?? 0) + (data?.summary.overdue ?? 0)
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-icon notify" type="button" onClick={onToggle} aria-label="Scadenze rapide" aria-haspopup="dialog" aria-expanded={open} title="Scadenze rapide">
        {icon}
        {urgent > 0 ? <span>{urgent > 99 ? '99+' : urgent}</span> : null}
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-deadline-panel" role="dialog" aria-label="Scadenze rapide">
          <header>
            <strong>Scadenze rapide</strong>
            <small>Oggi, domani e prossimi 7 giorni</small>
          </header>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento scadenze...</p> : null}
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          {data ? (
            <>
              <div className="iu-deadline-summary">
                <span><strong>{data.summary.today}</strong> oggi</span>
                <span><strong>{data.summary.tomorrow}</strong> domani</span>
                <span><strong>{data.summary.nextSevenDays}</strong> 7 giorni</span>
                <span><strong>{data.summary.overdue}</strong> scadute</span>
              </div>
              <div className="iu-panel-list">
                {deadlines.length ? deadlines.map((deadline) => (
                  <a className={`iu-panel-item is-${deadline.status === 'overdue' ? 'urgent' : deadline.priority}`} href={deadline.href} key={deadline.id} onClick={onClose}>
                    <span>{formatDate(deadline.dueDate)}</span>
                    <span>
                      <strong>{deadline.title}</strong>
                      <small>{deadline.caseTitle ?? deadline.clientName ?? 'Scadenziario'}</small>
                    </span>
                  </a>
                )) : <p className="iu-panel-state">Nessuna scadenza aperta nei prossimi giorni.</p>}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function dedupeDeadlines<T extends { id?: string; href?: string; title?: string; dueDate?: string }>(items: T[]): T[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = [item.id || '', item.href || '', item.dueDate || '', item.title || ''].join('|').toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
