import {
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  ClipboardList,
  FileText,
  Loader2,
  Mail,
  ReceiptText,
  Search,
  UsersRound,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { isCommandK, useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useGlobalSearch } from '../../hooks/useGlobalSearch'
import { trackRecentItem, trackRecentSearch } from '../../services/topbarApi'
import type { GlobalSearchResult, TopbarEntityType } from '../../types/topbar'

const groupLabels: Record<TopbarEntityType, string> = {
  case: 'Fascicoli',
  client: 'Clienti',
  matter: 'Pratiche',
  deadline: 'Scadenze',
  hearing: 'Udienze',
  document: 'Documenti',
  activity: 'Attività',
  communication: 'Comunicazioni',
  invoice: 'Fatture',
}

const icons: Record<TopbarEntityType, ReactNode> = {
  case: <BriefcaseBusiness size={17} />,
  client: <UsersRound size={17} />,
  matter: <ClipboardList size={17} />,
  deadline: <CalendarDays size={17} />,
  hearing: <CalendarDays size={17} />,
  document: <FileText size={17} />,
  activity: <ClipboardList size={17} />,
  communication: <Mail size={17} />,
  invoice: <ReceiptText size={17} />,
}

function recentEntityFromResult(result: GlobalSearchResult): { entityType: string; entityId: string } | null {
  if (['case', 'client', 'matter', 'document'].includes(result.type) && result.id) {
    return { entityType: result.type, entityId: result.id }
  }
  const destination = result.href || ''
  const documentMatch = destination.match(/^\/fascicoli\/([^/?#]+)\/documenti\/([^/?#]+)/)
  if (documentMatch?.[2]) {
    return { entityType: 'document', entityId: decodeURIComponent(documentMatch[2]) }
  }
  const caseMatch = destination.match(/^\/fascicoli\/([^/?#]+)/)
  if (caseMatch?.[1] && !['nuovo', 'esporta', 'archivio'].includes(caseMatch[1])) {
    return { entityType: 'case', entityId: decodeURIComponent(caseMatch[1]) }
  }
  const clientMatch = destination.match(/^\/clienti\/([^/?#]+)/)
  if (clientMatch?.[1] && clientMatch[1] !== 'nuovo') {
    return { entityType: 'client', entityId: decodeURIComponent(clientMatch[1]) }
  }
  return null
}

async function openResult(result: GlobalSearchResult, query: string, total: number) {
  const cleanQuery = query.trim()
  const destination = result.href || '/global-search'
  let recentChanged = false
  if (cleanQuery.length >= 2) {
    try {
      await trackRecentSearch(cleanQuery, total)
      recentChanged = true
    } catch {
      // La navigazione resta prioritaria: una mancata registrazione non deve bloccare l'apertura del risultato.
    }
  }
  const recentTarget = recentEntityFromResult(result)
  if (recentTarget) {
    try {
      await trackRecentItem(recentTarget.entityType, recentTarget.entityId)
      recentChanged = true
    } catch {
      // La navigazione resta prioritaria: una mancata registrazione non deve bloccare l'apertura del risultato.
    }
  }
  if (recentChanged) {
    window.dispatchEvent(new CustomEvent('iusentra:recent-items-updated'))
  }
  window.location.href = destination
}

function trapFocus(event: ReactKeyboardEvent<HTMLElement>, root: HTMLElement | null) {
  if (event.key !== 'Tab' || !root) return
  const nodes = Array.from(
    root.querySelectorAll<HTMLElement>('button, [href], input, [tabindex]:not([tabindex="-1"])'),
  ).filter((node) => !node.hasAttribute('disabled') && !node.getAttribute('aria-hidden'))
  if (!nodes.length) return
  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

export function TopBarSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const dialogRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const normalizedQuery = query.trim()
  const shortcutMatcher = useCallback((event: globalThis.KeyboardEvent) => isCommandK(event), [])
  const shortcutHandler = useCallback((event: globalThis.KeyboardEvent) => {
    event.preventDefault()
    setOpen(true)
  }, [])
  const { grouped, results, loading, error, empty } = useGlobalSearch(query, open)
  const activeResult = results[selectedIndex]

  useKeyboardShortcut(shortcutMatcher, shortcutHandler)
  useClickOutside(dialogRef, open, () => setOpen(false))

  useEffect(() => {
    if (!open) return
    window.setTimeout(() => inputRef.current?.focus(), 20)
  }, [open])

  useEffect(() => {
    setSelectedIndex(0)
  }, [query, results.length])

  const visibleHint = useMemo(() => (navigator.platform.toLowerCase().includes('mac') ? '⌘K' : 'Ctrl K'), [])

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    trapFocus(event, dialogRef.current)
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setSelectedIndex((current) => Math.min(results.length - 1, current + 1))
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setSelectedIndex((current) => Math.max(0, current - 1))
      return
    }
    if (event.key === 'Enter' && activeResult) {
      event.preventDefault()
      void openResult(activeResult, normalizedQuery, results.length)
    }
  }

  let absoluteIndex = 0

  return (
    <>
      <button className="iu-search iu-topbar-search-trigger" type="button" onClick={() => setOpen(true)} aria-label="Apri ricerca globale">
        <Search size={18} />
        <span>Cerca fascicolo, cliente, udienza, documento...</span>
        <kbd>{visibleHint}</kbd>
      </button>
      {open ? (
        <div className="iu-command-backdrop" role="presentation">
          <div
            className="iu-command"
            role="dialog"
            aria-modal="true"
            aria-label="Ricerca globale"
            ref={dialogRef}
            onKeyDown={handleKeyDown}
          >
            <div className="iu-command__input">
              <Search size={20} />
              <input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Cerca fascicolo, cliente, udienza, documento..."
                aria-controls="iu-command-results"
                aria-activedescendant={activeResult ? `iu-search-result-${activeResult.id}` : undefined}
              />
              {loading ? <Loader2 className="iu-spin" size={18} aria-label="Ricerca in corso" /> : <kbd>{visibleHint}</kbd>}
            </div>
            <div className="iu-command__body" id="iu-command-results" role="listbox" aria-label="Risultati ricerca">
              {query.trim().length < 2 ? <p className="iu-command-state">Inserisci almeno 2 caratteri per cercare nello studio.</p> : null}
              {error ? <p className="iu-command-state is-error">{error}</p> : null}
              {empty ? <p className="iu-command-state">Nessun risultato trovato.</p> : null}
              {!loading && !error && grouped.map((group) => (
                <section className="iu-command-group" key={group.type}>
                  <h2>{groupLabels[group.type]}</h2>
                  {group.items.map((item) => {
                    const currentIndex = absoluteIndex
                    absoluteIndex += 1
                    const selected = currentIndex === selectedIndex
                    return (
                      <button
                        type="button"
                        role="option"
                        aria-selected={selected}
                        id={`iu-search-result-${item.id}`}
                        className={`iu-command-result is-${item.priority} ${selected ? 'is-active' : ''}`}
                        key={`${item.type}-${item.id}-${item.href}`}
                        onMouseEnter={() => setSelectedIndex(currentIndex)}
                        onClick={() => { void openResult(item, normalizedQuery, results.length) }}
                      >
                        <span className="iu-command-result__icon">{icons[item.type]}</span>
                        <span className="iu-command-result__body">
                          <strong>{item.title}</strong>
                          {item.subtitle ? <small>{item.subtitle}</small> : null}
                          {item.description ? <em>{item.description}</em> : null}
                        </span>
                        <span className="iu-command-result__action">
                          Apri <ArrowUpRight size={14} />
                        </span>
                      </button>
                    )
                  })}
                </section>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
