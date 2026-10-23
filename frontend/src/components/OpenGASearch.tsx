import { useState, type FormEvent } from 'react'
import { apiPostJson } from '../lib/apiClient'
import { Button } from '../ui/Button'

type Decision = {
  relazione_id: string; organo_giudicante: string; numero_sentenza: string
  anno_sentenza: number; numero_ricorso: string; oggetto: string; esito: string
  official_search_url: string; resource_id: string; resource_sha256: string
}
type Result = { ok: boolean; message?: string; risultati: Decision[] }

export function OpenGASearch() {
  const [q, setQ] = useState('')
  const [dal, setDal] = useState('')
  const [al, setAl] = useState('')
  const [semantic, setSemantic] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  async function search(event: FormEvent) {
    event.preventDefault(); if (busy) return
    setBusy(true); setError(''); setResult(null)
    try {
      setResult(await apiPostJson<Result>('/api/v1/ui/giurisprudenza/ricerca-amministrativa', { q, dal, al, semantica: semantic }, { ok: false, message: 'Ricerca non disponibile.', risultati: [] }))
    } catch { setError('Ricerca non riuscita. Controlla gli anni e riprova.') }
    finally { setBusy(false) }
  }
  return <section className="iu-od-source-card" aria-label="Ricerca decisioni amministrative" aria-busy={busy}>
    <h2>Decisioni amministrative</h2>
    <p>Estremi, oggetto ed esito dai dati ufficiali OpenGA. Motivazioni e principi non sono disponibili: consulta il testo nella ricerca ufficiale prima di utilizzarli.</p>
    <form onSubmit={search} className="iu-openga-form">
      <label>Oggetto della ricerca<input value={q} onChange={e => setQ(e.target.value)} required maxLength={1000} disabled={busy} /></label>
      <label>Anno iniziale<input type="number" min="1900" max="2100" value={dal} onChange={e => setDal(e.target.value)} disabled={busy} /></label>
      <label>Anno finale<input type="number" min="1900" max="2100" value={al} onChange={e => setAl(e.target.value)} disabled={busy} /></label>
      <label><input type="checkbox" checked={semantic} onChange={e => setSemantic(e.target.checked)} disabled={busy} /> Ricerca approfondita per significato (più lenta)</label>
      <Button type="submit" disabled={busy || !q.trim()}>{busy ? 'Ricerca in corso…' : 'Cerca decisioni'}</Button>
    </form>
    {busy && semantic && <p role="status">Ricerca approfondita in corso. Sul server può richiedere oltre un minuto.</p>}
    {error && <p role="alert">{error}</p>}
    {result?.message && <p role="status">{result.message}</p>}
    {result?.ok && <>
      <p>Un’unica lista di massimo 10 decisioni. Oggetto ed esito non dimostrano il principio di diritto.</p>
      {([['Decisioni trovate', result.risultati]] as const).map(([title, rows]) => <section key={title}>
        <h3>{title}</h3>
        {!rows.length && <p>Nessun risultato in questa lista.</p>}
        <ol>{rows.map(row => <li key={row.relazione_id + row.oggetto + row.esito}>
          <article><h4>{row.organo_giudicante} · {row.numero_sentenza}/{row.anno_sentenza}</h4>
            <p>{row.oggetto}</p><p>Ricorso: {row.numero_ricorso} · Esito nel dato ufficiale: {row.esito || 'Non indicato'}</p>
            <a href="https://www.giustizia-amministrativa.it/dcsnprr" target="_blank" rel="noopener noreferrer">Apri la ricerca ufficiale</a>
            <details><summary>Provenienza</summary><p>OpenGA · Risorsa {row.resource_id}</p><p className="iu-openga-hash">Impronta della fonte: {row.resource_sha256}</p></details>
          </article>
        </li>)}</ol>
      </section>)}
    </>}
  </section>
}
