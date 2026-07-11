import { useEffect, useState } from 'react'
import { CalendarPlus, CheckCircle2, ClipboardList, Clock3, Mail, UserRound, XCircle } from 'lucide-react'
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
import { fetchDettaglioAttivita } from './api'
import type { AttivitaDettaglio, AttivitaPiano } from './types'

const fonteLabel: Record<string, string> = {
  pec: 'Presidio PEC',
  scadenziario: 'Scadenziario',
  agenda: 'Agenda',
  case_presidio: 'Presidio fascicolo',
  economic: 'Presidio economico',
  deposit: 'Depositi telematici',
}

type Props = {
  item: AttivitaPiano | null
  writeProposalsEnabled: boolean
  onClose: () => void
  onAzione: (item: AttivitaPiano, action: string, params?: Record<string, unknown>) => void
  busy: boolean
  esitoMessaggio: string
}

export function ItemDetailPanel({ item, writeProposalsEnabled, onClose, onAzione, busy, esitoMessaggio }: Props) {
  const [dettaglio, setDettaglio] = useState<AttivitaDettaglio | null>(null)
  const [motivoRifiuto, setMotivoRifiuto] = useState('')

  useEffect(() => {
    setDettaglio(null)
    setMotivoRifiuto('')
    if (!item) return
    const controller = new AbortController()
    fetchDettaglioAttivita(item.id, controller.signal).then((data) => {
      if (data.ok && data.attivita) setDettaglio(data.attivita)
    })
    return () => controller.abort()
  }, [item])

  if (!item) return null
  const chiusa = item.stato === 'completed' || item.stato === 'rejected'
  const azioni = new Set(item.azioni)

  return (
    <Sheet open={Boolean(item)} onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <SheetContent side="right" className="flex w-full flex-col gap-3 overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="pr-6 text-left">{item.titolo}</SheetTitle>
          <SheetDescription className="text-left">
            {item.fascicolo ? `Fascicolo ${item.fascicolo}` : 'Senza fascicolo collegato'}
            {item.cliente ? ` · ${item.cliente}` : ''}
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-wrap gap-1.5">
          <Badge variant={item.priorita === 'P0' ? 'destructive' : 'secondary'}>{item.priorita}</Badge>
          {item.perentorio ? <Badge variant="destructive">Termine perentorio</Badge> : null}
          {item.bloccante ? <Badge variant="destructive">Bloccante</Badge> : null}
          {item.da_rivedere ? <Badge variant="outline">Richiede la tua conferma</Badge> : null}
          <Badge variant="outline">Affidabilità {Math.round(item.affidabilita * 100)}%</Badge>
        </div>

        <section className="grid gap-1 text-sm">
          <h3 className="font-semibold">Perché è in piano</h3>
          <p className="text-muted-foreground">{dettaglio?.spiegazione_priorita || item.motivo}</p>
          {item.scadenza_label ? (
            <p className="flex items-center gap-1 text-muted-foreground">
              <Clock3 size={14} aria-hidden="true" /> Entro il {item.scadenza_label}
            </p>
          ) : null}
        </section>

        <Separator />

        <section className="grid gap-1.5 text-sm">
          <h3 className="font-semibold">Fonti che lo provano</h3>
          {dettaglio ? (
            dettaglio.evidenze_dettaglio.length ? (
              <ul className="grid gap-1.5">
                {dettaglio.evidenze_dettaglio.map((ev, idx) => (
                  <li key={`${ev.source_type}-${ev.source_id}-${idx}`} className="rounded-md border px-2.5 py-1.5">
                    <span className="font-medium">{fonteLabel[ev.source_type] || ev.source_type}</span>
                    {ev.label ? <span className="text-muted-foreground"> — {ev.label}</span> : null}
                    {ev.href ? (
                      <a className="ml-2 underline" href={ev.href}>Apri</a>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground">Nessuna evidenza registrata.</p>
            )
          ) : (
            <p className="text-muted-foreground">Caricamento evidenze…</p>
          )}
        </section>

        {esitoMessaggio ? (
          <p className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
            {esitoMessaggio}
          </p>
        ) : null}

        {!chiusa ? (
          <>
            <Separator />
            <section className="grid gap-2">
              <h3 className="text-sm font-semibold">Azioni</h3>
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
