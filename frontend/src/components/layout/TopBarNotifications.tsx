import { WorkPanelPortal } from './WorkPanelPortal'
import { CheckCheck, ExternalLink, Loader2, Search } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { formatDateIt, formatDateTimeIt } from '../../formatting'
import './TopBarNotifications.css'
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
  const { data, loading, mutating, error, notice, state, query, filter, setPage, markRead, markAllRead } = useNotifications(open)
  const [draftQuery, setDraftQuery] = useState('')
  const items = useMemo(() => dedupePanelItems(Array.isArray(data?.items) ? data.items : []), [data?.items])
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
      {open ? (<WorkPanelPortal onClose={onClose}>
        <div className="iu-topbar-panel iu-notifications-panel" role="dialog" aria-label="Notifiche operative">
          <header>
            <span>
              <strong>Notifiche</strong>
              <small>{!data ? 'Caricamento del conteggio…' : `${unread} da leggere · ${data.totalCount} notifiche`}</small>
            </span>
            <button type="button" className="iu-button" onClick={() => void markAllRead()} disabled={!data || !unread || loading || mutating} aria-busy={mutating}>
              {mutating ? <Loader2 className="iu-spin" size={15} /> : <CheckCheck size={15} />} Segna tutte come lette
            </button>
          </header>
          <form className="iu-notifications-filters" onSubmit={event => { event.preventDefault(); filter(state, draftQuery) }}>
            <label>Ricerca notifiche<input type="search" value={draftQuery} onChange={event => setDraftQuery(event.target.value)} placeholder="Titolo, fascicolo o attività…" maxLength={200} disabled={mutating} /></label>
            <label>Stato<select aria-label="Stato notifiche" value={state} onChange={event => filter(event.target.value, query)} disabled={mutating}><option value="all">Tutte</option><option value="unread">Da leggere</option><option value="read">Già lette</option></select></label>
            <button className="iu-button" type="submit" disabled={mutating}><Search size={15} /> Cerca</button>
            {query || state !== 'all' ? <button className="iu-button" type="button" disabled={mutating} onClick={() => { setDraftQuery(''); filter('all', '') }}>Azzera filtri</button> : null}
          </form>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento notifiche...</p> : null}
          {error ? <p className="iu-panel-state is-error" role="alert">{error}</p> : null}
          {notice ? <p className="iu-panel-state iu-notifications-notice" role="status">{notice}</p> : null}
          {data ? <p className="iu-notifications-results" aria-live="polite">{data.filteredCount} {data.filteredCount === 1 ? 'risultato' : 'risultati'}{query ? ` per “${query}”` : ''}</p> : null}
          <div className="iu-panel-list">
            {items.length ? items.map((item) => (
              <div className={`iu-notification is-${item.priority} ${item.read ? 'is-read' : ''}`} key={item.id}>
                <div className="iu-notification__content">
                  <small className="iu-notification__date">{item.type === 'deadline' ? formatDateIt(item.createdAt, 'Data non disponibile') : formatDateTimeIt(item.createdAt, 'Data non disponibile')} · {item.read ? 'Già letta' : 'Da leggere'}</small>
                  {item.href ? (
                    <a href={item.href} title={item.title}>
                      <strong>{item.title}</strong>
                      <small>{item.message}</small>
                    </a>
                  ) : (
                    <div className="iu-notification__body">
                      <strong>{item.title}</strong>
                      <small>{item.message}</small>
                    </div>
                  )}
                  {item.secondaryHref ? (
                    <a className="iu-notification__secondary" href={item.secondaryHref} target="_blank" rel="noreferrer">
                      <ExternalLink size={13} /> {item.secondaryLabel || 'Apri collegamento'}
                    </a>
                  ) : null}
                </div>
                {!item.read ? (
                  <button type="button" className="iu-button" disabled={mutating || loading} onClick={() => void markRead(item.id)}>
                    Segna letta
                  </button>
                ) : null}
              </div>
            )) : !loading && !error ? <p className="iu-panel-state">Nessuna notifica operativa.</p> : null}
          </div>
          {data && data.pageCount > 1 ? <nav className="iu-notifications-pagination" aria-label="Pagine delle notifiche"><button className="iu-button" type="button" disabled={data.page <= 1 || loading || mutating} onClick={() => setPage(data.page - 1)}>Precedente</button><span>Pagina {data.page} di {data.pageCount}</span><button className="iu-button" type="button" disabled={data.page >= data.pageCount || loading || mutating} onClick={() => setPage(data.page + 1)}>Successiva</button></nav> : null}
        </div></WorkPanelPortal>
      ) : null}
    </div>
  )
}

function dedupePanelItems<T extends { id?: string; href?: string | null; title?: string; message?: string }>(items: T[]): T[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = [item.id || '', item.href || '', item.title || '', item.message || ''].join('|').toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
