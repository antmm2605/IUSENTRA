import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function IusAppSidebar({
  children,
  collapsed = false,
  className,
}: {
  children: ReactNode
  collapsed?: boolean
  className?: string
}) {
  return (
    <aside className={cn('iu-sidebar ius-app-sidebar', collapsed && 'iu-sidebar--collapsed', className)}>
      {children}
    </aside>
  )
}
