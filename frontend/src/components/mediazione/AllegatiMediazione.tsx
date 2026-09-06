import { useState } from 'react'
import { ActionButton as Button } from './ActionButton'
import type { Document, Preview } from './types'

export function AllegatiMediazione({ docs, selected, change, preview }: {
  docs: Document[]; selected: string[]; change: (ids: string[]) => void; preview: (doc: Preview) => void
}) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const filtered = docs.filter((d) => !selected.includes(d.id) && d.nome.toLocaleLowerCase('it').includes(query.toLocaleLowerCase('it')))
  const show = (d: Document) => preview({ name: d.nome, url: d.preview, downloadUrl: d.preview.replace('/visualizza', '/scarica') })
  return <section aria-label="Allegati della mediazione">
    <h3>Allegati della mediazione</h3>
    <p>Puoi collegare più documenti, oltre all’istanza. La selezione non invia file all’organismo e non modifica gli originali del fascicolo.</p>
    <p aria-live="polite">{selected.length} allegati selezionati.</p>
    {selected.length ? <ul className="iu-mediazione-attachments">{selected.map((id) => {
      const doc = docs.find((d) => d.id === id)
      return <li key={id}><span>{doc?.nome || 'Documento non disponibile'}</span><div className="iu-mediazione-actions">{doc ? <Button onClick={() => show(doc)} aria-label={`Visualizza allegato ${doc.nome}`}>Visualizza</Button> : null}<Button onClick={() => change(selected.filter((v) => v !== id))} aria-label={`Scollega allegato ${doc?.nome || ''}`}>Scollega</Button></div></li>
    })}</ul> : <p>Nessun allegato collegato.</p>}
    <Button aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Chiudi selezione allegati' : 'Aggiungi documenti dal fascicolo'}</Button>
    {open ? <div className="iu-mediazione-block">
      <label>Cerca documento da allegare<input type="search" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
      <ul className="iu-mediazione-attachments">{filtered.map((doc) => <li key={doc.id}>
        <label className="iu-mediazione-check"><input type="checkbox" checked={false} onChange={() => change([...selected, doc.id])} />{doc.nome}</label>
        <Button onClick={() => show(doc)} aria-label={`Visualizza prima di allegare ${doc.nome}`}>Visualizza</Button>
      </li>)}</ul>
      {!filtered.length ? <p>Nessun altro documento corrisponde alla ricerca.</p> : null}
    </div> : null}
  </section>
}
