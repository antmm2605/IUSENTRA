import { WorkPanelPortal } from './WorkPanelPortal'
import { formatDateIt } from '../../formatting'
import { Loader2 } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { QuickDeadlineList, type QuickDeadlinePeriod } from './QuickDeadlineList'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useQuickDeadlines } from '../../hooks/useQuickDeadlines'

function formatDate(value: string) { return formatDateIt(value) }

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
  const [period, setPeriod] = useState<QuickDeadlinePeriod | null>(null)
  const ref = useRef<HTMLDivElement | null>(null)
  const { data, loading, error } = useQuickDeadlines(open)
  const deadlines = useMemo(() => dedupeDeadlines(data?.deadlines ?? []).filter(v => !v.letta), [data?.deadlines])
  const urgent = data?.summary.unreadUrgent ?? ((data?.summary.urgent ?? 0) + (data?.summary.overdue ?? 0))
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <>
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-icon notify" type="button" onClick={onToggle} aria-label="Scadenze rapide" aria-haspopup="dialog" aria-expanded={open} title="Scadenze rapide">
        {icon}
        {urgent > 0 ? <span>{urgent > 99 ? '99+' : urgent}</span> : null}
      </button>
      {open ? (<WorkPanelPortal onClose={onClose}>
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
                <button type="button" onClick={() => setPeriod('today')}><strong>{data.summary.today}</strong> oggi</button>
                <button type="button" onClick={() => setPeriod('tomorrow')}><strong>{data.summary.tomorrow}</strong> domani</button>
                <button type="button" onClick={() => setPeriod('week')}><strong>{data.summary.nextSevenDays}</strong> 7 giorni</button>
                <button type="button" onClick={() => setPeriod('overdue')}><strong>{data.summary.overdue}</strong> {data.summary.overdue === 1 ? 'scaduta' : 'scadute'}<small>{data.summary.unreadOverdue ?? data.summary.overdue} da leggere</small></button>
                {(data.summary.drafts ?? 0) > 0 ? (
                  <a className="iu-deadline-summary__drafts" href="/scadenziario#proposte">
                    <strong>{data.summary.drafts}</strong> proposte da confermare
                  </a>
                ) : null}
              </div>
              <div className="iu-panel-list">
                {deadlines.length ? deadlines.map((deadline) => (
                  <a className={`iu-panel-item is-${deadline.status === 'overdue' ? 'urgent' : deadline.priority}`} href={deadline.href} key={deadline.id} >
                    <span>{formatDate(deadline.dueDate)}</span>
                    <span>
                      <strong>{deadline.title}</strong>
                      <small>{deadline.caseTitle ?? deadline.clientName ?? 'Scadenziario'} · Da leggere</small>
                    </span>
                  </a>
                )) : <p className="iu-panel-state">Nessuna scadenza da leggere nell’anteprima. Le card permettono di consultare anche quelle già lette.</p>}
              </div>
            </>
          ) : null}
        </div></WorkPanelPortal>
      ) : null}
    </div>
    {period && <QuickDeadlineList period={period} onClose={() => setPeriod(null)}/>}
    </>
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
