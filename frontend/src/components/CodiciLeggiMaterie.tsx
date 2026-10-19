import { useMemo, useState } from 'react'
import { matchesCatalogueAct } from './codiciLeggiSearch'
import { groupByMateria, type MateriaAct } from './codiciLeggiGruppi'

type Props = { acts: MateriaAct[]; selected: string; onChoose: (id: string) => void }

// Biblioteca per materia: codici, leggi e decreti raggruppati per area del diritto.
export function CodiciLeggiMaterie({ acts, selected, onChoose }: Props) {
  const [materia, setMateria] = useState('')
  const [tipo, setTipo] = useState('')
  const [query, setQuery] = useState('')
  const tipi = useMemo(() => Array.from(new Set(acts.map(a => a.tipo || 'Altro atto'))).sort((a, b) => a.localeCompare(b, 'it')), [acts])
  const filtered = useMemo(() => acts.filter(a => (!tipo || (a.tipo || 'Altro atto') === tipo) && matchesCatalogueAct(a, query)), [acts, tipo, query])
  const groups = useMemo(() => groupByMateria(filtered), [filtered])
  const allGroups = useMemo(() => groupByMateria(acts.filter(a => !tipo || (a.tipo || 'Altro atto') === tipo)), [acts, tipo])
  const visible = materia ? groups.filter(g => g.materia === materia) : groups
  return <section className="iu-li-normativa-catalogue" aria-label="Codici, leggi e decreti per materia">
    <div className="iu-li-normativa-catalogue-head">
      <div><h3>Codici, leggi e decreti <span>({acts.length})</span></h3><p>Scegli una materia, poi l’atto da consultare.</p></div>
      <label>Trova un atto<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Locazioni, licenziamento, appalti, privacy…" type="search" /></label>
    </div>
    <div className="iu-li-normativa-materie-filtri">
      <div className="iu-li-normativa-materie" role="group" aria-label="Materie">
        <button type="button" aria-pressed={!materia} onClick={() => setMateria('')}>Tutte le materie</button>
        {allGroups.map(g => <button type="button" key={g.materia} aria-pressed={materia === g.materia} onClick={() => setMateria(g.materia)}>{g.materia} <span>{g.acts.length}</span></button>)}
      </div>
      <label>Tipo di atto<select value={tipo} onChange={e => setTipo(e.target.value)}><option value="">Tutti i tipi</option>{tipi.map(t => <option key={t}>{t}</option>)}</select></label>
    </div>
    {visible.map(g => <div key={g.materia} className="iu-li-normativa-materia">
      <h4>{g.materia} <span>({g.acts.length})</span></h4>
      <div className="iu-li-normativa-code-grid">{g.acts.map(a => <button type="button" key={a.id} aria-pressed={selected === String(a.id)} onClick={() => onChoose(String(a.id))}>
        <strong>{a.label}</strong><span>{a.tipo || 'Atto'} · {a.articles.toLocaleString('it-IT')} articoli</span>
      </button>)}</div>
    </div>)}
    {acts.length > 0 && visible.length === 0 ? <p role="status">Nessun atto corrisponde alla ricerca. Modifica le parole cercate, la materia o il tipo.</p> : null}
  </section>
}
