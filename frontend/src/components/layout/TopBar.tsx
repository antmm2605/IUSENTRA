import { Bell, CalendarClock, Clock3, FolderClock, Headphones, PanelLeftOpen, Plus, Settings2, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { TopBarCreateMenu } from './TopBarCreateMenu'
import { TopBarDeadlines } from './TopBarDeadlines'
import { TopBarNotifications } from './TopBarNotifications'
import { TopBarRecentItems } from './TopBarRecentItems'
import { TopBarSearch } from './TopBarSearch'
import { TopBarTimeTracker } from './TopBarTimeTracker'
import { TopBarTodayMenu } from './TopBarTodayMenu'
import { IusTopBar } from '../iusentra'
import type { TopbarCreateContext } from '../../types/topbar'

type PanelName = 'create' | 'today' | 'notifications' | 'deadlines' | 'recent' | 'timer' | null
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

function todayLabel() {
  return new Intl.DateTimeFormat('it-IT', {
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
  const [openPanel, setOpenPanel] = useState<PanelName>(null)
  const [supportOpening, setSupportOpening] = useState(false)
  const [supportError, setSupportError] = useState('')
  const context = useMemo(() => currentContext(activePath), [activePath])
  const togglePanel = (panel: Exclude<PanelName, null>) => setOpenPanel((current) => (current === panel ? null : panel))
  const closePanel = () => setOpenPanel(null)
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
            <span>{supportOpening ? 'Apro assistenza...' : 'Assistenza'}</span>
          </button>
          {supportError ? <div className="iu-support-request-error" role="alert">{supportError}</div> : null}
        </div>
      ) : null}
      <div className="iu-topbar__actions iu-topbar-op__actions">
        <TopBarTimeTracker
          open={openPanel === 'timer'}
          onToggle={() => togglePanel('timer')}
          onClose={closePanel}
          context={context}
          icon={<Clock3 size={18} />}
        />
        <TopBarTodayMenu
          open={openPanel === 'today'}
          onToggle={() => togglePanel('today')}
          onClose={closePanel}
          label={todayLabel()}
          icon={<CalendarClock size={16} />}
        />
        <TopBarDeadlines
          open={openPanel === 'deadlines'}
          onToggle={() => togglePanel('deadlines')}
          onClose={closePanel}
          icon={<TriangleAlert size={18} />}
        />
        <TopBarRecentItems
          open={openPanel === 'recent'}
          onToggle={() => togglePanel('recent')}
          onClose={closePanel}
          icon={<FolderClock size={18} />}
        />
        <TopBarNotifications
          open={openPanel === 'notifications'}
          onToggle={() => togglePanel('notifications')}
          onClose={closePanel}
          icon={<Bell size={18} />}
        />
        <a className="iu-icon" href="/impostazioni" aria-label="Impostazioni" title="Impostazioni">
          <Settings2 size={18} />
        </a>
        <TopBarCreateMenu
          context={context}
          open={openPanel === 'create'}
          onToggle={() => togglePanel('create')}
          onClose={closePanel}
          icon={<Plus size={16} />}
        />
      </div>
    </IusTopBar>
  )
}
