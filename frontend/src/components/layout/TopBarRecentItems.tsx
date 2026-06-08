import { Loader2 } from 'lucide-react'
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
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-icon" type="button" onClick={onToggle} aria-label="Ultimi elementi aperti" aria-haspopup="dialog" aria-expanded={open} title="Ultimi elementi aperti">
        {icon}
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-recent-panel" role="dialog" aria-label="Ultimi elementi aperti">
          <header>
            <strong>Recenti</strong>
            <small>Ultimi elementi aperti</small>
          </header>
          {loading ? <p className="iu-panel-state"><Loader2 className="iu-spin" size={16} /> Caricamento recenti...</p> : null}
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          <div className="iu-panel-list">
            {items.length ? items.map((item) => (
              <a className="iu-panel-item" href={item.href} key={`${item.type}-${item.id}`} onClick={onClose}>
                <span>{labelFor(item.type).slice(0, 3)}</span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.subtitle ?? labelFor(item.type)}</small>
                </span>
              </a>
            )) : !loading ? <p className="iu-panel-state">Nessun elemento recente registrato.</p> : null}
          </div>
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
