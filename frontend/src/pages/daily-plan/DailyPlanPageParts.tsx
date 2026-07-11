import type { LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { IusSectionHeader } from '@/components/iusentra'
import { ItemCard } from './ItemCard'
import type { AttivitaPiano, PianoGiornoPayload } from './types'

const fonteLabel: Record<string, string> = {
  pec: 'PEC',
  scadenziario: 'Scadenze',
  agenda: 'Agenda',
  case_presidio: 'Fascicoli',
  economic: 'Economia',
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
        >
          {fonteLabel[fonte.source_type] || fonte.source_type}:{' '}
          {fonte.status === 'complete'
            ? 'aggiornata'
            : fonte.status === 'stale'
              ? 'da aggiornare'
              : 'non disponibile'}
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
      <IusSectionHeader title={title} icon={icon} sequence={false} />
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
