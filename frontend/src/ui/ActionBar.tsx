import type { ReactNode } from 'react'
import './ui.css'

export function ActionBar({ children }: { children: ReactNode }) {
  return <div className="iu-action-bar">{children}</div>
}
