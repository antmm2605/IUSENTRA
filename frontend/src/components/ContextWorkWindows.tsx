import { documentWorkPreview, type DocumentWorkPreview } from './documentWorkWindow'
import { lazy, Suspense, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { OperationalModal } from './OperationalModal'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import type { ClientCatalogArea } from './CartellaClienteCatalog'
import { activateManagedWindowForNode } from './ManagedWindowState'
import { workWindowUrl } from './workWindowRoutes'
import { publishOperationalRefresh } from '../operationalRefresh'
const DocumentPreview = lazy(() => import('./FascicoliPage').then(module => ({ default: module.PdfPreviewModal })))
const AgendaPreparation = lazy(() => import('./ControlloStudioAgendaDetail'))

const ClientCatalog = lazy(() => import('./CartellaClienteCatalog'))
const CLIENT_CATALOG_AREAS = new Set(['matters', 'deadlines', 'documents', 'messages', 'invoices'])

type WorkWindow = { id: number; href: string; title: string; focusToken: number }
let nextWindow = 0
export function ContextWorkWindows({ embedded = false }: { embedded?: boolean }) {
  const [windows, setWindows] = useState<WorkWindow[]>([])
  const [sourceWindows, setSourceWindows] = useState<SourceDocument[]>([])
  const [documentWindows, setDocumentWindows] = useState<DocumentWorkPreview[]>([])
  useEffect(() => {
    const open = (href: string, title: string) => {
      const url = workWindowUrl(href, window.location.origin)
      if (!url) return
      if (embedded && window.parent !== window) { window.parent.postMessage({ type: 'iusentra:open-work-window', href: url.toString(), title }, window.location.origin); return }
      url.searchParams.set('embed', 'source')
      const hrefInContext = url.toString()
      setWindows((current) => current.some(entry => entry.href === hrefInContext)
        ? current.map(entry => entry.href === hrefInContext ? { ...entry, focusToken: entry.focusToken + 1 } : entry)
        : [...current, { id: ++nextWindow, href: hrefInContext, title, focusToken: 0 }])
    }
    const click = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      const anchor = event.target instanceof Element ? event.target.closest('a') : null
      if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download') || anchor.getAttribute('href')?.startsWith('#')) return
      if (!embedded && !anchor.closest('[role=dialog], main') && !(document.querySelector('.iu-managed-window') && anchor.closest('.iu-sidebar'))) return
      if (!workWindowUrl(anchor.href, window.location.origin)) return
      event.preventDefault()
      const explicitTitle = anchor.getAttribute('aria-label')?.trim() || anchor.getAttribute('title')?.trim()
      const action = explicitTitle || anchor.innerText?.replace(/\s+/g, ' ').trim() || 'Attività dello studio'
      const record = anchor.closest('li,article,tr,.iu-comp-row')?.querySelector('h2,h3,h4,strong,.iu-sogg-title-line>a,.iu-cli-title-line>a')?.textContent?.trim()
      open(anchor.href, !explicitTitle && record && record !== action ? action + ' · ' + record : action)
    }
    const requested = (event: Event) => {
      const detail = (event as CustomEvent<{ href: string; title: string; focusToken: number }>).detail
      if (detail?.href) open(detail.href, detail.title || 'Attività dello studio')
    }
    const message = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || !['iusentra:open-work-window', 'iusentra:activate-work-window', 'iusentra:open-document-window'].includes(event.data?.type)) return
      const frame = [...document.querySelectorAll('iframe')].find(frame => frame.contentWindow === event.source)
      if (!frame) return
      if (event.data.type === 'iusentra:activate-work-window') { if (document.activeElement === frame) activateManagedWindowForNode(frame); return }

      if (event.data.type === 'iusentra:open-document-window') {
        const preview = documentWorkPreview(event.data.preview, window.location.origin)
        if (!preview) return
        const host = [...document.querySelectorAll<HTMLElement>('[data-document-work-url]')].find(node => node.dataset.documentWorkUrl === preview.url)
        const modal = host?.querySelector<HTMLElement>('.iu-fas-preview-modal')
        if (modal) activateManagedWindowForNode(modal, true)
        setDocumentWindows(current => current.some(item => item.url === preview.url) ? current : [...current, preview])
        return
      }
      if (typeof event.data.href === 'string') open(event.data.href, String(event.data.title || 'Attività dello studio'))
    }
    const activateParent = () => { if (embedded && window.parent !== window) window.parent.postMessage({ type: 'iusentra:activate-work-window' }, window.location.origin) }
    document.addEventListener('pointerdown', activateParent, true)
    document.addEventListener('focusin', activateParent)
    window.addEventListener('message', message)
    document.addEventListener('click', click)
    window.addEventListener('iusentra:open-work-window', requested)
    return () => { document.removeEventListener('pointerdown', activateParent, true); document.removeEventListener('focusin', activateParent); window.removeEventListener('message', message); document.removeEventListener('click', click); window.removeEventListener('iusentra:open-work-window', requested) }
  }, [embedded])
  return createPortal(<>{windows.map((entry) => {
    const url = new URL(entry.href)
    const clientCatalog = url.pathname.match(/^\/clienti\/([a-zA-Z0-9_-]+)\/cartella\/?$/)
    const catalogArea = url.searchParams.get('catalogo') || ''
    if (clientCatalog && CLIENT_CATALOG_AREAS.has(catalogArea)) return <Suspense key={entry.id} fallback={<p role="status">Apertura del catalogo cliente…</p>}>
      <ClientCatalog clientId={clientCatalog[1]} clientName={entry.title} area={catalogArea as ClientCatalogArea} focusToken={entry.focusToken}
        onClose={() => setWindows(current => current.filter(item => item.id !== entry.id))}
        onOpenDocuments={items => setSourceWindows(current => [...new Map([...current, ...items.map(item => ({ href: item.href, label: item.title, context: item.subtitle || entry.title }))].map(source => [source.href, source])).values()])}/>
    </Suspense>
    const appointment = /^\/wizard-pro\/?$/.test(url.pathname) ? url.searchParams.get('id_appuntamento') : null
    if (appointment) return <Suspense key={entry.id} fallback={<p role="status">Apertura preparazione dell’udienza…</p>}>
      <AgendaPreparation focusToken={entry.focusToken}
        voce={{ id: `agenda-${appointment}`, area: 'agenda', area_etichetta: 'Agenda', titolo: entry.title, dettaglio: '', data: '', ora: '', gravita: 'normale', etichetta: '', fascicolo: { id: url.searchParams.get('id_fascicolo') || '' }, data_riferimento: '', tipo_data_riferimento: '', importo: 0, azioni: [], fascia: '' }}
        azione={{ etichetta: 'Prepara l’udienza', href: entry.href, endpoint: '', conferma: '', principale: true }}
        onClose={() => setWindows(current => current.filter(item => item.id !== entry.id))}
        onUpdated={() => publishOperationalRefresh(['agenda', 'fascicoli'])}/>
    </Suspense>
    return <OperationalModal key={entry.id} open focusToken={entry.focusToken} title={entry.title} ariaLabel={`Finestra ${entry.title}`} eyebrow="Area di lavoro"
    onClose={() => setWindows((current) => current.filter((item) => item.id !== entry.id))} boxClassName="iu-context-work-window" bodyClassName="iu-context-work-window__body">
    <iframe src={entry.href} title={entry.title} className="iu-context-work-frame"/>
  </OperationalModal>
  })}{sourceWindows.map(source => <SourceDocumentModal key={source.href} source={source} onClose={() => setSourceWindows(current => current.filter(item => item.href !== source.href))}/>)}{documentWindows.map(preview => <div key={preview.url} data-document-work-url={preview.url} style={{ display: 'contents' }}>
    <Suspense fallback={<p role="status">Apertura documento…</p>}><DocumentPreview preview={preview} onClose={() => setDocumentWindows(current => current.filter(item => item.url !== preview.url))}/></Suspense>
  </div>)}</>, document.body)
}
