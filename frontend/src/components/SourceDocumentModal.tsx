import { useEffect, useState } from 'react'
import { FileSearch, Maximize2, Minimize2 } from 'lucide-react'
import { OperationalModal } from './OperationalModal'

export type SourceDocument = {
  href: string
  label: string
  context: string
  kind?: string
}

function sourceViewerHref(source: SourceDocument, preview = true): string {
  try {
    const parsed = new URL(source.href, window.location.origin)
    if (parsed.origin === window.location.origin) {
      if (parsed.pathname.startsWith('/api/v1/ui/email/source/')) {
        if (preview) parsed.searchParams.set('viewer', 'mobile')
      } else if (parsed.pathname.includes('/documenti/') && parsed.pathname.includes('/visualizza')) {
        if (preview) parsed.searchParams.set('viewer', 'mobile')
      } else if (parsed.pathname.startsWith('/email')) {
        if (preview) parsed.searchParams.set('embed', 'source')
      }
      return `${parsed.pathname}${parsed.search}${parsed.hash}`
    }
    return parsed.toString()
  } catch {
    return source.href
  }
}

function sourceIframeSandbox(href: string): string {
  try {
    const parsed = new URL(href, window.location.origin)
    const normalizedPath = parsed.pathname.replace(/\/+$/, '') || '/'
    const trustedReactSource = parsed.origin === window.location.origin
      && (normalizedPath === '/email' || normalizedPath === '/email-ordinaria')
    return trustedReactSource
      ? 'allow-downloads allow-same-origin allow-scripts'
      : 'allow-downloads allow-scripts'
  } catch {
    return 'allow-downloads allow-scripts'
  }
}

export function SourceDocumentModal({ source, onClose }:{source:SourceDocument | null; onClose:()=>void}) {
  const [fullscreen, setFullscreen] = useState(false)
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle')
  const viewerHref = source ? sourceViewerHref(source, true) : ''
  const originalHref = source ? sourceViewerHref(source, false) : ''

  useEffect(() => {
    setFullscreen(false)
  }, [source?.href])

  useEffect(() => {
    setLoadState(source ? 'loading' : 'idle')
  }, [source?.href, viewerHref])

  return (
    <OperationalModal
      open={Boolean(source)}
      ariaLabel={source ? `Fonte: ${source.label}` : "Fonte dell'informazione"}
      eyebrow={<><FileSearch size={14}/> Fonte dell'informazione</>}
      title={source?.label || ''}
      subtitle={source?.context}
      actions={source ? (
        <>
          <button
            type="button"
            onClick={() => setFullscreen((value) => !value)}
            aria-pressed={fullscreen}
          >
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            {fullscreen ? 'Vista normale' : 'Tutto schermo'}
          </button>
          <a href={originalHref} target="_blank" rel="noreferrer">Apri originale</a>
        </>
      ) : null}
      onClose={onClose}
      boxClassName={fullscreen ? 'iu-ag-source-modal__box--fullscreen' : ''}
    >
      {source ? (
        <div className="iu-source-document-reader">
          {loadState === 'loading' ? (
            <div className="iu-source-document-reader__state" role="status">
              <strong>Caricamento documento...</strong>
              <span>Sto aprendo la fonte nel lettore interno IUSENTRA.</span>
            </div>
          ) : null}
          {loadState === 'error' ? (
            <div className="iu-source-document-reader__state iu-source-document-reader__state--error" role="alert">
              <strong>Documento non visualizzabile nel lettore.</strong>
              <span>Usa “Apri originale” o “Scarica” per recuperare il file, senza perdere il collegamento alla fonte.</span>
            </div>
          ) : null}
          <iframe
            src={viewerHref}
            title={`Visualizzazione fonte ${source.label}`}
            sandbox={sourceIframeSandbox(viewerHref)}
            referrerPolicy="no-referrer"
            onLoad={() => setLoadState('loaded')}
            onError={() => setLoadState('error')}
          />
        </div>
      ) : null}
    </OperationalModal>
  )
}
