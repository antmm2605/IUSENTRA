import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  FileText,
  Gavel,
  PlayCircle,
  Search,
  Sparkles,
} from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { csrfToken } from './WizardProShared'
import { getWizardProPage, type WizardProCase, type WizardProData } from '../wizardProData'
import './WizardProPage.css'

function CaseCard({ item, selected, onSelect }: { item: WizardProCase; selected: boolean; onSelect: (item: WizardProCase) => void }) {
  const session = item.activeSession
  return (
    <article className={`iu-wiz-case ${selected ? 'is-selected' : ''}`}>
      <button type="button" onClick={() => onSelect(item)} aria-pressed={selected}>
        <span className="iu-wiz-case__top">
          <strong>{item.title}</strong>
          <Badge tone={item.statusTone}>{item.statusLabel}</Badge>
        </span>
        <span>{item.client} · {item.court}</span>
        <span className="iu-wiz-case__meta">
          <CalendarDays size={14}/> {item.hearingLabel}
        </span>
      </button>
      <div className="iu-wiz-progress" aria-label={`Avanzamento ${item.progress}%`}>
        <span style={{ width: `${Math.min(Math.max(item.progress, 0), 100)}%` }} />
      </div>
      <div className="iu-wiz-case__badges">
        {item.badges.length ? item.badges.map((badge) => <Badge key={badge.label} tone={badge.tone}>{badge.label}</Badge>) : <Badge tone="neutral">Da presidiare</Badge>}
      </div>
      <div className="iu-wiz-case__actions">
        {session ? <a href={session.stepHref}><PlayCircle size={15}/> Riprendi</a> : (
          <form method="post" action={item.startHref}>
            <input type="hidden" name="_csrf_token" value={csrfToken()} />
            <input type="hidden" name="id_fascicolo" value={item.startPayload.id_fascicolo} />
            <input type="hidden" name="id_appuntamento" value={item.startPayload.id_appuntamento} />
            <input type="hidden" name="titolo" value="" />
            <button type="submit"><PlayCircle size={15}/> Avvia</button>
          </form>
        )}
        {item.completedSession ? <a href={item.completedSession.summaryHref}><CheckCircle2 size={15}/> Riepilogo</a> : null}
        <a href={item.folderHref}><FileText size={15}/> Fascicolo</a>
      </div>
    </article>
  )
}

function SelectedPanel({ item, actions }: { item: WizardProCase | null; actions: WizardProData['actions'] }) {
  if (!item) {
    return (
      <aside className="iu-wiz-selected">
        <AlertTriangle size={24}/>
        <h2>Nessun fascicolo disponibile</h2>
        <p>Crea un fascicolo o collega un’udienza in agenda per avviare la preparazione guidata.</p>
        <a className="iu-wiz-btn" href="/fascicoli/nuovo">Nuovo fascicolo</a>
      </aside>
    )
  }
  const session = item.activeSession
  return (
    <aside className="iu-wiz-selected">
      <span className="iu-wiz-kicker">Riepilogo operativo</span>
      <h2>{item.title}</h2>
      <p>{item.client} contro {item.opponent}</p>
      <div className="iu-wiz-selected__grid">
        <span><b>RG</b>{item.rg || 'Da completare'}</span>
        <span><b>Ufficio</b>{item.court}</span>
        <span><b>Udienza</b>{item.hearingLabel}</span>
        <span><b>Modalità</b>{item.hearingMode}</span>
      </div>
      <div className="iu-wiz-checks">
        <span><ClipboardCheck size={16}/> Documenti acquisiti: <b>{item.documentsReady}</b></span>
        <span><AlertTriangle size={16}/> Documenti mancanti: <b>{item.documentsMissing}</b></span>
        <span><CalendarDays size={16}/> Scadenze collegate: <b>{item.linkedDeadlines}</b></span>
      </div>
      <div className="iu-wiz-selected__actions">
        {session ? <a className="iu-wiz-btn primary" href={session.stepHref}>Riprendi step {session.step}</a> : (
          <form method="post" action={item.startHref}>
            <input type="hidden" name="_csrf_token" value={csrfToken()} />
            <input type="hidden" name="id_fascicolo" value={item.startPayload.id_fascicolo} />
            <input type="hidden" name="id_appuntamento" value={item.startPayload.id_appuntamento} />
            <input type="hidden" name="titolo" value="" />
            <button className="iu-wiz-btn primary" type="submit">Avvia preparazione</button>
          </form>
        )}
        <a className="iu-wiz-btn" href={item.agendaHref}>Apri udienza</a>
        <a className="iu-wiz-btn" href={item.deadlineHref}>Termini collegati</a>
        <a className="iu-wiz-btn" href={actions.lex}>Chiedi a Lex</a>
      </div>
    </aside>
  )
}

export function WizardProPage() {
  const [data, setData] = useState<WizardProData | null>(null)
  const [selected, setSelected] = useState<WizardProCase | null>(null)
  const [query, setQuery] = useState('')
  const [stateFilter, setStateFilter] = useState('tutti')
  const [onlyUpcoming, setOnlyUpcoming] = useState(false)
  const [onlyMissingDocs, setOnlyMissingDocs] = useState(false)

  useEffect(() => {
    let active = true
    getWizardProPage().then((payload) => {
      if (!active) return
      setData(payload)
      setSelected(payload.selectedCase)
    })
    return () => { active = false }
  }, [])

  const filtered = useMemo(() => {
    const rows = data?.cases ?? []
    const q = query.trim().toLowerCase()
    return rows.filter((item) => {
      if (q && ![item.title, item.client, item.opponent, item.court, item.rg].join(' ').toLowerCase().includes(q)) return false
      if (stateFilter === 'bozze' && !item.activeSession) return false
      if (stateFilter === 'complete' && !item.completedSession) return false
      if (stateFilter === 'senza-sessione' && (item.activeSession || item.completedSession)) return false
      if (onlyUpcoming && !(item.hearingDays !== null && item.hearingDays <= 7)) return false
      if (onlyMissingDocs && item.documentsMissing <= 0) return false
      return true
    })
  }, [data, query, stateFilter, onlyUpcoming, onlyMissingDocs])

  if (!data) {
    return <main className="iu-wiz-page"><div className="iu-wiz-loading">Caricamento preparazioni udienza...</div></main>
  }

  return (
    <main className="iu-wiz-page">
      <section className="iu-wiz-hero">
        <div>
          <span className="iu-wiz-kicker"><Gavel size={16}/> Preparazione Udienza Guidata</span>
          <h1>Preparazione Udienza Guidata</h1>
          <p>Briefing fascicolo, documenti, strategia, pre-partenza ed esito in un unico percorso operativo.</p>
        </div>
        <div className="iu-wiz-hero__actions">
          <a href={data.actions.newAppointment}>Nuova udienza</a>
          <a href={data.actions.newDeadline}>Nuova scadenza</a>
        </div>
      </section>

      <section className="iu-wiz-metrics">
        <article><strong>{data.summary.totalCases}</strong><span>Fascicoli presidiati</span></article>
        <article><strong>{data.summary.activeDrafts}</strong><span>Bozze attive</span></article>
        <article><strong>{data.summary.completed}</strong><span>Completate</span></article>
        <article><strong>{data.summary.upcomingHearings}</strong><span>Udienze imminenti</span></article>
        <article><strong>{data.summary.documentsMissing}</strong><span>Documenti mancanti</span></article>
        <article><strong>{data.summary.linkedDeadlines}</strong><span>Scadenze collegate</span></article>
      </section>

      <section className="iu-wiz-steps" aria-label="Fasi della preparazione">
        {data.steps.map((step, index) => <span key={step}><CheckCircle2 size={15}/>{index + 1}. {step}</span>)}
      </section>

      <section className="iu-wiz-layout">
        <div className="iu-wiz-list">
          <label className="iu-wiz-search">
            <Search size={17}/>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cerca fascicolo, cliente, RG o ufficio..." />
          </label>
          <div className="iu-wiz-filterbar" aria-label="Filtri preparazione udienza">
            <label>
              <span>Stato preparazione</span>
              <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
                <option value="tutti">Tutti</option>
                <option value="bozze">Bozze attive</option>
                <option value="complete">Completate</option>
                <option value="senza-sessione">Da avviare</option>
              </select>
            </label>
            <label className="iu-wiz-toggle">
              <input type="checkbox" checked={onlyUpcoming} onChange={(event) => setOnlyUpcoming(event.target.checked)} />
              <span>Udienze imminenti</span>
            </label>
            <label className="iu-wiz-toggle">
              <input type="checkbox" checked={onlyMissingDocs} onChange={(event) => setOnlyMissingDocs(event.target.checked)} />
              <span>Documenti mancanti</span>
            </label>
          </div>
          {filtered.length ? filtered.map((item) => (
            <CaseCard key={item.id} item={item} selected={selected?.id === item.id} onSelect={setSelected} />
          )) : (
            <div className="iu-wiz-empty">
              <Sparkles size={24}/>
              <strong>Nessun fascicolo trovato</strong>
              <span>Modifica la ricerca o crea una nuova udienza dall’agenda.</span>
            </div>
          )}
        </div>
        <SelectedPanel item={selected} actions={data.actions} />
      </section>

      <FloatingLex
        context="preparazione-udienza"
        title="Lex udienza"
        body="Posso preparare il briefing, controllare documenti mancanti e suggerire una checklist prudente prima della comparizione."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex udienza"
        secondaryHref={data.actions.deadlines}
        secondaryLabel="Termini collegati"
      />
    </main>
  )
}
