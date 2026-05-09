import { useEffect, useState } from 'react'
import { Archive, CalendarDays, CheckCircle2, FileText, Gavel, Trash2 } from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import { MatterSummary, WizardStepper, csrfToken } from './WizardProShared'
import { getWizardProCompletePage, type WizardProCompleteData } from '../wizardProData'
import './WizardProPage.css'

function DocumentsSummary({ data }: { data: WizardProCompleteData }) {
  if (!data.documents.length) {
    return <div className="iu-wiz-empty small"><FileText size={22}/><strong>Nessun documento in checklist</strong><span>La sessione non contiene documenti registrati.</span></div>
  }
  return (
    <div className="iu-wiz-docs">
      {data.documents.map((doc) => (
        <article key={`${doc.index}-${doc.label}`}>
          <div>
            <strong>{doc.label}</strong>
            <span>{doc.type || 'Tipo non indicato'}{doc.signed ? ' · firmato' : ''}</span>
          </div>
          <Badge tone={doc.statusTone}>{doc.statusLabel}</Badge>
          {doc.href ? <a href={doc.href}>Apri documento</a> : null}
        </article>
      ))}
    </div>
  )
}

export function WizardProCompletePage() {
  const [data, setData] = useState<WizardProCompleteData | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  useEffect(() => {
    let active = true
    getWizardProCompletePage().then((payload) => { if (active) setData(payload) })
    return () => { active = false }
  }, [])

  if (!data) {
    return <main className="iu-wiz-page"><div className="iu-wiz-loading">Caricamento riepilogo preparazione...</div></main>
  }

  return (
    <main className="iu-wiz-page iu-wiz-complete-page">
      <section className="iu-wiz-hero">
        <div>
          <span className="iu-wiz-kicker"><CheckCircle2 size={16}/> Riepilogo udienza</span>
          <h1>{data.session?.title || 'Preparazione completata'}</h1>
          <p>Esito, checklist, azioni successive e collegamenti operativi della sessione.</p>
        </div>
        <div className="iu-wiz-hero__actions">
          <a href={data.actions.folder}>Apri fascicolo</a>
          <a href={data.actions.agenda}>Agenda</a>
          <a href={data.actions.deadlines}>Scadenziario</a>
        </div>
      </section>
      <WizardStepper steps={data.steps} />
      <section className="iu-wiz-step-layout">
        <div className="iu-wiz-step-main">
          <section className="iu-wiz-panel">
            <div className="iu-wiz-panel__head">
              <div>
                <span className="iu-wiz-kicker"><Gavel size={15}/> Esito</span>
                <h2>{data.outcome.label || 'Esito non indicato'}</h2>
              </div>
              <Badge tone={data.outcome.tone}>{data.session?.statusLabel || 'Sessione'}</Badge>
            </div>
            <div className="iu-wiz-facts">
              <span><b>Completata</b>{data.session?.completedAtLabel || 'Non indicata'}</span>
              <span><b>Rinvio</b>{data.outcome.postponementDateLabel || 'Non indicato'}</span>
              <span><b>Fascicolo aggiornato</b>{data.outcome.matterUpdated ? 'Si' : 'No'}</span>
              <span><b>Documenti checklist</b>{data.documents.length}</span>
            </div>
            <div className="iu-wiz-note-grid">
              <article><strong>Note verbale</strong><p>{data.outcome.hearingNotes || 'Nessuna nota verbale registrata.'}</p></article>
              <article><strong>Azioni successive</strong><p>{data.outcome.nextActions || 'Nessuna azione successiva registrata.'}</p></article>
            </div>
          </section>
          <section className="iu-wiz-panel">
            <div className="iu-wiz-panel__head"><h2>Checklist documenti</h2></div>
            <DocumentsSummary data={data} />
          </section>
          <section className="iu-wiz-panel">
            <div className="iu-wiz-panel__head"><h2>Azioni sulla sessione</h2></div>
            <div className="iu-wiz-actions">
              <JsonPostForm action={data.actions.archive} successMessage="Sessione archiviata.">
                <input type="hidden" name="_csrf_token" value={csrfToken()} />
                <button type="submit"><Archive size={16}/> Archivia sessione</button>
              </JsonPostForm>
              <button type="button" className="danger" onClick={() => setConfirmDelete((value) => !value)}><Trash2 size={16}/> Elimina sessione</button>
              {confirmDelete ? (
                <JsonPostForm action={data.actions.delete} className="iu-wiz-delete" successMessage="Sessione eliminata.">
                  <input type="hidden" name="_csrf_token" value={csrfToken()} />
                  <p>Conferma esplicita richiesta: l eliminazione e una azione irreversibile e tracciata.</p>
                  <button type="submit" className="danger"><Trash2 size={16}/> Confermo eliminazione</button>
                </JsonPostForm>
              ) : null}
            </div>
          </section>
        </div>
        <aside className="iu-wiz-step-side">
          <MatterSummary matter={data.case} />
          <section className="iu-wiz-panel">
            <div className="iu-wiz-panel__head"><h2>Collegamenti</h2></div>
            <div className="iu-wiz-context-grid single">
              <article><CalendarDays size={18}/><strong>{data.appointment?.title || 'Agenda'}</strong><span>{data.appointment?.dateLabel || 'Udienza non collegata'}</span><a href={data.actions.agenda}>Apri agenda</a></article>
              <article><FileText size={18}/><strong>Nuova scadenza</strong><span>Crea il termine successivo se emerso dall esito.</span><a href={data.actions.newDeadline}>Nuova scadenza</a></article>
              <article><CheckCircle2 size={18}/><strong>Timesheet</strong><span>Registra attivita o tempo post-udienza.</span><a href={data.actions.timesheet}>Apri timesheet</a></article>
            </div>
          </section>
        </aside>
      </section>
      <FloatingLex
        context="preparazione-udienza-riepilogo"
        title="Lex riepilogo udienza"
        body="Legge esito, checklist e azioni successive per aiutarti a tradurre il riepilogo in attivita, scadenze e note fascicolo."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex riepilogo"
        secondaryHref={data.actions.folder}
        secondaryLabel="Fascicolo"
      />
    </main>
  )
}
