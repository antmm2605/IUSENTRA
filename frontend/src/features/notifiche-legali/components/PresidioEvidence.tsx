import { Download, Eye, FileCheck2 } from 'lucide-react'
import { formatDateTimeIt } from '@/formatting'
import { ButtonLink } from '@/ui/Button'
import { EmptyState } from '@/ui/EmptyState'
import { evidenceContentUrl } from '../api/presidiApi'
import { confidenceLabel, safeInternalHref } from '../presentation'
import type { PresidioEvidence as Evidence } from '../types'

export function PresidioEvidence({
  presidioId,
  items,
  canView,
}: {
  presidioId: string
  items: Evidence[]
  canView: boolean
}) {
  return (
    <section className="nlp-detail-section" aria-labelledby="nlp-evidence-title">
      <h3 id="nlp-evidence-title">Evidenze</h3>
      {items.length ? (
        <div className="nlp-evidence-list">
          {items.map((item) => {
            const viewer = safeInternalHref(item.content_url) || evidenceContentUrl(presidioId, item.id)
            const download = safeInternalHref(item.download_url) || evidenceContentUrl(presidioId, item.id, true)
            return (
              <article className="nlp-evidence-row" key={item.id}>
                <FileCheck2 size={17} aria-hidden="true" />
                <div>
                  <strong>{item.type_label}</strong>
                  <span>{item.source_label}</span>
                  {item.locator_label ? <small>{item.locator_label}</small> : null}
                  {item.text_excerpt ? <blockquote>{item.text_excerpt}</blockquote> : null}
                  <small>
                    {formatDateTimeIt(item.created_at, 'Data non disponibile')}
                    {' · Attendibilità '}
                    {confidenceLabel(item.confidence)}
                  </small>
                </div>
                {canView && item.can_view_content ? (
                  <div className="nlp-evidence-actions">
                    <ButtonLink tone="neutral" href={viewer}><Eye size={15} />Visualizza</ButtonLink>
                    <ButtonLink tone="neutral" href={download}><Download size={15} />Scarica</ButtonLink>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : (
        <EmptyState
          title="Nessuna evidenza disponibile"
          message="Le prove collegate compariranno qui senza esporre percorsi del sistema."
        />
      )}
    </section>
  )
}
