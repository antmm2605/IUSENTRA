import { useEffect, useRef, useState } from 'react'
import { Button } from '../ui/Button'
import { openSourceWindow } from './sourceWindowEvents'

type Job = { ok: boolean; id: string; stato: string; completati: number; totale: number; avvisi: number; lettore: string; message?: string }
type Info = { ok: boolean; title: string; languages: string[] }
const supported = new Set(['en','fr','pt','es','ja','tr','ru','ar','ko','th','de','vi','ms','id','tl','hi','zh','zh-hant','pl','cs','nl','km','my','fa','gu','ur','te','mr','he','bn','ta','uk','bo','kk','mn','ug','yue'])
const labels: Record<string,string> = {fr:'francese',en:'inglese',de:'tedesco',es:'spagnolo',pt:'portoghese',pl:'polacco',nl:'olandese',cs:'ceco',ru:'russo',uk:'ucraino',el:'greco',ro:'romeno'}

export function CorpusTranslationControl({ recordId, label, languages }: { recordId: number; label?: string; languages?: string[] }) {
  const [info,setInfo] = useState<Info | null>(() => languages ? {ok:true,title:label || 'Provvedimento',languages} : null)
  const [language,setLanguage] = useState('')
  const [job,setJob] = useState<Job | null>(null)
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const current = useRef<AbortController | null>(null)
  const languageKey = languages?.join(',')
  useEffect(() => () => current.current?.abort(),[recordId])
  useEffect(() => {
    const request=new AbortController()
    if (languageKey !== undefined) { setInfo({ok:true,title:label || 'Provvedimento',languages:languageKey ? languageKey.split(',') : []});return () => request.abort() }
    void fetch(`/giurisprudenza/corpus/${recordId}/traduzione-info`,{credentials:'same-origin',cache:'no-store',signal:request.signal}).then(async response => {
      if (!response.ok || response.redirected) throw new Error('Fonte non disponibile')
      const data=await response.json() as Info
      if (!data.ok || !Array.isArray(data.languages)) throw new Error('Lingua non verificata')
      if (!request.signal.aborted) setInfo(data)
    }).catch(() => { if (!request.signal.aborted) setError('Lingua della fonte non verificata.') })
    return () => request.abort()
  },[recordId,languageKey,label])
  const choices=(info?.languages || []).filter(code=>supported.has(code))
  const chosen=language || (choices.length===1 ? choices[0] : '')
  async function post(path: string,body: object,signal: AbortSignal): Promise<Job> {
    const response=await fetch(path,{method:'POST',credentials:'same-origin',cache:'no-store',signal,
      headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || ''},body:JSON.stringify(body)})
    if (!response.headers.get('Content-Type')?.includes('application/json')) throw new Error('Il servizio non ha restituito un esito valido. Nessun nuovo tentativo automatico.')
    let data: Job
    try { data=await response.json() as Job } catch { throw new Error('Esito della traduzione non leggibile. Nessun nuovo tentativo automatico.') }
    if (!response.ok || response.redirected || !data.ok) throw new Error(data.message || 'Traduzione locale non disponibile.')
    if (!/^[0-9a-f]{32}$/.test(data.id) || !Number.isInteger(data.totale) || data.totale<1 || !Number.isInteger(data.completati) || data.completati<0 || data.completati>data.totale || !['in_attesa','in_corso','completa','errore'].includes(data.stato)) throw new Error('Avanzamento della traduzione non verificato.')
    return data
  }
  async function translate() {
    if (!chosen || busy) return
    current.current?.abort()
    const request=new AbortController();current.current=request
    setBusy(true);setError('')
    try {
      let data=await post(`/giurisprudenza/corpus/${recordId}/traduzioni`,{lingua:chosen,riprova:job?.stato==='errore'},request.signal)
      if (request.signal.aborted) return
      setJob(data)
      while (data.stato==='in_attesa' || data.stato==='in_corso') {
        const before=data.completati
        data=await post(`/giurisprudenza/corpus/${recordId}/traduzioni/${data.id}/passo`,{},request.signal)
        if (request.signal.aborted) return
        setJob(data)
        if (data.completati===before && data.stato==='in_corso') await new Promise(resolve=>setTimeout(resolve,1000))
      }
      if (data.stato!=='completa' || !data.lettore) throw new Error('Traduzione interrotta. I passaggi completati sono conservati: puoi riprendere.')
      openSourceWindow({href:data.lettore+'?embed=source',label:`Traduzione italiana — ${info?.title || label || 'Provvedimento'}`.slice(0,240),context:'Traduzione automatica da confrontare con l’originale'},`corpus-traduzione-${data.id}`,()=>{})
    } catch (cause) {
      if (!request.signal.aborted) { setJob(previous=>previous ? {...previous,stato:'errore'} : null); setError(cause instanceof Error ? cause.message : 'Traduzione interrotta. Nessun nuovo tentativo automatico.') }
    } finally { if (!request.signal.aborted) setBusy(false) }
  }
  if (!info) return error ? <p role="status">{error}</p> : null
  if (!choices.length) return null
  return <div className="iu-corpus-translation" aria-busy={busy}>
    {choices.length>1 && <label>Lingua originale<select value={language} disabled={busy} onChange={event=>setLanguage(event.target.value)}><option value="">Seleziona la lingua</option>{choices.map(code=><option key={code} value={code}>{labels[code] || code}</option>)}</select></label>}
    <Button type="button" disabled={busy || !chosen} onClick={()=>void translate()}>{busy ? 'Traduzione in corso…' : job?.stato==='completa' ? 'Apri traduzione italiana' : job?.stato==='errore' || error ? 'Riprendi traduzione in italiano' : 'Traduci in italiano'}</Button>
    {busy && job && <p role="status">Tradotti {job.completati} di {job.totale} passaggi. L’originale resta disponibile.</p>}
    {error && <p role="alert">{error}</p>}
    {!busy && job?.avvisi ? <p role="note">{job.avvisi} passaggi richiedono un confronto puntuale con l’originale.</p> : null}
    <p>Traduzione automatica locale, non ufficiale. Da confrontare con il testo originale prima dell’uso professionale.</p>
  </div>
}
