import {
  AlertTriangle,
  CalendarClock,
  CalendarPlus,
  CheckCircle2,
  Clock3,
  FolderOpen,
  Mail,
  PauseCircle,
  UserRound,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { avvisoTermineAnomalo, statoTermine } from './termine'
import {
  dailyPlanActionKindLabel,
  dailyPlanPriorityLabel,
  dailyPlanStatusLabel,
  type AttivitaDettaglio,
  type AttivitaPiano,
} from './types'

type Props = {
  item: AttivitaPiano
  dettaglio: AttivitaDettaglio | null
  dataPiano: string
  fascicoloHref: string
  writeProposalsEnabled: boolean
  busy: boolean
  esitoMessaggio: string
  onAzione: (action: string, params?: Record<string, unknown>) => void
  onOpenDetail: () => void
}

const tonoTermine: Record<string, string> = {
  danger: 'border-destructive/40 bg-destructive/10 text-destructive',
  warning: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200',
  neutral: 'border-border bg-muted/40 text-foreground',
}

export function SourceWorkspacePanel({
  item,
  dettaglio,
  dataPiano,
  fascicoloHref,
  writeProposalsEnabled,
  busy,
  esitoMessaggio,
  onAzione,
  onOpenDetail,
}: Props) {
  const operativo = dettaglio || item
  const azioni = new Set(operativo.azioni)
  const chiusa = operativo.stato === 'completed' || operativo.stato === 'rejected'
  const termine = statoTermine(operativo.scadenza, dataPiano)
  const perche = dettaglio?.spiegazione_priorita || operativo.motivo

  return (
    <aside className="grid max-h-[46vh] content-start gap-3 overflow-y-auto border-t bg-background p-3 text-sm lg:max-h-none lg:border-t-0 lg:border-l" aria-label="Pannello operativo dell’attività">
      <div className="flex flex-wrap gap-1.5">
        <Badge variant={operativo.priorita === 'P0' ? 'destructive' : 'secondary'}>
          {operativo.priorita} · {dailyPlanPriorityLabel[operativo.priorita]}
        </Badge>
        {operativo.tipo_azione ? (
          <Badge variant="outline">{dailyPlanActionKindLabel[operativo.tipo_azione] || 'Attività operativa'}</Badge>
        ) : null}
        {operativo.perentorio ? <Badge variant="destructive">Perentorio</Badge> : null}
        <Badge variant="outline">{dailyPlanStatusLabel[operativo.stato] || operativo.stato}</Badge>
      </div>

      {operativo.scadenza_label ? (
        <div className={`grid gap-1 rounded-md border px-3 py-2 ${tonoTermine[termine?.tono || 'neutral']}`}>
          <span className="flex items-center gap-1.5 font-semibold">
            <CalendarClock size={15} aria-hidden="true" /> Termine {operativo.scadenza_label}
          </span>
          {termine ? <span className="text-xs font-medium">{termine.label}</span> : null}
          {termine?.anomalo ? (
            <span className="flex items-start gap-1.5 text-xs leading-5">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" aria-hidden="true" /> {avvisoTermineAnomalo}
            </span>
          ) : null}
        </div>
      ) : null}

      {perche ? (
        <section className="grid gap-1">
          <h3 className="font-semibold">Perché è in piano</h3>
          <p className="leading-6 text-muted-foreground">{perche}</p>
        </section>
      ) : null}

      <dl className="grid gap-2 border-y py-2">
        {operativo.fascicolo ? (
          <div className="flex items-center justify-between gap-2">
            <dt className="flex items-center gap-1 text-xs text-muted-foreground">
              <FolderOpen size={13} aria-hidden="true" /> Fascicolo
            </dt>
            <dd className="text-right font-medium">{operativo.fascicolo}</dd>
          </div>
        ) : null}
        {operativo.cliente ? (
          <div className="flex items-center justify-between gap-2">
            <dt className="text-xs text-muted-foreground">Cliente</dt>
            <dd className="text-right font-medium">{operativo.cliente}</dd>
          </div>
        ) : null}
        {operativo.assegnato_label ? (
          <div className="flex items-center justify-between gap-2">
            <dt className="flex items-center gap-1 text-xs text-muted-foreground">
              <UserRound size={13} aria-hidden="true" /> Assegnata a
            </dt>
            <dd className="text-right font-medium">{operativo.assegnato_label}</dd>
          </div>
        ) : null}
      </dl>

      {esitoMessaggio ? (
        <p role="status" className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
          {esitoMessaggio}
        </p>
      ) : null}

      {!chiusa ? (
        <section className="grid gap-2">
          <h3 className="font-semibold">Dopo aver letto la fonte</h3>
          <div className="grid grid-cols-2 gap-1.5">
            {azioni.has('complete') ? (
              <Button size="sm" disabled={busy} onClick={() => onAzione('complete')}>
                <CheckCircle2 aria-hidden="true" /> Già gestita
              </Button>
            ) : null}
            {azioni.has('snooze') ? (
              <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione('snooze')}>
                <PauseCircle aria-hidden="true" /> Rinvia
              </Button>
            ) : null}
          </div>
          {writeProposalsEnabled ? (
            <div className="grid gap-1.5">
              {azioni.has('create_deadline') ? (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione('create_deadline')}>
                  <Clock3 aria-hidden="true" /> Proponi scadenza
                </Button>
              ) : null}
              {azioni.has('create_calendar_proposal') ? (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione('create_calendar_proposal')}>
                  <CalendarPlus aria-hidden="true" /> Proponi in agenda
                </Button>
              ) : null}
              {azioni.has('create_pec_draft') ? (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione('create_pec_draft')}>
                  <Mail aria-hidden="true" /> Prepara bozza PEC
                </Button>
              ) : null}
              <p className="text-xs text-muted-foreground">
                Le proposte finiscono nella coda approvazioni: nulla viene registrato senza revisione.
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid gap-1.5">
        <Button type="button" size="sm" variant="ghost" className="justify-start" onClick={onOpenDetail}>
          Delega, rifiuta o vedi tutte le evidenze
        </Button>
        {fascicoloHref ? (
          <Button asChild size="sm" variant="ghost" className="justify-start">
            <a href={fascicoloHref}>
              <FolderOpen aria-hidden="true" /> Apri il fascicolo completo
            </a>
          </Button>
        ) : null}
      </div>
    </aside>
  )
}
