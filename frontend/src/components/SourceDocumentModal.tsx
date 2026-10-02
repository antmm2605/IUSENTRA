import { type CSSProperties, type RefObject, lazy, Suspense, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { FileSearch, Globe, Maximize2, Minimize2, Mail } from 'lucide-react'
import { OperationalModal } from './OperationalModal'

const ViewerDocumentEditor = lazy(() => import('./ViewerDocumentEditor').then((module) => ({ default: module.ViewerDocumentEditor })))

export type SourceDocument = {
  href: string
  label: string
  context: string
  kind?: string
}

export function sourceViewerHref(source: Pick<SourceDocument, 'href'>, preview = true): string {
  try {
    const parsed = new URL(source.href, window.location.origin)
    if (parsed.origin === window.location.origin) {
      const isEmailAttachment = (
        (
          parsed.pathname.startsWith('/email/messaggio/')
          || parsed.pathname.startsWith('/email-ordinaria/messaggio/')
        )
        && parsed.pathname.includes('/allegato/')
      )
      if (isEmailAttachment) {
        if (preview) parsed.searchParams.set('viewer', 'mobile')
      } else if (parsed.pathname.startsWith('/api/v1/ui/email/source/')) {
        if (preview) parsed.searchParams.set('viewer', 'mobile')
      } else if (parsed.pathname.includes('/documenti/') && parsed.pathname.includes('/visualizza')) {
        if (preview) parsed.searchParams.set('viewer', 'mobile')
        if (preview) parsed.searchParams.set('rotationScope', 'page')
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
    const trustedInternalReader = parsed.origin === window.location.origin
      && (
        normalizedPath === '/email'
        || normalizedPath === '/email-ordinaria'
        || /^\/email(?:-ordinaria)?\/messaggio\/[^/]+$/.test(normalizedPath)
        || (
          (
            normalizedPath.startsWith('/email/messaggio/')
            || normalizedPath.startsWith('/email-ordinaria/messaggio/')
          )
          && normalizedPath.includes('/allegato/')
        )
        || normalizedPath.startsWith('/api/v1/ui/email/source/')
        || normalizedPath.startsWith('/api/v1/ui/fonti-procedurali/')
        || normalizedPath === '/api/v1/ui/document-reader/web'
        || /^\/api\/v1\/ui\/controllo-studio\/conoscenza-notifiche\/fonti\/[a-z0-9_]+$/.test(normalizedPath)
        || (normalizedPath.includes('/documenti/') && normalizedPath.includes('/visualizza'))
      )
    return trustedInternalReader
      ? 'allow-downloads allow-same-origin allow-scripts allow-top-navigation-by-user-activation allow-popups allow-popups-to-escape-sandbox'
      : 'allow-downloads allow-scripts'
  } catch {
    return 'allow-downloads allow-scripts'
  }
}

/**
 * Lettore interno unico delle fonti (PDF, ZIP PEC, allegati, corpo PEC):
 * condiviso da Agenda, Scadenziario, PEC, Notifiche legali e Piano del giorno.
 */
export function SourceDocumentReader({
  href,
  label,
  rotation = 0,
  notice,
  readerRef,
}: {
  href: string
  label: string
  rotation?: number
  notice?: string
  readerRef?: RefObject<HTMLIFrameElement | null>
}) {
  const [destination, setDestination] = useState<{ href: string; label: string; mail: boolean } | null>(null)
  const [linkFullscreen, setLinkFullscreen] = useState(false)
  const detachLinks = useRef<(() => void) | null>(null)
  const [loadState, setLoadState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const viewerHref = sourceViewerHref({ href }, true)
  const normalizedRotation = ((rotation % 360) + 360) % 360

  useEffect(() => {
    setLoadState('loading')
    return () => { detachLinks.current?.(); detachLinks.current = null }
  }, [viewerHref])

  const attachDocumentLinks = () => {
    detachLinks.current?.()
    try {
      const content = iframeRef.current?.contentDocument
      if (!content) return
      const followLink = (event: MouseEvent) => {
        const element = event.target as Element | null
        const target = typeof element?.closest === 'function' ? element.closest('a[href]') : null
        const raw = target?.getAttribute('href') || ''
        if (!raw || raw.startsWith('#') || event.button !== 0) return
        let url: URL
        try { url = new URL(raw, content.URL) } catch { return }
        if (url.protocol === 'mailto:') {
          let address: string
          try { address = decodeURIComponent(url.pathname) } catch { return }
          if (!/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(address)) return
          event.preventDefault()
          const params = new URLSearchParams({ a: address, embed: 'source' })
          if (url.searchParams.get('subject')) params.set('oggetto', url.searchParams.get('subject') || '')
          setLinkFullscreen(false)
          setDestination({ href: `/email/scrivi?${params}`, label: address, mail: true })
        } else if (url.protocol === 'https:' || url.protocol === 'http:') {
          // I comandi propri del lettore (download, rotazione) restano sul percorso interno.
          if (url.origin === window.location.origin && !target?.classList.contains('reader-document-link') && target?.closest('.toolbar,header,nav')) return
          event.preventDefault()
          setLinkFullscreen(false)
          setDestination({ href: `/api/v1/ui/document-reader/web?${new URLSearchParams({ url: url.href })}`, label: url.href, mail: false })
        }
      }
      content.addEventListener('click', followLink, true)
      detachLinks.current = () => content.removeEventListener('click', followLink, true)
    } catch { /* I contenuti di altra origine non vengono ispezionati. */ }
  }

  const pushRotationToReader = () => {
    try {
      iframeRef.current?.contentWindow?.postMessage(
        { type: 'iusentra.document.setRotation', rotation: normalizedRotation },
        window.location.origin,
      )
    } catch {
      // Il lettore interno applica il messaggio quando è disponibile; gli altri
      // formati restano comunque scaricabili senza bloccare la preview.
    }
  }

  useEffect(() => {
    pushRotationToReader()
  }, [normalizedRotation, viewerHref])

  return (
    <div
      className="iu-source-document-reader"
      data-rotation={normalizedRotation}
      style={{ '--iu-source-reader-rotation': `${normalizedRotation}deg` } as CSSProperties}
    >
      {notice ? (
        <div className="iu-source-document-reader__notice" role="status">
          {notice}
        </div>
      ) : null}
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
      <div className="iu-source-document-reader__frame">
        <iframe
          ref={(element) => { iframeRef.current = element; if (readerRef) readerRef.current = element }}
          src={viewerHref}
          title={`Visualizzazione fonte ${label}`}
          sandbox={sourceIframeSandbox(viewerHref)}
          allow="clipboard-write"
          referrerPolicy="no-referrer"
          onLoad={() => {
            setLoadState('loaded')
            pushRotationToReader()
            attachDocumentLinks()
          }}
          onError={() => setLoadState('error')}
        />
      </div>
      {destination ? createPortal(
        <OperationalModal
          open
          draggable
          fullscreen={linkFullscreen}
          ariaLabel={destination.mail ? `Nuova PEC a ${destination.label}` : `Collegamento web ${destination.label}`}
          eyebrow={destination.mail ? <><Mail size={14} /> Comunicazioni dello studio</> : <><Globe size={14} /> Collegamento del documento</>}
          title={destination.mail ? 'Componi PEC' : 'Lettore web'}
          subtitle={destination.label}
          boxClassName={`iu-source-reader-box${linkFullscreen ? ' iu-ag-source-modal__box--fullscreen' : ''}`}
          actions={<button type="button" aria-pressed={linkFullscreen} onClick={() => setLinkFullscreen((value) => !value)}>{linkFullscreen ? <Minimize2 size={14}/> : <Maximize2 size={14}/>} {linkFullscreen ? 'Esci da tutto schermo' : 'Tutto schermo'}</button>}
          onClose={() => setDestination(null)}
        >
          {destination.mail ? <iframe title={`Componi PEC a ${destination.label}`} src={destination.href} style={{ width: '100%', height: '100%', border: 0 }} referrerPolicy="no-referrer"/> : <SourceDocumentReader href={destination.href} label={destination.label}/>}
        </OperationalModal>, document.body,
      ) : null}
    </div>
  )
}

export function SourceDocumentModal({ source, onClose }:{source:SourceDocument | null; onClose:()=>void}) {
  const [fullscreen, setFullscreen] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [discard, setDiscard] = useState(false)
  const originalHref = source ? sourceViewerHref(source, false) : ''

  useEffect(() => {
    setFullscreen(false)
    setDirty(false)
    setDiscard(false)
    setSaving(false)
  }, [source?.href])

  return createPortal(
    <OperationalModal
      draggable
      fullscreen={fullscreen}
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
      onClose={() => saving || dirty ? setDiscard(true) : onClose()}
      boxClassName={`iu-source-reader-box${fullscreen ? ' iu-ag-source-modal__box--fullscreen' : ''}`}
    >
      {discard ? <div className="iu-source-edit-discard" role="alert"><span>{saving ? 'Salvataggio in corso. Attendi l’esito prima di chiudere.' : 'Ci sono modifiche non salvate. Torna al documento per salvarle.'}</span><button type="button" onClick={() => setDiscard(false)}>Torna al documento</button><button type="button" disabled={saving} onClick={onClose}>Scarta e chiudi</button></div> : null}
      {source ? (
        <Suspense fallback={<div role="status">Caricamento del visualizzatore...</div>}><ViewerDocumentEditor
          key={source.href}
          source={source}
          onDirty={setDirty}
          onSaving={setSaving}
        /></Suspense>
      ) : null}
    </OperationalModal>,
    document.body,
  )
}
