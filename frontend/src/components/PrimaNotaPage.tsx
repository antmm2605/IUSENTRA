import { useEffect, useState } from 'react'
import { ArrowDownCircle, ArrowUpCircle, Banknote, CheckCircle2, FileDown, Landmark, Link2, Plus, RefreshCw, RotateCcw, Scale, Upload } from 'lucide-react'
import { FloatingLex } from './FloatingLex'
import { emptyPrimaNotaData, getPrimaNotaPage, type PrimaNotaData, type PrimaNotaMovimento, type RiconciliazioneProposta } from '../primaNotaData'
import './PrimaNotaPage.css'

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''
}

async function postJson(href: string, body: Record<string, unknown>): Promise<{ ok: boolean; message: string }> {
  try {
    const response = await fetch(href, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken() },
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({})) as { ok?: boolean; message?: string }
    return { ok: Boolean(payload.ok), message: payload.message || (response.ok ? 'Operazione completata.' : 'Operazione non riuscita.') }
  } catch {
    return { ok: false, message: 'Operazione non riuscita.' }
  }
}

function NewMovementForm({ data, onDone, onMessage }:{data:PrimaNotaData; onDone:()=>void; onMessage:(text:string)=>void}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ data: new Date().toISOString().slice(0, 10), tipo: 'INCASSO', importo: '', categoria: 'onorari', controparte: '', causale: '', metodo: 'banca', documento: '' })
  const update = (key: string, value: string) => setForm((prev) => {
    const next = { ...prev, [key]: value }
    if (key === 'tipo') next.categoria = value === 'INCASSO' ? 'onorari' : 'anticipazioni_clienti'
    return next
  })
  const categorie = form.tipo === 'INCASSO' ? data.options.categorieIncasso : data.options.categoriePagamento
  const submit = async () => {
    setBusy(true)
    const result = await postJson(data.actions.registra, { ...form, importo: form.importo.replace(',', '.') })
    onMessage(result.message)
    setBusy(false)
    if (result.ok) { setOpen(false); setForm((prev) => ({ ...prev, importo: '', controparte: '', causale: '', documento: '' })); onDone() }
  }
  if (!open) {
    return <button type="button" className="iu-pn-new-toggle" onClick={() => setOpen(true)}><Plus size={16}/> Nuovo movimento</button>
  }
  return (
    <div className="iu-pn-form" role="form" aria-label="Nuovo movimento di prima nota">
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
      <div className="iu-pn-form__actions">
        <button type="button" onClick={submit} disabled={busy || !form.importo.trim()}><Banknote size={15}/> Registra</button>
        <button type="button" className="iu-pn-form__cancel" onClick={() => setOpen(false)}>Annulla</button>
      </div>
    </div>
  )
}

function BankReconciliation({ data, onDone, onMessage }:{data:PrimaNotaData; onDone:()=>void; onMessage:(text:string)=>void}) {
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
      if (!payload.ok) { onMessage(payload.message || 'Analisi non riuscita.'); return }
      setProposte(Array.isArray(payload.proposte) ? payload.proposte : [])
      const c = payload.conteggi
      setConteggi(c ? `${c.abbinamenti} abbinamenti proposti · ${c.ambigui} da scegliere · ${c.nuovi} nuovi movimenti` : '')
      if (payload.avvisi?.length) onMessage(`Analisi completata con ${payload.avvisi.length} righe saltate.`)
    } catch { onMessage('Analisi non riuscita.') } finally { setBusy(false) }
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
    onMessage(result.message)
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
    onMessage(result.message)
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
      {conteggi ? <p className="iu-pn-recon__counts">{conteggi}</p> : null}
      {proposte.length ? (
        <ul className="iu-pn-recon__list">
          {proposte.map((proposta) => (
            <li key={proposta.riga.id} className={`iu-pn-recon__item iu-pn-recon__item--${proposta.tipo}`}>
              <div className="iu-pn-recon__row">
                <strong>{proposta.riga.data} · {proposta.riga.importo.toFixed(2).replace('.', ',')} €</strong>
                <span>{proposta.riga.descrizione || '(senza descrizione)'}</span>
              </div>
              <div className="iu-pn-recon__actions">
                {proposta.tipo === 'abbinamento' && proposta.movimento ? (
                  <button type="button" disabled={busy} onClick={() => conferma(proposta, proposta.movimento!.id)}>
                    <Link2 size={14}/> Abbina a: {proposta.movimento.causale || proposta.movimento.data}
                  </button>
                ) : null}
                {proposta.tipo === 'ambiguo' ? (
                  <span className="iu-pn-recon__choose">
                    <select value={scelte[proposta.riga.id] || ''} onChange={(e) => setScelte((prev) => ({ ...prev, [proposta.riga.id]: e.target.value }))}>
                      <option value="">Scegli il movimento...</option>
                      {proposta.candidati.map((c) => <option value={c.id} key={c.id}>{c.data} · {c.causale || c.id}</option>)}
                    </select>
                    <button type="button" disabled={busy || !scelte[proposta.riga.id]} onClick={() => conferma(proposta, scelte[proposta.riga.id])}><Link2 size={14}/> Abbina</button>
                  </span>
                ) : null}
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

function MovementRow({ movimento, onDone, onMessage }:{movimento:PrimaNotaMovimento; onDone:()=>void; onMessage:(text:string)=>void}) {
  const [showStorno, setShowStorno] = useState(false)
  const [motivo, setMotivo] = useState('')
  const [busy, setBusy] = useState(false)
  const storna = async () => {
    setBusy(true)
    const result = await postJson(movimento.actions.storna, { motivo })
    onMessage(result.message)
    setBusy(false)
    if (result.ok) { setShowStorno(false); onDone() }
  }
  return (
    <tr className={movimento.tipo === 'INCASSO' ? 'iu-pn-row--in' : 'iu-pn-row--out'}>
      <td>{movimento.data}</td>
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
  const [filters, setFilters] = useState({ dal: '', al: '', tipo: '' })
  const load = (next = filters) => {
    getPrimaNotaPage(Object.fromEntries(Object.entries(next).filter(([, v]) => v))).then(setData).catch(() => setData(emptyPrimaNotaData))
  }
  useEffect(() => { load() }, [])
  const riconcilia = async () => {
    if (!data) return
    const result = await postJson(data.actions.riconcilia, {})
    setMessage(result.message)
    if (result.ok) load()
  }
  if (!data) {
    return <main className="iu-pn-page"><div className="iu-pn-loading">Caricamento prima nota...</div></main>
  }
  const exportHref = `${data.actions.esporta}${filters.dal || filters.al ? `?dal=${filters.dal}&al=${filters.al}` : ''}`
  return (
    <main className="iu-pn-page">
      <section className="iu-pn-hero">
        <div>
          <span className="iu-pn-kicker"><Scale size={16}/> Contabilità di studio</span>
          <h1>Prima nota</h1>
          <p>Registro cronologico di incassi e pagamenti per principio di cassa: storni tracciati, riconciliazione con le parcelle, export per il commercialista.</p>
        </div>
        <div className="iu-pn-hero__stats" aria-label="Saldi del periodo">
          <article><strong>{data.summary.incassiLabel}</strong><small>Incassi</small></article>
          <article><strong>{data.summary.pagamentiLabel}</strong><small>Pagamenti</small></article>
          <article className={data.summary.saldo >= 0 ? 'iu-pn-stat--ok' : 'iu-pn-stat--neg'}><strong>{data.summary.saldoLabel}</strong><small>Saldo</small></article>
        </div>
      </section>

      <div className="iu-pn-toolbar">
        <NewMovementForm data={data} onDone={() => load()} onMessage={setMessage} />
        <div className="iu-pn-toolbar__side">
          <label><span>Dal</span><input type="date" value={filters.dal} onChange={(e) => { const next = { ...filters, dal: e.target.value }; setFilters(next); load(next) }}/></label>
          <label><span>Al</span><input type="date" value={filters.al} onChange={(e) => { const next = { ...filters, al: e.target.value }; setFilters(next); load(next) }}/></label>
          <button type="button" onClick={riconcilia}><RefreshCw size={15}/> Riconcilia parcelle</button>
          <a href={exportHref}><FileDown size={15}/> Esporta CSV</a>
        </div>
      </div>

      {message ? <p className="iu-pn-message" role="status"><CheckCircle2 size={15}/> {message}</p> : null}

      <BankReconciliation data={data} onDone={() => load()} onMessage={setMessage} />

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
                <MovementRow movimento={movimento} onDone={() => load()} onMessage={setMessage} key={movimento.id}/>
              )) : (
                <tr><td colSpan={7} className="iu-pn-empty">Nessun movimento nel periodo: registra il primo o riconcilia le parcelle pagate.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {data.avvertenza ? <p className="iu-pn-footnote">{data.avvertenza}</p> : null}
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
