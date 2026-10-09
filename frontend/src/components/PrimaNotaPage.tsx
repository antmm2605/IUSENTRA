import { useEffect, useRef, useState } from 'react'
import { ArrowDownCircle, ArrowUpCircle, Banknote, CheckCircle2, AlertCircle, FileDown, Landmark, Link2, Plus, RefreshCw, RotateCcw, Scale, Upload } from 'lucide-react'
import { FloatingLex } from './FloatingLex'
import { getPrimaNotaPage, type PrimaNotaData, type PrimaNotaMovimento, type RiconciliazioneProposta } from '../primaNotaData'
import { RiepilogoAnnuale } from './prima-nota/RiepilogoAnnuale'
import { formatDateInputIt, formatDateIt, formatEuroIt } from '../formatting'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { loadPendingCommand, savePendingCommand, clearPendingCommand, type PendingPrimaNotaCommand } from '../primaNotaCommand'
import './PrimaNotaPage.css'

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function postJson(href: string, body: Record<string, unknown>): Promise<{ ok: boolean; message: string; status: number; movementId?: string }> {
  try {
    const response = await fetch(href, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({})) as { ok?: boolean; message?: string; movimentoId?: string }
    const ok = response.ok && payload.ok === true
    return { ok, status: response.status, movementId: payload.movimentoId, message: payload.message || (ok ? 'Operazione completata.' : 'Esito non confermato. Verifica il salvataggio prima di riprovare.') }
  } catch {
    return { ok: false, status: 0, message: 'Connessione interrotta: verifica il salvataggio per recuperare l’esito senza duplicarlo.' }
  }
}

function NewMovementForm({ data, onDone, onMessage }:{data:PrimaNotaData; onDone:()=>void; onMessage:(text:string, ok?:boolean)=>void}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState(() => ({ data: formatDateInputIt(new Date()), tipo: 'INCASSO', importo: '', categoria: 'onorari', controparte: '', causale: '', metodo: 'banca', documento: '' }))
  const pending = useRef<PendingPrimaNotaCommand | null>(null)
  const submitting = useRef(false)
  const loadedScope = useRef('')
  const [uncertain, setUncertain] = useState(false)
  const [recoveryError, setRecoveryError] = useState('')
  useEffect(() => {
    const scope = data.writeProtocol?.scope
    if (!data.writeProtocol?.persistentCommands || !scope || loadedScope.current === scope) return
    loadedScope.current = scope
    try {
      const command = loadPendingCommand(sessionStorage, scope)
      if (command) {
        pending.current = command
        setForm(command.body as typeof form)
        setOpen(true); setUncertain(true)
      }
    } catch { setRecoveryError('Impossibile recuperare il comando pendente. La registrazione è sospesa per evitare doppioni.') }
  }, [data.writeProtocol?.scope, data.writeProtocol?.persistentCommands])
  const retryRecovery = () => {
    const scope = data.writeProtocol?.scope
    if (!scope) return
    try {
      const stored = loadPendingCommand(sessionStorage,scope)
      if (stored) { pending.current = stored; setForm(stored.body as typeof form); setUncertain(true) }
      else if (pending.current) savePendingCommand(sessionStorage,pending.current)
      setRecoveryError('')
    } catch { setRecoveryError('Recupero non riuscito. La bozza resta conservata: riprova quando l’archivio del browser è disponibile.') }
  }
  const update = (key: string, value: string) => setForm((prev) => {
    const next = { ...prev, [key]: value }
    if (key === 'tipo') next.categoria = value === 'INCASSO' ? 'onorari' : 'anticipazioni_clienti'
    return next
  })
  const categorie = form.tipo === 'INCASSO' ? data.options.categorieIncasso : data.options.categoriePagamento
  const submit = async () => {
    if (submitting.current || recoveryError) return
    submitting.current = true; setBusy(true)
    let body: Record<string, unknown> = { ...form, importo: form.importo.replace(',', '.') }
    const protocol = data.writeProtocol
    try {
      if (protocol?.persistentCommands) {
        if (!protocol.scope || protocol.revision === null) throw new Error('Contesto del comando incompleto.')
        if (!pending.current) {
          const command = {scope: protocol.scope, commandKey: crypto.randomUUID(), expectedRevision: protocol.revision,
            body: body as Record<string,string>}
          savePendingCommand(sessionStorage, command)
          pending.current = command
        }
        if (pending.current.scope !== protocol.scope) throw new Error('Comando appartenente a un altro contesto.')
        body = {...pending.current.body, commandKey: pending.current.commandKey, expectedRevision: pending.current.expectedRevision}
        setUncertain(true)
      }
      const result = await postJson(data.actions.registra, body)
      const confirmed = result.ok && (!protocol?.persistentCommands || Boolean(result.movementId))
      const rejected = !result.ok && [400, 401, 403, 409, 428].includes(result.status)
      if (confirmed || rejected) {
        if (pending.current) clearPendingCommand(sessionStorage, pending.current.scope)
        pending.current = null; setUncertain(false)
      }
      onMessage(confirmed ? result.message : result.ok ? 'Risposta incompleta: verifica il salvataggio prima di procedere.' : result.message, confirmed)
      if (confirmed) {
        setOpen(false); setForm(prev => ({...prev, importo: '', controparte: '', causale: '', documento: ''})); onDone()
      } else if (result.status === 409 || result.status === 428) onDone()
    } catch {
      setRecoveryError('Impossibile conservare o recuperare il comando. La bozza resta aperta; la registrazione è sospesa per evitare doppioni.')
    } finally { submitting.current = false; setBusy(false) }
  }

  if (!open) {
    return <button type="button" className="iu-pn-new-toggle" onClick={() => setOpen(true)}><Plus size={16}/> Nuovo movimento</button>
  }
  return (
    <>
    <fieldset className="iu-pn-form" disabled={busy || uncertain || Boolean(recoveryError)} aria-label="Nuovo movimento di prima nota">
      <label><span>Data</span><input type="date" value={form.data} onChange={(e) => update('data', e.target.value)}/></label>
      <label><span>Tipo</span>
        <select value={form.tipo} onChange={(e) => update('tipo', e.target.value)}>
          <option value="INCASSO">Incasso</option>
          <option value="PAGAMENTO">Pagamento</option>
        </select>
      </label>
      <label><span>Importo (€)</span><input inputMode="decimal" value={form.importo} onChange={(e) => update('importo', e.target.value)} placeholder="0,00"/></label>
      <label><span>Categoria</span>
        <select value={form.categoria} onChange={(e) => update('categoria', e.target.value)}>
          {categorie.map((c) => <option value={c.value} key={c.value}>{c.label}</option>)}
        </select>
      </label>
      <label><span>Controparte</span><input value={form.controparte} onChange={(e) => update('controparte', e.target.value)} placeholder="Cliente, fornitore, erario..."/></label>
      <label><span>Metodo</span>
        <select value={form.metodo} onChange={(e) => update('metodo', e.target.value)}>
          {data.options.metodi.map((m) => <option value={m.value} key={m.value}>{m.label}</option>)}
        </select>
      </label>
      <label className="iu-pn-form__full"><span>Causale</span><input value={form.causale} onChange={(e) => update('causale', e.target.value)} placeholder="Es. Saldo parcella 12/2026"/></label>
      <label><span>Documento</span><input value={form.documento} onChange={(e) => update('documento', e.target.value)} placeholder="N. fattura/ricevuta"/></label>
    </fieldset>
    {!busy && (uncertain || recoveryError) ? <p className="iu-pn-command-status" role="status">{recoveryError || 'Salvataggio da verificare. La bozza è conservata: recupera l’esito prima di modificarla.'}</p> : null}
    <div className="iu-pn-form__actions">
      {recoveryError ? <button type="button" onClick={retryRecovery} disabled={busy}><RefreshCw size={15}/> Riprova recupero</button> : null}
      <button type="button" onClick={submit} disabled={busy || Boolean(recoveryError) || !form.importo.trim()}><Banknote size={15}/> {busy ? 'Operazione in corso…' : uncertain ? 'Verifica salvataggio' : 'Registra'}</button>
      <button type="button" className="iu-pn-form__cancel" disabled={busy || uncertain || Boolean(recoveryError)} onClick={() => setOpen(false)}>Annulla</button>
    </div>
    </>
  )
}

function BankReconciliation({ data, onDone, onMessage }:{data:PrimaNotaData; onDone:()=>void; onMessage:(text:string, ok?:boolean)=>void}) {
  const [proposte, setProposte] = useState<RiconciliazioneProposta[]>([])
  const [conteggi, setConteggi] = useState('')
  const [busy, setBusy] = useState(false)
  const [scelte, setScelte] = useState<Record<string, string>>({})
  const analizza = async (file: File) => {
    setBusy(true); setProposte([])
    try {
      const form = new FormData()
      form.append('estratto', file)
      const response = await fetch(data.actions.analizzaEstratto, {
        method: 'POST', credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: form,
      })
      const payload = await response.json().catch(() => ({})) as { ok?:boolean; message?:string; proposte?:RiconciliazioneProposta[]; avvisi?:string[]; conteggi?:{abbinamenti:number;ambigui:number;nuovi:number} }
      if (!payload.ok) { onMessage(payload.message || 'Analisi non riuscita.', false); return }
      setProposte(Array.isArray(payload.proposte) ? payload.proposte : [])
      const c = payload.conteggi
      setConteggi(c ? `${c.abbinamenti} abbinamenti proposti · ${c.ambigui} da scegliere · ${c.nuovi} nuovi movimenti` : '')
      if (payload.avvisi?.length) onMessage(`Analisi completata con ${payload.avvisi.length} righe saltate.`)
    } catch { onMessage('Analisi non riuscita.', false) } finally { setBusy(false) }
  }
  const conferma = async (proposta: RiconciliazioneProposta, movimentoId: string) => {
    setBusy(true)
    // Importo e verso della riga viaggiano insieme all'abbinamento: il server
    // li riverifica contro il movimento (il client non e' fidato).
    const result = await postJson(data.actions.confermaRiconciliazione, {
      movimentoId,
      rigaId: proposta.riga.id,
      importoRiga: proposta.riga.importo,
      versoRiga: proposta.riga.verso,
    })
    onMessage(result.message, result.ok)
    setBusy(false)
    if (result.ok) { setProposte((prev) => prev.filter((p) => p.riga.id !== proposta.riga.id)); onDone() }
  }
  const registraNuovo = async (proposta: RiconciliazioneProposta) => {
    setBusy(true)
    const result = await postJson('/prima-nota/riconciliazione/registra-da-riga', {
      rigaId: proposta.riga.id,
      data: proposta.riga.data,
      verso: proposta.riga.verso,
      importo: Math.abs(proposta.riga.importo),
      descrizione: proposta.riga.descrizione,
    })
    onMessage(result.message, result.ok)
    setBusy(false)
    if (result.ok) { setProposte((prev) => prev.filter((p) => p.riga.id !== proposta.riga.id)); onDone() }
  }
  return (
    <section className="iu-pn-recon" aria-label="Riconciliazione bancaria">
      <header>
        <span><Landmark size={16}/> Riconciliazione bancaria</span>
        <small>Carica l'estratto conto CSV: il sistema propone gli abbinamenti, confermi tu movimento per movimento. {data.nonRiconciliati ? `${data.nonRiconciliati} movimenti non ancora riconciliati.` : ''}</small>
      </header>
      <label className="iu-pn-recon__upload">
        <Upload size={15}/> {busy ? 'Analisi in corso...' : "Carica estratto conto (CSV)"}
        <input type="file" accept=".csv,.txt" hidden disabled={busy} onChange={(e) => { const file = e.target.files?.[0]; if (file) analizza(file); e.target.value = '' }}/>
      </label>
      {conteggi ? <p className="iu-pn-recon__counts">Analisi del file: {conteggi}. Proposte ancora da gestire: {proposte.filter((p) => p.tipo !== 'gia_riconciliato').length}.</p> : null}
      {proposte.length ? (
        <ul className="iu-pn-recon__list">
          {proposte.map((proposta) => (
            <li key={proposta.riga.id} className={`iu-pn-recon__item iu-pn-recon__item--${proposta.tipo}`}>
              <div className="iu-pn-recon__row">
                <strong>{formatDateIt(proposta.riga.data)} · {formatEuroIt(proposta.riga.importo)}</strong>
                <span>{proposta.riga.descrizione || '(senza descrizione)'}</span>
              </div>
              <div className="iu-pn-recon__actions">
                {proposta.tipo === 'abbinamento' && proposta.movimento ? (
                  <button type="button" disabled={busy} onClick={() => conferma(proposta, proposta.movimento!.id)}>
                    <Link2 size={14}/> Abbina a: {proposta.movimento.causale || formatDateIt(proposta.movimento.data)}
                  </button>
                ) : null}
                {proposta.tipo === 'ambiguo' ? (
                  <span className="iu-pn-recon__choose">
                    <select value={scelte[proposta.riga.id] || ''} onChange={(e) => setScelte((prev) => ({ ...prev, [proposta.riga.id]: e.target.value }))}>
                      <option value="">Scegli il movimento...</option>
                      {proposta.candidati.map((c) => <option value={c.id} key={c.id}>{formatDateIt(c.data)} · {c.causale || c.id}</option>)}
                    </select>
                    <button type="button" disabled={busy || !scelte[proposta.riga.id]} onClick={() => conferma(proposta, scelte[proposta.riga.id])}><Link2 size={14}/> Abbina</button>
                  </span>
                ) : null}
                {proposta.tipo === 'gia_riconciliato' ? <span>Già riconciliato · movimento {proposta.movimento?.id}</span> : null}
                {proposta.tipo === 'nuovo_movimento' ? (
                  <button type="button" disabled={busy} onClick={() => registraNuovo(proposta)}><Plus size={14}/> Registra in prima nota</button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

function MovementRow({ movimento, onDone, onMessage }:{movimento:PrimaNotaMovimento; onDone:()=>void; onMessage:(text:string, ok?:boolean)=>void}) {
  const [showStorno, setShowStorno] = useState(false)
  const [motivo, setMotivo] = useState('')
  const [busy, setBusy] = useState(false)
  const storna = async () => {
    setBusy(true)
    const result = await postJson(movimento.actions.storna, { motivo })
    onMessage(result.message, result.ok)
    setBusy(false)
    if (result.ok) { setShowStorno(false); onDone() }
  }
  return (
    <tr className={movimento.tipo === 'INCASSO' ? 'iu-pn-row--in' : 'iu-pn-row--out'}>
      <td>{formatDateIt(movimento.data)}</td>
      <td>
        <span className="iu-pn-tipo">
          {movimento.tipo === 'INCASSO' ? <ArrowDownCircle size={14}/> : <ArrowUpCircle size={14}/>}
          {movimento.tipo === 'INCASSO' ? 'Incasso' : 'Pagamento'}
        </span>
      </td>
      <td className="iu-pn-amount">{movimento.importoLabel}</td>
      <td>{movimento.categoriaLabel}</td>
      <td className="iu-pn-desc"><strong>{movimento.controparte || '—'}</strong><span>{movimento.causale}</span></td>
      <td>{movimento.metodo}</td>
      <td>
        {showStorno ? (
          <span className="iu-pn-storno">
            <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo storno"/>
            <button type="button" disabled={busy || !motivo.trim()} onClick={storna}>Conferma</button>
            <button type="button" className="iu-pn-storno__cancel" onClick={() => setShowStorno(false)}>Annulla</button>
          </span>
        ) : movimento.stornabile ? (
          <button type="button" className="iu-pn-storna-btn" title="Storna con movimento contrario" onClick={() => setShowStorno(true)}><RotateCcw size={14}/></button>
        ) : null}
      </td>
    </tr>
  )
}

export function PrimaNotaPage() {
  const [data, setData] = useState<PrimaNotaData | null>(null)
  const [message, setMessage] = useState('')
  const [messageOk, setMessageOk] = useState(true)
  const showMessage = (text: string, ok = true) => { setMessage(text); setMessageOk(ok) }
  const [loadError, setLoadError] = useState('')
  const requestVersion = useRef(0)
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [filters, setFilters] = useState({ dal: '', al: '', tipo: '' })
  const load = (next = filters) => {
    const version = ++requestVersion.current
    return getPrimaNotaPage(Object.fromEntries(Object.entries(next).filter(([, v]) => v))).then((result) => {
      if (version !== requestVersion.current) return false
      setData(result)
      setLoadError('')
      setRefreshVersion((previous) => previous + 1)
      return true
    }).catch((error: unknown) => {
      if (version === requestVersion.current) setLoadError(error instanceof Error ? error.message : 'Prima nota non disponibile.')
      return false
    })
  }
  useOperationalRefresh(['incassi', 'fatturazione'], () => load())
  useEffect(() => { load() }, [])
  const riconcilia = async () => {
    if (!data) return
    const result = await postJson(data.actions.riconcilia, {})
    showMessage(result.message, result.ok)
    if (result.ok) load()
  }
  if (loadError && !data) {
    return <main className="iu-pn-page"><section className="iu-pn-load-error" role="alert">
      <h1>Prima nota non disponibile</h1><p>{loadError}</p>
      <p>I saldi non vengono mostrati finché il registro non è leggibile.</p>
      <button type="button" className="iu-pn-new-toggle" onClick={() => load()}><RefreshCw size={16}/> Riprova il caricamento</button>
    </section></main>
  }
  if (!data) {
    return <main className="iu-pn-page"><div className="iu-pn-loading">Caricamento prima nota...</div></main>
  }
  const exportHref = `${data.actions.esporta}${filters.dal || filters.al ? `?dal=${filters.dal}&al=${filters.al}` : ''}`
  return (
    <main className={`iu-pn-page${loadError ? ' iu-pn-page--unavailable' : ''}`}>
      {loadError ? <section className="iu-pn-load-error" role="alert">
        <h1>Prima nota non disponibile</h1><p>{loadError}</p>
        <p>La bozza resta aperta. Saldi e registrazioni sono sospesi fino al recupero del caricamento.</p>
        <button type="button" className="iu-pn-new-toggle" onClick={() => load()}><RefreshCw size={16}/> Riprova il caricamento</button>
      </section> : null}
      <fieldset className="iu-pn-content" disabled={Boolean(loadError)}>
      <section className="iu-pn-hero">
        <div>
          <span className="iu-pn-kicker"><Scale size={16}/> Contabilità di studio</span>
          <h1>Prima nota</h1>
          <p>Registro cronologico di incassi e pagamenti per principio di cassa: storni tracciati, riconciliazione con le parcelle, riepilogo dell'anno, registro delle fatture emesse ed export per il commercialista.</p>
        </div>
        <div className="iu-pn-hero__stats" aria-label="Saldi del periodo">
          <article><strong>{data.summary.incassiLabel}</strong><small>Incassi</small></article>
          <article><strong>{data.summary.pagamentiLabel}</strong><small>Pagamenti</small></article>
          <article className={data.summary.saldo >= 0 ? 'iu-pn-stat--ok' : 'iu-pn-stat--neg'}><strong>{data.summary.saldoLabel}</strong><small>Saldo</small></article>
        </div>
      </section>

      <div className="iu-pn-toolbar">
        <NewMovementForm data={data} onDone={() => load()} onMessage={showMessage} />
        <div className="iu-pn-toolbar__side">
          <label><span>Dal</span><input type="date" value={filters.dal} onChange={(e) => { const next = { ...filters, dal: e.target.value }; setFilters(next); load(next) }}/></label>
          <label><span>Al</span><input type="date" value={filters.al} onChange={(e) => { const next = { ...filters, al: e.target.value }; setFilters(next); load(next) }}/></label>
          <button type="button" onClick={riconcilia}><RefreshCw size={15}/> Riconcilia parcelle</button>
          {!loadError ? <a href={exportHref}><FileDown size={15}/> Esporta CSV</a> : null}
        </div>
      </div>

      {message ? <p className={`iu-pn-message${messageOk ? '' : ' iu-pn-message--error'}`} role={messageOk ? 'status' : 'alert'}>{messageOk ? <CheckCircle2 size={15}/> : <AlertCircle size={15}/>} {message}</p> : null}

      <RiepilogoAnnuale refreshVersion={refreshVersion}/>

      <BankReconciliation data={data} onDone={() => load()} onMessage={showMessage} />

      {data.summary.perCategoria.length ? (
        <div className="iu-pn-categories" aria-label="Totali per categoria">
          {data.summary.perCategoria.slice(0, 6).map((c) => <span key={c.categoria}>{c.label}: <strong>{c.importoLabel}</strong></span>)}
        </div>
      ) : null}

      <section className="iu-pn-table-card">
        <div className="iu-pn-table-wrap">
          <table aria-label="Registro cronologico">
            <thead>
              <tr><th>Data</th><th>Tipo</th><th>Importo</th><th>Categoria</th><th>Controparte / causale</th><th>Metodo</th><th><span className="sr-only">Azioni</span></th></tr>
            </thead>
            <tbody>
              {data.movimenti.length ? data.movimenti.map((movimento) => (
                <MovementRow movimento={movimento} onDone={() => load()} onMessage={showMessage} key={movimento.id}/>
              )) : (
                <tr><td colSpan={7} className="iu-pn-empty">Nessun movimento nel periodo: registra il primo o riconcilia le parcelle pagate.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {data.avvertenza ? <p className="iu-pn-footnote">{data.avvertenza}</p> : null}
      </fieldset>
      <FloatingLex
        context="prima-nota"
        title="Lex AI contabilità"
        body="Posso aiutarti a inquadrare un movimento (onorario, anticipazione art. 15, spesa) e ricordarti cosa portare al commercialista."
        primaryHref="#lex"
        primaryLabel="Apri Lex contabilità"
        secondaryHref="/fatturazione"
        secondaryLabel="Fatturazione"
      />
    </main>
  )
}

export default PrimaNotaPage
