import type { ReactNode } from 'react'
import './shell.css'

export function QuickActions({ children }: { children: ReactNode }) {
  return <div className="iu-quick-actions">{children}</div>
}
