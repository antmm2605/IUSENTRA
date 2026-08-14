import { useEffect, useState } from 'react'
import { ArrowDownCircle, ArrowUpCircle, Banknote, CheckCircle2, FileDown, Plus, RefreshCw, RotateCcw, Scale } from 'lucide-react'
import { FloatingLex } from './FloatingLex'
import { emptyPrimaNotaData, getPrimaNotaPage, type PrimaNotaData, type PrimaNotaMovimento } from '../primaNotaData'
import './PrimaNotaPage.css'

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

      {data.summary.perCategoria.length ? (
        <div className="iu-pn-categories" aria-label="Totali per categoria">
          {data.summary.perCategoria.slice(0, 6).map((c) => <span key={c.categoria}>{c.label}: <strong>{c.importoLabel}</strong></span>)}
        </div>
      ) : null}

      <section className="iu-pn-table-card">
        <div className="iu-pn-table-wrap">
          <table aria-label="Registro cronologico">
            <thead>
              <tr><th>Data</th><th>Tipo</th><th>Importo</th><th>Categoria</th><th>Controparte / causale</th><th>Metodo</th><th></th></tr>
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
