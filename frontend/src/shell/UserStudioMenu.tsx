import { UserRound } from 'lucide-react'
import './shell.css'

export function UserStudioMenu({ label = 'Profilo studio' }: { label?: string }) {
  return (
    <a className="iu-shell-nav-link" href="/profilo" aria-label={label}>
      <UserRound size={17} aria-hidden="true" />
      <span>{label}</span>
    </a>
  )
}
