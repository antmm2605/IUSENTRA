import {
  createContext,
  useCallback,
  useContext,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Archive,
  Bell,
  Box,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  Clock,
  Euro,
  FileText,
  FolderOpen,
  Mail,
  Paperclip,
  ReceiptText,
  Search,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
  UploadCloud,
  UserRound,
  UsersRound,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { IusTone } from '@/design/iusentraTokens'
import { IusLegalIcon } from './IusLegalIcon'
import { IusSectionHeader } from './IusSectionHeader'

const PRESET_ROUTE_LAYOUT_SELECTORS = [
  '.iusentra-main-area',
  '.iu-fas-layout',
  '.iu-fas-form-layout',
  '.iu-fas-detail-grid',
  '.iu-db-layout',
  '.iu-search-layout',
  '.iu-ag-layout',
  '.iu-agenda-import-grid',
  '.iu-scad-layout',
  '.iu-cli-layout',
  '.iu-cln-layout',
  '.iu-sogg-layout',
  '.iu-mail-layout',
  '.iu-msg-layout',
  '.iu-msg-compose-layout',
  '.iu-legal-layout',
  '.iu-timesheet-layout',
  '.iu-wiz-layout',
  '.iu-wiz-step-layout',
  '.iu-privacy-layout',
  '.iu-appt-layout',
  '.iu-deadline-layout',
  '.iu-sm-layout',
  '.iu-tar-layout',
  '.iu-pwiz-layout',
  '.iu-docai-layout',
  '.iu-template-compiler-layout',
  '.iu-prev-detail-layout',
  '.iu-site-ai-layout',
  '.iu-settings-layout',
  '.iu-tel-workspace',
  '.iu-tel-command-grid',
  '.iu-tel-surface-grid',
  '.iu-tel-acquisition__grid',
] as const

const PRESET_ROUTE_LAYOUT_SELECTOR = PRESET_ROUTE_LAYOUT_SELECTORS.join(',')

export const IUSENTRA_PAGE_SEQUENCE = [
  { slot: 'page-header', label: 'Header pagina', order: 10 },
  { slot: 'operational-subtitle', label: 'Sottotitolo operativo', order: 20 },
  { slot: 'primary-actions', label: 'Azioni principali', order: 30 },
  { slot: 'filters', label: 'Filtri', order: 40 },
  { slot: 'context-filters', label: 'Contesto filtri / riepilogo', order: 50 },
  { slot: 'main-content', label: 'Contenuto principale', order: 60 },
  { slot: 'pagination-footer', label: 'Paginazione / footer', order: 70 },
  { slot: 'support-sidebar', label: 'Sidebar di supporto', order: 80 },
] as const

export type IusentraPageSequenceSlot = (typeof IUSENTRA_PAGE_SEQUENCE)[number]['slot']

const IUSENTRA_PAGE_SEQUENCE_VERSION = 'canonical-v1'
const IUSENTRA_PAGE_SEQUENCE_ORDER = IUSENTRA_PAGE_SEQUENCE.map((item) => item.slot).join('>')

const IUSENTRA_SEQUENCE_ROOT_SELECTORS = [
  '.iu-content',
  '.iusentra-page-shell',
  '.iusentra-page-shell__body',
  '.iusentra-main-area',
  '.iusentra-main-surface',
  '.iusentra-data-surface',
  '.iusentra-route-main-surface',
] as const

const IUSENTRA_SEQUENCE_ROOT_SELECTOR = IUSENTRA_SEQUENCE_ROOT_SELECTORS.join(',')
const IUSENTRA_SEQUENCE_SLOT_CLASS_PREFIX = 'iusentra-sequence-slot--'

type PresetLayoutContextValue = {
  setSupportRailNode: (node: HTMLElement | null) => void
}

const PresetLayoutContext = createContext<PresetLayoutContextValue | null>(null)

function usePresetLayout() {
  return useContext(PresetLayoutContext)
}

function applyMinHeightVariable(node: HTMLElement | null, height: number) {
  if (!node) return
  node.style.setProperty('--iusentra-support-rail-min-height', `${Math.ceil(height)}px`)
}

function routeCategory(routeKey: string) {
  const route = routeKey.toLowerCase()
  if (route === '/sito-studio/builder') return 'builder'
  if (route.startsWith('/fascicoli')) return 'fascicoli'
  if (route.startsWith('/agenda') || route.startsWith('/scadenziario') || route.startsWith('/timesheet') || route.startsWith('/wizard-pro')) return 'agenda'
  if (route.startsWith('/email') || route.startsWith('/messaggi') || route.startsWith('/notifiche')) return 'comunicazioni'
  if (route.startsWith('/clienti') || route.startsWith('/soggetti') || route.startsWith('/cartelle-condivise')) return 'anagrafiche'
  if (route.startsWith('/telematico') || route.startsWith('/deposito') || route.startsWith('/pst') || route.startsWith('/pdp') || route.startsWith('/pat') || route.startsWith('/ptt') || route.startsWith('/polisweb')) return 'telematico'
  if (route.startsWith('/redazione-atti') || route.startsWith('/template-atti') || route.startsWith('/documenti')) return 'documenti'
  if (route.startsWith('/ricerca') || route.startsWith('/legal-intelligence') || route.startsWith('/giurisprudenza')) return 'ricerca'
  if (route.startsWith('/fatturazione') || route.startsWith('/preventivi') || route.startsWith('/compensi') || route.startsWith('/tariffario') || route.startsWith('/incassi')) return 'economico'
  if (route.startsWith('/admin') || route.startsWith('/utenti') || route.startsWith('/profili') || route.startsWith('/audit') || route.startsWith('/impostazioni') || route.startsWith('/backup')) return 'amministrazione'
  return 'operativo'
}

function isRailCandidate(element: HTMLElement) {
  if (element.tagName === 'ASIDE') return true
  const className = element.className.toString().toLowerCase()
  if (className.includes('main')) return false
  return (
    className.includes('rail') ||
    className.includes('side') ||
    className.includes('sidebar') ||
    className.includes('inspector') ||
    className.includes('insights') ||
    className.includes('support') ||
    className.includes('preview')
  )
}

function classNameOf(element: HTMLElement) {
  return element.className.toString().toLowerCase()
}

function ownsClassToken(element: HTMLElement, matcher: RegExp) {
  return Array.from(element.classList).some((token) => matcher.test(token.toLowerCase()))
}

function classifySequenceSlot(element: HTMLElement): IusentraPageSequenceSlot | null {
  const declared = element.dataset.iusentraSequenceSlot
  if (declared && IUSENTRA_PAGE_SEQUENCE.some((item) => item.slot === declared)) return declared as IusentraPageSequenceSlot

  const className = classNameOf(element)
  const preset = element.dataset.iusentraPreset || ''
  const tag = element.tagName.toLowerCase()

  if (preset === 'support-rail' || element.classList.contains('iusentra-route-rail') || isRailCandidate(element)) return 'support-sidebar'
  if (preset === 'pagination-bar' || tag === 'footer' || className.includes('pagination') || className.includes('pager')) return 'pagination-footer'
  if (preset === 'data-surface' || className.includes('table-card') || className.includes('data-surface')) return 'main-content'
  if (preset === 'context-filters' || className.includes('advanced') || className.includes('context') || className.includes('status-line') || className.endsWith('-status') || className.includes('-status ') || className.includes('bulkbar') || className.includes('notice') || className.includes('alert') || ownsClassToken(element, /(?:note|summary)$/)) return 'context-filters'
  if (preset === 'filters-bar' || className.includes('filters') || className.includes('filter') || className.includes('toolbar') || className.includes('searchbar') || className.includes('search-panel') || ownsClassToken(element, /(?:tabs|tablist|switcher)$/)) return 'filters'
  if (preset === 'action-card' || className.includes('actions-grid') || className.includes('quick-actions') || className.includes('action-grid') || className.includes('hero__actions') || ownsClassToken(element, /(?:stats|kpis|metrics)$/)) return 'primary-actions'
  if (className.includes('page-heading') || className.includes('section-header') || ownsClassToken(element, /hero$/)) return 'page-header'
  if (preset === 'main-surface' || className.includes('layout') || className.includes('workspace') || className.includes('main-list') || className.includes('main-panel') || className.includes('list-card') || className.includes('lower-grid')) return 'main-content'
  return null
}

function clearSequenceSlot(element: HTMLElement) {
  const routeManaged = element.dataset.iusentraSequenceManaged === 'route'
  if (routeManaged) {
    delete element.dataset.iusentraSequenceSlot
    delete element.dataset.iusentraSequenceOrder
    delete element.dataset.iusentraSequenceManaged
  }
  Array.from(element.classList)
    .filter((token) => token.startsWith(IUSENTRA_SEQUENCE_SLOT_CLASS_PREFIX))
    .forEach((token) => element.classList.remove(token))
}

function applySequenceSlot(element: HTMLElement, slot: IusentraPageSequenceSlot) {
  const order = IUSENTRA_PAGE_SEQUENCE.find((item) => item.slot === slot)?.order ?? 999
  const declaredByComponent = Boolean(element.dataset.iusentraSequenceSlot && element.dataset.iusentraSequenceManaged !== 'route')
  clearSequenceSlot(element)
  element.dataset.iusentraSequenceSlot = slot
  element.dataset.iusentraSequenceOrder = String(order)
  if (!declaredByComponent) element.dataset.iusentraSequenceManaged = 'route'
  element.classList.add(`${IUSENTRA_SEQUENCE_SLOT_CLASS_PREFIX}${slot}`)
}

function applySequencePart(element: HTMLElement, slot: IusentraPageSequenceSlot) {
  element.dataset.iusentraSequencePart = slot
  if (!element.dataset.iusentraSequenceSlot) {
    applySequenceSlot(element, slot)
  }
}

function markNestedSequenceParts(element: HTMLElement, slot: IusentraPageSequenceSlot) {
  if (slot === 'page-header') {
    const title = element.querySelector<HTMLElement>('h1,h2,[data-iusentra-title]')
    const subtitle = element.querySelector<HTMLElement>('p,.ius-section-header__description,[data-iusentra-subtitle]')
    const actions = element.querySelector<HTMLElement>('[class*="__actions"],[class*="hero-actions"],[data-iusentra-actions]')
    if (title) title.dataset.iusentraSequencePart = 'page-header'
    if (subtitle) applySequencePart(subtitle, 'operational-subtitle')
    if (actions) applySequencePart(actions, 'primary-actions')
  }

  if (slot === 'primary-actions') {
    element.querySelectorAll<HTMLElement>('article,a,button,[data-iusentra-preset="action-card"]')
      .forEach((child) => {
        child.dataset.iusentraSequencePart = 'primary-actions'
      })
  }
}

function applyRouteSequencePreset(root: HTMLElement) {
  const sequenceRoots = new Set<HTMLElement>()
  root.querySelectorAll<HTMLElement>(IUSENTRA_SEQUENCE_ROOT_SELECTOR).forEach((element) => {
    if (!element.closest('.iusentra-route-preset--excluded')) sequenceRoots.add(element)
  })

  sequenceRoots.forEach((sequenceRoot) => {
    sequenceRoot.classList.add('iusentra-route-sequence')
    sequenceRoot.dataset.iusentraSequence = IUSENTRA_PAGE_SEQUENCE_VERSION
    sequenceRoot.dataset.iusentraSequenceOrder = IUSENTRA_PAGE_SEQUENCE_ORDER

    Array.from(sequenceRoot.children).forEach((child) => {
      if (!(child instanceof HTMLElement)) return
      const slot = classifySequenceSlot(child) ?? 'main-content'
      applySequenceSlot(child, slot)
      markNestedSequenceParts(child, slot)
    })
  })

  return () => {
    sequenceRoots.forEach((sequenceRoot) => {
      sequenceRoot.classList.remove('iusentra-route-sequence')
      delete sequenceRoot.dataset.iusentraSequence
      delete sequenceRoot.dataset.iusentraSequenceOrder
      sequenceRoot.querySelectorAll<HTMLElement>('[data-iusentra-sequence-slot],[data-iusentra-sequence-part]').forEach((element) => {
        clearSequenceSlot(element)
        delete element.dataset.iusentraSequencePart
      })
    })
  }
}

function applyRouteGridPreset(root: HTMLElement) {
  const layouts = Array.from(root.querySelectorAll<HTMLElement>(PRESET_ROUTE_LAYOUT_SELECTOR))
  const observers: ResizeObserver[] = []

  layouts.forEach((layout) => {
    layout.classList.add('iusentra-route-grid')
    const children = Array.from(layout.children).filter((child): child is HTMLElement => child instanceof HTMLElement)
    const rails = children.filter(isRailCandidate)
    const mains = children.filter((child) => !rails.includes(child))

    layout.dataset.iusentraPresetGrid = 'true'
    layout.dataset.iusentraLayoutHasRail = rails.length ? 'true' : 'false'
    rails.forEach((rail) => rail.classList.add('iusentra-route-rail'))
    mains.forEach((main) => main.classList.add('iusentra-route-main-surface'))

    const measure = () => {
      const railHeight = rails.reduce((height, rail) => Math.max(height, rail.getBoundingClientRect().height), 0)
      layout.style.setProperty('--iusentra-route-rail-height', `${Math.ceil(railHeight)}px`)
    }

    measure()
    if (rails.length) {
      const observer = new ResizeObserver(measure)
      rails.forEach((rail) => observer.observe(rail))
      observers.push(observer)
    }
  })

  return () => {
    observers.forEach((observer) => observer.disconnect())
    layouts.forEach((layout) => {
      layout.classList.remove('iusentra-route-grid')
      layout.removeAttribute('data-iusentra-preset-grid')
      layout.removeAttribute('data-iusentra-layout-has-rail')
      layout.style.removeProperty('--iusentra-route-rail-height')
      Array.from(layout.children).forEach((child) => {
        if (child instanceof HTMLElement) {
          child.classList.remove('iusentra-route-rail', 'iusentra-route-main-surface')
        }
      })
    })
  }
}

export const iusentraPresetIcons = {
  fascicoli: FolderOpen,
  pratica: BriefcaseBusiness,
  scadenze: CalendarDays,
  calendario: Clock,
  documenti: FileText,
  allegati: Paperclip,
  comunicazioni: Mail,
  pec: Mail,
  depositi: UploadCloud,
  invio: Send,
  archivio: Archive,
  controlli: ShieldCheck,
  conferma: CheckCircle2,
  alert: Bell,
  attenzione: TriangleAlert,
  azioniRapide: Sparkles,
  energia: Zap,
  cliente: UserRound,
  soggetti: UsersRound,
  economico: Euro,
  fatture: ReceiptText,
  ricerca: Search,
  filtri: SlidersHorizontal,
  scatola: Box,
} satisfies Record<string, LucideIcon>

export type IusentraPresetIconKey = keyof typeof iusentraPresetIcons

export function IusentraRoutePresetFrame({
  routeKey,
  enabled = true,
  children,
}: {
  routeKey: string
  enabled?: boolean
  children: ReactNode
}) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const category = routeCategory(routeKey)

  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root || !enabled) return undefined

    let cleanup = () => {}
    let raf = window.requestAnimationFrame(() => {
      const cleanupGrid = applyRouteGridPreset(root)
      const cleanupSequence = applyRouteSequencePreset(root)
      cleanup = () => {
        cleanupSequence()
        cleanupGrid()
      }
    })

    const observer = new MutationObserver(() => {
      window.cancelAnimationFrame(raf)
      cleanup()
      raf = window.requestAnimationFrame(() => {
        const cleanupGrid = applyRouteGridPreset(root)
        const cleanupSequence = applyRouteSequencePreset(root)
        cleanup = () => {
          cleanupSequence()
          cleanupGrid()
        }
      })
    })
    observer.observe(root, { childList: true, subtree: true })

    return () => {
      window.cancelAnimationFrame(raf)
      observer.disconnect()
      cleanup()
    }
  }, [enabled, routeKey])

  return (
    <div
      ref={rootRef}
      className={cn('iusentra-route-preset', enabled ? 'iusentra-route-preset--active' : 'iusentra-route-preset--excluded')}
      data-iusentra-preset="route-frame"
      data-iusentra-route={routeKey}
      data-iusentra-route-category={category}
    >
      {children}
    </div>
  )
}

export function IusentraPageShell({
  title,
  description,
  actions,
  children,
  icon,
  iconKey,
  tone = 'primary',
  className,
}: {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  icon?: LucideIcon
  iconKey?: IusentraPresetIconKey
  tone?: IusTone
  className?: string
}) {
  const Icon = icon ?? (iconKey ? iusentraPresetIcons[iconKey] : undefined)
  return (
    <main className={cn('iu-content iusentra-page-shell', className)} data-iusentra-preset="page-shell">
      {title ? (
        <IusSectionHeader
          title={title}
          description={description}
          actions={actions}
          icon={Icon}
          tone={tone}
          level={1}
          className="iusentra-page-shell__header"
        />
      ) : null}
      <div className="iusentra-page-shell__body">{children}</div>
    </main>
  )
}

export function IusentraMainArea({
  children,
  className,
  style,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  const rootRef = useRef<HTMLElement | null>(null)
  const supportRailRef = useRef<HTMLElement | null>(null)

  const setSupportRailNode = useCallback((node: HTMLElement | null) => {
    supportRailRef.current = node
  }, [])

  useLayoutEffect(() => {
    const root = rootRef.current
    const rail = supportRailRef.current
    if (!root || !rail) return

    const measure = () => {
      const height = rail.getBoundingClientRect().height
      applyMinHeightVariable(root, height)
    }

    measure()
    const resizeObserver = new ResizeObserver(measure)
    resizeObserver.observe(rail)
    window.addEventListener('resize', measure)
    return () => {
      resizeObserver.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [])

  return (
    <PresetLayoutContext.Provider value={{ setSupportRailNode }}>
      <section
        ref={rootRef}
        className={cn('iusentra-main-area', className)}
        style={style}
        data-iusentra-preset="main-area"
        data-iusentra-sequence-slot="main-content"
      >
        {children}
      </section>
    </PresetLayoutContext.Provider>
  )
}

export function IusentraMainSurface({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('iusentra-main-surface', className)} data-iusentra-preset="main-surface" data-iusentra-sequence-slot="main-content">
      {children}
    </section>
  )
}

export function IusentraSupportRail({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const context = usePresetLayout()
  const ref = useCallback((node: HTMLElement | null) => {
    context?.setSupportRailNode(node)
  }, [context])

  return (
    <aside ref={ref} className={cn('iusentra-support-rail', className)} data-iusentra-preset="support-rail" data-iusentra-sequence-slot="support-sidebar">
      {children}
    </aside>
  )
}

export function IusentraPanelCard({
  title,
  children,
  subtitle,
  badge,
  icon,
  iconKey,
  tone = 'primary',
  action,
  className,
}: {
  title: string
  children: ReactNode
  subtitle?: string
  badge?: ReactNode
  icon?: LucideIcon
  iconKey?: IusentraPresetIconKey
  tone?: IusTone
  action?: ReactNode
  className?: string
}) {
  const Icon = icon ?? (iconKey ? iusentraPresetIcons[iconKey] : undefined)
  return (
    <section className={cn('iusentra-panel-card', className)} data-iusentra-preset="panel-card">
      <header className="iusentra-panel-card__header">
        <div className="iusentra-panel-card__title">
          {Icon ? <IusLegalIcon icon={Icon} tone={tone} /> : null}
          <span>
            <strong>{title}</strong>
            {subtitle ? <small>{subtitle}</small> : null}
          </span>
        </div>
        {action ? <div className="iusentra-panel-card__action">{action}</div> : badge ? <span className="iusentra-panel-card__badge">{badge}</span> : null}
      </header>
      <div className="iusentra-panel-card__body">{children}</div>
    </section>
  )
}

export function IusentraFiltersBar({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('iusentra-filters-bar', className)} data-iusentra-preset="filters-bar" data-iusentra-sequence-slot="filters" aria-label="Filtri principali">
      {children}
    </section>
  )
}

export function IusentraContextFilters({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('iusentra-context-filters', className)} data-iusentra-preset="context-filters" data-iusentra-sequence-slot="context-filters" aria-label="Contesto filtri">
      {children}
    </section>
  )
}

export function IusentraPaginationBar({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <footer className={cn('iusentra-pagination-bar', className)} data-iusentra-preset="pagination-bar" data-iusentra-sequence-slot="pagination-footer">
      {children}
    </footer>
  )
}

export function IusentraDataSurface({
  title,
  subtitle,
  toolbar,
  children,
  footer,
  empty,
  className,
  fill = false,
  ariaLabel,
}: {
  title?: ReactNode
  subtitle?: ReactNode
  toolbar?: ReactNode
  children: ReactNode
  footer?: ReactNode
  empty?: ReactNode
  className?: string
  fill?: boolean
  ariaLabel?: string
}) {
  return (
    <section
      className={cn('iusentra-data-surface', fill && 'iusentra-data-surface--fill', className)}
      data-iusentra-preset="data-surface"
      data-iusentra-sequence-slot="main-content"
      aria-label={ariaLabel}
    >
      {(title || toolbar) ? (
        <header className="iusentra-data-surface__header">
          <div className="iusentra-data-surface__title">
            {title ? <strong>{title}</strong> : null}
            {subtitle ? <small>{subtitle}</small> : null}
          </div>
          {toolbar ? <div className="iusentra-data-surface__toolbar">{toolbar}</div> : null}
        </header>
      ) : null}
      <div className="iusentra-data-surface__body">
        {children}
        {empty ? <div className="iusentra-data-surface__empty">{empty}</div> : null}
      </div>
      {footer ? <IusentraPaginationBar>{footer}</IusentraPaginationBar> : null}
    </section>
  )
}

export function IusentraActionCard({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <article className={cn('iusentra-action-card', className)} data-iusentra-preset="action-card" data-iusentra-sequence-slot="primary-actions">
      {children}
    </article>
  )
}

export function IusentraEmptyState({
  title,
  children,
  icon,
  iconKey,
  tone = 'neutral',
  action,
  className,
}: {
  title: string
  children?: ReactNode
  icon?: LucideIcon
  iconKey?: IusentraPresetIconKey
  tone?: IusTone
  action?: ReactNode
  className?: string
}) {
  const Icon = icon ?? (iconKey ? iusentraPresetIcons[iconKey] : undefined)
  return (
    <section className={cn('iusentra-empty-state', className)} data-iusentra-preset="empty-state">
      {Icon ? <IusLegalIcon icon={Icon} tone={tone} /> : null}
      <h2>{title}</h2>
      {children ? <p>{children}</p> : null}
      {action}
    </section>
  )
}
