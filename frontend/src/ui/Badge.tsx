import type { ReactNode } from 'react'
import './ui.css'

export type BadgeTone = 'primary' | 'neutral' | 'danger' | 'success' | 'warning' | 'info'

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: BadgeTone
}) {
  return <span className={`iu-badge iu-badge--${tone}`}>{children}</span>
}
