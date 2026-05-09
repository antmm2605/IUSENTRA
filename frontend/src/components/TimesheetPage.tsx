import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AlertTriangle, Banknote, CalendarDays, CheckCircle2, Clock3, FileText, Filter, Plus, Search } from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import { getTimesheetPage, type TimesheetData, type TimesheetEntry } from '../timesheetData'
import './TimesheetPage.css'

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

function StatCard({ label, value, icon }: { label: string; value: string | number; icon: ReactNode }) {
  return (
    <article className="iu-timesheet-stat">
      <span>{icon}</span>
      <strong>{value}</strong>
      <small>{label}</small>
    </article>
  )
}

function FilterBar({ data }: { data: TimesheetData }) {
  return (
    <form className="iu-timesheet-filters" method="get" action="/timesheet">
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
      <button type="submit"><Filter size={16}/> Applica</button>
      <a href="/timesheet">Azzera</a>
    </form>
  )
}

function NewEntryForm({ data }: { data: TimesheetData }) {
  return (
    <section className="iu-timesheet-panel">
      <div className="iu-timesheet-panel__head">
        <div>
          <span className="iu-timesheet-kicker"><Plus size={15}/> Nuova attivita</span>
          <h2>Registra tempo</h2>
        </div>
      </div>
      <JsonPostForm className="iu-timesheet-form" action={data.actions.create} successMessage="Attivita salvata.">
        <input type="hidden" name="_csrf_token" value={csrfToken()} />
        <input type="hidden" name="from_page" value="timesheet" />
        <label className="wide">
          <span>Descrizione</span>
          <input name="descrizione" required maxLength={300} placeholder="Attivita svolta" />
        </label>
        <label>
          <span>Minuti</span>
          <input name="minuti" type="number" min="1" step="1" required defaultValue="30" />
        </label>
        <label>
          <span>Data attivita</span>
          <input name="data_attivita" type="date" defaultValue={new Date().toISOString().slice(0, 10)} />
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
          <input type="checkbox" name="fatturabile" value="1" defaultChecked />
          <span>Voce fatturabile</span>
        </label>
        <button type="submit">Salva attivita</button>
      </JsonPostForm>
    </section>
  )
}

function StatusForm({ entry, data }: { entry: TimesheetEntry; data: TimesheetData }) {
  return (
    <JsonPostForm className="iu-timesheet-status" action={entry.stateAction} successMessage="Stato salvato.">
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

function EntryList({ data }: { data: TimesheetData }) {
  if (data.emptyStates.noEntries) {
    return <div className="iu-timesheet-empty"><Clock3 size={26}/><strong>Nessuna voce timesheet</strong><span>Registra la prima attivita dal form operativo.</span></div>
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
            <h3>{entry.description}</h3>
            <p>{entry.clientName} · {entry.fascicoloLabel}</p>
            <div className="iu-timesheet-entry__links">
              {entry.clientHref ? <a href={entry.clientHref}>Apri cliente</a> : null}
              {entry.fascicoloHref ? <a href={entry.fascicoloHref}>Apri fascicolo</a> : null}
            </div>
          </div>
          <dl>
            <div><dt>Tempo</dt><dd>{entry.hoursLabel}</dd></div>
            <div><dt>Valore unitario</dt><dd>{entry.hourlyRateLabel}</dd></div>
            <div><dt>Totale</dt><dd>{entry.totalValueLabel}</dd></div>
            <div><dt>Utente</dt><dd>{entry.user}</dd></div>
          </dl>
          <div className="iu-timesheet-entry__side">
            <Badge tone={entry.statusTone}>{entry.statusLabel}</Badge>
            <Badge tone={entry.billable ? 'success' : 'neutral'}>{entry.billableLabel}</Badge>
            {entry.origin ? <small>Origine: {entry.origin}</small> : null}
            {entry.notes ? <small>{entry.notes}</small> : null}
            <StatusForm entry={entry} data={data} />
          </div>
        </article>
      ))}
    </section>
  )
}

function BillingPanel({ data }: { data: TimesheetData }) {
  const eligible = useMemo(() => data.entries.filter((entry) => entry.eligibleForInvoice), [data.entries])
  const [selected, setSelected] = useState<string[]>(data.billing.entryIds)
  useEffect(() => setSelected(data.billing.entryIds), [data.billing.entryIds])
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
        <JsonPostForm className="iu-timesheet-billing" action={data.billing.action} successMessage="Parcella creata.">
          <input type="hidden" name="_csrf_token" value={csrfToken()} />
          <input type="hidden" name="id_cliente" value={data.billing.idCliente} />
          <input type="hidden" name="id_fascicolo" value={data.billing.idFascicolo} />
          <p>{data.billing.count} voci eleggibili, {data.billing.hoursLabel}, valore {data.billing.valueLabel}.</p>
          <div className="iu-timesheet-billing__checks">
            {eligible.map((entry) => (
              <label key={entry.id}>
                <input type="checkbox" name="entry_ids" value={entry.id} checked={selected.includes(entry.id)} onChange={() => toggle(entry.id)} />
                <span>{entry.dateLabel} · {entry.description} · {entry.totalValueLabel}</span>
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

  if (loadError) {
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
          <a href={data.actions.statistics}>Produttivita</a>
          <a href={data.actions.clients}>Clienti</a>
          <a href={data.actions.matters}>Fascicoli</a>
        </div>
      </section>

      <section className="iu-timesheet-stats">
        <StatCard icon={<FileText size={18}/>} label="Voci totali" value={data.summary.totalEntries} />
        <StatCard icon={<Clock3 size={18}/>} label="Tempo lavorato" value={data.summary.totalHoursLabel} />
        <StatCard icon={<Banknote size={18}/>} label="Valore totale" value={data.summary.totalValueLabel} />
        <StatCard icon={<CheckCircle2 size={18}/>} label="Validate" value={data.summary.validated} />
        <StatCard icon={<Clock3 size={18}/>} label="Aperte" value={data.summary.open} />
        <StatCard icon={<Banknote size={18}/>} label="Fatturate" value={data.summary.invoiced} />
        <StatCard icon={<CheckCircle2 size={18}/>} label="Fatturabili" value={data.summary.billable} />
        <StatCard icon={<FileText size={18}/>} label="Interne" value={data.summary.notBillable} />
      </section>

      <FilterBar data={data} />

      <section className="iu-timesheet-layout">
        <div>
          <EntryList data={data} />
        </div>
        <aside className="iu-timesheet-side">
          <NewEntryForm data={data} />
          <BillingPanel data={data} />
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
