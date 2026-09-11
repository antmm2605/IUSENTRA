import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Euro,
  FolderKanban,
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
} from '@/components/iusentra'
import { isFeatureFlagEnabledSync } from '@/lib/featureFlags'
import { formatTimeIt } from '@/formatting'
import { ItemDetailPanel } from './ItemDetailPanel'
import {
  DailyPlanDateControls,
  initialDailyPlanDate,
  syncDailyPlanDateUrl,
} from './DailyPlanDateControls'
import { ActivitySection, AgendaOggiSection, BacklogSection, CoverageChips } from './DailyPlanPageParts'
import { SourceWorkspace, type FonteAperta } from './SourceWorkspace'
import {
  eseguiAzione,
  fetchBacklog,
  fetchPianoGiorno,
  fetchStatoAggiornamento,
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
  const [aggiornamentoJobId, setAggiornamentoJobId] = useState('')
  const [aggiornamentoMessaggio, setAggiornamentoMessaggio] = useState('')
  const [backlog, setBacklog] = useState<AttivitaPiano[]>([])
  const [backlogCursor, setBacklogCursor] = useState('')
  const [backlogTotale, setBacklogTotale] = useState(0)
  const [backlogAperto, setBacklogAperto] = useState(false)
  const [fonteAperta, setFonteAperta] = useState<FonteAperta | null>(null)
  const apriFonte = useCallback((item: AttivitaPiano, lista: AttivitaPiano[]) => {
    setEsitoAzione('')
    setFonteAperta({ item, lista })
  }, [])

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
    setFonteAperta(null)
    setErrore('')
    setAggiornamentoMessaggio('')
    setAggiornamentoRichiesto(false)
    setAggiornamentoJobId('')
    setLoading(true)
  }, [dataSelezionata])

  useEffect(() => {
    const controller = new AbortController()
    carica(controller.signal).finally(() => setLoading(false))
    return () => controller.abort()
  }, [carica])
  useEffect(() => {
    if (!aggiornamentoRichiesto || !aggiornamentoJobId) return
    let annullato = false
    let tentativi = 0
    const controller = new AbortController()
    let timer = window.setTimeout(async function poll() {
      try {
        const esito = await fetchStatoAggiornamento(aggiornamentoJobId, controller.signal)
        if (annullato) return
        const stato = esito.stato || esito.status

        if (esito.ok && stato === 'done') {
          const aggiornato = await carica(controller.signal)
          if (annullato) return
          if (aggiornato?.ok && aggiornato.stato === 'pronto') {
            setAggiornamentoMessaggio('Piano aggiornato con le attività disponibili.')
            setAggiornamentoRichiesto(false)
            setAggiornamentoJobId('')
            return
          }
          setAggiornamentoMessaggio('Elaborazione completata. Aggiorno la visualizzazione del piano...')
        } else if (esito.ok && stato === 'failed') {
          setErrore(esito.detail || esito.messaggio || 'L’elaborazione del piano non è riuscita.')
          setAggiornamentoMessaggio(
            'Aggiornamento non completato. Il controllo automatico del piano verificherà nuovamente la copertura.',
          )
          setAggiornamentoRichiesto(false)
          setAggiornamentoJobId('')
          return
        } else if (esito.ok && stato === 'running') {
          setAggiornamentoMessaggio(
            esito.messaggio || 'Piano in elaborazione. Puoi continuare a lavorare mentre il servizio automatico lo prepara.',
          )
        } else if (esito.ok && stato === 'queued') {
          setAggiornamentoMessaggio(
            esito.messaggio || 'Aggiornamento in coda. Il piano resta consultabile durante la preparazione.',
          )
        } else {
          setAggiornamentoMessaggio('Verifico lo stato dell’aggiornamento del piano...')
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
      }

      tentativi += 1
      if (tentativi >= 18) {
        setAggiornamentoMessaggio(
          'Non ho ancora ricevuto l’esito dell’elaborazione. Puoi continuare a lavorare: il piano resta consultabile e il controllo automatico prosegue.',
        )
        setAggiornamentoRichiesto(false)
        setAggiornamentoJobId('')
        return
      }
      timer = window.setTimeout(poll, 5000)
    }, 800)
    return () => {
      annullato = true
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [aggiornamentoJobId, aggiornamentoRichiesto, carica])
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

  async function azione(item: AttivitaPiano, action: string, params: Record<string, unknown> = {}): Promise<boolean> {
    setBusyId(item.id)
    setEsitoAzione('')
    const esito = await eseguiAzione(item.id, action, params)
    setBusyId('')
    if (!esito.ok) {
      setEsitoAzione(esito.detail || 'Operazione non riuscita.')
      return false
    }
    if (esito.proposta_creata) {
      setEsitoAzione(esito.messaggio || 'Proposta inviata alla coda approvazioni.')
      return true
    }
    setEsitoAzione('')
    setDettaglio(null)
    await carica()
    return true
  }

  async function aggiorna() {
    setErrore('')
    setAggiornamentoMessaggio('Invio la richiesta di aggiornamento...')
    setAggiornamentoRichiesto(true)
    const esito = await richiediAggiornamento(dataSelezionata)
    if (!esito.ok || !esito.job_id) {
      setAggiornamentoMessaggio('')
      setErrore(esito.detail || 'Aggiornamento non avviato. Riprova tra poco.')
      setAggiornamentoRichiesto(false)
      return
    }
    setAggiornamentoJobId(esito.job_id)
    setAggiornamentoMessaggio(
      esito.stato === 'running'
        ? 'Piano in elaborazione. Ne mostrerò l’esito reale non appena disponibile.'
        : esito.stato === 'queued'
          ? 'Aggiornamento in coda. Ne mostrerò l’esito reale non appena disponibile.'
          : esito.messaggio || 'Verifico lo stato dell’aggiornamento richiesto.',
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
  const oraGenerazione = formatTimeIt(piano.generato_il, '')

  return (
    <IusPageShell
      title="Piano del giorno"
      description={
        piano.data_label
          ? `Piano operativo del ${piano.data_label}${oraGenerazione ? ` · aggiornato alle ${oraGenerazione}` : ''}`
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
          message="Il piano della giornata corrente viene preparato automaticamente alle 05:30, ora italiana, e si recupera da solo se la prima elaborazione non è disponibile. Per una data futura puoi richiedere un aggiornamento aggiuntivo senza bloccare la pagina."
          icon={Sunrise}
          action={
            <Button type="button" variant="outline" onClick={aggiorna} disabled={aggiornamentoRichiesto}>
              <RefreshCw aria-hidden="true" className={aggiornamentoRichiesto ? 'animate-spin' : ''} />
              Richiedi aggiornamento
            </Button>
          }
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
            onOpenSource={apriFonte}
            dataPiano={piano.data}
          />

          <AgendaOggiSection eventi={piano.agenda_oggi} />

          <ActivitySection
            title="PEC da presidiare"
            icon={Mail}
            items={piano.sezioni.pec}
            emptyText="Nessuna comunicazione in attesa di presidio."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
            onOpenSource={apriFonte}
            dataPiano={piano.data}
          />
          <ActivitySection
            title="Fascicoli da presidiare"
            icon={FolderKanban}
            items={piano.sezioni.fascicoli}
            emptyText="Nessun fascicolo richiede interventi questa settimana."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
            onOpenSource={apriFonte}
            dataPiano={piano.data}
          />
          <ActivitySection
            title="Presidio economico"
            icon={Euro}
            items={piano.sezioni.economico}
            emptyText="Preventivi, parcelle e incassi sono sotto controllo."
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
            onOpenSource={apriFonte}
            dataPiano={piano.data}
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
              onOpenSource={apriFonte}
              dataPiano={piano.data}
            />
          ) : null}

          <BacklogSection
            aperto={backlogAperto}
            items={backlog}
            restanti={backlogCursor ? backlogTotale - backlog.length : 0}
            totalePiano={piano.riepilogo.backlog || 0}
            onApri={apriBacklog}
            onAltri={backlogAltri}
            onOpenDetail={setDettaglio}
            onAction={azione}
            busyId={busyId}
            onOpenSource={apriFonte}
            dataPiano={piano.data}
          />
        </>
      )}

      <SourceWorkspace
        aperta={fonteAperta}
        dataPiano={piano.data}
        writeProposalsEnabled={writeProposalsEnabled}
        busy={Boolean(busyId)}
        esitoMessaggio={esitoAzione}
        onNavigate={(next) => {
          setEsitoAzione('')
          setFonteAperta(next)
        }}
        onClose={() => {
          setFonteAperta(null)
          setEsitoAzione('')
        }}
        onAzione={azione}
        onOpenDetail={(item) => {
          setFonteAperta(null)
          setDettaglio(item)
        }}
      />

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
        onOpenSource={(item) => {
          setDettaglio(null)
          apriFonte(item, [item])
        }}
      />
    </IusPageShell>
  )
}

export default OggiPage
