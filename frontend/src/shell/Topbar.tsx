import type { ReactNode } from 'react'
import { CommandPalette } from './CommandPalette'
import { NotificationCenter } from './NotificationCenter'
import { UserStudioMenu } from './UserStudioMenu'
import './shell.css'

export function Topbar({ children }: { children?: ReactNode }) {
  return (
    <header className="iu-shell-topbar">
      <CommandPalette />
      <div className="iu-shell-topbar__tools">
        {children}
        <NotificationCenter />
        <UserStudioMenu />
      </div>
    </header>
  )
}
