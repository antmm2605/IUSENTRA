import { Bell } from 'lucide-react'
import './shell.css'

export function NotificationCenter({ count = 0 }: { count?: number }) {
  return (
    <a className="iu-shell-nav-link" href="/notifiche" aria-label={count ? `Notifiche: ${count}` : 'Notifiche'}>
      <Bell size={17} aria-hidden="true" />
      <span>{count ? `${count} notifiche` : 'Notifiche'}</span>
    </a>
  )
}
