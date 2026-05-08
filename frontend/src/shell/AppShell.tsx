import type { ReactNode } from 'react'
import { LexFloatingButton } from './LexFloatingButton'
import { MobileNav } from './MobileNav'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import './shell.css'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="iu-app-shell">
      <Sidebar />
      <div className="iu-app-shell__main">
        <Topbar />
        <main className="iu-app-shell__workspace">{children}</main>
      </div>
      <MobileNav />
      <LexFloatingButton />
    </div>
  )
}
