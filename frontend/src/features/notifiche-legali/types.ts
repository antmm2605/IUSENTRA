export const PRESIDIO_STATUSES = [
  'DETECTED',
  'NEEDS_REVIEW',
  'ORIGINAL_TO_ACQUIRE',
  'ORIGINAL_ACQUIRED',
  'NOTIFICATION_CONFIRMED',
  'RECIPIENTS_TO_VERIFY',
  'READY_FOR_RELATA',
  'RELATA_DRAFTED',
  'RELATA_SIGNED',
  'READY_TO_SEND',
  'SENT_WAITING_RAC',
  'RAC_RECEIVED',
  'PARTIAL_DELIVERY',
  'DELIVERY_COMPLETE',
  'DELIVERY_FAILED',
  'PROOF_TO_DEPOSIT',
  'PROOF_DEPOSITED',
  'CLOSED',
  'NOT_REQUIRED',
  'CANCELLED',
  'LEGACY_ASSUMED_HANDLED',
  'LEGACY_REVIEW_REQUIRED',
] as const
export type PresidioStatus = typeof PRESIDIO_STATUSES[number]
export type PresidioPriority = 'P0' | 'P1' | 'P2' | 'P3'
export type PresidioTabKey =
  | 'review'
  | 'original'
  | 'relata'
  | 'waiting-rac'
  | 'waiting-rdac'
  | 'partial'
  | 'failed'
  | 'proof'
  | 'closed'
  | 'legacy'
export type PresidioMutation =
  | 'confirm'
  | 'not-required'
  | 'assign'
  | 'link-document'
  | 'reconcile'
  | 'retry'
export type PresidioResourceStatus =
  | 'idle'
  | 'loading'
  | 'refreshing'
  | 'ready'
  | 'forbidden'
  | 'flag-off'
  | 'repository-unavailable'
  | 'error'

export type PresidioOption = {
  value: string
  label: string
}

export type PresidioWarning = {
  code?: string
  message: string
}

export type PresidioPermissions = {
  can_read: boolean
  can_write: boolean
  can_link_document: boolean
  can_view_evidence: boolean
}

export type PresidioFilterControls = {
  priority: '' | PresidioPriority
  fascicolo: string
  assigned_user: string
  date_from: string
  date_to: string
  recipient: string
  channel: string
  legacy: '' | 'true' | 'false'
  needs_review: '' | 'true' | 'false'
}

export type PresidioListFilters = PresidioFilterControls & {
  statuses: PresidioStatus[]
  cursor: string
  limit: number
}

export type PresidioPractice = {
  id: string
  label: string
  rg?: string
  office?: string
  href?: string
}

export type PresidioDocumentSummary = {
  id?: string
  name: string
  role_label?: string
}

export type PresidioRecipientSummary = {
  id: string
  name: string
  role?: string
  status_label: string
  delivery_status?: string
  pec_address?: string
  failure_reason?: string
}

export type PresidioSummary = {
  id: string
  practice: PresidioPractice
  document: PresidioDocumentSummary | null
  source_effective_at: string
  explicit_due_at?: string | null
  notification_case: string
  notification_case_label: string
  channel: string
  channel_label: string
  recipients: PresidioRecipientSummary[]
  status: PresidioStatus
  status_label?: string
  priority: PresidioPriority
  confidence: number | null
  detection_reason: string
  rule_label: string
  legal_sources: string[]
  next_action: string
  human_review_required: boolean
  legacy_assumed_handled: boolean
  assigned_user?: PresidioOption | null
  updated_at: string
}

export type PresidioRecipient = PresidioRecipientSummary & {
  fiscal_id?: string
  pec_address?: string
  public_register?: string
  public_register_verified_at?: string | null
  send_status?: string
  rac_status?: string
  failure_reason?: string
  updated_at?: string
}

export type PresidioDocument = {
  id: string
  name: string
  role_label: string
  version_label?: string
  authoritative: boolean
  viewer_url?: string
  download_url?: string
}

export type PresidioAvailableAction = {
  id: string
  label: string
  kind: 'link' | 'mutation'
  href?: string
  mutation?: PresidioMutation
  payload?: Record<string, unknown>
  enabled: boolean
  disabled_reason?: string
  tone?: 'primary' | 'neutral' | 'danger' | 'success' | 'warning'
}

export type PresidioDetail = PresidioSummary & {
  recipients: PresidioRecipient[]
  documents: PresidioDocument[]
  available_actions: PresidioAvailableAction[]
  assignment_options: PresidioOption[]
  linkable_documents: PresidioOption[]
  source_pec_href?: string
  read_only_reason?: string
}

export type PresidioEvidence = {
  id: string
  type_label: string
  source_label: string
  locator_label?: string
  text_excerpt?: string
  confidence: number | null
  created_at: string
  can_view_content: boolean
  content_url?: string
  download_url?: string
}

export type PresidioTransition = {
  id: string
  previous_status?: PresidioStatus | null
  next_status: PresidioStatus
  actor_label: string
  reason: string
  occurred_at: string
}

export type PresidioPagination = {
  cursor: string
  next_cursor?: string | null
  has_more: boolean
  total?: number | null
  limit: number
}

export type PresidioListPayload = {
  ok: boolean
  items: PresidioSummary[]
  pagination: PresidioPagination
  facets?: {
    status?: Partial<Record<PresidioStatus, number>>
  }
  filter_options: {
    assignees: PresidioOption[]
    channels: PresidioOption[]
  }
  permissions: PresidioPermissions
  partial: boolean
  warnings: PresidioWarning[]
}

export type PresidioDetailPayload = {
  ok: boolean
  presidio: PresidioDetail
  permissions: PresidioPermissions
  warnings: PresidioWarning[]
}

export type PresidioEvidencePayload = {
  ok: boolean
  items: PresidioEvidence[]
}

export type PresidioTransitionsPayload = {
  ok: boolean
  items: PresidioTransition[]
}

export type PresidioMutationResult = {
  ok: boolean
  message: string
  status?: number
  code?: string
  presidio?: PresidioDetail
  warnings?: PresidioWarning[]
}
