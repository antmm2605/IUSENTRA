import { useEffect, useRef, useState } from 'react'
/** Preview fedeli, richieste accorpate e riuso limitato alla sessione del documento. */
export function useViewerPdfPreview(endpoint: string | null, hash: string | undefined, page: number, annotations: object[], setError: (value: string) => void, setImageLoaded: (value: boolean) => void, previewEmpty=false) {
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewPending, setPreviewPending] = useState(false)
  const [previewValid, setPreviewValid] = useState(false)
  const cache=useRef(new Map<string,{url:string;bytes:number}>())
  useEffect(()=>()=>{for(const item of cache.current.values())URL.revokeObjectURL(item.url);cache.current.clear()},[endpoint,hash])
  useEffect(()=>{setPreviewUrl('')},[page,endpoint,hash])
  useEffect(() => {
    setPreviewValid(false)
    if (!endpoint || !hash || (!annotations.length && !previewEmpty)) { setPreviewUrl('');setPreviewPending(false); return }
    const controller = new AbortController()
    setPreviewPending(true); setError('')
    const timer=window.setTimeout(()=>{void (async()=>{
      try {
        const body=JSON.stringify({ annotations, expectedHash: hash })
        const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`${page}:${body}`))
        const key=Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('')
        if(controller.signal.aborted)return
        const existing=cache.current.get(key)
        if(existing){setImageLoaded(false);setPreviewUrl(existing.url);setPreviewValid(true);return}
        const response=await fetch(`${endpoint}/anteprima/${page}`, { method: 'POST', credentials: 'same-origin', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },body })
        if (!response.ok) { const value = await response.json(); throw new Error(value.message || 'Modifica non applicata.') }
        const blob=await response.blob()
        if(controller.signal.aborted)return
        const url=URL.createObjectURL(blob)
        cache.current.set(key,{url,bytes:blob.size})
        while(cache.current.size>4||Array.from(cache.current.values()).reduce((total,item)=>total+item.bytes,0)>16_000_000){
          const oldest=cache.current.keys().next().value
          if(!oldest||oldest===key)break
          const removed=cache.current.get(oldest)!;cache.current.delete(oldest);URL.revokeObjectURL(removed.url)
        }
        setImageLoaded(false);setPreviewUrl(url);setPreviewValid(true)
      } catch(err){if(!controller.signal.aborted)setError(err instanceof Error?err.message:'Anteprima non disponibile.')}
      finally{if(!controller.signal.aborted)setPreviewPending(false)}
    })()},250)
    return () => {window.clearTimeout(timer);controller.abort()}
  }, [annotations, endpoint, hash, page, setError, setImageLoaded,previewEmpty])
  return { previewUrl, previewPending, previewValid, setPreviewValid }
}
