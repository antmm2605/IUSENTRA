import { useEffect, useState, type ReactNode } from 'react'
import { FileSearch } from 'lucide-react'
import type { FascicoloPaymentItem } from '../fascicoliData'
import { EconomicVerificationPanel } from './EconomicVerificationPanel'
import { OperationalModal } from './OperationalModal'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'

export function EconomicSourceWindow({ payment, context, children, className = 'iu-economic-source-action', label, onOpenChange }: {
  payment: FascicoloPaymentItem
  context: string
  children?: ReactNode
  className?: string
  label?: string
  onOpenChange?: (open: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const [reading, setReading] = useState(false)
  const [source, setSource] = useState<SourceDocument | null>(null)
  const active = open || Boolean(source)
  useEffect(() => { onOpenChange?.(active); return () => onOpenChange?.(false) }, [active, onOpenChange])
  const name = payment.displayLabel || payment.label
  function showSource() {
    const sources = payment.fontiVerifica || []
    if (sources.length === 1 && sources[0].previewHref && !payment.verificheMancanti?.length) {
      setSource({ href: sources[0].previewHref, label: sources[0].nome, context })
    } else setOpen(true)
  }
  return <>
    <button type="button" className={className} aria-label={label || `Apri fonti: ${name}`} aria-haspopup="dialog" aria-expanded={active} onClick={showSource}>
      {children || <><FileSearch size={15}/> Apri fonte</>}
    </button>
    {open ? <OperationalModal open ariaLabel={`Fonti: ${name} — ${context}`} eyebrow="Documenti del fascicolo" title={`Fonti: ${name}`} subtitle={context} onClose={() => { if (!reading) setOpen(false) }}>
      <EconomicVerificationPanel payment={payment} expanded onSourceOpenChange={setReading}/>
    </OperationalModal> : null}
    <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
  </>
}
