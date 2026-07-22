import type { BadgeTone } from '@/ui/Badge'
import type { PresidioPriority, PresidioStatus, PresidioTabKey } from './types'

export type PresidioTabDefinition = {
  id: PresidioTabKey
  label: string
  statuses: PresidioStatus[]
}

const STATUS_LABELS: Record<PresidioStatus, string> = {
  DETECTED: 'Rilevata',
  NEEDS_REVIEW: 'Da esaminare',
  ORIGINAL_TO_ACQUIRE: 'Originale da acquisire',
  ORIGINAL_ACQUIRED: 'Originale acquisito',
  NOTIFICATION_CONFIRMED: 'Notifica necessaria confermata',
  RECIPIENTS_TO_VERIFY: 'Destinatari da verificare',
  READY_FOR_RELATA: 'Relata da preparare',
  RELATA_DRAFTED: 'Relata predisposta',
  RELATA_SIGNED: 'Relata firmata',
  READY_TO_SEND: 'Pronta per l’invio',
  SENT_WAITING_RAC: 'In attesa RAC',
  RAC_RECEIVED: 'In attesa RdAC',
  PARTIAL_DELIVERY: 'Consegna parziale',
  DELIVERY_COMPLETE: 'Consegna completata',
  DELIVERY_FAILED: 'Mancata consegna',
  PROOF_TO_DEPOSIT: 'Prova da depositare',
  PROOF_DEPOSITED: 'Prova depositata',
  CLOSED: 'Chiusa',
  NOT_REQUIRED: 'Non necessaria',
  CANCELLED: 'Annullata',
  LEGACY_ASSUMED_HANDLED: 'Storico presunto',
  LEGACY_REVIEW_REQUIRED: 'Storico da esaminare',
}

export const PRESIDIO_TABS: PresidioTabDefinition[] = [
  {
    id: 'review',
    label: 'Da esaminare',
    statuses: ['DETECTED', 'NEEDS_REVIEW', 'NOTIFICATION_CONFIRMED', 'RECIPIENTS_TO_VERIFY'],
  },
  { id: 'original', label: 'Originale da acquisire', statuses: ['ORIGINAL_TO_ACQUIRE'] },
  {
    id: 'relata',
    label: 'Relata da preparare',
    statuses: ['ORIGINAL_ACQUIRED', 'READY_FOR_RELATA', 'RELATA_DRAFTED', 'RELATA_SIGNED', 'READY_TO_SEND'],
  },
  { id: 'waiting-rac', label: 'In attesa RAC', statuses: ['SENT_WAITING_RAC'] },
  { id: 'waiting-rdac', label: 'In attesa RdAC', statuses: ['RAC_RECEIVED'] },
  { id: 'partial', label: 'Consegna parziale', statuses: ['PARTIAL_DELIVERY'] },
  { id: 'failed', label: 'Mancata consegna', statuses: ['DELIVERY_FAILED'] },
  { id: 'proof', label: 'Prova da depositare', statuses: ['DELIVERY_COMPLETE', 'PROOF_TO_DEPOSIT'] },
  { id: 'closed', label: 'Chiuse', statuses: ['PROOF_DEPOSITED', 'CLOSED', 'NOT_REQUIRED', 'CANCELLED'] },
  { id: 'legacy', label: 'Storico presunto', statuses: ['LEGACY_ASSUMED_HANDLED', 'LEGACY_REVIEW_REQUIRED'] },
]

export function presidioStatusLabel(status: PresidioStatus, serverLabel?: string): string {
  return String(serverLabel || STATUS_LABELS[status] || 'Stato non disponibile')
}

export function presidioStatusTone(status: PresidioStatus): BadgeTone {
  if (status === 'DELIVERY_FAILED') return 'danger'
  if (['DELIVERY_COMPLETE', 'PROOF_DEPOSITED', 'CLOSED'].includes(status)) return 'success'
  if (['SENT_WAITING_RAC', 'RAC_RECEIVED', 'PARTIAL_DELIVERY', 'PROOF_TO_DEPOSIT'].includes(status)) return 'warning'
  if (status === 'CANCELLED' || status === 'NOT_REQUIRED' || status === 'LEGACY_ASSUMED_HANDLED') return 'neutral'
  return 'info'
}

export function priorityTone(priority: PresidioPriority): BadgeTone {
  if (priority === 'P0') return 'danger'
  if (priority === 'P1') return 'warning'
  if (priority === 'P2') return 'info'
  return 'neutral'
}

export function confidenceLabel(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return 'Da verificare'
  const normalized = value <= 1 ? value : value / 100
  return new Intl.NumberFormat('it-IT', {
    style: 'percent',
    maximumFractionDigits: 0,
  }).format(Math.max(0, Math.min(1, normalized)))
}

export function safeInternalHref(value?: string): string {
  const raw = String(value || '').trim()
  if (!raw || typeof window === 'undefined') return ''
  try {
    const target = new URL(raw, window.location.origin)
    if (target.origin !== window.location.origin) return ''
    return target.pathname + target.search + target.hash
  } catch {
    return ''
  }
}

export function tabCount(
  statuses: PresidioStatus[],
  counts?: Partial<Record<PresidioStatus, number>>,
): number | null {
  if (!counts) return null
  return statuses.reduce((total, status) => total + Number(counts[status] || 0), 0)
}
