import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function IusTopBar({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <header className={cn('iu-topbar ius-topbar', className)}>{children}</header>
}
