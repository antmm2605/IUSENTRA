import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Banknote, CalendarDays, CheckCircle2, Clock3, Filter, Plus, Search } from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import { getTimesheetPage, type TimesheetData, type TimesheetEntry, type TrackingProposal } from '../timesheetData'
import './TimesheetPage.css'
import { TimesheetMetrics } from './TimesheetMetrics'
import { todayInRome } from '../pages/daily-plan/DailyPlanDateControls'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { publishMutationRefresh } from '../operationalRefresh'

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function TrackingProposalsSection({ proposals, onDone }:{proposals:TrackingProposal[]; onDone:()=>Promise<void>}) {
  const [busyId, setBusyId] = useState('')
  const [message, setMessage] = useState('')
  const [minutesById, setMinutesById] = useState<Record<string, string>>({})
  if (!proposals.length) return null
  const send = async (href: string, id: string, body: Record<string, unknown>) => {
    setBusyId(id); setMessage('')
    try {
      const response = await fetch(href, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(body),
      })
      const payload = await response.json().catch(() => ({})) as { ok?:boolean; message?:string }
      setMessage(payload.message || (response.ok ? 'Operazione completata.' : 'Operazione non riuscita.'))
      if (!response.ok || !payload.ok) throw new Error(payload.message || 'Operazione non riuscita.')
      publishMutationRefresh(href)
      try { await onDone() } catch {
        setMessage('Operazione salvata. Aggiornamento dei dati non riuscito: riprova senza ripetere il comando.')
      }
    } catch {
      setMessage('Operazione non riuscita.')
    } finally { setBusyId('') }
  }
  return (
    <section className="iu-timesheet-proposals" aria-label="Proposte dal tracking passivo">
      <header>
        <span><Clock3 size={17}/> Tempo rilevato automaticamente</span>
        <small>Sessioni di lavoro rilevate dalle attività registrate: conferma per creare la voce timesheet (art. 22-bis D.M. 55/2014) o scarta.</small>
      </header>
      {message ? <p className="iu-timesheet-proposals__msg" role="status">{message}</p> : null}
      <ul>
        {proposals.map((proposta) => (
          <li key={proposta.id}>
            <div className="iu-timesheet-proposals__info">
              <strong>{proposta.fascicoloLabel}</strong>
              <span>{proposta.data} · {proposta.oraInizio}-{proposta.oraFine} · {proposta.username}</span>
              <em>{proposta.descrizione}</em>
            </div>
            <div className="iu-timesheet-proposals__actions">
              <label>
                <span>Minuti</span>
                <input
                  type="number" min={1} max={720}
                  value={minutesById[proposta.id] ?? String(proposta.minuti)}
                  onChange={(event) => setMinutesById((prev) => ({ ...prev, [proposta.id]: event.target.value }))}
                />
              </label>
              <button type="button" disabled={busyId === proposta.id} onClick={() => send(proposta.confirmHref, proposta.id, { minuti: minutesById[proposta.id] ?? String(proposta.minuti) })}>
                <CheckCircle2 size={15}/> Conferma
              </button>
              <button type="button" className="iu-timesheet-proposals__dismiss" disabled={busyId === proposta.id} onClick={() => send(proposta.dismissHref, proposta.id, {})}>
                Scarta
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function FilterBar({ data, onFilter }: { data: TimesheetData; onFilter: (filters: Record<string, string>) => void }) {
  return (
    <form className="iu-timesheet-filters" method="get" action="/timesheet" onSubmit={event => {
      event.preventDefault()
      onFilter(Object.fromEntries(Array.from(new FormData(event.currentTarget).entries(), ([key, value]) => [key, String(value)])))
    }}>
      <input type="hidden" name="fatturabile" value={data.filters.fatturabile || ''}/>
      <input type="hidden" name="ordina" value={data.filters.ordina || ''}/>
      <label>
        <span>Cliente</span>
        <select name="id_cliente" defaultValue={data.filters.id_cliente || ''}>
          <option value="">Tutti i clienti</option>
          {data.options.clients.map((client) => <option value={client.id} key={client.id}>{client.label}</option>)}
        </select>
      </label>
      <label>
        <span>Fascicolo</span>
        <select name="id_fascicolo" defaultValue={data.filters.id_fascicolo || ''}>
          <option value="">Tutti i fascicoli</option>
          {data.options.matters.map((matter) => <option value={matter.id} key={matter.id}>{matter.label}</option>)}
        </select>
      </label>
      <label>
        <span>Stato</span>
        <select name="stato" defaultValue={data.filters.stato || ''}>
          <option value="">Tutti gli stati</option>
          {data.options.statuses.map((status) => <option value={status.value} key={status.value}>{status.label}</option>)}
        </select>
      </label>
      <label>
        <span>Utente</span>
        <select name="utente" defaultValue={data.filters.utente || ''}>
          <option value="">Tutti gli utenti</option>
          {data.options.users.map((user) => <option value={user.value} key={user.value}>{user.label}</option>)}
        </select>
      </label>
      <label>
        <span>Dal</span>
        <input type="date" name="data_da" defaultValue={data.filters.data_da || ''} />
      </label>
      <label>
        <span>Al</span>
        <input type="date" name="data_a" defaultValue={data.filters.data_a || ''} />
      </label>
      <label className="iu-timesheet-filters__search">
        <span>Ricerca</span>
        <input type="search" name="q" defaultValue={data.filters.q || ''} placeholder="Descrizione, note, origine..." />
      </label>
      <div className="iu-timesheet-filters__actions">
        <button type="submit"><Filter size={16}/> Applica</button>
        <button type="button" onClick={() => onFilter({})}>Azzera</button>
      </div>
    </form>
  )
}

function NewEntryForm({ data, onDone }: { data: TimesheetData; onDone: () => Promise<void> }) {
  const [billable, setBillable] = useState(true)
  return (
    <section className="iu-timesheet-panel">
      <div className="iu-timesheet-panel__head">
        <div>
          <span className="iu-timesheet-kicker"><Plus size={15}/> Nuova attività</span>
          <h2>Registra tempo</h2>
        </div>
      </div>
      <JsonPostForm className="iu-timesheet-form" action={data.actions.create} successMessage="Attività salvata." onSuccess={async (_result, form) => { await onDone(); form.reset(); setBillable(true) }}>
        <input type="hidden" name="_csrf_token" value={csrfToken()} />
        <input type="hidden" name="from_page" value="timesheet" />
        <label className="wide">
          <span>Descrizione</span>
          <input name="descrizione" required maxLength={300} placeholder="Attività svolta" />
        </label>
        <label>
          <span>Minuti</span>
          <input name="minuti" type="number" min="1" step="1" required defaultValue="30" />
        </label>
        <label>
          <span>Data attività</span>
          <input name="data_attivita" type="date" defaultValue={todayInRome()} />
        </label>
        <label>
          <span>Cliente</span>
          <select name="id_cliente" defaultValue={data.filters.id_cliente || ''}>
            <option value="">Non collegato</option>
            {data.options.clients.map((client) => <option value={client.id} key={client.id}>{client.label}</option>)}
          </select>
        </label>
        <label>
          <span>Fascicolo</span>
          <select name="id_fascicolo" defaultValue={data.filters.id_fascicolo || ''}>
            <option value="">Non collegato</option>
            {data.options.matters.map((matter) => <option value={matter.id} key={matter.id}>{matter.label}</option>)}
          </select>
        </label>
        <label>
          <span>Valore unitario</span>
          <input name="valore_unitario" type="number" min="0" step="0.01" defaultValue="0" />
        </label>
        <label>
          <span>Contesto</span>
          <input name="contesto" maxLength={120} placeholder="Udienza, telefonata, studio atti..." />
        </label>
        <label className="wide">
          <span>Note</span>
          <textarea name="note" rows={3} placeholder="Annotazioni interne" />
        </label>
        <label className="iu-timesheet-check">
          <input type="hidden" name="fatturabile" value={billable ? '1' : '0'} />
          <input type="checkbox" checked={billable} onChange={event => setBillable(event.target.checked)} />
          <span>Voce fatturabile</span>
        </label>
        <button type="submit">Salva attività</button>
      </JsonPostForm>
    </section>
  )
}

function StatusForm({ entry, data, onDone }: { entry: TimesheetEntry; data: TimesheetData; onDone: () => Promise<void> }) {
  return (
    <JsonPostForm className="iu-timesheet-status" action={entry.stateAction} successMessage="Stato salvato." onSuccess={onDone}>
      <input type="hidden" name="_csrf_token" value={csrfToken()} />
      <input type="hidden" name="id_cliente" value={data.filters.id_cliente || entry.idCliente} />
      <input type="hidden" name="id_fascicolo" value={data.filters.id_fascicolo || entry.idFascicolo} />
      <select name="stato" defaultValue={entry.status} aria-label={`Stato ${entry.description}`}>
        {data.options.statuses.map((status) => <option value={status.value} key={status.value}>{status.label}</option>)}
      </select>
      <button type="submit">Aggiorna</button>
    </JsonPostForm>
  )
}

function EntryList({ data, onDone }: { data: TimesheetData; onDone: () => Promise<void> }) {
  if (data.emptyStates.noEntries) {
    return <div className="iu-timesheet-empty"><Clock3 size={26}/><strong>Nessuna voce timesheet</strong><span>Registra la prima attività dal form operativo.</span></div>
  }
  if (data.emptyStates.noFilteredEntries) {
    return <div className="iu-timesheet-empty"><Search size={26}/><strong>Nessun risultato</strong><span>I filtri selezionati non restituiscono voci.</span></div>
  }
  return (
    <section className="iu-timesheet-list" aria-label="Voci timesheet">
      {data.entries.map((entry) => (
        <article className="iu-timesheet-entry" key={entry.id}>
          <div>
            <span className="iu-timesheet-entry__date"><CalendarDays size={14}/>{entry.dateLabel}</span>
            <h3 data-allow-technical-text="true">{entry.description}</h3>
            <p data-allow-technical-text="true">{entry.clientName} · {entry.fascicoloLabel}</p>
            <div className="iu-timesheet-entry__links">
              {entry.clientHref ? <a href={entry.clientHref}>Apri cliente</a> : null}
              {entry.fascicoloHref ? <a href={entry.fascicoloHref}>Apri fascicolo</a> : null}
            </div>
          </div>
          <dl>
            <div><dt>Tempo</dt><dd>{entry.hoursLabel}</dd></div>
            <div><dt>Valore unitario</dt><dd>{entry.hourlyRateLabel}</dd></div>
            <div><dt>Totale</dt><dd>{entry.totalValueLabel}</dd></div>
            <div><dt>Utente</dt><dd data-allow-technical-text="true">{entry.user}</dd></div>
          </dl>
          <div className="iu-timesheet-entry__side">
            <Badge tone={entry.statusTone}>{entry.statusLabel}</Badge>
            <Badge tone={entry.billable ? 'success' : 'neutral'}>{entry.billableLabel}</Badge>
            {entry.origin ? <small>Origine: {entry.origin}</small> : null}
            {entry.notes ? <small data-allow-technical-text="true">{entry.notes}</small> : null}
            <StatusForm entry={entry} data={data} onDone={onDone} />
          </div>
        </article>
      ))}
    </section>
  )
}

function BillingPanel({ data, onDone }: { data: TimesheetData; onDone: () => Promise<void> }) {
  const eligible = useMemo(() => data.entries.filter((entry) => entry.eligibleForInvoice), [data.entries])
  const [selected, setSelected] = useState<string[]>(data.billing.entryIds)
  useEffect(() => setSelected(current => current.filter(id => data.billing.entryIds.includes(id))), [data.billing.entryIds])
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])
  return (
    <section className="iu-timesheet-panel">
      <div className="iu-timesheet-panel__head">
        <div>
          <span className="iu-timesheet-kicker"><Banknote size={15}/> Parcella</span>
          <h2>Genera parcella</h2>
        </div>
        <a href={data.actions.billing}>Apri fatturazione</a>
      </div>
      {eligible.length ? (
        <JsonPostForm className="iu-timesheet-billing" action={data.billing.action} successMessage="Parcella creata." onSuccess={async result => {
          await onDone()
          if (result.redirect) window.dispatchEvent(new CustomEvent('iusentra:open-work-window', { detail: { href: result.redirect, title: 'Parcella da Timesheet' } }))
        }}>
          <input type="hidden" name="_csrf_token" value={csrfToken()} />
          <input type="hidden" name="id_cliente" value={data.billing.idCliente} />
          <input type="hidden" name="id_fascicolo" value={data.billing.idFascicolo} />
          <p>{data.billing.count} voci eleggibili, {data.billing.hoursLabel}, valore {data.billing.valueLabel}.</p>
          <div className="iu-timesheet-billing__checks">
            {eligible.map((entry) => (
              <label key={entry.id}>
                <input type="checkbox" name="entry_ids" value={entry.id} checked={selected.includes(entry.id)} onChange={() => toggle(entry.id)} />
                <span data-allow-technical-text="true">{entry.dateLabel} · {entry.description} · {entry.totalValueLabel}</span>
              </label>
            ))}
          </div>
          <label>
            <span>Data scadenza</span>
            <input type="date" name="data_scadenza" />
          </label>
          <button type="submit" disabled={!selected.length}>Genera parcella da voci validate</button>
        </JsonPostForm>
      ) : (
        <div className="iu-timesheet-empty small">
          <CheckCircle2 size={22}/>
          <strong>Nessuna voce fatturabile pronta</strong>
          <span>Servono voci validate e fatturabili dello stesso perimetro cliente/fascicolo.</span>
        </div>
      )}
      {data.billing.issues.length ? <ul className="iu-timesheet-issues">{data.billing.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : null}
    </section>
  )
}

export function TimesheetPage() {
  const [data, setData] = useState<TimesheetData | null>(null)
  const [loadError, setLoadError] = useState('')
  const [filtering, setFiltering] = useState(false)
  async function refreshEntries() {
    try {
      const payload = await getTimesheetPage()
      setData(payload)
      setLoadError('')
    } catch (error) {
      setLoadError('Il comando è stato salvato, ma i dati non sono stati aggiornati. Riprova l’aggiornamento senza ripetere il comando.')
      throw error
    }
  }
  useOperationalRefresh(['timesheet'], refreshEntries)
  async function filterEntries(filters: Record<string, string>) {
    if (filtering) return
    setFiltering(true)
    setLoadError('')
    try {
      const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)))
      if (new URLSearchParams(window.location.search).get('embed') === 'source') params.set('embed', 'source')
      const search = params.size ? `?${params}` : ''
      const payload = await getTimesheetPage(search)
      setData(payload)
      window.history.replaceState(null, '', `/timesheet${search}`)
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : 'Errore durante il caricamento del timesheet.')
    } finally { setFiltering(false) }
  }
  useEffect(() => {
    let active = true
    getTimesheetPage()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setLoadError('')
      })
      .catch(() => {
        if (active) setLoadError('Errore durante il caricamento del timesheet.')
      })
    return () => { active = false }
  }, [])

  if (loadError && !data) {
    return (
      <main className="iu-timesheet-page">
        <div className="iu-timesheet-empty">
          <AlertTriangle size={26}/>
          <strong>Timesheet non disponibile</strong>
          <span>{loadError}</span>
          <button type="button" onClick={() => window.location.reload()}>Riprova</button>
        </div>
      </main>
    )
  }

  if (!data) {
    return <main className="iu-timesheet-page"><div className="iu-timesheet-loading">Caricamento timesheet...</div></main>
  }

  return (
    <main className="iu-timesheet-page">
      <section className="iu-timesheet-hero">
        <div>
          <span className="iu-timesheet-kicker"><Clock3 size={16}/> Timesheet operativo</span>
          <h1>Timesheet</h1>
          <p>Tempo, validazione e fatturazione collegati a clienti, fascicoli e parcelle reali.</p>
        </div>
        <div className="iu-timesheet-hero__actions">
          <a href={data.actions.agenda}>Agenda</a>
          <a href={data.actions.statistics}>Produttività</a>
          <a href={data.actions.clients}>Clienti</a>
          <a href={data.actions.matters}>Fascicoli</a>
        </div>
      </section>

      <TimesheetMetrics data={data} onFilter={filterEntries} busy={filtering}/>
      <p className="iu-timesheet-filter-status" role={loadError ? 'alert' : 'status'}>{loadError || (filtering ? 'Aggiornamento delle voci in corso…' : 'Indicatori e voci del contesto selezionato. Le card filtrano e ordinano la ricerca.')}</p>
      {loadError ? <button type="button" onClick={() => { void refreshEntries().catch(() => undefined) }}>Riprova aggiornamento</button> : null}
      <FilterBar key={JSON.stringify(data.filters)} data={data} onFilter={filterEntries} />

      <TrackingProposalsSection proposals={data.trackingProposals} onDone={refreshEntries} />

      <section className="iu-timesheet-layout">
        <div>
          <EntryList data={data} onDone={refreshEntries} />
        </div>
        <aside className="iu-timesheet-side">
          <NewEntryForm data={data} onDone={refreshEntries} />
          <BillingPanel data={data} onDone={refreshEntries} />
        </aside>
      </section>

      <FloatingLex
        context="timesheet"
        title="Lex timesheet"
        body="Legge voci, clienti, fascicoli e stati per aiutarti a controllare tempi fatturabili e prossime azioni economiche."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex timesheet"
        secondaryHref={data.actions.billing}
        secondaryLabel="Fatturazione"
      />
    </main>
  )
}
