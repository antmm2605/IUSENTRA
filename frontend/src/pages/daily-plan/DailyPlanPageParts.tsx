import { CalendarDays, Inbox, type LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { IusSectionHeader } from '@/components/iusentra'
import { formatTimeIt } from '@/formatting'
import { ItemCard } from './ItemCard'
import {
  dailyPlanSourceLabel,
  type AgendaOggiEntry,
  type AttivitaPiano,
  type PianoGiornoPayload,
} from './types'

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
  onOpenSource,
  dataPiano,
}: {
  title: string
  icon: LucideIcon
  items: AttivitaPiano[]
  emptyText: string
  onOpenDetail: (item: AttivitaPiano) => void
  onAction: (item: AttivitaPiano, action: string) => void
  busyId: string
  onOpenSource: (item: AttivitaPiano, lista: AttivitaPiano[]) => void
  dataPiano: string
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
              onOpenSource={(row) => onOpenSource(row, items)}
              dataPiano={dataPiano}
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

export function AgendaOggiSection({ eventi }: { eventi: AgendaOggiEntry[] }) {
  return (
    <section className="grid gap-2">
      <IusSectionHeader title="Agenda del giorno" icon={CalendarDays} sequence={false} />
      {eventi.length ? (
        <div className="grid gap-1.5">
          {eventi.map((evento) => (
            <div key={evento.id} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
              <Badge variant={evento.tipo.includes('UDIENZA') ? 'destructive' : 'secondary'}>
                {evento.tipo.includes('UDIENZA') ? 'Udienza' : 'Appuntamento'}
              </Badge>
              <strong>{formatTimeIt(evento.data_ora, 'Orario non indicato')}</strong>
              <span>{evento.titolo}</span>
              <span className="text-muted-foreground">
                {evento.durata_minuti} min{evento.luogo ? ` · ${evento.luogo}` : ''}
                {evento.avvocato ? ` · ${evento.avvocato}` : ''}
                {evento.procedimento ? ` · Proc. ${evento.procedimento}` : ''}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
          Nessun impegno fisso in agenda per questa data.
        </p>
      )}
    </section>
  )
}

export function BacklogSection({
  aperto,
  items,
  restanti,
  totalePiano,
  onApri,
  onAltri,
  onOpenDetail,
  onAction,
  busyId,
  onOpenSource,
  dataPiano,
}: {
  aperto: boolean
  items: AttivitaPiano[]
  restanti: number
  totalePiano: number
  onApri: () => void
  onAltri: () => void
  onOpenDetail: (item: AttivitaPiano) => void
  onAction: (item: AttivitaPiano, action: string) => void
  busyId: string
  onOpenSource: (item: AttivitaPiano, lista: AttivitaPiano[]) => void
  dataPiano: string
}) {
  return (
    <section className="grid gap-2">
      <IusSectionHeader title="Backlog" icon={Inbox} sequence={false} />
      {aperto ? (
        <>
          {items.length ? (
            <div className="grid gap-2">
              {items.map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  onOpenDetail={onOpenDetail}
                  onAzione={onAction}
                  busy={busyId === item.id}
                  onOpenSource={(row) => onOpenSource(row, items)}
                  dataPiano={dataPiano}
                />
              ))}
            </div>
          ) : (
            <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
              Il backlog è vuoto: tutto ciò che conta è già nel piano del giorno.
            </p>
          )}
          {restanti > 0 ? (
            <Button type="button" variant="outline" onClick={onAltri}>
              Carica altri ({restanti} rimanenti)
            </Button>
          ) : null}
        </>
      ) : (
        <Button type="button" variant="outline" onClick={onApri}>
          Mostra il backlog{totalePiano ? ` (${totalePiano})` : ''}
        </Button>
      )}
    </section>
  )
}
