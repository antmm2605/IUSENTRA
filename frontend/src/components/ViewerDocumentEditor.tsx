import { useEffect, useRef, useState, type PointerEvent, type RefObject } from 'react'
import { Pencil, Save, Undo2, Redo2, ZoomIn, ZoomOut } from 'lucide-react'
import { SourceDocumentModal, SourceDocumentReader, type SourceDocument } from './SourceDocumentModal'
import './ViewerDocumentEditor.css'
import { useViewerPdfPreview } from './useViewerPdfPreview'
import { editorEndpoint, requestJson } from './viewerEditorApi'

type Policy = { editable: boolean; reason: string; hash: string; base: string; studio: boolean }
import type { Mark, PageInfo } from './viewerEditorTypes'
import { ViewerColorSampling, useViewerColorSampler } from './useViewerColorSampler'
import { useViewerPageTools } from './useViewerPageTools'
import { ViewerColorPalette } from './ViewerColorPalette'
import { ViewerImageTools } from './ViewerImageTools'
import { ViewerHandwrittenSignaturePanel } from './ViewerHandwrittenSignaturePanel'
import { ViewerCanvasObjects } from './ViewerCanvasObjects'
type TextSpan = { id: number; text: string; x: number; y: number; width: number; height: number }

export function ViewerDocumentEditor({ source, onDirty, onSaving, readerRotation = 0, readerRef, compactReader = true }: { source: SourceDocument; onDirty: (value: boolean) => void; onSaving?: (value: boolean) => void; readerRotation?: number; readerRef?: RefObject<HTMLIFrameElement | null>; compactReader?: boolean }) {
  const endpoint = editorEndpoint(source.href)
  const [policy, setPolicy] = useState<Policy | null>(null)
  const [open, setOpen] = useState(false)
  const [signatureOpen, setSignatureOpen] = useState(false)
  const [signatureOpenRequest, setSignatureOpenRequest] = useState(0)
  const [pages, setPages] = useState<PageInfo[]>([])
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [tool, setTool] = useState<Mark['type']>('text')
  const [armed, setArmed] = useState(false)
  const [text, setText] = useState('')
  const [size, setSize] = useState(12)
  const [fontFamily, setFontFamily] = useState('helvetica')
  const [bold, setBold] = useState(false)
  const [italic, setItalic] = useState(false)
  const [underline, setUnderline] = useState(false)
  const [align, setAlign] = useState('left')
  const [textRotation, setTextRotation] = useState(0)
  const [listStyle, setListStyle] = useState<Mark['listStyle']>('none')
  const [lineHeight, setLineHeight] = useState(14.4)
  const [margin, setMargin] = useState<number | null>(null)
  const learnedMargin = useRef(.12)
  const [imageOptions, setImageOptions] = useState<Partial<Mark>>({width:.25,height:.15,keepRatio:true})
  const [selectedInsertion, setSelectedInsertion] = useState<number | null>(null)
  const [color, setColor] = useState('#111827')
  const [highlightColor, setHighlightColor] = useState('#fef3c7')
  const [marks, setMarks] = useState<Mark[]>([])
  const [history, setHistory] = useState<Mark[][]>([])
  const [redo, setRedo] = useState<Mark[][]>([])
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [revision, setRevision] = useState(0)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [spans, setSpans] = useState<TextSpan[]>([])
  const [selected, setSelected] = useState<TextSpan | null>(null)
  const [copySource, setCopySource] = useState<SourceDocument | null>(null)
  const [draft, setDraft] = useState<{ x: number; y: number; x1: number; y1: number } | null>(null)
  const { previewUrl, previewPending, previewValid, setPreviewValid } = useViewerPdfPreview(endpoint, policy?.hash, page, marks, setError, setImageLoaded)
  const drag = useRef<{ x: number; y: number; id: number } | null>(null)
  const localReaderRef = useRef<HTMLIFrameElement | null>(null)
  const activeReaderRef = readerRef || localReaderRef
  useViewerPageTools(activeReaderRef, Boolean(policy?.editable), setPage, setOpen, setArmed)
  const sampler = useViewerColorSampler(setStatus, setError)

  useEffect(() => {
    if (!endpoint) return
    const controller = new AbortController()
    requestJson(endpoint, { signal: controller.signal }).then(setPolicy).catch((err) => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Permessi editor non disponibili.')
    })
    return () => controller.abort()
  }, [endpoint])
  useEffect(() => { onDirty(Boolean(marks.length || saving)) }, [marks.length, saving, onDirty])
  useEffect(() => { onSaving?.(saving) }, [saving, onSaving])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (marks.length || saving) { event.preventDefault(); event.returnValue = '' }
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [marks.length, saving])
  useEffect(() => {
    if (!open || !policy?.editable || pages.length) return
    const controller = new AbortController()
    requestJson(`${policy.base}/pdf-meta`, { signal: controller.signal }).then((value) => setPages(value.pages)).catch((err) => {
      if (!controller.signal.aborted) setError(err.message)
    })
    return () => controller.abort()
  }, [open, policy, pages.length])
  useEffect(() => { setImageLoaded(false); setDraft(null); drag.current = null; setArmed(false);sampler.cancel() }, [page, revision])
  useEffect(() => { if (selectedInsertion !== null && !marks[selectedInsertion]) setSelectedInsertion(null) }, [marks, selectedInsertion])
  useEffect(() => {
    setSelected(null); setSpans([])
    if (!open || !['replace','text'].includes(tool) || !endpoint || !policy?.studio) return
    const controller = new AbortController()
    requestJson(`${endpoint}/testo/${page}`, { signal: controller.signal }).then((value) => {
      setSpans(value.spans)
      if(tool==='text' && selectedInsertion===null && value.layout){const v=value.layout;learnedMargin.current=v.x;setMargin(v.x);setLineHeight(v.lineHeightPt);setSize(v.fontSizePt);setFontFamily(v.fontFamily);setBold(v.bold);setItalic(v.italic);setColor(v.color)}
      if (!value.spans.length) setError('Questa pagina non contiene testo digitale modificabile. Puoi inserire nuovo testo o lavorare sul documento sorgente.')
    }).catch((err) => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [open, tool, page, revision, endpoint, policy?.studio])

  const commitMarks = (update: Mark[] | ((previous: Mark[]) => Mark[])) => {
    setHistory((previous)=>[...previous.slice(-49),marks]);setRedo([])
    setMarks(typeof update==='function'?update(marks):update);setStatus('');setError('')
  }
  const add = (mark: Mark) => commitMarks((previous)=>[...previous,mark])
  const point = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) }
  }
  const addText = (x: number, y: number) => {
    if (!open || !armed) return
    if (!text.trim()) { setError('Scrivi il testo da inserire, poi scegli il punto sulla pagina.'); return }
    add({ type: 'text', page, x: margin ?? x, y, text: text.trim(), fontSizePt: size, color, fontFamily, bold, italic, underline, align, rotation: textRotation, listStyle, lineHeightPt:lineHeight })
    setSelectedInsertion(marks.length);setArmed(false)
  }
  const start = (event: PointerEvent<HTMLDivElement>) => {
    if (!open || saving || !imageLoaded || event.button !== 0) return
    if(!armed){setSelectedInsertion(null);setSelected(null);return}
    if (marks.some((mark)=>mark.type==='rotate')) {setError('Salva la rotazione della pagina prima di inserire altri interventi.');return}
    if (tool === 'replace') return
    const p = point(event)
    if (tool === 'text') { addText(p.x, p.y); return }
    if (tool === 'image') {if(!imageOptions.imageData){setError('Carica l’immagine, poi crea il riquadro sulla pagina.');return}}
    event.currentTarget.setPointerCapture(event.pointerId)
    drag.current = { ...p, id: event.pointerId }
    setDraft({ ...p, x1: p.x, y1: p.y })
  }
  const finish = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current || drag.current.id !== event.pointerId) return
    const end = point(event), startPoint = drag.current
    const width = Math.abs(end.x - startPoint.x), height = Math.abs(end.y - startPoint.y)
    drag.current = null; setDraft(null)
    if (width < 0.004 || height < 0.004) { setError('Trascina sulla pagina per delimitare l’area.'); return }
    add({ ...(tool==='image'?imageOptions:{}), type: tool, page, x: Math.min(end.x, startPoint.x), y: Math.min(end.y, startPoint.y), width, height, fillColor: highlightColor })
    if(tool==='image')setSelectedInsertion(marks.length);setArmed(false);setArmed(false)
  }
  const save = async (destination: 'versione' | 'copia' | 'scarica') => {
    if (!endpoint || !policy?.editable || !marks.length || saving || previewPending || !previewValid || !imageLoaded) return
    sampler.cancel();setSaving(true); setError(''); setStatus(destination==='versione'?'Salvataggio della nuova versione...':destination==='copia'?'Salvataggio della copia...':'Preparazione della copia da scaricare...')
    try {
      const response = await fetch(endpoint, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', Accept: destination === 'scarica' ? 'application/pdf' : 'application/json' }, body: JSON.stringify({ annotations: marks, destinazione: destination, expectedHash: policy.hash }) })
      if (destination === 'scarica' && response.ok) {
        const url = URL.createObjectURL(await response.blob())
        const link = document.createElement('a'); link.href = url; link.download = `${source.label.replace(/\.pdf$/i, '')} (copia per condivisione).pdf`; link.click()
        window.setTimeout(() => URL.revokeObjectURL(url), 1000)
        setStatus('Copia scaricata. L’originale nel fascicolo è rimasto intatto.')
      } else {
        const result = await response.json()
        if (!response.ok || result.ok === false) throw new Error(result.message || result.errore || 'Modifiche non salvate.')
        if (destination === 'versione' && result.destinazione === 'versione') { setPolicy({ ...policy, hash: result.documento.hash }); setRevision(Date.now()); setPages([]); setStatus('Nuova versione salvata nel fascicolo. La versione precedente resta nello storico.') }
        else {
          setCopySource({ href: source.href.replace(/\/documenti\/[^/]+\//, `/documenti/${result.documento.id}/`), label: result.documento.nome, context: 'Copia per condivisione. L’originale è rimasto intatto.' })
          setStatus(`Copia salvata nel fascicolo: ${result.documento.nome}. L’originale è rimasto intatto.`)
        }
      }
      setMarks([]); setRedo([]); setHistory([])
    } catch (err) { setStatus(''); setError(err instanceof Error ? err.message : 'Modifiche non salvate.') }
    finally { setSaving(false) }
  }
  const currentPage = pages.find((item) => item.number === page)
  const rotatePage = (degrees: number) => {
    setArmed(false)
    if (marks.some((mark)=>mark.type!=='rotate')) {setError('Salva gli interventi prima di ruotare la pagina.');return}
    const existing = marks.find((mark)=>mark.type==='rotate'&&mark.page===page)
    const total=((existing?.degrees||0)+degrees+360)%360
    commitMarks((previous)=>[...previous.filter((mark)=>!(mark.type==='rotate'&&mark.page===page)),...(total?[{type:'rotate' as const,page,x:0,y:0,degrees:total}]:[])])
    setRedo([]);setError('')
  }
  const formatInsertion = (patch: Partial<Mark>) => {
    if(selectedInsertion!==null) commitMarks((previous)=>previous.map((mark,index)=>index===selectedInsertion?{...mark,...patch}:mark))
  }
  const selectInsertion = (index: number, mark: Mark) => {
    setArmed(false);setSelectedInsertion(index);setText(mark.text||'');setSize(mark.fontSizePt||12);setFontFamily(mark.fontFamily||'helvetica');setBold(Boolean(mark.bold));setItalic(Boolean(mark.italic));setUnderline(Boolean(mark.underline));setAlign(mark.align||'left');setColor(mark.color||'#111827');setTextRotation(mark.rotation||0);setListStyle(mark.listStyle||'none');setLineHeight(mark.lineHeightPt||((mark.fontSizePt||12)*1.2));if(mark.type==='image'){setTool('image');setImageOptions(mark)}else setTool('text')
  }
  const readerUrl = new URL(source.href, window.location.origin)
  if (revision) readerUrl.searchParams.set('iuRevision', String(revision))
  return <ViewerColorSampling.Provider value={sampler}><div className="iu-viewer-edit" onContextMenu={(event)=>{event.stopPropagation();if(open)event.preventDefault()}} onKeyDown={event=>{if(event.key==='Escape'&&sampler.active){event.preventDefault();event.stopPropagation();sampler.cancel()}else if(event.key==='Escape'&&armed){event.preventDefault();event.stopPropagation();setArmed(false);setDraft(null);drag.current=null}}}>
    {endpoint && !(compactReader && !policy?.editable && policy?.reason === 'Questo formato resta consultabile nel lettore e scaricabile.' && !error) ? <div className="iu-viewer-edit__bar">
      {policy?.editable ? <button type="button" aria-expanded={open} aria-controls="iu-viewer-edit-workbench" onClick={() => {sampler.cancel();setArmed(false);setOpen((value) => !value)}} disabled={saving}><Pencil size={15}/>{open ? 'Chiudi strumenti di modifica' : policy.studio ? 'Modifica documento' : 'Prepara copia per condivisione'}</button>
        : <span>{policy?.reason || (error ? error : 'Verifica provenienza e permessi...')}</span>}
      {marks.length ? <span role="status">{marks.length} {marks.length === 1 ? 'intervento da salvare' : 'interventi da salvare'}</span> : null}
      {policy?.editable ? <><button type="button" disabled={saving} aria-expanded={signatureOpen} onClick={() => {sampler.cancel();setArmed(false);setSignatureOpenRequest(value => value + 1);setSignatureOpen(true)}}>Firma grafica</button><button type="button" disabled={saving || !policy.studio} title={policy.studio ? 'Seleziona la riga da modificare nel documento' : 'La modifica del testo è riservata ai PDF prodotti dallo studio e non firmati.'} onClick={() => {sampler.cancel();setSelectedInsertion(null);setSelected(null);setDraft(null);setTool('replace');setOpen(true);setArmed(true)}}>Modifica testo</button>{!policy.studio ? <span>Testo protetto: PDF firmato, acquisito da fonte esterna o senza provenienza dello studio verificata.</span> : null}</> : null}
      {open || marks.length ? <div className="iu-viewer-edit__zoom" role="group" aria-label="Zoom della pagina"><button type="button" title="Riduci" aria-label="Riduci pagina" disabled={zoom<=.5} onClick={()=>setZoom(Math.max(.5,zoom-.25))}><ZoomOut size={16}/></button><button type="button" title="Adatta alla larghezza" onClick={()=>setZoom(1)}>Adatta</button><span>{Math.round(zoom*100)}%</span><button type="button" title="Ingrandisci" aria-label="Ingrandisci pagina" disabled={zoom>=2} onClick={()=>setZoom(Math.min(2,zoom+.25))}><ZoomIn size={16}/></button></div> : null}
    </div> : null}
    {(open || marks.length>0) && policy?.editable ? <section id="iu-viewer-edit-workbench" className={`iu-viewer-edit__workbench${open?'':' is-tools-closed'}`} aria-label={policy.studio ? 'Modifica documento dello studio' : 'Copia per condivisione'}>
      <div className="iu-viewer-edit__tools">
        <div className="iu-viewer-edit__panel-title"><Pencil size={18}/><strong>Strumenti documento</strong></div>
        <div className="iu-viewer-edit__fields">
        <label>Pagina<select value={page} onChange={(event) => setPage(Number(event.target.value))} disabled={saving || !pages.length}>{pages.map((item) => <option key={item.number} value={item.number}>{item.number} di {pages.length}</option>)}</select></label>
        <div className="iu-viewer-edit__rotate-page"><button type="button" disabled={saving || !pages.length} onClick={()=>rotatePage(-90)}>Ruota pagina a sinistra</button><button type="button" disabled={saving || !pages.length} onClick={()=>rotatePage(90)}>Ruota pagina a destra</button></div>
        <label>Strumento<select value={armed?tool:'select'} onChange={(event) => {const value=event.target.value;setArmed(value!=='select');if(value!=='select')setTool(value as Mark['type']);setSelectedInsertion(null);setSelected(null);setDraft(null);drag.current=null;setError('')}} disabled={saving}><option value="select">Seleziona e sposta</option><option value="text">Inserisci testo</option>{policy.studio ? <option value="replace">Modifica testo esistente</option> : null}<option value="image">Inserisci immagine</option><option value="highlight">Evidenzia</option><option value="cover">Oscura contenuto</option></select></label>
        {armed && tool === 'replace' ? <label className="iu-viewer-edit__text">Nuovo testo<textarea aria-label="Nuovo testo" value={text} maxLength={1200} onChange={(event) => setText(event.target.value)} disabled={saving || !selected}/><button type="button" disabled={saving || !selected || !text.trim()} onClick={() => { if (selected) { commitMarks((previous) => [...previous.filter((mark) => !(mark.type === 'replace' && mark.page === page && mark.span === selected.id)), { type: 'replace', page, span: selected.id, x: selected.x, y: selected.y, text, width: selected.width, height: selected.height }]); setSelected(null);setArmed(false) } }}>Applica alla riga selezionata</button></label> : null}
        {tool === 'image' && (armed || selectedInsertion!==null) ? <ViewerImageTools value={selectedInsertion!==null&&marks[selectedInsertion]?.type==='image'?marks[selectedInsertion]:imageOptions} page={currentPage} disabled={saving} onChange={(patch)=>{setImageOptions((previous)=>({...previous,...patch}));if(selectedInsertion!==null&&marks[selectedInsertion]?.type==='image')formatInsertion(patch)}} onError={setError} onNew={()=>{setArmed(true);setTool('image');setSelectedInsertion(null);setImageOptions({width:.25,height:.15,keepRatio:true})}}/> : null}
        {tool === 'text' && (armed || selectedInsertion!==null) ? <>
          <label className="iu-viewer-edit__text">{selectedInsertion===null?'Testo da inserire':'Testo selezionato'}<textarea aria-label="Testo da inserire" value={text} maxLength={1200} onChange={(event) => {setText(event.target.value);formatInsertion({text:event.target.value})}} disabled={saving}/></label>
          {selectedInsertion!==null?<button type="button" onClick={()=>{setArmed(true);setTool('text');setSelectedInsertion(null);setText('')}} disabled={saving}>Inserisci un altro testo</button>:null}
          <label>Elenco<select value={listStyle} disabled={saving} onChange={(event)=>{const value=event.target.value as Mark['listStyle'];setListStyle(value);formatInsertion({listStyle:value})}}><option value="none">Nessun elenco</option><option value="bullet">Elenco puntato</option><option value="number">Elenco numerato</option></select></label>
          <label>Interlinea (pt)<input type="number" min={6} max={100} step={.1} value={lineHeight} disabled={saving} onChange={(event)=>{const value=Math.max(6,Math.min(100,Number(event.target.value)||size*1.2));setLineHeight(value);formatInsertion({lineHeightPt:value})}}/></label>
          <label>Margine sinistro<input type="checkbox" checked={margin!==null} disabled={saving} onChange={(event)=>setMargin(event.target.checked?learnedMargin.current:null)}/>Usa il margine del documento</label>
          <label>Carattere<select value={fontFamily} onChange={(event)=>{setFontFamily(event.target.value);formatInsertion({fontFamily:event.target.value})}} disabled={saving}><option value="helvetica">Helvetica</option><option value="times">Times</option><option value="courier">Courier</option></select></label>
          <label>Dimensione<input type="number" min={6} max={48} value={size} onChange={(event) => {const value=Math.max(6, Math.min(48, Number(event.target.value) || 12));setSize(value);formatInsertion({fontSizePt:value})}} disabled={saving}/></label>
          <div className="iu-viewer-edit__text-style" role="group" aria-label="Stile testo">
            <button type="button" title="Grassetto" aria-label="Grassetto" aria-pressed={bold} disabled={saving} onClick={()=>{setBold(!bold);formatInsertion({bold:!bold})}}><strong>G</strong></button>
            <button type="button" title="Corsivo" aria-label="Corsivo" aria-pressed={italic} disabled={saving} onClick={()=>{setItalic(!italic);formatInsertion({italic:!italic})}}><em>C</em></button>
            <button type="button" title="Sottolineato" aria-label="Sottolineato" aria-pressed={underline} disabled={saving} onClick={()=>{setUnderline(!underline);formatInsertion({underline:!underline})}}><u>S</u></button>
          </div>
          <label>Allineamento<select value={align} onChange={(event)=>{setAlign(event.target.value);formatInsertion({align:event.target.value})}} disabled={saving}><option value="left">Sinistra</option><option value="center">Centro</option><option value="right">Destra</option></select></label>
          <ViewerColorPalette label="Colore testo" value={color} disabled={saving} onChange={value=>{setColor(value);formatInsertion({color:value})}}/>
          <label>Rotazione testo<select value={textRotation} onChange={(event)=>{const value=Number(event.target.value);setTextRotation(value);formatInsertion({rotation:value})}} disabled={saving}><option value={0}>0° · Orizzontale</option><option value={45}>45° · A sinistra</option><option value={90}>90° · A sinistra</option><option value={135}>135° · A sinistra</option><option value={180}>180° · Capovolto</option><option value={225}>135° · A destra</option><option value={270}>90° · A destra</option><option value={315}>45° · A destra</option></select></label>
        </> : null}
        <button type="button" onClick={() => {const previous=history.at(-1);if(previous){setRedo([...redo,marks]);setMarks(previous);setHistory(history.slice(0,-1));setError('');setStatus('')}}} disabled={!history.length || saving}><Undo2 size={15}/>Annulla</button>
        <button type="button" onClick={() => {const next=redo.at(-1);if(next){setHistory([...history,marks]);setMarks(next);setRedo(redo.slice(0,-1));setError('');setStatus('')}}} disabled={!redo.length || saving}><Redo2 size={15}/>Ripristina</button>
        {armed && tool === 'highlight' ? <ViewerColorPalette label="Colore evidenziatore" value={highlightColor} disabled={saving} presets={[["Giallo","#fef3c7"],["Verde","#bbf7d0"],["Azzurro","#bfdbfe"],["Rosa","#fbcfe8"],["Arancione","#fed7aa"]]} onChange={setHighlightColor}/> : null}
        </div>
        <div className="iu-viewer-edit__actions">
        {policy.studio ? <button type="button" className="iu-viewer-edit__save" onClick={() => void save('versione')} disabled={!marks.length || saving || previewPending || !previewValid || !imageLoaded}><Save size={15}/>{saving ? 'Salvataggio...' : 'Salva nuova versione'}</button> : null}
        <button type="button" onClick={() => void save('copia')} disabled={!marks.length || saving || previewPending || !previewValid || !imageLoaded}>Salva copia nel fascicolo</button>
        <button type="button" onClick={() => void save('scarica')} disabled={!marks.length || saving || previewPending || !previewValid || !imageLoaded}>Scarica copia</button>
        </div>
      </div>
      <div className="iu-viewer-edit__messages">
      <p className="iu-viewer-edit__help">{policy.studio ? '' : 'Originale protetto: lavori su una copia. '}{sampler.active ? 'Contagocce: clicca il colore sulla pagina. Esc annulla il prelievo; nessun oggetto viene inserito.' : !armed ? 'Modalità selezione: clicca un oggetto per modificarlo o trascinalo per spostarlo. Per inserire altro, scegli uno strumento.' : tool === 'replace' ? 'Seleziona il testo, correggilo e premi Applica. Il carattere originale viene conservato.' : tool === 'text' ? 'Clicca per inserire il testo. Trascinalo per spostarlo; usa le frecce per regolare la posizione.' : tool === 'image' ? 'Carica un’immagine e trascina per crearne il riquadro. Selezionala per spostarla, ridimensionarla o aprire il menu con il tasto destro.' : tool === 'cover' ? 'Trascina sull’area da oscurare. Il contenuto verrà rimosso dalla copia o nuova versione.' : 'Scegli un colore e trascina sulle aree da evidenziare. Dopo ogni intervento si torna alla selezione. Esc annulla lo strumento.'}</p>
      {error ? <p role="alert" className="iu-viewer-edit__error">{error}</p> : null}
      {status ? <p role="status" className="iu-viewer-edit__status">{status}</p> : null}
      {previewPending ? <p role="status" className="iu-viewer-edit__help">Preparazione dell’anteprima fedele al PDF...</p> : null}
      </div>
      <div className="iu-viewer-edit__paper-scroll">
        {!pages.length ? <p role="status">Caricamento delle pagine...</p> : <div className="iu-viewer-edit__paper" style={{cursor:sampler.active||armed?'crosshair':'default',...(zoom===1?{}:{width:`${zoom*100}%`})}} role="button" aria-label="Pagina del documento: seleziona gli oggetti o scegli uno strumento per modificare" tabIndex={0}
          onPointerDown={event=>{if(sampler.active)sampler.capture(event);else start(event)}} onPointerMove={(event) => { if (drag.current) { const p = point(event); setDraft({ x: drag.current.x, y: drag.current.y, x1: p.x, y1: p.y }) } }} onPointerUp={finish} onPointerCancel={() => { drag.current = null; setDraft(null) }} onKeyDown={(event) => { if (event.key === 'Enter' && tool === 'text' && imageLoaded && !saving) addText(0.12, 0.12) }}>
          <img src={previewUrl || `${policy.base}/pdf-pagina/${page}.png?v=${revision}`} alt={`Pagina ${page} di ${source.label}`} draggable={false} onLoad={() => setImageLoaded(true)} onError={() => { setImageLoaded(false); setPreviewValid(false); setError('Pagina non caricata. Riapri il pannello per riprovare.') }}/>
          {open && armed && tool === 'replace' ? spans.map((span) => <button key={span.id} type="button" className={`iu-viewer-edit__span${selected?.id === span.id ? ' is-selected' : ''}`} aria-label={`Modifica testo: ${span.text}`} style={{ left: `${span.x * 100}%`, top: `${span.y * 100}%`, width: `${span.width * 100}%`, height: `${span.height * 100}%` }} onPointerDown={(event) => event.stopPropagation()} onClick={() => { setSelected(span); setText(marks.find((mark) => mark.type === 'replace' && mark.span === span.id && mark.page === page)?.text || span.text) }} disabled={saving}/> ) : null}
          {open && !armed && !sampler.active ? <ViewerCanvasObjects marks={marks} page={page} pageInfo={currentPage} disabled={saving} selected={selectedInsertion} onSelect={selectInsertion} onChange={commitMarks}/> : null}
          {draft ? <span className="iu-viewer-edit__draft" style={{ left: `${Math.min(draft.x, draft.x1) * 100}%`, top: `${Math.min(draft.y, draft.y1) * 100}%`, width: `${Math.abs(draft.x1 - draft.x) * 100}%`, height: `${Math.abs(draft.y1 - draft.y) * 100}%` }}/> : null}
        </div>}
      </div>
    </section> : <SourceDocumentReader key={`${source.href}-${revision}`} href={readerUrl.toString()} label={source.label} rotation={readerRotation} readerRef={activeReaderRef} compact={compactReader}/>}
    <SourceDocumentModal source={copySource} onClose={() => setCopySource(null)}/>
    {signatureOpen ? <ViewerHandwrittenSignaturePanel disabled={saving} openRequest={signatureOpenRequest} onClose={() => setSignatureOpen(false)} onInsert={(imageData, width, height) => {setImageOptions({imageData,imageName:'Firma grafica',width:.25,height:.25*(currentPage?.width||595)/(currentPage?.height||842)*height/width,keepRatio:true,imageBrightness:1,imageContrast:1,imageSharpness:1,imageGrayscale:false,imageAutocontrast:false});setSelectedInsertion(null);setTool('image');setOpen(true);setArmed(true);setSignatureOpen(false)}}/> : null}
  </div></ViewerColorSampling.Provider>
}
