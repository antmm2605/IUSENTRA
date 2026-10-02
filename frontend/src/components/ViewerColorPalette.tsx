import { useContext, useEffect, useState } from 'react'
import { ViewerColorSampling } from './useViewerColorSampler'
type Props = { label: string; value: string; disabled: boolean; presets?: readonly (readonly [string, string])[]; onChange: (value: string) => void; sampling?: boolean }
export function ViewerColorPalette({ label, value, disabled, presets = [], onChange, sampling = true }: Props) {
  const sampler = useContext(ViewerColorSampling)
  const [hex, setHex] = useState(value)
  const [invalid, setInvalid] = useState(false)
  useEffect(() => { setHex(value); setInvalid(false) }, [value])
  const commit = () => {
    const normalized = '#' + hex.trim().replace(/^#/, '').toLowerCase()
    if (!/^#[0-9a-f]{6}$/.test(normalized)) { setInvalid(true); return }
    setInvalid(false); setHex(normalized); if(normalized!==value.toLowerCase())onChange(normalized)
  }
  return <fieldset className="iu-viewer-edit__colors"><legend>{label}</legend>
    {presets.map(([name, color]) => <button key={color} type="button" aria-label={`${label} ${name}`} aria-pressed={value.toLowerCase() === color.toLowerCase()} disabled={disabled} onClick={() => onChange(color)}><span style={{ background: color }}/>{name}</button>)}
    <div className="iu-viewer-edit__custom-color">
      <label>Tavolozza RGB<input aria-label={`Tavolozza RGB: ${label}`} type="color" value={value} disabled={disabled} onChange={event => onChange(event.target.value)}/></label>
      <label>Codice colore<input aria-label={`Codice colore: ${label}`} type="text" value={hex} maxLength={7} spellCheck={false} autoComplete="off" aria-invalid={invalid} disabled={disabled} onChange={event => { setHex(event.target.value); setInvalid(false) }} onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); commit() } }}/></label>
      {sampler && sampling ? <button className="iu-viewer-edit__eyedropper" type="button" disabled={disabled} aria-pressed={sampler.active} onClick={()=>sampler.start(onChange)}>Preleva colore dalla pagina</button> : null}
      <small>16,7 milioni di colori · RGB</small>
      {invalid ? <small role="alert">Inserisci sei cifre esadecimali, per esempio #1748BF.</small> : null}
    </div>
  </fieldset>
}
