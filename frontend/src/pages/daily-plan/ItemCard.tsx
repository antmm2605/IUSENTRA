import { AlertTriangle, CalendarClock, FolderOpen, ShieldAlert } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { AttivitaPiano } from './types'

const prioritaVariant: Record<string, 'destructive' | 'default' | 'secondary' | 'outline'> = {
  P0: 'destructive',
  P1: 'default',
  P2: 'secondary',
  P3: 'outline',
}

const prioritaLabel: Record<string, string> = {
  P0: 'Immediata',
  P1: 'Entro oggi',
  P2: 'Questa settimana',
  P3: 'Organizzativa',
}

const statoLabel: Record<string, string> = {
  proposed: 'Proposta',
  needs_review: 'Da confermare',
  accepted: 'Accettata',
  in_progress: 'In corso',
  completed: 'Completata',
  delegated: 'Delegata',
  snoozed: 'Rinviata',
  rejected: 'Rifiutata',
  obsolete: 'Superata',
}

type Props = {
  item: AttivitaPiano
  onOpenDetail: (item: AttivitaPiano) => void
  busy?: boolean
  onAzione?: (item: AttivitaPiano, action: string) => void
}

export function ItemCard({ item, onOpenDetail, busy, onAzione }: Props) {
  const chiusa = item.stato === 'completed' || item.stato === 'rejected'
  return (
    <div
      className={`rounded-md border px-3 py-2 transition hover:bg-muted/60 ${chiusa ? 'opacity-60' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={prioritaVariant[item.priorita] || 'outline'}>
          {item.priorita} · {prioritaLabel[item.priorita] || item.priorita}
        </Badge>
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
        <Badge variant="outline">{statoLabel[item.stato] || item.stato}</Badge>
        {item.scadenza_label ? (
          <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
            <CalendarClock size={13} aria-hidden="true" /> {item.scadenza_label}
          </span>
        ) : null}
      </div>
      <button
        type="button"
        className="mt-1 block w-full text-left"
        onClick={() => onOpenDetail(item)}
      >
        <strong className="text-sm">{item.titolo}</strong>
        {item.motivo ? (
          <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{item.motivo}</p>
        ) : null}
      </button>
      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        {item.fascicolo ? (
          <span className="flex items-center gap-1">
            <FolderOpen size={13} aria-hidden="true" /> {item.fascicolo}
          </span>
        ) : null}
        {item.cliente ? <span>{item.cliente}</span> : null}
        {item.assegnato_label ? <span>Assegnata a {item.assegnato_label}</span> : null}
        {item.fascia_proposta ? (
          <span>Fascia proposta {item.fascia_proposta.slice(11, 16)}</span>
        ) : null}
        <span>Affidabilità {Math.round(item.affidabilita * 100)}%</span>
        <span>{item.evidenze} {item.evidenze === 1 ? 'fonte' : 'fonti'}</span>
        <span className="ml-auto flex gap-1.5">
          {item.apri ? (
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
