import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button } from '../ui/Button'
import { OpenGAOfficialLookup } from './OpenGAOfficialLookup'

import { searchOpenGA, officialDecisionNumber, type OpenGAResult } from '../opengaSearch'

export function OpenGASearch() {
  const [q, setQ] = useState('')
  const [dal, setDal] = useState('')
  const [al, setAl] = useState('')
  const [semantic, setSemantic] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<OpenGAResult | null>(null)
  const [error, setError] = useState('')
  const [deep, setDeep] = useState<OpenGAResult | null>(null)
  const [selected, setSelected] = useState<'rapid' | 'deep'>('rapid')
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])
  async function search(event: FormEvent) {
    event.preventDefault(); if (busy) return
    const controller = new AbortController()
    request.current = controller
    setBusy(true); setError(''); setResult(null); setDeep(null); setSelected('rapid')
    try {
      await searchOpenGA({ q, dal, al, semantica: semantic }, controller.signal, setResult, setDeep)
    } catch {
      if (!controller.signal.aborted) setError('Ricerca non riuscita. I risultati già disponibili restano visibili.')
    } finally {
      if (!controller.signal.aborted) setBusy(false)
    }
  }
  const deepReady = deep?.ok && deep.semantic_available === true
  const visible = selected === 'deep' && deepReady ? deep : result
  return <section id="ricerca-openga" className="iu-od-source-card" aria-label="Ricerca decisioni amministrative">
    <h2>Decisioni amministrative</h2>
    <p>Il catalogo cerca estremi, oggetto ed esito ufficiali. Per leggere motivazioni e dispositivo, apri «Leggi il testo del provvedimento»: IUSENTRA proverà a recuperare e verificare il documento ufficiale. Oggetto ed esito, da soli, non dimostrano principi di diritto.</p>
    <form onSubmit={search} className="iu-openga-form" aria-busy={busy}>
      <label>Oggetto della ricerca<input value={q} onChange={e => setQ(e.target.value)} required maxLength={1000} disabled={busy} /></label>
      <label>Anno iniziale<input type="number" min="1900" max="2100" value={dal} onChange={e => setDal(e.target.value)} disabled={busy} /></label>
      <label>Anno finale<input type="number" min="1900" max="2100" value={al} onChange={e => setAl(e.target.value)} disabled={busy} /></label>
      <label><input type="checkbox" checked={semantic} onChange={e => setSemantic(e.target.checked)} disabled={busy} /> Ricerca approfondita per significato (più lenta)</label>
      <Button type="submit" disabled={busy || !q.trim()}>Cerca decisioni</Button>
    </form>
    {busy && !result?.ok && <p role="status">Ricerca in corso…</p>}
    {semantic && result?.ok && <div className="iu-openga-progress">
      <p role="status">{deepReady
        ? 'Ricerca approfondita pronta. La lista visibile cambia solo quando lo scegli.'
        : deep || error
          ? deep?.message || error || 'Approfondimento non disponibile. Restano visibili i risultati rapidi.'
          : 'Risultati rapidi disponibili. Approfondimento in corso: puoi continuare a leggerli.'}</p>
      <Button type="button" aria-pressed={selected === 'rapid'} onClick={() => setSelected('rapid')}>Mostra risultati rapidi</Button>
      <Button type="button" disabled={!deepReady} aria-pressed={selected === 'deep'} onClick={() => setSelected('deep')}>Mostra risultati approfonditi</Button>
    </div>}
    {error && !result?.ok && <p role="alert">{error}</p>}
    {result?.message && <p role="status">{result.message}</p>}
    {visible?.ok && <>
      <p>Un’unica lista di massimo 10 decisioni. Oggetto ed esito non dimostrano il principio di diritto.</p>
      {([[selected === 'deep' ? 'Risultati approfonditi' : 'Risultati rapidi', visible.risultati]] as const).map(([title, rows]) => <section key={title}>
        <h3>{title}</h3>
        {!rows.length && <p>Nessun risultato in questa lista.</p>}
        <ol>{rows.map(row => <li key={row.relazione_id + row.oggetto + row.esito}>
          <article><h4>{row.organo_giudicante} · {officialDecisionNumber(row.numero_sentenza, row.anno_sentenza)}/{row.anno_sentenza}</h4>
            <p>{row.oggetto}</p><p>Ricorso: {row.numero_ricorso} · Esito nel dato ufficiale: {row.esito || 'Non indicato'}</p>
            <OpenGAOfficialLookup decision={row} />
            <details><summary>Provenienza</summary><p>OpenGA · Risorsa {row.resource_id}</p><p className="iu-openga-hash">Impronta della fonte: {row.resource_sha256}</p></details>
          </article>
        </li>)}</ol>
      </section>)}
    </>}
  </section>
}
