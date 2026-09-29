import { CheckCircle2, Clock3, FolderOpen, Loader2, Pause, Play, Search, Square, Trash2, UserRound, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useTimeTracker } from '../../hooks/useTimeTracker'
import { searchTimerLinks } from '../../services/topbarApi'
import type { TimeTrackingActivityType, TimeTrackingLink, TopbarCreateContext } from '../../types/topbar'
import './TopBarTimeTracker.css'

const activities: Array<{ value: TimeTrackingActivityType; label: string }> = [
  { value: 'research', label: 'Studio pratica' },
  { value: 'drafting', label: 'Redazione atto' },
  { value: 'call', label: 'Telefonata' },
  { value: 'meeting', label: 'Riunione' },
  { value: 'hearing', label: 'Udienza' },
  { value: 'email', label: 'Email/PEC' },
  { value: 'filing', label: 'Deposito' },
  { value: 'other', label: 'Altro' },
]

function formatElapsed(seconds: number) {
  const total = Math.max(0, seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return h > 0
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatMinutes(minutes: number) {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (!h) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}

/** Scelta del fascicolo o del cliente per nome, numero o R.G.: niente identificativi da digitare. */
function CollegamentoPicker({ scelto, onScegli, recenti }: {
  scelto: TimeTrackingLink | null
  onScegli: (link: TimeTrackingLink | null) => void
  recenti: TimeTrackingLink[]
}) {
  const [testo, setTesto] = useState('')
  const [risultati, setRisultati] = useState<TimeTrackingLink[]>([])
  const [cerca, setCerca] = useState(false)

  useEffect(() => {
    const q = testo.trim()
    if (q.length < 2) { setRisultati([]); return undefined }
    let attivo = true
    setCerca(true)
    const handle = window.setTimeout(() => {
      searchTimerLinks(q)
        .then((payload) => { if (attivo) setRisultati(payload.items) })
        .catch(() => { if (attivo) setRisultati([]) })
        .finally(() => { if (attivo) setCerca(false) })
    }, 250)
    return () => { attivo = false; window.clearTimeout(handle) }
  }, [testo])

  if (scelto) {
    return (
      <div className="iu-tt-scelto">
        {scelto.caseId ? <FolderOpen size={15}/> : <UserRound size={15}/>}
        <span><strong>{scelto.label}</strong>{scelto.detail ? <small>{scelto.detail}</small> : null}</span>
        <button type="button" onClick={() => onScegli(null)} aria-label="Togli il collegamento"><X size={14}/></button>
      </div>
    )
  }
  return (
    <div className="iu-tt-picker">
      <label className="iu-tt-cerca">
        <Search size={15}/>
        <input value={testo} onChange={(e) => setTesto(e.target.value)} placeholder="Cerca fascicolo o cliente: nome, numero, R.G."
          aria-label="Fascicolo o cliente dell'attività"/>
        {cerca ? <Loader2 className="iu-spin" size={14}/> : null}
      </label>
      {risultati.length ? (
        <ul className="iu-tt-risultati" role="listbox" aria-label="Fascicoli e clienti trovati">
          {risultati.map((r) => (
            <li key={`${r.kind}-${r.caseId}-${r.clientId}`}>
              <button type="button" role="option" aria-selected={false} onClick={() => { onScegli(r); setTesto('') }}>
                {r.caseId ? <FolderOpen size={14}/> : <UserRound size={14}/>}
                <span><strong>{r.label}</strong>{r.detail ? <small>{r.detail}</small> : null}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : testo.trim().length >= 2 && !cerca ? <p className="iu-tt-vuoto">Nessun fascicolo o cliente trovato.</p> : null}
      {!testo && recenti.length ? (
        <div className="iu-tt-recenti">
          <span>Ultimi fascicoli</span>
          {recenti.map((r) => (
            <button type="button" key={r.caseId || r.label} onClick={() => onScegli(r)} title={r.detail}>{r.label}</button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function TopBarTimeTracker({
  open,
  onToggle,
  onClose,
  context,
  icon,
}: {
  open: boolean
  onToggle: () => void
  onClose: () => void
  context: TopbarCreateContext
  icon: ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const { timer, elapsedSeconds, today, recent, saved, notice, loading, error, reload, start, pause, resume, update, stop, dismiss } = useTimeTracker()
  const [activityType, setActivityType] = useState<TimeTrackingActivityType>('research')
  const [link, setLink] = useState<TimeTrackingLink | null>(null)
  const [description, setDescription] = useState('')
  const [nota, setNota] = useState('')
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  useEffect(() => {
    // Dalla pagina di un fascicolo o di un cliente il timer parte già collegato, con il nome leggibile.
    const id = context.contextId
    if (!id || (context.contextType !== 'case' && context.contextType !== 'client')) return undefined
    const tipo = context.contextType === 'case' ? 'caseId' : 'clientId'
    let attivo = true
    searchTimerLinks('', { [tipo]: id })
      .then((payload) => { if (attivo && payload.items[0]) setLink(payload.items[0]) })
      .catch(() => undefined)
    return () => { attivo = false }
  }, [context])

  useEffect(() => {
    if (open) void reload()
  }, [open, reload])

  useEffect(() => {
    setNota(timer?.description || '')
  }, [timer?.id, timer?.description])

  const handleStart = () => {
    void start({ caseId: link?.caseId || '', clientId: link?.clientId || '', activityType, description })
      .then(() => setDescription(''))
  }
  const salvaNota = () => {
    if (timer && nota.trim() !== (timer.description || '')) void update({ description: nota.trim() })
  }
  const scarta = () => {
    if (window.confirm('Scartare questo tempo? Non verrà registrato nel timesheet.')) void stop({ discard: true })
  }
  const etichettaAttivita = (valore: string) => activities.find((item) => item.value === valore)?.label ?? 'Attività'
  const oggi = !today ? '' : today.voci ? `Oggi ${formatMinutes(today.minuti)} in ${today.voci} ${today.voci === 1 ? 'voce' : 'voci'}` : 'Oggi nessun tempo registrato'

  return (
    <div className="iu-topbar-popover iu-tt-radice" ref={ref}>
      <button
        className={`iu-icon iu-timer-button ${timer ? 'is-active' : ''} ${timer?.status === 'paused' ? 'is-paused' : ''}`}
        type="button"
        onClick={onToggle}
        aria-label={timer ? `Timer attività: ${formatElapsed(elapsedSeconds)}${timer.status === 'paused' ? ', in pausa' : ''}` : 'Timer attività'}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={timer ? `${etichettaAttivita(timer.activityType)}${timer.caseLabel ? ` · ${timer.caseLabel}` : ''}` : 'Timer attività'}
      >
        {icon}
        {timer ? <small>{timer.status === 'paused' ? 'Pausa ' : ''}{formatElapsed(elapsedSeconds)}</small> : null}
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-timer-panel iu-tt" role="dialog" aria-label="Timer attività">
          <header className="iu-tt-testa">
            <span><Clock3 size={16}/><strong>Timer attività</strong></span>
            {today ? <a href={today.href}>{oggi}</a> : null}
          </header>
          {error ? <p className="iu-panel-state is-error" role="alert">{error}</p> : null}
          {notice ? (
            <div className={`iu-tt-esito ${saved ? 'is-ok' : ''}`} role="status">
              <CheckCircle2 size={16}/>
              <span>
                <strong>{notice}</strong>
                {saved ? <small>{saved.description}{saved.caseLabel ? ` · ${saved.caseLabel}` : ''}</small> : null}
              </span>
              {saved ? <a href={saved.href}>Apri il timesheet</a> : null}
              <button type="button" onClick={dismiss} aria-label="Chiudi l'avviso"><X size={14}/></button>
            </div>
          ) : null}
          {timer ? (
            <div className="iu-tt-corso">
              <div className="iu-tt-orologio">
                <strong>{formatElapsed(elapsedSeconds)}</strong>
                <span className={timer.status === 'paused' ? 'is-pausa' : 'is-corso'}>{timer.status === 'paused' ? 'In pausa' : 'In corso'}</span>
              </div>
              <dl className="iu-tt-dati">
                <div><dt>Attività</dt><dd>{etichettaAttivita(timer.activityType)}</dd></div>
                <div><dt>Fascicolo</dt><dd>{timer.caseHref ? <a href={timer.caseHref}>{timer.caseLabel}</a> : <em>Non collegato</em>}</dd></div>
                {timer.clientLabel ? <div><dt>Cliente</dt><dd>{timer.clientLabel}</dd></div> : null}
              </dl>
              {!timer.caseId ? (
                <CollegamentoPicker scelto={null} recenti={recent} onScegli={(scelta) => {
                  if (scelta) void update({ caseId: scelta.caseId || '', clientId: scelta.clientId || '' })
                }}/>
              ) : null}
              <label className="iu-tt-campo">
                <span>Cosa stai facendo</span>
                <input value={nota} onChange={(e) => setNota(e.target.value)} onBlur={salvaNota} placeholder="Es. studio della comparsa avversaria"/>
              </label>
              <div className="iu-tt-azioni">
                {timer.status === 'paused' ? (
                  <button type="button" onClick={() => void resume()}><Play size={15} /> Riprendi</button>
                ) : (
                  <button type="button" onClick={() => void pause()}><Pause size={15} /> Pausa</button>
                )}
                <button type="button" className="is-primario" disabled={loading} onClick={() => void stop({ description: nota.trim() })}>
                  {loading ? <Loader2 className="iu-spin" size={15}/> : <Square size={15} />} Stop e registra
                </button>
              </div>
              <button type="button" className="iu-tt-scarta" onClick={scarta}><Trash2 size={13}/> Scarta senza registrare</button>
            </div>
          ) : (
            <div className="iu-tt-avvio">
              <div className="iu-tt-gruppo">
                <span>Su cosa lavori</span>
                <CollegamentoPicker scelto={link} onScegli={setLink} recenti={recent}/>
              </div>
              <div className="iu-tt-gruppo">
                <span>Tipo attività</span>
                <div className="iu-tt-tipi" role="group" aria-label="Tipo attività">
                  {activities.map((item) => (
                    <button type="button" key={item.value} aria-pressed={activityType === item.value} onClick={() => setActivityType(item.value)}>{item.label}</button>
                  ))}
                </div>
              </div>
              <label className="iu-tt-campo">
                <span>Descrizione</span>
                <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Attività svolta (si può completare dopo)" />
              </label>
              <button type="button" className="iu-tt-avvia" onClick={handleStart} disabled={loading}>
                {loading ? <Loader2 className="iu-spin" size={16} /> : <Play size={16} />}
                Avvia attività
              </button>
              <p className="iu-tt-nota">Allo stop il tempo diventa una voce del timesheet, pronta per la parcella a tempo.</p>
            </div>
          )}
          {today?.ultime.length ? (
            <footer className="iu-tt-oggi">
              <span>Registrato oggi</span>
              <ul>
                {today.ultime.map((voce, indice) => (
                  <li key={`${voce.descrizione}-${indice}`}><span>{voce.descrizione}{voce.fascicolo ? <small>{voce.fascicolo}</small> : null}</span><b>{formatMinutes(voce.minuti)}</b></li>
                ))}
              </ul>
            </footer>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
