import { useState } from 'react'
import { ViewerHandwrittenSignaturePanel } from './ViewerHandwrittenSignaturePanel'
import type { Mark, PageInfo } from './viewerEditorTypes'
const MM_PER_PT = 25.4 / 72
export function ViewerImageTools({value, page, disabled, onChange, onError, onNew}: {value:Partial<Mark>;page?:PageInfo;disabled:boolean;onChange:(patch:Partial<Mark>)=>void;onError:(message:string)=>void;onNew:()=>void}) {
  const [signatureOpen,setSignatureOpen]=useState(false)
  const load = async (file?: File) => {
    if(!file)return
    if(!['image/png','image/jpeg'].includes(file.type)||file.size>5_000_000){onError('Scegli un’immagine PNG o JPEG di massimo 5 MB.');return}
    try {
      const bitmap=await createImageBitmap(file)
      const width=bitmap.width, height=bitmap.height;bitmap.close()
      if(width*height>20_000_000)throw new Error('L’immagine supera 20 milioni di pixel.')
      const imageData=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('Immagine non leggibile.'));reader.readAsDataURL(file)})
      onChange({imageData,imageName:file.name,width:.25,height:Math.min(.6,.25*(page?.width||595)/(page?.height||842)*height/width)})
    } catch(error){onError(error instanceof Error?error.message:'Immagine non leggibile.')}
  }
  const dimension = (key:'width'|'height', mm:number) => {
    const ratio=Math.min(1,Math.max(.005,mm/(MM_PER_PT*(key==='width'?(page?.width||595):(page?.height||842)))))
    const old=value[key]||.1
    onChange({[key]:ratio,...(value.keepRatio!==false?{[key==='width'?'height':'width']:(value[key==='width'?'height':'width']||.1)*ratio/old}:{})})
  }
  return <fieldset className="iu-viewer-edit__image-tools"><legend>Riquadro immagine</legend>
    <button type="button" disabled={disabled} aria-expanded={signatureOpen} onClick={()=>setSignatureOpen(!signatureOpen)}>Disegna firma grafica</button>
    {signatureOpen?<ViewerHandwrittenSignaturePanel disabled={disabled} onClose={()=>setSignatureOpen(false)} onInsert={(imageData,width,height)=>{onChange({imageData,imageName:'Firma grafica',width:.25,height:.25*(page?.width||595)/(page?.height||842)*height/width,keepRatio:true,imageBrightness:1,imageContrast:1,imageSharpness:1,imageGrayscale:false,imageAutocontrast:false});setSignatureOpen(false)}}/>:null}
    <label>{value.imageData?'Sostituisci immagine':'Carica immagine'}<input aria-label="Carica o sostituisci immagine" type="file" accept="image/png,image/jpeg" disabled={disabled} onChange={(event)=>{void load(event.target.files?.[0]);event.target.value=''}}/></label>
    {value.imageName?<span className="iu-viewer-edit__filename">{value.imageName}</span>:null}
    <label>Larghezza (mm)<input type="number" min={1} step={1} disabled={disabled} value={Math.round((value.width||.25)*(page?.width||595)*MM_PER_PT)} onChange={(event)=>dimension('width',Number(event.target.value))}/></label>
    <label>Altezza (mm)<input type="number" min={1} step={1} disabled={disabled} value={Math.round((value.height||.15)*(page?.height||842)*MM_PER_PT)} onChange={(event)=>dimension('height',Number(event.target.value))}/></label>
    <label><input type="checkbox" checked={value.keepRatio!==false} disabled={disabled} onChange={(event)=>onChange({keepRatio:event.target.checked})}/>Mantieni proporzioni</label>
    <fieldset className="iu-viewer-edit__image-adjust"><legend>Regolazioni dell’immagine selezionata</legend>
      <div className="iu-viewer-edit__text-style"><button type="button" disabled={disabled||!value.imageData} onClick={()=>onChange({imageBrightness:Math.max(.2,(value.imageBrightness??1)-.1)})}>Scurisci</button><button type="button" disabled={disabled||!value.imageData} onClick={()=>onChange({imageBrightness:Math.min(2,(value.imageBrightness??1)+.1)})}>Schiarisci</button></div>
      {([['imageBrightness','Luminosità',20,200],['imageContrast','Contrasto',20,200],['imageSharpness','Nitidezza',0,300]] as const).map(([key,label,min,max])=><label key={key}>{label} · {Math.round((value[key]??1)*100)}%<input aria-label={label} type="range" min={min} max={max} step={5} value={Math.round((value[key]??1)*100)} disabled={disabled||!value.imageData} onChange={event=>onChange({[key]:Number(event.target.value)/100})}/></label>)}
      <label><input type="checkbox" checked={Boolean(value.imageGrayscale)} disabled={disabled||!value.imageData} onChange={event=>onChange({imageGrayscale:event.target.checked})}/>Scala di grigi</label>
      <button type="button" disabled={disabled||!value.imageData} aria-pressed={Boolean(value.imageAutocontrast)} onClick={()=>onChange({imageAutocontrast:!value.imageAutocontrast})}>Contrasto automatico</button>
      <button type="button" disabled={disabled||!value.imageData} onClick={()=>onChange({imageBrightness:1,imageContrast:1,imageSharpness:1,imageGrayscale:false,imageAutocontrast:false})}>Ripristina immagine originale</button>
    </fieldset>
    <button type="button" disabled={disabled} onClick={onNew}>Inserisci un’altra immagine</button>
  </fieldset>
}
