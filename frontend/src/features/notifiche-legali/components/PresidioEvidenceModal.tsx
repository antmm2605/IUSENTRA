import { Download, X } from 'lucide-react'
import { formatDateTimeIt } from '@/formatting'
import { Button, ButtonLink } from '@/ui/Button'
import { evidenceContentUrl } from '../api/presidiApi'
import { confidenceLabel, safeInternalHref } from '../presentation'
import type { PresidioEvidence as Evidence } from '../types'
import './PresidioEvidenceModal.css'

function evidenceMeta(item: Evidence): string {
  return [
    item.source_label,
    item.locator_label,
    formatDateTimeIt(item.created_at, 'Data non disponibile'),
    `Attendibilità ${confidenceLabel(item.confidence)}`,
  ].filter(Boolean).join(' · ')
}

export function PresidioEvidenceModal({
  item,
  presidioId,
  onClose,
}: {
  item: Evidence
  presidioId: string
  onClose: () => void
}) {
  const download = safeInternalHref(item.download_url) || evidenceContentUrl(presidioId, item.id, true)
  return (
    <div className="nlp-evidence-modal" role="dialog" aria-modal="true" aria-labelledby="nlp-evidence-modal-title">
      <section className="nlp-evidence-modal__box">
        <header>
          <div>
            <span>Evidenza verificabile</span>
            <h3 id="nlp-evidence-modal-title">{item.type_label}</h3>
            <small>{evidenceMeta(item)}</small>
          </div>
          <Button type="button" tone="neutral" onClick={onClose}><X size={15} />Chiudi</Button>
        </header>
        <div className="nlp-evidence-modal__content">
          <pre>{item.text_excerpt || 'Nessun testo disponibile per questa evidenza.'}</pre>
        </div>
        <footer>
          <ButtonLink tone="neutral" href={download}><Download size={15} />Scarica evidenza</ButtonLink>
        </footer>
      </section>
    </div>
  )
}
