import { useEffect, useRef, useState } from 'react'
import { Maximize2, Minimize2, ZoomIn, ZoomOut } from 'lucide-react'
import { ensureJson } from '../../lib/apiClient'
import { ActionButton as Button } from './ActionButton'

type Field = { nome: string; etichetta: string; tipo: string; pagina: number; valore: string; opzioni: string[]; sola_lettura: boolean; max_caratteri: number; selezionato: boolean; rettangolo: number[] }
type ModuleData = { campi: Field[]; pagine: { numero: number; larghezza: number; altezza: number }[]; documento: string; versione: number }
export function PdfModulo({ endpoint, previewUrl, busy, save, onDirty }: {
  endpoint: string; previewUrl: string; busy: boolean; save: (values: Record<string, string | boolean>) => Promise<boolean>; onDirty: (dirty: boolean) => void
}) {
  const [data, setData] = useState<ModuleData | null>(null)
  const [values, setValues] = useState<Record<string, string | boolean>>({})
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [dirty, setDirty] = useState(false)
  const [retry, setRetry] = useState(0)
  const surface = useRef<HTMLElement>(null)
  const expandButton = useRef<HTMLSpanElement>(null)
  const [expanded, setExpanded] = useState(false)
  const [zoom, setZoom] = useState(100)
  useEffect(() => {
    if (!expanded) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpanded(false) }
    let wasNative = document.fullscreenElement === surface.current
    const sync = () => {
      if (document.fullscreenElement === surface.current) wasNative = true
      else if (wasNative) setExpanded(false)
    }
    document.addEventListener('keydown', close)
    document.addEventListener('fullscreenchange', sync)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', close)
      document.removeEventListener('fullscreenchange', sync)
      if (document.fullscreenElement === surface.current) void document.exitFullscreen().catch(() => {})
      expandButton.current?.querySelector('button')?.focus({ preventScroll: true })
    }
  }, [expanded])
  const toggleExpanded = () => {
    setExpanded(!expanded)
    // Same in-app expansion contract as the fascicolo table. The native API
    // is optional in embedded browsers; no remount, new tab or data reload.
    if (!expanded && surface.current?.requestFullscreen) void surface.current.requestFullscreen().catch(() => {})
  }
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    ensureJson<ModuleData>(endpoint, { signal: abort.signal }).then((r) => { setData(r); setValues({}); setPage(1) })
      .catch((e) => { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : 'Modulo non disponibile.') })
    return () => abort.abort()
  }, [endpoint, retry])
  useEffect(() => { onDirty(dirty); return () => onDirty(false) }, [dirty, onDirty])
  useEffect(() => { const guard = (e: BeforeUnloadEvent) => { if (dirty) { e.preventDefault(); e.returnValue = '' } }; window.addEventListener('beforeunload', guard); return () => window.removeEventListener('beforeunload', guard) }, [dirty])
  if (error) return <p role="alert">{error} <Button onClick={() => setRetry(retry + 1)}>Rileggi modulo</Button></p>
  if (!data) return <p role="status">Lettura dei campi predisposti dall’organismo…</p>
  const sheet = data.pagine[page - 1]
  const fields = data.campi.filter((f) => f.pagina === page)
  const update = (name: string, value: string | boolean) => { setValues((old) => ({ ...old, [name]: value })); setDirty(true) }
  return <section ref={surface} className={`iu-mediazione-block iu-mediazione-pdf-editor${expanded ? ' iu-mediazione-pdf-editor--expanded' : ''}`} aria-label="Compilazione del modulo originale">
    <header className="iu-mediazione-pdf-header">
      <h3>Compila il modulo dell’organismo</h3>
      <span ref={expandButton}><Button onClick={toggleExpanded} aria-pressed={expanded} aria-label={expanded ? 'Torna alla vista normale del modulo' : 'Apri il modulo a tutto schermo'}>
        {expanded ? <Minimize2 size={16} aria-hidden="true" /> : <Maximize2 size={16} aria-hidden="true" />}
        {expanded ? 'Vista normale' : 'Tutto schermo'}
      </Button></span>
    </header>
    <p>Scrivi nei campi del PDF originale. Verrà salvata una copia distinta nel fascicolo: modello, firme e dichiarazioni non vengono confermati automaticamente. Controlla tutte le pagine prima di usare la copia.</p>
    <div className="iu-mediazione-actions"><Button disabled={page === 1} onClick={() => setPage(page - 1)}>Pagina precedente</Button><strong>Pagina {page} di {data.pagine.length}</strong><Button disabled={page === data.pagine.length} onClick={() => setPage(page + 1)}>Pagina successiva</Button></div>
    <div className="iu-mediazione-actions" aria-label="Ingrandimento del modulo">
      <Button disabled={zoom <= 50} onClick={() => setZoom(Math.max(50, zoom - 25))} aria-label="Riduci il modulo"><ZoomOut size={16}/></Button>
      <output aria-live="polite">{zoom}%</output>
      <Button disabled={zoom >= 200} onClick={() => setZoom(Math.min(200, zoom + 25))} aria-label="Ingrandisci il modulo"><ZoomIn size={16}/></Button>
      <Button onClick={() => setZoom(100)}>Dimensione normale</Button>
    </div>
    {!data.campi.length ? <p>Questo PDF non contiene campi predisposti. Il modello originale rimane consultabile; non è stato trasformato o compilato automaticamente.</p> : null}
    <div className="iu-mediazione-pdf-scroll" tabIndex={0} aria-label="Pagina del modulo, scorrimento orizzontale disponibile">
      <div className="iu-mediazione-pdf-sheet" style={{ aspectRatio: `${sheet.larghezza} / ${sheet.altezza}`, width: `${8 * zoom}px` }}>
        <img src={`${previewUrl}?viewer=mobile&page=${page}`} alt={`Pagina ${page} del modulo dell’organismo`} onError={() => setError('Anteprima non disponibile. Non compilare senza verificare la pagina.')} />
        {fields.map((f, i) => {
          const current = values[f.nome] ?? (f.tipo === 'CheckBox' ? f.selezionato : f.valore)
          const style = { left: `${f.rettangolo[0] * 100}%`, top: `${f.rettangolo[1] * 100}%`, width: `${f.rettangolo[2] * 100}%`, height: `${f.rettangolo[3] * 100}%` }
          const label = `${f.etichetta || 'Campo'} — pagina ${page}, campo ${i + 1}`
          return <div key={`${f.nome}-${i}`} className="iu-mediazione-pdf-field" style={style}>
            {f.tipo === 'CheckBox' ? <input type="checkbox" aria-label={label} title={label} disabled={f.sola_lettura || busy} checked={Boolean(current)} onChange={(e) => update(f.nome, e.target.checked)} /> : f.opzioni.length ? <select aria-label={label} title={label} disabled={f.sola_lettura || busy} value={String(current)} onChange={(e) => update(f.nome, e.target.value)}><option value="">Scegli</option>{f.opzioni.map((v) => <option key={v}>{v}</option>)}</select> : <textarea aria-label={label} title={label} disabled={f.sola_lettura || busy} rows={1} maxLength={f.max_caratteri} value={String(current)} onChange={(e) => update(f.nome, e.target.value)} />}
          </div>
        })}
      </div>
    </div>
    <Button disabled={!dirty || busy} onClick={async () => { if (await save(values)) { setDirty(false); setValues({}) } }}>{busy ? 'Salvataggio della copia…' : 'Salva copia compilata nel fascicolo'}</Button>
    {dirty ? <p role="status">Compilazione da salvare. Salva la copia prima di cambiare organismo o procedimento.</p> : null}
  </section>
}
