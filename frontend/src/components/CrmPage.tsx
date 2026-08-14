import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  CheckCircle2,
  ChevronRight,
  Mail,
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
  const [form, setForm] = useState({ denominazione: '', codiceFiscale: '', email: '', telefono: '', fonte: 'passaparola', materia: '', esigenza: '' })
  const update = (key: string, value: string) => setForm((prev) => ({ ...prev, [key]: value }))
  const submit = async () => {
    setBusy(true)
    const result = await postJson(data.actions.nuovo, form)
    onMessage(result.message)
    setBusy(false)
    if (result.ok) { setOpen(false); onDone() }
  }
  if (!open) {
    return <button type="button" className="iu-crm-new-toggle" onClick={() => setOpen(true)}><Plus size={16}/> Nuovo contatto</button>
  }
  return (
    <div className="iu-crm-new-form" role="form" aria-label="Nuovo contatto in pipeline">
      <label><span>Nome e cognome / denominazione *</span><input value={form.denominazione} onChange={(e) => update('denominazione', e.target.value)} placeholder="Es. Rossi Mario oppure Alfa S.r.l."/></label>
      <label><span>Codice fiscale / P.IVA</span><input value={form.codiceFiscale} onChange={(e) => update('codiceFiscale', e.target.value)} placeholder="Facoltativo, migliora la verifica conflitti"/></label>
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

function LeadCard({ lead, onDone, onMessage }:{lead:CrmLead; onDone:()=>void; onMessage:(text:string)=>void}) {
  const [busy, setBusy] = useState(false)
  const [showLostReason, setShowLostReason] = useState(false)
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
        <span>{lead.fonteLabel}{lead.materia ? ` · ${lead.materia}` : ''}{lead.creatoIl ? ` · ${lead.creatoIl}` : ''}</span>
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
      {lead.motivoPerso ? <p className="iu-crm-card__lost">Motivo: {lead.motivoPerso}</p> : null}
      {showLostReason ? (
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
          {lead.stato === 'PREVENTIVO' && lead.conflitto.verificato && !lead.clienteId ? (
            <button type="button" disabled={busy} onClick={() => act(lead.actions.converti, {})}><Banknote size={14}/> Converti in cliente</button>
          ) : next ? (
            <button type="button" disabled={busy || (next === 'VINTO' && !lead.conflitto.verificato)} title={next === 'VINTO' && !lead.conflitto.verificato ? 'Prima serve la verifica conflitti (art. 24 CDF)' : undefined} onClick={() => act(lead.actions.stato, { stato: next })}>
              <ArrowRight size={14}/> {next === 'VINTO' ? 'Incarico assunto' : 'Avanza'}
            </button>
          ) : null}
          {lead.clienteId ? <a href={`/clienti?focus=${encodeURIComponent(lead.clienteId)}`}><Users size={14}/> Cliente</a> : null}
          {lead.stato !== 'PERSO' && lead.stato !== 'VINTO' ? (
            <button type="button" className="iu-crm-card__dismiss" disabled={busy} onClick={() => setShowLostReason(true)}>Perso</button>
          ) : null}
        </footer>
      )}
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
  return (
    <main className="iu-crm-page">
      <section className="iu-crm-hero">
        <div>
          <span className="iu-crm-kicker"><Sparkles size={16}/> Intake dello studio</span>
          <h1>Pipeline nuovi clienti</h1>
          <p>Dal primo contatto all'incarico: verifica conflitti ex art. 24 CDF prima dell'assunzione, preventivo scritto, conversione in anagrafica.</p>
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
        {data.columns.map((column) => (
          <div className={`iu-crm-column iu-crm-column--${column.tone}`} key={column.stato}>
            <header>
              <span>{column.label}</span>
              <Badge tone={column.tone}>{column.count}</Badge>
            </header>
            {column.leads.length ? column.leads.map((lead) => (
              <LeadCard lead={lead} onDone={load} onMessage={setMessage} key={lead.id}/>
            )) : <p className="iu-crm-column__empty"><ChevronRight size={13}/> Nessun contatto</p>}
          </div>
        ))}
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
