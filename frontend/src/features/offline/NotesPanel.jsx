import React, {useState} from 'react'
import {saveNote,resolveConflict} from './sync.mjs'
export function NotesPanel({vault,run,refresh}) {
  const [edit,setEdit] = useState(null)
  const [payload,setPayload] = useState({fascicolo_id:vault.state.cases?.[0]?.id || '',title:'',text:'',attachment:null})
  const pending = new Map(vault.state.queue.map(op => [op.id,op]))
  const rows = new Map(Object.values(vault.state.notes).map(note => [note.id,note]))
  for (const op of pending.values()) rows.set(op.id,{...op,version:op.base})
  const start = note => {setEdit(note.id);setPayload(note.payload)}
  return <section><h2>Note di lavoro del fascicolo</h2><p>Le note sono personali. Invii, firme e depositi richiedono la connessione e mantengono il percorso esistente.</p>
    <form onSubmit={e => {e.preventDefault();run(async () => {
      await saveNote(vault,payload,edit || crypto.randomUUID());setEdit(null);setPayload({...payload,title:'',text:'',attachment:null});refresh()
    })}}>
      <label>Fascicolo<select required value={payload.fascicolo_id} onChange={e => setPayload({...payload,fascicolo_id:e.target.value})}>
        <option value="">Seleziona fascicolo</option>{(vault.state.cases || []).map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select></label>
      <label>Titolo<input required maxLength={200} value={payload.title} onChange={e => setPayload({...payload,title:e.target.value})} /></label>
      <label>Nota<textarea required maxLength={32000} value={payload.text} onChange={e => setPayload({...payload,text:e.target.value})} /></label>
      <label>Documento di testo, facoltativo (massimo 64 KB)<input type="file" accept=".txt,text/plain" onChange={e => run(async () => {
        const file = e.target.files?.[0]; if (!file) return
        if (file.size > 65536) throw new Error('Il documento supera 64 KB.')
        setPayload({...payload,attachment:{name:file.name,text:await file.text()}})
      })} /></label>
      {payload.attachment && <p>{payload.attachment.name} <button type="button" onClick={() => setPayload({...payload,attachment:null})}>Rimuovi allegato</button></p>}
      <button disabled={!vault.state.can_write || pending.has(edit)} type="submit">Conserva modifica sul computer</button>
      {edit && <button type="button" onClick={() => {setEdit(null);setPayload({...payload,title:'',text:'',attachment:null})}}>Annulla modifica</button>}
    </form>
    {!rows.size && <p>Nessuna nota. Crea la prima nota dopo la prima sincronizzazione autorizzata.</p>}
    {Array.from(rows.values()).filter(note => !note.deleted).map(note => {
      const op = pending.get(note.id)
      return <article key={note.id}><h3>{note.payload.title}</h3>
        <p>{op?.conflict ? 'Conflitto da riconciliare':op ? 'Modifica locale in attesa':'Salvataggio confermato dal server'}</p>
        <p className="offline-note-text">{note.payload.text}</p>
        {note.payload.attachment && <details><summary>{note.payload.attachment.name}</summary><pre>{note.payload.attachment.text}</pre></details>}
        <button disabled={!!op || !vault.state.can_write} onClick={() => start(note)}>Modifica</button>
        <button disabled={!!op || !vault.state.can_write} onClick={() => run(async () => {
          if (!window.confirm('Eliminare la nota? La richiesta sarà sincronizzata alla riconnessione.')) return
          await saveNote(vault,note.payload,note.id,true);refresh()
        })}>Elimina</button>
      </article>
    })}
    {vault.state.queue.filter(op => op.conflict).map(op => <article key={op.command}><h3>Riconcilia «{op.payload.title}»</h3>
      <p>La tua bozza è conservata. Confrontala con la versione attuale prima di scegliere.</p>
      <h4>Versione sul computer</h4><pre>{op.payload.text}</pre>
      <h4>Versione sul server</h4><pre>{op.conflict.deleted ? 'Nota eliminata':op.conflict.payload?.text}</pre>
      <button onClick={() => run(async () => {await resolveConflict(vault,op.command,false);refresh()})}>Usa la versione del server</button>
      <button disabled={op.conflict.deleted} onClick={() => run(async () => {await resolveConflict(vault,op.command,true);refresh()})}>Proponi la mia versione</button>
      {op.conflict.deleted && <button onClick={() => {setEdit(null);setPayload(op.payload)}}>Copia la bozza in una nuova nota</button>}
    </article>)}
  </section>
}
