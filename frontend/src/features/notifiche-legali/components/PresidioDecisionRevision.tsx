import { PencilLine } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button } from '@/ui/Button'
import { Select } from '@/ui/Select'
import { TextArea } from '@/ui/TextArea'
import type { PresidioAvailableAction, PresidioStatus } from '../types'

export function PresidioDecisionRevision({
  action,
  readOnly,
  busyAction,
  onAction,
}: {
  action: PresidioAvailableAction
  readOnly: boolean
  busyAction: string
  onAction: (action: PresidioAvailableAction, payload?: Record<string, unknown>) => Promise<void>
}) {
  const [decision, setDecision] = useState<PresidioStatus>('NOTIFICATION_CONFIRMED')
  const [reason, setReason] = useState('')
  const [open, setOpen] = useState(false)
  const pending = busyAction === action.id
  const disabled = !action.enabled || readOnly || Boolean(busyAction)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (decision === 'NOTIFICATION_CONFIRMED' || reason.trim().length < 12) return
    await onAction(action, { target_status: decision, reason: reason.trim() })
    setReason('')
    setOpen(false)
  }

  return (
    <section className="nlp-action-form nlp-decision-revision">
      <Button
        type="button"
        tone="neutral"
        className="nlp-decision-revision__trigger"
        aria-expanded={open}
        aria-controls="nlp-decision-revision-form"
        disabled={!action.enabled || readOnly || Boolean(busyAction)}
        onClick={() => setOpen((current) => !current)}
      >
        <PencilLine size={16} aria-hidden="true" />
        {open ? 'Chiudi modifica' : action.label}
      </Button>
      {open ? (
        <form id="nlp-decision-revision-form" onSubmit={submit} aria-describedby="nlp-decision-revision-help">
          <p id="nlp-decision-revision-help" className="nlp-action-guidance">
            Correggi la decisione prima dell’invio. La motivazione, l’autore e la data restano nella cronologia verificabile.
          </p>
          <Select
            label="Nuova decisione"
            value={decision}
            required
            disabled={disabled}
            onChange={(event) => setDecision(event.target.value as PresidioStatus)}
          >
            <option value="NOTIFICATION_CONFIRMED">Notifica necessaria confermata</option>
            <option value="NEEDS_REVIEW">Da riesaminare</option>
            <option value="NOT_REQUIRED">Notifica non necessaria</option>
          </Select>
          <TextArea
            label="Motivazione della correzione"
            value={reason}
            minLength={12}
            required
            disabled={disabled}
            placeholder="Spiega perché la decisione precedente deve essere corretta."
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="nlp-decision-revision__actions">
            <Button
              type="submit"
              disabled={disabled || decision === 'NOTIFICATION_CONFIRMED' || reason.trim().length < 12}
            >
              {pending ? 'Correzione in corso' : 'Salva decisione corretta'}
            </Button>
            <Button type="button" tone="neutral" disabled={pending} onClick={() => setOpen(false)}>
              Annulla
            </Button>
          </div>
          {decision === 'NOTIFICATION_CONFIRMED' ? (
            <small className="nlp-action-disabled">Seleziona una decisione diversa da quella già registrata.</small>
          ) : null}
        </form>
      ) : null}
      {!action.enabled && action.disabled_reason ? (
        <small className="nlp-action-disabled">{action.disabled_reason}</small>
      ) : null}
    </section>
  )
}
