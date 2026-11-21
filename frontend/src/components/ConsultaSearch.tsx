import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button } from '../ui/Button'
import { openSourceWindow } from './sourceWindowEvents'
import { formatDateLabelIt } from '../formatting'
import { consultaQuery, estremiConsulta } from '../archivioSentenze'

// Archivio delle pronunce della Corte costituzionale conservato in IUSENTRA (dati aperti ufficiali della Consulta,
// fonte «corte_costituzionale» del corpus dello studio): sentenze e ordinanze con oggetto, massime e testo.
type Pronuncia = { id: number; title: string; authority: string; kind?: string; number?: string; year?: number | string; subject?: string; judgment?: string; ruling?: string; date: string; decisionDate?: string; textAvailable: boolean; textHref: string; pdfHref?: string }
type Risposta = { ok: boolean; source: string; records: Pronuncia[]; message?: string }

const ATTESA_MASSIMA_MS = 30_000

export function ConsultaSearch() {
  const [testo, setTesto] = useState('')
  const [anno, setAnno] = useState('')
  const [risposta, setRisposta] = useState<Risposta | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const cercata = useRef('')
  const controller = useRef<AbortController | null>(null)

  async function carica(query: string) {
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    let scaduta = false
    const timer = window.setTimeout(() => { scaduta = true; active.abort() }, ATTESA_MASSIMA_MS)
    setBusy(true)
    setError('')
    try {
      const opzioni: RequestInit = { credentials: 'same-origin', cache: 'no-store', signal: active.signal }
      // L'archivio della Consulta sta nel corpus dello studio o, su altre installazioni, nel corpus pubblico condiviso.
      let response = await fetch(`/giurisprudenza/corpus/api?${query}`, opzioni)
      if (response.status === 400) response = await fetch(`/giurisprudenza/corpus/pubblico/api?${query}`, opzioni)
      if (response.status === 403) throw new Error('permesso')
      const data = await response.json() as Risposta
      if (!response.ok || !data.ok || !Array.isArray(data.records)) throw new Error(data.message || 'risposta')
      if (controller.current === active) setRisposta(data)
    } catch (caught) {
      if (scaduta) setError('L’archivio della Corte costituzionale non ha risposto entro 30 secondi. Per una pronuncia precisa indica numero e anno.')
      else if (!active.signal.aborted) setError(caught instanceof Error && caught.message === 'permesso' ? 'Non hai il permesso per consultare le fonti.' : 'Lettura dell’archivio della Corte costituzionale non riuscita. Riprova tra poco.')
    } finally {
      window.clearTimeout(timer)
      if (controller.current === active) setBusy(false)
    }
  }
  useEffect(() => { void carica(consultaQuery('', '')); return () => controller.current?.abort() }, [])
  function cerca(event: FormEvent) {
    event.preventDefault()
    cercata.current = consultaQuery(testo, anno)
    void carica(cercata.current)
  }
  function apri(record: Pronuncia, pdf = false) {
    openSourceWindow({ href: pdf && record.pdfHref ? record.pdfHref : `${record.textHref}?embed=source`, label: estremiConsulta(record), context: 'Corte costituzionale' }, `consulta-${record.id}-${pdf ? 'pdf' : 'testo'}`, () => {})
  }
  const records = risposta?.records || []
  return <section id="ricerca-consulta" className="iu-od-source-card" aria-label="Corte costituzionale">
    <h2>Corte costituzionale</h2>
    <p>Sentenze e ordinanze della Consulta dai dati aperti ufficiali della Corte, con oggetto e testo integrale conservati in IUSENTRA.</p>
    <form onSubmit={cerca} className="iu-openga-form" aria-busy={busy}>
      <label>Numero, estremi o parole<input value={testo} maxLength={500} placeholder="Es. 194/2018, oppure: licenziamento indennità" onChange={event => setTesto(event.target.value)} /></label>
      <label>Anno<input inputMode="numeric" value={anno} maxLength={4} onChange={event => setAnno(event.target.value.replace(/\D/g, ''))} /></label>
      <Button type="submit" disabled={busy}>Cerca nella Corte costituzionale</Button>
    </form>
    {busy ? <p role="status">Ricerca nell’archivio della Corte costituzionale…</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    {!cercata.current && !busy && records.length ? <p>Ultime pronunce conservate. Cerca per numero e anno o con le parole dell’oggetto e del testo.</p> : null}
    {records.length ? <ol>{records.map(record => <li key={record.id}><article>
      <h3>{estremiConsulta(record)}</h3>
      <dl className="iu-legal-meta">
        <div><dt>Corte</dt><dd>Corte costituzionale</dd></div>
        <div><dt>Numero</dt><dd>{record.number && record.year ? `${record.number}/${record.year}` : 'Non indicato'}</dd></div>
        <div><dt>Deposito</dt><dd>{record.date ? formatDateLabelIt(record.date, 'non indicato') : record.decisionDate ? `decisione ${formatDateLabelIt(record.decisionDate, 'non indicata')}` : 'non indicato'}</dd></div>
        {record.judgment && record.judgment !== record.subject ? <div><dt>Giudizio</dt><dd>{record.judgment}</dd></div> : null}
        <div><dt>Oggetto</dt><dd>{record.subject || 'Oggetto non indicato dalla fonte'}</dd></div>
        {record.ruling ? <div><dt>Dispositivo</dt><dd>{record.ruling}</dd></div> : null}
      </dl>
      {record.textAvailable ? <Button type="button" onClick={() => apri(record)}>Leggi il testo</Button> : <p>Testo non ancora disponibile: gli estremi non sostituiscono il documento.</p>}
      {record.pdfHref ? <Button type="button" onClick={() => apri(record, true)}>Apri il PDF conservato</Button> : null}
    </article></li>)}</ol> : risposta && !busy && !error ? <p>Nessuna pronuncia trovata con questa ricerca.</p> : null}
  </section>
}
