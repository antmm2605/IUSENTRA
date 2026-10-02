import { useEffect, useState } from 'react'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'

type Catalogo = { ok: boolean; message?: string; origine: string; avvertenza: string; totale: number; pagina: number; pagine: number
  schede: Array<{ id: string; title: string; research_text: string; correzioni: Array<{ testo: string; fonte: { titolo: string; reader_url: string } }> }> }

export default function ConoscenzaNotifichePanel() {
  const [query, setQuery] = useState('')
  const [pagina, setPagina] = useState(1)
  const [data, setData] = useState<Catalogo | null>(null)
  const [errore, setErrore] = useState('')
  const [loading, setLoading] = useState(false)
  const [source, setSource] = useState<SourceDocument | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true); setErrore('')
      void fetch(`/api/v1/ui/controllo-studio/conoscenza-notifiche?q=${encodeURIComponent(query)}&pagina=${pagina}`, {
        credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal,
      }).then(async (response) => {
        const payload = await response.json() as Catalogo
        if (!response.ok || !payload.ok) throw new Error(payload.message || 'Catalogo non disponibile.')
        setData(payload)
      }).catch((error: unknown) => {
        if (!controller.signal.aborted) setErrore(error instanceof Error ? error.message : 'Catalogo non disponibile.')
      }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [query, pagina])
  return <section className="iu-cs-conoscenza" aria-label="Ricerca sugli adempimenti di notifica">
    <h4>Consulta la ricerca dello studio</h4>
    <p>{data?.avvertenza || 'Indicazioni da confrontare con il testo vigente e con il provvedimento del caso.'}</p>
    <label>Cerca rito, atto o norma<input type="search" value={query} placeholder="Es. lavoro, ricorso, art. 415" onChange={(event) => { setQuery(event.target.value); setPagina(1) }}/></label>
    {errore ? <p role="alert">{errore}</p> : null}
    {loading ? <p role="status">Ricerca in corso…</p> : null}
    {!loading && !errore && data ? <>
      <p>{data.totale} schede · {data.origine}</p>
      {data.schede.map((scheda) => <details key={scheda.id}><summary>{scheda.title}</summary>{scheda.correzioni?.map((correzione, index) => <div key={index} className="iu-cs-conoscenza__correzione"><strong>Correzione verificata sulla fonte ufficiale</strong><p>{correzione.testo}</p><button type="button" onClick={() => setSource({ href: correzione.fonte.reader_url, label: correzione.fonte.titolo, context: 'Fonte ufficiale consultata il 30/09/2026' })}>Leggi {correzione.fonte.titolo}</button></div>)}<div className="iu-cs-conoscenza__testo">{scheda.research_text}</div></details>)}
      {!data.totale ? <p>Nessuna scheda corrispondente. Prova con il nome dell’atto o una singola parola.</p> : null}
      <nav aria-label="Pagine della ricerca"><button type="button" disabled={data.pagina <= 1} onClick={() => setPagina(data.pagina - 1)}>Precedenti</button><span>Pagina {data.pagina} di {data.pagine}</span><button type="button" disabled={data.pagina >= data.pagine} onClick={() => setPagina(data.pagina + 1)}>Successive</button></nav>
    </> : null}
    <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
  </section>
}
