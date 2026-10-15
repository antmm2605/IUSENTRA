import { useEffect, useRef, useState } from 'react'
import { Modal } from '../ui/legalPrimitives'
import { csrfToken } from '../formSubmit'
import { FascicoloSearchSelect, type FascicoloOption } from './FascicoloSearchSelect'
import { useBusyActivity } from '../ui/useBusyActivity'
import { LoadingState } from '../ui/LoadingState'
import '../ui/activity.css'
import './EditorPersonalTemplates.css'

export function EditorPersonalTemplates({ open, onClose, serialize, matterId, options, onMatterChange, onApply, mattersLoading, mattersError, sourceDocument, onUsageChange }: {
  open: boolean; onClose: () => void; serialize: () => string; matterId: string; options: FascicoloOption[];
  onMatterChange?: (id: string) => void; onApply: (html: string, title: string, missing: string[]) => void;
  mattersLoading?: boolean; mattersError?: string; sourceDocument?: {matter: string; document: string};
  onUsageChange?: (usingModel: boolean) => void;
}) {
  const [mode, setMode] = useState<'save' | 'use'>('save')
  const [title, setTitle] = useState('')
  const [models, setModels] = useState<Array<{id: string; titolo: string; ambito?: string}>>([])
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError, setCatalogError] = useState('')
  const [catalogReload, setCatalogReload] = useState(0)
  const [model, setModel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [ready, setReady] = useState<{html: string; titolo: string; mancanti: string[]} | null>(null)
  const intent = useRef<{titolo: string; html: string; command_id: string; source_document?: {matter: string; document: string}} | null>(null)
  useBusyActivity(open && mode === 'use' && catalogLoading, 'Caricamento modelli…')
  useBusyActivity(open && busy, mode === 'save' ? 'Salvataggio modello…' : 'Compilazione del modello…')
  useEffect(() => { setReady(null) }, [model, matterId])
  useEffect(() => { onUsageChange?.(open && mode === 'use') }, [open, mode, onUsageChange])
  useEffect(() => {
    // Saving the current document does not need the catalog of other models.
    if (!open || mode !== 'use') return
    let active = true
    const controller = new AbortController()
    setCatalogLoading(true); setCatalogError('')
    fetch('/api/editor/modelli-personali', { credentials: 'same-origin', signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(async response => { const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.errore); if (active) setModels(data.modelli) })
      .catch(error => { if (active) setCatalogError(error instanceof Error ? error.message : 'Modelli non caricati.') })
      .finally(() => { if (active) setCatalogLoading(false) })
    return () => { active = false; controller.abort() }
  }, [open, mode, success, catalogReload])
  const save = async () => {
    setBusy(true); setError(''); setSuccess('')
    intent.current ||= { titolo: title.trim(), html: serialize(), command_id: crypto.randomUUID(), source_document: sourceDocument }
    try {
      const response = await fetch('/api/editor/modelli-personali', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' }, body: JSON.stringify(intent.current) })
      const data = await response.json()
      if (!response.ok || !data.ok) { if ([400,403,409].includes(response.status)) intent.current = null; throw new Error(data.errore || 'Salvataggio non confermato.') }
      setSuccess(`Modello «${data.titolo}» salvato.`); intent.current = null
    } catch (error) { setError(error instanceof Error ? error.message : 'Salvataggio non confermato.') }
    finally { setBusy(false) }
  }
  const prepare = async () => {
    setBusy(true); setError(''); setSuccess(''); setReady(null)
    try {
      const response = await fetch(`/api/editor/${encodeURIComponent(matterId)}/modelli-personali/${encodeURIComponent(model)}/compila`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      const data = await response.json()
      if (!response.ok || !data.ok) throw new Error(data.errore || 'Compilazione non riuscita.')
      setReady(data)
    } catch (error) { setError(error instanceof Error ? error.message : 'Compilazione non riuscita.') }
    finally { setBusy(false) }
  }
  return <Modal title="Modelli" open={open} onClose={() => { if (!busy) onClose() }}>
    <div className="iu-de-personal-templates">
    <div className="iu-de-template-actions"><button type="button" aria-pressed={mode === 'save'} disabled={busy} onClick={() => { setMode('save'); setError(''); setSuccess('') }}>Salva modello personale</button><button type="button" aria-pressed={mode === 'use'} disabled={busy || intent.current !== null} onClick={() => { setMode('use'); setError(''); setSuccess('') }}>Usa modello</button></div>
    {mode === 'save' ? <>
      <p>I campi collegati diventano segnaposto riutilizzabili. Il testo scritto liberamente rimane nel modello: controlla che non contenga dati del precedente cliente.</p>
      <label>Nome del modello<input aria-label="Nome del modello personale" value={title} maxLength={100} disabled={busy || intent.current !== null} onChange={event => setTitle(event.target.value)}/></label>
      <button type="button" disabled={busy || !title.trim()} onClick={() => void save()}>{busy ? 'Salvataggio…' : intent.current ? 'Riprova salvataggio' : 'Salva modello personale'}</button>
    </> : <>
      <label>Modello<select aria-label="Modello" value={model} disabled={busy} onChange={event => setModel(event.target.value)}><option value="">Scegli il modello</option>{['condiviso', 'personale'].map(scope => <optgroup key={scope} label={scope === 'condiviso' ? 'Modelli condivisi' : 'Modelli del mio studio'}>{models.filter(item => (item.ambito || 'personale') === scope).map(item => <option key={item.id} value={item.id}>{item.titolo}</option>)}</optgroup>)}</select></label>
      {catalogLoading && <LoadingState title="Caricamento modelli" message="Lettura dei modelli disponibili per lo studio in corso."/>}
      {catalogError && <p role="alert">{catalogError} <button type="button" onClick={() => setCatalogReload(value => value + 1)}>Riprova caricamento</button></p>}
      {!catalogLoading && !catalogError && !models.length && <p>Nessun modello disponibile.</p>}
      {onMatterChange && <FascicoloSearchSelect options={options} value={matterId} onChange={onMatterChange} disabled={busy} selectionLabel="Fascicolo del modello"/>}
      {onMatterChange && mattersLoading && <LoadingState title="Caricamento fascicoli" message="Lettura dei fascicoli selezionabili in corso."/>}
      {onMatterChange && mattersError && <p role="alert">{mattersError}</p>}
      <button type="button" disabled={busy || catalogLoading || Boolean(catalogError) || !model || !matterId} onClick={() => void prepare()}>Compila con i dati del fascicolo</button>
      {ready && <><p>La compilazione sostituirà il contenuto attuale del documento. Puoi annullarla con il comando Annulla.</p>{ready.mancanti.length > 0 && <p role="status">Da compilare: {ready.mancanti.join(', ')}.</p>}<button type="button" onClick={() => { onApply(ready.html, ready.titolo, ready.mancanti); onClose() }}>Applica modello compilato</button></>}
    </>}
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    </div>
  </Modal>
}
