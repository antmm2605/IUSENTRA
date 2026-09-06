import { useState } from 'react'
import { ActionButton as Button } from './ActionButton'
import type { Document, Preview } from './types'

export function DocumentoMediazione({ label, selected, docs, update, preview }: {
  label: string; selected: string; docs: Document[]; update: (id: string) => void; preview: (doc: Preview) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [candidate, setCandidate] = useState('')
  const [viewed, setViewed] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const doc = docs.find((d) => d.id === selected)
  const chosen = docs.find((d) => d.id === candidate)
  const show = (d: Document) => { preview({ name: d.nome, url: d.preview, downloadUrl: d.preview.replace('/visualizza', '/scarica') }); setViewed(d.id) }
  return <section className="iu-mediazione-document" aria-label={label}>
    <strong>{label}</strong>
    <p>{doc?.nome || 'Nessun documento collegato per questa funzione.'}</p>
    <div className="iu-mediazione-actions">{doc ? <Button onClick={() => show(doc)} aria-label={`Visualizza ${label}`}>Visualizza</Button> : null}
      <Button aria-expanded={open} onClick={() => { setOpen(!open); setCandidate(''); setConfirmed(false); setViewed('') }}>{doc ? 'Cambia documento' : 'Collega documento verificato'}</Button>
      {doc ? <Button onClick={() => update('')}>Scollega</Button> : null}
    </div>
    {open ? <div className="iu-mediazione-choice">
      <p>Documenti del fascicolo da esaminare, non documenti già riconosciuti come «{label}». Apri il contenuto e verifica che riguardi questa mediazione prima di collegarlo.</p>
      <label>Cerca per nome<input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      <label>Documento da verificare per {label}<select value={candidate} onChange={(e) => { setCandidate(e.target.value); setConfirmed(false); setViewed('') }}><option value="">Scegli il documento da esaminare</option>{docs.filter((d) => d.id === candidate || d.nome.toLocaleLowerCase('it').includes(query.toLocaleLowerCase('it'))).map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}</select></label>
      {chosen ? <Button onClick={() => show(chosen)}>Apri e controlla il contenuto</Button> : null}
      <label className="iu-mediazione-check"><input type="checkbox" disabled={!chosen || viewed !== candidate} checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />Ho verificato che il documento è pertinente a questa mediazione e alla funzione «{label}».</label>
      <Button disabled={!chosen || viewed !== candidate || !confirmed} onClick={() => { update(candidate); setOpen(false) }}>Collega come {label}</Button>
    </div> : null}
  </section>
}
