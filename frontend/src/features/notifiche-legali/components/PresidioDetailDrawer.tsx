import { useState } from 'react'
import { Download, Eye, FileDown, FileText, UserRound } from 'lucide-react'
import { ApiClientError } from '@/lib/apiClient'
import { formatDateTimeIt } from '@/formatting'
import { IusSkeletonTable } from '@/components/iusentra'
import { SourceDocumentModal, type SourceDocument } from '@/components/SourceDocumentModal'
import { Button, ButtonLink } from '@/ui/Button'
import { Drawer } from '@/ui/Drawer'
import { ErrorState } from '@/ui/ErrorState'
import { InlineAlert } from '@/ui/InlineAlert'
import { PermissionDeniedState } from '@/ui/PermissionDeniedState'
import { StatusBadge } from '@/ui/StatusBadge'
import { Toast } from '@/ui/Toast'
import { classifyPresidioError, mutatePresidio } from '../api/presidiApi'
import { usePresidioDetail } from '../hooks/usePresidioDetail'
import { presidioStatusLabel, presidioStatusTone, priorityTone, safeInternalHref } from '../presentation'
import type { PresidioAvailableAction } from '../types'
import { PresidioActions } from './PresidioActions'
import { PresidioEvidence } from './PresidioEvidence'

function downloadHrefForPresidioDocument(viewerHref: string, fallbackHref: string): string {
  if (viewerHref.includes('/documenti/') && viewerHref.includes('/visualizza')) {
    try {
      const parsed = new URL(viewerHref, window.location.origin)
      if (parsed.origin === window.location.origin) {
        parsed.searchParams.set('download', '1')
        return `${parsed.pathname}${parsed.search}${parsed.hash}`
      }
    } catch {
      return fallbackHref
    }
  }
  return fallbackHref
}

export default function PresidioDetailDrawer({
  id,
  onClose,
  onUpdated,
}: {
  id: string | null
  onClose: () => void
  onUpdated: () => void
}) {
  const resource = usePresidioDetail(id)
  const [busyAction, setBusyAction] = useState('')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'danger'; message: string } | null>(null)
  const [documentSource, setDocumentSource] = useState<SourceDocument | null>(null)
  const data = resource.data
  const detail = data?.detail.presidio
  const permissions = data?.detail.permissions
  const readOnly = permissions ? !permissions.can_write : true

  const runAction = async (action: PresidioAvailableAction, body: Record<string, unknown> = {}) => {
    if (!id || !action.mutation) return
    setBusyAction(action.id)
    setFeedback(null)
    try {
      const result = await mutatePresidio(id, action.mutation, { ...(action.payload || {}), ...body })
      setFeedback({ tone: 'success', message: result.message || 'Operazione completata.' })
      resource.refresh()
      onUpdated()
    } catch (error: unknown) {
      const failure = classifyPresidioError(error)
      const message = error instanceof ApiClientError && [400, 409, 422].includes(error.status)
        ? error.message
        : failure.message
      setFeedback({ tone: 'danger', message })
    } finally {
      setBusyAction('')
    }
  }

  return (
    <Drawer title={detail?.practice.label || 'Dettaglio presidio'} open={Boolean(id)} onClose={onClose}>
      <div className="nlp-detail">
        {resource.status === 'loading' || resource.status === 'idle'
          ? <IusSkeletonTable rows={6} columns={2} />
          : null}
        {resource.status === 'forbidden' ? <PermissionDeniedState /> : null}
        {resource.status === 'flag-off'
          ? <ErrorState title="Registro non attivo" message={resource.message} />
          : null}
        {resource.status === 'repository-unavailable'
          ? <ErrorState title="Registro temporaneamente non disponibile" message={resource.message} />
          : null}
        {resource.status === 'error' && !data ? <ErrorState message={resource.message} /> : null}
        {resource.status !== 'ready' && data ? <InlineAlert tone="warning">{resource.message}</InlineAlert> : null}
        {feedback ? <Toast tone={feedback.tone}>{feedback.message}</Toast> : null}

        {detail && permissions ? (
          <>
            <section className="nlp-detail-summary">
              <div>
                <StatusBadge tone={presidioStatusTone(detail.status)}>
                  {presidioStatusLabel(detail.status, detail.status_label)}
                </StatusBadge>
                <StatusBadge tone={priorityTone(detail.priority)}>{detail.priority}</StatusBadge>
              </div>
              <dl>
                <div><dt>Cliente/parte</dt><dd>{detail.practice.client || 'Da completare'}</dd></div>
                <div><dt>Pratica</dt><dd>{detail.practice.subject || detail.practice.label || 'Da completare'}</dd></div>
                <div><dt>R.G.</dt><dd>{detail.practice.rg || 'Non indicato'}</dd></div>
                <div><dt>Ufficio</dt><dd>{detail.practice.office || 'Non indicato'}</dd></div>
                <div><dt>Caso</dt><dd>{detail.notification_case_label}</dd></div>
                <div><dt>Canale</dt><dd>{detail.channel_label}</dd></div>
                <div><dt>Data sorgente</dt><dd>{formatDateTimeIt(detail.source_effective_at, 'Non disponibile')}</dd></div>
                <div><dt>Termine</dt><dd>{formatDateTimeIt(detail.explicit_due_at, 'Nessun termine espresso')}</dd></div>
              </dl>
              <p><strong>Motivo:</strong> {detail.detection_reason}</p>
              <p><strong>Prossima azione:</strong> {detail.next_action}</p>
            </section>

            {readOnly ? (
              <InlineAlert tone="warning">
                {detail.read_only_reason || 'Puoi consultare il presidio, ma non modificarlo.'}
              </InlineAlert>
            ) : null}
            {data.detail.warnings.map((warning) => (
              <InlineAlert tone="warning" key={warning.code || warning.message}>{warning.message}</InlineAlert>
            ))}

            <section className="nlp-detail-section" aria-labelledby="nlp-recipients-title">
              <h3 id="nlp-recipients-title">Destinatari</h3>
              <div className="nlp-recipient-list">
                {detail.recipients.map((recipient) => (
                  <article key={recipient.id}>
                    <UserRound size={17} aria-hidden="true" />
                    <div>
                      <strong>{recipient.name}</strong>
                      <span>{recipient.role || 'Destinatario'} · {recipient.status_label}</span>
                      {recipient.pec_address ? <small>{recipient.pec_address}</small> : null}
                      {recipient.failure_reason ? <small className="nlp-danger-text">{recipient.failure_reason}</small> : null}
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="nlp-detail-section" aria-labelledby="nlp-documents-title">
              <h3 id="nlp-documents-title">Documenti collegati</h3>
              <div className="nlp-document-list">
                {detail.documents.map((document) => {
                  const viewer = safeInternalHref(document.viewer_url)
                  const download = downloadHrefForPresidioDocument(viewer, safeInternalHref(document.download_url))
                  const acquisition = safeInternalHref(document.original_acquisition_url)
                  return (
                    <article key={document.id}>
                      <FileText size={17} aria-hidden="true" />
                      <div>
                        <strong>{document.name}</strong>
                        <span>{document.role_label}{document.version_label ? ' · ' + document.version_label : ''}</span>
                        {document.authoritative ? <small>Originale autorevole acquisito dal Portale Servizi</small> : null}
                        {document.original_acquisition_required ? (
                          <small>Originale da acquisire dal Portale Servizi prima della relata.</small>
                        ) : null}
                      </div>
                      <div>
                        {viewer ? (
                          <Button
                            type="button"
                            tone="neutral"
                            onClick={() => setDocumentSource({
                              href: viewer,
                              label: document.name,
                              context: `${document.role_label} · ${detail.practice.client || detail.practice.label}`,
                              kind: 'documento-presidio-notifica',
                            })}
                          >
                            <Eye size={15} />Visualizza
                          </Button>
                        ) : null}
                        {download ? <ButtonLink tone="neutral" href={download} download><Download size={15} />Scarica</ButtonLink> : null}
                        {acquisition ? (
                          <ButtonLink tone="primary" href={acquisition}>
                            <FileDown size={15} />Acquisisci originale
                          </ButtonLink>
                        ) : null}
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>

            <SourceDocumentModal source={documentSource} onClose={() => setDocumentSource(null)} />

            <PresidioActions detail={detail} readOnly={readOnly} busyAction={busyAction} onAction={runAction} />
            <PresidioEvidence
              presidioId={detail.id}
              items={data.evidence.items}
              canView={permissions.can_view_evidence}
            />

            <section className="nlp-detail-section" aria-labelledby="nlp-history-title">
              <h3 id="nlp-history-title">Cronologia verificabile</h3>
              <ol className="nlp-transition-list">
                {data.transitions.items.map((transition) => (
                  <li key={transition.id}>
                    <span aria-hidden="true" />
                    <div>
                      <strong>{presidioStatusLabel(transition.next_status)}</strong>
                      <p>{transition.reason || 'Transizione registrata'}</p>
                      <small>
                        {formatDateTimeIt(transition.occurred_at, 'Data non disponibile')}
                        {' · '}
                        {transition.actor_label}
                      </small>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          </>
        ) : null}
      </div>
    </Drawer>
  )
}
