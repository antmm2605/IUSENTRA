import type { Tone } from './data'

export type EmailFolder = 'INBOX' | 'INVIATI' | 'CESTINO'
export type EmailStatus = 'tutti' | 'NON_LETTA' | 'LETTA' | 'CESTINO'

export type PecAuditIssue = {
  code: string
  severity: string
  title: string
  detail: string
  blocking: boolean
}

export type PecAuditAttachment = {
  name: string
  classification: string
  classificationScore: number
  ocrCoverage: number
  signatureStatus: string
}

export type PecAuditReference = {
  label: string
  reason: string
}

export type PecAuditField = {
  value: unknown
  confidence: number
  motivation: string
  features: string[]
}

export type PecAuditSummary = {
  id: string
  qualityStatus: string
  qualityLabel: string
  qualityTone: Tone
  signatureStatus: string
  signatureLabel: string
  signatureTone: Tone
  linkedFascicoloId: string
  linkedFascicoloScore: number
  mimeHref: string
  validationIssues: PecAuditIssue[]
  validationSeverity: string
  eventType: string
  depositLifecycle: Record<string, unknown>
  semanticContext: Record<string, unknown>
  proceduralProfile: Record<string, unknown>
  lawyerChecklist: string[]
  normativeReferences: PecAuditReference[]
  agentQuestions: string[]
  recommendedActions: string[]
  deadlineProposal: Record<string, unknown>
  confidence: Record<string, PecAuditField>
  candidates: Array<Record<string, unknown>>
  attachments: PecAuditAttachment[]
  quickActions: {
    saveMatter: string
    requestMissingAttachment: string
    scheduleDeadline: string
    openMime: string
    runAudit: string
  }
  persisted: boolean
  storageLabel: string
  storageTone: Tone
  sourceEmailId: string
}

export type EmailPecRow = {
  id: string
  folder: EmailFolder
  sender: string
  senderName: string
  recipients: string
  subject: string
  preview: string
  timestamp: string
  timeLabel: string
  unread: boolean
  isPst: boolean
  pctStatus: string
  attachmentCount: number
  origin: string
  detailHref: string
  operationalHref: string
  replyHref: string
  trashHref: string
  restoreHref: string
  deleteHref: string
  markReadHref: string
  markUnreadHref: string
  tone: Tone
  auditOnly: boolean
  pecPresidiata: boolean
  pecPresidioStatus: string
  pecPresidioDeadlineStatus: string
  pecPresidioDueDate: string
  pecAudit?: PecAuditSummary
}

export type EmailPecSummary = {
  total: number
  filtered: number
  inbox: number
  unread: number
  sent: number
  trash: number
  pst: number
  attachments: number
  autoLinked: number
  warnings: number
}

export type EmailPecPageData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean }
  summary: EmailPecSummary
  items: EmailPecRow[]
  facets: {
    folders: Array<{ value: EmailFolder; label: string; count: number }>
    statuses: Array<{ value: EmailStatus; label: string; count: number }>
    pctStatuses: Array<{ value: string; label: string; count: number }>
  }
  actions: {
    compose: string
    settings: string
    sync: string
    bulkAction: string
    autoEsiti: string
    pecLocalAcquire: string
    operationalInbox: string
    localPecTest: string
    legalNotice: string
    lex: string
  }
}

export type EmailAttachment = {
  index: number
  name: string
  mime: string
  sizeLabel: string
  viewHref: string
  previewHref: string
  downloadHref: string
  available: boolean
  statusLabel: string
}

export type EmailDetailData = {
  source: string
  generatedAt: string
  item: EmailPecRow | null
  bodyText: string
  bodyCompleteness: string
  bodyCompletenessLabel: string
  bodyHtml: string
  attachments: EmailAttachment[]
  pecAudit?: PecAuditSummary
  actions: {
    inbox: string
    reply: string
    settings: string
  }
}

export type EmailPecParams = {
  folder?: EmailFolder
  q?: string
  stato?: EmailStatus
  pst?: boolean
  conAllegati?: boolean
  statoPct?: string
}

const emptySummary: EmailPecSummary = {
  total: 0,
  filtered: 0,
  inbox: 0,
  unread: 0,
  sent: 0,
  trash: 0,
  pst: 0,
  attachments: 0,
  autoLinked: 0,
  warnings: 0,
}

export const emptyEmailPecPage: EmailPecPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true },
  summary: emptySummary,
  items: [],
  facets: {
    folders: [
      { value: 'INBOX', label: 'In arrivo', count: 0 },
      { value: 'INVIATI', label: 'Inviati', count: 0 },
      { value: 'CESTINO', label: 'Cestino', count: 0 },
    ],
    statuses: [
      { value: 'tutti', label: 'Tutte', count: 0 },
      { value: 'NON_LETTA', label: 'Non lette', count: 0 },
      { value: 'LETTA', label: 'Lette', count: 0 },
      { value: 'CESTINO', label: 'Nel cestino', count: 0 },
    ],
    pctStatuses: [{ value: '', label: 'Tutti gli esiti', count: 0 }],
  },
  actions: {
    compose: '/email/scrivi',
    settings: '/email/impostazioni',
    sync: '/email/sincronizza',
    bulkAction: '/api/v1/ui/email/bulk-action',
    autoEsiti: '/email/auto-esiti',
    pecLocalAcquire: '/api/pec/email/acquisisci-locali?limit=5000&batch_size=50',
    operationalInbox: '/email/',
    localPecTest: '/email/impostazioni',
    legalNotice: '/notifiche-legali',
    lex: '#lex',
  },
}

export const emptyEmailOrdinariaPage: EmailPecPageData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true },
  summary: emptySummary,
  items: [],
  facets: {
    folders: emptyEmailPecPage.facets.folders,
    statuses: emptyEmailPecPage.facets.statuses,
    pctStatuses: [{ value: '', label: 'Nessun esito telematico', count: 0 }],
  },
  actions: {
    compose: '/email-ordinaria/scrivi',
    settings: '/impostazioni?tab=smtp',
    sync: '/email-ordinaria/sincronizza',
    bulkAction: '/api/v1/ui/email-ordinaria/bulk-action',
    autoEsiti: '',
    pecLocalAcquire: '',
    operationalInbox: '/email-ordinaria/',
    localPecTest: '/impostazioni?tab=smtp',
    legalNotice: '/notifiche-legali',
    lex: '#lex',
  },
}

export const emptyEmailDetail: EmailDetailData = {
  source: 'vuoto',
  generatedAt: '',
  item: null,
  bodyText: '',
  bodyCompleteness: '',
  bodyCompletenessLabel: '',
  bodyHtml: '',
  attachments: [],
  actions: {
    inbox: '/email/',
    reply: '/email/scrivi',
    settings: '/impostazioni?tab=pec',
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function text(value: unknown, fallback = ''): string {
  return String(value ?? fallback).trim()
}

function number(value: unknown): number {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function bool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1'
}

function normaliseFolder(value: unknown): EmailFolder {
  const raw = text(value).toUpperCase()
  if (raw === 'INVIATI' || raw.includes('SENT')) return 'INVIATI'
  if (raw === 'CESTINO' || raw.includes('TRASH') || raw.includes('DELETED')) return 'CESTINO'
  return 'INBOX'
}

function normaliseTone(value: unknown, item?: Record<string, unknown>): Tone {
  const raw = text(value).toLowerCase()
  if (['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw)) return raw as Tone
  if (bool(item?.isPst ?? item?.is_pst)) return 'primary'
  if (text(item?.pctStatus ?? item?.stato_pct)) return 'warning'
  return 'neutral'
}

function normaliseAuditTone(value: unknown, fallback: Tone = 'neutral'): Tone {
  const raw = text(value).toLowerCase()
  if (['danger', 'warning', 'primary', 'success', 'info', 'purple', 'orange', 'neutral'].includes(raw)) return raw as Tone
  return fallback
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => text(item)).filter(Boolean) : []
}

function issueFromPayload(value: unknown): PecAuditIssue {
  const item = isRecord(value) ? value : {}
  return {
    code: text(item.code),
    severity: text(item.severity),
    title: text(item.title),
    detail: text(item.detail),
    blocking: bool(item.blocking),
  }
}

function referenceFromPayload(value: unknown): PecAuditReference {
  const item = isRecord(value) ? value : {}
  return { label: text(item.label), reason: text(item.reason) }
}

function auditFieldFromPayload(value: unknown): PecAuditField {
  const item = isRecord(value) ? value : {}
  return {
    value: item.value,
    confidence: number(item.confidence),
    motivation: text(item.motivation),
    features: stringList(item.features),
  }
}

function auditFromPayload(value: unknown): PecAuditSummary | undefined {
  const item = isRecord(value) ? value : {}
  const id = text(item.id)
  if (!id) return undefined
  const rawConfidence = isRecord(item.confidence) ? item.confidence : {}
  const confidence = Object.fromEntries(Object.entries(rawConfidence).map(([key, field]) => [key, auditFieldFromPayload(field)]))
  const quickActions = isRecord(item.quickActions) ? item.quickActions : {}
  const semanticContext = item.semanticContext ?? item.semantic_context
  const proceduralProfile = item.proceduralProfile ?? item.procedural_profile
  const depositLifecycle = item.depositLifecycle ?? item.deposit_lifecycle
  return {
    id,
    qualityStatus: text(item.qualityStatus ?? item.quality_status),
    qualityLabel: text(item.qualityLabel ?? item.quality_label, 'Controllo non disponibile'),
    qualityTone: normaliseAuditTone(item.qualityTone ?? item.quality_tone),
    signatureStatus: text(item.signatureStatus ?? item.signature_status),
    signatureLabel: text(item.signatureLabel ?? item.signature_label, 'Firme non controllate'),
    signatureTone: normaliseAuditTone(item.signatureTone ?? item.signature_tone),
    linkedFascicoloId: text(item.linkedFascicoloId ?? item.linked_fascicolo_id),
    linkedFascicoloScore: number(item.linkedFascicoloScore ?? item.linked_fascicolo_score),
    mimeHref: text(item.mimeHref ?? item.mime_href),
    validationIssues: Array.isArray(item.validationIssues) ? item.validationIssues.map(issueFromPayload) : [],
    validationSeverity: text(item.validationSeverity ?? item.validation_severity),
    eventType: text(item.eventType ?? item.event_type),
    depositLifecycle: isRecord(depositLifecycle) ? depositLifecycle : {},
    semanticContext: isRecord(semanticContext) ? semanticContext : {},
    proceduralProfile: isRecord(proceduralProfile) ? proceduralProfile : {},
    lawyerChecklist: stringList(item.lawyerChecklist ?? item.lawyer_checklist),
    normativeReferences: Array.isArray(item.normativeReferences) ? item.normativeReferences.map(referenceFromPayload).filter((ref) => ref.label) : [],
    agentQuestions: stringList(item.agentQuestions ?? item.agent_questions),
    recommendedActions: stringList(item.recommendedActions ?? item.recommended_actions),
    deadlineProposal: isRecord(item.deadlineProposal ?? item.deadline_proposal) ? { ...((item.deadlineProposal ?? item.deadline_proposal) as Record<string, unknown>) } : {},
    confidence,
    candidates: Array.isArray(item.candidates) ? item.candidates.filter(isRecord) : [],
    attachments: Array.isArray(item.attachments)
      ? item.attachments.map((raw) => {
        const attachment = isRecord(raw) ? raw : {}
        return {
          name: text(attachment.name),
          classification: text(attachment.classification),
          classificationScore: number(attachment.classificationScore ?? attachment.classification_score),
          ocrCoverage: number(attachment.ocrCoverage ?? attachment.ocr_coverage),
          signatureStatus: text(attachment.signatureStatus ?? attachment.signature_status),
        }
      }).filter((attachment) => attachment.name)
      : [],
    quickActions: {
      saveMatter: text(quickActions.saveMatter ?? quickActions.save_matter),
      requestMissingAttachment: text(quickActions.requestMissingAttachment ?? quickActions.request_missing_attachment),
      scheduleDeadline: text(quickActions.scheduleDeadline ?? quickActions.schedule_deadline),
      openMime: text(quickActions.openMime ?? quickActions.open_mime),
      runAudit: text(quickActions.runAudit ?? quickActions.run_audit),
    },
    persisted: item.persisted !== false,
    storageLabel: text(item.storageLabel ?? item.storage_label, item.persisted === false ? 'MIME da acquisire automaticamente' : 'MIME originale conservato'),
    storageTone: normaliseAuditTone(item.storageTone ?? item.storage_tone, item.persisted === false ? 'warning' : 'success'),
    sourceEmailId: text(item.sourceEmailId ?? item.source_email_id),
  }
}

function rowFromPayload(value: unknown, index: number, fallbackBasePath = '/email'): EmailPecRow {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `email-${index}`)
  const folder = normaliseFolder(item.folder ?? item.cartella)
  const isPst = bool(item.isPst ?? item.is_pst ?? item.e_pst)
  const pctStatus = text(item.pctStatus ?? item.pct_status ?? item.stato_pct)
  const unread = bool(item.unread ?? item.non_letta) || text(item.status ?? item.stato) === 'NON_LETTA'
  const pecAudit = auditFromPayload(item.pecAudit ?? item.pec_audit)
  const tone = pecAudit?.qualityTone === 'danger' || pecAudit?.qualityTone === 'warning'
    ? pecAudit.qualityTone
    : normaliseTone(item.tone, item)
  return {
    id,
    folder,
    sender: text(item.sender ?? item.mittente),
    senderName: text(item.senderName ?? item.sender_name ?? item.mittente_nome),
    recipients: text(item.recipients ?? item.destinatari),
    subject: text(item.subject ?? item.oggetto, '(nessun oggetto)'),
    preview: text(item.preview ?? item.anteprima ?? item.corpo_testo),
    timestamp: text(item.timestamp ?? item.data),
    timeLabel: text(item.timeLabel ?? item.time_label),
    unread,
    isPst,
    pctStatus,
    attachmentCount: number(item.attachmentCount ?? item.attachment_count ?? item.allegati_count),
    origin: text(item.origin ?? item.origine),
    detailHref: text(item.detailHref ?? item.detail_href, `${fallbackBasePath}/messaggio/${encodeURIComponent(id)}`),
    operationalHref: text(item.operationalHref ?? item.operational_href, `${fallbackBasePath}/?cartella=${folder}&id=${encodeURIComponent(id)}`),
    replyHref: text(
      item.replyHref ?? item.reply_href,
      `${fallbackBasePath}/scrivi?oggetto=${encodeURIComponent(`Re: ${text(item.subject ?? item.oggetto)}`)}`,
    ),
    trashHref: text(item.trashHref ?? item.trash_href, `${fallbackBasePath}/${encodeURIComponent(id)}/cestino`),
    restoreHref: text(item.restoreHref ?? item.restore_href, `${fallbackBasePath}/${encodeURIComponent(id)}/ripristina`),
    deleteHref: text(item.deleteHref ?? item.delete_href, `${fallbackBasePath}/${encodeURIComponent(id)}/elimina`),
    markReadHref: text(item.markReadHref ?? item.mark_read_href, `${fallbackBasePath}/${encodeURIComponent(id)}/segna-letta`),
    markUnreadHref: text(item.markUnreadHref ?? item.mark_unread_href, `${fallbackBasePath}/${encodeURIComponent(id)}/segna-non-letta`),
    tone,
    auditOnly: bool(item.auditOnly ?? item.audit_only),
    pecPresidiata: bool(item.pecPresidiata ?? item.pec_presidiata),
    pecPresidioStatus: text(item.pecPresidioStatus ?? item.pec_presidio_status),
    pecPresidioDeadlineStatus: text(item.pecPresidioDeadlineStatus ?? item.pec_presidio_deadline_status),
    pecPresidioDueDate: text(item.pecPresidioDueDate ?? item.pec_presidio_due_date),
    pecAudit,
  }
}

function summaryFromPayload(payload: Record<string, unknown>, items: EmailPecRow[]): EmailPecSummary {
  const raw = isRecord(payload.summary) ? payload.summary : {}
  return {
    total: number(raw.total ?? raw.totale ?? items.length),
    filtered: number(raw.filtered ?? raw.filtrate ?? items.length),
    inbox: number(raw.inbox ?? raw.in_arrivo ?? items.filter((item) => item.folder === 'INBOX').length),
    unread: number(raw.unread ?? raw.non_lette ?? items.filter((item) => item.unread).length),
    sent: number(raw.sent ?? raw.inviati ?? items.filter((item) => item.folder === 'INVIATI').length),
    trash: number(raw.trash ?? raw.cestino ?? items.filter((item) => item.folder === 'CESTINO').length),
    pst: number(raw.pst ?? items.filter((item) => item.isPst).length),
    attachments: number(raw.attachments ?? raw.allegati ?? items.reduce((acc, item) => acc + item.attachmentCount, 0)),
    autoLinked: number(raw.autoLinked ?? raw.auto_linked ?? raw.auto_registrate),
    warnings: number(raw.warnings ?? raw.avvisi),
  }
}

function normaliseFacet<T extends string>(value: unknown, fallback: Array<{ value: T; label: string; count: number }>): Array<{ value: T; label: string; count: number }> {
  if (!Array.isArray(value)) return fallback
  return value.map((item) => {
    const record = isRecord(item) ? item : {}
    return {
      value: text(record.value) as T,
      label: text(record.label, text(record.value)),
      count: number(record.count),
    }
  }).filter((item) => item.value && item.label)
}

function normalisePayload(payload: unknown, fallback = emptyEmailPecPage): EmailPecPageData {
  if (!isRecord(payload)) return fallback
  const rawItems = Array.isArray(payload.items) ? payload.items : Array.isArray(payload.emails) ? payload.emails : []
  const actions = isRecord(payload.actions) ? payload.actions : {}
  const fallbackBasePath = text(actions.operationalInbox ?? actions.operational_inbox, fallback.actions.operationalInbox).replace(/\/+$/, '') || '/email'
  const items = rawItems.map((item, index) => rowFromPayload(item, index, fallbackBasePath))
  const facets = isRecord(payload.facets) ? payload.facets : {}
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: isRecord(payload.contracts)
      ? {
        mock_fallback: Boolean(payload.contracts.mock_fallback),
        read_only: payload.contracts.read_only !== false,
      }
      : { mock_fallback: false, read_only: true },
    summary: summaryFromPayload(payload, items),
    items,
    facets: {
      folders: normaliseFacet<EmailFolder>(facets.folders, fallback.facets.folders),
      statuses: normaliseFacet<EmailStatus>(facets.statuses, fallback.facets.statuses),
      pctStatuses: normaliseFacet<string>(facets.pctStatuses ?? facets.pct_statuses, fallback.facets.pctStatuses),
    },
    actions: {
      compose: text(actions.compose, fallback.actions.compose),
      settings: text(actions.settings, fallback.actions.settings),
      sync: text(actions.sync, fallback.actions.sync),
      bulkAction: text(actions.bulkAction ?? actions.bulk_action, fallback.actions.bulkAction),
      autoEsiti: text(actions.autoEsiti ?? actions.auto_esiti, fallback.actions.autoEsiti),
      pecLocalAcquire: text(actions.pecLocalAcquire ?? actions.pec_local_acquire, fallback.actions.pecLocalAcquire),
      operationalInbox: text(actions.operationalInbox ?? actions.operational_inbox, fallback.actions.operationalInbox),
      localPecTest: text(actions.localPecTest ?? actions.local_pec_test, fallback.actions.localPecTest),
      legalNotice: text(actions.legalNotice ?? actions.legal_notice, fallback.actions.legalNotice),
      lex: text(actions.lex, fallback.actions.lex),
    },
  }
}

function attachmentFromPayload(value: unknown): EmailAttachment {
  const item = isRecord(value) ? value : {}
  return {
    index: number(item.index),
    name: text(item.name, 'allegato'),
    mime: text(item.mime),
    sizeLabel: text(item.sizeLabel ?? item.size_label),
    viewHref: text(item.viewHref ?? item.view_href ?? item.previewHref ?? item.preview_href),
    previewHref: text(item.previewHref ?? item.preview_href ?? item.viewHref ?? item.view_href),
    downloadHref: text(item.downloadHref ?? item.download_href),
    available: item.available !== false,
    statusLabel: text(item.statusLabel ?? item.status_label),
  }
}

function emptyDetailFor(basePath: string): EmailDetailData {
  const ordinary = basePath.includes('ordinaria')
  return {
    ...emptyEmailDetail,
    actions: {
      inbox: `${basePath}/`,
      reply: `${basePath}/scrivi`,
      settings: ordinary ? '/impostazioni?tab=smtp' : '/impostazioni?tab=pec',
    },
  }
}

function normaliseDetailPayload(payload: unknown, fallbackBasePath: string): EmailDetailData {
  if (!isRecord(payload)) return emptyDetailFor(fallbackBasePath)
  const actions = isRecord(payload.actions) ? payload.actions : {}
  const rawItem = payload.item ?? payload.email
  return {
    source: text(payload.source, 'repository_reali'),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    item: rawItem ? rowFromPayload(rawItem, 0, fallbackBasePath) : null,
    bodyText: text(payload.bodyText ?? payload.body_text),
    bodyCompleteness: text(payload.bodyCompleteness ?? payload.body_completeness),
    bodyCompletenessLabel: text(payload.bodyCompletenessLabel ?? payload.body_completeness_label),
    bodyHtml: text(payload.bodyHtml ?? payload.body_html),
    attachments: (Array.isArray(payload.attachments) ? payload.attachments : []).map(attachmentFromPayload),
    pecAudit: auditFromPayload(payload.pecAudit ?? payload.pec_audit ?? (isRecord(rawItem) ? rawItem.pecAudit ?? rawItem.pec_audit : undefined)),
    actions: {
      inbox: text(actions.inbox, `${fallbackBasePath}/`),
      reply: text(actions.reply, `${fallbackBasePath}/scrivi`),
      settings: text(actions.settings, fallbackBasePath.includes('ordinaria') ? '/impostazioni?tab=smtp' : '/impostazioni?tab=pec'),
    },
  }
}

async function fetchEmailDetail(endpoint: string, fallbackBasePath: string): Promise<EmailDetailData> {
  try {
    const response = await fetch(`${endpoint}?_ts=${Date.now()}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyDetailFor(fallbackBasePath)
    return normaliseDetailPayload(await response.json(), fallbackBasePath)
  } catch {
    return emptyDetailFor(fallbackBasePath)
  }
}

function auditDetailFromPayload(payload: unknown): EmailDetailData {
  const root = isRecord(payload) && isRecord(payload.data) ? payload.data : {}
  const message = isRecord(root.message) ? root.message : {}
  const parsed = isRecord(root.parsed) ? root.parsed : {}
  const metadata = isRecord(message.metadata) ? message.metadata : {}
  const headers = isRecord(metadata.headers) ? metadata.headers : {}
  const report = isRecord(root.validation_report) ? root.validation_report : {}
  const link = isRecord(root.fascicolo_link) ? root.fascicolo_link : {}
  const pecId = text(message.id)
  const encoded = encodeURIComponent(pecId)
  const attachments = Array.isArray(root.attachments) ? root.attachments : []
  const parsedBody = isRecord(parsed.body) ? parsed.body : {}
  const fullBodyText = [parsed.body_text, parsedBody.text, parsedBody.html_text]
    .map((value) => text(value))
    .find(Boolean) || ''
  const qualityStatus = text(message.quality_status)
  const signatureStatus = text(message.signature_status)
  const audit = auditFromPayload({
    id: pecId,
    qualityStatus,
    qualityLabel: qualityStatus === 'verde' ? 'Qualità verde' : qualityStatus === 'giallo' ? 'Qualità da presidiare' : qualityStatus === 'rosso' ? 'Qualità critica' : 'Presidio richiesto',
    qualityTone: qualityStatus === 'rosso' ? 'danger' : qualityStatus === 'giallo' ? 'warning' : qualityStatus === 'verde' ? 'success' : 'neutral',
    signatureStatus,
    signatureLabel: signatureStatus === 'valida' ? 'Firme valide' : ['non_valida', 'errore', 'scaduta'].includes(signatureStatus) ? 'Firme da verificare' : 'Firme non verificate',
    signatureTone: ['non_valida', 'errore', 'scaduta'].includes(signatureStatus) ? 'danger' : signatureStatus === 'valida' ? 'success' : 'neutral',
    linkedFascicoloId: message.linked_fascicolo_id,
    linkedFascicoloScore: message.linked_fascicolo_score,
    mimeHref: `/api/pec/messages/${encoded}/mime`,
    validationIssues: report.issues,
    validationSeverity: report.severity,
    eventType: report.event_type,
    depositLifecycle: report.deposit_lifecycle,
    semanticContext: report.semantic_context,
    proceduralProfile: report.procedural_profile,
    lawyerChecklist: report.lawyer_checklist,
    normativeReferences: report.normative_references,
    agentQuestions: report.agent_questions,
    recommendedActions: report.recommended_actions,
    deadlineProposal: report.deadline_proposal,
    confidence: isRecord(parsed.fields) ? parsed.fields : {},
    candidates: link.candidates,
    attachments: attachments.map((raw) => {
      const item = isRecord(raw) ? raw : {}
      return {
        name: item.filename,
        classification: item.classification,
        classificationScore: item.classification_score,
        ocrCoverage: item.ocr_coverage,
        signatureStatus: item.signature_status,
      }
    }),
    quickActions: {
      runAudit: '/api/pec/workers/run',
      saveMatter: `/api/pec/messages/${encoded}/salva-fascicolo`,
      requestMissingAttachment: `/api/pec/messages/${encoded}/richiedi-allegato-mancante`,
      scheduleDeadline:
        isRecord(report.deadline_proposal) &&
        (report.deadline_proposal.auto_create ||
          (isRecord(report.deadline_proposal.legal_deadline_proposal) &&
            (report.deadline_proposal.legal_deadline_proposal as Record<string, unknown>).ok === true))
          ? `/api/pec/messages/${encoded}/schedula-scadenza`
          : '',
      openMime: `/api/pec/messages/${encoded}/mime`,
    },
  })
  const row = rowFromPayload({
    id: `pec-audit:${pecId}`,
    folder: 'INBOX',
    status: 'LETTA',
    sender: headers.from,
    senderName: headers.from,
    recipients: headers.to,
    subject: headers.subject,
    preview: fullBodyText,
    timestamp: message.received_at,
    timeLabel: '',
    unread: false,
    isPst: true,
    pctStatus: report.event_type,
    attachmentCount: attachments.length,
    origin: 'controllo PEC',
    detailHref: `/api/pec/messages/${encoded}/mime`,
    operationalHref: `/email/?pec_audit=${encoded}`,
    auditOnly: true,
    pecAudit: audit,
  }, 0, '/email')
  return {
    source: 'pec_audit',
    generatedAt: text(root.generated_at),
    item: row,
    bodyText: fullBodyText,
    bodyCompleteness: 'presidio_pec',
    bodyCompletenessLabel: 'Testo ricostruito dal presidio PEC; apri il MIME per consultare la copia originale quando disponibile.',
    bodyHtml: '',
    attachments: attachments.map((raw, index) => {
      const item = isRecord(raw) ? raw : {}
      const name = text(item.filename, `allegato-${index + 1}`)
      const sourceHref = pecId && name
        ? `/api/v1/ui/email/source/${encoded}?name=${encodeURIComponent(name)}`
        : ''
      return {
        index,
        name,
        mime: text(item.mime_type),
        sizeLabel: '',
        viewHref: sourceHref,
        previewHref: sourceHref,
        downloadHref: sourceHref ? `${sourceHref}&download=1` : '',
        available: Boolean(sourceHref),
        statusLabel: sourceHref
          ? 'Allegato originale disponibile per visualizzazione o scarico.'
          : 'Allegato conservato nel controllo PEC.',
      }
    }),
    pecAudit: audit,
    actions: {
      inbox: '/email/',
      reply: '/email/scrivi',
      settings: '/impostazioni?tab=pec',
    },
  }
}

export function getEmailPecEmbeddedSourceDetail(id: string): EmailDetailData | null {
  if (!id || typeof document === 'undefined') return null
  const element = document.getElementById('iusentra-react-bootstrap')
  if (!element?.textContent) return null
  try {
    const parsed = JSON.parse(element.textContent) as unknown
    const root = isRecord(parsed) ? parsed : {}
    const source = isRecord(root.embeddedSourceDetail) ? root.embeddedSourceDetail : {}
    if (text(source.mode) !== 'pec') return null
    if (text(source.sourceId) !== id) return null
    const data = isRecord(source.data) ? source.data : {}
    return auditDetailFromPayload({ data })
  } catch {
    return null
  }
}

async function fetchPecAuditDetail(id: string): Promise<EmailDetailData> {
  const pecId = id.replace(/^pec-audit:/, '')
  try {
    const response = await fetch(`/api/pec/messages/${encodeURIComponent(pecId)}?_ts=${Date.now()}`, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return emptyDetailFor('/email')
    return auditDetailFromPayload(await response.json())
  } catch {
    return emptyDetailFor('/email')
  }
}

const pecSourceRetryStatuses = new Set([423, 429, 500, 503])

function sleepPecSourceRetry(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function fetchPecAuditSourceDetail(id: string): Promise<EmailDetailData> {
  const pecId = id.replace(/^pec-audit:/, '')
  for (let attempt = 0; attempt < 3; attempt += 1) {
    let timeout: ReturnType<typeof setTimeout> | undefined
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
    if (controller) {
      timeout = setTimeout(() => controller.abort(), 8000)
    }
    try {
      const response = await fetch(`/api/pec/messages/${encodeURIComponent(pecId)}/source?_ts=${Date.now()}`, {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: controller?.signal,
      })
      if (response.ok) return auditDetailFromPayload(await response.json())
      if (!pecSourceRetryStatuses.has(response.status) || attempt === 2) return emptyDetailFor('/email')
    } catch {
      if (attempt === 2) return emptyDetailFor('/email')
    } finally {
      if (timeout) clearTimeout(timeout)
    }
    await sleepPecSourceRetry(450 + attempt * 550)
  }
  return emptyDetailFor('/email')
}

export function folderLabel(value: EmailFolder): string {
  if (value === 'INVIATI') return 'Inviati'
  if (value === 'CESTINO') return 'Cestino'
  return 'In arrivo'
}

export function folderParam(value: EmailFolder): string {
  return value
}

async function fetchEmailPage(endpoint: string, fallback: EmailPecPageData, params: EmailPecParams = {}): Promise<EmailPecPageData> {
  const query = new URLSearchParams()
  if (params.folder) query.set('cartella', folderParam(params.folder))
  if (params.q?.trim()) query.set('q', params.q.trim())
  if (params.stato && params.stato !== 'tutti') query.set('stato', params.stato)
  if (params.pst) query.set('pst', '1')
  if (params.conAllegati) query.set('con_allegati', '1')
  if (params.statoPct) query.set('stato_pct', params.statoPct)
  query.set('_ts', String(Date.now()))
  try {
    const url = `${endpoint}${query.toString() ? `?${query.toString()}` : ''}`
    const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } })
    if (!response.ok) return fallback
    return normalisePayload(await response.json(), fallback)
  } catch {
    return fallback
  }
}

export async function getEmailPecPage(params: EmailPecParams = {}): Promise<EmailPecPageData> {
  return fetchEmailPage('/api/v1/ui/email', emptyEmailPecPage, params)
}

export async function getEmailOrdinariaPage(params: EmailPecParams = {}): Promise<EmailPecPageData> {
  return fetchEmailPage('/api/v1/ui/email-ordinaria', emptyEmailOrdinariaPage, params)
}

export async function getEmailPecDetail(id: string): Promise<EmailDetailData> {
  if (id.startsWith('pec-audit:')) return fetchPecAuditDetail(id)
  return fetchEmailDetail(`/api/v1/ui/email/messaggio/${encodeURIComponent(id)}`, '/email')
}

export async function getEmailPecSourceDetail(id: string): Promise<EmailDetailData> {
  if (id.startsWith('pec-audit:')) return fetchPecAuditSourceDetail(id)
  return fetchEmailDetail(`/api/v1/ui/email/messaggio/${encodeURIComponent(id)}`, '/email')
}

export async function getEmailOrdinariaDetail(id: string): Promise<EmailDetailData> {
  return fetchEmailDetail(`/api/v1/ui/email-ordinaria/messaggio/${encodeURIComponent(id)}`, '/email-ordinaria')
}

export async function submitEmailBulkAction(
  endpoint: string,
  ids: string[],
  action: 'trash' | 'delete',
): Promise<string> {
  if (!endpoint) throw new Error('Azione multipla non disponibile in questa casella.')
  const response = await fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify({ ids, action }),
  })
  let payload: Record<string, unknown> = {}
  try {
    payload = await response.json() as Record<string, unknown>
  } catch {
    payload = {}
  }
  if (!response.ok || payload.ok === false) {
    throw new Error(text(payload.message ?? payload.errore, 'Operazione multipla non completata.'))
  }
  return text(payload.message, 'Operazione multipla completata.')
}
