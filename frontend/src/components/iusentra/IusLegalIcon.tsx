import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { iusLegalIcons, iusToneClass, type IusLegalArea, type IusTone } from '@/design/iusentraTokens'

export function IusLegalIcon({
  area,
  icon: Icon,
  tone = 'primary',
  className,
  decorative = true,
}: {
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  className?: string
  decorative?: boolean
}) {
  const ResolvedIcon = Icon ?? (area ? iusLegalIcons[area] : iusLegalIcons.fascicoli)
  return (
    <span className={cn('ius-legal-icon', iusToneClass[tone], className)} aria-hidden={decorative}>
      <ResolvedIcon />
    </span>
  )
}
