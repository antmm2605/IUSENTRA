import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CalendarDays,
  Euro,
  FolderKanban,
  Inbox,
  ListTodo,
  Mail,
  RefreshCw,
  Sunrise,
  Users,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  IusEmptyState,
  IusErrorState,
  IusLoadingState,
  IusPageShell,
  IusSectionHeader,
} from '@/components/iusentra'
import { isFeatureFlagEnabledSync } from '@/lib/featureFlags'
import { ItemCard } from './ItemCard'
import { ItemDetailPanel } from './ItemDetailPanel'
import {
  DailyPlanDateControls,
  initialDailyPlanDate,
  syncDailyPlanDateUrl,
} from './DailyPlanDateControls'
import { ActivitySection, CoverageChips } from './DailyPlanPageParts'
import {
  eseguiAzione,
  fetchBacklog,
  fetchPianoGiorno,
  richiediAggiornamento,
} from './api'
import type { AttivitaPiano, PianoGiornoPayload } from './types'

export function OggiPage() {
  const [dataSelezionata, setDataSelezionata] = useState(initialDailyPlanDate)
  const [piano, setPiano] = useState<PianoGiornoPayload | null>(null)
  const [codaStudio, setCodaStudio] = useState<AttivitaPiano[]>([])
  const [loading, setLoading] = useState(true)
  const [errore, setErrore] = useState('')
  const [dettaglio, setDettaglio] = useState<AttivitaPiano | null>(null)
  const [busyId, setBusyId] = useState('')
  const [esitoAzione, setEsitoAzione] = useState('')
  const [aggiornamentoRichiesto, setAggiornamentoRichiesto] = useState(false)
  const [aggiornamentoMessaggio, setAggiornamentoMessaggio] = useState('')
  const [versioneInAttesa, setVersioneInAttesa] = useState('')
  const [generatoInAttesa, setGeneratoInAttesa] = useState('')
  const [backlog, setBacklog] = useState<AttivitaPiano[]>([])
  const [backlogCursor, setBacklogCursor] = useState('')
  const [backlogTotale, setBacklogTotale] = useState(0)
  const [backlogAperto, setBacklogAperto] = useState(false)

  const writeProposalsEnabled = isFeatureFlagEnabledSync('lex.dailyPlan.writeProposals')

  const carica = useCallback((signal?: AbortSignal) => {
    return fetchPianoGiorno(signal, { date: dataSelezionata })
      .then((data) => {
        setPiano(data)
        if (!data.ok && data.stato !== 'non_generato') {
          setErrore(data.message || 'Piano del giorno non disponibile.')
        } else {
          setErrore('')
        }
        // coda studio "Da assegnare": visibile a chi può leggerla
        return fetchPianoGiorno(signal, { user: 'studio', date: dataSelezionata }).then((studio) => {
          if (studio.ok && studio.stato === 'pronto') {
            setCodaStudio(studio.sezioni.da_assegnare)
          } else {
            setCodaStudio([])
          }
          return data
        })
      })
      .catch(() => undefined)
  }, [dataSelezionata])

  const cambiaData = useCallback((value: string) => {
    if (value === dataSelezionata) return
    syncDailyPlanDateUrl(value)
    setDataSelezionata(value)
    setPiano(null)
    setCodaStudio([])
    setBacklog([])
    setBacklogCursor('')
    setBacklogTotale(0)
    setBacklogAperto(false)
    setDettaglio(null)
    setErrore('')
    setAggiornamentoMessaggio('')
    setAggiornamentoRichiesto(false)
    setLoading(true)
  }, [dataSelezionata])

  useEffect(() => {
    const controller = new AbortController()
    carica(controller.signal).finally(() => setLoading(false))
    return () => controller.abort()
  }, [carica])
  useEffect(() => {
    if (!aggiornamentoRichiesto) return
    let annullato = false
    let tentativi = 0
    let timer = window.setTimeout(async function poll() {
      const aggiornato = await carica()
      if (annullato) return
      if (
        aggiornato?.stato === 'pronto' &&
        (!versioneInAttesa ||
          aggiornato.versione_piano !== versioneInAttesa ||
          aggiornato.generato_il !== generatoInAttesa)
      ) {
        setAggiornamentoMessaggio('Piano aggiornato con le attività disponibili.')
        setAggiornamentoRichiesto(false)
        return
      }
      tentativi += 1
      if (tentativi >= 12) {
        setAggiornamentoMessaggio(
          'Richiesta acquisita. Non ci sono ancora variazioni visibili: puoi continuare a lavorare.',
        )
        setAggiornamentoRichiesto(false)
        return
      }
      timer = window.setTimeout(poll, 5000)
    }, 3000)
    return () => {
      annullato = true
      window.clearTimeout(timer)
    }
  }, [aggiornamentoRichiesto, carica, generatoInAttesa, versioneInAttesa])
  const apriBacklog = useCallback(() => {
    setBacklogAperto(true)
    fetchBacklog({ date: dataSelezionata, limit: 25 }).then((data) => {
      setBacklog(data.items)
      setBacklogCursor(data.next_cursor)
      setBacklogTotale(data.total_matching)
    })
  }, [dataSelezionata])
  const backlogAltri = useCallback(() => {
    fetchBacklog({ date: dataSelezionata, cursor: backlogCursor, limit: 25 }).then((data) => {
      setBacklog((prev) => [...prev, ...data.items])
      setBacklogCursor(data.next_cursor)
    })
  }, [backlogCursor, dataSelezionata])

  async function azione(item: AttivitaPiano, action: string, params: Record<string, unknown> = {}) {
    setBusyId(item.id)
    setEsitoAzione('')
    const esito = await eseguiAzione(item.id, action, params)
    setBusyId('')
    if (!esito.ok) {
      setEsitoAzione(esito.detail || 'Operazione non riuscita.')
      return
    }
    if (esito.proposta_creata) {
      setEsitoAzione(esito.messaggio || 'Proposta inviata alla coda approvazioni.')
      return
    }
    setEsitoAzione('')
    setDettaglio(null)
    await carica()
  }

  async function aggiorna() {
    setVersioneInAttesa(piano?.versione_piano || '')
    setGeneratoInAttesa(piano?.generato_il || '')
    setAggiornamentoMessaggio('Invio la richiesta di aggiornamento...')
    setAggiornamentoRichiesto(true)
    const esito = await richiediAggiornamento(dataSelezionata)
    if (!esito.ok) {
      setAggiornamentoMessaggio('')
      setErrore(esito.detail || 'Aggiornamento non avviato. Riprova tra poco.')
      setAggiornamentoRichiesto(false)
      return
    }
    setAggiornamentoMessaggio(
      esito.messaggio ||
        (esito.gia_in_coda
          ? 'Aggiornamento già in coda: la pagina si riallinea automaticamente.'
          : 'Richiesta acquisita: la pagina si riallinea automaticamente.'),
    )
  }

  const conteggi = useMemo(() => {
    const per = piano?.riepilogo?.per_priorita || {}
    return { p0: per.P0 || 0, p1: per.P1 || 0 }
  }, [piano])

  if (loading) {
    return (
      <IusLoadingState
        title="Preparo il piano"
        message="Leggo il piano operativo già elaborato: nessuna attesa di analisi."
      />
    )
  }
  if (!piano) {
    return <IusErrorState title="Piano non disponibile" message={errore || 'Riprova tra poco.'} />
  }

  const nonGenerato = piano.stato === 'non_generato'

  return (
    <IusPageShell
      title="Piano del giorno"
      description={
        piano.data_label
          ? `Piano operativo del ${piano.data_label}${piano.generato_il_label ? ` · aggiornato alle ${piano.generato_il_label.slice(11)}` : ''}`
          : 'Il tuo piano operativo della giornata.'
      }
      icon={Sunrise}
      area="lex"
      actions={
        <Button type="button" variant="outline" onClick={aggiorna} disabled={aggiornamentoRichiesto}>
          <RefreshCw aria-hidden="true" className={aggiornamentoRichiesto ? 'animate-spin' : ''} />
          Aggiorna
        </Button>
      }
    >
      <DailyPlanDateControls value={dataSelezionata} onChange={cambiaData} />
      {errore ? <IusErrorState title="Avviso" message={errore} /> : null}
      {aggiornamentoMessaggio ? (
        <p
          role="status"
          aria-live="polite"
          className="rounded-md border bg-muted/40 px-3 py-2 text-sm"
        >
          {aggiornamentoMessaggio}
        </p>
      ) : null}

      <section className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={conteggi.p0 ? 'destructive' : 'secondary'}>
            {conteggi.p0} immediate
          </Badge>
          <Badge variant={conteggi.p1 ? 'default' : 'secondary'}>{conteggi.p1} entro il giorno</Badge>
          {piano.riepilogo.da_assegnare_studio ? (
            <Badge variant="outline">{piano.riepilogo.da_assegnare_studio} da assegnare</Badge>
          ) : null}
          {piano.riepilogo.da_rivedere ? (
            <Badge variant="outline">{piano.riepilogo.da_rivedere} da confermare</Badge>
          ) : null}
          {!piano.copertura_completa && !nonGenerato ? (
            <Badge variant="destructive" className="gap-1">
              <AlertTriangle size={12} aria-hidden="true" /> Copertura incompleta
            </Badge>
          ) : null}
        </div>
        <CoverageChips piano={piano} />
        {piano.avvisi.length ? (
          <div className="grid gap-1 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
            {piano.avvisi.map((avviso) => (
              <p key={avviso}>{avviso}</p>
            ))}
          </div>
        ) : null}
        {piano.sintesi ? (
          <p className="whitespace-pre-line rounded-md border bg-muted/40 px-3 py-2 text-sm">
            {piano.sintesi}
          </p>
        ) : null}
      </section>

      {nonGenerato ? (
        <IusEmptyState
          title="Piano non ancora generato"
          message="Usa Aggiorna per richiederlo: l'elaborazione avviene in coda e la pagina resta immediata."
          icon={Sunrise}
        />
      ) : (
        <>
          <ActivitySection
            title="Priorità del giorno"
            icon={ListTodo}
            items={piano.sezioni.da_fare_ora}
            emptyText="Nessuna urgenza per la data selezionata."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
          />

          <section className="grid gap-2">
            <IusSectionHeader title="Agenda del giorno" icon={CalendarDays} sequence={false} />
            {piano.agenda_oggi.length ? (
              <div className="grid gap-1.5">
                {piano.agenda_oggi.map((evento) => (
                  <div key={evento.id} className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <Badge variant={evento.tipo.includes('UDIENZA') ? 'destructive' : 'secondary'}>
                      {evento.tipo.includes('UDIENZA') ? 'Udienza' : 'Appuntamento'}
                    </Badge>
                    <strong>{evento.data_ora.slice(11, 16)}</strong>
                    <span>{evento.titolo}</span>
                    <span className="text-muted-foreground">
                      {evento.durata_minuti} min{evento.luogo ? ` · ${evento.luogo}` : ''}
                      {evento.avvocato ? ` · ${evento.avvocato}` : ''}
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

          <ActivitySection
            title="PEC da presidiare"
            icon={Mail}
            items={piano.sezioni.pec}
            emptyText="Nessuna comunicazione in attesa di presidio."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
          />
          <ActivitySection
            title="Fascicoli da presidiare"
            icon={FolderKanban}
            items={piano.sezioni.fascicoli}
            emptyText="Nessun fascicolo richiede interventi questa settimana."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
          />
          <ActivitySection
            title="Presidio economico"
            icon={Euro}
            items={piano.sezioni.economico}
            emptyText="Preventivi, parcelle e incassi sono sotto controllo."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
          />

          {codaStudio.length ? (
            <ActivitySection
              title="Da assegnare (studio)"
              icon={Users}
              items={codaStudio}
              emptyText=""
              onOpenDetail={setDettaglio}
              onAction={azione}
              busyId={busyId}
            />
          ) : null}

          <section className="grid gap-2">
            <IusSectionHeader title="Backlog" icon={Inbox} sequence={false} />
            {backlogAperto ? (
              <>
                {backlog.length ? (
                  <div className="grid gap-2">
                    {backlog.map((item) => (
                      <ItemCard
                        key={item.id}
                        item={item}
                        onOpenDetail={setDettaglio}
                        onAzione={azione}
                        busy={busyId === item.id}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
                    Il backlog è vuoto: tutto ciò che conta è già nel piano del giorno.
                  </p>
                )}
                {backlogCursor ? (
                  <Button type="button" variant="outline" onClick={backlogAltri}>
                    Carica altri ({backlogTotale - backlog.length} rimanenti)
                  </Button>
                ) : null}
              </>
            ) : (
              <Button type="button" variant="outline" onClick={apriBacklog}>
                Mostra il backlog{piano.riepilogo.backlog ? ` (${piano.riepilogo.backlog})` : ''}
              </Button>
            )}
          </section>
        </>
      )}

      <ItemDetailPanel
        item={dettaglio}
        writeProposalsEnabled={writeProposalsEnabled}
        onClose={() => {
          setDettaglio(null)
          setEsitoAzione('')
        }}
        onAzione={azione}
        busy={Boolean(busyId)}
        esitoMessaggio={esitoAzione}
      />
    </IusPageShell>
  )
}

export default OggiPage
