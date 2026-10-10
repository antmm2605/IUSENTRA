import { useEffect, useState } from 'react'
import { ZoomOut, ZoomIn, Scan, RotateCw, Download, MoreHorizontal, Copy, Highlighter, Eraser, Printer, Save } from 'lucide-react'

/** Commands are forwarded to the existing reader, keeping its selection and page state. */
export function ReaderInlineControls({ document: reader }: { document: Document | null }) {
  const [, refresh] = useState(0)
  const [more, setMore] = useState(false)
  useEffect(() => {
    if (!reader?.querySelector('[data-document-pages]')) return
    const style = reader.createElement('style')
    style.textContent = '.reader>header .reader-controls{display:none!important}.reader>header:has(.reader-download-status:empty){padding:0!important;min-height:0!important}'
    reader.head.appendChild(style)
    const observer = new MutationObserver(() => refresh(value => value + 1))
    const header = reader.querySelector('.reader>header')
    if (header) observer.observe(header, { subtree: true, childList: true, attributes: true, characterData: true })
    return () => { observer.disconnect(); style.remove() }
  }, [reader])
  if (!reader?.querySelector('[data-document-pages]')) return null
  const command = (selector: string) => reader.querySelector<HTMLElement>(selector)
  const button = (selector: string, label: string, Icon: typeof ZoomOut) => {
    const target = command(selector)
    return target ? <button type="button" title={label} aria-label={label} disabled={target.tagName === 'BUTTON' && (target as HTMLButtonElement).disabled}
      onMouseDown={event => event.preventDefault()} onClick={() => { target.click(); setMore(false) }}><Icon size={16} aria-hidden="true"/></button> : null
  }
  return <div className="iu-reader-inline" role="group" aria-label="Comandi del lettore">
    {button('[data-zoom-out]', 'Riduci documento', ZoomOut)}
    <output aria-live="polite">{command('[data-zoom-value]')?.textContent || '100%'}</output>
    {button('[data-zoom-in]', 'Ingrandisci documento', ZoomIn)}
    {button('[data-zoom-reset]', 'Adatta documento alla larghezza', Scan)}
    {button('[data-rotate-right]', command('[data-rotate-right]')?.getAttribute('aria-label') || 'Ruota documento', RotateCw)}
    {command('[data-document-download]') ? <a href={command('[data-document-download]')!.getAttribute('href') || undefined} download title="Scarica documento" aria-label="Scarica documento"><Download size={16} aria-hidden="true"/></a> : null}
    <div className="iu-reader-inline__more" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setMore(false) } }}>
      <button type="button" title="Altri comandi del lettore" aria-label="Altri comandi del lettore" aria-expanded={more} onClick={() => setMore(value => !value)}><MoreHorizontal size={16}/></button>
      {more ? <div className="iu-reader-inline__menu" role="group" aria-label="Altri comandi">
        {button('[data-document-save-rotation]', 'Salva rotazione', Save)}
        {button('[data-document-copy]', 'Copia testo selezionato', Copy)}
        {button('[data-document-highlight]', 'Evidenzia selezione', Highlighter)}
        {button('[data-document-clear]', 'Rimuovi evidenziazioni', Eraser)}
        {button('[data-document-print]', 'Stampa documento', Printer)}
      </div> : null}
    </div>
  </div>
}
