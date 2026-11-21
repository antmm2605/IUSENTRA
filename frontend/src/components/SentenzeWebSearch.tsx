import { openSourceWindow } from './sourceWindowEvents'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button, ButtonLink } from '../ui/Button'

import { formatDateLabelIt } from '../formatting'
import { sentenzeWebQuery, statoArchivioCassazione, type FiltriCassazione as Filtri } from '../archivioSentenze'
type Decision = { id: number; title: string; authority: string; court?: string; branch?: string; number?: string; year?: number | string; section?: string; sectionLabel?: string; kind?: string; subject?: string; date: string; decisionDate?: string; textAvailable: boolean; textHref: string; textStatus?: string; textSourceUrl?: string; textSourceOfficial?: boolean | null }
type Result = { ok: boolean; available?: boolean; message?: string; caseCount?: number | null; received?: number | null; expected?: number | null; status?: string; searchedBy?: string; records: Decision[] }

const ATTESA_MASSIMA_MS = 40_000
const filtriVuoti: Filtri = { q: '', numero: '', anno: '', sezione: '', ramo: '' }
const sezioni: Array<[string, string]> = [['', 'Tutte le sezioni'], ['U', 'Sezioni Unite'], ['1', 'Sezione I'], ['2', 'Sezione II'], ['3', 'Sezione III'], ['4', 'Sezione IV'], ['5', 'Sezione V'], ['6', 'Sezione VI'], ['7', 'Sezione VII'], ['L', 'Sezione lavoro'], ['F', 'Sezione feriale']]

type OriginalVariant = { id: number; title: string; sha256: string; chars: number; textHref: string; textStatus?: string; official?: boolean; sourceUrl?: string }

function SourceVariants({ recordId }: { recordId: number }) {
  const [documents, setDocuments] = useState<OriginalVariant[] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function load() {
    if (documents || busy) return
    setBusy(true)
    try {
      const response = await fetch(`/giurisprudenza/sentenzeweb/${recordId}/documenti`, { credentials: 'same-origin', cache: 'no-store' })
      const data = await response.json() as { ok: boolean; documents: OriginalVariant[] }
      if (!response.ok || !data.ok || !Array.isArray(data.documents)) throw new Error('Varianti non disponibili')
      setDocuments(data.documents)
      setError('')
    } catch { setError('Lettura delle varianti non riuscita. Puoi riprovare riaprendo questa sezione.') }
    finally { setBusy(false) }
  }
  return <details onToggle={event => { if (event.currentTarget.open) void load() }}>
    <summary>Documenti originali e varianti conservate</summary>
    <p>I diversi identificativi della fonte restano conservati. La loro presenza non determina quale variante sia giuridicamente applicabile.</p>
    {busy ? <p role="status">Lettura dei documenti archiviati…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {documents?.length ? <ul>{documents.map(document => <li key={document.id}><ButtonLink href={document.textHref} target="_blank" rel="noreferrer">{document.title || 'Testo della fonte'}</ButtonLink>{document.textStatus === 'source_notice' ? <p>Avviso della fonte: il testo della decisione resta da recuperare.</p> : document.textStatus === 'empty' ? <p>Documento conservato senza testo estratto: recupero da completare.</p> : <p>{document.official === false ? 'Trascrizione da fonte non ufficiale; controllo professionale da completare.' : 'Contenuto della fonte; completezza e controllo professionale da verificare.'}</p>}{document.sourceUrl ? <ButtonLink href={document.sourceUrl} target="_blank" rel="noreferrer">Apri la fonte del documento</ButtonLink> : null}<p>{document.chars.toLocaleString('it-IT')} caratteri · SHA-256 archiviato: {document.sha256}</p></li>)}</ul> : documents ? <p>Nessuna variante distinta registrata; il testo disponibile resta consultabile dal pulsante principale.</p> : null}
  </details>
}

export function SentenzeWebSearch() {
  const [filtri, setFiltri] = useState<Filtri>(filtriVuoti)
  const query = filtri.q
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  const submittedQuery = useRef('')
  const setQuery = (value: string) => setFiltri(current => ({ ...current, q: value }))
  const imposta = (key: keyof Filtri) => (value: string) => setFiltri(current => ({ ...current, [key]: value }))
  useEffect(() => {
    const query = new URLSearchParams(window.location.search)
    const record = query.get('sentenzeweb') || ''
    const document = query.get('documento') || ''
    if (!/^\d+$/.test(record) || (document && !/^\d+$/.test(document))) return
    const href = `/giurisprudenza/sentenzeweb/${record}${document ? `/documenti/${document}` : ''}/testo${window.location.hash}`
    openSourceWindow({ href, label: 'Provvedimento della Cassazione', context: 'Archivio condiviso Cassazione' }, 'collegamento-cassazione', () => {})
  }, [])
  const pending = useRef<Promise<boolean> | null>(null)
  function load(value: string, background = false): Promise<boolean> {
    // Live revisions join a pending read; only a user search supersedes it.
    if (background && pending.current) return pending.current
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    if (!background) setBusy(true)
    setError('')
    let scaduta = false
    const timer = window.setTimeout(() => { scaduta = true; active.abort() }, ATTESA_MASSIMA_MS)
    const request = (async () => {
    try {
      const response = await fetch(`/giurisprudenza/sentenzeweb/api?${value}`, { signal: active.signal, cache: 'no-store', credentials: 'same-origin' })
      if (!response.ok) throw new Error('Archivio non disponibile')
      const data = await response.json() as Result
      if (!data.ok || !Array.isArray(data.records)) throw new Error(data.message || 'Risposta non disponibile')
      if (!active.signal.aborted) setResult(data)
      return !active.signal.aborted
    } catch {
      if (scaduta) {
        setError('La ricerca nei testi non ha risposto entro 40 secondi. Per una pronuncia precisa indica numero e anno: la ricerca per estremi risponde subito.')
        if (!background) setBusy(false)
      } else if (!active.signal.aborted) setError('Lettura dell’archivio non riuscita. I risultati precedenti restano visibili.')
      return false
    } finally {
      window.clearTimeout(timer)
      if (!active.signal.aborted && !background) setBusy(false)
    }
    })()
    pending.current = request
    void request.finally(() => { if (pending.current === request) pending.current = null })
    return request
  }
  useEffect(() => { void load(''); return () => controller.current?.abort() }, [])
  useOperationalRefresh(['normativa'], async () => { if (!await load(submittedQuery.current, true)) throw new Error('Revisione del corpus non confermata') })
  function search(event: FormEvent) { event.preventDefault(); submittedQuery.current = sentenzeWebQuery(filtri); void load(submittedQuery.current) }
  return <section id="ricerca-cassazione" className="iu-od-source-card" aria-label="Corte di cassazione">
    <h2>Corte di cassazione</h2>
    <p>Sentenze, ordinanze e decreti civili e penali scaricati da SentenzeWeb (ItalgiureWeb), la banca dati pubblica della Corte. Il testo è quello della fonte: la citazione in un atto resta da controllare.</p>
    {result?.available ? <p role="status">{statoArchivioCassazione(result)}</p> : null}
    {!submittedQuery.current && result?.records.length ? <p>Ultime decisioni acquisite. Cerca per numero e anno, con la sezione se la conosci, oppure con le parole del testo.</p> : null}
    <form onSubmit={search} className="iu-openga-form" aria-busy={busy}>
      <label>Numero<input inputMode="numeric" value={filtri.numero} maxLength={6} onChange={event => imposta('numero')(event.target.value.replace(/\D/g, ''))} /></label>
      <label>Anno<input inputMode="numeric" value={filtri.anno} maxLength={4} onChange={event => imposta('anno')(event.target.value.replace(/\D/g, ''))} /></label>
      <label>Sezione<select value={filtri.sezione} onChange={event => imposta('sezione')(event.target.value)}>{sezioni.map(([value, label]) => <option key={value || 'tutte'} value={value}>{label}</option>)}</select></label>
      <label>Ramo<select value={filtri.ramo} onChange={event => imposta('ramo')(event.target.value)}><option value="">Civile e penale</option><option value="civile">Civile</option><option value="penale">Penale</option></select></label>
      <label>Estremi o parole nel testo<input value={query} maxLength={500} placeholder="Es. 5425/2021 sezioni unite, oppure: responsabilità medica onere della prova" onChange={event => setQuery(event.target.value)} /></label>
      <Button type="submit" disabled={busy || !result?.available}>Cerca nella Cassazione</Button>
      <Button type="button" disabled={busy} onClick={() => { setFiltri(filtriVuoti); submittedQuery.current = ''; void load('') }}>Azzera</Button>
    </form>
    {busy ? <p role="status">Ricerca nell’archivio della Cassazione…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {result?.message && result.available ? <p>{result.message}</p> : null}
    {result?.records.length ? <ol>{result.records.map(record => <li key={record.id}><article>
      <h3>{record.title}</h3>
      <dl className="iu-legal-meta">
        <div><dt>Corte</dt><dd>Corte di cassazione{record.branch ? ` — ${record.branch}` : ''}</dd></div>
        <div><dt>Sezione</dt><dd>{record.sectionLabel || 'Non indicata dalla fonte'}</dd></div>
        <div><dt>Numero</dt><dd>{record.number && record.year ? `${record.kind ? `${record.kind} ` : ''}n. ${record.number}/${record.year}` : 'Non indicato'}</dd></div>
        <div><dt>Deposito</dt><dd>{formatDateLabelIt(record.date, 'non indicato')}</dd></div>
        <div><dt>Oggetto</dt><dd>{record.subject || 'Materia non ancora registrata per questa pronuncia'}</dd></div>
      </dl>
      {record.textAvailable ? <><ButtonLink href={record.textHref} target="_blank" rel="noreferrer">Leggi il testo</ButtonLink>{record.textSourceOfficial === false ? <p>Trascrizione da fonte non ufficiale: identità collegata, revisione professionale da completare.</p> : null}{record.textSourceUrl ? <ButtonLink href={record.textSourceUrl} target="_blank" rel="noreferrer">Apri la fonte del testo</ButtonLink> : null}</> : <p>{record.textStatus === 'source_notice' ? 'La fonte contiene un avviso di oscuramento: recupero del testo da completare.' : 'Testo non ancora disponibile nella fonte.'}</p>}
      <SourceVariants recordId={record.id} />
    </article></li>)}</ol> : result?.available && !busy && !result.message ? <p>Nessuna decisione trovata con questa ricerca.</p> : null}
  </section>
}
