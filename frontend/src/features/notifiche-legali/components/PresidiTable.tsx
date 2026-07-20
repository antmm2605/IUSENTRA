import { ChevronRight, Clock3, FileText, Scale, UsersRound } from 'lucide-react'
import { formatDateTimeIt } from '@/formatting'
import { Button } from '@/ui/Button'
import { DataTable, type DataTableColumn } from '@/ui/DataTable'
import { EmptyState } from '@/ui/EmptyState'
import { StatusBadge } from '@/ui/StatusBadge'
import {
  confidenceLabel,
  presidioStatusLabel,
  presidioStatusTone,
  priorityTone,
  safeInternalHref,
} from '../presentation'
import type { PresidioSummary } from '../types'

function PracticeCell({ item }: { item: PresidioSummary }) {
  const href = safeInternalHref(item.practice.href)
  return (
    <div className="nlp-cell-stack">
      {href
        ? <a className="nlp-strong-link" href={href}>{item.practice.label}</a>
        : <strong>{item.practice.label}</strong>}
      {item.practice.rg ? <span>R.G. {item.practice.rg}</span> : null}
      {item.practice.office ? <small>{item.practice.office}</small> : null}
    </div>
  )
}

function DocumentCell({ item }: { item: PresidioSummary }) {
  return (
    <div className="nlp-cell-stack">
      <strong className="nlp-icon-line">
        <FileText size={15} aria-hidden="true" />
        {item.document?.name || 'Documento da collegare'}
      </strong>
      {item.document?.role_label ? <span>{item.document.role_label}</span> : null}
      <time dateTime={item.source_effective_at}>
        Fonte: {formatDateTimeIt(item.source_effective_at, 'Data non disponibile')}
      </time>
    </div>
  )
}

function RecipientsCell({ item }: { item: PresidioSummary }) {
  const visible = item.recipients.slice(0, 2)
  return (
    <div className="nlp-cell-stack">
      <strong className="nlp-icon-line">
        <UsersRound size={15} aria-hidden="true" />
        {item.notification_case_label}
      </strong>
      {visible.map((recipient) => (
        <span key={recipient.id}>{recipient.name}: {recipient.status_label}</span>
      ))}
      {item.recipients.length > visible.length
        ? <small>Altri {item.recipients.length - visible.length} destinatari</small>
        : null}
      <small>{item.channel_label}</small>
    </div>
  )
}

function StatusCell({ item }: { item: PresidioSummary }) {
  return (
    <div className="nlp-cell-stack nlp-cell-stack--badges">
      <span>
        <StatusBadge tone={presidioStatusTone(item.status)}>
          {presidioStatusLabel(item.status, item.status_label)}
        </StatusBadge>
        <StatusBadge tone={priorityTone(item.priority)}>{item.priority}</StatusBadge>
      </span>
      {item.explicit_due_at ? (
        <time className="nlp-deadline" dateTime={item.explicit_due_at}>
          <Clock3 size={14} aria-hidden="true" />
          Termine {formatDateTimeIt(item.explicit_due_at, 'da verificare')}
        </time>
      ) : <small>Nessun termine espresso</small>}
      {item.assigned_user ? <small>Assegnata a {item.assigned_user.label}</small> : null}
    </div>
  )
}

function ReasonCell({ item }: { item: PresidioSummary }) {
  return (
    <div className="nlp-cell-stack nlp-reason">
      <span>{item.detection_reason || 'Motivazione da verificare'}</span>
      <small className="nlp-icon-line">
        <Scale size={14} aria-hidden="true" />
        {item.rule_label || 'Regola non indicata'}
      </small>
      {item.legal_sources.length ? <small>{item.legal_sources.join(' · ')}</small> : null}
      <small>Attendibilità {confidenceLabel(item.confidence)}</small>
    </div>
  )
}

export function PresidiTable({
  items,
  onOpen,
}: {
  items: PresidioSummary[]
  onOpen: (id: string) => void
}) {
  const columns: DataTableColumn<PresidioSummary>[] = [
    { key: 'practice', header: 'Pratica', render: (item) => <PracticeCell item={item} /> },
    { key: 'document', header: 'Documento e fonte', render: (item) => <DocumentCell item={item} /> },
    { key: 'recipients', header: 'Caso e destinatari', render: (item) => <RecipientsCell item={item} /> },
    { key: 'status', header: 'Stato', render: (item) => <StatusCell item={item} /> },
    { key: 'reason', header: 'Motivo, regola e fonte', render: (item) => <ReasonCell item={item} /> },
    {
      key: 'action',
      header: 'Prossima azione',
      render: (item) => (
        <div className="nlp-next-action">
          <span>{item.next_action || 'Esamina il presidio'}</span>
          <Button type="button" tone="neutral" onClick={() => onOpen(item.id)}>
            Apri dettaglio
            <ChevronRight size={16} aria-hidden="true" />
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="nlp-table">
      <DataTable
        columns={columns}
        rows={items}
        getRowKey={(item) => item.id}
        empty={(
          <EmptyState
            title="Nessun presidio in questa coda"
            message="Modifica i filtri oppure passa a un’altra coda operativa."
          />
        )}
      />
    </div>
  )
}
