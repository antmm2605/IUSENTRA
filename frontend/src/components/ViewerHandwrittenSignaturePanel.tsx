import { useEffect, useRef, useState } from 'react'
import type { PointerEvent } from 'react'
import { ViewerColorPalette } from './ViewerColorPalette'
import { drawSignatureInk } from './viewerSignatureInk'
import type { SignaturePoint as Point, SignatureStroke as Stroke } from './viewerSignatureInk'
export function ViewerHandwrittenSignaturePanel({disabled,onInsert,onClose,openRequest=0}:{disabled:boolean;onInsert:(data:string,width:number,height:number)=>void;onClose:()=>void;openRequest?:number}) {
  const canvas=useRef<HTMLCanvasElement>(null)
  const dialog=useRef<HTMLDialogElement>(null)
  const [expanded,setExpanded]=useState(true)
  useEffect(()=>{setExpanded(true)},[openRequest])
  useEffect(()=>{const element=dialog.current;if(!element)return;if(expanded&&!element.open)element.showModal();else if(!expanded&&element.open)element.close();return()=>{if(element.open)element.close()}},[expanded])
  const resizeWindow=(large:boolean)=>{const element=dialog.current;if(!element)return;element.style.width=`${Math.min(window.innerWidth-32,large?1080:600)}px`;element.style.height=`${Math.min(window.innerHeight-32,large?760:540)}px`}
  const windowDrag=useRef<{x:number;y:number;width:number;height:number}|null>(null)
  const setWindowSize=(width:number,height:number)=>{const element=dialog.current;if(!element)return;element.style.width=`${Math.max(Math.min(560,window.innerWidth-32),Math.min(window.innerWidth-32,width))}px`;element.style.height=`${Math.max(Math.min(440,window.innerHeight-32),Math.min(window.innerHeight-32,height))}px`}
  const current=useRef<Stroke|null>(null)
  const [strokes,setStrokes]=useState<Stroke[]>([])
  const [width,setWidth]=useState(1.2)
  const [color,setColor]=useState('#1748bf')
  const [pen,setPen]=useState('ballpoint')
  const draw=(items:Stroke[],active?:Stroke|null)=>{
    const element=canvas.current,context=element?.getContext('2d')
    if(!element||!context)return
    context.clearRect(0,0,element.width,element.height)
    drawSignatureInk(context,[...items,...(active?[active]:[])])
  }
  useEffect(()=>{draw(strokes)},[strokes])
  const point=(event:PointerEvent<HTMLCanvasElement>)=>{const rect=event.currentTarget.getBoundingClientRect();return{x:Math.max(0,Math.min(800,(event.clientX-rect.left)*800/rect.width)),y:Math.max(0,Math.min(320,(event.clientY-rect.top)*320/rect.height))}}
  const finish=()=>{const stroke=current.current;current.current=null;if(stroke)setStrokes(previous=>[...previous,stroke])}
  const insert=()=>{
    if(!canvas.current||!strokes.length)return
    const points=strokes.flatMap(stroke=>stroke.points),padding=Math.ceil(Math.max(...strokes.map(stroke=>stroke.width))*2+4)
    const left=Math.max(0,Math.floor(Math.min(...points.map(p=>p.x))-padding)),top=Math.max(0,Math.floor(Math.min(...points.map(p=>p.y))-padding))
    const right=Math.min(800,Math.ceil(Math.max(...points.map(p=>p.x))+padding)),bottom=Math.min(320,Math.ceil(Math.max(...points.map(p=>p.y))+padding))
    const output=document.createElement('canvas');output.width=right-left;output.height=bottom-top
    output.getContext('2d')!.drawImage(canvas.current,left,top,output.width,output.height,0,0,output.width,output.height)
    onInsert(output.toDataURL('image/png').split(',')[1],output.width,output.height)
  }
  return <div className="iu-viewer-edit__signature-entry">
    <button type="button" disabled={disabled} onClick={()=>setExpanded(true)}>Apri finestra firma</button>
    <p>{strokes.length?`${strokes.length} tratti conservati. Riapri la finestra per continuare.`:'Disegna la firma in una finestra ridimensionabile.'}</p>
    <dialog ref={dialog} className="iu-viewer-edit__signature-window" aria-labelledby="iu-signature-window-title" onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setExpanded(false)}}} onCancel={event=>{event.preventDefault();event.stopPropagation();setExpanded(false)}}>
      <header><h2 id="iu-signature-window-title">Disegna la firma grafica</h2><button type="button" onClick={()=>setExpanded(false)} aria-label="Chiudi finestra firma">Chiudi</button></header>
      <div className="iu-viewer-edit__signature-body"><div className="iu-viewer-edit__signature-sizing"><button type="button" onClick={()=>resizeWindow(true)}>Ingrandisci finestra</button><button type="button" onClick={()=>resizeWindow(false)}>Riduci finestra</button><span>Trascina l’angolo in basso a destra per scegliere le dimensioni.</span></div>
      <fieldset className="iu-viewer-edit__signature"><legend>Penna e area di firma</legend>
    <p>Disegna con il mouse o la penna. È un’immagine, non una firma digitale.</p>
    <div className="iu-viewer-edit__signature-pens" role="group" aria-label="Colore della penna">{[["Blu","#1748bf"],["Nero","#171717"],["Rosso","#c42b30"]].map(([name,value])=><button key={value} type="button" disabled={disabled} aria-label={`Colore della penna ${name}`} aria-pressed={color===value} onClick={()=>setColor(value)}><span style={{background:value}}/>{name}</button>)}</div>
    <details className="iu-viewer-edit__signature-extra-colors"><summary>Altri colori · {color.toUpperCase()}</summary><ViewerColorPalette label="Colore personalizzato della penna" value={color} disabled={disabled} onChange={setColor} sampling={false}/></details>
    <label>Tipo di penna<select value={pen} disabled={disabled} onChange={event=>{setPen(event.target.value);setWidth(event.target.value==='felt'?3:event.target.value==='fountain'?2:1.2)}}><option value="ballpoint">Penna a sfera</option><option value="fountain">Stilografica</option><option value="felt">Pennarello</option></select></label>
    <canvas ref={canvas} width={800} height={320} aria-label="Riquadro per disegnare la firma grafica" onPointerDown={event=>{if(disabled||event.button!==0)return;event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);current.current={points:[point(event)],width,color,pen};draw(strokes,current.current)}} onPointerMove={event=>{if(!current.current)return;current.current.points.push(point(event));draw(strokes,current.current)}} onPointerUp={finish} onPointerCancel={finish}/>
    <label>Spessore · {width.toLocaleString('it-IT')} pt<input type="range" min={.5} max={6} step={.1} value={width} disabled={disabled} onChange={event=>setWidth(Number(event.target.value))}/></label>
    <div className="iu-viewer-edit__text-style"><button type="button" disabled={disabled||!strokes.length} onClick={()=>setStrokes(strokes.slice(0,-1))}>Annulla tratto</button><button type="button" disabled={disabled||!strokes.length} onClick={()=>setStrokes([])}>Cancella</button></div>
    <button type="button" disabled={disabled||!strokes.length} onClick={insert}>Usa questa firma grafica</button>
    <button type="button" disabled={disabled} onClick={onClose}>Chiudi pannello firma</button>
  </fieldset></div>
      <button type="button" className="iu-viewer-edit__signature-resize" aria-label="Ridimensiona finestra firma" title="Trascina per ridimensionare. Con la tastiera usa le frecce." onPointerDown={event=>{if(event.button!==0)return;event.preventDefault();event.stopPropagation();const rect=dialog.current!.getBoundingClientRect();windowDrag.current={x:event.clientX,y:event.clientY,width:rect.width,height:rect.height};event.currentTarget.setPointerCapture(event.pointerId)}} onPointerMove={event=>{const start=windowDrag.current;if(!start)return;event.preventDefault();setWindowSize(start.width+2*(event.clientX-start.x),start.height+2*(event.clientY-start.y))}} onPointerUp={()=>{windowDrag.current=null}} onPointerCancel={()=>{windowDrag.current=null}} onKeyDown={event=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return;event.preventDefault();event.stopPropagation();const rect=dialog.current!.getBoundingClientRect();setWindowSize(rect.width+(event.key==='ArrowLeft'?-20:event.key==='ArrowRight'?20:0),rect.height+(event.key==='ArrowUp'?-20:event.key==='ArrowDown'?20:0))}}>↘</button>
    </dialog>
  </div>
}
