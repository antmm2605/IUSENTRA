import { CheckCheck, Loader2 } from 'lucide-react'
import { useCallback, useRef, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useNotifications } from '../../hooks/useNotifications'

export function TopBarNotifications({
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
  const { data, loading, error, markRead, markAllRead } = useNotifications(open)
  const items = Array.isArray(data?.items) ? data.items : []
  const unread = data?.unreadCount ?? 0
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-icon notify" type="button" onClick={onToggle} aria-label="Notifiche operative" aria-haspopup="dialog" aria-expanded={open} title="Notifiche operative">
        {icon}
        {unread > 0 ? <span>{unread > 99 ? '99+' : unread}</span> : null}
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-notifications-panel" role="dialog" aria-label="Notifiche operative">
          <header>
            <span>
              <strong>Notifiche</strong>
              <small>{unread ? `${unread} da leggere` : 'Tutto letto'}</small>
            </span>
            <button type="button" className="iu-panel-ghost" onClick={() => void markAllRead()} disabled={!items.length || loading}>
              <CheckCheck size={15} /> Segna tutte come lette
            </button>
          </header>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento notifiche...</p> : null}
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          <div className="iu-panel-list">
            {items.length ? items.map((item) => (
              <div className={`iu-notification is-${item.priority} ${item.read ? 'is-read' : ''}`} key={item.id}>
                {item.href ? (
                  <a href={item.href} onClick={onClose}>
                    <strong>{item.title}</strong>
                    <small>{item.message}</small>
                  </a>
                ) : (
                  <div className="iu-notification__body">
                    <strong>{item.title}</strong>
                    <small>{item.message}</small>
                  </div>
                )}
                {!item.read ? (
                  <button type="button" onClick={() => void markRead(item.id)}>
                    Segna letta
                  </button>
                ) : null}
              </div>
            )) : !loading && !error ? <p className="iu-panel-state">Nessuna notifica operativa.</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
