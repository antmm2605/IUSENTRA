import { openSourceWindow } from './sourceWindowEvents'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button, ButtonLink } from '../ui/Button'

type Decision = { id: number; title: string; authority: string; date: string; textAvailable: boolean; textHref: string; textStatus?: string; textSourceUrl?: string; textSourceOfficial?: boolean | null }
type Result = { ok: boolean; available?: boolean; message?: string; caseCount?: number; received?: number; expected?: number; status?: string; records: Decision[] }

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
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<Result | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  const submittedQuery = useRef('')
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
    const request = (async () => {
    try {
      const response = await fetch(`/giurisprudenza/sentenzeweb/api?q=${encodeURIComponent(value)}`, { signal: active.signal, cache: 'no-store', credentials: 'same-origin' })
      if (!response.ok) throw new Error('Archivio non disponibile')
      const data = await response.json() as Result
      if (!data.ok || !Array.isArray(data.records)) throw new Error(data.message || 'Risposta non disponibile')
      if (!active.signal.aborted) setResult(data)
      return !active.signal.aborted
    } catch {
      if (!active.signal.aborted) setError('Lettura del corpus non riuscita. I risultati precedenti restano visibili.')
      return false
    } finally {
      if (!active.signal.aborted && !background) setBusy(false)
    }
    })()
    pending.current = request
    void request.finally(() => { if (pending.current === request) pending.current = null })
    return request
  }
  useEffect(() => { void load(''); return () => controller.current?.abort() }, [])
  useOperationalRefresh(['normativa'], async () => { if (!await load(submittedQuery.current, true)) throw new Error('Revisione del corpus non confermata') })
  function search(event: FormEvent) { event.preventDefault(); submittedQuery.current = query; void load(query) }
  return <section id="ricerca-cassazione" className="iu-od-source-card" aria-label="Archivio condiviso Cassazione">
    <h2>Cassazione — testi scaricati</h2>
    <p>Provvedimenti civili e penali acquisiti da SentenzeWeb. La disponibilità del testo OCR non equivale al controllo professionale della citazione o alla disponibilità del PDF.</p>
    {result?.available ? <p role="status">{result.caseCount?.toLocaleString('it-IT')} decisioni salvate · {result.received?.toLocaleString('it-IT')} record della passata su {result.expected?.toLocaleString('it-IT')} dichiarati dalla fonte · {result.status === 'complete' ? 'Passata terminata' : 'Recupero storico o incrementale da completare'}</p> : result?.message ? <p>{result.message}</p> : null}
    {!submittedQuery.current && result?.records.length ? <p>Ultime decisioni acquisite. Inserisci gli estremi o le parole da cercare nei testi.</p> : null}
    <form onSubmit={search} className="iu-openga-form" aria-busy={busy}>
      <label>Cerca nella Cassazione scaricata<input value={query} maxLength={500} onChange={event => setQuery(event.target.value)} /></label>
      <Button type="submit" disabled={busy || !result?.available}>Cerca nei testi scaricati</Button>
      <Button type="button" disabled={busy} onClick={() => { submittedQuery.current = query; void load(query) }}>Aggiorna risultati e stato</Button>
    </form>
    {busy ? <p role="status">Lettura dell’archivio locale…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {result?.records.length ? <ol>{result.records.map(record => <li key={record.id}><article><h3>{record.title}</h3><p>{record.authority} · deposito {record.date || 'non indicato'}</p>{record.textAvailable ? <><ButtonLink href={record.textHref} target="_blank" rel="noreferrer">Leggi testo archiviato</ButtonLink>{record.textSourceOfficial === false ? <p>Trascrizione da fonte non ufficiale: identità collegata, revisione professionale da completare.</p> : null}{record.textSourceUrl ? <ButtonLink href={record.textSourceUrl} target="_blank" rel="noreferrer">Apri la fonte del testo</ButtonLink> : null}</> : <p>{record.textStatus === 'source_notice' ? 'La fonte contiene un avviso di oscuramento: recupero del testo da completare.' : 'Record conservato: testo OCR da completare.'}</p>}<SourceVariants recordId={record.id} /></article></li>)}</ol> : result?.available && !busy ? <p>Nessuna decisione trovata con questa ricerca.</p> : null}
  </section>
}
