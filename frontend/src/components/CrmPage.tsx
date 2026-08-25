import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  LockKeyhole,
  Mail,
  PencilLine,
  Phone,
  Plus,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UserPlus,
  Users,
} from 'lucide-react'
import { Badge } from './dashboard'
import { FloatingLex } from './FloatingLex'
import { emptyCrmData, getCrmPage, type CrmData, type CrmLead } from '../crmData'
import { formatDateIt } from '../formatting'
import './CrmPage.css'

const NEXT_STATE: Record<string, string> = {
  NUOVO: 'CONTATTATO',
  CONTATTATO: 'APPUNTAMENTO',
  APPUNTAMENTO: 'PREVENTIVO',
  PREVENTIVO: 'VINTO',
}

async function postJson(href: string, body: Record<string, unknown>): Promise<{ ok: boolean; message: string }> {
  try {
    const response = await fetch(href, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({})) as { ok?: boolean; message?: string }
    return { ok: Boolean(payload.ok), message: payload.message || (response.ok ? 'Operazione completata.' : 'Operazione non riuscita.') }
  } catch {
    return { ok: false, message: 'Operazione non riuscita.' }
  }
}

function NewLeadForm({ data, onDone, onMessage }:{data:CrmData; onDone:()=>void; onMessage:(text:string)=>void}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ denominazione: '', codiceFiscale: '', partitaIva: '', email: '', telefono: '', fonte: 'passaparola', materia: '', esigenza: '' })
  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }))
  const submit = async () => {
    setBusy(true)
    const result = await postJson(data.actions.nuovo, form)
    onMessage(result.message)
    setBusy(false)
    if (result.ok) { setOpen(false); onDone() }
  }
  if (!open) {
    return <button type="button" className="iu-crm-new-toggle" onClick={() => setOpen(true)}><Plus size={16}/> Registra contatto</button>
  }
  return (
    <div className="iu-crm-new-form" role="form" aria-label="Nuovo contatto per acquisizione incarico">
      <label><span>Nome e cognome / denominazione *</span><input value={form.denominazione} onChange={(e) => update('denominazione', e.target.value)} placeholder="Es. Rossi Mario oppure Alfa S.r.l."/></label>
      <label><span>Codice fiscale</span><input value={form.codiceFiscale} onChange={(e) => update('codiceFiscale', e.target.value)} placeholder="Facoltativo, migliora la verifica conflitti"/></label>
      <label><span>Partita IVA</span><input value={form.partitaIva} onChange={(e) => update('partitaIva', e.target.value)} placeholder="Facoltativa per persona giuridica"/></label>
      <label><span>Email</span><input value={form.email} onChange={(e) => update('email', e.target.value)}/></label>
      <label><span>Telefono</span><input value={form.telefono} onChange={(e) => update('telefono', e.target.value)}/></label>
      <label><span>Fonte</span>
        <select value={form.fonte} onChange={(e) => update('fonte', e.target.value)}>
          {data.options.fonti.map((f) => <option value={f.value} key={f.value}>{f.label}</option>)}
        </select>
      </label>
      <label><span>Materia</span><input value={form.materia} onChange={(e) => update('materia', e.target.value)} placeholder="Es. lavoro, famiglia, recupero crediti"/></label>
      <label className="iu-crm-new-form__full"><span>Esigenza</span><textarea value={form.esigenza} onChange={(e) => update('esigenza', e.target.value)} rows={2} placeholder="Cosa chiede il potenziale cliente"/></label>
      <div className="iu-crm-new-form__actions">
        <button type="button" onClick={submit} disabled={busy || !form.denominazione.trim()}><UserPlus size={15}/> Registra contatto</button>
        <button type="button" className="iu-crm-new-form__cancel" onClick={() => setOpen(false)}>Annulla</button>
      </div>
    </div>
  )
}

function LeadCorrectionForm({ lead, onDone, onCancel, onMessage }:{lead:CrmLead; onDone:()=>void; onCancel:()=>void; onMessage:(text:string)=>void}) {
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    denominazione: lead.denominazione,
    codiceFiscale: lead.codiceFiscale,
    partitaIva: lead.partitaIva,
    email: lead.email,
    telefono: lead.telefono,
    materia: lead.materia,
    esigenza: lead.esigenza,
  })
  const update = (key: keyof typeof form, value: string) => setForm((previous) => ({ ...previous, [key]: value }))
  const save = async () => {
    setBusy(true)
    const result = await postJson(lead.actions.aggiorna, { ...form, fonte: lead.fonte })
    setBusy(false)
    onMessage(result.message)
    if (result.ok) { onCancel(); onDone() }
  }
  return (
    <div className="iu-crm-card__edit" role="form" aria-label={`Correggi dati di ${lead.denominazione}`}>
      <p>Correggi i dati senza perdere la richiesta. Se cambiano nominativo, codice fiscale o Partita IVA, la verifica conflitti viene ripetuta sul dato aggiornato.</p>
      <label><span>Nome e cognome / denominazione *</span><input value={form.denominazione} onChange={(event) => update('denominazione', event.target.value)}/></label>
      <label><span>Codice fiscale</span><input value={form.codiceFiscale} onChange={(event) => update('codiceFiscale', event.target.value)}/></label>
      <label><span>Partita IVA</span><input value={form.partitaIva} onChange={(event) => update('partitaIva', event.target.value)}/></label>
      <label><span>Email</span><input value={form.email} onChange={(event) => update('email', event.target.value)}/></label>
      <label><span>Telefono</span><input value={form.telefono} onChange={(event) => update('telefono', event.target.value)}/></label>
      <label><span>Materia</span><input value={form.materia} onChange={(event) => update('materia', event.target.value)}/></label>
      <label className="iu-crm-card__edit-full"><span>Esigenza</span><textarea value={form.esigenza} onChange={(event) => update('esigenza', event.target.value)} rows={2}/></label>
      <div className="iu-crm-card__edit-actions">
        <button type="button" disabled={busy || !form.denominazione.trim()} onClick={save}>Salva correzione</button>
        <button type="button" className="iu-crm-card__cancel" disabled={busy} onClick={onCancel}>Annulla</button>
      </div>
    </div>
  )
}

function ConflictClearanceForm({ lead, onDone, onCancel, onMessage }:{lead:CrmLead; onDone:()=>void; onCancel:()=>void; onMessage:(text:string)=>void}) {
  const [busy, setBusy] = useState(false)
  const [decisione, setDecisione] = useState('CLEARANCE_CONCESSA')
  const [motivazione, setMotivazione] = useState('')
  const save = async () => {
    setBusy(true)
    const result = await postJson(lead.actions.decisioneConflitto, { decisione, motivazione })
    setBusy(false)
    onMessage(result.message)
    if (result.ok) { onCancel(); onDone() }
  }
  return (
    <section className="iu-crm-clearance" role="form" aria-label={`Decisione sul conflitto per ${lead.denominazione}`}>
      <strong>Decisione professionale sul conflitto</strong>
      <p>La ricerca ha prodotto un riscontro. Registra la clearance motivata oppure l’astensione: nessuna delle due è dedotta automaticamente.</p>
      <label><span>Decisione</span><select value={decisione} onChange={(event) => setDecisione(event.target.value)}><option value="CLEARANCE_CONCESSA">Clearance concessa</option><option value="ASTENSIONE">Astensione</option></select></label>
      <label><span>Motivazione *</span><textarea value={motivazione} onChange={(event) => setMotivazione(event.target.value)} rows={2} placeholder="Motivazione professionale verificabile"/></label>
      <div><button type="button" disabled={busy || !motivazione.trim()} onClick={save}>Registra decisione</button><button type="button" className="iu-crm-card__cancel" disabled={busy} onClick={onCancel}>Annulla</button></div>
    </section>
  )
}

function EthicalWallForm({ data, lead, mode, onDone, onCancel, onMessage }:{data:CrmData; lead:CrmLead; mode:'create'|'manage'; onDone:()=>void; onCancel:()=>void; onMessage:(text:string)=>void}) {
  const wall = lead.barrieraRiservatezza
  const [busy, setBusy] = useState(false)
  const [motivazione, setMotivazione] = useState(wall.motivazione)
  const [utentiAutorizzati, setUtentiAutorizzati] = useState<string[]>(
    wall.utentiAutorizzati.length ? wall.utentiAutorizzati : [data.accesso.operatore].filter(Boolean),
  )
  const [revoca, setRevoca] = useState(false)
  const [motivazioneRevoca, setMotivazioneRevoca] = useState('')
  const toggle = (username: string) => setUtentiAutorizzati((previous) => previous.includes(username)
    ? previous.filter((item) => item !== username)
    : [...previous, username])
  const save = async () => {
    setBusy(true)
    const result = await postJson(
      mode === 'create' ? lead.actions.creaBarrieraRiservatezza : lead.actions.aggiornaBarrieraRiservatezza,
      { motivazione, utentiAutorizzati },
    )
    setBusy(false)
    onMessage(result.message)
    if (result.ok) { onCancel(); onDone() }
  }
  const revoke = async () => {
    setBusy(true)
    const result = await postJson(lead.actions.revocaBarrieraRiservatezza, { motivazione: motivazioneRevoca })
    setBusy(false)
    onMessage(result.message)
    if (result.ok) { onCancel(); onDone() }
  }
  if (revoca) {
    return (
      <section className="iu-crm-wall iu-crm-wall--revoke" role="form" aria-label={`Revoca barriera informativa per ${lead.denominazione}`}>
        <strong><LockKeyhole size={14}/> Revoca barriera informativa</strong>
        <p>La revoca riapre l’accesso al contatto per gli utenti con il normale permesso CRM. Indica il motivo: l’azione resta registrata nell’audit.</p>
        <label><span>Motivazione della revoca *</span><textarea value={motivazioneRevoca} onChange={(event) => setMotivazioneRevoca(event.target.value)} rows={2} placeholder="Es. conclusione della trattativa riservata"/></label>
        <div className="iu-crm-wall__actions"><button type="button" disabled={busy || !motivazioneRevoca.trim()} onClick={revoke}>Revoca con motivazione</button><button type="button" className="iu-crm-card__cancel" disabled={busy} onClick={() => setRevoca(false)}>Indietro</button></div>
      </section>
    )
  }
  return (
    <section className="iu-crm-wall" role="form" aria-label={`${mode === 'create' ? 'Istituisci' : 'Gestisci'} barriera informativa per ${lead.denominazione}`}>
      <strong><LockKeyhole size={14}/> {mode === 'create' ? 'Proteggi riservatezza' : 'Gestisci accessi riservati'}</strong>
      <p>La barriera limita questo contatto agli utenti autorizzati. Non sostituisce la verifica conflitti né una decisione di astensione.</p>
      <label><span>Motivazione professionale *</span><textarea value={motivazione} onChange={(event) => setMotivazione(event.target.value)} rows={2} placeholder="Es. trattativa riservata con potenziale conflitto"/></label>
      <fieldset>
        <legend>Professionisti autorizzati</legend>
        {data.options.utentiAutorizzabili.map((utente) => (
          <label key={utente.username} className="iu-crm-wall__member">
            <input type="checkbox" checked={utentiAutorizzati.includes(utente.username)} onChange={() => toggle(utente.username)}/>
            <span>{utente.label}{utente.username === data.accesso.operatore ? ' (responsabile)' : ''}</span>
          </label>
        ))}
      </fieldset>
      <div className="iu-crm-wall__actions">
        <button type="button" disabled={busy || !motivazione.trim()} onClick={save}>{mode === 'create' ? 'Istituisci barriera' : 'Salva autorizzazioni'}</button>
        {mode === 'manage' ? <button type="button" className="iu-crm-wall__revoke" disabled={busy} onClick={() => setRevoca(true)}>Revoca barriera</button> : null}
        <button type="button" className="iu-crm-card__cancel" disabled={busy} onClick={onCancel}>Annulla</button>
      </div>
    </section>
  )
}

function AmlPanel({ data, lead, onDone, onMessage }:{data:CrmData; lead:CrmLead; onDone:()=>void; onMessage:(text:string)=>void}) {
  const aml = lead.antiriciclaggio
  const [open, setOpen] = useState(Boolean(aml.id && aml.status !== 'COMPLETATA'))
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    prestazione: aml.prestazione || data.options.prestazioniAml[0]?.value || '',
    descrizionePrestazione: aml.descrizionePrestazione,
    scopoNatura: aml.scopoNatura,
    clientePep: aml.clientePep,
    paeseAltoRischio: aml.paeseAltoRischio,
    titolareNome: aml.titolareEffettivo.nome,
    titolareCodiceFiscale: aml.titolareEffettivo.codiceFiscale,
    titolareCriterio: aml.titolareEffettivo.criterio,
    titolareNote: aml.titolareEffettivo.note,
    note: aml.note,
    livello: aml.selectedLevel || aml.suggestedLevel || 'ORDINARIA',
    motivazioneScostamento: '',
  })
  const patch = (key: keyof typeof form, value: string | boolean) => setForm((previous) => ({ ...previous, [key]: value }))
  const body = {
    prestazione: form.prestazione,
    descrizionePrestazione: form.descrizionePrestazione,
    scopoNatura: form.scopoNatura,
    clientePep: form.clientePep,
    paeseAltoRischio: form.paeseAltoRischio,
    titolareEffettivo: { nome: form.titolareNome, codice_fiscale: form.titolareCodiceFiscale, criterio: form.titolareCriterio, note: form.titolareNote },
    note: form.note,
  }
  const save = async () => {
    setBusy(true)
    const result = await postJson(aml.id ? aml.actions.aggiorna : aml.actions.avvia, body)
    setBusy(false)
    onMessage(result.message)
    if (result.ok) { setOpen(false); onDone() }
  }
  const confirm = async () => {
    setBusy(true)
    const result = await postJson(aml.actions.conferma, { livello: form.livello, motivazioneScostamento: form.motivazioneScostamento })
    setBusy(false)
    onMessage(result.message)
    if (result.ok) { setOpen(false); onDone() }
  }
  const runScreening = async () => {
    setBusy(true)
    const result = await postJson(aml.actions.screening, {})
    setBusy(false)
    onMessage(result.message)
    onDone()
  }
  if (!aml.available) return null
  return (
    <section className="iu-crm-aml" aria-label={`Adeguata verifica per ${lead.denominazione}`}>
      <header><span><ClipboardCheck size={14}/> Adeguata verifica</span><Badge tone={aml.status === 'COMPLETATA' ? 'success' : aml.status === 'DA_RINNOVARE' ? 'warning' : 'neutral'}>{aml.label}</Badge></header>
      {aml.selectedLevel ? <p>Livello {aml.selectedLevel.toLowerCase()}{aml.renewalAt ? ` · rinnovo ${formatDateIt(aml.renewalAt, aml.renewalAt)}` : ''}</p> : null}
      {aml.screening.outcome ? <p className="iu-crm-aml__screening">Screening lista UE: <strong>{aml.screening.outcome.replaceAll('_', ' ').toLowerCase()}</strong>{aml.screening.matches ? ` · ${aml.screening.matches} riscontri da valutare` : ''}{aml.screening.checkedAt ? ` · ${formatDateIt(aml.screening.checkedAt, aml.screening.checkedAt)}` : ''}</p> : null}
      {aml.screening.sourceUrl ? <p className="iu-crm-aml__source">Fonte ufficiale: elenco consolidato UE delle sanzioni finanziarie{aml.screening.sourceVersion ? ` · aggiornato ${formatDateIt(aml.screening.sourceVersion, aml.screening.sourceVersion)}` : ''}{aml.screening.snapshotHash ? ` · impronta verificata ${aml.screening.snapshotHash.slice(0, 12)}…` : ''}</p> : null}
      {aml.id ? <button type="button" className="iu-crm-aml__screening-button" disabled={busy || !aml.actions.screening} onClick={runScreening}>Esegui screening lista UE</button> : null}
      {!open ? <button type="button" onClick={() => setOpen(true)}>{aml.id ? 'Apri e aggiorna verifica' : 'Avvia adeguata verifica'}</button> : (
        <div className="iu-crm-aml__form" role="form">
          <p>La scheda è SQL-first, collegata al cliente e all’intake. Identifica la prestazione e lo scopo prima della conferma.</p>
          <label><span>Prestazione *</span><select value={form.prestazione} onChange={(event) => patch('prestazione', event.target.value)}>{data.options.prestazioniAml.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>
          <label><span>Scopo e natura del rapporto *</span><input value={form.scopoNatura} onChange={(event) => patch('scopoNatura', event.target.value)} placeholder="Es. assistenza per acquisto immobile"/></label>
          <label><span>Descrizione prestazione</span><input value={form.descrizionePrestazione} onChange={(event) => patch('descrizionePrestazione', event.target.value)}/></label>
          <label><span>Titolare effettivo</span><input value={form.titolareNome} onChange={(event) => patch('titolareNome', event.target.value)} placeholder="Nome e cognome"/></label>
          <label><span>Codice fiscale titolare</span><input value={form.titolareCodiceFiscale} onChange={(event) => patch('titolareCodiceFiscale', event.target.value)}/></label>
          <label><span>Criterio titolare</span><input value={form.titolareCriterio} onChange={(event) => patch('titolareCriterio', event.target.value)} placeholder="Es. proprietà diretta 25%"/></label>
          <label className="iu-crm-aml__full"><span>Note sul titolare</span><input value={form.titolareNote} onChange={(event) => patch('titolareNote', event.target.value)}/></label>
          <label className="iu-crm-aml__check"><input type="checkbox" checked={form.clientePep} onChange={(event) => patch('clientePep', event.target.checked)}/> Cliente PEP</label>
          <label className="iu-crm-aml__check"><input type="checkbox" checked={form.paeseAltoRischio} onChange={(event) => patch('paeseAltoRischio', event.target.checked)}/> Paese terzo ad alto rischio</label>
          <label className="iu-crm-aml__full"><span>Note</span><textarea value={form.note} onChange={(event) => patch('note', event.target.value)} rows={2}/></label>
          <div className="iu-crm-aml__actions"><button type="button" disabled={busy || !form.prestazione || !form.scopoNatura.trim()} onClick={save}>{aml.id ? 'Salva verifica' : 'Crea scheda'}</button><button type="button" className="iu-crm-card__cancel" disabled={busy} onClick={() => setOpen(false)}>Chiudi</button></div>
          {aml.id && aml.inScope ? <div className="iu-crm-aml__confirmation"><label><span>Livello finale</span><select value={form.livello} onChange={(event) => patch('livello', event.target.value)}>{data.options.livelliAml.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label><label><span>Motivazione se meno rigoroso del suggerito</span><textarea value={form.motivazioneScostamento} onChange={(event) => patch('motivazioneScostamento', event.target.value)} rows={2}/></label><button type="button" disabled={busy || !form.livello} onClick={confirm}>Conferma adeguata verifica</button></div> : null}
        </div>
      )}
    </section>
  )
}

function LeadCard({ data, lead, onDone, onMessage }:{data:CrmData; lead:CrmLead; onDone:()=>void; onMessage:(text:string)=>void}) {
  const [busy, setBusy] = useState(false)
  const [showLostReason, setShowLostReason] = useState(false)
  const [showCorrection, setShowCorrection] = useState(false)
  const [showClearance, setShowClearance] = useState(false)
  const [wallMode, setWallMode] = useState<'create'|'manage'|null>(null)
  const [lostReason, setLostReason] = useState('')
  const next = NEXT_STATE[lead.stato]
  const act = async (href: string, body: Record<string, unknown>) => {
    setBusy(true)
    const result = await postJson(href, body)
    onMessage(result.message)
    setBusy(false)
    if (result.ok) onDone()
  }
  return (
    <article className="iu-crm-card">
      <header>
        <strong>{lead.denominazione}</strong>
        <Badge tone={lead.conflitto.tone}>{lead.conflitto.label}</Badge>
      </header>
      <div className="iu-crm-card__meta">
        <span>{lead.fonteLabel}{lead.materia ? ` · ${lead.materia}` : ''}{lead.creatoIl ? ` · ${formatDateIt(lead.creatoIl, lead.creatoIl)}` : ''}</span>
        {lead.email ? <span><Mail size={12}/> {lead.email}</span> : null}
        {lead.telefono ? <span><Phone size={12}/> {lead.telefono}</span> : null}
      </div>
      {lead.esigenza ? <p className="iu-crm-card__need">{lead.esigenza}</p> : null}
      {lead.conflitto.riscontri.length ? (
        <ul className="iu-crm-card__matches" aria-label="Riscontri verifica conflitti">
          {lead.conflitto.riscontri.slice(0, 3).map((r, index) => (
            <li key={`${r.etichetta}-${index}`}>
              <AlertTriangle size={12}/>
              <span>{r.tipo === 'controparte' ? 'Controparte' : r.tipo === 'cliente_esistente' ? 'Cliente' : 'Soggetto'}: {r.etichetta}{r.certo ? ' (match certo)' : ' (omonimia)'}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {lead.conflitto.clearance.label ? <p className={`iu-crm-card__clearance iu-crm-card__clearance--${lead.conflitto.clearance.convertibile ? 'ok' : 'pending'}`}>{lead.conflitto.clearance.label}</p> : null}
      {lead.barrieraRiservatezza.attiva ? <p className="iu-crm-card__wall"><LockKeyhole size={12}/>{lead.barrieraRiservatezza.label}</p> : null}
      {lead.clienteId ? <AmlPanel data={data} lead={lead} onDone={onDone} onMessage={onMessage}/> : null}
      {lead.motivoPerso ? <p className="iu-crm-card__lost">Motivo: {lead.motivoPerso}</p> : null}
      {showCorrection ? (
        <LeadCorrectionForm lead={lead} onDone={onDone} onCancel={() => setShowCorrection(false)} onMessage={onMessage}/>
      ) : showLostReason ? (
        <div className="iu-crm-card__lost-form">
          <input value={lostReason} onChange={(e) => setLostReason(e.target.value)} placeholder="Motivo della perdita (obbligatorio)"/>
          <button type="button" disabled={busy || !lostReason.trim()} onClick={() => act(lead.actions.stato, { stato: 'PERSO', motivoPerso: lostReason })}>Conferma</button>
          <button type="button" className="iu-crm-card__cancel" onClick={() => setShowLostReason(false)}>Annulla</button>
        </div>
      ) : (
        <footer>
          {!lead.conflitto.verificato ? (
            <button type="button" disabled={busy} onClick={() => act(lead.actions.verificaConflitti, {})}><ShieldCheck size={14}/> Verifica conflitti</button>
          ) : null}
          {lead.conflitto.verificato && lead.conflitto.clearance.richiesta && !lead.conflitto.clearance.decisione ? (
            <button type="button" disabled={busy} onClick={() => setShowClearance(true)}><ShieldCheck size={14}/> Decidi conflitto</button>
          ) : null}
          {lead.stato === 'PREVENTIVO' && lead.conflitto.verificato && lead.conflitto.clearance.convertibile && !lead.clienteId ? (
            <button type="button" disabled={busy} onClick={() => act(lead.actions.converti, {})}><Banknote size={14}/> Converti in cliente</button>
          ) : next ? (
            <button type="button" disabled={busy || (next === 'VINTO' && !lead.conflitto.verificato)} title={next === 'VINTO' && !lead.conflitto.verificato ? 'Prima serve la verifica conflitti (art. 24 CDF)' : undefined} onClick={() => act(lead.actions.stato, { stato: next })}>
              <ArrowRight size={14}/> {next === 'VINTO' ? 'Incarico assunto' : 'Avanza'}
            </button>
          ) : null}
          {!lead.clienteId ? <button type="button" disabled={busy} onClick={() => setShowCorrection(true)}><PencilLine size={14}/> Correggi dati</button> : null}
          {!lead.barrieraRiservatezza.attiva ? <button type="button" disabled={busy} onClick={() => setWallMode('create')}><LockKeyhole size={14}/> Proteggi riservatezza</button> : null}
          {lead.barrieraRiservatezza.attiva && lead.barrieraRiservatezza.gestibile ? <button type="button" disabled={busy} onClick={() => setWallMode('manage')}><LockKeyhole size={14}/> Gestisci accessi</button> : null}
          {lead.clienteId ? <a href={`/clienti?focus=${encodeURIComponent(lead.clienteId)}`}><Users size={14}/> Cliente</a> : null}
          {lead.stato !== 'PERSO' && lead.stato !== 'VINTO' ? (
            <button type="button" className="iu-crm-card__dismiss" disabled={busy} onClick={() => setShowLostReason(true)}>Perso</button>
          ) : null}
        </footer>
      )}
      {showClearance ? <ConflictClearanceForm lead={lead} onDone={onDone} onCancel={() => setShowClearance(false)} onMessage={onMessage}/> : null}
      {wallMode ? <EthicalWallForm data={data} lead={lead} mode={wallMode} onDone={onDone} onCancel={() => setWallMode(null)} onMessage={onMessage}/> : null}
    </article>
  )
}

export function CrmPage() {
  const [data, setData] = useState<CrmData | null>(null)
  const [message, setMessage] = useState('')
  const load = () => { getCrmPage().then(setData).catch(() => setData(emptyCrmData)) }
  useEffect(() => { load() }, [])
  if (!data) {
    return <main className="iu-crm-page"><div className="iu-crm-loading">Caricamento pipeline...</div></main>
  }
  const columnsByState = new Map(data.columns.map((column) => [column.stato, column]))
  const renderColumn = (column: CrmData['columns'][number] | undefined) => {
    if (!column) return null
    const hasAmlVerification = column.leads.some((lead) => Boolean(lead.antiriciclaggio.id))
    return (
      <div className={`iu-crm-column iu-crm-column--${column.tone}${hasAmlVerification ? ' iu-crm-column--with-aml' : ''}`} key={column.stato}>
        <header>
          <span>{column.label}</span>
          <Badge tone={column.tone}>{column.count}</Badge>
        </header>
        {column.leads.length ? column.leads.map((lead) => (
          <LeadCard data={data} lead={lead} onDone={load} onMessage={setMessage} key={lead.id}/>
        )) : <p className="iu-crm-column__empty"><ChevronRight size={13}/> Nessun contatto</p>}
      </div>
    )
  }
  return (
    <main className="iu-crm-page">
      <section className="iu-crm-hero">
        <div>
          <span className="iu-crm-kicker"><Sparkles size={16}/> Acquisizione dello studio</span>
          <h1>Acquisizione e apertura incarichi</h1>
          <p>Dal primo contatto al conferimento: verifica conflitti ex art. 24 CDF, adeguata verifica quando dovuta, preventivo e collegamento all’anagrafica.</p>
        </div>
        <div className="iu-crm-hero__stats" aria-label="Statistiche intake">
          <article><strong>{data.summary.aperti}</strong><small>In lavorazione</small></article>
          <article><strong>{data.summary.vinti}</strong><small>Incarichi</small></article>
          <article><strong><TrendingUp size={14}/> {Math.round(data.summary.tassoConversione * 100)}%</strong><small>Conversione</small></article>
        </div>
      </section>
      <div className="iu-crm-toolbar">
        <NewLeadForm data={data} onDone={load} onMessage={setMessage} />
        {data.summary.perFonte.length ? (
          <div className="iu-crm-sources" aria-label="Contatti per fonte">
            {data.summary.perFonte.slice(0, 4).map((f) => <span key={f.fonte}>{f.label}: <strong>{f.count}</strong></span>)}
          </div>
        ) : null}
      </div>
      {message ? <p className="iu-crm-message" role="status"><CheckCircle2 size={15}/> {message}</p> : null}
      <section className="iu-crm-board" aria-label="Pipeline per stato">
        <div className="iu-crm-board__early">
          {renderColumn(columnsByState.get('NUOVO'))}
          {renderColumn(columnsByState.get('CONTATTATO'))}
          {renderColumn(columnsByState.get('APPUNTAMENTO'))}
        </div>
        <div className="iu-crm-board__outcomes">
          <div className="iu-crm-board__pending">
            {renderColumn(columnsByState.get('PREVENTIVO'))}
            {renderColumn(columnsByState.get('PERSO'))}
          </div>
          {renderColumn(columnsByState.get('VINTO'))}
        </div>
      </section>
      {data.fonteDeontologica ? <p className="iu-crm-footnote">{data.fonteDeontologica}</p> : null}
      <FloatingLex
        context="crm-intake"
        title="Lex AI intake"
        body="Posso aiutarti a inquadrare la richiesta del potenziale cliente, suggerire la materia e ricordarti i controlli deontologici prima dell'incarico."
        primaryHref="#lex"
        primaryLabel="Apri Lex intake"
        secondaryHref="/preventivi/nuovo"
        secondaryLabel="Nuovo preventivo"
      />
    </main>
  )
}

export default CrmPage
