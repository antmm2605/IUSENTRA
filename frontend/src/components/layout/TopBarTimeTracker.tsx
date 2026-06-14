import { Loader2, Pause, Play, Square } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import { useTimeTracker } from '../../hooks/useTimeTracker'
import type { TimeTrackingActivityType, TopbarCreateContext } from '../../types/topbar'

const activities: Array<{ value: TimeTrackingActivityType; label: string }> = [
  { value: 'call', label: 'Telefonata' },
  { value: 'drafting', label: 'Redazione atto' },
  { value: 'research', label: 'Studio pratica' },
  { value: 'hearing', label: 'Udienza' },
  { value: 'meeting', label: 'Riunione' },
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
  const { timer, elapsedSeconds, loading, error, start, pause, resume, stop } = useTimeTracker()
  const [activityType, setActivityType] = useState<TimeTrackingActivityType>('research')
  const [caseId, setCaseId] = useState('')
  const [clientId, setClientId] = useState('')
  const [description, setDescription] = useState('')
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  useEffect(() => {
    if (context.contextType === 'case' && context.contextId) setCaseId(context.contextId)
    if (context.contextType === 'client' && context.contextId) setClientId(context.contextId)
  }, [context])

  const handleStart = () => {
    void start({ caseId, clientId, activityType, description })
  }

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button
        className={`iu-icon iu-timer-button ${timer ? 'is-active' : ''}`}
        type="button"
        onClick={onToggle}
        aria-label="Timer attività"
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Timer attività"
      >
        {icon}
        {timer ? <small>{formatElapsed(elapsedSeconds)}</small> : null}
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-timer-panel" role="dialog" aria-label="Timer attività">
          <header>
            <strong>Timer attività</strong>
            <small>{timer ? (timer.status === 'paused' ? 'In pausa' : 'In corso') : 'Avvia attività'}</small>
          </header>
          {error ? <p className="iu-panel-state is-error">{error}</p> : null}
          {timer ? (
            <div className="iu-timer-active">
              <strong>{formatElapsed(elapsedSeconds)}</strong>
              <small>{activities.find((item) => item.value === timer.activityType)?.label ?? 'Attività'}</small>
              {timer.description ? <p>{timer.description}</p> : null}
              <div className="iu-timer-actions">
                {timer.status === 'paused' ? (
                  <button type="button" onClick={() => void resume()}><Play size={15} /> Riprendi</button>
                ) : (
                  <button type="button" onClick={() => void pause()}><Pause size={15} /> Pausa</button>
                )}
                <button type="button" className="is-danger" onClick={() => void stop()}><Square size={15} /> Stop</button>
              </div>
            </div>
          ) : (
            <div className="iu-timer-form">
              <label>
                <span>Tipo attività</span>
                <select value={activityType} onChange={(event) => setActivityType(event.target.value as TimeTrackingActivityType)}>
                  {activities.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                </select>
              </label>
              <div className="iu-timer-grid">
                <label>
                  <span>Collega a fascicolo</span>
                  <input value={caseId} onChange={(event) => setCaseId(event.target.value)} placeholder="ID fascicolo" />
                </label>
                <label>
                  <span>Collega a cliente</span>
                  <input value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder="ID cliente" />
                </label>
              </div>
              <label>
                <span>Descrizione</span>
                <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Attività svolta" />
              </label>
              <button type="button" className="iu-timer-start" onClick={handleStart} disabled={loading}>
                {loading ? <Loader2 className="iu-spin" size={16} /> : <Play size={16} />}
                Avvia attività
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
