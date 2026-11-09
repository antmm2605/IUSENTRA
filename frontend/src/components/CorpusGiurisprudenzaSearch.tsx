import { CorpusTranslationControl } from './CorpusTranslationControl'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import type { GiurisprudenzaSource } from '../giurisprudenzaData'
import { Button } from '../ui/Button'
import { openSourceWindow } from './sourceWindowEvents'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { createCorpusRequestGate } from '../corpusSearchRequest'

type Decision = { id: number; title: string; authority: string; date: string; decisionDate?: string; languages?: string[]; textAvailable: boolean; textHref: string; pdfHref?: string }
type Result = { ok: boolean; source: string; records: Decision[]; message?: string }
const languageLabels: Record<string,string> = {it:"italiano",fr:"francese",en:"inglese",hu:"ungherese"}
const dateIt = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.slice(8)+'/'+value.slice(5,7)+'/'+value.slice(0,4) : value || 'non indicata'

export function CorpusGiurisprudenzaSearch({ sources }: { sources: GiurisprudenzaSource[] }) {
  const choices = useMemo(() => sources.flatMap(item => {
    if (['cassazione','cassazione_sentenzeweb','openga','manuale_interno'].includes(item.id) || item.accessMode === 'Materiale autorizzato') return []
    const entries = []
    if ((item.sharedCorpusCount ?? 0) > 0) entries.push({key:`pubblico:${item.id}`, item, public:true, count:item.sharedCorpusCount})
    if ((item.corpusCount ?? 0) > 0) entries.push({key:item.id, item, public:false, count:item.corpusCount})
    return entries
  }),[sources])
  const [source,setSource] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('corpus_fonte')
    return choices.find(entry => entry.item.id === requested)?.key || choices[0]?.key || ''
  })
  const [query,setQuery] = useState('')
  const submitted = useRef('')
  const [result,setResult] = useState<Result | null>(null)
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const [requests] = useState(createCorpusRequestGate)
  function load(code: string,value: string): Promise<boolean> {
    const choice = choices.find(entry => entry.key === code)
    if (!choice) return Promise.resolve(false)
    return requests.run(code,value,async (controller,isCurrent) => {
      if (controller.signal.aborted) return false
      setBusy(true);setError('')
      const timeout = window.setTimeout(() => controller.abort(), 25000)
      try {
        const response = await fetch(`/giurisprudenza/corpus${choice.public ? '/pubblico' : ''}/api?${new URLSearchParams({fonte:choice.item.id,q:value})}`,{credentials:'same-origin',cache:'no-store',signal:controller.signal})
        if (!response.ok || response.redirected) throw new Error('Archivio non disponibile')
        const data = await response.json() as Result
        if (!data.ok || data.source !== choice.item.id || !Array.isArray(data.records)) throw new Error('Risposta non valida')
        if (!isCurrent() || controller.signal.aborted) return false
        setResult({...data, source:code})
        return true
      } catch {
        if (isCurrent()) {
          setError(controller.signal.aborted
            ? 'La ricerca ha impiegato troppo tempo. Puoi riprovare o restringere la ricerca.'
            : 'Lettura dell’archivio non riuscita. Nessun nuovo scaricamento è stato avviato.')
        }
        return false
      } finally {
        window.clearTimeout(timeout)
        if (isCurrent()) setBusy(false)
      }
    })
  }
  useEffect(() => { if (!choices.some(entry=>entry.key===source) && choices.length) setSource(choices[0].key) },[choices,source])
  useEffect(() => { void load(source,submitted.current);return requests.cancel },[source])
  useEffect(() => {
    const select = (event: Event) => {
      const code = (event as CustomEvent<unknown>).detail
      const choice = choices.find(entry => entry.item.id === code)
      if (choice) {
        submitted.current='';setQuery('');setSource(choice.key)
        document.getElementById('ricerca-corpus')?.scrollIntoView({behavior:'smooth',block:'start'})
      }
    }
    window.addEventListener('iusentra:corpus-source',select)
    return () => window.removeEventListener('iusentra:corpus-source',select)
  },[choices])
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('corpus_documento') || ''
    const translation = new URLSearchParams(window.location.search).get('corpus_traduzione') || ''
    const scope = new URLSearchParams(window.location.search).get('corpus_ambito') === 'pubblico' ? '/pubblico' : ''
    if (/^\d+$/.test(id) && /^[0-9a-f]{32}$/.test(translation)) openSourceWindow({href:`/giurisprudenza/corpus/${id}/traduzioni/${translation}?embed=source`,label:'Traduzione italiana del provvedimento',context:'Traduzione automatica, non ufficiale'},'corpus-traduzione-collegamento',()=>{})
    else if (/^\d+$/.test(id)) openSourceWindow({href:`/giurisprudenza/corpus${scope}/${id}/testo?embed=source`,label:'Provvedimento archiviato',context:'Corpus dello studio'},'corpus-collegamento',()=>{})
  },[])
  useOperationalRefresh(['normativa'],async () => { if (!await load(source,submitted.current)) throw new Error('Revisione del corpus non confermata') })
  if (!choices.length) return null
  const chosen = choices.find(entry => entry.key === source)
  const records = result?.source === source ? result.records : []
  function search(event: FormEvent) { event.preventDefault();submitted.current=query;void load(source,query) }
  function open(record: Decision,pdf=false) { openSourceWindow({href:pdf ? record.pdfHref! : record.textHref+'?embed=source',label:record.title,context:chosen?.item.label || 'Corpus dello studio'},`corpus-${source}-${record.id}-${pdf?'pdf':'testo'}`,()=>{}) }
  return <section id="ricerca-corpus" className="iu-od-source-card" aria-label="Testi acquisiti dalle fonti">
    <h2>Testi acquisiti dalle fonti</h2>
    <p>Consulta le fonti pubbliche condivise e i documenti conservati dal tuo studio. La ricerca non avvia scaricamenti e non attesta una revisione giuridica.</p>
    <form onSubmit={search} className="iu-openga-form" aria-busy={busy}>
      <label>Fonte dei testi<select value={source} onChange={event=>setSource(event.target.value)}>{choices.map(entry=><option key={entry.key} value={entry.key}>{entry.item.label} · {entry.count?.toLocaleString('it-IT')} {entry.public ? '· Pubblico condiviso' : '· Studio'}</option>)}</select></label>
      <label>Estremi o parole nel testo<input value={query} maxLength={500} onChange={event=>setQuery(event.target.value)} /></label>
      <Button type="submit" disabled={busy && query === submitted.current}>Cerca nell’archivio</Button>
      <Button type="button" disabled={busy && query === submitted.current} onClick={()=>{submitted.current=query;void load(source,query)}}>Aggiorna risultati</Button>
    </form>
    {busy && <p role="status">Lettura del corpus locale…</p>}
    {error && <p role="alert">{error}</p>}
    {!submitted.current && !busy && records.length>0 && <p>Ultimi provvedimenti conservati. Sono mostrati al massimo 20 risultati: usa gli estremi o parole specifiche per restringere la ricerca.</p>}
    {records.length>0 ? <ol>{records.map(record=><li key={record.id}><article><h3>{record.title}</h3><p>{record.authority} · {record.date ? `deposito ${dateIt(record.date)}` : record.decisionDate ? `decisione ${dateIt(record.decisionDate)}` : "data non indicata"}</p>{record.languages?.length ? <p>Lingua originale: {record.languages.map(language => (languageLabels[language] || language)).join(", ")}. Il testo conserva la lingua della fonte.</p> : null}{record.textAvailable ? <Button type="button" onClick={()=>open(record)}>Leggi testo in IUSENTRA</Button> : <p>Testo da acquisire: gli estremi non sostituiscono il documento.</p>}{record.pdfHref && <Button type="button" onClick={()=>open(record,true)}>Apri PDF conservato</Button>}{!chosen?.public && <CorpusTranslationControl recordId={record.id} label={record.title} languages={record.languages}/>}</article></li>)}</ol> : !busy && !error ? <p>Nessun provvedimento trovato per questa fonte e ricerca.</p> : null}
  </section>
}
