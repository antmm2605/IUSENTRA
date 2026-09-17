import { type CSSProperties, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { FileSearch, Maximize2, Minimize2, RotateCw, Save } from 'lucide-react'
import { csrfToken } from '../formSubmit'
import { OperationalModal } from './OperationalModal'

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
        || (
          (
            normalizedPath.startsWith('/email/messaggio/')
            || normalizedPath.startsWith('/email-ordinaria/messaggio/')
          )
          && normalizedPath.includes('/allegato/')
        )
        || normalizedPath.startsWith('/api/v1/ui/email/source/')
        || normalizedPath.startsWith('/api/v1/ui/fonti-procedurali/')
        || (normalizedPath.includes('/documenti/') && normalizedPath.includes('/visualizza'))
      )
    return trustedInternalReader
      ? 'allow-downloads allow-same-origin allow-scripts'
      : 'allow-downloads allow-scripts'
  } catch {
    return 'allow-downloads allow-scripts'
  }
}

function sourceRotationSaveHref(href: string): string {
  try {
    const parsed = new URL(href, window.location.origin)
    if (parsed.origin !== window.location.origin) return ''
    const match = parsed.pathname.match(/^\/fascicoli\/([^/]+)\/documenti\/([^/]+)\/(?:visualizza|scarica)$/)
    if (!match) return ''
    return `/fascicoli/${encodeURIComponent(match[1])}/documenti/${encodeURIComponent(match[2])}/ruota`
  } catch {
    return ''
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
}: {
  href: string
  label: string
  rotation?: number
  notice?: string
}) {
  const [loadState, setLoadState] = useState<'loading' | 'loaded' | 'error'>('loading')
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const viewerHref = sourceViewerHref({ href }, true)
  const normalizedRotation = ((rotation % 360) + 360) % 360

  useEffect(() => {
    setLoadState('loading')
  }, [viewerHref])

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
          ref={iframeRef}
          src={viewerHref}
          title={`Visualizzazione fonte ${label}`}
          sandbox={sourceIframeSandbox(viewerHref)}
          allow="clipboard-write"
          referrerPolicy="no-referrer"
          onLoad={() => {
            setLoadState('loaded')
            pushRotationToReader()
          }}
          onError={() => setLoadState('error')}
        />
      </div>
    </div>
  )
}

export function SourceDocumentModal({ source, onClose }:{source:SourceDocument | null; onClose:()=>void}) {
  const [fullscreen, setFullscreen] = useState(false)
  const [rotation, setRotation] = useState(0)
  const [readerHref, setReaderHref] = useState('')
  const [readerRevision, setReaderRevision] = useState(0)
  const [savingRotation, setSavingRotation] = useState(false)
  const [saveNotice, setSaveNotice] = useState('')
  const originalHref = source ? sourceViewerHref(source, false) : ''
  const rotationSaveHref = useMemo(() => sourceRotationSaveHref(readerHref || originalHref), [readerHref, originalHref])

  useEffect(() => {
    setFullscreen(false)
    setRotation(0)
    setReaderHref(source?.href || '')
    setSaveNotice('')
    setSavingRotation(false)
    setReaderRevision(0)
  }, [source?.href])

  const saveRotation = async () => {
    if (!rotationSaveHref || !rotation || savingRotation) return
    setSavingRotation(true)
    setSaveNotice('Salvataggio della copia ruotata nel fascicolo…')
    try {
      const token = csrfToken()
      const response = await fetch(rotationSaveHref, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...(token ? { 'X-CSRFToken': token } : {}),
        },
        body: JSON.stringify({ rotation }),
      })
      const payload = await response.json().catch(() => ({})) as {
        ok?: boolean
        messaggio?: string
        message?: string
        errore?: string
        desktop_preview_url?: string
        preview_url?: string
      }
      if (!response.ok || payload.ok === false) {
        throw new Error(String(payload.messaggio || payload.errore || 'Rotazione non salvata.'))
      }
      const nextHref = payload.desktop_preview_url || payload.preview_url || ''
      if (nextHref) {
        setReaderHref(nextHref)
        setReaderRevision((value) => value + 1)
      }
      setRotation(0)
      setSaveNotice(String(payload.messaggio || payload.message || 'Copia ruotata salvata nel fascicolo.'))
    } catch (error) {
      setSaveNotice(error instanceof Error ? error.message : 'Rotazione non salvata. Verifica il documento e riprova.')
    } finally {
      setSavingRotation(false)
    }
  }

  return createPortal(
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
            onClick={() => setRotation((value) => (value + 90) % 360)}
            aria-label={`Ruota documento. Orientamento attuale ${rotation} gradi`}
            title="Ruota il documento di 90 gradi"
          >
            <RotateCw size={14} />
            Ruota
          </button>
          <button
            type="button"
            onClick={saveRotation}
            disabled={!rotation || !rotationSaveHref || savingRotation}
            title={rotationSaveHref ? 'Salva una copia ruotata nel fascicolo' : 'Salvataggio disponibile solo per documenti del fascicolo'}
          >
            <Save size={14} />
            {savingRotation ? 'Salvo…' : 'Salva rotazione'}
          </button>
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
      boxClassName={`iu-source-reader-box${fullscreen ? ' iu-ag-source-modal__box--fullscreen' : ''}`}
    >
      {source ? (
        <SourceDocumentReader
          key={`${readerHref || source.href}:${readerRevision}`}
          href={readerHref || source.href}
          label={source.label}
          rotation={rotation}
          notice={saveNotice}
        />
      ) : null}
    </OperationalModal>,
    document.body,
  )
}
