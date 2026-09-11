import {
  AlertTriangle,
  CalendarClock,
  Clock3,
  FileCheck2,
  FileSearch,
  FolderOpen,
  ShieldAlert,
  Timer,
  UserRound,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatTimeIt } from '@/formatting'
import { statoTermine } from './termine'
import {
  dailyPlanActionKindLabel,
  dailyPlanPriorityLabel,
  dailyPlanStatusLabel,
  type AttivitaPiano,
} from './types'

const prioritaVariant: Record<string, 'destructive' | 'default' | 'secondary' | 'outline'> = {
  P0: 'destructive',
  P1: 'default',
  P2: 'secondary',
  P3: 'outline',
}

type Props = {
  item: AttivitaPiano
  onOpenDetail: (item: AttivitaPiano) => void
  busy?: boolean
  onAzione?: (item: AttivitaPiano, action: string) => void
  /** Apre la fonte dell'attività sopra la pagina, non l'intero fascicolo. */
  onOpenSource?: (item: AttivitaPiano) => void
  dataPiano?: string
}

function programmazioneLabel(item: AttivitaPiano): string {
  const ora = formatTimeIt(item.fascia_proposta, '')
  const durata = item.minuti_stimati ? `${item.minuti_stimati} min` : ''
  if (ora && durata) return `${ora} · ${durata}`
  if (ora) return ora
  return durata
}

export function ItemCard({ item, onOpenDetail, busy, onAzione, onOpenSource, dataPiano = '' }: Props) {
  const chiusa = item.stato === 'completed' || item.stato === 'rejected'
  const programmazione = programmazioneLabel(item)
  const fonteLabel = item.evidenze === 1 ? 'fonte' : 'fonti'
  const termine = chiusa ? null : statoTermine(item.scadenza, dataPiano)

  return (
    <div
      className={`rounded-md border px-3 py-2.5 transition-colors hover:bg-muted/60 ${chiusa ? 'opacity-60' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={prioritaVariant[item.priorita] || 'outline'}>
          {item.priorita} · {dailyPlanPriorityLabel[item.priorita] || item.priorita}
        </Badge>
        {item.tipo_azione ? (
          <Badge variant="outline">
            {dailyPlanActionKindLabel[item.tipo_azione] || 'Attività operativa'}
          </Badge>
        ) : null}
        {item.perentorio ? (
          <Badge variant="destructive" className="gap-1">
            <ShieldAlert size={12} aria-hidden="true" /> Perentorio
          </Badge>
        ) : null}
        {item.bloccante && !item.perentorio ? (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle size={12} aria-hidden="true" /> Bloccante
          </Badge>
        ) : null}
        {item.da_rivedere ? <Badge variant="outline">Da confermare</Badge> : null}
        <Badge variant="outline">{dailyPlanStatusLabel[item.stato] || item.stato}</Badge>
        {item.scadenza_label ? (
          <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
            <CalendarClock size={13} aria-hidden="true" /> Termine {item.scadenza_label}
            {termine ? (
              <span className={termine.tono === 'neutral' ? '' : termine.tono === 'danger' ? 'font-medium text-destructive' : 'font-medium text-amber-700 dark:text-amber-300'}>
                · {termine.label}
              </span>
            ) : null}
          </span>
        ) : null}
      </div>

      <button
        type="button"
        className="mt-1.5 block w-full rounded-sm text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        onClick={() => onOpenDetail(item)}
        aria-label={`Apri il dettaglio di ${item.titolo}`}
      >
        <strong className="text-sm">{item.titolo}</strong>
        {item.motivo ? (
          <p className="mt-0.5 line-clamp-3 text-sm leading-5 text-muted-foreground">{item.motivo}</p>
        ) : null}
      </button>

      <div className="mt-2 grid gap-x-4 gap-y-1.5 border-t pt-2 text-xs text-muted-foreground sm:grid-cols-2 xl:grid-cols-3">
        {item.fascicolo ? (
          <span className="flex min-w-0 items-center gap-1">
            <FolderOpen size={13} aria-hidden="true" />
            <span className="font-medium text-foreground">Fascicolo</span>
            <span className="truncate">{item.fascicolo}</span>
          </span>
        ) : null}
        {item.cliente ? (
          <span className="min-w-0 truncate">
            <span className="font-medium text-foreground">Cliente</span> {item.cliente}
          </span>
        ) : null}
        {item.assegnato_label ? (
          <span className="flex min-w-0 items-center gap-1">
            <UserRound size={13} aria-hidden="true" />
            <span className="font-medium text-foreground">Assegnata a</span>
            <span className="truncate">{item.assegnato_label}</span>
          </span>
        ) : null}
        {programmazione ? (
          <span className="flex items-center gap-1">
            {item.fascia_proposta ? <Clock3 size={13} aria-hidden="true" /> : <Timer size={13} aria-hidden="true" />}
            <span className="font-medium text-foreground">Pianificazione</span> {programmazione}
          </span>
        ) : null}
        <span className="flex min-w-0 items-center gap-1">
          <FileCheck2 size={13} aria-hidden="true" />
          <span className="font-medium text-foreground">Fonti</span>
          <span className="truncate" title={item.fonte_label || undefined}>
            {item.fonte_label || `${item.evidenze} ${fonteLabel}`}
          </span>
        </span>
        <span>
          <span className="font-medium text-foreground">Attendibilità</span> {Math.round(item.affidabilita * 100)}%
        </span>
        <span className="flex flex-wrap gap-1.5 sm:col-span-2 sm:justify-self-end xl:col-span-1">
          {onOpenSource ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onOpenSource(item)}
              aria-label={`Apri la fonte di ${item.titolo}`}
            >
              <FileSearch aria-hidden="true" /> Apri
            </Button>
          ) : item.apri ? (
            <Button asChild size="sm" variant="outline">
              <a href={item.apri}>Apri</a>
            </Button>
          ) : null}
          {!chiusa && onAzione && item.azioni.includes('complete') ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() => onAzione(item, 'complete')}
            >
              Già gestita
            </Button>
          ) : null}
        </span>
      </div>
    </div>
  )
}
