import { useEffect, useState } from 'react'
import { FileSearch } from 'lucide-react'
import { OperationalModal } from './OperationalModal'

export type SourceDocument = {
  href: string
  label: string
  context: string
  kind?: string
}

function sourceViewerHref(source: SourceDocument, mobile: boolean): string {
  try {
    const parsed = new URL(source.href, window.location.origin)
    if (parsed.origin === window.location.origin) {
      if (source.kind === 'documento' && parsed.pathname.includes('/documenti/') && parsed.pathname.includes('/visualizza')) {
        if (mobile) parsed.searchParams.set('viewer', 'mobile')
      } else if (source.kind === 'pec' || parsed.pathname.startsWith('/email')) {
        parsed.searchParams.set('embed', 'source')
      }
      return `${parsed.pathname}${parsed.search}${parsed.hash}`
    }
    return parsed.toString()
  } catch {
    return source.href
  }
}

export function SourceDocumentModal({ source, onClose }:{source:SourceDocument | null; onClose:()=>void}) {
  const [mobile, setMobile] = useState(() => typeof window !== 'undefined' && window.matchMedia('(max-width: 900px)').matches)

  useEffect(() => {
    if (!source) return undefined
    const media = window.matchMedia('(max-width: 900px)')
    const update = () => setMobile(media.matches)
    update()
    if (typeof media.addEventListener === 'function') media.addEventListener('change', update)
    else media.addListener(update)
    return () => {
      if (typeof media.removeEventListener === 'function') media.removeEventListener('change', update)
      else media.removeListener(update)
    }
  }, [source])

  return (
    <OperationalModal
      open={Boolean(source)}
      ariaLabel={source ? `Fonte: ${source.label}` : 'Fonte dell’informazione'}
      eyebrow={<><FileSearch size={14}/> Fonte dell'informazione</>}
      title={source?.label || ''}
      subtitle={source?.context}
      actions={source ? <a href={source.href} target="_blank" rel="noreferrer">Apri originale</a> : null}
      onClose={onClose}
    >
      {source ? <iframe src={sourceViewerHref(source, mobile)} title={`Visualizzazione fonte ${source.label}`} /> : null}
    </OperationalModal>
  )
}
