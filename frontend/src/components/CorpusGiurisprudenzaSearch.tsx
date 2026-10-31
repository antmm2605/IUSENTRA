import { CorpusTranslationControl } from './CorpusTranslationControl'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import type { GiurisprudenzaSource } from '../giurisprudenzaData'
import { Button } from '../ui/Button'
import { openSourceWindow } from './sourceWindowEvents'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'

type Decision = { id: number; title: string; authority: string; date: string; decisionDate?: string; languages?: string[]; textAvailable: boolean; textHref: string; pdfHref?: string }
type Result = { ok: boolean; source: string; records: Decision[]; message?: string }
const languageLabels: Record<string,string> = {it:"italiano",fr:"francese",en:"inglese",hu:"ungherese"}
const dateIt = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.slice(8)+'/'+value.slice(5,7)+'/'+value.slice(0,4) : value || 'non indicata'

export function CorpusGiurisprudenzaSearch({ sources }: { sources: GiurisprudenzaSource[] }) {
  const choices = useMemo(() => sources.filter(item => (item.corpusCount ?? 0) > 0 && !['cassazione','cassazione_sentenzeweb','openga','manuale_interno'].includes(item.id)),[sources])
  const [source,setSource] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('corpus_fonte')
    return choices.find(item => item.id === requested)?.id || choices[0]?.id || ''
  })
  const [query,setQuery] = useState('')
  const submitted = useRef('')
  const [result,setResult] = useState<Result | null>(null)
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const active = useRef<AbortController | null>(null)
  async function load(code: string,value: string) {
    if (!code) return false
    active.current?.abort()
    const request = new AbortController(); active.current = request
    setBusy(true);setError('')
    try {
      const response = await fetch(`/giurisprudenza/corpus/api?${new URLSearchParams({fonte:code,q:value})}`,{credentials:'same-origin',cache:'no-store',signal:request.signal})
      if (!response.ok || response.redirected) throw new Error('Archivio non disponibile')
      const data = await response.json() as Result
      if (!data.ok || data.source !== code || !Array.isArray(data.records)) throw new Error('Risposta non valida')
      if (!request.signal.aborted) setResult(data)
      return !request.signal.aborted
    } catch {
      if (!request.signal.aborted) setError('Lettura dell’archivio non riuscita. Nessun nuovo scaricamento è stato avviato.')
      return false
    } finally { if (!request.signal.aborted) setBusy(false) }
  }
  useEffect(() => { if (!choices.some(item=>item.id===source) && choices.length) setSource(choices[0].id) },[choices,source])
  useEffect(() => { void load(source,submitted.current);return () => active.current?.abort() },[source])
  useEffect(() => {
    const select = (event: Event) => {
      const code = (event as CustomEvent<unknown>).detail
      if (typeof code === 'string' && choices.some(item => item.id === code)) {
        submitted.current='';setQuery('');setSource(code)
        document.getElementById('ricerca-corpus')?.scrollIntoView({behavior:'smooth',block:'start'})
      }
    }
    window.addEventListener('iusentra:corpus-source',select)
    return () => window.removeEventListener('iusentra:corpus-source',select)
  },[choices])
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('corpus_documento') || ''
    const translation = new URLSearchParams(window.location.search).get('corpus_traduzione') || ''
    if (/^\d+$/.test(id) && /^[0-9a-f]{32}$/.test(translation)) openSourceWindow({href:`/giurisprudenza/corpus/${id}/traduzioni/${translation}?embed=source`,label:'Traduzione italiana del provvedimento',context:'Traduzione automatica, non ufficiale'},'corpus-traduzione-collegamento',()=>{})
    else if (/^\d+$/.test(id)) openSourceWindow({href:`/giurisprudenza/corpus/${id}/testo?embed=source`,label:'Provvedimento archiviato',context:'Corpus dello studio'},'corpus-collegamento',()=>{})
  },[])
  useOperationalRefresh(['normativa'],async () => { if (!await load(source,submitted.current)) throw new Error('Revisione del corpus non confermata') })
  if (!choices.length) return null
  const chosen = choices.find(item => item.id === source)
  const records = result?.source === source ? result.records : []
  function search(event: FormEvent) { event.preventDefault();submitted.current=query;void load(source,query) }
  function open(record: Decision,pdf=false) { openSourceWindow({href:pdf ? record.pdfHref! : record.textHref+'?embed=source',label:record.title,context:chosen?.label || 'Corpus dello studio'},`corpus-${record.id}-${pdf?'pdf':'testo'}`,()=>{}) }
  return <section id="ricerca-corpus" className="iu-od-source-card" aria-label="Testi acquisiti dalle fonti">
    <h2>Testi acquisiti dalle fonti</h2>
    <p>Cerca nei documenti già conservati nello studio e leggili in IUSENTRA. La ricerca non avvia scaricamenti e non attesta una revisione giuridica.</p>
    <form onSubmit={search} className="iu-openga-form" aria-busy={busy}>
      <label>Fonte dei testi<select value={source} onChange={event=>setSource(event.target.value)}>{choices.map(item=><option key={item.id} value={item.id}>{item.label} · {item.corpusCount?.toLocaleString('it-IT')}</option>)}</select></label>
      <label>Estremi o parole nel testo<input value={query} maxLength={500} onChange={event=>setQuery(event.target.value)} /></label>
      <Button type="submit" disabled={busy}>Cerca nell’archivio</Button>
      <Button type="button" disabled={busy} onClick={()=>{submitted.current=query;void load(source,query)}}>Aggiorna risultati</Button>
    </form>
    {busy && <p role="status">Lettura del corpus locale…</p>}
    {error && <p role="alert">{error}</p>}
    {!submitted.current && !busy && records.length>0 && <p>Ultimi provvedimenti conservati. Sono mostrati al massimo 20 risultati: usa gli estremi o parole specifiche per restringere la ricerca.</p>}
    {records.length>0 ? <ol>{records.map(record=><li key={record.id}><article><h3>{record.title}</h3><p>{record.authority} · {record.date ? `deposito ${dateIt(record.date)}` : record.decisionDate ? `decisione ${dateIt(record.decisionDate)}` : "data non indicata"}</p>{record.languages?.length ? <p>Lingua originale: {record.languages.map(language => (languageLabels[language] || language)).join(", ")}. Il testo conserva la lingua della fonte.</p> : null}{record.textAvailable ? <Button type="button" onClick={()=>open(record)}>Leggi testo in IUSENTRA</Button> : <p>Testo da acquisire: gli estremi non sostituiscono il documento.</p>}{record.pdfHref && <Button type="button" onClick={()=>open(record,true)}>Apri PDF conservato</Button>}<CorpusTranslationControl recordId={record.id} label={record.title} languages={record.languages}/></article></li>)}</ol> : !busy && !error ? <p>Nessun provvedimento trovato per questa fonte e ricerca.</p> : null}
  </section>
}
