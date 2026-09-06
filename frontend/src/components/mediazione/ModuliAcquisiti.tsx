import { ActionButton as Button } from './ActionButton'
import { formatDateTimeIt } from '../../formatting'
import type { Document, Preview, Procedure } from './types'
import { text } from './types'

export function ModuliAcquisiti({ value, change, docs, preview }: {
  value: Procedure; change: (patch: Partial<Procedure>) => void; docs: Document[]; preview: (doc: Preview) => void
}) {
  const modules = (value.moduli_organismo || []).filter((m) => m.fonte.organismo_numero === value.organismo_numero)
  const show = (id: string) => { const d = docs.find((doc) => doc.id === id); if (d) preview({ name: d.nome, url: d.preview, downloadUrl: d.preview.replace('/visualizza', '/scarica') }) }
  return <section className="iu-mediazione-block" aria-label="Moduli dell’organismo acquisiti">
    <h3>Moduli dell’organismo acquisiti</h3>
    <p>Qui compaiono soltanto i moduli acquisiti dalle risorse dell’organismo scelto. I provvedimenti e gli altri atti del fascicolo non sono moduli dell’ente.</p>
    {modules.length ? <>
      <label>Modulo dell’organismo da compilare<select value={text(value, 'modulo_ufficiale_documento')} onChange={(e) => change({ modulo_ufficiale_documento: e.target.value, modulo_verificato: false })}><option value="">Scegli fra i moduli acquisiti</option>{modules.map((m) => <option key={m.documento} value={m.documento}>{m.fonte.titolo || m.nome}</option>)}</select></label>
      <ul className="iu-mediazione-attachments">{modules.map((m) => <li key={m.documento}><div><strong>{m.fonte.titolo || m.nome}</strong><p>Acquisito il {formatDateTimeIt(m.fonte.acquisito_il)} · <a href={m.fonte.url} target="_blank" rel="noopener noreferrer">Fonte dell’organismo</a></p></div><Button onClick={() => show(m.documento)}>Visualizza originale</Button>{m.copie_compilate?.map((id, i) => {
        const copy = docs.find((d) => d.id === id)
        return <span key={id}><Button onClick={() => show(id)}>Visualizza copia {i + 1}</Button>{copy && /\.docx?$/i.test(copy.nome) ? <a href={copy.preview.replace('/visualizza', '/editor')} target="_blank" rel="noopener noreferrer">Compila la copia nell’editor</a> : null}</span>
      })}</li>)}</ul>
    </> : <p>Nessun modulo acquisito per questo organismo. Usa «Acquisisci modulo nel fascicolo» nelle sue risorse, sopra.</p>}
    {(value.moduli_organismo || []).some((m) => m.fonte.organismo_numero !== value.organismo_numero) ? <p>I moduli acquisiti per altri organismi restano conservati nel fascicolo, ma non sono proposti per questo ente.</p> : null}
  </section>
}
