import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CalendarDays, CheckCircle2, ClipboardCheck, FileText, Gavel, PenLine } from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { JsonPostForm } from './JsonPostForm'
import { MatterSummary, WizardStepper, csrfToken } from './WizardProShared'
import { getWizardProStepPage, type WizardProDocument, type WizardProStepData } from '../wizardProData'
import './WizardProPage.css'

const stepLexContext: Record<number, string> = {
  1: 'preparazione-udienza-briefing',
  2: 'preparazione-udienza-documenti',
  3: 'preparazione-udienza-strategia',
  4: 'preparazione-udienza-precheck',
  5: 'preparazione-udienza-esito',
}

function LinkedRows({ data }: { data: WizardProStepData }) {
  return (
    <section className="iu-wiz-panel">
      <div className="iu-wiz-panel__head">
        <div>
          <span className="iu-wiz-kicker">Contesto operativo</span>
          <h2>Udienze, scadenze e attivita</h2>
        </div>
      </div>
      <div className="iu-wiz-context-grid">
        <article>
          <CalendarDays size={18}/>
          <strong>{data.appointment?.title || 'Udienza non collegata'}</strong>
          <span>{data.appointment?.dateLabel || data.case?.nextHearingLabel || 'Data non indicata'}</span>
          {data.appointment?.href ? <a href={data.appointment.href}>Apri agenda</a> : <a href={data.actions.agenda}>Apri agenda</a>}
        </article>
        <article>
          <ClipboardCheck size={18}/>
          <strong>{data.deadlines.length} scadenze collegate</strong>
          <span>{data.emptyStates.noDeadlines ? 'Nessuna scadenza aperta nel perimetro corrente.' : 'Verifica termini e avvisi prima dell udienza.'}</span>
          <a href={data.actions.deadlines}>Apri scadenziario</a>
        </article>
        <article>
          <FileText size={18}/>
          <strong>{data.caseDocuments.length} documenti fascicolo</strong>
          <span>{data.missingDocuments.length ? `${data.missingDocuments.length} documenti da presidiare` : 'Nessun documento mancante nella checklist.'}</span>
          {data.case?.documentsHref ? <a href={data.case.documentsHref}>Apri documenti</a> : null}
        </article>
      </div>
    </section>
  )
}

function DocumentsList({ documents }: { documents: WizardProDocument[] }) {
  if (!documents.length) {
    return <div className="iu-wiz-empty small"><FileText size={22}/><strong>Nessun documento in checklist</strong><span>Puoi aggiungere un documento extra nel form.</span></div>
  }
  return (
    <div className="iu-wiz-docs">
      {documents.map((doc) => (
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

function Step1({ data }: { data: WizardProStepData }) {
  return (
    <JsonPostForm className="iu-wiz-panel iu-wiz-form" action={data.actions.form} successMessage="Briefing salvato.">
      <input type="hidden" name="_csrf_token" value={csrfToken()} />
      <label>
        <span>Note briefing fascicolo</span>
        <textarea name="step1_note" defaultValue={data.fields.step1_note} rows={7} placeholder="Punti da verificare, indicazioni del cliente, criticita del fascicolo." />
      </label>
      <div className="iu-wiz-actions">
        <button type="submit">Salva e vai allo step 2</button>
        {data.case?.href ? <a href={data.case.href}>Apri fascicolo</a> : null}
        <a href={data.actions.agenda}>Apri agenda</a>
      </div>
    </JsonPostForm>
  )
}

function Step2({ data }: { data: WizardProStepData }) {
  return (
    <JsonPostForm className="iu-wiz-panel iu-wiz-form" action={data.actions.form} successMessage="Documenti salvati.">
      <input type="hidden" name="_csrf_token" value={csrfToken()} />
      <DocumentsList documents={data.documents} />
      <div className="iu-wiz-doc-edit">
        {data.documents.map((doc) => (
          <fieldset key={`edit-${doc.index}`}>
            <legend>{doc.label}</legend>
            <label>
              <span>Stato documento</span>
              <select name={`doc_stato_${doc.index}`} defaultValue={doc.status}>
                <option value="da_portare">Da portare</option>
                <option value="pronto">Pronto</option>
                <option value="non_necessario">Non necessario</option>
              </select>
            </label>
            <label>
              <span>Note documento</span>
              <input name={`doc_note_${doc.index}`} defaultValue={doc.notes} placeholder="Note operative" />
            </label>
          </fieldset>
        ))}
      </div>
      <label>
        <span>Documento extra</span>
        <input name="doc_extra_label" placeholder="Aggiungi documento da portare" />
      </label>
      <div className="iu-wiz-actions">
        <button type="submit">Salva e vai allo step 3</button>
        {data.case?.href ? <a href={data.case.href}>Apri fascicolo</a> : null}
      </div>
    </JsonPostForm>
  )
}

function Step3({ data }: { data: WizardProStepData }) {
  return (
    <JsonPostForm className="iu-wiz-panel iu-wiz-form" action={data.actions.form} successMessage="Strategia salvata.">
      <input type="hidden" name="_csrf_token" value={csrfToken()} />
      <div className="iu-wiz-warning">
        <PenLine size={18}/>
        <span>Compila strategia, richieste ed eccezioni in modo verificabile: il salvataggio resta tracciato nello studio.</span>
      </div>
      <label>
        <span>Note preparazione</span>
        <textarea name="note_preparazione" defaultValue={data.fields.note_preparazione} rows={4} />
      </label>
      <label>
        <span>Argomenti principali</span>
        <textarea name="argomenti_principali" defaultValue={data.fields.argomenti_principali} rows={4} />
      </label>
      <label>
        <span>Richieste al giudice</span>
        <textarea name="richieste_giudice" defaultValue={data.fields.richieste_giudice} rows={4} />
      </label>
      <label>
        <span>Eccezioni da sollevare</span>
        <textarea name="eccezioni_da_sollevare" defaultValue={data.fields.eccezioni_da_sollevare} rows={4} />
      </label>
      <div className="iu-wiz-actions"><button type="submit">Salva e vai allo step 4</button></div>
    </JsonPostForm>
  )
}

function Step4({ data }: { data: WizardProStepData }) {
  const hasMissing = data.missingDocuments.length > 0
  return (
    <JsonPostForm className="iu-wiz-panel iu-wiz-form" action={data.actions.form} successMessage="Pre-controlli salvati.">
      <input type="hidden" name="_csrf_token" value={csrfToken()} />
      {hasMissing ? <div className="iu-wiz-warning danger"><AlertTriangle size={18}/><span>Ci sono documenti ancora da portare o verificare prima della partenza.</span></div> : null}
      <div className="iu-wiz-precheck">
        <label><input type="checkbox" name="precheck_firma_ok" value="1" defaultChecked={data.fields.precheck_firma_ok} /><span>Firma digitale verificata</span></label>
        <label><input type="checkbox" name="precheck_docs_pronti" value="1" defaultChecked={data.fields.precheck_docs_pronti} /><span>Documenti pronti</span></label>
        <label><input type="checkbox" name="precheck_cliente_notificato" value="1" defaultChecked={data.fields.precheck_cliente_notificato} /><span>Cliente notificato</span></label>
        <label><input type="checkbox" name="precheck_trasporto_ok" value="1" defaultChecked={data.fields.precheck_trasporto_ok} /><span>Trasporto o collegamento confermato</span></label>
      </div>
      <label>
        <span>Note pre-partenza</span>
        <textarea name="precheck_note" defaultValue={data.fields.precheck_note} rows={4} />
      </label>
      <div className="iu-wiz-actions">
        <button type="submit">Salva e vai allo step 5</button>
        <a href={data.actions.signature}>Guida firma digitale</a>
        <a href={data.actions.agenda}>Apri agenda</a>
      </div>
    </JsonPostForm>
  )
}

function Step5({ data }: { data: WizardProStepData }) {
  return (
    <JsonPostForm className="iu-wiz-panel iu-wiz-form" action={data.actions.form} successMessage="Preparazione completata.">
      <input type="hidden" name="_csrf_token" value={csrfToken()} />
      <div className="iu-wiz-warning">
        <Gavel size={18}/>
        <span>Il completamento puo aggiornare il fascicolo se confermi il relativo campo.</span>
      </div>
      <label>
        <span>Esito</span>
        <select name="esito" defaultValue={data.fields.esito} required>
          <option value="">Seleziona esito</option>
          {data.esiti.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
        </select>
      </label>
      <label>
        <span>Data rinvio</span>
        <input type="date" name="esito_rinvio_data" defaultValue={data.fields.esito_rinvio_data} />
      </label>
      <label>
        <span>Note verbale</span>
        <textarea name="esito_note_verbale" defaultValue={data.fields.esito_note_verbale} rows={4} />
      </label>
      <label>
        <span>Azioni successive</span>
        <textarea name="esito_azioni" defaultValue={data.fields.esito_azioni} rows={4} />
      </label>
      <label className="iu-wiz-check">
        <input type="checkbox" name="esito_aggiorna_fascicolo" value="1" defaultChecked={data.fields.esito_aggiorna_fascicolo} />
        <span>Aggiorna il fascicolo con l esito udienza</span>
      </label>
      <div className="iu-wiz-actions"><button type="submit">Completa preparazione</button></div>
    </JsonPostForm>
  )
}

function StepBody({ data }: { data: WizardProStepData }) {
  if (data.currentStep === 2) return <Step2 data={data} />
  if (data.currentStep === 3) return <Step3 data={data} />
  if (data.currentStep === 4) return <Step4 data={data} />
  if (data.currentStep === 5) return <Step5 data={data} />
  return <Step1 data={data} />
}

export function WizardProStepPage() {
  const [data, setData] = useState<WizardProStepData | null>(null)
  useEffect(() => {
    let active = true
    getWizardProStepPage().then((payload) => { if (active) setData(payload) })
    return () => { active = false }
  }, [])
  const lexContext = useMemo(() => stepLexContext[data?.currentStep || 1] || 'preparazione-udienza', [data?.currentStep])

  if (!data) {
    return <main className="iu-wiz-page"><div className="iu-wiz-loading">Caricamento step preparazione...</div></main>
  }

  return (
    <main className="iu-wiz-page iu-wiz-step-page">
      <section className="iu-wiz-hero">
        <div>
          <span className="iu-wiz-kicker"><Gavel size={16}/> Preparazione Udienza Guidata</span>
          <h1>Step {data.currentStep}: {data.currentStepLabel}</h1>
          <p>{data.session?.title || 'Sessione di preparazione udienza'}</p>
        </div>
        <div className="iu-wiz-hero__actions">
          {data.case?.href ? <a href={data.case.href}>Apri fascicolo</a> : null}
          <a href={data.actions.agenda}>Agenda</a>
          <a href={data.actions.deadlines}>Scadenziario</a>
        </div>
      </section>
      <WizardStepper steps={data.steps} />
      <section className="iu-wiz-step-layout">
        <div className="iu-wiz-step-main">
          <StepBody data={data} />
        </div>
        <aside className="iu-wiz-step-side">
          <MatterSummary matter={data.case} />
          <LinkedRows data={data} />
        </aside>
      </section>
      <FloatingLex
        context={lexContext}
        title="Lex udienza"
        body="Legge il contesto dello step corrente e aiuta a controllare fascicolo, documenti, strategia ed esito."
        primaryHref={data.actions.lex}
        primaryLabel="Apri Lex udienza"
        secondaryHref={data.actions.folder}
        secondaryLabel="Fascicolo"
      />
    </main>
  )
}
