import type { Tone } from './data'

export type EmailFolder = 'INBOX' | 'INVIATI' | 'CESTINO'
export type EmailStatus = 'tutti' | 'NON_LETTA' | 'LETTA' | 'CESTINO'

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
    autoEsiti: string
    operationalInbox: string
    localPecTest: string
    lex: string
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
    autoEsiti: '/email/auto-esiti',
    operationalInbox: '/email/',
    localPecTest: '/email/impostazioni',
    lex: '/lex?context=email-pec',
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
    compose: '/email/scrivi',
    settings: '/impostazioni?tab=smtp',
    sync: '/email-ordinaria/sincronizza',
    autoEsiti: '',
    operationalInbox: '/email-ordinaria/',
    localPecTest: '/impostazioni?tab=smtp',
    lex: '/lex?context=email-ordinaria',
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

function rowFromPayload(value: unknown, index: number, fallbackBasePath = '/email'): EmailPecRow {
  const item = isRecord(value) ? value : {}
  const id = text(item.id, `email-${index}`)
  const folder = normaliseFolder(item.folder ?? item.cartella)
  const isPst = bool(item.isPst ?? item.is_pst ?? item.e_pst)
  const pctStatus = text(item.pctStatus ?? item.pct_status ?? item.stato_pct)
  const unread = bool(item.unread ?? item.non_letta) || text(item.status ?? item.stato) === 'NON_LETTA'
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
    replyHref: text(item.replyHref ?? item.reply_href, `/email/scrivi?oggetto=${encodeURIComponent(`Re: ${text(item.subject ?? item.oggetto)}`)}`),
    trashHref: text(item.trashHref ?? item.trash_href, `${fallbackBasePath}/${encodeURIComponent(id)}/cestino`),
    restoreHref: text(item.restoreHref ?? item.restore_href, `${fallbackBasePath}/${encodeURIComponent(id)}/ripristina`),
    deleteHref: text(item.deleteHref ?? item.delete_href, `${fallbackBasePath}/${encodeURIComponent(id)}/elimina`),
    markReadHref: text(item.markReadHref ?? item.mark_read_href, `${fallbackBasePath}/${encodeURIComponent(id)}/segna-letta`),
    markUnreadHref: text(item.markUnreadHref ?? item.mark_unread_href, `${fallbackBasePath}/${encodeURIComponent(id)}/segna-non-letta`),
    tone: normaliseTone(item.tone, item),
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
      autoEsiti: text(actions.autoEsiti ?? actions.auto_esiti, fallback.actions.autoEsiti),
      operationalInbox: text(actions.operationalInbox ?? actions.operational_inbox, fallback.actions.operationalInbox),
      localPecTest: text(actions.localPecTest ?? actions.local_pec_test, fallback.actions.localPecTest),
      lex: text(actions.lex, fallback.actions.lex),
    },
  }
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
