import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CalendarDays, Gavel } from 'lucide-react'
import { Badge } from '../dashboard'
import { formatDateIt } from '../../formatting'
import { useOperationalRefresh } from '../../hooks/useOperationalRefresh'
import { parseCtuWriteProtocol, type CtuWriteProtocol } from '../../ctuCommand'
import { useCtuCommand } from '../../hooks/useCtuCommand'
import type { CtuDettaglio } from './CtuIncaricoDettaglio'
import './CtuSection.css'

const CtuIncaricoDettaglio = lazy(() => import('./CtuIncaricoDettaglio'))

type CtuIncarico = CtuDettaglio & {
  statoLabel: string
  nomeCtu: string
  timeline: Array<{ chiave: string; label: string; data: string }>
  avvisi: string[]
  consulentiParte: Array<{ nome: string; parte: string }>
  actions: CtuDettaglio['actions'] & { proponiScadenze: string }
}

function addDaysToIsoDate(base: string, days: string): string {
  const cleanBase = String(base || '').slice(0, 10)
  if (!days.trim()) return ''
  const amount = Number(days)
  if (!cleanBase || !Number.isSafeInteger(amount) || amount < 0) return ''
  const parts = cleanBase.split('-').map((part) => Number(part))
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return ''
  const [year, month, day] = parts
  const date = new Date(Date.UTC(year, month - 1, day))
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== cleanBase) return ''
  date.setUTCDate(date.getUTCDate() + Math.trunc(amount))
  if (!Number.isFinite(date.getTime())) return ''
  const result = date.toISOString().slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(result) ? result : ''
}

function CtuDeadlineCommand({ protocol, fascicoloId, incarico, disabled, onAggiornato }: {
  protocol: CtuWriteProtocol | null; fascicoloId: string; incarico: CtuIncarico;
  disabled: boolean; onAggiornato: () => void
}) {
  const command = useCtuCommand(protocol, fascicoloId, incarico.id)
  const [busy, setBusy] = useState(false)
  const inFlight = useRef(false)
  const [message, setMessage] = useState('')
  const execute = async (recover = false) => {
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    try {
      const result = recover ? await command.recover() : await command.submit(incarico.actions.proponiScadenze, {})
      setMessage(typeof result.message === 'string' ? result.message : 'Esito della consegna non confermato.')
      if (result.ok === true || result.terminalRejected === true) onAggiornato()
    } finally { inFlight.current = false; setBusy(false) }
  }
  return <div>
    <button type="button" disabled={disabled || busy || command.blocked} onClick={() => void execute()}><CalendarDays size={14}/> Proponi scadenze</button>
    {message ? <p role="status">{message}</p> : null}
    {command.storageError ? <p role="alert">{command.storageError}</p> : null}
    {command.pending ? <div role="status"><p>Un comando dell’incarico attende il riscontro. Recuperalo prima di proporre altre scadenze.</p>
      <button type="button" disabled={disabled || busy} onClick={() => void execute(true)}>Recupera esito del comando</button></div> : null}
  </div>
}

export default function CtuSection({ fascicoloId }:{fascicoloId:string}) {
  const [incarichi, setIncarichi] = useState<CtuIncarico[]>([])
  const [loadError, setLoadError] = useState('')
  const [loading, setLoading] = useState(true)
  const [writeProtocol, setWriteProtocol] = useState<CtuWriteProtocol | null>(null)
  const command = useCtuCommand(writeProtocol, fascicoloId, '')
  const readSequence = useRef(0)
  const readController = useRef<AbortController | null>(null)
  const [message, setMessage] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const writeInFlight = useRef(false)
  const [form, setForm] = useState({ ruoloStudio: 'PARTE', nomeCtu: '', dataNomina: '', termineBozza: '', termineOsservazioni: '', termineDeposito: '' })
  const [ctuCalc, setCtuCalc] = useState({ decorrenza: '', giorniBozza: '', giorniOsservazioni: '', giorniDeposito: '' })
  const currentForm = useRef(form)
  const currentCalc = useRef(ctuCalc)
  currentForm.current = form
  currentCalc.current = ctuCalc
  const [gestito, setGestito] = useState('')
  const [openedDetails, setOpenedDetails] = useState<Set<string>>(() => new Set())
  const load = useCallback(async () => {
    const sequence = ++readSequence.current
    readController.current?.abort()
    const controller = new AbortController()
    readController.current = controller
    setLoading(true)
    try {
      const response = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/ctu`, {
        credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal,
      })
      const payload = await response.json() as { ok?: boolean; message?: string; incarichi?: CtuIncarico[]; writeProtocol?: unknown }
      if (!response.ok || payload.ok !== true || !Array.isArray(payload.incarichi)) {
        throw new Error(payload.message || 'Lettura degli incarichi CTU non riuscita. Riprova.')
      }
      if (sequence !== readSequence.current) return
      setWriteProtocol(parseCtuWriteProtocol(payload.writeProtocol))
      setIncarichi(payload.incarichi)
      setLoadError('')
    } catch (error) {
      if (controller.signal.aborted || sequence !== readSequence.current) return
      setLoadError(error instanceof Error ? error.message : 'Connessione non riuscita. Riprova la lettura degli incarichi CTU.')
      throw error
    } finally {
      if (sequence === readSequence.current) setLoading(false)
    }
  }, [fascicoloId])
  const reload = () => { void load().catch(() => { /* L'errore resta visibile; dati e bozze sono conservati. */ }) }
  useEffect(() => {
    setIncarichi([])
    setLoadError('')
    setWriteProtocol(null)
    reload()
    return () => { ++readSequence.current; readController.current?.abort() }
  }, [load])
  useOperationalRefresh(['fascicoli'], load)
  const post = async (href: string, body: Record<string, unknown>, creation = false, recover = false) => {
    if (writeInFlight.current) return
    writeInFlight.current = true
    setBusy(true)
    const submittedForm = JSON.stringify(body)
    const submittedCalc = JSON.stringify(currentCalc.current)
    try {
      const payload = await (recover ? command.recover() : command.submit(href, body))
      const confirmed = payload?.ok === true
      setMessage(typeof payload?.message === 'string' ? payload.message : (confirmed ? 'Operazione completata.' : 'Esito non confermato: la bozza è conservata.'))
      if (confirmed) {
        // Un recupero può riguardare una bozza precedente: conserva il modulo corrente.
        if (creation && !recover && JSON.stringify(currentForm.current) === submittedForm && JSON.stringify(currentCalc.current) === submittedCalc) {
          setFormOpen(false)
          setForm({ ruoloStudio: 'PARTE', nomeCtu: '', dataNomina: '', termineBozza: '', termineOsservazioni: '', termineDeposito: '' })
          setCtuCalc({ decorrenza: '', giorniBozza: '', giorniOsservazioni: '', giorniDeposito: '' })
        } else if (creation) setMessage('Registrazione confermata nell’elenco. Le modifiche successive della bozza sono conservate.')
        reload()
      } else if (payload?.terminalRejected === true) reload()
    } catch { setMessage('Esito non confermato: la bozza è conservata. Verifica il salvataggio prima di riprovare.') } finally { writeInFlight.current = false; setBusy(false) }
  }
  const applyCtuTermini = () => {
    const decorrenza = ctuCalc.decorrenza || form.dataNomina
    if (!decorrenza) {
      setMessage('Indica la decorrenza riportata nell’ordinanza prima di applicare i termini.')
      return
    }
    const next = { ...form }
    const bozza = addDaysToIsoDate(decorrenza, ctuCalc.giorniBozza)
    const osservazioni = addDaysToIsoDate(decorrenza, ctuCalc.giorniOsservazioni)
    const deposito = addDaysToIsoDate(decorrenza, ctuCalc.giorniDeposito)
    let applicati = 0
    if (bozza) { next.termineBozza = bozza; applicati += 1 }
    if (osservazioni) { next.termineOsservazioni = osservazioni; applicati += 1 }
    if (deposito) { next.termineDeposito = deposito; applicati += 1 }
    if (!applicati) {
      setMessage('Inserisci almeno un termine in giorni indicato nell’ordinanza.')
      return
    }
    setForm(next)
    setMessage('Date CTU calcolate dai termini dell’ordinanza e pronte per la verifica.')
  }
  return (
    <div className="iu-fas-ctu">
      {loading ? <p className="iu-fas-ctu__msg" role="status">Aggiornamento incarichi CTU…</p> : null}
      {loadError ? <div className="iu-fas-ctu__warn" role="alert">
        <p>{loadError} {incarichi.length ? 'Gli ultimi dati caricati restano visibili.' : ''}</p>
        <button type="button" disabled={loading} onClick={reload}>Riprova lettura</button>
      </div> : null}
      {message ? <p className="iu-fas-ctu__msg" role="status">{message}</p> : null}
      {command.storageError ? <p className="iu-fas-ctu__warn" role="alert">{command.storageError}</p> : null}
      {command.pending ? <div className="iu-fas-ctu__warn" role="status">
        <p>Una registrazione CTU attende il riscontro. Recupera lo stesso comando prima di registrarne un altro; la bozza corrente resta conservata.</p>
        <button type="button" disabled={busy || loading || Boolean(loadError)} onClick={() => void post('', {}, true, true)}>Recupera esito registrazione</button>
      </div> : null}
      {incarichi.map((incarico) => (
        <article className="iu-fas-ctu__card" key={incarico.id}>
          <header>
            <strong>{incarico.nomeCtu || 'CTU da indicare'}</strong>
            <Badge tone="neutral">{incarico.statoLabel}</Badge>
            <span>{incarico.ruoloStudio === 'AUSILIARIO' ? 'Lo studio assiste il CTU' : 'Lo studio assiste una parte'}</span>
          </header>
          <ol className="iu-fas-ctu__timeline">
            {incarico.timeline.map((tappa) => (
              <li className={tappa.data ? 'is-set' : ''} key={tappa.chiave}><span>{tappa.label}</span><strong>{tappa.data ? formatDateIt(tappa.data) : '—'}</strong></li>
            ))}
          </ol>
          {incarico.avvisi.map((avviso) => <p className="iu-fas-ctu__warn" key={avviso}><AlertTriangle size={13}/> {avviso}</p>)}
          {incarico.consulentiParte.length ? (
            <p className="iu-fas-ctu__ctp">CTP: {incarico.consulentiParte.map((c) => `${c.nome} (${c.parte || 'parte'})`).join(', ')}</p>
          ) : null}
          <footer>
            <CtuDeadlineCommand protocol={writeProtocol} fascicoloId={fascicoloId} incarico={incarico}
              disabled={busy || loading || Boolean(loadError)} onAggiornato={reload}/>
            <button type="button" aria-expanded={gestito === incarico.id} onClick={() => {
              setOpenedDetails((previous) => new Set(previous).add(incarico.id))
              setGestito(gestito === incarico.id ? '' : incarico.id)
            }}><Gavel size={14}/> {gestito === incarico.id ? 'Chiudi gestione' : 'Operazioni, compenso e liquidazione'}</button>
          </footer>
          {openedDetails.has(incarico.id) ? (
            <div hidden={gestito !== incarico.id}>
              <Suspense fallback={<p className="iu-fas-ctu__msg">Caricamento…</p>}>
                <CtuIncaricoDettaglio incarico={incarico} fascicoloId={fascicoloId} writeProtocol={writeProtocol} onAggiornato={reload}/>
              </Suspense>
            </div>
          ) : null}
        </article>
      ))}
      {formOpen ? (
        <div className="iu-fas-ctu__form" role="form" aria-label="Nuovo incarico CTU">
          <label><span>Ruolo studio</span>
            <select value={form.ruoloStudio} onChange={(e) => setForm({ ...form, ruoloStudio: e.target.value })}>
              <option value="PARTE">Assistiamo una parte</option>
              <option value="AUSILIARIO">Assistiamo il CTU</option>
            </select>
          </label>
          <label><span>Nome CTU</span><input value={form.nomeCtu} onChange={(e) => setForm({ ...form, nomeCtu: e.target.value })} placeholder="Es. Ing. Bruni"/></label>
          <label><span>Ordinanza di nomina</span><input type="date" value={form.dataNomina} onChange={(e) => setForm({ ...form, dataNomina: e.target.value })}/></label>
          <label><span>Termine bozza (art. 195)</span><input type="date" value={form.termineBozza} onChange={(e) => setForm({ ...form, termineBozza: e.target.value })}/></label>
          <label><span>Termine osservazioni</span><input type="date" value={form.termineOsservazioni} onChange={(e) => setForm({ ...form, termineOsservazioni: e.target.value })}/></label>
          <label><span>Termine deposito</span><input type="date" value={form.termineDeposito} onChange={(e) => setForm({ ...form, termineDeposito: e.target.value })}/></label>
          <section className="iu-fas-ctu__calc" aria-label="Calcolo assistito dall’ordinanza">
            <header>
              <strong>Calcolo assistito dall’ordinanza</strong>
              <span>Usa solo decorrenza e giorni indicati dal giudice.</span>
            </header>
            <label><span>Decorrenza indicata</span><input type="date" value={ctuCalc.decorrenza} onChange={(e) => setCtuCalc({ ...ctuCalc, decorrenza: e.target.value })}/></label>
            <label><span>Giorni bozza</span><input type="number" min="0" inputMode="numeric" value={ctuCalc.giorniBozza} onChange={(e) => setCtuCalc({ ...ctuCalc, giorniBozza: e.target.value })}/></label>
            <label><span>Giorni osservazioni</span><input type="number" min="0" inputMode="numeric" value={ctuCalc.giorniOsservazioni} onChange={(e) => setCtuCalc({ ...ctuCalc, giorniOsservazioni: e.target.value })}/></label>
            <label><span>Giorni deposito</span><input type="number" min="0" inputMode="numeric" value={ctuCalc.giorniDeposito} onChange={(e) => setCtuCalc({ ...ctuCalc, giorniDeposito: e.target.value })}/></label>
            <button type="button" onClick={applyCtuTermini}>Applica date</button>
            <p>I termini non sono standard: vanno copiati dall’ordinanza. Le date calcolate restano modificabili prima del salvataggio.</p>
          </section>
          <div className="iu-fas-ctu__form-actions">
            <button type="button" disabled={busy || loading || Boolean(loadError) || command.blocked || !form.nomeCtu.trim()} onClick={() => post(`/fascicoli/${encodeURIComponent(fascicoloId)}/ctu/nuovo`, form, true)}>Registra incarico</button>
            <button type="button" className="iu-fas-ctu__cancel" onClick={() => { setFormOpen(false); setMessage('') }}>Annulla</button>
          </div>
          <p className="iu-fas-ctu__note">L’ordinanza fissa i termini ex art. 195 c.3 c.p.c.: IUSENTRA calcola solo le date ricavabili dai giorni o dalle date indicati nell’ordinanza.</p>
        </div>
      ) : (
        <button type="button" className="iu-fas-ctu__add" disabled={loading || Boolean(loadError)} onClick={() => setFormOpen(true)}><Gavel size={15}/> Nuovo incarico CTU</button>
      )}
    </div>
  )
}
