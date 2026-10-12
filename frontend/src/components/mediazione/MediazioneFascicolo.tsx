import { useBusyActivity } from '../../ui/useBusyActivity'
import { useEffect, useRef, useState } from 'react'
import { useOperationalRefresh } from '../../hooks/useOperationalRefresh'
import { Plus, Save, RefreshCw } from 'lucide-react'
import { apiPostJson, ensureJson } from '../../lib/apiClient'
import { formatDateTimeIt } from '../../formatting'
import { ActionButton as Button } from './ActionButton'
import { OrganismoScelta } from './OrganismoScelta'
import { ProcedimentoForm } from './ProcedimentoForm'
import { ModuliAcquisiti } from './ModuliAcquisiti'
import { PdfModulo } from './PdfModulo'
import { text } from './types'
import { newProcedure, states } from './types'
import type { Data, Preview, Procedure } from './types'
import './mediazione.css'
import { hasProcedureDraftChanges, mergeProcedureRefresh } from './mergeProcedureRefresh'

const conflictValue = (value: unknown): string => typeof value === 'string' ? value || 'Non compilato' : typeof value === 'boolean' ? value ? 'Sì' : 'No' : Array.isArray(value) ? `${value.length} elementi: verifica le righe nel modulo.` : 'Verifica il valore nel modulo.'

export default function MediazioneFascicolo({ id, preview, onDocuments }: {
  id: string; preview: (doc: Preview) => void; onDocuments: () => void
}) {
  const base = `/api/fascicoli/${encodeURIComponent(id)}/mediazioni`
  const liveSequence = useRef(0)
  const [data, setData] = useState<Data | null>(null)
  const [selected, setSelected] = useState<Procedure | null>(null)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  useBusyActivity(busy, 'Salvataggio del procedimento di mediazione…')
  const [moduleDirty, setModuleDirty] = useState(false)
  const [moduleOpen, setModuleOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [conflicts, setConflicts] = useState<string[]>([])
  const liveGuard = useRef({ dirty, busy, moduleDirty, selectedId: selected?.id, selected })
  liveGuard.current = { dirty, busy, moduleDirty, selectedId: selected?.id, selected }
  const refresh = async () => {
    if (!data || liveGuard.current.busy || liveGuard.current.moduleDirty) return false
    const sequence = ++liveSequence.current
    const selectedId = liveGuard.current.selectedId
    const result = await ensureJson<Data>(base, { activity: false })
    if (sequence !== liveSequence.current || liveGuard.current.busy
      || liveGuard.current.moduleDirty || liveGuard.current.selectedId !== selectedId) return false
    if (!result.ok || result.id_fascicolo !== id) throw new Error('Aggiornamento della mediazione non confermato.')
    setData(result)
    const incoming = result.procedimenti.find(procedure => procedure.id === selectedId)
    const previous = data.procedimenti.find(procedure => procedure.id === selectedId)
    const current = liveGuard.current.selected
    if (current?.id && !incoming) setError('Il procedimento non è più disponibile: la bozza è conservata.')
    if (current?.id && incoming && previous) {
      const merged = mergeProcedureRefresh(current, previous, incoming)
      setConflicts(existing => [...new Set([...existing, ...merged.conflicts])])
      setSelected(merged.values)
      setDirty(hasProcedureDraftChanges(merged.values, incoming))
    }
    return true
  }
  useOperationalRefresh(['fascicoli'], refresh)
  useEffect(() => {
    liveSequence.current += 1
    const abort = new AbortController()
    setError('')
    ensureJson<Data>(base, { signal: abort.signal }).then((r) => { setData(r); setSelected(r.procedimenti[0] || null) })
      .catch((e: unknown) => { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : 'Mediazione non disponibile.') })
    return () => { liveSequence.current += 1; abort.abort() }
  }, [base, retry])
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [dirty])
  const change = (patch: Partial<Procedure>) => { setSelected((p) => p ? { ...p, ...patch } : null); setDirty(true); setMessage('') }
  const choose = (next: Procedure) => {
    if (dirty || moduleDirty) { setError('Salva le modifiche prima di cambiare procedimento.'); return }
    setError(''); setMessage(''); setModuleOpen(false); setConflicts([]); setSelected(next)
  }
  const resolveConflict = (key: string, useSaved: boolean) => {
    const current = liveGuard.current.selected
    const persisted = data?.procedimenti.find(procedure => procedure.id === current?.id)
    if (!current || !persisted) return
    const values = useSaved ? { ...current, [key]: persisted[key] } : current
    setSelected(values)
    setDirty(hasProcedureDraftChanges(values, persisted))
    setConflicts(fields => fields.filter(field => field !== key))
    setError('')
  }
  const save = async (resource = '', body: unknown = selected) => {
    if (!selected || busy || conflicts.length) return false
    liveSequence.current += 1
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await apiPostJson<Data>(`${base}${resource}`, body, { ok: false, message: 'Connessione interrotta. Le modifiche restano nel modulo.' } as Data)
      if (!result.ok) throw new Error(result.message || 'Salvataggio non riuscito.')
      if (result.id_fascicolo !== id) throw new Error('Risposta riferita a un fascicolo diverso: aggiornamento non confermato.')
      setData(result)
      setSelected(result.procedimenti.find((p) => p.id === selected.id) || result.procedimenti[result.procedimenti.length - 1])
      setDirty(false)
      setMessage(resource.endsWith('/campi') ? 'Copia compilata salvata nel fascicolo. L’originale non è stato modificato.' : resource.endsWith('/copia') ? 'Copia Word creata: aprila nell’editor per compilarla. Il modulo originale resta invariato.' : resource.endsWith('/bozza') ? 'Bozza salvata nel fascicolo: non sostituisce il modulo dell’organismo.' : resource ? 'Modulo acquisito e collegato a questo procedimento. Aprilo e verifica i campi da compilare.' : 'Procedimento salvato nel fascicolo, con storico della modifica.')
      if (resource) onDocuments()
      return true
    } catch (e) { setError(e instanceof Error ? e.message : 'Operazione non riuscita.'); return false }
    finally { setBusy(false) }
  }
  if (!data) return <div className="iu-mediazione">{error ? <p role="alert">{error} <Button onClick={() => setRetry(retry + 1)}>Riprova</Button></p> : <p role="status">Caricamento mediazioni del fascicolo…</p>}</div>
  const currentModule = selected ? data.documenti.find((d) => d.id === text(selected, 'modulo_ufficiale_documento')) : null
  return <div className="iu-mediazione" aria-busy={busy}>
    <p>Gestisci la mediazione senza perdere il collegamento alla pratica: organismo e moduli, parti, deposito, incontri ed esito. Le trasmissioni all’organismo richiedono un’azione esplicita dell’avvocato sul canale previsto.</p>
    <div className="iu-mediazione-actions">
      <Button disabled={!data.can_write || busy || dirty || moduleDirty} onClick={() => { choose(newProcedure(data.proposta)); setDirty(true) }}><Plus size={16} />Nuova mediazione</Button>
      <Button disabled={busy || moduleDirty} onClick={() => { void refresh().catch(e => setError(e instanceof Error ? e.message : 'Aggiornamento non riuscito.')) }}><RefreshCw size={16} />Rileggi dati</Button>
    </div>
    {data.procedimenti.length ? <label>Procedimento nel fascicolo<select value={selected?.id || ''} onChange={(e) => { const next = data.procedimenti.find((p) => p.id === e.target.value); if (next) choose(next) }}><option value="" disabled>Nuovo procedimento</option>{data.procedimenti.map((p) => <option key={p.id} value={p.id}>{p.titolo || 'Mediazione'} — {states[p.stato]}</option>)}</select></label> : <p>Nessun procedimento di mediazione registrato in questo fascicolo.</p>}
    {error ? <p className="iu-mediazione-error" role="alert">{error}</p> : null}
    {message ? <p className="iu-mediazione-success" role="status">{message}</p> : null}
    {conflicts.length ? <aside className="iu-mediazione-block" aria-label="Modifiche concorrenti della mediazione"><strong>Modifiche concorrenti: la tua bozza è conservata.</strong><p>Scegli quale valore mantenere prima di salvare. Gli altri campi ricevono gli aggiornamenti confermati.</p>{conflicts.map(key => <div key={key}><strong>{key.replaceAll('_', ' ')}</strong><p>La tua modifica: {conflictValue(selected?.[key])}<br />Valore salvato: {conflictValue(data.procedimenti.find(p => p.id === selected?.id)?.[key])}</p><Button onClick={() => resolveConflict(key, false)}>Mantieni la mia modifica</Button><Button onClick={() => resolveConflict(key, true)}>Usa il valore salvato</Button></div>)}</aside> : null}
    {selected ? <form onSubmit={(e) => { e.preventDefault(); void save() }}>
      <fieldset className="iu-mediazione-form" disabled={busy || !data.can_write || moduleDirty}>
        <OrganismoScelta base={base} value={selected} change={change} busy={busy} dirty={dirty} canWrite={data.can_write} acquire={(url) => save(`/${selected.id}/modulo`, { url, versione: selected.versione })} />
        <ModuliAcquisiti value={selected} change={change} docs={data.documenti} preview={preview} />
        {currentModule?.nome.toLowerCase().endsWith('.pdf') ? <Button disabled={dirty || !selected.id} onClick={() => setModuleOpen(!moduleOpen)}>{moduleOpen ? 'Chiudi compilazione modulo' : 'Compila modulo PDF dell’organismo'}</Button> : null}
        {currentModule && /\.docx?$/i.test(currentModule.nome) ? <Button disabled={dirty || !selected.id} onClick={() => void save(`/${selected.id}/modulo/copia`, { versione: selected.versione })}>Prepara copia Word da compilare</Button> : null}
        <Button disabled={dirty || !selected.id} onClick={() => void save(`/${selected.id}/bozza`, { versione: selected.versione })}>Prepara bozza dai dati della mediazione</Button>
        <ProcedimentoForm value={selected} change={change} docs={data.documenti} preview={preview} />
      </fieldset>
      {moduleOpen && currentModule?.nome.toLowerCase().endsWith('.pdf') ? <PdfModulo key={currentModule.id} endpoint={`${base}/${selected.id}/modulo/campi`} previewUrl={currentModule.preview} busy={busy} onDirty={setModuleDirty}
        onEditWithoutFields={() => preview({ name: currentModule.nome, url: currentModule.preview, downloadUrl: currentModule.preview.replace('/visualizza', '/scarica') })}
        save={(valori) => save(`/${selected.id}/modulo/campi`, { valori, versione: selected.versione })} /> : null}
      {selected.controlli?.some((c) => !c.ok) ? <aside className="iu-mediazione-block" aria-label="Verifiche sui dati salvati"><strong>Prima del deposito — dati dell’ultimo salvataggio</strong><ul>{selected.controlli.filter((c) => !c.ok).map((c) => <li key={c.id}>{c.messaggio}</li>)}</ul></aside> : null}
      <div className="iu-mediazione-save"><span>{dirty ? 'Modifiche da salvare' : 'Nessuna modifica in sospeso'}</span><Button type="submit" tone="primary" disabled={busy || !data.can_write || moduleDirty || Boolean(conflicts.length)}><Save size={16} />{busy ? 'Salvataggio…' : 'Salva procedimento'}</Button></div>
    </form> : null}
    <details className="iu-mediazione-block"><summary>Fonti e storico del procedimento</summary>
      <ul>{data.fonti.map((f) => <li key={f.url}><a href={f.url} target="_blank" rel="noopener noreferrer">{f.titolo}</a></li>)}</ul>
      {data.audit.length ? <ol>{data.audit.map((a) => <li key={a.id}>{formatDateTimeIt(a.timestamp)} — versione {a.versione}, modifica registrata.</li>)}</ol> : <p>Nessuna modifica registrata.</p>}
    </details>
  </div>
}
