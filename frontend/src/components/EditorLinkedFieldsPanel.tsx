import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, X, RefreshCw } from 'lucide-react'
import { OPERATIONAL_REFRESH_EVENT } from '../operationalRefresh'
import { csrfToken } from '../formSubmit'
import { FascicoloSearchSelect, type FascicoloOption } from './FascicoloSearchSelect'
import './EditorLinkedFieldsPanel.css'

export type LinkedEditorField = { id: string; label: string; group: string; value: string; available: boolean; missing_reason?: string; conflict?: boolean }
export type LinkedEditorContext = { matterId: string; clientId: string; clientLabel: string; matterLabel: string; revision: string; fields: LinkedEditorField[]; notice?: string }

export function EditorLinkedFieldsPanel({ matterId, options, onMatterChange, onInsert, onClose, onRefreshFields, disabled, catalogLoading, catalogError }: {
  matterId: string; options?: FascicoloOption[]; onMatterChange?: (id: string) => void;
  onInsert: (field: LinkedEditorField, context: LinkedEditorContext) => void; onClose: () => void;
  onRefreshFields: (context: LinkedEditorContext) => void; disabled: boolean;
  catalogLoading?: boolean; catalogError?: string;
}) {
  const [context, setContext] = useState<LinkedEditorContext | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [reload, setReload] = useState(0)
  const [changed, setChanged] = useState(false)
  const [recoveryPending, setRecoveryPending] = useState(false)
  const [recoveryError, setRecoveryError] = useState('')
  const [recover, setRecover] = useState(0)
  const revisionRef = useRef('')
  useEffect(() => {
    const refresh = () => setReload(value => value + 1)
    window.addEventListener(OPERATIONAL_REFRESH_EVENT, refresh)
    return () => window.removeEventListener(OPERATIONAL_REFRESH_EVENT, refresh)
  }, [])
  useEffect(() => {
    setContext(null); setChanged(false); revisionRef.current = ''
  }, [matterId])
  useEffect(() => {
    if (!matterId) return
    const controller = new AbortController()
    setRecoveryError(''); setRecoveryPending(false)
    fetch(`/api/editor/${encodeURIComponent(matterId)}/recupera-campi`, {
      method: 'POST', credentials: 'same-origin', signal: controller.signal,
      headers: { Accept: 'application/json', 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
    }).then(async response => {
      const payload = await response.json()
      if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Recupero non avviato.')
      if (!controller.signal.aborted) { setRecoveryPending(true); setReload(value => value + 1) }
    }).catch(error => { if (!controller.signal.aborted) setRecoveryError(error instanceof Error ? error.message : 'Recupero non avviato.') })
    return () => controller.abort()
  }, [matterId, recover])
  useEffect(() => {
    if (!recoveryPending) return
    let checks = 0
    const timer = window.setInterval(() => {
      if (++checks > 40) {
        window.clearInterval(timer); setRecoveryPending(false)
        setRecoveryError('Il recupero è ancora in coda. Puoi aggiornare i dati; il documento è preservato.')
      } else setReload(value => value + 1)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [matterId, recoveryPending])
  useEffect(() => {
    if (!matterId) return
    const controller = new AbortController()
    setLoading(true); setError('')
    fetch(`/api/editor/${encodeURIComponent(matterId)}/campi-collegati`, { credentials: 'same-origin', signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async response => {
        const payload = await response.json()
        if (!response.ok || !payload.ok) throw new Error(payload.errore || 'Dati non caricati.')
        if (revisionRef.current && revisionRef.current !== payload.revision) setChanged(true)
        revisionRef.current = payload.revision
        setContext(payload)
        if (payload.recoveryState === 'idle') setRecoveryPending(false)
      }).catch(error => { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Dati non caricati.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [matterId, reload])
  const groups = useMemo(() => [...new Set(context?.fields.map(field => field.group) || [])], [context])
  return <aside className="iu-linked-fields" aria-label="Dati collegati al documento">
    <header><strong>Dati collegati</strong><button type="button" aria-label="Chiudi dati collegati" onClick={onClose}><X size={16}/></button></header>
    {onMatterChange && catalogLoading && <p role="status">Caricamento fascicoli…</p>}
    {onMatterChange && catalogError && <p role="alert">{catalogError}</p>}
    {onMatterChange && <FascicoloSearchSelect options={options || []} value={matterId} onChange={onMatterChange} disabled={disabled} selectionLabel="Fascicolo per compilazione" hint="Scegli il fascicolo: il cliente viene individuato dal collegamento in anagrafica."/>}
    {!matterId && <p>Scegli il fascicolo per visualizzare i suoi dati e quelli del cliente.</p>}
    {context && <div className="iu-linked-fields__context"><strong>{context.clientLabel || 'Cliente non associato'}</strong><span>{context.matterLabel}</span></div>}
    {matterId && <button className="iu-linked-fields__refresh" type="button" disabled={loading} onClick={() => setReload(value => value + 1)}><RefreshCw size={14}/> Aggiorna dati</button>}
    {loading && <p role="status">Caricamento dati…</p>}
    {recoveryPending && <p role="status">Recupero dei campi dalle fonti del fascicolo…</p>}
    {recoveryError && <p role="alert">{recoveryError} <button type="button" onClick={() => setRecover(value => value + 1)}>Riprova recupero</button></p>}
    {error && <p role="alert" className="iu-linked-fields__error">{error}</p>}
    {context?.notice && <p>{context.notice}</p>}
    {changed && <p role="status">I dati di origine sono cambiati. Il testo del documento è preservato.</p>}
    {context && <button type="button" disabled={disabled || loading || Boolean(error)} onMouseDown={event => event.preventDefault()} onClick={() => { onRefreshFields(context); setChanged(false) }}>Confronta campi inseriti</button>}
    <div className="iu-linked-fields__groups">{groups.map(group => {
      const fields = context!.fields.filter(field => field.group === group)
      const available = fields.filter(field => field.available).length
      return <details key={group} open={group === 'Anagrafica' || undefined}>
        <summary><span>{group}</span><small>{available}/{fields.length}</small><ChevronDown size={15}/></summary>
        <div>{fields.map(field => <button key={field.id} type="button" disabled={disabled || Boolean(error) || Boolean(field.conflict)}
          title={field.available ? `Inserisci ${field.label}` : field.conflict ? 'Dato discordante: controlla la fonte' : `Inserisci il segnaposto ${field.label}: il dato sarà compilato dal fascicolo quando disponibile`}
          onMouseDown={event => event.preventDefault()} onClick={() => onInsert(field, context!)}>
          <span>{field.label}</span><strong>{field.value || (field.conflict ? 'Da verificare' : 'Inserisci segnaposto')}</strong>
        </button>)}</div>
      </details>
    })}</div>
  </aside>
}
