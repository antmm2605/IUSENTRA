import type { Tone } from './data'

export type MessageChannel = 'EMAIL' | 'SMS' | 'WHATSAPP'

export type RegistryOption = {
  value: string
  label: string
  subtitle?: string
  tone?: Tone
  count?: number
}

export type ChannelInfo = RegistryOption & {
  value: MessageChannel
  available: boolean
  configured: boolean
  destinationPlaceholder: string
  destinationHelp: string
  subjectVisible: boolean
  maxLength?: number
}

export type ClientOption = {
  id: string
  label: string
  fiscalId?: string
  email?: string
  phone?: string
}

export type MessageItem = {
  id: string
  channel: MessageChannel
  channelLabel: string
  recipientName: string
  recipient: string
  destination: string
  subject: string
  body: string
  preview: string
  status: string
  statusLabel: string
  tone: Tone
  createdAt: string
  createdLabel: string
  sentLabel: string
  automationLabel: string
  clientLabel: string
  clientHref: string
  detailHref: string
  whatsappLink: string
  error: string
  note: string
  initials: string
  manualWhatsapp: boolean
}

export type MessageTemplate = {
  id: string
  label: string
  subject: string
  body: string
  channel?: MessageChannel | 'ALL'
}

export type MessaggiSummary = {
  total: number
  sent: number
  queued: number
  delivered: number
  read: number
  failed: number
  cancelled: number
  email: number
  sms: number
  whatsapp: number
  recent: number
  manualWhatsapp: number
}

export type MessaggiData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes: string }
  summary: MessaggiSummary
  items: MessageItem[]
  facets: { channels: RegistryOption[]; statuses: RegistryOption[] }
  filters: { q: string; channel: string; status: string }
  actions: { newMessage: string; sendEndpoint: string; settings: string; emailSettings: string }
  channelInfo: ChannelInfo[]
  lex: string[]
}

export type NuovoMessaggioData = {
  source: string
  generatedAt: string
  contracts: { mock_fallback: boolean; read_only: boolean; writes: string }
  channelInfo: ChannelInfo[]
  clientOptions: ClientOption[]
  templates: MessageTemplate[]
  query: { channel: MessageChannel; idCliente: string; fromCliente: string }
  actions: { messagesList: string; sendEndpoint: string; clientFolder: string }
  insights: string[]
}

const defaultSummary: MessaggiSummary = {
  total: 0,
  sent: 0,
  queued: 0,
  delivered: 0,
  read: 0,
  failed: 0,
  cancelled: 0,
  email: 0,
  sms: 0,
  whatsapp: 0,
  recent: 0,
  manualWhatsapp: 0,
}

export const defaultChannelInfo: ChannelInfo[] = [
  {
    value: 'EMAIL',
    label: 'Email',
    subtitle: 'SMTP configurato nello studio',
    tone: 'primary',
    count: 0,
    available: true,
    configured: false,
    destinationPlaceholder: 'cliente@esempio.it',
    destinationHelp: 'Indirizzo email del destinatario',
    subjectVisible: true,
  },
  {
    value: 'SMS',
    label: 'SMS',
    subtitle: 'Numero in formato E.164',
    tone: 'success',
    count: 0,
    available: true,
    configured: false,
    destinationPlaceholder: '+39 333 1234567',
    destinationHelp: 'Numero di telefono in formato internazionale',
    subjectVisible: false,
    maxLength: 160,
  },
  {
    value: 'WHATSAPP',
    label: 'WhatsApp',
    subtitle: 'API Twilio o link WhatsApp Web',
    tone: 'success',
    count: 0,
    available: true,
    configured: false,
    destinationPlaceholder: '+39 333 1234567',
    destinationHelp: 'Se Twilio non è configurato viene generato un link WhatsApp Web',
    subjectVisible: false,
  },
]

export const defaultTemplates: MessageTemplate[] = [
  {
    id: 'aggiornamento-pratica',
    label: 'Aggiornamento pratica',
    channel: 'ALL',
    subject: 'Aggiornamento sulla pratica',
    body: 'Gentile {nome},\n\nla informiamo che la Sua pratica è stata aggiornata. Restiamo a disposizione per ogni chiarimento.\n\nCordiali saluti',
  },
  {
    id: 'richiesta-documenti',
    label: 'Richiesta documenti',
    channel: 'ALL',
    subject: 'Richiesta documentazione',
    body: 'Gentile {nome},\n\nper proseguire abbiamo necessità della seguente documentazione:\n- documento di identità\n- codice fiscale\n- documenti relativi alla pratica\n\nPuò inviarli rispondendo a questo messaggio.',
  },
  {
    id: 'promemoria-appuntamento',
    label: 'Promemoria appuntamento',
    channel: 'ALL',
    subject: 'Promemoria appuntamento',
    body: 'Gentile {nome},\n\nle ricordiamo l’appuntamento presso lo Studio. Per modifiche o conferme può rispondere a questo messaggio.\n\nGrazie',
  },
]

export const emptyMessaggiData: MessaggiData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes' },
  summary: defaultSummary,
  items: [],
  facets: {
    channels: [{ value: '', label: 'Tutti i canali', count: 0 }, ...defaultChannelInfo.map(({ value, label, tone }) => ({ value, label, tone, count: 0 }))],
    statuses: [{ value: '', label: 'Tutti gli stati', count: 0 }],
  },
  filters: { q: '', channel: '', status: '' },
  actions: { newMessage: '/messaggi/nuovo', sendEndpoint: '/messaggi/nuovo', settings: '/impostazioni', emailSettings: '/email/impostazioni' },
  channelInfo: defaultChannelInfo,
  lex: [
    'Prima dell’invio controlla destinatario, cliente collegato e canale corretto.',
    'Per WhatsApp senza Twilio usa il link manuale e verifica che il messaggio risulti in coda.',
  ],
}

export const emptyNuovoMessaggioData: NuovoMessaggioData = {
  source: 'vuoto',
  generatedAt: '',
  contracts: { mock_fallback: false, read_only: true, writes: 'operational_routes' },
  channelInfo: defaultChannelInfo,
  clientOptions: [],
  templates: defaultTemplates,
  query: { channel: 'EMAIL', idCliente: '', fromCliente: '' },
  actions: { messagesList: '/messaggi', sendEndpoint: '/messaggi/nuovo', clientFolder: '' },
  insights: [
    'Il messaggio viene inviato dal servizio operativo dello studio, mantenendo validazioni, tracciamento e alternativa WhatsApp Web.',
    'Se selezioni un cliente, email o telefono vengono precompilati in base al canale.',
  ],
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

function tone(value: unknown, fallback: Tone = 'neutral'): Tone {
  const raw = text(value, fallback)
  return ['primary', 'info', 'success', 'warning', 'danger', 'purple', 'orange', 'neutral'].includes(raw) ? raw as Tone : fallback
}

function channel(value: unknown): MessageChannel {
  const raw = text(value, 'EMAIL').toUpperCase()
  return raw === 'SMS' || raw === 'WHATSAPP' ? raw : 'EMAIL'
}

function optionsFrom(value: unknown, fallback: RegistryOption[]): RegistryOption[] {
  if (!Array.isArray(value)) return fallback
  const rows = value.filter(isRecord).map((item) => ({
    value: text(item.value),
    label: text(item.label ?? item.value),
    subtitle: item.subtitle === undefined ? undefined : text(item.subtitle),
    tone: item.tone === undefined ? undefined : tone(item.tone),
    count: item.count === undefined ? undefined : number(item.count),
  })).filter((item) => item.label)
  return rows.length ? rows : fallback
}

function channelInfoFrom(value: unknown): ChannelInfo[] {
  if (!Array.isArray(value)) return defaultChannelInfo
  const rows = value.filter(isRecord).map((item) => {
    const base = defaultChannelInfo.find((info) => info.value === channel(item.value)) || defaultChannelInfo[0]
    return {
      ...base,
      value: channel(item.value),
      label: text(item.label, base.label),
      subtitle: text(item.subtitle, base.subtitle),
      tone: tone(item.tone, base.tone || 'neutral'),
      count: item.count === undefined ? base.count : number(item.count),
      available: item.available !== false,
      configured: Boolean(item.configured),
      destinationPlaceholder: text(item.destinationPlaceholder ?? item.destination_placeholder, base.destinationPlaceholder),
      destinationHelp: text(item.destinationHelp ?? item.destination_help, base.destinationHelp),
      subjectVisible: item.subjectVisible === undefined ? base.subjectVisible : Boolean(item.subjectVisible),
      maxLength: item.maxLength === undefined && item.max_length === undefined ? base.maxLength : number(item.maxLength ?? item.max_length),
    }
  })
  return rows.length ? rows : defaultChannelInfo
}

function clientOptionsFrom(value: unknown): ClientOption[] {
  if (!Array.isArray(value)) return []
  return value.filter(isRecord).map((item, index) => ({
    id: text(item.id, `cliente-${index}`),
    label: text(item.label ?? item.nome_completo ?? item.name, 'Cliente senza nome'),
    fiscalId: text(item.fiscalId ?? item.fiscal_id ?? item.codice_fiscale ?? item.partita_iva),
    email: text(item.email),
    phone: text(item.phone ?? item.telefono ?? item.cellulare),
  })).filter((item) => item.id)
}

function templatesFrom(value: unknown): MessageTemplate[] {
  if (!Array.isArray(value)) return defaultTemplates
  const rows = value.filter(isRecord).map((item, index) => {
    const templateChannel: MessageTemplate['channel'] = item.channel === 'SMS' || item.channel === 'WHATSAPP' || item.channel === 'EMAIL' ? item.channel : 'ALL'
    return {
      id: text(item.id, `template-${index}`),
      label: text(item.label, 'Template'),
      subject: text(item.subject),
      body: text(item.body),
      channel: templateChannel,
    }
  }).filter((item) => item.body)
  return rows.length ? rows : defaultTemplates
}

function itemFrom(value: unknown, index: number): MessageItem | null {
  if (!isRecord(value)) return null
  const itemChannel = channel(value.channel ?? value.canale)
  const status = text(value.status ?? value.stato, 'IN_CODA')
  const recipientName = text(value.recipientName ?? value.recipient_name ?? value.nome_destinatario)
  const destination = text(value.destination ?? value.destinatario ?? value.email_destinatario ?? value.telefono_destinatario)
  const subject = text(value.subject ?? value.oggetto)
  const body = text(value.body ?? value.corpo)
  return {
    id: text(value.id, `messaggio-${index}`),
    channel: itemChannel,
    channelLabel: text(value.channelLabel ?? value.channel_label, itemChannel === 'WHATSAPP' ? 'WhatsApp' : itemChannel),
    recipientName,
    recipient: text(value.recipient ?? value.destinatario, recipientName || destination || 'Destinatario non indicato'),
    destination,
    subject,
    body,
    preview: text(value.preview, subject || body || 'Messaggio senza testo'),
    status,
    statusLabel: text(value.statusLabel ?? value.status_label, status.replace(/_/g, ' ')),
    tone: tone(value.tone),
    createdAt: text(value.createdAt ?? value.created_at ?? value.creato_il),
    createdLabel: text(value.createdLabel ?? value.created_label),
    sentLabel: text(value.sentLabel ?? value.sent_label),
    automationLabel: text(value.automationLabel ?? value.automation_label),
    clientLabel: text(value.clientLabel ?? value.client_label),
    clientHref: text(value.clientHref ?? value.client_href),
    detailHref: text(value.detailHref ?? value.detail_href, `/messaggi/${text(value.id, '')}`),
    whatsappLink: text(value.whatsappLink ?? value.whatsapp_link),
    error: text(value.error ?? value.errore),
    note: text(value.note),
    initials: text(value.initials, (recipientName || destination || itemChannel).slice(0, 2).toUpperCase()),
    manualWhatsapp: Boolean(value.manualWhatsapp ?? value.manual_whatsapp),
  }
}

function summaryFrom(value: unknown): MessaggiSummary {
  if (!isRecord(value)) return defaultSummary
  return {
    total: number(value.total ?? value.totale),
    sent: number(value.sent ?? value.inviati),
    queued: number(value.queued ?? value.in_coda),
    delivered: number(value.delivered ?? value.consegnati),
    read: number(value.read ?? value.letti),
    failed: number(value.failed ?? value.falliti),
    cancelled: number(value.cancelled ?? value.annullati),
    email: number(value.email),
    sms: number(value.sms),
    whatsapp: number(value.whatsapp),
    recent: number(value.recent ?? value.recenti),
    manualWhatsapp: number(value.manualWhatsapp ?? value.manual_whatsapp),
  }
}

function mergeMessaggiPayload(payload: unknown): MessaggiData {
  if (!isRecord(payload)) return emptyMessaggiData
  const facets = isRecord(payload.facets) ? payload.facets : {}
  const filters = isRecord(payload.filters) ? payload.filters : {}
  const actions = isRecord(payload.actions) ? payload.actions : {}
  return {
    ...emptyMessaggiData,
    source: text(payload.source, emptyMessaggiData.source),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: isRecord(payload.contracts) ? {
      mock_fallback: Boolean(payload.contracts.mock_fallback),
      read_only: payload.contracts.read_only !== false,
      writes: text(payload.contracts.writes, emptyMessaggiData.contracts.writes),
    } : emptyMessaggiData.contracts,
    summary: summaryFrom(payload.summary ?? payload.stats),
    items: Array.isArray(payload.items) ? payload.items.map(itemFrom).filter(Boolean) as MessageItem[] : [],
    facets: {
      channels: optionsFrom(facets.channels, emptyMessaggiData.facets.channels),
      statuses: optionsFrom(facets.statuses, emptyMessaggiData.facets.statuses),
    },
    filters: { q: text(filters.q), channel: text(filters.channel ?? filters.canale), status: text(filters.status ?? filters.stato) },
    actions: {
      newMessage: text(actions.newMessage ?? actions.new_message, emptyMessaggiData.actions.newMessage),
      sendEndpoint: text(actions.sendEndpoint ?? actions.send_endpoint, emptyMessaggiData.actions.sendEndpoint),
      settings: text(actions.settings, emptyMessaggiData.actions.settings),
      emailSettings: text(actions.emailSettings ?? actions.email_settings, emptyMessaggiData.actions.emailSettings),
    },
    channelInfo: channelInfoFrom(payload.channelInfo ?? payload.channel_info),
    lex: Array.isArray(payload.lex) ? payload.lex.map((item) => text(item)).filter(Boolean) : emptyMessaggiData.lex,
  }
}

function mergeNuovoPayload(payload: unknown): NuovoMessaggioData {
  if (!isRecord(payload)) return emptyNuovoMessaggioData
  const query = isRecord(payload.query) ? payload.query : {}
  const actions = isRecord(payload.actions) ? payload.actions : {}
  return {
    ...emptyNuovoMessaggioData,
    source: text(payload.source, emptyNuovoMessaggioData.source),
    generatedAt: text(payload.generatedAt ?? payload.generated_at),
    contracts: isRecord(payload.contracts) ? {
      mock_fallback: Boolean(payload.contracts.mock_fallback),
      read_only: payload.contracts.read_only !== false,
      writes: text(payload.contracts.writes, emptyNuovoMessaggioData.contracts.writes),
    } : emptyNuovoMessaggioData.contracts,
    channelInfo: channelInfoFrom(payload.channelInfo ?? payload.channel_info),
    clientOptions: clientOptionsFrom(payload.clientOptions ?? payload.client_options),
    templates: templatesFrom(payload.templates),
    query: {
      channel: channel(query.channel ?? query.canale),
      idCliente: text(query.idCliente ?? query.id_cliente),
      fromCliente: text(query.fromCliente ?? query.from_cliente),
    },
    actions: {
      messagesList: text(actions.messagesList ?? actions.messages_list, emptyNuovoMessaggioData.actions.messagesList),
      sendEndpoint: text(actions.sendEndpoint ?? actions.send_endpoint, emptyNuovoMessaggioData.actions.sendEndpoint),
      clientFolder: text(actions.clientFolder ?? actions.client_folder),
    },
    insights: Array.isArray(payload.insights) ? payload.insights.map((item) => text(item)).filter(Boolean) : emptyNuovoMessaggioData.insights,
  }
}

export async function getMessaggiData(): Promise<MessaggiData> {
  try {
    const search = typeof window !== 'undefined' ? window.location.search : ''
    const response = await fetch(`/api/v1/ui/messaggi${search}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptyMessaggiData
    return mergeMessaggiPayload(await response.json())
  } catch {
    return emptyMessaggiData
  }
}

export async function getNuovoMessaggioData(): Promise<NuovoMessaggioData> {
  try {
    const search = typeof window !== 'undefined' ? window.location.search : ''
    const response = await fetch(`/api/v1/ui/messaggi/nuovo${search}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!response.ok) return emptyNuovoMessaggioData
    return mergeNuovoPayload(await response.json())
  } catch {
    return emptyNuovoMessaggioData
  }
}
