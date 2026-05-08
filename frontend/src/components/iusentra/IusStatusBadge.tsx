import type { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { iusToneClass, type IusTone } from '@/design/iusentraTokens'

function toneFromStatus(status: string): IusTone {
  if (/scad|errore|rifiut|fallit|blocc/i.test(status)) return 'danger'
  if (/attesa|verifica|bozza|warning|controll/i.test(status)) return 'warning'
  if (/chius|pagat|accett|complet|healthy|ok/i.test(status)) return 'success'
  if (/pec|pct|deposit|telematic/i.test(status)) return 'info'
  return 'neutral'
}

export function IusStatusBadge({
  children,
  status,
  tone,
  className,
}: {
  children?: ReactNode
  status?: string
  tone?: IusTone
  className?: string
}) {
  const resolvedTone = tone ?? toneFromStatus(status ?? String(children ?? ''))
  return (
    <Badge variant="outline" className={cn('ius-status-badge', iusToneClass[resolvedTone], className)}>
      {children ?? status}
    </Badge>
  )
}
