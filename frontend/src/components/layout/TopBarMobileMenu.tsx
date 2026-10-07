import { useState } from 'react'
import { Bell, CalendarClock, FolderClock, Headphones, MoreHorizontal, Plus, Settings2, TriangleAlert } from 'lucide-react'
import { OperationalModal } from '../OperationalModal'
import './TopBarMobileMenu.css'

type Command = 'today' | 'deadlines' | 'recent' | 'notifications' | 'create'
const commands = [
  { key: 'today', label: 'Oggi', icon: CalendarClock },
  { key: 'deadlines', label: 'Scadenze rapide', icon: TriangleAlert },
  { key: 'notifications', label: 'Notifiche operative', icon: Bell },
  { key: 'recent', label: 'Recenti e ricerche', icon: FolderClock },
  { key: 'create', label: 'Crea nuovo elemento', icon: Plus },
] satisfies { key: Command; label: string; icon: typeof Bell }[]

export function TopBarMobileMenu({ onSelect, onSupport, supportOpening, supportError }: {
  onSelect: (command: Command) => void
  onSupport?: () => void
  supportOpening: boolean
  supportError: string
}) {
  const [open, setOpen] = useState(false)
  return <>
    <button className="iu-icon iu-topbar-mobile-menu" type="button" aria-label="Altri comandi studio" title="Altri comandi studio" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}><MoreHorizontal size={18}/></button>
    <OperationalModal open={open} ariaLabel="Comandi studio" eyebrow="Accesso rapido" title="Comandi studio" boxClassName="iu-mobile-commands-window" onClose={() => setOpen(false)}>
      <nav className="iu-mobile-commands" aria-label="Comandi studio">
        {commands.map(({ key, label, icon: Icon }) => <button className="iu-button" key={key} type="button" onClick={() => { setOpen(false); onSelect(key) }}><Icon size={18}/><span>{label}</span></button>)}
        <a className="iu-button" href="/impostazioni" onClick={() => setOpen(false)}><Settings2 size={18}/><span>Impostazioni</span></a>
        {onSupport && <button className="iu-button" type="button" disabled={supportOpening} aria-busy={supportOpening} onClick={onSupport}><Headphones size={18}/><span>{supportOpening ? 'Apro assistenza…' : 'Assistenza remota'}</span></button>}
      </nav>
      {supportError && <p role="alert">{supportError}</p>}
    </OperationalModal>
  </>
}
