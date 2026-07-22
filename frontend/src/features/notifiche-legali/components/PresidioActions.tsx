import { useState, type FormEvent } from 'react'
import { ExternalLink, LoaderCircle } from 'lucide-react'
import { Button, ButtonLink } from '@/ui/Button'
import { Select } from '@/ui/Select'
import { TextArea } from '@/ui/TextArea'
import { safeInternalHref } from '../presentation'
import type { PresidioAvailableAction, PresidioDetail } from '../types'
import { PresidioDecisionRevision } from './PresidioDecisionRevision'

const FORM_MUTATIONS = new Set(['revise-decision', 'not-required', 'assign', 'link-document'])

function availableAction(
  detail: PresidioDetail,
  mutation: PresidioAvailableAction['mutation'],
): PresidioAvailableAction | undefined {
  return detail.available_actions.find((action) => action.kind === 'mutation' && action.mutation === mutation)
}

function DisabledReason({ action }: { action: PresidioAvailableAction }) {
  return !action.enabled && action.disabled_reason
    ? <small className="nlp-action-disabled">{action.disabled_reason}</small>
    : null
}

export function PresidioActions({
  detail,
  readOnly,
  busyAction,
  onAction,
}: {
  detail: PresidioDetail
  readOnly: boolean
  busyAction: string
  onAction: (action: PresidioAvailableAction, payload?: Record<string, unknown>) => Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [assignee, setAssignee] = useState(detail.assigned_user?.value || '')
  const [documentId, setDocumentId] = useState('')
  const reviseDecision = availableAction(detail, 'revise-decision')
  const notRequired = reviseDecision ? undefined : availableAction(detail, 'not-required')
  const assign = availableAction(detail, 'assign')
  const linkDocument = availableAction(detail, 'link-document')
  const directActions = detail.available_actions.filter(
    (action) => action.kind === 'link' || !FORM_MUTATIONS.has(String(action.mutation || '')),
  )

  const pending = (action: PresidioAvailableAction) => busyAction === action.id
  const disabled = (action: PresidioAvailableAction) => (
    !action.enabled || (action.kind === 'mutation' && readOnly) || Boolean(busyAction)
  )

  const submitNotRequired = async (event: FormEvent) => {
    event.preventDefault()
    if (!notRequired || reason.trim().length < 10) return
    await onAction(notRequired, { reason: reason.trim() })
    setReason('')
  }

  const submitAssignment = async (event: FormEvent) => {
    event.preventDefault()
    if (!assign || !assignee) return
    await onAction(assign, { assigned_user_id: assignee })
  }

  const submitDocument = async (event: FormEvent) => {
    event.preventDefault()
    if (!linkDocument || !documentId) return
    const selected = detail.linkable_documents.find((option) => option.value === documentId)
    await onAction(linkDocument, {
      fascicolo_document_id: documentId,
      document_name: selected?.document_name || selected?.label || '',
    })
    setDocumentId('')
  }

  return (
    <section className="nlp-detail-section" aria-labelledby="nlp-actions-title">
      <h3 id="nlp-actions-title">Azioni disponibili</h3>
      {directActions.length ? (
        <div className="nlp-direct-actions">
          {directActions.map((action) => {
            const href = action.kind === 'link' ? safeInternalHref(action.href) : ''
            if (action.kind === 'link' && !href) return null
            return (
              <div className="nlp-action-item" key={action.id}>
                {action.kind === 'link' ? (
                  <ButtonLink href={href} tone={action.tone || 'neutral'}>
                    {action.label}
                    <ExternalLink size={15} aria-hidden="true" />
                  </ButtonLink>
                ) : (
                  <Button
                    type="button"
                    tone={action.tone || 'neutral'}
                    disabled={disabled(action)}
                    onClick={() => void onAction(action, action.payload)}
                  >
                    {pending(action) ? <LoaderCircle className="nlp-spin" size={16} aria-hidden="true" /> : null}
                    {pending(action) ? 'Operazione in corso' : action.label}
                  </Button>
                )}
                <DisabledReason action={action} />
              </div>
            )
          })}
        </div>
      ) : <p className="nlp-muted">Nessuna azione immediata disponibile.</p>}

      {reviseDecision ? (
        <PresidioDecisionRevision
          action={reviseDecision}
          readOnly={readOnly}
          busyAction={busyAction}
          onAction={onAction}
        />
      ) : null}

      {notRequired ? (
        <details className="nlp-action-form">
          <summary>{notRequired.label}</summary>
          <form onSubmit={submitNotRequired}>
            <TextArea
              label="Motivazione obbligatoria"
              value={reason}
              minLength={10}
              required
              disabled={disabled(notRequired)}
              placeholder="Indica perché la notifica non è necessaria."
              onChange={(event) => setReason(event.target.value)}
            />
            <Button
              type="submit"
              tone={notRequired.tone || 'warning'}
              disabled={disabled(notRequired) || reason.trim().length < 10}
            >
              {pending(notRequired) ? 'Salvataggio in corso' : 'Conferma come non necessaria'}
            </Button>
            <DisabledReason action={notRequired} />
          </form>
        </details>
      ) : null}

      {assign ? (
        <details className="nlp-action-form">
          <summary>{assign.label}</summary>
          <form onSubmit={submitAssignment}>
            <Select
              label="Responsabile"
              value={assignee}
              required
              disabled={disabled(assign)}
              onChange={(event) => setAssignee(event.target.value)}
            >
              <option value="">Seleziona un professionista</option>
              {detail.assignment_options.map((option) => (
                <option value={option.value} key={option.value}>{option.label}</option>
              ))}
            </Select>
            <Button type="submit" disabled={disabled(assign) || !assignee}>
              {pending(assign) ? 'Assegnazione in corso' : 'Assegna'}
            </Button>
            <DisabledReason action={assign} />
          </form>
        </details>
      ) : null}

      {linkDocument ? (
        <details className="nlp-action-form">
          <summary>{linkDocument.label}</summary>
          <form onSubmit={submitDocument}>
            <p className="nlp-muted">
              Seleziona dal fascicolo l’atto da notificare, una ricevuta PEC, la relata o la prova da associare a questo presidio.
            </p>
            <Select
              label="Prova, ricevuta o documento della notifica"
              value={documentId}
              required
              disabled={disabled(linkDocument) || !detail.linkable_documents.length}
              onChange={(event) => setDocumentId(event.target.value)}
            >
              <option value="">Seleziona dal fascicolo</option>
              {detail.linkable_documents.map((option) => (
                <option value={option.value} key={option.value}>{option.label}</option>
              ))}
            </Select>
            <Button type="submit" disabled={disabled(linkDocument) || !documentId}>
              {pending(linkDocument) ? 'Collegamento in corso' : 'Collega al presidio'}
            </Button>
            <DisabledReason action={linkDocument} />
          </form>
        </details>
      ) : null}
    </section>
  )
}
