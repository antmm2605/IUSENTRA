import { Copy, Eye, GripVertical, Monitor, RefreshCw, Smartphone, Tablet, Trash2, ArrowDown, ArrowUp } from 'lucide-react'
import type { BuilderBlock, BuilderPage, BuilderPreset } from '../../sitoStudioBuilderData'
import { blockLabel, optionLabel } from '../../sitoStudioBuilderData'

export type PreviewSize = 'desktop' | 'tablet' | 'mobile'

export function BuilderCanvas({
  page,
  blocks,
  presets,
  selectedIndex,
  previewSize,
  previewUrl,
  previewVersion,
  onSelect,
  onMove,
  onDuplicate,
  onDelete,
  onPreviewSize,
  onRefreshPreview,
}: {
  page: BuilderPage
  blocks: BuilderBlock[]
  presets: BuilderPreset[]
  selectedIndex: number
  previewSize: PreviewSize
  previewUrl: string
  previewVersion: number
  onSelect: (index: number) => void
  onMove: (index: number, direction: -1 | 1) => void
  onDuplicate: (index: number) => void
  onDelete: (index: number) => void
  onPreviewSize: (size: PreviewSize) => void
  onRefreshPreview: () => void
}) {
  const frameUrl = previewUrl ? `${previewUrl}${previewUrl.includes('?') ? '&' : '?'}vista=${previewVersion}` : ''
  return (
    <main className="iu-builder-main" aria-label="Area composizione pagina">
      <section className="iu-builder-panel iu-builder-canvas">
        <header className="iu-builder-toolbar">
          <div>
            <span>Pagina selezionata</span>
            <h2>{page.title || 'Pagina non selezionata'}</h2>
            <p>{page.statusLabel || 'Bozza'} · {blocks.length} blocchi</p>
          </div>
          <div className="iu-builder-preview-buttons" aria-label="Formato anteprima">
            {[
              ['desktop', Monitor, 'Desktop'],
              ['tablet', Tablet, 'Tablet'],
              ['mobile', Smartphone, 'Mobile'],
            ].map(([value, Icon, label]) => (
              <button
                className={previewSize === value ? 'is-active' : ''}
                type="button"
                onClick={() => onPreviewSize(value as PreviewSize)}
                key={value as string}
              >
                <Icon size={15} />
                {label as string}
              </button>
            ))}
          </div>
        </header>

        {blocks.length ? (
          <div className="iu-builder-blocks">
            {blocks.map((block, index) => (
              <article className={`iu-builder-block${selectedIndex === index ? ' is-selected' : ''}`} key={`${block.type}-${index}`}>
                <button className="iu-builder-block__select" type="button" onClick={() => onSelect(index)}>
                  <GripVertical size={16} />
                  <span>
                    <strong>{block.title || blockLabel(block.type, presets)}</strong>
                    <small>{blockLabel(block.type, presets)} · {optionLabel(block.spacing)} · {optionLabel(block.alignment)}</small>
                  </span>
                </button>
                <div className="iu-builder-block__actions">
                  <button type="button" onClick={() => onMove(index, -1)} disabled={index === 0} title="Sposta su"><ArrowUp size={15} /></button>
                  <button type="button" onClick={() => onMove(index, 1)} disabled={index === blocks.length - 1} title="Sposta giu"><ArrowDown size={15} /></button>
                  <button type="button" onClick={() => onDuplicate(index)} title="Duplica blocco"><Copy size={15} /></button>
                  <button type="button" onClick={() => onDelete(index)} title="Elimina blocco"><Trash2 size={15} /></button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="iu-builder-empty">
            <Eye size={24} />
            <strong>Nessun blocco nella pagina</strong>
            <span>Aggiungi un blocco dalla palette: comparira qui e potrai modificarlo subito.</span>
          </div>
        )}
      </section>

      <section className="iu-builder-panel iu-builder-preview">
        <header className="iu-builder-toolbar">
          <div>
            <span>Anteprima live</span>
            <h2>Risultato pubblico</h2>
            <p>Verifica impaginazione e contenuti prima della pubblicazione.</p>
          </div>
          <button className="iu-builder-outline" type="button" onClick={onRefreshPreview}>
            <RefreshCw size={15} />
            Aggiorna
          </button>
        </header>
        <div className={`iu-builder-frame iu-builder-frame--${previewSize}`}>
          {frameUrl ? <iframe title="Anteprima sito studio" src={frameUrl} /> : <span>Anteprima non disponibile</span>}
        </div>
      </section>
    </main>
  )
}
