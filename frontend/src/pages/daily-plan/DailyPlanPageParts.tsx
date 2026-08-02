import type { LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { IusSectionHeader } from '@/components/iusentra'
import { ItemCard } from './ItemCard'
import { dailyPlanSourceLabel, type AttivitaPiano, type PianoGiornoPayload } from './types'

const coverageStatusLabel: Record<string, string> = {
  complete: 'aggiornata',
  stale: 'da aggiornare',
  unavailable: 'non disponibile',
  never: 'non ancora rilevata',
}

export function CoverageChips({ piano }: { piano: PianoGiornoPayload }) {
  if (!piano.copertura.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {piano.copertura.map((fonte) => (
        <Badge
          key={fonte.source_type}
          variant={
            fonte.status === 'complete'
              ? 'secondary'
              : fonte.status === 'stale'
              ? 'outline'
              : 'destructive'
          }
          title={fonte.note || undefined}
          aria-label={`${dailyPlanSourceLabel[fonte.source_type] || 'Fonte'}: ${
            coverageStatusLabel[fonte.status] || fonte.status
          }${fonte.note ? `. ${fonte.note}` : ''}`}
        >
          {dailyPlanSourceLabel[fonte.source_type] || 'Fonte'}:{' '}
          {coverageStatusLabel[fonte.status] || fonte.status}
        </Badge>
      ))}
    </div>
  )
}

export function ActivitySection({
  title,
  icon,
  items,
  emptyText,
  onOpenDetail,
  onAction,
  busyId,
}: {
  title: string
  icon: LucideIcon
  items: AttivitaPiano[]
  emptyText: string
  onOpenDetail: (item: AttivitaPiano) => void
  onAction: (item: AttivitaPiano, action: string) => void
  busyId: string
}) {
  return (
    <section className="grid gap-2">
      <IusSectionHeader
        title={title}
        icon={icon}
        sequence={false}
        actions={
          items.length ? <Badge variant="outline">{items.length} attività</Badge> : undefined
        }
      />
      {items.length ? (
        <div className="grid gap-2">
          {items.map((item) => (
            <ItemCard
              key={item.id}
              item={item}
              onOpenDetail={onOpenDetail}
              onAzione={onAction}
              busy={busyId === item.id}
            />
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
          {emptyText}
        </p>
      )}
    </section>
  )
}
