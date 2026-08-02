import { useEffect, useState } from 'react'
import {
  CalendarPlus,
  CheckCircle2,
  ClipboardList,
  Clock3,
  FileCheck2,
  FolderOpen,
  ListChecks,
  Mail,
  RefreshCw,
  Timer,
  UserRound,
  XCircle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { formatDateIt, formatDateTimeIt, formatTimeIt } from '@/formatting'
import { fetchDettaglioAttivita } from './api'
import {
  dailyPlanActionKindLabel,
  dailyPlanPriorityLabel,
  dailyPlanSourceLabel,
  dailyPlanStatusLabel,
  type AttivitaDettaglio,
  type AttivitaPiano,
} from './types'

type Props = {
  item: AttivitaPiano | null
  writeProposalsEnabled: boolean
  onClose: () => void
  onAzione: (item: AttivitaPiano, action: string, params?: Record<string, unknown>) => void
  busy: boolean
  esitoMessaggio: string
}

function programmazioneLabel(item: AttivitaPiano): string {
  const ora = formatTimeIt(item.fascia_proposta, '')
  const durata = item.minuti_stimati ? `${item.minuti_stimati} min` : ''
  if (ora && durata) return `${ora} · ${durata}`
  if (ora) return ora
  return durata
}

function evidenzaDataLabel(value: string): string {
  if (!value) return ''
  return /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? formatDateIt(value, '')
    : formatDateTimeIt(value, '')
}

export function ItemDetailPanel({ item, writeProposalsEnabled, onClose, onAzione, busy, esitoMessaggio }: Props) {
  const [dettaglio, setDettaglio] = useState<AttivitaDettaglio | null>(null)
  const [erroreDettaglio, setErroreDettaglio] = useState('')
  const [tentativoDettaglio, setTentativoDettaglio] = useState(0)
  const [motivoRifiuto, setMotivoRifiuto] = useState('')

  useEffect(() => {
    setDettaglio(null)
    setErroreDettaglio('')
    setMotivoRifiuto('')
    if (!item) return
    const controller = new AbortController()
    fetchDettaglioAttivita(item.id, controller.signal).then((data) => {
      if (data.ok && data.attivita) {
        setDettaglio(data.attivita)
        return
      }
      setErroreDettaglio('Le fonti non sono disponibili in questo momento. Riprova tra poco.')
    }).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      setErroreDettaglio('Le fonti non sono disponibili in questo momento. Riprova tra poco.')
    })
    return () => controller.abort()
  }, [item, tentativoDettaglio])

  if (!item) return null
  const itemOperativo = dettaglio || item
  const chiusa = itemOperativo.stato === 'completed' || itemOperativo.stato === 'rejected'
  const azioni = new Set(itemOperativo.azioni)
  const programmazione = programmazioneLabel(itemOperativo)
  const statoAggiornato = dettaglio ? evidenzaDataLabel(dettaglio.stato_aggiornato_il) : ''

  return (
    <Sheet open={Boolean(item)} onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <SheetContent side="right" className="flex w-full flex-col gap-3 overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="pr-6 text-left">{itemOperativo.titolo}</SheetTitle>
          <SheetDescription className="text-left">
            {itemOperativo.fascicolo ? `Fascicolo ${itemOperativo.fascicolo}` : 'Senza fascicolo collegato'}
            {itemOperativo.cliente ? ` · ${itemOperativo.cliente}` : ''}
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-wrap gap-1.5">
          <Badge variant={itemOperativo.priorita === 'P0' ? 'destructive' : 'secondary'}>
            {itemOperativo.priorita} · {dailyPlanPriorityLabel[itemOperativo.priorita]}
          </Badge>
          {itemOperativo.tipo_azione ? (
            <Badge variant="outline">
              {dailyPlanActionKindLabel[itemOperativo.tipo_azione] || 'Attività operativa'}
            </Badge>
          ) : null}
          <Badge variant="outline">{dailyPlanStatusLabel[itemOperativo.stato] || itemOperativo.stato}</Badge>
          {itemOperativo.perentorio ? <Badge variant="destructive">Termine perentorio</Badge> : null}
          {itemOperativo.bloccante ? <Badge variant="destructive">Bloccante</Badge> : null}
          {itemOperativo.da_rivedere ? <Badge variant="outline">Richiede la tua conferma</Badge> : null}
        </div>

        <section className="grid gap-1 text-sm">
          <h3 className="font-semibold">Perché è in piano</h3>
          <p className="leading-6 text-muted-foreground">
            {dettaglio?.spiegazione_priorita || itemOperativo.motivo || 'Motivazione non disponibile.'}
          </p>
          {dettaglio?.spiegazione_priorita && itemOperativo.motivo && itemOperativo.motivo !== dettaglio.spiegazione_priorita ? (
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">Presidio richiesto: </span>{itemOperativo.motivo}
            </p>
          ) : null}
        </section>

        <Separator />

        <section className="grid gap-2 text-sm">
          <h3 className="font-semibold">Contesto e pianificazione</h3>
          <dl className="grid gap-x-6 gap-y-3 border-y py-3 sm:grid-cols-2">
            <div className="grid gap-0.5">
              <dt className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                <ListChecks size={13} aria-hidden="true" /> Intervento
              </dt>
              <dd>{dailyPlanActionKindLabel[itemOperativo.tipo_azione] || 'Attività operativa'}</dd>
            </div>
            <div className="grid gap-0.5">
              <dt className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                <Clock3 size={13} aria-hidden="true" /> Termine
              </dt>
              <dd>{itemOperativo.scadenza_label || 'Nessun termine espresso'}</dd>
            </div>
            {programmazione ? (
              <div className="grid gap-0.5">
                <dt className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                  <Timer size={13} aria-hidden="true" /> Fascia proposta
                </dt>
                <dd>{programmazione}</dd>
              </div>
            ) : null}
            {itemOperativo.fascicolo ? (
              <div className="grid gap-0.5">
                <dt className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                  <FolderOpen size={13} aria-hidden="true" /> Fascicolo
                </dt>
                <dd>{itemOperativo.fascicolo}</dd>
              </div>
            ) : null}
            {itemOperativo.cliente ? (
              <div className="grid gap-0.5">
                <dt className="text-xs font-medium text-muted-foreground">Cliente</dt>
                <dd>{itemOperativo.cliente}</dd>
              </div>
            ) : null}
            {itemOperativo.assegnato_label ? (
              <div className="grid gap-0.5">
                <dt className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                  <UserRound size={13} aria-hidden="true" /> Assegnata a
                </dt>
                <dd>{itemOperativo.assegnato_label}</dd>
              </div>
            ) : null}
          </dl>
        </section>

        {dettaglio?.nota_stato || statoAggiornato ? (
          <section className="grid gap-1 text-sm">
            <h3 className="font-semibold">Stato dell’attività</h3>
            {dettaglio?.nota_stato ? <p className="text-muted-foreground">{dettaglio.nota_stato}</p> : null}
            {statoAggiornato ? (
              <p className="text-xs text-muted-foreground">Aggiornato il {statoAggiornato}</p>
            ) : null}
          </section>
        ) : null}

        <Separator />

        <section className="grid gap-1.5 text-sm">
          <h3 className="font-semibold">Fonti che lo provano</h3>
          {dettaglio ? (
            dettaglio.evidenze_dettaglio.length ? (
              <ul className="grid divide-y rounded-md border px-3">
                {dettaglio.evidenze_dettaglio.map((ev, idx) => {
                  const dataEvidenza = evidenzaDataLabel(ev.timestamp)
                  return (
                    <li key={`${ev.source_type}-${ev.source_id}-${idx}`} className="grid gap-1 py-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                        <span className="flex items-center gap-1 font-medium">
                          <FileCheck2 size={14} aria-hidden="true" />
                          {dailyPlanSourceLabel[ev.source_type] || 'Fonte'}
                        </span>
                        {ev.href ? (
                          <a className="text-sm font-medium text-primary underline underline-offset-2" href={ev.href}>
                            Apri fonte
                          </a>
                        ) : null}
                      </div>
                      {ev.label ? <p className="text-muted-foreground">{ev.label}</p> : null}
                      <p className="text-xs text-muted-foreground">
                        {dataEvidenza ? `Rilevata il ${dataEvidenza}` : 'Data non disponibile'}
                        {ev.confidence ? ` · Attendibilità ${Math.round(ev.confidence * 100)}%` : ''}
                      </p>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <p className="text-muted-foreground">Nessuna evidenza registrata.</p>
            )
          ) : erroreDettaglio ? (
            <div
              role="alert"
              className="grid justify-items-start gap-2 rounded-md border border-destructive/40 px-3 py-2 text-destructive"
            >
              <p>{erroreDettaglio}</p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setTentativoDettaglio((value) => value + 1)}
              >
                <RefreshCw aria-hidden="true" /> Riprova
              </Button>
            </div>
          ) : (
            <p className="text-muted-foreground">Caricamento evidenze…</p>
          )}
        </section>

        {esitoMessaggio ? (
          <p role="status" className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
            {esitoMessaggio}
          </p>
        ) : null}

        {!chiusa ? (
          <>
            <Separator />
            <section className="grid gap-2">
              <h3 className="text-sm font-semibold">Azioni disponibili</h3>
              <div className="flex flex-wrap gap-1.5">
                {azioni.has('accept') ? (
                  <Button size="sm" disabled={busy} onClick={() => onAzione(item, 'accept')}>
                    <CheckCircle2 aria-hidden="true" /> Accetta
                  </Button>
                ) : null}
                {azioni.has('complete') ? (
                  <Button size="sm" variant="secondary" disabled={busy} onClick={() => onAzione(item, 'complete')}>
                    Completa
                  </Button>
                ) : null}
                {azioni.has('snooze') ? (
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione(item, 'snooze')}>
                    Rinvia
                  </Button>
                ) : null}
                {azioni.has('delegate') ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      const utente = window.prompt('Utente a cui delegare (identificativo):') || ''
                      if (utente.trim()) onAzione(item, 'delegate', { user_id: utente.trim() })
                    }}
                  >
                    <UserRound aria-hidden="true" /> Delega
                  </Button>
                ) : null}
              </div>
              <div className="grid gap-1.5">
                <label className="text-xs text-muted-foreground" htmlFor="motivo-rifiuto">
                  Rifiuta con motivazione
                </label>
                <div className="flex gap-1.5">
                  <input
                    id="motivo-rifiuto"
                    className="h-8 w-full rounded-md border bg-background px-2 text-sm"
                    value={motivoRifiuto}
                    onChange={(event) => setMotivoRifiuto(event.target.value)}
                    placeholder="Perché non va fatta"
                  />
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={busy || !motivoRifiuto.trim()}
                    onClick={() => onAzione(item, 'reject', { motivo: motivoRifiuto.trim() })}
                  >
                    <XCircle aria-hidden="true" /> Rifiuta
                  </Button>
                </div>
              </div>

              <h3 className="mt-1 text-sm font-semibold">Proposte da approvare</h3>
              {writeProposalsEnabled ? (
                <div className="flex flex-wrap gap-1.5">
                  {azioni.has('create_task') ? (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione(item, 'create_task')}>
                      <ClipboardList aria-hidden="true" /> Crea attività
                    </Button>
                  ) : null}
                  {azioni.has('create_deadline') ? (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione(item, 'create_deadline')}>
                      <Clock3 aria-hidden="true" /> Crea scadenza
                    </Button>
                  ) : null}
                  {azioni.has('create_calendar_proposal') ? (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione(item, 'create_calendar_proposal')}>
                      <CalendarPlus aria-hidden="true" /> Proponi in agenda
                    </Button>
                  ) : null}
                  {azioni.has('create_pec_draft') ? (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onAzione(item, 'create_pec_draft')}>
                      <Mail aria-hidden="true" /> Prepara bozza PEC
                    </Button>
                  ) : null}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Le proposte operative sono disattivate: ogni modifica resta manuale finché lo
                  studio non le abilita.
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Le proposte non applicano nulla da sole: finiscono nella coda approvazioni e
                servono sempre una revisione e un permesso di approvazione.
              </p>
            </section>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
