import { Loader2, Search } from 'lucide-react'
import { useCallback, useMemo, useRef, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useRecentItems } from '../../hooks/useRecentItems'

function labelFor(type: string) {
  return {
    case: 'Fascicolo',
    client: 'Cliente',
    document: 'Documento',
    matter: 'Pratica',
  }[type] ?? 'Elemento'
}

export function TopBarRecentItems({
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
  const { data, loading, error } = useRecentItems(open)
  const items = useMemo(() => dedupeRecentItems(data?.items ?? []), [data?.items])
  const searches = useMemo(() => dedupeRecentSearches(data?.searches ?? []), [data?.searches])
  const count = data?.totalCount ?? (items.length + searches.length)
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-icon notify" type="button" onClick={onToggle} aria-label={`Recenti e ricerche (${count})`} aria-haspopup="dialog" aria-expanded={open} title="Recenti e ricerche">
        {icon}
        {count > 0 ? <span>{count > 9 ? '9+' : count}</span> : null}
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-recent-panel" role="dialog" aria-label="Recenti e ricerche">
          <header>
            <strong>Recenti</strong>
            <small>Elementi aperti e ricerche recenti</small>
          </header>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento recenti...</p> : null}
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          {items.length ? (
            <section className="iu-panel-section">
              <h3>Elementi aperti</h3>
              <div className="iu-panel-list">
                {items.map((item) => (
                  <a className="iu-panel-item" href={item.href} key={`${item.type}-${item.id}`} onClick={onClose}>
                    <span>{labelFor(item.type).slice(0, 3)}</span>
                    <span>
                      <strong>{item.title}</strong>
                      <small>{item.subtitle ?? labelFor(item.type)}</small>
                    </span>
                  </a>
                ))}
              </div>
            </section>
          ) : null}
          {searches.length ? (
            <section className="iu-panel-section">
              <h3>Ricerche recenti</h3>
              <div className="iu-panel-list">
                {searches.map((search) => (
                  <a className="iu-panel-item" href={search.href} key={search.id} onClick={onClose}>
                    <span><Search size={14} /></span>
                    <span>
                      <strong>{search.title}</strong>
                      <small>{search.subtitle ?? 'Ricerca Studio'}</small>
                    </span>
                  </a>
                ))}
              </div>
            </section>
          ) : null}
          {!loading && !items.length && !searches.length ? <p className="iu-panel-state">Nessun elemento o ricerca recente.</p> : null}
        </div>
      ) : null}
    </div>
  )
}

function dedupeRecentItems<T extends { id?: string; href?: string; type?: string; title?: string }>(items: T[]): T[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = [item.type || '', item.id || '', item.href || '', item.title || ''].join('|').toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function dedupeRecentSearches<T extends { id?: string; href?: string; query?: string; title?: string }>(items: T[]): T[] {
  const seen = new Set<string>()
  return items.filter((item) => {
    const key = [item.query || '', item.href || '', item.title || item.id || ''].join('|').toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
