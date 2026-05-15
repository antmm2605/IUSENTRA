import { ImagePlus, Link2, Plus, Trash2, ArrowDown, ArrowUp, Copy } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import type { BuilderAsset, BuilderBlock, BuilderBlockItem, BuilderPreset } from '../../sitoStudioBuilderData'
import { blockLabel, optionLabel } from '../../sitoStudioBuilderData'

const backgrounds = ['default', 'muted', 'dark', 'accent']
const spacings = ['compact', 'standard', 'wide']
const alignments = ['start', 'center', 'end']
const animations = ['fade-up', 'soft-reveal', 'none']

function TextField({
  label,
  value,
  onChange,
  area = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  area?: boolean
}) {
  return (
    <label className="iu-builder-field">
      <span>{label}</span>
      {area ? (
        <textarea value={value} rows={3} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  )
}

function SelectField({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return (
    <label className="iu-builder-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {values.map((entry) => <option value={entry} key={entry}>{optionLabel(entry)}</option>)}
      </select>
    </label>
  )
}

export function BuilderProperties({
  block,
  blockIndex,
  presets,
  assets,
  busy,
  onUpdate,
  onAddItem,
  onUpdateItem,
  onMoveItem,
  onDuplicateItem,
  onDeleteItem,
  onAttachAsset,
  onUploadAsset,
}: {
  block: BuilderBlock | null
  blockIndex: number
  presets: BuilderPreset[]
  assets: BuilderAsset[]
  busy: boolean
  onUpdate: (patch: Partial<BuilderBlock>) => void
  onAddItem: () => void
  onUpdateItem: (itemIndex: number, patch: Partial<BuilderBlockItem>) => void
  onMoveItem: (itemIndex: number, direction: -1 | 1) => void
  onDuplicateItem: (itemIndex: number) => void
  onDeleteItem: (itemIndex: number) => void
  onAttachAsset: (asset: BuilderAsset) => void
  onUploadAsset: (file: File, values: { altText: string; title: string; category: string }) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [assetForm, setAssetForm] = useState({ altText: '', title: '', category: '' })
  const submitAsset = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) return
    onUploadAsset(file, assetForm)
    setFile(null)
    setAssetForm({ altText: '', title: '', category: '' })
    event.currentTarget.reset()
  }
  const pickFile = (event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] || null)

  return (
    <aside className="iu-builder-props" aria-label="Proprieta e controlli">
      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Proprieta</span>
            <h2>Blocco selezionato</h2>
          </div>
          {block ? <strong className="iu-builder-count">#{blockIndex + 1}</strong> : null}
        </header>
        {block ? (
          <div className="iu-builder-formgrid">
            <label className="iu-builder-field">
              <span>Tipo blocco</span>
              <input value={blockLabel(block.type, presets)} readOnly />
            </label>
            <TextField label="Titolo" value={block.title} onChange={(title) => onUpdate({ title })} />
            <TextField label="Sottotitolo" value={block.subtitle} onChange={(subtitle) => onUpdate({ subtitle })} />
            <TextField label="Testo" value={block.text} area onChange={(text) => onUpdate({ text })} />
            <TextField label="Immagine" value={block.image_url} onChange={(image_url) => onUpdate({ image_url })} />
            <TextField label="Testo alternativo" value={block.image_alt} onChange={(image_alt) => onUpdate({ image_alt })} />
            <TextField label="Testo pulsante" value={block.button_text} onChange={(button_text) => onUpdate({ button_text })} />
            <TextField label="Collegamento pulsante" value={block.button_url} onChange={(button_url) => onUpdate({ button_url })} />
            <SelectField label="Sfondo" value={block.background} values={backgrounds} onChange={(background) => onUpdate({ background })} />
            <SelectField label="Spaziatura" value={block.spacing} values={spacings} onChange={(spacing) => onUpdate({ spacing })} />
            <SelectField label="Allineamento" value={block.alignment} values={alignments} onChange={(alignment) => onUpdate({ alignment })} />
            <SelectField label="Animazione" value={block.animation} values={animations} onChange={(animation) => onUpdate({ animation })} />
            <div className="iu-builder-checks">
              {(['desktop', 'tablet', 'mobile'] as const).map((name) => (
                <label key={name}>
                  <input
                    type="checkbox"
                    checked={block.visibility[name]}
                    onChange={(event) => onUpdate({ visibility: { ...block.visibility, [name]: event.target.checked } })}
                  />
                  {optionLabel(name)}
                </label>
              ))}
            </div>
          </div>
        ) : (
          <p className="iu-builder-muted">Seleziona un blocco nel canvas per modificare testi, immagini, pulsanti e visibilita.</p>
        )}
      </section>

      {block ? (
        <section className="iu-builder-panel">
          <header className="iu-builder-panel__head">
            <div>
              <span>Elementi</span>
              <h2>Contenuti interni</h2>
            </div>
            <button className="iu-builder-outline" type="button" onClick={onAddItem}><Plus size={15} /> Aggiungi</button>
          </header>
          <div className="iu-builder-items">
            {block.items.length ? block.items.map((item, index) => (
              <article className="iu-builder-item" key={index}>
                <TextField label="Titolo elemento" value={item.title} onChange={(title) => onUpdateItem(index, { title })} />
                <TextField label="Testo elemento" value={item.text} area onChange={(text) => onUpdateItem(index, { text })} />
                <TextField label="Immagine elemento" value={item.image_url} onChange={(image_url) => onUpdateItem(index, { image_url })} />
                <TextField label="Testo alternativo" value={item.image_alt} onChange={(image_alt) => onUpdateItem(index, { image_alt })} />
                <div className="iu-builder-mini-actions">
                  <button type="button" onClick={() => onMoveItem(index, -1)} disabled={index === 0} aria-label="Sposta elemento in alto" title="Sposta in alto"><ArrowUp size={14} aria-hidden="true" /></button>
                  <button type="button" onClick={() => onMoveItem(index, 1)} disabled={index === block.items.length - 1} aria-label="Sposta elemento in basso" title="Sposta in basso"><ArrowDown size={14} aria-hidden="true" /></button>
                  <button type="button" onClick={() => onDuplicateItem(index)} aria-label="Duplica elemento" title="Duplica"><Copy size={14} aria-hidden="true" /></button>
                  <button type="button" onClick={() => onDeleteItem(index)} aria-label="Elimina elemento" title="Elimina"><Trash2 size={14} aria-hidden="true" /></button>
                </div>
              </article>
            )) : <p className="iu-builder-muted">Questo blocco non contiene elementi interni.</p>}
          </div>
        </section>
      ) : null}

      <section className="iu-builder-panel">
        <header className="iu-builder-panel__head">
          <div>
            <span>Media</span>
            <h2>Libreria immagini</h2>
          </div>
          <ImagePlus size={17} />
        </header>
        <form className="iu-builder-upload" onSubmit={submitAsset}>
          <input type="file" accept="image/*" onChange={pickFile} />
          <input placeholder="Testo alternativo" value={assetForm.altText} onChange={(event) => setAssetForm((current) => ({ ...current, altText: event.target.value }))} />
          <input placeholder="Titolo immagine" value={assetForm.title} onChange={(event) => setAssetForm((current) => ({ ...current, title: event.target.value }))} />
          <button type="submit" disabled={busy || !file || !assetForm.altText.trim()}><ImagePlus size={15} /> Carica</button>
        </form>
        <div className="iu-builder-assets">
          {assets.slice(0, 10).map((asset) => (
            <button type="button" onClick={() => onAttachAsset(asset)} disabled={!block} key={`${asset.id}-${asset.url}`}>
              <Link2 size={14} />
              <span>{asset.title}</span>
              <small>{asset.altText || 'Testo alternativo non indicato'}</small>
            </button>
          ))}
        </div>
      </section>
    </aside>
  )
}
