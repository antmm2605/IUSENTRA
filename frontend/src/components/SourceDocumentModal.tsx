import { openSourceWindow } from './sourceWindowEvents'
import { type CSSProperties, type RefObject, lazy, Suspense, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, FileSearch, Globe, Mail } from 'lucide-react'
import { OperationalModal } from './OperationalModal'
import { activateManagedWindowForNode } from './ManagedWindowState'

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
      if (/^\/fascicoli\/[a-zA-Z0-9_-]+\/?$/.test(parsed.pathname)) {
        if (preview) parsed.searchParams.set('embed', 'source')
      } else if (isEmailAttachment) {
        if (preview) parsed.searchParams.set('viewer', 'mobile')
      } else if (parsed.pathname.startsWith('/api/v1/ui/email/source/')) {
        if (preview) {
          parsed.searchParams.set('viewer', 'mobile')
          parsed.searchParams.set('reader', 'v4')
        }
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
        /^\/fascicoli\/[a-zA-Z0-9_-]+$/.test(normalizedPath)
        || normalizedPath === '/email'
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
        || /^\/api\/v1\/ui\/document-tools\/results\/[^/]+\/visualizza$/.test(normalizedPath)
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
  compact = false,
  onReaderReady,
}: {
  href: string
  label: string
  rotation?: number
  notice?: string
  readerRef?: RefObject<HTMLIFrameElement | null>
  compact?: boolean
  onReaderReady?: (document: Document) => void
}) {
  const [destination, setDestination] = useState<{ href: string; label: string; mail: boolean } | null>(null)
  const detachLinks = useRef<(() => void) | null>(null)
  const [loadState, setLoadState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const viewerHref = sourceViewerHref({ href }, true)
  const normalizedRotation = ((rotation % 360) + 360) % 360
  const caseContext = (() => {
    try {
      const url = new URL(viewerHref, window.location.origin)
      return url.origin === window.location.origin && /^\/fascicoli\/[a-zA-Z0-9_-]+\/?$/.test(url.pathname)
    } catch { return false }
  })()
  const readerNotice = notice || (caseContext ? 'Contesto del fascicolo: questa vista non costituisce il documento sorgente della scadenza.' : '')

  useEffect(() => {
    setLoadState('loading')
    return () => { detachLinks.current?.(); detachLinks.current = null }
  }, [viewerHref])

  const attachDocumentLinks = () => {
    detachLinks.current?.()
    try {
      const content = iframeRef.current?.contentDocument
      if (!content || caseContext) return
      if (content.querySelector('[data-document-pages]')) onReaderReady?.(content)
      // Ordine visivo e da tastiera: riduci, percentuale, ingrandisci, adatta.
      const fit = content.querySelector('[data-zoom-reset]')
      const zoomIn = content.querySelector('[data-zoom-in]')
      if (content.querySelector('[data-document-pages]') && fit && zoomIn && fit.parentElement === zoomIn.parentElement) zoomIn.after(fit)
      // Solo il lettore PDF interno: il titolo è già nella barra della finestra.
      if (compact && content.querySelector('[data-document-pages]') && !content.getElementById('iu-embedded-reader-compact')) {
        const style = content.createElement('style')
        style.id = 'iu-embedded-reader-compact'
        style.textContent = '.reader>header>strong{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}.reader>header{grid-template-columns:minmax(0,1fr);padding:4px 6px}.reader-controls{justify-self:end}.reader-controls[open]{grid-column:1}.reader-controls[open]>.reader-toolbar{grid-column:1}.reader-controls[open]{display:flex;align-items:center;gap:6px;min-width:0}.reader-controls[open]>summary{flex:none;margin:0}.reader-controls[open]>.reader-toolbar{flex:1;width:auto;min-width:0}.reader-toolbar__main{flex-wrap:nowrap!important;overflow-x:auto;min-width:0}.reader-toolbar__main>*{flex-shrink:0}'
        content.head.appendChild(style)
      }
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
          setDestination({ href: `/email/scrivi?${params}`, label: address, mail: true })
        } else if (url.protocol === 'https:' || url.protocol === 'http:') {
          // I comandi propri del lettore (download, rotazione) restano sul percorso interno.
          if (url.origin === window.location.origin && !target?.classList.contains('reader-document-link') && target?.closest('.toolbar,header,nav')) return
          event.preventDefault()
          setDestination({ href: `/api/v1/ui/document-reader/web?${new URLSearchParams({ url: url.href })}`, label: url.href, mail: false })
        }
      }
      const activateReader = () => {
        if (iframeRef.current) activateManagedWindowForNode(iframeRef.current)
      }
      content.addEventListener('pointerdown', activateReader, true)
      content.addEventListener('focusin', activateReader)
      content.addEventListener('click', followLink, true)
      detachLinks.current = () => {
        content.removeEventListener('pointerdown', activateReader, true)
        content.removeEventListener('focusin', activateReader)
        content.removeEventListener('click', followLink, true)
      }
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
      {readerNotice ? (
        <div className="iu-source-document-reader__notice" role="status">
          {readerNotice}
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
          data-iusentra-operational-frame={caseContext ? "true" : undefined}
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
          ariaLabel={destination.mail ? `Nuova PEC a ${destination.label}` : `Collegamento web ${destination.label}`}
          eyebrow={destination.mail ? <><Mail size={14} /> Comunicazioni dello studio</> : <><Globe size={14} /> Collegamento del documento</>}
          title={destination.mail ? 'Componi PEC' : 'Lettore web'}
          subtitle={destination.label}
          boxClassName="iu-source-reader-box"
          onClose={() => setDestination(null)}
        >
          {destination.mail ? <iframe title={`Componi PEC a ${destination.label}`} src={destination.href} style={{ width: '100%', height: '100%', border: 0 }} referrerPolicy="no-referrer"/> : <SourceDocumentReader href={destination.href} label={destination.label}/>}
        </OperationalModal>, document.body,
      ) : null}
    </div>
  )
}

export function SourceDocumentModal({ source, onClose, requestToken }: { source: SourceDocument | null; onClose: () => void; requestToken?: object | null }) {
  const owner = useId()
  const current = useRef({ source, onClose, mounted: false }); current.current.source = source; current.current.onClose = onClose
  useEffect(() => { current.current.mounted = true; return () => { current.current.mounted = false } }, [])
  useEffect(() => {
    if (!source) return
    const href = source.href
    openSourceWindow(source, owner, () => { if (current.current.mounted && current.current.source?.href === href) current.current.onClose() })
  }, [owner,source?.href,source?.label,source?.context,requestToken])
  return null
}
export function SourceDocumentWorkWindow({ source, onClose, focusToken = 0 }: { source: SourceDocument | null; onClose: () => void; focusToken?: number }) {
  const [closeFocus,setCloseFocus] = useState(0)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [discard, setDiscard] = useState(false)
  const originalHref = source ? sourceViewerHref(source, false) : ''
  const caseSource = (() => {
    try {
      const url = new URL(originalHref, window.location.origin)
      return url.origin === window.location.origin && /^\/fascicoli\/[a-zA-Z0-9_-]+\/?$/.test(url.pathname)
    } catch { return false }
  })()
  const contextParts = (source?.context || '').split(' · ').map(part => part.trim()).filter(part => part && part !== '-')
  const compactContext = contextParts.filter((part, index) => contextParts.findIndex(other => other.toLocaleLowerCase('it-IT') === part.toLocaleLowerCase('it-IT')) === index).join(' · ')
  const sourceTitle = caseSource ? 'Fascicolo · ' + (source?.context.split(' · ').slice(-2).join(' · ') || 'Documenti') : source?.label || ''

  useEffect(() => {
    setDirty(false)
    setDiscard(false)
    setSaving(false)
  }, [source?.href])

  return createPortal(
    <OperationalModal
      draggable
      focusToken={`${focusToken}:${closeFocus}`}
      open={Boolean(source)}
      ariaLabel={source ? `${caseSource ? 'Contesto' : 'Fonte'}: ${sourceTitle}` : "Fonte dell'informazione"}
      eyebrow={<><FileSearch size={14}/> {caseSource ? 'Contesto del fascicolo' : "Fonte dell'informazione"}</>}
      title={sourceTitle}
      subtitle={compactContext}
      actions={source ? (
        <>
          <a className={caseSource ? undefined : "iu-source-original-icon"} href={originalHref} target={caseSource ? undefined : "_blank"} rel="noreferrer" aria-label={caseSource ? undefined : "Apri originale"} title={caseSource ? undefined : "Apri originale"}>{caseSource ? 'Apri fascicolo' : <ExternalLink size={16} aria-hidden="true"/>}</a>
        </>
      ) : null}
      onClose={() => { if (saving || dirty) { setDiscard(true); setCloseFocus(value => value + 1) } else onClose() }}
      boxClassName={`iu-source-reader-box${caseSource ? '' : ' iu-source-reader-box--compact'}`}
    >
      {discard ? <div className="iu-source-edit-discard" role="alert"><span>{saving ? 'Salvataggio in corso. Attendi l’esito prima di chiudere.' : 'Ci sono modifiche non salvate. Torna al documento per salvarle.'}</span><button type="button" onClick={() => setDiscard(false)}>Torna al documento</button><button type="button" disabled={saving} onClick={onClose}>Scarta e chiudi</button></div> : null}
      {source ? (
        <Suspense fallback={<div role="status">Caricamento del visualizzatore...</div>}><ViewerDocumentEditor
          key={source.href}
          source={source}
          compactReader={!caseSource}
          onDirty={setDirty}
          onSaving={setSaving}
        /></Suspense>
      ) : null}
    </OperationalModal>,
    document.body,
  )
}
