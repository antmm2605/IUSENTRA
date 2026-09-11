import { ArrowDown, ArrowUp, FileCheck2, RotateCw, Trash2 } from 'lucide-react'
import { Button } from '../../ui/Button'
import type { CapturePage } from './captureImages'

type Props = {
  pages: CapturePage[]
  name: string
  busy: boolean
  onName: (name: string) => void
  onRotate: (id: string) => void
  onMove: (index: number, delta: number) => void
  onRemove: (id: string) => void
  onBuild: () => void
}

const ROTATION_CLASS: Record<number, string> = { 0: '', 90: 'is-rot-90', 180: 'is-rot-180', 270: 'is-rot-270' }

/** Pagine acquisite nell'ordine del PDF, con rotazione, riordino e rimozione. */
export function AcquisitionPages({ pages, name, busy, onName, onRotate, onMove, onRemove, onBuild }: Props) {
  if (!pages.length) {
    return <p className="iu-acq-empty">Nessuna pagina acquisita. Le pagine confermate compaiono qui, nell’ordine del PDF.</p>
  }
  return (
    <section className="iu-acq-pages" aria-label="Pagine acquisite">
      <ol>
        {pages.map((page, index) => (
          <li key={page.id}>
            <figure>
              <span className="iu-acq-thumb">
                <img className={ROTATION_CLASS[page.rotation] || ''} src={page.url} alt={`Pagina ${index + 1}`} />
              </span>
              <figcaption>Pagina {index + 1}</figcaption>
            </figure>
            <div className="iu-acq-pages__tools">
              <Button type="button" tone="neutral" aria-label={`Ruota pagina ${index + 1}`} title="Ruota" disabled={busy} onClick={() => onRotate(page.id)}><RotateCw size={15} aria-hidden="true" /></Button>
              <Button type="button" tone="neutral" aria-label={`Sposta pagina ${index + 1} prima`} title="Sposta prima" disabled={busy || index === 0} onClick={() => onMove(index, -1)}><ArrowUp size={15} aria-hidden="true" /></Button>
              <Button type="button" tone="neutral" aria-label={`Sposta pagina ${index + 1} dopo`} title="Sposta dopo" disabled={busy || index === pages.length - 1} onClick={() => onMove(index, 1)}><ArrowDown size={15} aria-hidden="true" /></Button>
              <Button type="button" tone="neutral" aria-label={`Rimuovi pagina ${index + 1}`} title="Rimuovi" disabled={busy} onClick={() => onRemove(page.id)}><Trash2 size={15} aria-hidden="true" /></Button>
            </div>
          </li>
        ))}
      </ol>
      <label className="iu-acq-field iu-acq-field--wide">
        <span>Nome del PDF</span>
        <input value={name} maxLength={120} disabled={busy} onChange={(event) => onName(event.target.value)} />
      </label>
      <Button type="button" disabled={busy || !name.trim()} onClick={onBuild}>
        <FileCheck2 size={16} aria-hidden="true" />Crea PDF ({pages.length} {pages.length === 1 ? 'pagina' : 'pagine'})
      </Button>
    </section>
  )
}
