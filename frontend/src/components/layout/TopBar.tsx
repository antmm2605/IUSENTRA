import { Bell, CalendarClock, Clock3, FolderClock, Headphones, PanelLeftOpen, Plus, Settings2, TriangleAlert } from 'lucide-react'
import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import { TopBarCreateMenu } from './TopBarCreateMenu'
import { TopBarDeadlines } from './TopBarDeadlines'
import { TopBarNotifications } from './TopBarNotifications'
import { TopBarRecentItems } from './TopBarRecentItems'
import { TopBarSearch } from './TopBarSearch'
import { TopBarTimeTracker } from './TopBarTimeTracker'
import { TopBarTodayMenu } from './TopBarTodayMenu'
import { TopBarMobileMenu } from './TopBarMobileMenu'
import { IusTopBar } from '../iusentra'
import { trackRecentItem } from '../../services/topbarApi'
import type { TopbarCreateContext } from '../../types/topbar'

const StudioVoiceAssistant = lazy(() => import('../StudioVoiceAssistant'))
const DiscordanzeAccesso = lazy(() => import('./DiscordanzeAccesso'))
const VOICE_ASSISTANT_IDLE_TIMEOUT_MS = 2500
const VOICE_ASSISTANT_FALLBACK_DELAY_MS = 900

type PanelName = 'create' | 'today' | 'notifications' | 'deadlines' | 'recent' | 'timer' | null
type IdleHandleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout?: number }) => number
  cancelIdleCallback?: (handle: number) => void
}
type SupportBootstrap = {
  user?: {
    displayName?: string
    username?: string
    email?: string
  } | null
  tenant?: {
    slug?: string
    name?: string
  } | null
}

function currentContext(path: string): TopbarCreateContext {
  const caseMatch = path.match(/^\/fascicoli\/([^/?#]+)/)
  if (caseMatch && caseMatch[1] !== 'nuovo') {
    return { contextType: 'case', contextId: decodeURIComponent(caseMatch[1]) }
  }
  const clientMatch = path.match(/^\/clienti\/([^/?#]+)/)
  if (clientMatch && clientMatch[1] !== 'nuovo') {
    return { contextType: 'client', contextId: decodeURIComponent(clientMatch[1]) }
  }
  return { contextType: 'global', contextId: null }
}

function recentTargetFromPath(path: string): { entityType: string; entityId: string } | null {
  const normalized = path.split(/[?#]/, 1)[0] || '/'
  const documentMatch = normalized.match(/^\/fascicoli\/([^/?#]+)\/documenti\/([^/?#]+)/)
  if (documentMatch && documentMatch[2]) {
    return { entityType: 'document', entityId: decodeURIComponent(documentMatch[2]) }
  }
  const caseMatch = normalized.match(/^\/fascicoli\/([^/?#]+)/)
  if (caseMatch && !['nuovo', 'esporta', 'archivio'].includes(caseMatch[1])) {
    return { entityType: 'case', entityId: decodeURIComponent(caseMatch[1]) }
  }
  const clientMatch = normalized.match(/^\/clienti\/([^/?#]+)/)
  if (clientMatch && clientMatch[1] !== 'nuovo') {
    return { entityType: 'client', entityId: decodeURIComponent(clientMatch[1]) }
  }
  return null
}

function todayLabel() {
  return new Intl.DateTimeFormat('it-IT', {
    timeZone: 'Europe/Rome',
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  }).format(new Date())
}

function openSupportRoom(url: string): boolean {
  const opened = window.open(url, '_blank', 'noopener')
  if (opened) return true
  window.location.assign(url)
  return false
}

export function TopBar({
  onOpenMenu,
  activePath,
  supportEnabled = true,
  bootstrap,
}: {
  onOpenMenu: () => void
  activePath: string
  supportEnabled?: boolean
  bootstrap?: SupportBootstrap
}) {
  const [openPanels, setOpenPanels] = useState<Set<Exclude<PanelName, null>>>(() => new Set())
  const [supportOpening, setSupportOpening] = useState(false)
  const [supportError, setSupportError] = useState('')
  const [voiceAssistantReady, setVoiceAssistantReady] = useState(false)
  const lastRecentKey = useRef('')
  const context = useMemo(() => currentContext(activePath), [activePath])
  useEffect(() => {
    let cancelled = false
    let idleHandle: number | null = null
    let timeoutHandle: number | null = null
    const activate = () => {
      if (!cancelled) setVoiceAssistantReady(true)
    }
    const idleWindow = window as IdleHandleWindow
    if (typeof idleWindow.requestIdleCallback === 'function') {
      idleHandle = idleWindow.requestIdleCallback(activate, { timeout: VOICE_ASSISTANT_IDLE_TIMEOUT_MS })
    } else {
      timeoutHandle = window.setTimeout(activate, VOICE_ASSISTANT_FALLBACK_DELAY_MS)
    }
    return () => {
      cancelled = true
      if (idleHandle !== null && typeof idleWindow.cancelIdleCallback === 'function') {
        idleWindow.cancelIdleCallback(idleHandle)
      }
      if (timeoutHandle !== null) window.clearTimeout(timeoutHandle)
    }
  }, [])
  useEffect(() => {
    const target = recentTargetFromPath(activePath)
    if (!target) return
    const key = `${target.entityType}:${target.entityId}`
    if (lastRecentKey.current === key) return
    lastRecentKey.current = key
    const handle = window.setTimeout(() => {
      void trackRecentItem(target.entityType, target.entityId)
        .then(() => window.dispatchEvent(new CustomEvent('iusentra:recent-items-updated')))
        .catch(() => {})
    }, 1200)
    return () => window.clearTimeout(handle)
  }, [activePath])
  const togglePanel = (panel: Exclude<PanelName, null>) => setOpenPanels(current => { const next = new Set(current); if (next.has(panel)) next.delete(panel); else next.add(panel); return next })
  const closePanel = (panel: Exclude<PanelName, null>) => setOpenPanels(current => { const next = new Set(current); next.delete(panel); return next })
  const requestSupport = async () => {
    if (supportOpening) return
    const contextLabel = `Richiesta aperta dalla barra dello studio: ${activePath || '/'}`
    const supportUser = bootstrap?.user
    const supportTenant = bootstrap?.tenant
    setSupportOpening(true)
    setSupportError('')
    try {
      const response = await fetch('/support/studio/sessione', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          customer_name: supportUser?.displayName || supportUser?.username || '',
          customer_email: supportUser?.email || '',
          studio_slug: supportTenant?.slug || '',
          studio_nome: supportTenant?.name || '',
          context_label: contextLabel,
          practice_label: contextLabel,
          notes: contextLabel,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.description || payload?.error || 'Richiesta assistenza non completata.')
      }
      if (payload.customer_entry && payload.join_url) {
        if (openSupportRoom(String(payload.join_url))) setSupportOpening(false)
        return
      }
      if (payload.operator_url) {
        if (openSupportRoom(String(payload.operator_url))) setSupportOpening(false)
        return
      }
      throw new Error('Link assistenza non ricevuto.')
    } catch (error) {
      setSupportError(error instanceof Error ? error.message : 'Assistenza non avviata.')
      setSupportOpening(false)
    }
  }

  return (
    <IusTopBar className="iu-topbar-op">
      <button className="iu-icon iu-menu-mobile" type="button" onClick={onOpenMenu} aria-label="Apri menu">
        <PanelLeftOpen size={18} />
      </button>
      <TopBarSearch />
      {voiceAssistantReady ? (
        <Suspense fallback={<div className="iu-voice-assistant__fallback" aria-hidden="true" />}>
          <StudioVoiceAssistant activePath={activePath} />
        </Suspense>
      ) : (
        <div className="iu-voice-assistant__fallback" aria-hidden="true" />
      )}
      {supportEnabled ? (
        <div className="iu-support-request-wrap">
          <button
            className="iu-new iu-support-request"
            type="button"
            onClick={requestSupport}
            disabled={supportOpening}
            aria-busy={supportOpening}
            aria-label="Richiedi assistenza remota"
            title="Richiedi assistenza remota"
          >
            <Headphones size={16} />
            <span>{supportOpening ? 'Apro assistenza...' : 'Assistenza remota'}</span>
          </button>
          {supportError ? <div className="iu-support-request-error" role="alert">{supportError}</div> : null}
        </div>
      ) : null}
      <TopBarMobileMenu onSelect={panel => setOpenPanels(current => new Set(current).add(panel))} onSupport={supportEnabled ? () => { void requestSupport() } : undefined} supportOpening={supportOpening} supportError={supportError}/>
      <div className="iu-topbar__actions iu-topbar-op__actions">
        <Suspense fallback={null}><DiscordanzeAccesso sessionKey={`${bootstrap?.tenant?.slug || ''}:${bootstrap?.user?.username || ''}`} /></Suspense>
        <TopBarTimeTracker
          open={openPanels.has('timer')}
          onToggle={() => togglePanel('timer')}
          onClose={() => closePanel('timer')}
          context={context}
          icon={<Clock3 size={18} />}
        />
        <TopBarTodayMenu
          open={openPanels.has('today')}
          onToggle={() => togglePanel('today')}
          onClose={() => closePanel('today')}
          label={todayLabel()}
          icon={<CalendarClock size={16} />}
        />
        <TopBarDeadlines
          open={openPanels.has('deadlines')}
          onToggle={() => togglePanel('deadlines')}
          onClose={() => closePanel('deadlines')}
          icon={<TriangleAlert size={18} />}
        />
        <TopBarRecentItems
          open={openPanels.has('recent')}
          onToggle={() => togglePanel('recent')}
          onClose={() => closePanel('recent')}
          icon={<FolderClock size={18} />}
        />
        <TopBarNotifications
          open={openPanels.has('notifications')}
          onToggle={() => togglePanel('notifications')}
          onClose={() => closePanel('notifications')}
          icon={<Bell size={18} />}
        />
        <a className="iu-icon" href="/impostazioni" aria-label="Impostazioni" title="Impostazioni">
          <Settings2 size={18} />
        </a>
        <TopBarCreateMenu
          context={context}
          open={openPanels.has('create')}
          onToggle={() => togglePanel('create')}
          onClose={() => closePanel('create')}
          icon={<Plus size={16} />}
        />
      </div>
    </IusTopBar>
  )
}
